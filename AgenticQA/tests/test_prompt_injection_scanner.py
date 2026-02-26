"""Unit tests for PromptInjectionScanner — @pytest.mark.unit"""
import pytest
from pathlib import Path

from agenticqa.security.prompt_injection_scanner import (
    InjectionFinding,
    InjectionScanResult,
    PromptInjectionScanner,
)


def make_scanner() -> PromptInjectionScanner:
    return PromptInjectionScanner()


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Direct concatenation
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDirectConcatenation:
    def test_fstring_user_input_flagged(self, tmp_path):
        write(tmp_path / "api" / "chat.py",
              'system = f"You are a helpful assistant. User says: {user_input}"\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PROMPT_INJECTION_SURFACE"]
        assert len(hits) >= 1
        assert hits[0].severity == "critical"

    def test_template_literal_user_message(self, tmp_path):
        write(tmp_path / "route.ts",
              'const system = `You are helpful. Context: ${userMessage}`;\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PROMPT_INJECTION_SURFACE"]
        assert len(hits) >= 1

    def test_hardcoded_prompt_no_finding(self, tmp_path):
        write(tmp_path / "agent.py",
              'system = "You are a helpful assistant. Answer concisely."\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PROMPT_INJECTION_SURFACE"]
        assert len(hits) == 0

    def test_env_var_prompt_no_finding(self, tmp_path):
        write(tmp_path / "app.ts",
              'const system = process.env.SYSTEM_PROMPT;\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PROMPT_INJECTION_SURFACE"]
        assert len(hits) == 0


# ---------------------------------------------------------------------------
# Template injection
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTemplateInjection:
    def test_format_call_on_prompt_flagged(self, tmp_path):
        write(tmp_path / "llm.py",
              'prompt = TEMPLATE.format(query=user_query)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "TEMPLATE_INJECTION"]
        assert len(hits) >= 1
        assert hits[0].severity == "high"

    def test_hardcoded_format_no_finding(self, tmp_path):
        write(tmp_path / "util.py",
              'msg = "Hello {}".format("world")\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "TEMPLATE_INJECTION"]
        assert len(hits) == 0


# ---------------------------------------------------------------------------
# Unvalidated LLM output
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestUnvalidatedOutput:
    def test_eval_llm_output_flagged(self, tmp_path):
        write(tmp_path / "executor.py",
              'result = eval(llm_output)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "UNVALIDATED_LLM_OUTPUT"]
        assert len(hits) >= 1
        assert hits[0].severity == "medium"

    def test_subprocess_with_response_flagged(self, tmp_path):
        write(tmp_path / "runner.py",
              'subprocess.run(response, shell=True)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "UNVALIDATED_LLM_OUTPUT"]
        assert len(hits) >= 1

    def test_safe_eval_call_no_finding(self, tmp_path):
        write(tmp_path / "math_util.py",
              'result = eval("2 + 2")\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "UNVALIDATED_LLM_OUTPUT"]
        assert len(hits) == 0


# ---------------------------------------------------------------------------
# System prompt override
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSystemPromptOverride:
    def test_user_controls_role_flagged(self, tmp_path):
        write(tmp_path / "api.ts",
              '{ role: "system", content: userInput }\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "SYSTEM_PROMPT_OVERRIDE"]
        assert len(hits) >= 1
        assert hits[0].severity == "high"

    def test_fixed_role_no_finding(self, tmp_path):
        write(tmp_path / "llm.ts",
              '{ role: "user", content: message }\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "SYSTEM_PROMPT_OVERRIDE"]
        assert len(hits) == 0


# ---------------------------------------------------------------------------
# Surface score + clean repo
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSurfaceScore:
    def test_clean_repo_zero_score(self, tmp_path):
        result = make_scanner().scan(str(tmp_path))
        assert result.surface_score == 0.0
        assert len(result.findings) == 0

    def test_all_critical_score_is_one(self):
        scanner = make_scanner()
        findings = [
            InjectionFinding("a.ts", 1, "PROMPT_INJECTION_SURFACE", "critical", "msg"),
            InjectionFinding("b.ts", 2, "PROMPT_INJECTION_SURFACE", "critical", "msg"),
            InjectionFinding("c.ts", 3, "PROMPT_INJECTION_SURFACE", "critical", "msg"),
        ]
        result = scanner._build_result(findings)
        assert result.surface_score == 1.0

    def test_mixed_severities_score_between(self):
        scanner = make_scanner()
        findings = [
            InjectionFinding("a.ts", 1, "PROMPT_INJECTION_SURFACE", "critical", "msg"),  # 1.0
            InjectionFinding("b.ts", 2, "UNVALIDATED_LLM_OUTPUT", "medium", "msg"),       # 0.4
        ]
        result = scanner._build_result(findings)
        # mean([1.0, 0.4]) = 0.7
        assert abs(result.surface_score - 0.7) < 0.01

    def test_clean_file_no_findings(self, tmp_path):
        write(tmp_path / "utils.py", "def add(a, b):\n    return a + b\n")
        result = make_scanner().scan(str(tmp_path))
        assert result.surface_score == 0.0
        assert result.scan_error is None
