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
    write(tmp_path / "runner.ts",
          "import { exec } from 'child_process';\nexec('xcodebuild build');\n")
    result = scanner().scan(str(tmp_path))
    shell = [a for a in result.integration_areas if a.category == "SHELL_EXEC"]
    assert len(shell) >= 1
    assert shell[0].severity == "critical"


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
    assert result.attack_surface_score > 30.0


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
