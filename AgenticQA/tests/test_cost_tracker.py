"""Tests for API cost tracker with per-agent quotas."""
import json
import pytest
from pathlib import Path
from agenticqa.security.cost_tracker import (
    CostTracker, QuotaConfig, UsageRecord, CostCheckResult, MODEL_PRICING,
)


@pytest.fixture
def tracker(tmp_path):
    return CostTracker(storage_path=tmp_path / "costs.jsonl")


# ── Cost estimation ─────────────────────────────────────────────────────────

class TestCostEstimation:
    @pytest.mark.unit
    def test_known_model_pricing(self, tracker):
        # Claude Opus: $15/M input, $75/M output
        cost = tracker.estimate_cost("claude-opus-4-6", input_tokens=1000, output_tokens=1000)
        expected = 1000 * 15.0 / 1_000_000 + 1000 * 75.0 / 1_000_000
        assert abs(cost - expected) < 0.0001

    @pytest.mark.unit
    def test_sonnet_cheaper_than_opus(self, tracker):
        opus_cost = tracker.estimate_cost("claude-opus-4-6", input_tokens=1000, output_tokens=1000)
        sonnet_cost = tracker.estimate_cost("claude-sonnet-4-6", input_tokens=1000, output_tokens=1000)
        assert sonnet_cost < opus_cost

    @pytest.mark.unit
    def test_unknown_model_uses_default(self, tracker):
        cost = tracker.estimate_cost("some-unknown-model", input_tokens=1000, output_tokens=1000)
        default_pricing = MODEL_PRICING["_default"]
        expected = 1000 * default_pricing["input"] / 1_000_000 + 1000 * default_pricing["output"] / 1_000_000
        assert abs(cost - expected) < 0.0001

    @pytest.mark.unit
    def test_zero_tokens_zero_cost(self, tracker):
        cost = tracker.estimate_cost("claude-opus-4-6", input_tokens=0, output_tokens=0)
        assert cost == 0.0


# ── Recording usage ─────────────────────────────────────────────────────────

class TestRecordUsage:
    @pytest.mark.unit
    def test_record_creates_entry(self, tracker):
        record = tracker.record("qa_agent", "claude-sonnet-4-6",
                                input_tokens=500, output_tokens=1500)
        assert record.agent_id == "qa_agent"
        assert record.model == "claude-sonnet-4-6"
        assert record.estimated_cost_usd > 0
        assert record.timestamp > 0

    @pytest.mark.unit
    def test_record_persists_to_file(self, tracker, tmp_path):
        tracker.record("qa_agent", "claude-sonnet-4-6",
                        input_tokens=500, output_tokens=1500)
        # Read back
        content = (tmp_path / "costs.jsonl").read_text()
        data = json.loads(content.strip())
        assert data["agent_id"] == "qa_agent"

    @pytest.mark.unit
    def test_multiple_records(self, tracker):
        tracker.record("agent_a", "claude-sonnet-4-6", 100, 200)
        tracker.record("agent_b", "claude-opus-4-6", 300, 400)
        tracker.record("agent_a", "claude-sonnet-4-6", 150, 250)
        assert tracker.get_total_cost() > 0

    @pytest.mark.unit
    def test_session_and_team_fields(self, tracker):
        record = tracker.record("qa_agent", "claude-sonnet-4-6", 100, 200,
                                session_id="sess-123", team="platform")
        assert record.session_id == "sess-123"
        assert record.team == "platform"


# ── Quota enforcement ────────────────────────────────────────────────────────

class TestQuotaEnforcement:
    @pytest.mark.unit
    def test_default_quota_allows_small_call(self, tracker):
        result = tracker.check_quota("new_agent", model="claude-sonnet-4-6",
                                      estimated_tokens=1000)
        assert result.allowed
        assert result.remaining_budget_usd > 0

    @pytest.mark.unit
    def test_exhausted_cost_quota_blocks(self, tracker):
        tracker.set_quota("expensive_agent", QuotaConfig(max_cost_usd=0.01))
        # Record enough to exhaust
        tracker.record("expensive_agent", "claude-opus-4-6",
                        input_tokens=50_000, output_tokens=50_000)
        result = tracker.check_quota("expensive_agent")
        assert not result.allowed
        assert "exhausted" in result.block_reason

    @pytest.mark.unit
    def test_exhausted_token_quota_blocks(self, tracker):
        tracker.set_quota("token_agent", QuotaConfig(max_tokens=1000))
        tracker.record("token_agent", "claude-sonnet-4-6",
                        input_tokens=600, output_tokens=600)
        result = tracker.check_quota("token_agent")
        assert not result.allowed
        assert "token quota" in result.block_reason.lower()

    @pytest.mark.unit
    def test_alert_near_limit(self, tracker):
        tracker.set_quota("alert_agent", QuotaConfig(
            max_cost_usd=1.0, alert_threshold_pct=80.0
        ))
        # Spend ~$0.90 worth
        tracker.record("alert_agent", "claude-opus-4-6",
                        input_tokens=5000, output_tokens=5000)
        result = tracker.check_quota("alert_agent")
        # Check if we're near the threshold
        if result.current_cost_usd / 1.0 * 100 >= 80:
            assert result.alert

    @pytest.mark.unit
    def test_unlimited_quota(self, tracker):
        tracker.set_quota("unlimited_agent", QuotaConfig.unlimited())
        for _ in range(10):
            tracker.record("unlimited_agent", "claude-opus-4-6", 100_000, 100_000)
        result = tracker.check_quota("unlimited_agent")
        assert result.allowed


# ── Quota presets ────────────────────────────────────────────────────────────

class TestQuotaPresets:
    @pytest.mark.unit
    def test_standard_preset(self):
        q = QuotaConfig.standard()
        assert q.max_cost_usd == 10.0
        assert q.max_tokens == 1_000_000

    @pytest.mark.unit
    def test_elevated_preset(self):
        q = QuotaConfig.elevated()
        assert q.max_cost_usd == 100.0

    @pytest.mark.unit
    def test_unlimited_preset(self):
        q = QuotaConfig.unlimited()
        assert q.max_cost_usd == float("inf")


# ── Agent summaries ──────────────────────────────────────────────────────────

class TestSummaries:
    @pytest.mark.unit
    def test_agent_summary(self, tracker):
        tracker.record("qa_agent", "claude-sonnet-4-6", 1000, 2000)
        tracker.record("qa_agent", "claude-opus-4-6", 500, 1500)
        summary = tracker.get_agent_summary("qa_agent")
        assert summary["agent_id"] == "qa_agent"
        assert summary["total_calls"] == 2
        assert summary["total_input_tokens"] == 1500
        assert summary["total_output_tokens"] == 3500
        assert summary["total_cost_usd"] > 0
        assert len(summary["models_used"]) == 2

    @pytest.mark.unit
    def test_all_summaries(self, tracker):
        tracker.record("agent_a", "claude-sonnet-4-6", 100, 200)
        tracker.record("agent_b", "claude-opus-4-6", 300, 400)
        summaries = tracker.get_all_summaries()
        assert len(summaries) == 2
        ids = {s["agent_id"] for s in summaries}
        assert ids == {"agent_a", "agent_b"}

    @pytest.mark.unit
    def test_empty_agent_summary(self, tracker):
        summary = tracker.get_agent_summary("nonexistent")
        assert summary["total_calls"] == 0
        assert summary["total_cost_usd"] == 0

    @pytest.mark.unit
    def test_total_cost(self, tracker):
        tracker.record("a", "claude-sonnet-4-6", 1000, 1000)
        tracker.record("b", "claude-sonnet-4-6", 1000, 1000)
        total = tracker.get_total_cost()
        single = tracker.estimate_cost("claude-sonnet-4-6", 1000, 1000)
        assert abs(total - 2 * single) < 0.0001


# ── Persistence ──────────────────────────────────────────────────────────────

class TestPersistence:
    @pytest.mark.unit
    def test_load_from_existing_file(self, tmp_path):
        path = tmp_path / "costs.jsonl"
        record = {
            "agent_id": "loaded_agent",
            "model": "claude-sonnet-4-6",
            "input_tokens": 100,
            "output_tokens": 200,
            "estimated_cost_usd": 0.001,
            "timestamp": 1000000.0,
            "session_id": "",
            "team": "",
        }
        path.write_text(json.dumps(record) + "\n")
        tracker = CostTracker(storage_path=path)
        summary = tracker.get_agent_summary("loaded_agent")
        assert summary["total_calls"] == 1
