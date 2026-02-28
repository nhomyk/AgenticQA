"""Unit tests for OWASPScanner."""
import pytest
from pathlib import Path
from agenticqa.security.owasp_scanner import OWASPScanner, OWASPFinding


@pytest.fixture
def scanner():
    return OWASPScanner()


def write_file(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ── A01 — Broken Access Control ──────────────────────────────────────────────

@pytest.mark.unit
def test_cors_wildcard_detected(scanner, tmp_path):
    write_file(tmp_path, "app.py", 'allow_origins=["*"]')
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A01-003" for f in r.findings)


@pytest.mark.unit
def test_idor_request_id_detected(scanner, tmp_path):
    write_file(tmp_path, "views.py", 'user = db.get(request.args["user_id"])')
    r = scanner.scan(str(tmp_path))
    assert any(f.owasp_id == "A01" for f in r.findings)


# ── A02 — Cryptographic Failures ─────────────────────────────────────────────

@pytest.mark.unit
def test_hardcoded_password_detected(scanner, tmp_path):
    write_file(tmp_path, "config.py", 'password = "supersecret123"')
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A02-001" and f.severity == "critical" for f in r.findings)


@pytest.mark.unit
def test_hardcoded_api_key_detected(scanner, tmp_path):
    write_file(tmp_path, "config.py", 'api_key = "sk-live-abc123xyz"')
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A02-001" for f in r.findings)


@pytest.mark.unit
def test_md5_weak_crypto(scanner, tmp_path):
    write_file(tmp_path, "hash.py", "import md5\nhashlib.md5(data)")
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A02-002" for f in r.findings)


@pytest.mark.unit
def test_sha1_weak_crypto(scanner, tmp_path):
    write_file(tmp_path, "auth.py", "hashlib.sha1(password)")
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A02-002" for f in r.findings)


@pytest.mark.unit
def test_ssl_verify_false(scanner, tmp_path):
    write_file(tmp_path, "client.py", "requests.get(url, verify=False)")
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A02-004" for f in r.findings)


# ── A03 — Injection ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_sql_injection_format(scanner, tmp_path):
    write_file(tmp_path, "db.py", 'cursor.execute("SELECT * FROM users WHERE id=%s" % user_id)')
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A03-001" and f.severity == "critical" for f in r.findings)


@pytest.mark.unit
def test_command_injection_concat(scanner, tmp_path):
    write_file(tmp_path, "shell.py", 'subprocess.run("ls " + path)')
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A03-002" and f.severity == "critical" for f in r.findings)


@pytest.mark.unit
def test_xss_inner_html(scanner, tmp_path):
    write_file(tmp_path, "app.js", "element.innerHTML = req.body.content")
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A03-003" for f in r.findings)


# ── A04 — Insecure Design ────────────────────────────────────────────────────

@pytest.mark.unit
def test_open_redirect(scanner, tmp_path):
    write_file(tmp_path, "views.py", "return redirect(request.args.get('next'))")
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A04-002" for f in r.findings)


# ── A05 — Security Misconfiguration ──────────────────────────────────────────

@pytest.mark.unit
def test_debug_true_detected(scanner, tmp_path):
    write_file(tmp_path, "settings.py", "DEBUG = True")
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A05-001" for f in r.findings)


@pytest.mark.unit
def test_weak_secret_key(scanner, tmp_path):
    write_file(tmp_path, "settings.py", "SECRET_KEY = 'changeme'")
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A05-003" for f in r.findings)


# ── A07 — Auth & Session Mgmt ─────────────────────────────────────────────────

@pytest.mark.unit
def test_insecure_cookie(scanner, tmp_path):
    write_file(tmp_path, "app.py", "SESSION_COOKIE_SECURE = False")
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A07-001" for f in r.findings)


@pytest.mark.unit
def test_jwt_none_algorithm(scanner, tmp_path):
    write_file(tmp_path, "auth.py", 'jwt.decode(token, algorithms=["none"])')
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A07-003" for f in r.findings)


# ── A08 — Software Integrity ──────────────────────────────────────────────────

@pytest.mark.unit
def test_pickle_loads_critical(scanner, tmp_path):
    write_file(tmp_path, "deserial.py", "pickle.loads(user_data)")
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A08-001" and f.severity == "critical" for f in r.findings)


@pytest.mark.unit
def test_unsafe_yaml_load(scanner, tmp_path):
    write_file(tmp_path, "config.py", "yaml.load(stream, Loader=yaml.FullLoader)")
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A08-002" for f in r.findings)


# ── A09 — Logging Failures ────────────────────────────────────────────────────

@pytest.mark.unit
def test_bare_except_pass(scanner, tmp_path):
    write_file(tmp_path, "handler.py", "try:\n    do_thing()\nexcept:\n    pass")
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A09-001" for f in r.findings)


# ── A10 — SSRF ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_ssrf_request_args(scanner, tmp_path):
    write_file(tmp_path, "proxy.py", "requests.get(request.args['url'])")
    r = scanner.scan(str(tmp_path))
    assert any(f.rule_id == "A10-001" and f.severity == "critical" for f in r.findings)


# ── Result structure ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_clean_file_no_findings(scanner, tmp_path):
    write_file(tmp_path, "clean.py", "def add(a, b):\n    return a + b\n")
    r = scanner.scan(str(tmp_path))
    assert r.findings == []
    assert r.risk_score == 0.0


@pytest.mark.unit
def test_to_dict_has_fields(scanner, tmp_path):
    write_file(tmp_path, "app.py", "DEBUG = True")
    r = scanner.scan(str(tmp_path))
    d = r.to_dict()
    for key in ("repo_path", "files_scanned", "risk_score", "owasp_coverage",
                "findings", "critical_count", "high_count", "timestamp"):
        assert key in d


@pytest.mark.unit
def test_finding_to_dict_has_fields(scanner, tmp_path):
    write_file(tmp_path, "app.py", "DEBUG = True")
    r = scanner.scan(str(tmp_path))
    assert r.findings
    d = r.findings[0].to_dict()
    for key in ("owasp_id", "rule_id", "severity", "source_file",
                "line_number", "evidence", "description", "cwe", "owasp_category"):
        assert key in d


@pytest.mark.unit
def test_risk_score_zero_on_empty_repo(scanner, tmp_path):
    r = scanner.scan(str(tmp_path))
    assert r.risk_score == 0.0
    assert r.files_scanned == 0


@pytest.mark.unit
def test_by_category_groups_correctly(scanner, tmp_path):
    write_file(tmp_path, "app.py", "DEBUG = True\npickle.loads(data)")
    r = scanner.scan(str(tmp_path))
    cats = r.by_category()
    assert "A05" in cats
    assert "A08" in cats


@pytest.mark.unit
def test_owasp_report_string(scanner, tmp_path):
    write_file(tmp_path, "app.py", "DEBUG = True")
    r = scanner.scan(str(tmp_path))
    report = r.owasp_report()
    assert "OWASP Top 10" in report
    assert "A05" in report


@pytest.mark.unit
def test_deduplication_same_rule_same_line(scanner, tmp_path):
    # Same pattern appearing twice on same line shouldn't double-count
    write_file(tmp_path, "app.py", "DEBUG = True  # DEBUG = True")
    r = scanner.scan(str(tmp_path))
    a05 = [f for f in r.findings if f.rule_id == "A05-001"]
    assert len(a05) == 1
