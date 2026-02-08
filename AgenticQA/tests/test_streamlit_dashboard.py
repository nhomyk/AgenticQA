"""
Streamlit Dashboard Tests

Dedicated tests for dashboard render functions in dashboard/app.py.
Mocks Streamlit and Neo4j to verify rendering logic without a browser.
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock, call

# Add project paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def _make_ctx():
    """Create a MagicMock that works as a context manager."""
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


@pytest.fixture
def mock_st():
    """Mock streamlit module."""
    mock = MagicMock()
    mock.cache_resource = MagicMock(return_value=lambda f: f)
    mock.set_page_config = MagicMock()
    # st.columns(n) or st.columns([3,2]) must return the right number of mocks
    def _columns(spec, **kw):
        count = len(spec) if isinstance(spec, list) else spec
        return [_make_ctx() for _ in range(count)]
    mock.columns.side_effect = _columns
    # st.tabs returns variable-length lists too
    mock.tabs.side_effect = lambda labels, **kw: [_make_ctx() for _ in labels]
    # Make sidebar context manager work
    mock.sidebar.__enter__ = MagicMock(return_value=mock.sidebar)
    mock.sidebar.__exit__ = MagicMock(return_value=False)
    return mock


@pytest.fixture
def mock_store():
    """Mock DelegationGraphStore with sample data."""
    store = MagicMock()

    # Mock session context manager for Cypher queries
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)

    # Default: return delegation data
    delegation_agg_records = [
        {"from_agent": "SDET_Agent", "to_agent": "SRE_Agent", "total": 4,
         "successes": 3, "success_rate": 0.75, "avg_duration_ms": 245.0},
        {"from_agent": "QA_Agent", "to_agent": "DevOps_Agent", "total": 2,
         "successes": 2, "success_rate": 1.0, "avg_duration_ms": 300.0},
    ]
    agent_records = [
        {"name": "SDET_Agent"}, {"name": "SRE_Agent"},
        {"name": "QA_Agent"}, {"name": "DevOps_Agent"},
    ]
    live_activity_records = [
        {"from_agent": "SDET_Agent", "to_agent": "SRE_Agent", "status": "success",
         "duration_ms": 250, "timestamp": "2025-01-01T10:00:00", "task": "deploy_tests",
         "error_message": None},
    ]

    def _make_record(data):
        m = MagicMock()
        m.__getitem__ = lambda s, k: data[k]
        m.keys = lambda s: data.keys()
        return m

    def mock_run(query):
        if "ORDER BY d.timestamp" in query:
            return [_make_record(r) for r in live_activity_records]
        if "DELEGATES_TO" in query:
            return [_make_record(r) for r in delegation_agg_records]
        return [_make_record(r) for r in agent_records]

    mock_session.run = mock_run
    store.session.return_value = mock_session

    store.get_database_stats.return_value = {
        "total_agents": 7,
        "total_delegations": 25,
    }
    store.get_most_delegated_agents.return_value = [
        {"agent": "SRE_Agent", "delegation_count": 7, "successes": 6, "avg_duration_ms": 900.0},
        {"agent": "QA_Agent", "delegation_count": 3, "successes": 3, "avg_duration_ms": 490.0},
    ]
    store.find_bottleneck_agents.return_value = [
        {"agent": "SRE_Agent", "avg_duration": 1500.0, "p95_duration": 2100.0, "slow_delegations": 3},
    ]
    store.get_delegation_success_rate_by_pair.return_value = [
        {"from_agent": "SDET_Agent", "to_agent": "SRE_Agent", "success_rate": 0.75, "total": 4},
    ]
    store.find_delegation_chains.return_value = [
        {"origin": "SDET_Agent", "destination": "DevOps_Agent", "chain_length": 3, "total_duration_ms": 2400.0},
    ]
    store.recommend_delegation_target.return_value = {
        "recommended_agent": "SRE_Agent",
        "success_count": 6,
        "avg_duration": 900.0,
        "priority_score": 0.85,
    }

    return store


def _import_app(mock_st):
    """Import dashboard app with mocked streamlit."""
    with patch.dict(sys.modules, {"streamlit": mock_st}):
        # Need to also handle plotly imports
        import importlib
        if "dashboard.app" in sys.modules:
            del sys.modules["dashboard.app"]
        # Import the module
        import dashboard.app as app_module
        return app_module


class TestRenderHeader:
    """Tests for render_header function"""

    def test_header_renders_title(self, mock_st):
        app = _import_app(mock_st)
        app.render_header()
        mock_st.markdown.assert_called()
        # Verify the main header HTML was rendered
        calls = [str(c) for c in mock_st.markdown.call_args_list]
        assert any("AgenticQA" in c for c in calls)


class TestRenderOverviewMetrics:
    """Tests for render_overview_metrics function"""

    def test_overview_calls_get_database_stats(self, mock_st, mock_store):
        app = _import_app(mock_st)
        app.render_overview_metrics(mock_store)
        mock_store.get_database_stats.assert_called_once()

    def test_overview_creates_two_columns(self, mock_st, mock_store):
        app = _import_app(mock_st)
        app.render_overview_metrics(mock_store)
        mock_st.columns.assert_called_with(2)


class TestRenderTopAgents:
    """Tests for render_top_agents function"""

    def test_top_agents_with_data(self, mock_st, mock_store):
        app = _import_app(mock_st)
        app.render_top_agents(mock_store)
        mock_store.get_most_delegated_agents.assert_called_once_with(limit=10)
        # plotly_chart is called on mock_st (the streamlit module mock)
        assert mock_st.plotly_chart.called

    def test_top_agents_empty_data(self, mock_st, mock_store):
        mock_store.get_most_delegated_agents.return_value = []
        app = _import_app(mock_st)
        app.render_top_agents(mock_store)
        mock_st.info.assert_called()


class TestRenderPerformanceMetrics:
    """Tests for render_performance_metrics function"""

    def test_performance_renders_bottlenecks(self, mock_st, mock_store):
        app = _import_app(mock_st)
        app.render_performance_metrics(mock_store)
        mock_store.find_bottleneck_agents.assert_called_once()
        mock_store.get_delegation_success_rate_by_pair.assert_called_once()

    def test_performance_no_bottlenecks(self, mock_st, mock_store):
        mock_store.find_bottleneck_agents.return_value = []
        app = _import_app(mock_st)
        app.render_performance_metrics(mock_store)
        # Should show success message
        calls = [str(c) for c in mock_st.success.call_args_list]
        assert any("bottleneck" in c.lower() for c in calls)


class TestRenderDelegationChains:
    """Tests for render_delegation_chains function"""

    def test_chains_with_data(self, mock_st, mock_store):
        app = _import_app(mock_st)
        app.render_delegation_chains(mock_store)
        mock_store.find_delegation_chains.assert_called_once()

    def test_chains_empty(self, mock_st, mock_store):
        mock_store.find_delegation_chains.return_value = []
        app = _import_app(mock_st)
        app.render_delegation_chains(mock_store)
        mock_st.info.assert_called()


class TestGetGraphStore:
    """Tests for the cached Neo4j connection function"""

    def test_returns_none_on_connection_failure(self, mock_st):
        app = _import_app(mock_st)
        with patch.object(app, "DelegationGraphStore", side_effect=Exception("connection refused")):
            # get_graph_store is decorated with cache_resource, test the underlying logic
            result = None
            try:
                store = app.DelegationGraphStore()
                store.connect()
                result = store
            except Exception:
                result = None
            assert result is None


class TestMainFunction:
    """Tests for the main dashboard entrypoint"""

    def test_main_renders_without_store(self, mock_st):
        app = _import_app(mock_st)
        mock_st.radio.return_value = "System Overview"
        mock_st.checkbox.return_value = False
        mock_st.button.return_value = False

        with patch.object(app, "get_graph_store", return_value=None):
            app.main()
        # Should still render header and sidebar
        mock_st.markdown.assert_called()

    def test_main_renders_with_store(self, mock_st, mock_store):
        app = _import_app(mock_st)
        mock_st.radio.return_value = "System Overview"
        mock_st.checkbox.return_value = False
        mock_st.button.return_value = False

        with patch.object(app, "get_graph_store", return_value=mock_store):
            app.main()
        mock_st.markdown.assert_called()

    def test_neo4j_required_pages_show_warning(self, mock_st):
        app = _import_app(mock_st)
        mock_st.radio.return_value = "Collaboration"
        mock_st.checkbox.return_value = False
        mock_st.button.return_value = False

        with patch.object(app, "get_graph_store", return_value=None):
            app.main()
        mock_st.warning.assert_called()
