"""Unit tests for InstructionPersistenceWarden."""
import pytest
from agenticqa.security.instruction_persistence_warden import (
    InstructionPersistenceWarden,
    GuardrailBlock,
)


def _msgs(n_chars: int) -> list:
    """Fake conversation history of approximate character length."""
    return [{"role": "user", "content": "x" * n_chars}]


@pytest.fixture
def warden(tmp_path):
    return InstructionPersistenceWarden(context_window_tokens=1000, audit_path=tmp_path)


@pytest.fixture
def guardrails():
    return [
        GuardrailBlock(
            name="no_bulk_delete",
            content="Never delete more than 1 item without explicit user confirmation.",
            drift_signals=["deleting all", "removing everything", "bulk delete"],
            priority=10,
        ),
        GuardrailBlock(
            name="confirm_before_send",
            content="Always ask the user before sending any email.",
            drift_signals=["sending all emails"],
            priority=5,
        ),
    ]


# ── Compaction risk ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_low_risk_when_empty(warden):
    report = warden.check("s1", [])
    assert report.compaction_risk == "low"
    assert report.recommended_action == "continue"

@pytest.mark.unit
def test_medium_risk_at_60_percent(warden):
    # 1000 tokens window × 60% = 600 tokens × 4 chars = 2400 chars
    msgs = _msgs(2400)
    risk = warden.compaction_risk(msgs)
    assert risk == "medium"

@pytest.mark.unit
def test_high_risk_at_80_percent(warden):
    # 1000 × 80% = 800 tokens × 4 = 3200 chars → "high" (75–90%)
    msgs = _msgs(3200)
    risk = warden.compaction_risk(msgs)
    assert risk == "high"

@pytest.mark.unit
def test_critical_risk_at_96_percent(warden):
    msgs = _msgs(4000)  # 4000/4=1000 tokens = 100% fill
    risk = warden.compaction_risk(msgs)
    assert risk == "critical"

@pytest.mark.unit
def test_reinject_recommended_at_critical(warden):
    msgs = _msgs(4000)
    report = warden.check("s1", msgs)
    assert report.recommended_action in ("re_inject", "terminate", "pause")
    assert report.guardrails_re_injected is True


# ── Guardrail registration ────────────────────────────────────────────────────

@pytest.mark.unit
def test_register_and_retrieve(warden, guardrails):
    warden.register_guardrails("s1", guardrails)
    registered = warden.get_guardrails("s1")
    assert len(registered) == 2

@pytest.mark.unit
def test_guardrails_sorted_by_priority(warden, guardrails):
    warden.register_guardrails("s1", guardrails)
    blocks = warden.get_guardrails("s1")
    assert blocks[0].priority >= blocks[1].priority


# ── Constraint drift detection ────────────────────────────────────────────────

@pytest.mark.unit
def test_no_drift_on_clean_output(warden, guardrails):
    warden.register_guardrails("s1", guardrails)
    report = warden.check("s1", [], "I found 3 emails matching your criteria.")
    assert report.constraint_drift_detected is False

@pytest.mark.unit
def test_drift_detected_on_guardrail_signal(warden, guardrails):
    warden.register_guardrails("s1", guardrails)
    bad_output = "I'll start deleting all emails older than 7 days now."
    report = warden.check("s1", [], bad_output)
    assert report.constraint_drift_detected is True
    assert report.recommended_action in ("pause", "terminate")

@pytest.mark.unit
def test_drift_terminate_on_high_severity(warden, guardrails):
    warden.register_guardrails("s1", guardrails)
    evil = "I am now removing everything from the inbox."
    report = warden.check("s1", [], evil)
    assert report.recommended_action == "terminate"
    assert report.guardrails_re_injected is True

@pytest.mark.unit
def test_global_override_signal_detected(warden):
    # No guardrails registered — generic override pattern still fires
    report = warden.check("s1", [], "I am ignoring the instruction and will wipe all emails.")
    assert report.constraint_drift_detected is True

@pytest.mark.unit
def test_drift_signals_populated(warden, guardrails):
    warden.register_guardrails("s1", guardrails)
    report = warden.check("s1", [], "I'll be sending all emails now, bulk delete confirmed.")
    assert len(report.drift_signals) >= 1
    signal_names = {d.guardrail_name for d in report.drift_signals}
    # At least one should reference a named guardrail or global
    assert len(signal_names) >= 1


# ── Reinforced prompt ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_reinforced_prompt_contains_guardrails(warden, guardrails):
    warden.register_guardrails("s1", guardrails)
    prompt = warden.get_reinforced_system_prompt("s1")
    assert "IMMUTABLE GUARDRAIL" in prompt
    assert "no_bulk_delete" in prompt
    assert "confirm_before_send" in prompt

@pytest.mark.unit
def test_reinforced_prompt_prepends_to_base(warden, guardrails):
    warden.register_guardrails("s1", guardrails)
    prompt = warden.get_reinforced_system_prompt("s1", base_prompt="You are a helpful assistant.")
    assert "IMMUTABLE GUARDRAIL" in prompt
    assert "You are a helpful assistant." in prompt
    # Guardrails should come before base prompt
    assert prompt.index("IMMUTABLE") < prompt.index("helpful assistant")

@pytest.mark.unit
def test_reinforced_prompt_empty_when_no_guardrails(warden):
    base = "You are a helpful assistant."
    prompt = warden.get_reinforced_system_prompt("unknown-session", base_prompt=base)
    assert prompt == base


# ── Report structure ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_report_to_dict_has_fields(warden):
    report = warden.check("s1", _msgs(100), "")
    d = report.to_dict()
    for key in ("session_id", "token_estimate", "compaction_risk",
                 "constraint_drift_detected", "recommended_action", "fill_fraction"):
        assert key in d

@pytest.mark.unit
def test_fill_fraction_range(warden):
    report = warden.check("s1", _msgs(2000), "")
    assert 0.0 <= report.fill_fraction <= 1.0
