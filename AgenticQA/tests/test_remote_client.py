from unittest.mock import MagicMock

from agenticqa.client import RemoteClient


def _mock_response(payload, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def test_init_normalizes_base_url_and_timeout():
    client = RemoteClient("http://localhost:8000/", timeout=12)
    assert client.base_url == "http://localhost:8000"
    assert client.timeout == 12


def test_execute_agents_posts_to_execute_endpoint():
    client = RemoteClient("http://api")
    client.session = MagicMock()
    client.session.post.return_value = _mock_response({"ok": True})

    payload = {"tests": ["a"]}
    result = client.execute_agents(payload)

    assert result == {"ok": True}
    client.session.post.assert_called_once_with(
        "http://api/api/agents/execute", json=payload, timeout=30
    )


def test_get_agent_insights_with_agent_param():
    client = RemoteClient("http://api")
    client.session = MagicMock()
    client.session.get.return_value = _mock_response({"insights": []})

    result = client.get_agent_insights("qa")

    assert result == {"insights": []}
    client.session.get.assert_called_once_with(
        "http://api/api/agents/insights", params={"agent": "qa"}, timeout=30
    )


def test_get_agent_insights_without_agent_param():
    client = RemoteClient("http://api")
    client.session = MagicMock()
    client.session.get.return_value = _mock_response({"all": True})

    result = client.get_agent_insights()

    assert result == {"all": True}
    client.session.get.assert_called_once_with(
        "http://api/api/agents/insights", params={}, timeout=30
    )


def test_history_search_artifact_and_stats_endpoints():
    client = RemoteClient("http://api")
    client.session = MagicMock()
    client.session.get.side_effect = [
        _mock_response([{"id": 1}]),
        _mock_response([{"artifact": "a"}]),
        _mock_response({"id": "abc"}),
        _mock_response({"total": 10}),
        _mock_response({"patterns": {}}),
    ]

    history = client.get_agent_history("qa", limit=5)
    search = client.search_artifacts("error", limit=3)
    artifact = client.get_artifact("abc")
    stats = client.get_datastore_stats()
    patterns = client.get_patterns()

    assert history == [{"id": 1}]
    assert search == [{"artifact": "a"}]
    assert artifact == {"id": "abc"}
    assert stats == {"total": 10}
    assert patterns == {"patterns": {}}

    expected_calls = [
        (("http://api/api/agents/qa/history",), {"params": {"limit": 5}, "timeout": 30}),
        (("http://api/api/datastore/search",), {"params": {"q": "error", "limit": 3}, "timeout": 30}),
        (("http://api/api/datastore/artifact/abc",), {"timeout": 30}),
        (("http://api/api/datastore/stats",), {"timeout": 30}),
        (("http://api/api/datastore/patterns",), {"timeout": 30}),
    ]
    assert client.session.get.call_args_list == expected_calls


def test_health_check_true_false_and_exception():
    client = RemoteClient("http://api")
    client.session = MagicMock()

    client.session.get.return_value = _mock_response({}, status_code=200)
    assert client.health_check() is True

    client.session.get.return_value = _mock_response({}, status_code=503)
    assert client.health_check() is False

    client.session.get.side_effect = RuntimeError("boom")
    assert client.health_check() is False


def test_context_manager_closes_session():
    client = RemoteClient("http://api")
    client.session = MagicMock()

    with client as cm:
        assert cm is client

    client.session.close.assert_called_once()
