"""Unit tests for POST /api/agent-factory/from-prompt endpoint."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import agent_api
from agenticqa.factory.spec_extractor import AgentSpec


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_base_dependencies():
    """Patch module-level orchestrator and data_pipeline — required by agent_api init."""
    mock_orch = MagicMock()
    mock_orch.agents = {}
    mock_pipeline = MagicMock()
    with patch.object(agent_api, "orchestrator", mock_orch), \
         patch.object(agent_api, "data_pipeline", mock_pipeline):
        yield


@pytest.fixture
def client():
    return TestClient(agent_api.app)


def _make_spec(**overrides) -> AgentSpec:
    defaults = dict(
        agent_name="security_scanner",
        description="Scans Python for vulnerabilities",
        capabilities=["scan_code", "report_findings"],
        framework="sandboxed",
        scope={"file_patterns": ["**/*.py"], "languages": ["python"]},
        checks=["no_secrets", "valid_json_output"],
    )
    defaults.update(overrides)
    return AgentSpec(**defaults)


# ─────────────────────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestFromPromptHappyPath:
    def test_happy_path_returns_200(self, client, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        spec = _make_spec()
        with patch("agent_api.NaturalLanguageSpecExtractor") as mock_cls:
            mock_cls.return_value.extract.return_value = spec
            resp = client.post(
                "/api/agent-factory/from-prompt",
                json={"description": "An agent that scans Python for vulnerabilities", "persist": False},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "spec" in data
        assert "generated_code" in data

    def test_response_spec_matches_extracted_spec(self, client, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        spec = _make_spec()
        with patch("agent_api.NaturalLanguageSpecExtractor") as mock_cls:
            mock_cls.return_value.extract.return_value = spec
            resp = client.post(
                "/api/agent-factory/from-prompt",
                json={"description": "security scanner", "persist": False},
            )
        returned_spec = resp.json()["spec"]
        assert returned_spec["agent_name"] == "security_scanner"
        assert returned_spec["framework"] == "sandboxed"
        assert "scan_code" in returned_spec["capabilities"]

    def test_generated_code_is_non_empty(self, client, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        spec = _make_spec()
        with patch("agent_api.NaturalLanguageSpecExtractor") as mock_cls:
            mock_cls.return_value.extract.return_value = spec
            resp = client.post(
                "/api/agent-factory/from-prompt",
                json={"description": "security scanner", "persist": False},
            )
        assert len(resp.json()["generated_code"]) > 50

    def test_generated_code_is_valid_python(self, client, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        spec = _make_spec()
        with patch("agent_api.NaturalLanguageSpecExtractor") as mock_cls:
            mock_cls.return_value.extract.return_value = spec
            resp = client.post(
                "/api/agent-factory/from-prompt",
                json={"description": "security scanner", "persist": False},
            )
        code = resp.json()["generated_code"]
        compile(code, "<from_prompt>", "exec")


# ─────────────────────────────────────────────────────────────────────────────
# Framework override
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestFromPromptFrameworkOverride:
    def test_framework_override_is_applied(self, client, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        spec = _make_spec(framework="sandboxed")  # LLM chose sandboxed
        with patch("agent_api.NaturalLanguageSpecExtractor") as mock_cls:
            mock_cls.return_value.extract.return_value = spec
            resp = client.post(
                "/api/agent-factory/from-prompt",
                json={"description": "security scanner", "framework": "langchain", "persist": False},
            )
        assert resp.status_code == 200
        # The override must be reflected in the returned spec
        assert resp.json()["spec"]["framework"] == "langchain"

    def test_invalid_framework_override_returns_400(self, client, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        spec = _make_spec()
        with patch("agent_api.NaturalLanguageSpecExtractor") as mock_cls:
            mock_cls.return_value.extract.return_value = spec
            resp = client.post(
                "/api/agent-factory/from-prompt",
                json={"description": "security scanner", "framework": "NOT_A_FRAMEWORK", "persist": False},
            )
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Persist behaviour
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestFromPromptPersist:
    def test_persist_true_writes_file(self, client, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        spec = _make_spec()
        with patch("agent_api.NaturalLanguageSpecExtractor") as mock_cls:
            mock_cls.return_value.extract.return_value = spec
            resp = client.post(
                "/api/agent-factory/from-prompt",
                json={"description": "security scanner", "persist": True},
            )
        assert resp.status_code == 200
        assert resp.json()["persisted_path"] is not None
        saved = Path(resp.json()["persisted_path"])
        assert saved.exists()
        assert saved.suffix == ".py"

    def test_persist_false_returns_no_path(self, client, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        spec = _make_spec()
        with patch("agent_api.NaturalLanguageSpecExtractor") as mock_cls:
            mock_cls.return_value.extract.return_value = spec
            resp = client.post(
                "/api/agent-factory/from-prompt",
                json={"description": "security scanner", "persist": False},
            )
        assert resp.json()["persisted_path"] is None

    def test_persist_file_content_is_valid_python(self, client, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        spec = _make_spec()
        with patch("agent_api.NaturalLanguageSpecExtractor") as mock_cls:
            mock_cls.return_value.extract.return_value = spec
            resp = client.post(
                "/api/agent-factory/from-prompt",
                json={"description": "security scanner", "persist": True},
            )
        saved_code = Path(resp.json()["persisted_path"]).read_text()
        compile(saved_code, "<persisted>", "exec")


# ─────────────────────────────────────────────────────────────────────────────
# Input validation
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestFromPromptInputValidation:
    def test_empty_description_returns_400(self, client):
        resp = client.post(
            "/api/agent-factory/from-prompt",
            json={"description": "", "persist": False},
        )
        assert resp.status_code == 400
        assert "description" in resp.json()["detail"].lower()

    def test_whitespace_only_description_returns_400(self, client):
        resp = client.post(
            "/api/agent-factory/from-prompt",
            json={"description": "   ", "persist": False},
        )
        assert resp.status_code == 400

    def test_extractor_exception_returns_500(self, client, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("agent_api.NaturalLanguageSpecExtractor") as mock_cls:
            mock_cls.return_value.extract.side_effect = RuntimeError("llm exploded")
            resp = client.post(
                "/api/agent-factory/from-prompt",
                json={"description": "some agent", "persist": False},
            )
        assert resp.status_code == 500
        assert "llm exploded" in resp.json()["detail"]
