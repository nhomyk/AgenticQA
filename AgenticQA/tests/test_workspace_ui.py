"""Tests for the workspace dashboard UI.

Validates:
  - render_workspace function exists and is callable
  - All workspace sub-render functions exist
  - Workspace is in the navigation pages list
  - Workspace is the default landing page
"""
import pytest


@pytest.mark.unit
def test_render_workspace_exists():
    """render_workspace function is importable from dashboard."""
    import importlib
    import sys
    # Add dashboard to path if needed
    sys.path.insert(0, "dashboard")
    try:
        spec = importlib.util.spec_from_file_location("app", "dashboard/app.py")
        mod = importlib.util.module_from_spec(spec)

        # Mock streamlit to avoid UI initialisation
        from unittest.mock import MagicMock
        mock_st = MagicMock()
        mock_st.set_page_config = MagicMock()
        mock_st.cache_resource = lambda f: f
        sys.modules["streamlit"] = mock_st
        sys.modules["plotly"] = MagicMock()
        sys.modules["plotly.express"] = MagicMock()
        sys.modules["plotly.graph_objects"] = MagicMock()
        sys.modules["pandas"] = MagicMock()

        spec.loader.exec_module(mod)

        assert hasattr(mod, "render_workspace"), "render_workspace should exist"
        assert callable(mod.render_workspace)
    finally:
        # Cleanup mock modules
        for m in ["streamlit", "plotly", "plotly.express", "plotly.graph_objects", "pandas"]:
            sys.modules.pop(m, None)


@pytest.mark.unit
def test_workspace_sub_renders_exist():
    """All workspace sub-render functions exist."""
    import importlib
    import sys

    sys.path.insert(0, "dashboard")
    try:
        spec = importlib.util.spec_from_file_location("app", "dashboard/app.py")
        mod = importlib.util.module_from_spec(spec)

        from unittest.mock import MagicMock
        mock_st = MagicMock()
        mock_st.set_page_config = MagicMock()
        mock_st.cache_resource = lambda f: f
        sys.modules["streamlit"] = mock_st
        sys.modules["plotly"] = MagicMock()
        sys.modules["plotly.express"] = MagicMock()
        sys.modules["plotly.graph_objects"] = MagicMock()
        sys.modules["pandas"] = MagicMock()

        spec.loader.exec_module(mod)

        expected = [
            "_render_workspace_files",
            "_render_workspace_email",
            "_render_workspace_links",
            "_render_workspace_safety",
        ]
        for name in expected:
            assert hasattr(mod, name), f"{name} should exist in dashboard app"
    finally:
        for m in ["streamlit", "plotly", "plotly.express", "plotly.graph_objects", "pandas"]:
            sys.modules.pop(m, None)


@pytest.mark.unit
def test_workspace_in_navigation():
    """Workspace page appears in the navigation pages list."""
    # Read the source directly to check the pages list
    with open("dashboard/app.py") as f:
        source = f.read()

    assert '"Workspace"' in source, "Workspace should be in pages list"
    # Check it's the first page (default landing)
    pages_line = [l for l in source.split("\n") if "pages = [" in l and "Workspace" in l]
    assert len(pages_line) >= 1, "Workspace should be in pages array"
    # Workspace should be first
    idx = pages_line[0].index('"Workspace"')
    bracket_idx = pages_line[0].index("[")
    assert idx < pages_line[0].index('"Live Pipeline Demo"'), \
        "Workspace should come before Live Pipeline Demo"


@pytest.mark.unit
def test_workspace_is_default_landing():
    """Workspace is the default landing page."""
    with open("dashboard/app.py") as f:
        source = f.read()

    # The default else clause should point to Workspace
    assert 'default_index = pages.index("Workspace")' in source


@pytest.mark.unit
def test_workspace_query_param_routing():
    """?view=workspace routes to Workspace page."""
    with open("dashboard/app.py") as f:
        source = f.read()

    assert '"workspace"' in source
    assert '"files"' in source or '"mail"' in source


@pytest.mark.unit
def test_workspace_render_route():
    """Workspace page is routed in the if/elif chain."""
    with open("dashboard/app.py") as f:
        source = f.read()

    assert 'page == "Workspace"' in source
    assert "render_workspace()" in source
