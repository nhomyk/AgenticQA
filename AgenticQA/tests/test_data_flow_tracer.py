"""Unit tests for CrossAgentDataFlowTracer — @pytest.mark.unit"""
import pytest
from pathlib import Path

from agenticqa.security.data_flow_tracer import (
    CrossAgentDataFlowTracer,
    DataFlowReport,
    DataFlowFinding,
)


def make_tracer() -> CrossAgentDataFlowTracer:
    return CrossAgentDataFlowTracer()


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Taint source detection
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestTaintSources:
    def test_os_environ_secret_detected(self, tmp_path):
        write(tmp_path / "agent.py",
              "class DataAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        password = os.environ['DB_PASSWORD']\n"
              "        return password\n")
        report = make_tracer().trace(str(tmp_path))
        types = {f.finding_type for f in report.findings}
        assert "SECRET_SOURCE" in types

    def test_os_getenv_token_detected(self, tmp_path):
        write(tmp_path / "agent.py",
              "class AuthAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        token = os.getenv('API_TOKEN')\n"
              "        return token\n")
        report = make_tracer().trace(str(tmp_path))
        types = {f.finding_type for f in report.findings}
        assert "SECRET_SOURCE" in types

    def test_sql_pii_query_detected(self, tmp_path):
        write(tmp_path / "agent.py",
              "class DatabaseAgent:\n"
              "    def run(self, cursor):\n"
              "        cursor.execute('SELECT * FROM patients WHERE id = ?', [1])\n"
              "        return cursor.fetchall()\n")
        report = make_tracer().trace(str(tmp_path))
        types = {f.finding_type for f in report.findings}
        assert "PII_SOURCE" in types

    def test_request_ssn_field_detected(self, tmp_path):
        write(tmp_path / "agent.py",
              "class FormAgent:\n"
              "    def run(self, request):\n"
              "        ssn = request.form.get('ssn')\n"
              "        return ssn\n")
        report = make_tracer().trace(str(tmp_path))
        types = {f.finding_type for f in report.findings}
        assert "SECRET_SOURCE" in types or "PII_SOURCE" in types

    def test_clean_agent_no_source(self, tmp_path):
        write(tmp_path / "agent.py",
              "class GreetingAgent:\n"
              "    def run(self, name: str) -> str:\n"
              "        return f'Hello, {name}!'\n")
        report = make_tracer().trace(str(tmp_path))
        types = {f.finding_type for f in report.findings}
        assert "SECRET_SOURCE" not in types
        assert "PII_SOURCE" not in types


# ─────────────────────────────────────────────────────────────────────────────
# Sink detection
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestSinkDetection:
    def test_logging_sink_detected(self, tmp_path):
        write(tmp_path / "agent.py",
              "import logging\n"
              "class DataAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        password = os.environ['DB_PASSWORD']\n"
              "        logging.info(f'Connecting with password: {password}')\n")
        report = make_tracer().trace(str(tmp_path))
        types = {f.finding_type for f in report.findings}
        assert "SINK_LOGGING" in types

    def test_print_sink_detected(self, tmp_path):
        write(tmp_path / "agent.py",
              "class DataAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        api_key = os.environ['API_KEY']\n"
              "        print(f'Using key: {api_key}')\n")
        report = make_tracer().trace(str(tmp_path))
        types = {f.finding_type for f in report.findings}
        assert "SINK_LOGGING" in types

    def test_network_sink_detected(self, tmp_path):
        write(tmp_path / "agent.py",
              "import requests\n"
              "class DataAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        token = os.environ['API_TOKEN']\n"
              "        requests.post('https://api.example.com', json={'token': token})\n")
        report = make_tracer().trace(str(tmp_path))
        types = {f.finding_type for f in report.findings}
        assert "SINK_NETWORK" in types

    def test_file_write_sink_detected(self, tmp_path):
        write(tmp_path / "agent.py",
              "class DataAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        secret = os.environ['SECRET_KEY']\n"
              "        with open('output.txt', 'w') as f:\n"
              "            f.write(secret)\n")
        report = make_tracer().trace(str(tmp_path))
        types = {f.finding_type for f in report.findings}
        assert "SINK_STORAGE" in types

    def test_return_propagation_detected(self, tmp_path):
        write(tmp_path / "agent.py",
              "class DataAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        password = os.environ['DB_PASSWORD']\n"
              "        return {'data': 'ok', 'password': password}\n")
        report = make_tracer().trace(str(tmp_path))
        types = {f.finding_type for f in report.findings}
        assert "TAINT_PROPAGATION" in types


# ─────────────────────────────────────────────────────────────────────────────
# Sanitization detection
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestSanitizationDetection:
    def test_redact_before_log_lowers_severity(self, tmp_path):
        write(tmp_path / "agent.py",
              "import logging, hashlib\n"
              "class DataAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        password = os.environ['DB_PASSWORD']\n"
              "        hashed = hashlib.sha256(password.encode()).hexdigest()\n"
              "        logging.info(f'Hash: {hashed}')\n")
        report = make_tracer().trace(str(tmp_path))
        log_findings = [f for f in report.findings if f.finding_type == "SINK_LOGGING"]
        # Sanitized findings should have lower severity or be marked sanitized
        if log_findings:
            sanitized = [f for f in log_findings if f.sanitized]
            assert sanitized or all(f.severity in ("low", "medium") for f in log_findings)

    def test_masked_literal_recognized(self, tmp_path):
        write(tmp_path / "agent.py",
              "import logging\n"
              "class DataAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        password = os.environ['DB_PASSWORD']\n"
              "        safe = password.replace(password, '***')\n"
              "        logging.info(f'Password: {safe}')\n")
        report = make_tracer().trace(str(tmp_path))
        # Risk score should be lower than without sanitization
        assert report.risk_score < 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Cross-agent delegation taint
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestDelegationTaint:
    def test_tainted_var_in_delegation_flagged(self, tmp_path):
        write(tmp_path / "orchestrator.py",
              "class OrchestratorAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        api_key = os.environ['API_KEY']\n"
              "        result = delegate_to('worker_agent', {'key': api_key})\n"
              "        return result\n")
        report = make_tracer().trace(str(tmp_path))
        types = {f.finding_type for f in report.findings}
        assert "TAINT_PROPAGATION" in types

    def test_initiate_chat_with_tainted_data(self, tmp_path):
        write(tmp_path / "agent.py",
              "import autogen\n"
              "class CoordAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        password = os.environ['DB_PASSWORD']\n"
              "        proxy = autogen.UserProxyAgent('proxy')\n"
              "        proxy.initiate_chat(assistant, message=password)\n")
        report = make_tracer().trace(str(tmp_path))
        types = {f.finding_type for f in report.findings}
        assert "TAINT_PROPAGATION" in types

    def test_crew_kickoff_with_tainted_context(self, tmp_path):
        write(tmp_path / "pipeline.py",
              "from crewai import Crew, Agent\n"
              "class PipelineAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        secret = os.environ['SECRET_KEY']\n"
              "        crew = Crew(agents=[])\n"
              "        crew.kickoff({'secret': secret})\n")
        report = make_tracer().trace(str(tmp_path))
        types = {f.finding_type for f in report.findings}
        assert "TAINT_PROPAGATION" in types

    def test_transfer_to_target_extracted(self, tmp_path):
        write(tmp_path / "agent.py",
              "class RouterAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        token = os.environ['API_TOKEN']\n"
              "        return transfer_to_storage_agent(token)\n")
        report = make_tracer().trace(str(tmp_path))
        delegation = [f for f in report.findings if f.finding_type == "TAINT_PROPAGATION"]
        if delegation:
            assert delegation[0].sink_agent == "storage_agent"


# ─────────────────────────────────────────────────────────────────────────────
# File / path handling
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestFileHandling:
    def test_non_agent_file_skipped(self, tmp_path):
        write(tmp_path / "utils.py",
              "def add(a, b): return a + b\n")
        report = make_tracer().trace(str(tmp_path))
        assert report.files_scanned == 0

    def test_skips_test_directories(self, tmp_path):
        write(tmp_path / "tests" / "agent.py",
              "class TestAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        password = os.environ['DB_PASSWORD']\n"
              "        print(password)\n")
        write(tmp_path / "src" / "agent.py",
              "class RealAgent:\n"
              "    def run(self): return 'safe'\n")
        report = make_tracer().trace(str(tmp_path))
        assert all("tests" not in f.source_file for f in report.findings)

    def test_bad_path_returns_report_with_error(self):
        report = make_tracer().trace("/nonexistent/path/xyz")
        assert isinstance(report, DataFlowReport)
        assert report.scan_error is not None

    def test_multiple_agent_files_analyzed(self, tmp_path):
        write(tmp_path / "agent_a.py",
              "class AgentA:\n"
              "    def run(self):\n"
              "        import os\n"
              "        secret = os.environ['SECRET']\n"
              "        return secret\n")
        write(tmp_path / "agent_b.py",
              "class AgentB:\n"
              "    def run(self):\n"
              "        import os\n"
              "        token = os.environ['API_TOKEN']\n"
              "        return token\n")
        report = make_tracer().trace(str(tmp_path))
        assert report.files_scanned == 2
        assert report.agents_analyzed == 2


# ─────────────────────────────────────────────────────────────────────────────
# Risk score and report structure
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestRiskScoreAndStructure:
    def test_clean_repo_zero_risk(self, tmp_path):
        write(tmp_path / "agent.py",
              "class SafeAgent:\n"
              "    def run(self, name: str) -> str:\n"
              "        return f'Hello {name}'\n")
        report = make_tracer().trace(str(tmp_path))
        assert report.risk_score == 0.0

    def test_credentials_in_log_raises_risk(self, tmp_path):
        write(tmp_path / "agent.py",
              "import logging\n"
              "class DataAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        password = os.environ['DB_PASSWORD']\n"
              "        logging.info(f'password={password}')\n")
        report = make_tracer().trace(str(tmp_path))
        assert report.risk_score > 0.0

    def test_risk_score_capped_at_one(self, tmp_path):
        # Many findings should not exceed 1.0
        lines = ["import logging, os\n", "class DataAgent:\n", "    def run(self):\n"]
        for i in range(20):
            lines.append(f"        secret_{i} = os.environ['SECRET_{i}']\n")
            lines.append(f"        logging.info(secret_{i})\n")
        write(tmp_path / "agent.py", "".join(lines))
        report = make_tracer().trace(str(tmp_path))
        assert report.risk_score <= 1.0

    def test_finding_has_remediation(self, tmp_path):
        write(tmp_path / "agent.py",
              "import logging\n"
              "class DataAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        password = os.environ['DB_PASSWORD']\n"
              "        logging.info(password)\n")
        report = make_tracer().trace(str(tmp_path))
        assert report.findings
        assert all(f.remediation for f in report.findings)

    def test_finding_types_list(self, tmp_path):
        write(tmp_path / "agent.py",
              "import logging\n"
              "class DataAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        password = os.environ['DB_PASSWORD']\n"
              "        logging.info(password)\n")
        report = make_tracer().trace(str(tmp_path))
        assert isinstance(report.finding_types, list)

    def test_trace_hop_populated(self, tmp_path):
        write(tmp_path / "agent.py",
              "class DataAgent:\n"
              "    def run(self):\n"
              "        import os\n"
              "        password = os.environ['DB_PASSWORD']\n"
              "        return password\n")
        report = make_tracer().trace(str(tmp_path))
        assert report.findings
        for f in report.findings:
            assert isinstance(f.trace, list)
            if f.trace:
                hop = f.trace[0]
                assert hop.agent_name
                assert hop.source_file
                assert hop.evidence
