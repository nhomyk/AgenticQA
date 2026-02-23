from agenticqa.delegation.guardrails import DelegationGuardrails


class _FakeResult:
    def __init__(self, record):
        self._record = record

    def single(self):
        return self._record


class _FakeSession:
    def __init__(self, record=None, raises=False):
        self.record = record
        self.raises = raises

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, query, **params):
        assert "MATCH (from:Agent" in query
        assert "from_agent" in params
        if self.raises:
            raise RuntimeError("db down")
        return _FakeResult(self.record)


class _FakeStore:
    def __init__(self, record=None, raises=False):
        self.record = record
        self.raises = raises

    def session(self):
        return _FakeSession(record=self.record, raises=self.raises)


def test_normalize_agent_name_aliases():
    assert DelegationGuardrails.normalize_agent_name("QA_Agent") == "QA_Assistant"
    assert DelegationGuardrails.normalize_agent_name("QAAssistantAgent") == "QA_Assistant"
    assert DelegationGuardrails.normalize_agent_name("SRE_Agent") == "SRE_Agent"


def test_validate_delegation_valid_and_invalid():
    valid = DelegationGuardrails.validate_delegation("Any", "Performance_Agent", "benchmark")
    invalid = DelegationGuardrails.validate_delegation("Any", "DevOps_Agent", "benchmark")

    assert valid["valid"] is True
    assert valid["confidence"] == 1.0

    assert invalid["valid"] is False
    assert "alternatives" in invalid
    assert "Performance_Agent" in invalid["suggestion"]


def test_validate_unknown_task_type_respects_strict():
    permissive = DelegationGuardrails.validate_delegation("A", "B", "unknown_task", strict=False)
    strict = DelegationGuardrails.validate_delegation("A", "B", "unknown_task", strict=True)

    assert permissive["valid"] is True
    assert strict["valid"] is False
    assert "Unknown task type" in strict["reason"]


def test_get_recommended_agent_and_self_delegation():
    assert DelegationGuardrails.get_recommended_agent("deploy") == "DevOps_Agent"
    assert DelegationGuardrails.get_recommended_agent("does_not_exist") is None

    same = DelegationGuardrails.check_self_delegation("QA_Agent", "QAAssistantAgent")
    different = DelegationGuardrails.check_self_delegation("QA_Agent", "SRE_Agent")

    assert same["is_self_delegation"] is True
    assert "logic error" in same["warning"]
    assert different == {"is_self_delegation": False, "warning": None}


def test_validate_with_history_without_store_returns_rule_validation():
    result = DelegationGuardrails.validate_with_history(
        from_agent="A",
        to_agent="Performance_Agent",
        task_type="benchmark",
        graph_store=None,
    )
    assert result["valid"] is True


def test_validate_with_history_low_success_rate_invalidates():
    store = _FakeStore(record={"total": 10, "success_rate": 0.2})

    result = DelegationGuardrails.validate_with_history(
        from_agent="X",
        to_agent="Performance_Agent",
        task_type="benchmark",
        graph_store=store,
        min_success_rate=0.7,
    )

    assert result["valid"] is False
    assert "Historical success rate" in result["reason"]
    assert result["confidence"] == 0.2


def test_validate_with_history_good_success_rate_keeps_valid():
    store = _FakeStore(record={"total": 5, "success_rate": 0.9})

    result = DelegationGuardrails.validate_with_history(
        from_agent="X",
        to_agent="Performance_Agent",
        task_type="benchmark",
        graph_store=store,
        min_success_rate=0.7,
    )

    assert result["valid"] is True
    assert result["confidence"] == 0.9


def test_validate_with_history_handles_store_exception():
    store = _FakeStore(raises=True)

    result = DelegationGuardrails.validate_with_history(
        from_agent="X",
        to_agent="Performance_Agent",
        task_type="benchmark",
        graph_store=store,
    )

    # Falls back to rule-based result on exception
    assert result["valid"] is True
    assert result["confidence"] == 1.0
