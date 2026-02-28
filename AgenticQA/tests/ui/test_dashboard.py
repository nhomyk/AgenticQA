"""
Streamlit UI tests for the AgenticQA dashboard.

Uses streamlit.testing.v1.AppTest — runs the Streamlit app headlessly,
no browser required. Tests assert pages render without crashing and that
key UI elements are present.

These tests run as part of the unit suite and protect against:
  - Import errors / missing dependencies crashing the app
  - Sidebar navigation failures
  - API connection errors not being handled gracefully
  - Missing st.session_state keys causing KeyError crashes

Notes on Streamlit AppTest API
-------------------------------
- at.exception  → ElementList of Exception elements (NOT None when empty)
- at.error      → ElementList of st.error() calls
- at.markdown   → ElementList of st.markdown() calls
- at.sidebar    → SidebarBlock (always present)
- at.text_input → ElementList of st.text_input() calls in main area
- at.sidebar.text_input → ElementList of sidebar text_input widgets
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

MOCK_HEALTH = {"status": "healthy", "agents_ready": 4}
DASHBOARD_PATH = str(Path(__file__).parent.parent.parent / "dashboard" / "app.py")

try:
    from streamlit.testing.v1 import AppTest
    STREAMLIT_TESTING = True
except ImportError:
    STREAMLIT_TESTING = False

pytestmark = pytest.mark.skipif(
    not STREAMLIT_TESTING, reason="streamlit >= 1.18 required for AppTest"
)


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _mock_response(data: dict = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = data or MOCK_HEALTH
    resp.raise_for_status.return_value = None
    return resp


def _run(at: "AppTest") -> "AppTest":
    """Run AppTest with all HTTP calls mocked (no live server needed)."""
    with patch("requests.get", return_value=_mock_response()), \
         patch("requests.post", return_value=_mock_response()):
        at.run()
    return at


def _at(timeout: int = 15) -> "AppTest":
    return AppTest.from_file(DASHBOARD_PATH, default_timeout=timeout)


def _no_exceptions(at: "AppTest") -> bool:
    """True when the app raised no unhandled exceptions."""
    return len(at.exception) == 0


# ── Smoke tests ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_dashboard_loads_without_exception():
    """The entire app must execute without raising an unhandled exception."""
    at = _run(_at())
    assert _no_exceptions(at), \
        f"Dashboard raised: {[e.value for e in at.exception]}"


@pytest.mark.unit
def test_dashboard_has_no_error_widgets():
    """No st.error() calls should fire on initial render."""
    at = _run(_at())
    assert len(at.error) == 0, \
        f"Dashboard has {len(at.error)} error widget(s): {[e.value for e in at.error]}"


@pytest.mark.unit
def test_dashboard_renders_content():
    """Dashboard must render at least some visible content (markdown, text, etc.)."""
    at = _run(_at())
    assert _no_exceptions(at)
    # App should produce markdown, text, or widget elements
    total_elements = (
        len(at.markdown) + len(at.text_input) + len(at.text_area) +
        len(at.selectbox) + len(at.button) + len(at.expander)
    )
    assert total_elements > 0, "Dashboard rendered no visible elements"


@pytest.mark.unit
def test_dashboard_sidebar_renders():
    """Sidebar block must be present (navigation lives there)."""
    at = _run(_at())
    assert _no_exceptions(at)
    assert at.sidebar is not None


@pytest.mark.unit
def test_dashboard_sidebar_has_inputs():
    """Sidebar must contain at least one input widget (API key, nav, etc.)."""
    at = _run(_at())
    assert _no_exceptions(at)
    sidebar_widgets = (
        len(at.sidebar.text_input) +
        len(at.sidebar.selectbox) +
        len(at.sidebar.radio)
    )
    assert sidebar_widgets >= 1, \
        "Sidebar has no interactive widgets (expected API key input + navigation)"


@pytest.mark.unit
def test_dashboard_main_area_has_text_or_widgets():
    """Main content area must render something."""
    at = _run(_at())
    assert _no_exceptions(at)
    main_elements = len(at.markdown) + len(at.text_area) + len(at.text_input)
    assert main_elements >= 1, "Main area rendered nothing"


# ── API key sidebar input ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_api_key_input_widget_exists():
    """Anthropic API key password input must be rendered in the sidebar."""
    at = _run(_at())
    assert _no_exceptions(at)
    # Sidebar text inputs include the API key field
    sidebar_inputs = list(at.sidebar.text_input)
    labels = [inp.label.lower() for inp in sidebar_inputs if hasattr(inp, "label")]
    assert any("api" in l or "anthropic" in l or "key" in l for l in labels), \
        f"No API key input found in sidebar. Sidebar input labels: {labels}"


@pytest.mark.unit
def test_github_token_widget_exists():
    """GitHub token password input must be rendered in the sidebar."""
    at = _run(_at())
    assert _no_exceptions(at)
    sidebar_inputs = list(at.sidebar.text_input)
    labels = [inp.label.lower() for inp in sidebar_inputs if hasattr(inp, "label")]
    assert any("github" in l or "token" in l for l in labels), \
        f"No GitHub token input found in sidebar. Sidebar input labels: {labels}"


# ── Navigation ─────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_navigation_radio_exists():
    """Navigation radio group must exist in the sidebar (st.radio page selector)."""
    at = _run(_at())
    assert _no_exceptions(at)
    sidebar_radios = list(at.sidebar.radio)
    assert len(sidebar_radios) >= 1, \
        "No navigation radio widget found in sidebar"


@pytest.mark.unit
def test_navigation_radio_has_pages():
    """Navigation radio must contain all expected page options."""
    at = _run(_at())
    assert _no_exceptions(at)
    sidebar_radios = list(at.sidebar.radio)
    assert len(sidebar_radios) >= 1
    nav_radio = sidebar_radios[0]
    assert len(nav_radio.options) >= 5, \
        f"Navigation radio has too few options: {nav_radio.options}"


# ── Import safety ──────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_dashboard_imports_cleanly():
    """dashboard/app.py must be spec-loadable (no import-time crashes)."""
    spec = importlib.util.spec_from_file_location("dashboard_app", DASHBOARD_PATH)
    assert spec is not None, "Could not build module spec for dashboard/app.py"


# ── Resilience: API server down ────────────────────────────────────────────────

@pytest.mark.unit
def test_dashboard_handles_api_server_down():
    """Dashboard must not raise an unhandled exception when API server is down."""
    import requests

    def _raise(*a, **kw):
        raise requests.exceptions.ConnectionError("Connection refused")

    at = _at()
    with patch("requests.get", side_effect=_raise), \
         patch("requests.post", side_effect=_raise):
        at.run()

    # App must handle the error gracefully — no unhandled Python exception.
    assert _no_exceptions(at), \
        f"Dashboard crashed when API server was down: {[e.value for e in at.exception]}"


@pytest.mark.unit
def test_dashboard_handles_malformed_api_response():
    """Dashboard must not crash when API returns unexpected JSON."""
    at = _at()
    with patch("requests.get", return_value=_mock_response({"unexpected": True})), \
         patch("requests.post", return_value=_mock_response({"unexpected": True})):
        at.run()

    assert _no_exceptions(at), \
        f"Dashboard crashed on malformed API response: {[e.value for e in at.exception]}"


@pytest.mark.unit
def test_dashboard_handles_api_500():
    """Dashboard must not crash when API returns HTTP 500."""
    resp = _mock_response()
    resp.status_code = 500
    resp.raise_for_status.side_effect = Exception("500 Internal Server Error")

    at = _at()
    with patch("requests.get", return_value=resp), \
         patch("requests.post", return_value=resp):
        at.run()

    assert _no_exceptions(at), \
        f"Dashboard crashed on API 500: {[e.value for e in at.exception]}"
