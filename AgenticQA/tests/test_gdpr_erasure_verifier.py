"""Unit tests for GDPREraseVerifier."""
import json
import pytest
from agenticqa.security.gdpr_erasure_verifier import GDPREraseVerifier, ErasureRequest


@pytest.fixture
def verifier(tmp_path):
    return GDPREraseVerifier(
        request_path=tmp_path / "erasure.jsonl",
        agenticqa_dir=tmp_path / "agenticqa",
    )


@pytest.mark.unit
def test_request_erasure_creates_record(verifier):
    req = verifier.request_erasure("tenant-abc", "user-1")
    assert isinstance(req, ErasureRequest)
    assert req.tenant_id == "tenant-abc"
    assert req.subject_id == "user-1"
    assert req.status == "pending"
    assert req.request_id


@pytest.mark.unit
def test_list_requests_empty(verifier):
    assert verifier.list_requests() == []


@pytest.mark.unit
def test_list_requests_after_erasure(verifier):
    verifier.request_erasure("t1", "s1")
    verifier.request_erasure("t2", "s2")
    reqs = verifier.list_requests()
    assert len(reqs) == 2


@pytest.mark.unit
def test_verify_erasure_unknown_id_raises(verifier):
    with pytest.raises(ValueError, match="No erasure request"):
        verifier.verify_erasure("nonexistent-uuid")


@pytest.mark.unit
def test_verify_clean_when_no_data(verifier):
    req = verifier.request_erasure("tenant-xyz", "user-99")
    result = verifier.verify_erasure(req.request_id)
    assert result.verified_clean is True
    assert result.stores_with_residual == []


@pytest.mark.unit
def test_verify_finds_residual_in_metrics(tmp_path):
    agenticqa_dir = tmp_path / "agenticqa"
    agenticqa_dir.mkdir()
    metrics = agenticqa_dir / "metrics_history.jsonl"
    metrics.write_text(json.dumps({"repo_id": "target-tenant", "run_id": "r1", "fix_rate": 0.9}) + "\n")

    v = GDPREraseVerifier(
        request_path=tmp_path / "req.jsonl",
        agenticqa_dir=agenticqa_dir,
    )
    req = v.request_erasure("target-tenant", "u1")
    result = v.verify_erasure(req.request_id)
    assert result.verified_clean is False
    assert "metrics_history" in result.stores_with_residual


@pytest.mark.unit
def test_verify_finds_residual_in_repo_profiles(tmp_path):
    agenticqa_dir = tmp_path / "agenticqa"
    repos_dir = agenticqa_dir / "repos"
    repos_dir.mkdir(parents=True)
    (repos_dir / "target-tenant.json").write_text(
        json.dumps({"repo_id": "target-tenant", "total_runs": 5})
    )
    v = GDPREraseVerifier(
        request_path=tmp_path / "req.jsonl",
        agenticqa_dir=agenticqa_dir,
    )
    req = v.request_erasure("target-tenant", "u1")
    result = v.verify_erasure(req.request_id)
    assert "repo_profiles" in result.stores_with_residual


@pytest.mark.unit
def test_status_updated_after_verify(verifier):
    req = verifier.request_erasure("t1", "s1")
    verifier.verify_erasure(req.request_id)
    reqs = verifier.list_requests()
    updated = next(r for r in reqs if r.request_id == req.request_id)
    assert updated.status in ("verified_clean", "residual_found")


@pytest.mark.unit
def test_to_dict_contains_required_fields(verifier):
    req = verifier.request_erasure("t1", "s1")
    result = verifier.verify_erasure(req.request_id)
    d = result.to_dict()
    for key in ("request_id", "tenant_id", "subject_id", "verified_at",
                "verified_clean", "stores_with_residual", "stores_checked"):
        assert key in d


@pytest.mark.unit
def test_multiple_requests_independent(verifier):
    r1 = verifier.request_erasure("tenant-1", "u1")
    r2 = verifier.request_erasure("tenant-2", "u2")
    assert r1.request_id != r2.request_id
    v1 = verifier.verify_erasure(r1.request_id)
    v2 = verifier.verify_erasure(r2.request_id)
    assert v1.tenant_id == "tenant-1"
    assert v2.tenant_id == "tenant-2"
