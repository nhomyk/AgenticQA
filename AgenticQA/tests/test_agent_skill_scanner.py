"""
Unit tests for AgentSkillScanner — AST-based custom agent skill security scanner.

Covers:
- Detection of all dangerous patterns (COMMAND_INJECTION, SSRF_RISK,
  AMBIENT_AUTHORITY, GOVERNANCE_BYPASS)
- Risk score accumulation and cap
- is_safe property
- scan_source() and scan_directory() convenience methods
- Syntax error handling
- Pre-scan gate in run_custom_agents.pre_scan_agent()
- Structural fixes: path canonicalization, runtime registrations
"""
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agenticqa.security.agent_skill_scanner import (
    AgentSkillScanner,
    SkillScanResult,
    SkillFinding,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _scan(source: str) -> SkillScanResult:
    return AgentSkillScanner().scan_source(source, filename="<test>")


def _attack_types(result: SkillScanResult):
    return [f.attack_type for f in result.findings]


def _severities(result: SkillScanResult):
    return [f.severity for f in result.findings]


# ---------------------------------------------------------------------------
# Clean agent
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_clean_agent_no_findings():
    code = '''
def run(context: dict) -> dict:
    """Safe agent — just returns context keys."""
    return {"keys": list(context.keys()), "status": "ok"}
'''
    result = _scan(code)
    assert result.findings == []
    assert result.risk_score == 0.0
    assert result.parse_error is None
    assert result.is_safe is True


# ---------------------------------------------------------------------------
# COMMAND_INJECTION detections
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_eval_detected():
    result = _scan("def run(ctx): return eval(ctx['x'])")
    assert "COMMAND_INJECTION" in _attack_types(result)
    assert "critical" in _severities(result)
    assert result.is_safe is False


@pytest.mark.unit
def test_exec_detected():
    result = _scan("def run(ctx):\n    exec(ctx['code'])\n    return {}")
    assert "COMMAND_INJECTION" in _attack_types(result)
    assert "critical" in _severities(result)


@pytest.mark.unit
def test_compile_detected():
    result = _scan("def run(ctx): return compile(ctx['src'], '<str>', 'exec')")
    assert "COMMAND_INJECTION" in _attack_types(result)


@pytest.mark.unit
def test_subprocess_import_detected():
    code = "import subprocess\ndef run(ctx): return {}"
    result = _scan(code)
    assert "COMMAND_INJECTION" in _attack_types(result)
    assert "critical" in _severities(result)


@pytest.mark.unit
def test_os_system_detected():
    code = "import os\ndef run(ctx):\n    os.system(ctx['cmd'])\n    return {}"
    result = _scan(code)
    assert "COMMAND_INJECTION" in _attack_types(result)
    assert "critical" in _severities(result)


@pytest.mark.unit
def test_pickle_import_detected():
    code = "import pickle\ndef run(ctx): return {}"
    result = _scan(code)
    assert "COMMAND_INJECTION" in _attack_types(result)
    assert any(f.severity == "high" for f in result.findings
               if f.attack_type == "COMMAND_INJECTION")


@pytest.mark.unit
def test_dunder_import_detected():
    code = "def run(ctx):\n    mod = __import__(ctx['mod'])\n    return {}"
    result = _scan(code)
    assert "COMMAND_INJECTION" in _attack_types(result)


@pytest.mark.unit
def test_globals_dunder_detected():
    code = "def run(ctx):\n    g = ctx.__globals__\n    return {}"
    result = _scan(code)
    assert "COMMAND_INJECTION" in _attack_types(result)
    assert "critical" in _severities(result)


@pytest.mark.unit
def test_ctypes_import_detected():
    code = "import ctypes\ndef run(ctx): return {}"
    result = _scan(code)
    assert "COMMAND_INJECTION" in _attack_types(result)


# ---------------------------------------------------------------------------
# SSRF_RISK detections
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_socket_import_detected():
    code = "import socket\ndef run(ctx): return {}"
    result = _scan(code)
    assert "SSRF_RISK" in _attack_types(result)
    assert any(f.severity == "high" for f in result.findings
               if f.attack_type == "SSRF_RISK")


@pytest.mark.unit
def test_requests_import_detected():
    code = "import requests\ndef run(ctx): return {}"
    result = _scan(code)
    assert "SSRF_RISK" in _attack_types(result)
    assert any(f.severity == "medium" for f in result.findings
               if f.attack_type == "SSRF_RISK")


@pytest.mark.unit
def test_cloud_metadata_ip_detected():
    code = '''
def run(ctx):
    url = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
    return {"url": url}
'''
    result = _scan(code)
    assert "SSRF_RISK" in _attack_types(result)
    assert any(f.severity == "critical" for f in result.findings
               if f.attack_type == "SSRF_RISK")


# ---------------------------------------------------------------------------
# AMBIENT_AUTHORITY detections
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_open_write_mode_detected():
    code = '''
def run(ctx):
    with open("/etc/evil", "w") as f:
        f.write("injected")
    return {}
'''
    result = _scan(code)
    assert "AMBIENT_AUTHORITY" in _attack_types(result)


@pytest.mark.unit
def test_open_append_mode_detected():
    code = 'def run(ctx): open("log", "a").write("x"); return {}'
    result = _scan(code)
    assert "AMBIENT_AUTHORITY" in _attack_types(result)


@pytest.mark.unit
def test_open_read_mode_not_flagged():
    """Reading files is low-risk — only write modes should be flagged."""
    code = 'def run(ctx): data = open("readme.txt", "r").read(); return {"data": data}'
    result = _scan(code)
    assert "AMBIENT_AUTHORITY" not in _attack_types(result)


# ---------------------------------------------------------------------------
# GOVERNANCE_BYPASS detection
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_governance_bypass_from_import():
    code = '''
from agenticqa.constitutional_gate import check_action
def run(ctx):
    result = check_action("run_agents", {"ci_status": "PASSED"})
    return {}
'''
    result = _scan(code)
    assert "GOVERNANCE_BYPASS" in _attack_types(result)
    assert "critical" in _severities(result)
    assert result.is_safe is False


@pytest.mark.unit
def test_governance_bypass_import():
    code = '''
import agenticqa.constitutional_wrapper
def run(ctx): return {}
'''
    result = _scan(code)
    assert "GOVERNANCE_BYPASS" in _attack_types(result)


# ---------------------------------------------------------------------------
# Risk score and is_safe
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_risk_score_nonzero_on_critical_finding():
    result = _scan("eval(x)")
    assert result.risk_score >= 0.4


@pytest.mark.unit
def test_risk_score_caps_at_1():
    """Multiple critical findings should not push risk_score above 1.0."""
    code = '''
import subprocess
eval(x)
exec(y)
import ctypes
import socket
url = "http://169.254.169.254"
'''
    result = _scan(code)
    assert result.risk_score == 1.0


@pytest.mark.unit
def test_is_safe_false_on_critical():
    result = _scan("exec('rm -rf /')")
    assert result.is_safe is False


@pytest.mark.unit
def test_is_safe_true_clean_agent():
    code = "def run(ctx):\n    return {'status': 'ok'}"
    result = _scan(code)
    assert result.is_safe is True


# ---------------------------------------------------------------------------
# scan_source and scan_directory
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_scan_source_method():
    result = AgentSkillScanner().scan_source("eval(x)", filename="evil.py")
    assert result.path == "evil.py"
    assert "COMMAND_INJECTION" in _attack_types(result)


@pytest.mark.unit
def test_syntax_error_handled():
    result = _scan("def run(ctx):\n    return {invalid python!!")
    assert result.parse_error is not None
    assert result.is_safe is False
    assert result.findings == []


@pytest.mark.unit
def test_scan_directory(tmp_path: Path):
    """scan_directory() returns one result per .py file."""
    (tmp_path / "clean_agent.py").write_text(
        "def run(ctx): return {'ok': True}\n"
    )
    (tmp_path / "evil_agent.py").write_text(
        "import subprocess\ndef run(ctx): return {}\n"
    )
    results = AgentSkillScanner().scan_directory(tmp_path)
    assert len(results) == 2
    by_name = {Path(r.path).name: r for r in results}
    assert by_name["clean_agent.py"].is_safe is True
    assert by_name["evil_agent.py"].is_safe is False


@pytest.mark.unit
def test_scan_directory_empty(tmp_path: Path):
    results = AgentSkillScanner().scan_directory(tmp_path)
    assert results == []


@pytest.mark.unit
def test_to_dict_shape():
    result = _scan("import subprocess\ndef run(ctx): return {}")
    d = result.to_dict()
    assert "path" in d
    assert "is_safe" in d
    assert "risk_score" in d
    assert "findings" in d
    assert isinstance(d["findings"], list)
    assert d["findings"][0]["attack_type"] == "COMMAND_INJECTION"


# ---------------------------------------------------------------------------
# Pre-scan gate in run_custom_agents
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_run_agent_blocked_by_scanner(tmp_path: Path):
    """run_agent() returns status='blocked' when pre-scan finds critical issues."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import run_custom_agents as rca

    evil = tmp_path / "evil_agent.py"
    evil.write_text("import subprocess\ndef run(ctx): return {}\n")

    result = rca.run_agent(evil, {"test": True}, skip_scan=False)
    assert result["status"] == "blocked"
    assert "scan_findings" in result


@pytest.mark.unit
def test_run_agent_skip_scan_loads_module(tmp_path: Path):
    """With skip_scan=True, a dangerous agent is still attempted (warning bypassed)."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import run_custom_agents as rca

    agent = tmp_path / "safe_agent.py"
    agent.write_text("def run(ctx): return {'ok': True}\n")

    result = rca.run_agent(agent, {"key": "val"}, skip_scan=True)
    assert result["status"] == "success"
    assert result["output"]["ok"] is True


# ---------------------------------------------------------------------------
# Structural fix: path canonicalization in constitutional_gate
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_path_traversal_blocked():
    """
    A path like tests/../src/constitutional_gate.py should NOT match tests/**
    after normpath canonicalization.
    """
    from agenticqa.constitutional_gate import _path_matches

    # Without canonicalization this would match tests/** (false positive)
    assert _path_matches(
        "tests/../src/constitutional_gate.py", "tests/**"
    ) is False


@pytest.mark.unit
def test_path_within_scope_still_matches():
    """Legitimate paths within scope still match after canonicalization."""
    from agenticqa.constitutional_gate import _path_matches

    assert _path_matches("tests/unit/test_foo.py", "tests/**") is True


# ---------------------------------------------------------------------------
# Structural fix: runtime registrations protect core TASK_AGENT_MAP
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_runtime_registration_does_not_mutate_core_map():
    """register_agent_task() adds to _RUNTIME_REGISTRATIONS, not TASK_AGENT_MAP."""
    from agenticqa.delegation.guardrails import (
        DelegationGuardrails, register_agent_task, _RUNTIME_REGISTRATIONS,
    )
    task_type = "_test_task_unique_12345"
    original_map = dict(DelegationGuardrails.TASK_AGENT_MAP)

    register_agent_task(task_type, "TestAgent")

    # Core map unchanged
    assert DelegationGuardrails.TASK_AGENT_MAP == original_map
    # Runtime registry has the new entry
    assert "TestAgent" in _RUNTIME_REGISTRATIONS.get(task_type, [])

    # Cleanup
    _RUNTIME_REGISTRATIONS.pop(task_type, None)


@pytest.mark.unit
def test_get_allowed_agents_merges_core_and_runtime():
    """get_allowed_agents() returns core + runtime entries merged."""
    from agenticqa.delegation.guardrails import (
        register_agent_task, get_allowed_agents, _RUNTIME_REGISTRATIONS,
    )
    task_type = "_test_merge_task_99999"
    register_agent_task(task_type, "NewFactoryAgent")

    allowed = get_allowed_agents(task_type)
    assert "NewFactoryAgent" in allowed

    # Cleanup
    _RUNTIME_REGISTRATIONS.pop(task_type, None)
