"""Tests for CIArtifactIngestion fallback to local artifact store."""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ingestion(tmp_path, rag=None):
    """Create a CIArtifactIngestion without triggering real RAG/network init."""
    from ingest_ci_artifacts import CIArtifactIngestion
    from src.data_store.artifact_store import TestArtifactStore

    obj = CIArtifactIngestion.__new__(CIArtifactIngestion)
    obj.rag = rag
    obj.ingested_count = 0
    obj.artifact_store = TestArtifactStore(str(tmp_path / "store"))
    return obj


# ---------------------------------------------------------------------------
# Fix 1 — _fallback_to_local_store
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fallback_writes_artifact_and_increments_count(tmp_path):
    ing = _make_ingestion(tmp_path)
    doc = {"artifact_type": "test_result", "status": "pass", "tags": ["jest"]}

    result = ing._fallback_to_local_store("qa", doc)

    assert result is True
    assert ing.ingested_count == 1


@pytest.mark.unit
def test_fallback_returns_false_without_artifact_store(tmp_path):
    ing = _make_ingestion(tmp_path)
    ing.artifact_store = None

    result = ing._fallback_to_local_store("qa", {"artifact_type": "ci_artifact"})

    assert result is False
    assert ing.ingested_count == 0


@pytest.mark.unit
def test_fallback_uses_ci_artifact_type_when_missing(tmp_path):
    ing = _make_ingestion(tmp_path)
    doc = {"content": "some data"}  # no artifact_type key

    result = ing._fallback_to_local_store("sre", doc)

    assert result is True
    # Verify the artifact exists in the store
    hits = ing.artifact_store.search_artifacts(artifact_type="ci_artifact")
    assert len(hits) >= 1


@pytest.mark.unit
def test_fallback_propagates_tags(tmp_path):
    ing = _make_ingestion(tmp_path)
    doc = {"artifact_type": "coverage", "tags": ["coverage", "sdet"]}

    ing._fallback_to_local_store("sdet", doc)

    hits = ing.artifact_store.search_artifacts()
    assert len(hits) >= 1
    stored = ing.artifact_store.get_artifact(hits[0]["artifact_id"])
    assert "tags" in stored


# ---------------------------------------------------------------------------
# ingest_pa11y_report — routes to fallback when rag is None
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_ingest_pa11y_report_uses_fallback_when_no_rag(tmp_path):
    ing = _make_ingestion(tmp_path)

    report = tmp_path / "pa11y.txt"
    report.write_text("Error: WCAG2AA.Principle1.Guideline1_1.1_1_1.H37 at #img\n")

    result = ing.ingest_pa11y_report(str(report), run_id="ci-001")

    assert result is True
    assert ing.ingested_count == 1


@pytest.mark.unit
def test_ingest_pa11y_report_calls_rag_when_available(tmp_path):
    mock_rag = MagicMock()
    ing = _make_ingestion(tmp_path, rag=mock_rag)

    report = tmp_path / "pa11y.txt"
    report.write_text("Error: something\n")

    ing.ingest_pa11y_report(str(report), run_id="ci-002")

    mock_rag.log_agent_execution.assert_called_once()
    call_args = mock_rag.log_agent_execution.call_args
    assert call_args[0][0] == "compliance"


# ---------------------------------------------------------------------------
# ingest_coverage_report — routes to fallback
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_ingest_coverage_report_uses_fallback_when_no_rag(tmp_path):
    ing = _make_ingestion(tmp_path)

    cov = {"total": {"statements": {"pct": 82.5}, "branches": {"pct": 70.0}}}
    cov_file = tmp_path / "coverage-summary.json"
    cov_file.write_text(json.dumps(cov))

    result = ing.ingest_coverage_report(str(cov_file), run_id="ci-003")

    assert result is True
    assert ing.ingested_count == 1


# ---------------------------------------------------------------------------
# ingest_agent_log — routes to fallback
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_ingest_agent_log_uses_fallback_when_no_rag(tmp_path):
    ing = _make_ingestion(tmp_path)

    log = tmp_path / "agent.md"
    log.write_text("# Agent Report\n\nAll checks passed.\n")

    result = ing.ingest_agent_log(str(log), agent_type="compliance", run_id="ci-004")

    assert result is True
    assert ing.ingested_count == 1


# ---------------------------------------------------------------------------
# Multiple fallback writes accumulate
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_multiple_fallbacks_accumulate_count(tmp_path):
    ing = _make_ingestion(tmp_path)

    report = tmp_path / "pa11y.txt"
    report.write_text("Error: something\n")

    cov = {"total": {"statements": {"pct": 80.0}}}
    cov_file = tmp_path / "cov.json"
    cov_file.write_text(json.dumps(cov))

    ing.ingest_pa11y_report(str(report), run_id="r1")
    ing.ingest_coverage_report(str(cov_file), run_id="r1")

    assert ing.ingested_count == 2
    assert len(ing.artifact_store.search_artifacts()) == 2
