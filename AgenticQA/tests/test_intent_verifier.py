"""Unit tests for IntentToCodeVerifier."""
import pytest
from agenticqa.security.intent_verifier import IntentToCodeVerifier


@pytest.fixture
def verifier():
    return IntentToCodeVerifier(static_only=True)


# ── INTENT_MET ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_rate_limit_intent_met(verifier):
    diff = """
+from slowapi import Limiter
+limiter = Limiter(key_func=get_remote_address)
+@app.route("/login")
+@limiter.limit("5 per minute")
+def login():
+    return authenticate(request.form)
"""
    r = verifier.verify("Add rate limiting to the login endpoint max 5 per minute", diff)
    assert r.verdict == "INTENT_MET"
    assert "rate limiting" in r.intent_signals_found


@pytest.mark.unit
def test_encryption_intent_met(verifier):
    diff = """
+import hashlib
+def hash_password(pwd):
+    return hashlib.sha256(pwd.encode()).hexdigest()
"""
    r = verifier.verify("Hash and encrypt the user password before storing", diff)
    assert r.verdict == "INTENT_MET"


@pytest.mark.unit
def test_validation_intent_met(verifier):
    diff = """
+from pydantic import BaseModel, validator
+class LoginRequest(BaseModel):
+    username: str
+    password: str
+    @validator('password')
+    def password_min_length(cls, v):
+        if len(v) < 8:
+            raise ValueError('Password too short')
+        return v
"""
    r = verifier.verify("Add validation to ensure password is at least 8 characters", diff)
    assert r.verdict == "INTENT_MET"


# ── HALLUCINATION ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_hallucinated_requests_method(verifier):
    diff = "+response = requests.get_with_retry(url, retries=3)"
    r = verifier.verify("Fetch data from the API with retry logic", diff)
    assert r.verdict == "HALLUCINATION"
    assert any(i.issue_type == "HALLUCINATION" for i in r.issues)


@pytest.mark.unit
def test_hallucinated_has_key(verifier):
    diff = "+if data.has_key('user'):\n+    process(data)"
    r = verifier.verify("Check if user key exists in the dict", diff)
    issues = [i for i in r.issues if i.issue_type == "HALLUCINATION"]
    assert len(issues) >= 1


@pytest.mark.unit
def test_hallucinated_os_makepath(verifier):
    diff = "+os.makepath('/tmp/data')"
    r = verifier.verify("Create the directory for data storage", diff)
    assert any(i.issue_type == "HALLUCINATION" for i in r.issues)


@pytest.mark.unit
def test_syntax_error_flags_hallucination(verifier):
    diff = "+def broken(x\n+    return x"  # missing closing paren
    r = verifier.verify("Add a helper function", diff)
    assert r.verdict == "HALLUCINATION"
    assert any(i.issue_type == "SYNTAX_ERROR" for i in r.issues)


# ── GAP_DETECTED ──────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_rate_limit_gap_detected(verifier):
    diff = """
+def login(username, password):
+    return authenticate(username, password)
"""
    r = verifier.verify("Add rate limiting to the login endpoint", diff)
    assert r.verdict in ("GAP_DETECTED", "UNCERTAIN")
    assert "rate limiting" in r.intent_signals_missing


@pytest.mark.unit
def test_encryption_gap_no_crypto(verifier):
    diff = "+def store_password(pwd):\n+    db.save(pwd)"
    r = verifier.verify("Encrypt the password before storing it in the database", diff)
    assert "encryption" in r.intent_signals_missing


@pytest.mark.unit
def test_caching_gap_detected(verifier):
    diff = (
        "+def get_user(user_id):\n"
        "+    # fetch user from database\n"
        "+    result = db.query(User).filter_by(id=user_id).first()\n"
        "+    return result\n"
    )
    r = verifier.verify("Add caching to the get_user function to reduce database load", diff)
    assert "caching" in r.intent_signals_missing


# ── STUB_ONLY ─────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_pass_stub_detected(verifier):
    diff = "+def add_rate_limiting():\n+    pass"
    r = verifier.verify("Add rate limiting", diff)
    assert r.verdict == "STUB_ONLY"
    assert any(i.issue_type == "STUB" for i in r.issues)


@pytest.mark.unit
def test_todo_comment_is_stub(verifier):
    diff = "+def authenticate(user, pwd):\n+    # TODO: implement this"
    r = verifier.verify("Implement authentication", diff)
    assert any(i.issue_type == "STUB" for i in r.issues)


@pytest.mark.unit
def test_not_implemented_error_is_stub(verifier):
    diff = "+def rate_limit():\n+    raise NotImplementedError"
    r = verifier.verify("Add rate limiting", diff)
    assert any(i.issue_type == "STUB" for i in r.issues)


# ── UNCERTAIN ─────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_empty_diff_is_uncertain(verifier):
    r = verifier.verify("Add rate limiting", "")
    assert r.verdict == "UNCERTAIN"


@pytest.mark.unit
def test_no_recognisable_keywords_is_uncertain(verifier):
    diff = "+x = 1\n+y = 2"
    r = verifier.verify("Refactor the internals", diff)
    # Very generic intent with no signal keywords → uncertain
    assert r.verdict in ("UNCERTAIN", "INTENT_MET")


# ── Result structure ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_to_dict_has_required_fields(verifier):
    r = verifier.verify("Add logging", "+import logging\n+log = logging.getLogger(__name__)")
    d = r.to_dict()
    for key in ("verdict", "confidence", "intent_summary", "is_safe_to_merge",
                "issues", "intent_signals_found", "intent_signals_missing",
                "added_lines", "timestamp"):
        assert key in d


@pytest.mark.unit
def test_confidence_in_range(verifier):
    diff = "+import hashlib\n+def hash_pwd(p): return hashlib.sha256(p.encode()).hexdigest()"
    r = verifier.verify("Hash the password", diff)
    assert 0.0 <= r.confidence <= 1.0


@pytest.mark.unit
def test_is_safe_to_merge_true_when_intent_met(verifier):
    diff = "+import hashlib\n+def hash_pwd(p): return hashlib.sha256(p.encode()).hexdigest()"
    r = verifier.verify("Hash the password before saving", diff)
    if r.verdict == "INTENT_MET":
        assert r.is_safe_to_merge is True


@pytest.mark.unit
def test_is_safe_to_merge_false_on_hallucination(verifier):
    diff = "+response = requests.get_with_retry(url)"
    r = verifier.verify("Fetch data with retry", diff)
    assert r.is_safe_to_merge is False


@pytest.mark.unit
def test_issue_to_dict_has_fields(verifier):
    diff = "+requests.get_with_retry(url)"
    r = verifier.verify("Fetch data", diff)
    if r.issues:
        d = r.issues[0].to_dict()
        for key in ("issue_type", "severity", "description", "line_snippet"):
            assert key in d


@pytest.mark.unit
def test_non_diff_plain_code_works(verifier):
    # Not a diff — plain code string
    code = "def authenticate(user, pwd):\n    return bcrypt.check(user.hash, pwd)"
    r = verifier.verify("Implement authentication with bcrypt", code)
    assert r.added_lines > 0


@pytest.mark.unit
def test_multiple_hallucinations_all_reported(verifier):
    diff = "+requests.get_with_retry(url)\n+os.makepath('/tmp')"
    r = verifier.verify("Fetch data and create directory", diff)
    hallucinations = [i for i in r.issues if i.issue_type == "HALLUCINATION"]
    assert len(hallucinations) >= 2
