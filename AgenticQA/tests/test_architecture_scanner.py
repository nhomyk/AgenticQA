"""Unit tests for ArchitectureScanner."""
import json
import pytest
from pathlib import Path

from agenticqa.security.architecture_scanner import ArchitectureScanner, ArchitectureScanResult


# ── Helpers ───────────────────────────────────────────────────────────────────

def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def scanner() -> ArchitectureScanner:
    return ArchitectureScanner()


# ── Python pattern tests ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_shell_exec_python_detected(tmp_path):
    write(tmp_path / "run.py", "import subprocess\nresult = subprocess.run(cmd, shell=True)\n")
    result = scanner().scan(str(tmp_path))
    shell = [a for a in result.integration_areas if a.category == "SHELL_EXEC"]
    assert len(shell) >= 1
    assert shell[0].severity == "critical"
    assert "CWE-78" in shell[0].cwe
    assert shell[0].plain_english  # non-empty plain-English description


@pytest.mark.unit
def test_external_http_python_detected(tmp_path):
    write(tmp_path / "api.py", "import requests\nresp = requests.get('https://api.example.com')\n")
    result = scanner().scan(str(tmp_path))
    http = [a for a in result.integration_areas if a.category == "EXTERNAL_HTTP"]
    assert len(http) >= 1
    assert http[0].severity == "high"


@pytest.mark.unit
def test_database_python_detected(tmp_path):
    write(tmp_path / "db.py", "import sqlite3\nconn = sqlite3.connect('data.db')\n")
    result = scanner().scan(str(tmp_path))
    db = [a for a in result.integration_areas if a.category == "DATABASE"]
    assert len(db) >= 1
    assert db[0].severity == "high"


@pytest.mark.unit
def test_env_secrets_python_detected(tmp_path):
    write(tmp_path / "config.py", "import os\nkey = os.environ['API_KEY']\n")
    result = scanner().scan(str(tmp_path))
    env = [a for a in result.integration_areas if a.category == "ENV_SECRETS"]
    assert len(env) >= 1


@pytest.mark.unit
def test_serialization_pickle_detected(tmp_path):
    write(tmp_path / "cache.py", "import pickle\nobj = pickle.loads(data)\n")
    result = scanner().scan(str(tmp_path))
    ser = [a for a in result.integration_areas if a.category == "SERIALIZATION"]
    assert len(ser) >= 1
    assert ser[0].severity == "high"


@pytest.mark.unit
def test_auth_boundary_python_detected(tmp_path):
    write(tmp_path / "auth.py", "import jwt\npayload = jwt.decode(token, key, algorithms=['HS256'])\n")
    result = scanner().scan(str(tmp_path))
    auth = [a for a in result.integration_areas if a.category == "AUTH_BOUNDARY"]
    assert len(auth) >= 1


@pytest.mark.unit
def test_clean_python_file_no_findings(tmp_path):
    write(tmp_path / "math_utils.py", "def add(a, b):\n    return a + b\n")
    result = scanner().scan(str(tmp_path))
    assert result.integration_areas == []
    assert result.attack_surface_score == 0.0


# ── TypeScript/JavaScript pattern tests ───────────────────────────────────────

@pytest.mark.unit
def test_shell_exec_typescript_detected(tmp_path):
    # child_process import → critical; execFile with separate args → high (safer variant)
    write(tmp_path / "runner.ts",
          "import { exec } from 'child_process';\nspawnSync('xcodebuild', ['-scheme', s]);\n")
    result = scanner().scan(str(tmp_path))
    shell = [a for a in result.integration_areas if a.category == "SHELL_EXEC"]
    assert len(shell) >= 1
    # child_process is always critical
    assert any(a.severity == "critical" for a in shell)


@pytest.mark.unit
def test_mcp_tool_typescript_detected(tmp_path):
    write(tmp_path / "server.ts",
          "const t = createTypedTool('build', schema, handler);\nserver.tool('run', {}, fn);\n")
    result = scanner().scan(str(tmp_path))
    mcp = [a for a in result.integration_areas if a.category == "MCP_TOOL"]
    assert len(mcp) >= 1
    assert mcp[0].severity == "medium"
    assert "Prompt Injection via Tool" in mcp[0].attack_vectors


@pytest.mark.unit
def test_cloud_sentry_typescript_detected(tmp_path):
    write(tmp_path / "monitoring.ts",
          "import * as Sentry from '@sentry/node';\nSentry.init({ dsn: process.env.DSN });\n")
    result = scanner().scan(str(tmp_path))
    cloud = [a for a in result.integration_areas if a.category == "CLOUD_SERVICE"]
    assert len(cloud) >= 1


@pytest.mark.unit
def test_env_secrets_process_env_detected(tmp_path):
    write(tmp_path / "config.ts",
          "const key = process.env['SECRET_KEY'];\nconst host = process.env.DB_HOST;\n")
    result = scanner().scan(str(tmp_path))
    env = [a for a in result.integration_areas if a.category == "ENV_SECRETS"]
    assert len(env) >= 1


@pytest.mark.unit
def test_network_socket_typescript_detected(tmp_path):
    write(tmp_path / "daemon.ts",
          "import net from 'net';\nconst server = net.createServer(handler);\n")
    result = scanner().scan(str(tmp_path))
    sock = [a for a in result.integration_areas if a.category == "NETWORK_SOCKET"]
    assert len(sock) >= 1
    assert sock[0].severity == "high"


@pytest.mark.unit
def test_serialization_json_parse_detected(tmp_path):
    write(tmp_path / "parser.ts",
          "const data = JSON.parse(rawInput);\n")
    result = scanner().scan(str(tmp_path))
    ser = [a for a in result.integration_areas if a.category == "SERIALIZATION"]
    assert len(ser) >= 1


# ── Swift pattern tests ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_swift_url_session_detected(tmp_path):
    write(tmp_path / "Network.swift",
          "let task = URLSession.shared.dataTask(with: url) { data, _, _ in }\n")
    result = scanner().scan(str(tmp_path))
    http = [a for a in result.integration_areas if a.category == "EXTERNAL_HTTP"]
    assert len(http) >= 1


# ── YAML pattern tests ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_yaml_env_secret_reference_detected(tmp_path):
    write(tmp_path / "deploy.yaml",
          "env:\n  API_KEY: ${SECRET_KEY}\n  DB_PASS: ${DB_PASSWORD}\n")
    result = scanner().scan(str(tmp_path))
    env = [a for a in result.integration_areas if a.category == "ENV_SECRETS"]
    assert len(env) >= 1


# ── Test traceability ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_test_file_matched_for_source(tmp_path):
    write(tmp_path / "src" / "runner.py",
          "import subprocess\nsubprocess.run(cmd)\n")
    write(tmp_path / "tests" / "test_runner.py",
          "import pytest\ndef test_runs(): pass\n")
    result = scanner().scan(str(tmp_path))
    shell = [a for a in result.integration_areas if a.category == "SHELL_EXEC"]
    assert len(shell) >= 1
    assert any("test_runner" in tf for tf in shell[0].test_files)


@pytest.mark.unit
def test_untested_area_detected(tmp_path):
    write(tmp_path / "db.py", "import sqlite3\nconn = sqlite3.connect('x.db')\n")
    # No test file for db.py
    result = scanner().scan(str(tmp_path))
    assert len(result.untested_areas) >= 1


@pytest.mark.unit
def test_test_coverage_confidence_full(tmp_path):
    write(tmp_path / "src" / "db.py", "import sqlite3\nconn = sqlite3.connect('x.db')\n")
    write(tmp_path / "tests" / "test_db.py", "def test_it(): pass\n")
    result = scanner().scan(str(tmp_path))
    if result.integration_areas:
        assert result.test_coverage_confidence > 0.0


@pytest.mark.unit
def test_test_coverage_confidence_zero(tmp_path):
    write(tmp_path / "app.py", "import subprocess\nsubprocess.run(cmd)\n")
    result = scanner().scan(str(tmp_path))
    assert result.test_coverage_confidence == 0.0


# ── Score tests ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_schema_validation_detected_as_info(tmp_path):
    # Zod schemas are protective — should be info severity, not penalise score
    write(tmp_path / "schema.ts",
          "const s = z.object({ name: z.string(), age: z.number() });\n")
    result = scanner().scan(str(tmp_path))
    schema = [a for a in result.integration_areas if a.category == "SCHEMA_VALIDATION"]
    assert len(schema) >= 1
    assert schema[0].severity == "info"
    # Info-level findings do NOT contribute to attack surface score
    assert result.attack_surface_score == 0.0


@pytest.mark.unit
def test_attack_surface_score_zero_clean(tmp_path):
    write(tmp_path / "clean.py", "x = 1 + 2\nprint(x)\n")
    result = scanner().scan(str(tmp_path))
    assert result.attack_surface_score == 0.0


@pytest.mark.unit
def test_attack_surface_score_high_for_critical(tmp_path):
    src = "\n".join([
        "import subprocess",
        "subprocess.run(cmd, shell=True)",
        "os.system(cmd)",
        "import socket",
        "import pickle",
    ])
    write(tmp_path / "danger.py", src)
    result = scanner().scan(str(tmp_path))
    assert result.attack_surface_score > 10.0


@pytest.mark.unit
def test_attack_surface_score_capped_at_100(tmp_path):
    lines = ["import subprocess\nsubprocess.run(c)\n"] * 10
    write(tmp_path / "many.py", "".join(lines))
    result = scanner().scan(str(tmp_path))
    assert result.attack_surface_score <= 100.0


# ── Output structure tests ────────────────────────────────────────────────────

@pytest.mark.unit
def test_plain_english_report_contains_sections(tmp_path):
    write(tmp_path / "app.py", "import subprocess\nsubprocess.run(cmd)\n")
    result = scanner().scan(str(tmp_path))
    report = result.plain_english_report()
    assert "Architecture Scan" in report
    assert "Attack surface score" in report
    assert "INTEGRATION AREAS" in report


@pytest.mark.unit
def test_by_category_groups_correctly(tmp_path):
    write(tmp_path / "app.py",
          "import subprocess\nsubprocess.run(cmd)\nimport sqlite3\nsqlite3.connect('x')\n")
    result = scanner().scan(str(tmp_path))
    cats = result.by_category()
    assert "SHELL_EXEC" in cats
    assert "DATABASE" in cats


@pytest.mark.unit
def test_to_dict_has_required_fields(tmp_path):
    write(tmp_path / "app.py", "import subprocess\nsubprocess.run(cmd)\n")
    result = scanner().scan(str(tmp_path))
    d = result.to_dict()
    for key in ("repo_path", "files_scanned", "attack_surface_score",
                "test_coverage_confidence", "integration_areas"):
        assert key in d


# ── Skip dirs test ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_skip_node_modules(tmp_path):
    write(tmp_path / "node_modules" / "evil" / "index.ts",
          "exec('rm -rf /');\n")
    result = scanner().scan(str(tmp_path))
    # Should not scan anything in node_modules
    assert all("node_modules" not in a.source_file for a in result.integration_areas)


# ── Empty repo test ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_empty_repo_returns_zero_score(tmp_path):
    result = scanner().scan(str(tmp_path))
    assert result.attack_surface_score == 0.0
    assert result.integration_areas == []
    assert result.scan_error is None


# ── Context-aware severity adjustment ─────────────────────────────────────────

@pytest.mark.unit
def test_frontend_external_http_downgraded_to_info(tmp_path):
    """EXTERNAL_HTTP inside a ui/ directory must be downgraded to info."""
    write(tmp_path / "ui" / "app.py",
          "import requests\nresp = requests.get('http://localhost:8000/tasks')\n")
    result = scanner().scan(str(tmp_path))
    http_areas = [a for a in result.integration_areas if a.category == "EXTERNAL_HTTP"]
    assert len(http_areas) == 1
    assert http_areas[0].severity == "info", f"Expected info, got {http_areas[0].severity}"
    assert "attack_vectors" in http_areas[0].to_dict()
    assert http_areas[0].attack_vectors == []


@pytest.mark.unit
def test_backend_external_http_remains_high(tmp_path):
    """EXTERNAL_HTTP in a backend file must stay high severity."""
    write(tmp_path / "src" / "service.py",
          "import requests\nresp = requests.get('https://external-api.com/data')\n")
    result = scanner().scan(str(tmp_path))
    http_areas = [a for a in result.integration_areas if a.category == "EXTERNAL_HTTP"]
    assert len(http_areas) == 1
    assert http_areas[0].severity == "high"


@pytest.mark.unit
def test_frontend_in_frontend_dir_downgraded(tmp_path):
    """EXTERNAL_HTTP inside a frontend/ directory is also downgraded."""
    write(tmp_path / "frontend" / "app.ts",
          "import axios from 'axios';\naxios.get('/api/tasks');\n")
    result = scanner().scan(str(tmp_path))
    http_areas = [a for a in result.integration_areas if a.category == "EXTERNAL_HTTP"]
    assert all(a.severity == "info" for a in http_areas)


@pytest.mark.unit
def test_url_env_var_downgraded_to_info(tmp_path):
    """os.environ.get('API_BASE', ...) is config, not a credential — must be info."""
    write(tmp_path / "src" / "config.py",
          "import os\nAPI_BASE = os.environ.get('API_BASE', 'http://localhost:8000')\n")
    result = scanner().scan(str(tmp_path))
    env_areas = [a for a in result.integration_areas if a.category == "ENV_SECRETS"]
    # API_BASE is a URL, not a credential
    assert all(a.severity == "info" for a in env_areas), \
        f"Expected all info, got: {[a.severity for a in env_areas]}"


@pytest.mark.unit
def test_credential_env_var_stays_high(tmp_path):
    """os.environ.get('SECRET_KEY', ...) is a real secret — must stay high."""
    write(tmp_path / "src" / "auth.py",
          "import os\nSECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret')\n")
    result = scanner().scan(str(tmp_path))
    env_areas = [a for a in result.integration_areas if a.category == "ENV_SECRETS"]
    assert len(env_areas) >= 1
    assert any(a.severity == "high" for a in env_areas), \
        f"Expected high severity for SECRET_KEY, got: {[a.severity for a in env_areas]}"


@pytest.mark.unit
def test_frontend_http_excluded_from_attack_surface_score(tmp_path):
    """Frontend HTTP calls (info) must not inflate the attack surface score."""
    write(tmp_path / "ui" / "app.py",
          "import requests\n" + "resp = requests.get('http://api/x')\n" * 5)
    result = scanner().scan(str(tmp_path))
    # info areas don't contribute to the score
    assert result.attack_surface_score == 0.0


@pytest.mark.unit
def test_is_frontend_file_recognises_ui_dir():
    from agenticqa.security.architecture_scanner import ArchitectureScanner
    assert ArchitectureScanner._is_frontend_file("ui/app.py")
    assert ArchitectureScanner._is_frontend_file("frontend/components/Button.tsx")
    assert ArchitectureScanner._is_frontend_file("client/src/pages/Home.tsx")
    assert not ArchitectureScanner._is_frontend_file("src/service.py")
    assert not ArchitectureScanner._is_frontend_file("api/server.py")


# ── Agent Framework detection ────────────────────────────────────────────────

@pytest.mark.unit
def test_agent_framework_langchain_python(tmp_path):
    """LangChain import in Python must be detected as AGENT_FRAMEWORK."""
    write(tmp_path / "agent.py",
          "from langchain.agents import AgentExecutor\nagent = AgentExecutor(agent=my_agent)\n")
    result = scanner().scan(str(tmp_path))
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    assert len(agents) >= 1
    assert agents[0].severity == "high"
    assert "CWE-693" in agents[0].cwe


@pytest.mark.unit
def test_agent_framework_langgraph_python(tmp_path):
    """LangGraph StateGraph must be detected as AGENT_FRAMEWORK."""
    write(tmp_path / "graph.py",
          "from langgraph.graph import StateGraph\ngraph = StateGraph(AgentState)\n")
    result = scanner().scan(str(tmp_path))
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    assert len(agents) >= 1


@pytest.mark.unit
def test_agent_framework_crewai_python(tmp_path):
    """CrewAI import must be detected as AGENT_FRAMEWORK."""
    write(tmp_path / "crew.py",
          "from crewai import Crew, Agent, Task\ncrew = Crew(agents=[a1, a2])\n")
    result = scanner().scan(str(tmp_path))
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    assert len(agents) >= 1


@pytest.mark.unit
def test_agent_framework_autogen_python(tmp_path):
    """AutoGen AssistantAgent must be detected as AGENT_FRAMEWORK."""
    write(tmp_path / "chat.py",
          "from autogen import AssistantAgent\nassistant = AssistantAgent('coder')\n")
    result = scanner().scan(str(tmp_path))
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    assert len(agents) >= 1


@pytest.mark.unit
def test_agent_framework_openai_python(tmp_path):
    """OpenAI SDK import must be detected as AGENT_FRAMEWORK."""
    write(tmp_path / "llm.py",
          "from openai import OpenAI\nclient = OpenAI()\n")
    result = scanner().scan(str(tmp_path))
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    assert len(agents) >= 1


@pytest.mark.unit
def test_agent_framework_anthropic_python(tmp_path):
    """Anthropic SDK import must be detected as AGENT_FRAMEWORK."""
    write(tmp_path / "claude.py",
          "from anthropic import Anthropic\nclient = Anthropic()\n")
    result = scanner().scan(str(tmp_path))
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    assert len(agents) >= 1


@pytest.mark.unit
def test_agent_framework_langchain_ts(tmp_path):
    """LangChain import in TypeScript must be detected as AGENT_FRAMEWORK."""
    write(tmp_path / "agent.ts",
          "import { AgentExecutor } from '@langchain/core';\nconst agent = AgentExecutor({});\n")
    result = scanner().scan(str(tmp_path))
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    assert len(agents) >= 1
    assert agents[0].severity == "high"


@pytest.mark.unit
def test_agent_framework_openai_ts(tmp_path):
    """OpenAI SDK in TypeScript must be detected as AGENT_FRAMEWORK."""
    write(tmp_path / "llm.ts",
          "import OpenAI from 'openai';\nconst client = new OpenAI();\n")
    result = scanner().scan(str(tmp_path))
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    assert len(agents) >= 1


@pytest.mark.unit
def test_agent_framework_anthropic_ts(tmp_path):
    """Anthropic SDK in TypeScript must be detected as AGENT_FRAMEWORK."""
    write(tmp_path / "claude.ts",
          "import Anthropic from '@anthropic-ai/sdk';\nconst client = new Anthropic();\n")
    result = scanner().scan(str(tmp_path))
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    assert len(agents) >= 1


@pytest.mark.unit
def test_agent_framework_go(tmp_path):
    """Go langchaingo import must be detected as AGENT_FRAMEWORK."""
    write(tmp_path / "agent.go",
          'package main\nimport "github.com/tmc/langchaingo/agents"\nfunc main() {}\n')
    result = scanner().scan(str(tmp_path))
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    assert len(agents) >= 1


@pytest.mark.unit
def test_agent_framework_java(tmp_path):
    """Java langchain4j import must be detected as AGENT_FRAMEWORK."""
    write(tmp_path / "Agent.java",
          "import dev.langchain4j.model.chat.ChatLanguageModel;\npublic class Agent {}\n")
    result = scanner().scan(str(tmp_path))
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    assert len(agents) >= 1


@pytest.mark.unit
def test_agent_framework_has_plain_english(tmp_path):
    """AGENT_FRAMEWORK findings must have a plain-English description."""
    write(tmp_path / "agent.py",
          "from langchain.agents import AgentExecutor\nagent = AgentExecutor(agent=my_agent)\n")
    result = scanner().scan(str(tmp_path))
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    assert len(agents) >= 1
    assert "agent framework" in agents[0].plain_english.lower() or \
           "agent" in agents[0].plain_english.lower()


@pytest.mark.unit
def test_agent_framework_has_attack_vectors(tmp_path):
    """AGENT_FRAMEWORK findings must list attack vectors."""
    write(tmp_path / "agent.py",
          "from crewai import Crew\ncrew = Crew(agents=[])\n")
    result = scanner().scan(str(tmp_path))
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    assert len(agents) >= 1
    assert len(agents[0].attack_vectors) >= 1
    assert any("injection" in v.lower() or "escalation" in v.lower() for v in agents[0].attack_vectors)


@pytest.mark.unit
def test_agent_framework_no_false_positive_on_clean_file(tmp_path):
    """A file with no agent code must not produce AGENT_FRAMEWORK findings."""
    write(tmp_path / "clean.py", "x = 1\ny = 2\nresult = x + y\n")
    result = scanner().scan(str(tmp_path))
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    assert len(agents) == 0


@pytest.mark.unit
def test_agent_framework_semantic_kernel_python(tmp_path):
    """Semantic Kernel import must be detected as AGENT_FRAMEWORK."""
    write(tmp_path / "sk.py",
          "from semantic_kernel import Kernel\nkernel = Kernel()\n")
    result = scanner().scan(str(tmp_path))
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    assert len(agents) >= 1


@pytest.mark.unit
def test_agent_framework_llama_index_python(tmp_path):
    """LlamaIndex import must be detected as AGENT_FRAMEWORK."""
    write(tmp_path / "rag.py",
          "from llama_index import GPTSimpleVectorIndex\nindex = GPTSimpleVectorIndex([])\n")
    result = scanner().scan(str(tmp_path))
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    assert len(agents) >= 1


@pytest.mark.unit
def test_total_categories_is_13(tmp_path):
    """ArchitectureScanner must have exactly 13 integration categories + SCHEMA_VALIDATION."""
    from agenticqa.security.architecture_scanner import _PLAIN_ENGLISH
    # 13 categories + SCHEMA_VALIDATION (protective)
    assert len(_PLAIN_ENGLISH) == 14, \
        f"Expected 14 category descriptions (13 + SCHEMA_VALIDATION), got {len(_PLAIN_ENGLISH)}: {sorted(_PLAIN_ENGLISH.keys())}"
