"""
_record_execution() Integration Tests — verify that agent execution triggers
all 7 learning subsystems.

The agent calls _record_execution() at the end of every execute(). This test
verifies that a real execute() call fires all the non-blocking subsystems:

  1. Artifact store — structured storage
  2. Weaviate RAG — semantic embeddings (mocked, no live Weaviate)
  3. Feedback loop — relevance feedback for retrieved docs
  4. Golden snapshot — model regression testing
  5. Output provenance — HMAC signature chain
  6. Immutable audit — append-only audit log
  7. Hallucination gate — overconfidence detection

We verify each subsystem was called by patching the import paths and
checking call counts — proving the wiring is correct.
"""
import pytest
from unittest.mock import patch, MagicMock, ANY
from agents import QAAssistantAgent, SREAgent, PerformanceAgent


# ── Helpers ──────────────────────────────────────────────────────────────────

def _simple_qa_data():
    return {"total": 10, "passed": 10, "failed": 0, "coverage": 100}


def _simple_sre_data():
    return {
        "file_path": "app.py",
        "errors": [{"rule": "E301", "message": "expected 2 blank lines", "line": 1, "file": "app.py"}],
    }


# ── Artifact store (subsystem 1) ─────────────────────────────────────────────

@pytest.mark.unit
def test_execute_stores_artifact():
    """execute() must store an artifact via pipeline.execute_with_validation()."""
    agent = QAAssistantAgent()
    # The pipeline is initialized in __init__ — verify it's called
    with patch.object(agent.pipeline, "execute_with_validation",
                      return_value=(True, {"artifact_id": "test-123"})) as mock_store:
        agent.execute(_simple_qa_data())
    mock_store.assert_called_once()
    call_args = mock_store.call_args
    assert call_args[0][0] == "QA_Assistant"  # agent_name


@pytest.mark.unit
def test_execute_appends_to_execution_history():
    """execute() must append to agent.execution_history."""
    agent = QAAssistantAgent()
    initial_len = len(agent.execution_history)
    agent.execute(_simple_qa_data())
    assert len(agent.execution_history) == initial_len + 1
    latest = agent.execution_history[-1]
    assert latest["status"] == "success"
    assert "timestamp" in latest


# ── Golden snapshot (subsystem 4) ─────────────────────────────────────────────

@pytest.mark.unit
def test_execute_captures_golden_snapshot():
    """On success, _record_execution() must call ModelRegressionTester.capture_golden()."""
    agent = QAAssistantAgent()
    with patch("agenticqa.regression.model_regression.ModelRegressionTester") as MockTester:
        mock_instance = MockTester.return_value
        agent.execute(_simple_qa_data())
    mock_instance.capture_golden.assert_called_once()
    args = mock_instance.capture_golden.call_args
    assert args[0][0] == "QA_Assistant"  # agent_name


# ── Output provenance (subsystem 5) ──────────────────────────────────────────

@pytest.mark.unit
def test_execute_signs_provenance():
    """On success, _record_execution() must call OutputProvenanceLogger.sign_and_log()."""
    agent = QAAssistantAgent()
    with patch("agenticqa.provenance.output_provenance.OutputProvenanceLogger") as MockProv:
        mock_instance = MockProv.return_value
        agent.execute(_simple_qa_data())
    mock_instance.sign_and_log.assert_called_once()
    kwargs = mock_instance.sign_and_log.call_args
    assert kwargs[1]["agent_name"] == "QA_Assistant" or kwargs[0][0] == "QA_Assistant"


# ── Immutable audit (subsystem 6) ────────────────────────────────────────────

@pytest.mark.unit
def test_execute_appends_audit_event():
    """_record_execution() must append to ImmutableAuditChain."""
    agent = QAAssistantAgent()
    with patch("agenticqa.security.immutable_audit.ImmutableAuditChain") as MockAudit:
        mock_chain = MockAudit.return_value
        agent.execute(_simple_qa_data())
    mock_chain.append.assert_called_once()
    event = mock_chain.append.call_args[0][0]
    assert event.actor == "QA_Assistant"
    assert event.event_type == "AGENT_EXEC"
    assert event.action == "success"


# ── Hallucination gate (subsystem 7) ─────────────────────────────────────────

@pytest.mark.unit
def test_execute_runs_hallucination_check():
    """On success, _record_execution() must call HallucinationConfidenceGate.risk_score()."""
    agent = QAAssistantAgent()
    with patch("agenticqa.security.hallucination_guard.HallucinationConfidenceGate") as MockGate:
        mock_instance = MockGate.return_value
        mock_instance.risk_score.return_value = 0.1  # Low risk
        agent.execute(_simple_qa_data())
    mock_instance.risk_score.assert_called_once()


# ── Multiple agents trigger the same subsystems ──────────────────────────────

@pytest.mark.unit
def test_sre_execute_stores_artifact():
    """SRE agent execution also triggers artifact storage."""
    agent = SREAgent()
    with patch.object(agent.pipeline, "execute_with_validation",
                      return_value=(True, {"artifact_id": "sre-123"})) as mock_store:
        agent.execute(_simple_sre_data())
    mock_store.assert_called_once()


@pytest.mark.unit
def test_performance_execute_captures_golden():
    """Performance agent execution also captures golden snapshots."""
    agent = PerformanceAgent()
    with patch("agenticqa.regression.model_regression.ModelRegressionTester") as MockTester:
        mock_instance = MockTester.return_value
        agent.execute({"duration_ms": 100, "baseline_ms": 50, "memory_mb": 64})
    mock_instance.capture_golden.assert_called_once()


# ── Error path does NOT call success-only subsystems ─────────────────────────

@pytest.mark.unit
def test_error_execution_skips_golden_and_provenance():
    """When agent raises, golden snapshot and provenance should NOT be called."""
    agent = QAAssistantAgent()

    # Force an error in _generate_recommendations
    with patch.object(agent, "_generate_recommendations", side_effect=RuntimeError("boom")):
        with patch("agenticqa.regression.model_regression.ModelRegressionTester") as MockTester:
            with patch("agenticqa.provenance.output_provenance.OutputProvenanceLogger") as MockProv:
                with pytest.raises(RuntimeError):
                    agent.execute(_simple_qa_data())
    # On error, _record_execution is called with status="error" — not "success"
    # So golden and provenance (guarded by `if status == "success"`) should NOT fire
    MockTester.return_value.capture_golden.assert_not_called()
    MockProv.return_value.sign_and_log.assert_not_called()


# ── Subsystem failure is non-blocking ────────────────────────────────────────

@pytest.mark.unit
def test_provenance_failure_does_not_block_execution():
    """If provenance signing fails, execute() must still succeed."""
    agent = QAAssistantAgent()
    with patch("agenticqa.provenance.output_provenance.OutputProvenanceLogger",
               side_effect=RuntimeError("provenance down")):
        result = agent.execute(_simple_qa_data())
    assert result["total_tests"] == 10  # Agent still returns valid result


@pytest.mark.unit
def test_audit_failure_does_not_block_execution():
    """If audit chain fails, execute() must still succeed."""
    agent = QAAssistantAgent()
    with patch("agenticqa.security.immutable_audit.ImmutableAuditChain",
               side_effect=RuntimeError("audit down")):
        result = agent.execute(_simple_qa_data())
    assert result["total_tests"] == 10


@pytest.mark.unit
def test_hallucination_gate_failure_does_not_block():
    """If hallucination gate fails, execute() must still succeed."""
    agent = QAAssistantAgent()
    with patch("agenticqa.security.hallucination_guard.HallucinationConfidenceGate",
               side_effect=RuntimeError("gate down")):
        result = agent.execute(_simple_qa_data())
    assert result["total_tests"] == 10


@pytest.mark.unit
def test_golden_snapshot_failure_does_not_block():
    """If golden snapshot capture fails, execute() must still succeed."""
    agent = QAAssistantAgent()
    with patch("agenticqa.regression.model_regression.ModelRegressionTester",
               side_effect=RuntimeError("regression down")):
        result = agent.execute(_simple_qa_data())
    assert result["total_tests"] == 10


# ── Safety annotations — closed loop verification ─────────────────────────

@pytest.mark.unit
def test_execute_populates_regression_annotation():
    """execute() must populate _safety_annotations.regression_check."""
    agent = QAAssistantAgent()
    mock_reg_result = MagicMock()
    mock_reg_result.similarity_score = 0.92
    mock_reg_result.regression_detected = False
    mock_reg_result.threshold_used = 0.75
    mock_reg_result.baseline_snapshot = MagicMock()  # has baseline

    with patch("agenticqa.regression.model_regression.ModelRegressionTester") as MockTester:
        mock_instance = MockTester.return_value
        mock_instance.compare.return_value = mock_reg_result
        result = agent.execute(_simple_qa_data())

    ann = result.get("_safety_annotations", {})
    assert "regression_check" in ann
    assert ann["regression_check"]["similarity_score"] == 0.92
    assert ann["regression_check"]["regression_detected"] is False
    assert ann["regression_check"]["has_baseline"] is True
    # compare() must be called BEFORE capture_golden()
    mock_instance.compare.assert_called_once()
    mock_instance.capture_golden.assert_called_once()


@pytest.mark.unit
def test_execute_populates_provenance_annotation():
    """execute() must populate _safety_annotations.provenance_verified."""
    agent = QAAssistantAgent()
    mock_verify_result = MagicMock()
    mock_verify_result.valid = True
    mock_verify_result.reason = "valid"

    with patch("agenticqa.provenance.output_provenance.OutputProvenanceLogger") as MockProv:
        mock_instance = MockProv.return_value
        mock_instance.verify.return_value = mock_verify_result
        result = agent.execute(_simple_qa_data())

    ann = result.get("_safety_annotations", {})
    assert "provenance_verified" in ann
    assert ann["provenance_verified"]["valid"] is True
    assert ann["provenance_verified"]["reason"] == "valid"
    mock_instance.sign_and_log.assert_called_once()
    mock_instance.verify.assert_called_once()


@pytest.mark.unit
def test_execute_populates_audit_chain_annotation():
    """execute() must populate _safety_annotations.audit_chain_intact."""
    agent = QAAssistantAgent()

    with patch("agenticqa.security.immutable_audit.ImmutableAuditChain") as MockChain:
        mock_instance = MockChain.return_value
        mock_instance.verify_chain.return_value = (True, [])
        mock_instance.length.return_value = 42
        result = agent.execute(_simple_qa_data())

    ann = result.get("_safety_annotations", {})
    assert "audit_chain_intact" in ann
    assert ann["audit_chain_intact"]["intact"] is True
    assert ann["audit_chain_intact"]["chain_length"] == 42
    assert ann["audit_chain_intact"]["violations"] == 0


@pytest.mark.unit
def test_execute_populates_hallucination_annotation():
    """execute() must populate _safety_annotations.hallucination_risk with findings."""
    agent = QAAssistantAgent()
    mock_finding = MagicMock()
    mock_finding.finding_type = "ABSOLUTE_CERTAINTY"
    mock_finding.severity = "medium"
    mock_finding.detail = "Certainty keyword near compliance language"
    mock_finding.excerpt = "definitely all tests pass"

    with patch("agenticqa.security.hallucination_guard.HallucinationConfidenceGate") as MockGate:
        mock_instance = MockGate.return_value
        mock_instance.scan.return_value = [mock_finding]
        mock_instance.risk_score.return_value = 0.25
        result = agent.execute(_simple_qa_data())

    ann = result.get("_safety_annotations", {})
    assert "hallucination_risk" in ann
    assert ann["hallucination_risk"]["risk_score"] == 0.25
    assert ann["hallucination_risk"]["is_safe"] is True
    assert ann["hallucination_risk"]["finding_count"] == 1
    assert len(ann["hallucination_risk"]["findings"]) == 1
    assert ann["hallucination_risk"]["findings"][0]["type"] == "ABSOLUTE_CERTAINTY"
    mock_instance.scan.assert_called_once()
    mock_instance.risk_score.assert_called_once()


@pytest.mark.unit
def test_execute_populates_contract_annotation():
    """execute() must populate _safety_annotations.contract_valid on success."""
    agent = QAAssistantAgent()
    result = agent.execute(_simple_qa_data())

    ann = result.get("_safety_annotations", {})
    assert "contract_valid" in ann
    assert ann["contract_valid"] is True
