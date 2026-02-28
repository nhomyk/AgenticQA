"""Unit tests for DestructiveActionInterceptor."""
import pytest
from agenticqa.security.destructive_action_interceptor import (
    ActionCall,
    ActionClassifier,
    DestructiveActionInterceptor,
    SAFE, REVERSIBLE, IRREVERSIBLE, DESTRUCTIVE,
)


# ── Classifier ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_read_only_tool_is_safe():
    cls, ev = ActionClassifier().classify("get_email", {})
    assert cls == SAFE

@pytest.mark.unit
def test_list_tool_is_safe():
    cls, _ = ActionClassifier().classify("list_files", {})
    assert cls == SAFE

@pytest.mark.unit
def test_delete_tool_is_irreversible():
    cls, ev = ActionClassifier().classify("delete_file", {})
    assert cls == IRREVERSIBLE
    assert len(ev) >= 1

@pytest.mark.unit
def test_send_email_is_irreversible():
    cls, _ = ActionClassifier().classify("send_email", {})
    assert cls == IRREVERSIBLE

@pytest.mark.unit
def test_purge_is_destructive():
    cls, ev = ActionClassifier().classify("purge_inbox", {})
    assert cls == DESTRUCTIVE

@pytest.mark.unit
def test_bulk_delete_is_destructive():
    cls, _ = ActionClassifier().classify("bulk_delete", {})
    assert cls == DESTRUCTIVE

@pytest.mark.unit
def test_bulk_param_key_escalates_to_destructive():
    # Even a "safe" tool name + bulk param → DESTRUCTIVE
    cls, ev = ActionClassifier().classify("remove_items", {"all": True})
    assert cls == DESTRUCTIVE
    assert any("all" in e.lower() for e in ev)

@pytest.mark.unit
def test_wildcard_value_escalates():
    cls, ev = ActionClassifier().classify("archive_email", {"filter": "*"})
    assert cls == DESTRUCTIVE

@pytest.mark.unit
def test_high_risk_domain_upgrades_reversible():
    # Unknown tool with "email" domain → reversible upgraded to irreversible
    cls, ev = ActionClassifier().classify("move_email", {})
    assert cls == IRREVERSIBLE

@pytest.mark.unit
def test_unknown_tool_defaults_reversible():
    cls, ev = ActionClassifier().classify("frob_widget", {})
    assert cls == REVERSIBLE


# ── Interceptor: blocking ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_safe_action_allowed(tmp_path):
    interceptor = DestructiveActionInterceptor(audit_path=tmp_path)
    call = ActionCall(tool_name="list_emails", parameters={}, agent_id="bot")
    verdict = interceptor.intercept(call)
    assert verdict.allowed is True
    assert verdict.approval_token is None

@pytest.mark.unit
def test_destructive_action_blocked(tmp_path):
    interceptor = DestructiveActionInterceptor(audit_path=tmp_path)
    call = ActionCall(tool_name="bulk_delete", parameters={"all": True}, agent_id="bot")
    verdict = interceptor.intercept(call)
    assert verdict.allowed is False
    assert verdict.requires_approval is True
    assert verdict.approval_token is not None
    assert verdict.classification == DESTRUCTIVE
    assert verdict.risk_level == "critical"

@pytest.mark.unit
def test_irreversible_action_blocked_by_default(tmp_path):
    interceptor = DestructiveActionInterceptor(audit_path=tmp_path)
    call = ActionCall(tool_name="delete_email", parameters={}, agent_id="bot")
    verdict = interceptor.intercept(call)
    assert verdict.allowed is False
    assert verdict.approval_token is not None

@pytest.mark.unit
def test_reversible_auto_approved(tmp_path):
    interceptor = DestructiveActionInterceptor(
        block_on=(IRREVERSIBLE, DESTRUCTIVE),
        auto_approve_reversible=True,
        audit_path=tmp_path,
    )
    call = ActionCall(tool_name="move_to_draft", parameters={}, agent_id="bot")
    verdict = interceptor.intercept(call)
    assert verdict.allowed is True


# ── Interceptor: approval flow ────────────────────────────────────────────────

@pytest.mark.unit
def test_approve_valid_token(tmp_path):
    interceptor = DestructiveActionInterceptor(audit_path=tmp_path)
    call = ActionCall(tool_name="delete_email", parameters={}, agent_id="bot")
    verdict = interceptor.intercept(call)
    token = verdict.approval_token
    assert interceptor.approve(token) is True
    assert interceptor.is_approved(token) is True

@pytest.mark.unit
def test_approve_invalid_token(tmp_path):
    interceptor = DestructiveActionInterceptor(audit_path=tmp_path)
    assert interceptor.approve("not-a-real-token") is False

@pytest.mark.unit
def test_deny_removes_from_pending(tmp_path):
    interceptor = DestructiveActionInterceptor(audit_path=tmp_path)
    call = ActionCall(tool_name="drop_table", parameters={}, agent_id="bot")
    verdict = interceptor.intercept(call)
    token = verdict.approval_token
    assert interceptor.deny(token) is True
    assert interceptor.is_approved(token) is False

@pytest.mark.unit
def test_pending_approvals_list(tmp_path):
    interceptor = DestructiveActionInterceptor(audit_path=tmp_path)
    for i in range(3):
        interceptor.intercept(ActionCall(tool_name="delete_email", parameters={}, agent_id="bot"))
    pending = interceptor.get_pending_approvals()
    assert len(pending) == 3

@pytest.mark.unit
def test_destructive_count_tracked(tmp_path):
    interceptor = DestructiveActionInterceptor(audit_path=tmp_path)
    for _ in range(4):
        interceptor.intercept(ActionCall(tool_name="delete_email", parameters={}, agent_id="openclawbot"))
    assert interceptor.agent_destructive_count("openclawbot") == 4

@pytest.mark.unit
def test_block_reason_contains_token(tmp_path):
    interceptor = DestructiveActionInterceptor(audit_path=tmp_path)
    verdict = interceptor.intercept(ActionCall(tool_name="delete_all", parameters={}, agent_id="bot"))
    assert verdict.approval_token in verdict.block_reason
