from contextlib import contextmanager

import pytest

import agenticqa.graph.delegation_store as ds


class _Result:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single
        self.consumed = False

    def __iter__(self):
        return iter(self._rows)

    def single(self):
        return self._single

    def consume(self):
        self.consumed = True


class _Session:
    def __init__(self, responses):
        self.responses = responses
        self.queries = []

    def run(self, query, **params):
        self.queries.append((query, params))
        for key, value in self.responses.items():
            if key in query:
                return value
        return _Result()


def _store_with_session(monkeypatch, responses):
    monkeypatch.setattr(ds, "NEO4J_AVAILABLE", True)
    store = ds.DelegationGraphStore(uri="bolt://x", user="u", password="p")
    fake_session = _Session(responses)

    @contextmanager
    def _session():
        yield fake_session

    monkeypatch.setattr(store, "session", _session)
    return store, fake_session


def test_create_update_and_record_delegation(monkeypatch):
    store, fake = _store_with_session(
        monkeypatch,
        {
            "RETURN a": _Result(single={"a": {"name": "SDET_Agent"}}),
            "RETURN d.delegation_id as id": _Result(single={"id": "d1"}),
        },
    )

    agent = store.create_or_update_agent("SDET_Agent", "qa")
    did = store.record_delegation("SDET_Agent", "SRE_Agent", {"task_type": "deploy"}, "d1")

    assert agent["name"] == "SDET_Agent"
    assert did == "d1"
    assert any("CREATE (from)-[d:DELEGATES_TO" in q for q, _ in fake.queries)


def test_recommend_target_and_history(monkeypatch):
    store, _ = _store_with_session(
        monkeypatch,
        {
            "ORDER BY priority_score": _Result(single={"recommended_agent": "SRE_Agent", "success_count": 3, "avg_duration": 100.0, "duration_stddev": 1.0, "priority_score": 30.0}),
            "ORDER BY d.timestamp DESC": _Result(rows=[{"from_agent": "A", "to_agent": "B", "task_json": "{}", "result_json": "{}", "duration_ms": 1.0, "timestamp": "2026"}]),
        },
    )

    rec = store.recommend_delegation_target("A", "deploy")
    history = store.get_delegation_history_for_task("deploy")

    assert rec["recommended_agent"] == "SRE_Agent"
    assert len(history) == 1


def test_predict_failure_risk_no_data_and_high_risk(monkeypatch):
    # no data path
    store1, _ = _store_with_session(monkeypatch, {"recent_statuses": _Result(single=None)})
    no_data = store1.predict_delegation_failure_risk("A", "B", "deploy")
    assert no_data["risk_level"] == "unknown"

    # high risk path
    store2, _ = _store_with_session(
        monkeypatch,
        {
            "recent_statuses": _Result(single={"total": 10, "failures": 5, "failure_rate": 0.5, "avg_duration": 100.0, "recent_statuses": ["failed", "failed", "success"]}),
        },
    )
    high = store2.predict_delegation_failure_risk("A", "B", "deploy")
    assert high["risk_level"] in {"medium", "high"}
    assert high["sample_size"] == 10


def test_cost_optimization_and_trends(monkeypatch):
    store, fake = _store_with_session(
        monkeypatch,
        {
            "p95_duration_ms": _Result(single={"total_delegations": 10, "total_seconds": 100.0, "avg_duration_ms": 50.0, "max_duration_ms": 200.0, "p95_duration_ms": 150.0}),
            "optimization_suggestion": _Result(rows=[]),
            "toString(period)": _Result(rows=[{"period": "2026-02-23", "delegations": 2, "avg_duration": 10.0, "successes": 2, "success_rate": 1.0}]),
        },
    )

    costs = store.calculate_cost_optimization(time_window_hours=24)
    trends = store.get_delegation_trends(days=7, granularity="invalid")

    assert costs["total_cost"] > 0
    assert len(trends) == 1
    # invalid granularity should default to day in generated query
    assert any("date.truncate('day'" in q for q, _ in fake.queries)


def test_get_agent_stats_and_not_found(monkeypatch):
    store_ok, _ = _store_with_session(
        monkeypatch,
        {
            "count(DISTINCT d_in)": _Result(single={"a": {"name": "A"}, "delegations_made": 2, "delegations_received": 3}),
        },
    )
    stats = store_ok.get_agent_stats("A")
    assert stats["name"] == "A"
    assert stats["delegations_made"] == 2

    store_none, _ = _store_with_session(monkeypatch, {"count(DISTINCT d_in)": _Result(single=None)})
    assert store_none.get_agent_stats("missing") is None


def test_core_analytics_queries(monkeypatch):
    rows = [{"agent": "SRE_Agent", "delegation_count": 3, "avg_duration_ms": 10.0, "successes": 2}]
    store, _ = _store_with_session(
        monkeypatch,
        {
            "ORDER BY delegation_count DESC": _Result(rows=rows),
            "ORDER BY chain_length DESC": _Result(rows=[{"origin": "A", "destination": "C", "chain_length": 2}]),
            "cycle_length": _Result(rows=[{"cycle": ["A", "B", "A"], "cycle_length": 2}]),
            "success_rate": _Result(rows=[{"from_agent": "A", "to_agent": "B", "success_rate": 1.0}]),
            "ORDER BY avg_duration DESC": _Result(rows=[{"agent": "B", "slow_delegations": 6}]),
        },
    )

    assert store.get_most_delegated_agents(limit=1) == rows
    assert store.find_delegation_chains(min_length=2, limit=1)[0]["origin"] == "A"
    assert store.find_circular_delegations()[0]["cycle"][0] == "A"
    assert store.get_delegation_success_rate_by_pair(limit=1)[0]["success_rate"] == 1.0
    assert store.find_bottleneck_agents(slow_threshold_ms=50, min_count=1)[0]["agent"] == "B"


def test_execution_stats_and_clear(monkeypatch):
    created = _Result()
    updated = _Result()
    cleared = _Result()
    stats = _Result(single={"total_agents": 2, "total_executions": 3, "total_delegations": 4})

    store, _ = _store_with_session(
        monkeypatch,
        {
            "MERGE (e:Execution": created,
            "SET e.status = $status": updated,
            "DETACH DELETE": cleared,
            "total_agents": stats,
        },
    )

    assert store.create_execution("exec1", "A", "task") == "exec1"
    store.update_execution_status("exec1", "success", duration_ms=12.0)
    store.clear_all_data()
    assert store.get_database_stats()["total_agents"] == 2


def test_find_optimal_path_and_no_path(monkeypatch):
    store_ok, _ = _store_with_session(
        monkeypatch,
        {
            "efficiency_score": _Result(
                single={
                    "path_agents": ["A", "B", "C"],
                    "hops": 2,
                    "endpoint": "C",
                    "total_duration": 33.0,
                    "efficiency_score": 900.0,
                }
            )
        },
    )
    path = store_ok.find_optimal_delegation_path("A", "deploy", max_hops=3)
    assert path["hops"] == 2
    assert path["path"] == ["A", "B", "C"]

    store_none, _ = _store_with_session(monkeypatch, {"efficiency_score": _Result(single=None)})
    assert store_none.find_optimal_delegation_path("A", "deploy") is None


def test_calculate_cost_optimization_empty_window(monkeypatch):
    store, _ = _store_with_session(monkeypatch, {"p95_duration_ms": _Result(single=None)})
    result = store.calculate_cost_optimization(time_window_hours=1)
    assert result["total_cost"] == 0.0
    assert result["optimization_opportunities"] == []


def test_connect_session_close_and_initialize_schema(monkeypatch):
    monkeypatch.setattr(ds, "NEO4J_AVAILABLE", True)

    class _ManagedSession:
        def __init__(self):
            self.runs = []
            self.closed = False

        def run(self, query, **params):
            self.runs.append((query, params))
            if "CREATE INDEX" in query:
                raise RuntimeError("index exists")
            return _Result(single={"ok": 1})

        def close(self):
            self.closed = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()

    class _Driver:
        def __init__(self):
            self.sessions = []
            self.closed = False

        def session(self, database=None):
            s = _ManagedSession()
            self.sessions.append((database, s))
            return s

        def close(self):
            self.closed = True

    fake_driver = _Driver()
    monkeypatch.setattr(ds.GraphDatabase, "driver", lambda *args, **kwargs: fake_driver)

    store = ds.DelegationGraphStore(uri="bolt://x", user="u", password="p")
    store.connect()
    assert store._connected is True

    with store.session() as s:
        assert s is not None
    assert s.closed is True

    store.initialize_schema()
    assert fake_driver.sessions  # multiple schema sessions executed

    store.close()
    assert fake_driver.closed is True


def test_connect_failure_resets_state(monkeypatch):
    monkeypatch.setattr(ds, "NEO4J_AVAILABLE", True)

    class _BadDriver:
        def __init__(self):
            self.closed = False

        def session(self, database=None):
            raise ds.ServiceUnavailable("down")

        def close(self):
            self.closed = True

    bad_driver = _BadDriver()
    monkeypatch.setattr(ds.GraphDatabase, "driver", lambda *args, **kwargs: bad_driver)

    store = ds.DelegationGraphStore(uri="bolt://x", user="u", password="p")
    with pytest.raises(ds.ServiceUnavailable):
        store.connect()

    assert store.driver is None
    assert store._connected is False
    assert bad_driver.closed is True


def test_record_and_update_result_handles_non_dict_task(monkeypatch):
    consume_marker = _Result(single={"id": "d2"})
    update_marker = _Result()
    store, fake = _store_with_session(
        monkeypatch,
        {
            "RETURN d.delegation_id as id": consume_marker,
            "SET d.status": update_marker,
        },
    )

    did = store.record_delegation("A", "B", "not-a-dict", "d2")
    store.update_delegation_result("d2", "failed", 55.0, result={"x": 1}, error_message="boom")

    assert did == "d2"
    assert consume_marker.consumed is True
    assert update_marker.consumed is True
    record_queries = [params for q, params in fake.queries if "DELEGATES_TO" in q]
    assert record_queries
    assert record_queries[0]["task_type"] == "unknown"
