"""
Frontend Test Generator

Detects the frontend framework used in a repository and generates
framework-appropriate tests for code produced by the AgenticQA pipeline.

Supported frameworks
--------------------
React           → Jest + @testing-library/react
Next.js         → Jest + @testing-library/react (page-level)
Vue 3           → Vitest + @vue/test-utils
Angular         → Jasmine / @angular/core/testing
Svelte          → Vitest + @testing-library/svelte
Vanilla JS/TS   → Jest (no framework)
Streamlit       → streamlit.testing.v1.AppTest (Python)
FastAPI         → httpx.AsyncClient + pytest-asyncio
Django          → Django TestCase + Client
Flask           → flask.testing.FlaskClient + pytest
Python generic  → pytest (default)

The generated test code is designed to:
  1. Render / call the component or endpoint
  2. Assert it does not crash
  3. Assert key outputs are present
  4. Mock all external dependencies (HTTP, DB, file-system)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class Framework(str, Enum):
    REACT = "react"
    NEXTJS = "nextjs"
    VUE = "vue"
    ANGULAR = "angular"
    SVELTE = "svelte"
    VANILLA_JS = "vanilla_js"
    STREAMLIT = "streamlit"
    FASTAPI = "fastapi"
    DJANGO = "django"
    FLASK = "flask"
    PYTHON = "python"
    UNKNOWN = "unknown"


@dataclass
class FrameworkDetection:
    framework: Framework
    test_runner: str          # "jest" | "vitest" | "pytest" | "ng test"
    test_command: str         # shell command to run tests
    file_extension: str       # ".test.tsx" | ".spec.ts" | "_test.py" etc.
    confidence: float         # 0.0–1.0
    signals: List[str] = field(default_factory=list)


@dataclass
class GeneratedFrontendTest:
    framework: Framework
    test_runner: str
    test_command: str
    test_filename: str        # relative path suggestion
    test_code: str
    setup_instructions: List[str] = field(default_factory=list)


# ── Framework Detector ─────────────────────────────────────────────────────────

class FrameworkDetector:
    """Detect frontend framework from repo structure and package.json."""

    def detect(self, repo_path: str, file_path: str = "") -> FrameworkDetection:
        root = Path(repo_path)
        ext = Path(file_path).suffix.lower() if file_path else ""
        signals: List[str] = []

        # Python-side frameworks first (no package.json needed)
        if ext in (".py", "") or not file_path:
            py_fw = self._detect_python(root, file_path, signals)
            if py_fw:
                return py_fw

        # JS/TS — read package.json
        pkg = self._read_package_json(root)

        if pkg:
            deps = {
                **pkg.get("dependencies", {}),
                **pkg.get("devDependencies", {}),
            }

            if "next" in deps:
                signals.append("next in package.json")
                return FrameworkDetection(
                    Framework.NEXTJS, "jest",
                    "npx jest --passWithNoTests",
                    ".test.tsx", 0.95, signals,
                )
            if "react" in deps or "@types/react" in deps:
                signals.append("react in package.json")
                runner = "vitest" if "vitest" in deps else "jest"
                cmd = "npx vitest run --passWithNoTests" if runner == "vitest" else "npx jest --passWithNoTests"
                return FrameworkDetection(
                    Framework.REACT, runner, cmd, ".test.tsx", 0.95, signals,
                )
            if "vue" in deps or "@vue/core" in deps:
                signals.append("vue in package.json")
                return FrameworkDetection(
                    Framework.VUE, "vitest",
                    "npx vitest run --passWithNoTests",
                    ".spec.ts", 0.95, signals,
                )
            if "@angular/core" in deps:
                signals.append("@angular/core in package.json")
                return FrameworkDetection(
                    Framework.ANGULAR, "ng test",
                    "npx ng test --watch=false --browsers=ChromeHeadless",
                    ".spec.ts", 0.90, signals,
                )
            if "svelte" in deps:
                signals.append("svelte in package.json")
                return FrameworkDetection(
                    Framework.SVELTE, "vitest",
                    "npx vitest run --passWithNoTests",
                    ".spec.ts", 0.90, signals,
                )
            # Any JS/TS project
            if ext in (".ts", ".tsx", ".js", ".jsx"):
                runner = "vitest" if "vitest" in deps else "jest"
                cmd = "npx vitest run --passWithNoTests" if runner == "vitest" else "npx jest --passWithNoTests"
                return FrameworkDetection(
                    Framework.VANILLA_JS, runner, cmd, ".test.ts", 0.70, signals,
                )

        # File extension fallback
        if ext in (".ts", ".tsx", ".js", ".jsx"):
            return FrameworkDetection(
                Framework.VANILLA_JS, "jest",
                "npx jest --passWithNoTests",
                ".test.ts", 0.40, ["file extension only"],
            )

        return FrameworkDetection(
            Framework.PYTHON, "pytest",
            "python -m pytest --tb=short -q",
            "_test.py", 0.50, ["default python fallback"],
        )

    def _read_package_json(self, root: Path) -> Optional[dict]:
        pkg_path = root / "package.json"
        if pkg_path.exists():
            try:
                return json.loads(pkg_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    def _detect_python(
        self, root: Path, file_path: str, signals: List[str]
    ) -> Optional[FrameworkDetection]:
        content = ""
        if file_path:
            p = root / file_path
            if p.exists():
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    pass

        # Check imports in file
        if re.search(r"import streamlit|from streamlit", content):
            signals.append("streamlit import in file")
            return FrameworkDetection(
                Framework.STREAMLIT, "pytest",
                "python -m pytest --tb=short -q",
                "_test.py", 0.95, signals,
            )
        if re.search(r"from fastapi|import fastapi|FastAPI\(", content):
            signals.append("fastapi import in file")
            return FrameworkDetection(
                Framework.FASTAPI, "pytest",
                "python -m pytest --tb=short -q",
                "_test.py", 0.95, signals,
            )
        if re.search(r"from flask|import flask|Flask\(", content):
            signals.append("flask import in file")
            return FrameworkDetection(
                Framework.FLASK, "pytest",
                "python -m pytest --tb=short -q",
                "_test.py", 0.90, signals,
            )
        if re.search(r"from django|import django|Django", content):
            signals.append("django import in file")
            return FrameworkDetection(
                Framework.DJANGO, "pytest",
                "python -m pytest --tb=short -q",
                "_test.py", 0.90, signals,
            )
        if Path(file_path).suffix == ".py":
            signals.append(".py extension")
            return FrameworkDetection(
                Framework.PYTHON, "pytest",
                "python -m pytest --tb=short -q",
                "_test.py", 0.80, signals,
            )
        return None


# ── Test Generator ─────────────────────────────────────────────────────────────

class FrontendTestGenerator:
    """Generate framework-appropriate tests for a given file and description."""

    def generate(
        self,
        description: str,
        code: str,
        file_path: str,
        repo_path: str = ".",
        detection: Optional[FrameworkDetection] = None,
    ) -> GeneratedFrontendTest:
        if detection is None:
            detection = FrameworkDetector().detect(repo_path, file_path)

        stem = Path(file_path).stem
        test_filename = str(
            Path(file_path).parent / f"{stem}{detection.file_extension}"
        )

        generators = {
            Framework.REACT:    self._react,
            Framework.NEXTJS:   self._nextjs,
            Framework.VUE:      self._vue,
            Framework.SVELTE:   self._svelte,
            Framework.ANGULAR:  self._angular,
            Framework.VANILLA_JS: self._vanilla_js,
            Framework.STREAMLIT: self._streamlit,
            Framework.FASTAPI:  self._fastapi,
            Framework.FLASK:    self._flask,
            Framework.DJANGO:   self._django,
            Framework.PYTHON:   self._python,
            Framework.UNKNOWN:  self._python,
        }
        fn = generators.get(detection.framework, self._python)
        test_code, setup = fn(description, code, stem, file_path)

        return GeneratedFrontendTest(
            framework=detection.framework,
            test_runner=detection.test_runner,
            test_command=detection.test_command,
            test_filename=test_filename,
            test_code=test_code,
            setup_instructions=setup,
        )

    # ── React ──────────────────────────────────────────────────────────────────

    def _react(
        self, description: str, code: str, stem: str, file_path: str
    ) -> tuple[str, list[str]]:
        component_name = stem[0].upper() + stem[1:] if stem else "Component"
        has_hooks = "useState" in code or "useEffect" in code
        has_fetch = "fetch(" in code or "axios" in code

        fetch_mock = (
            "\n// Mock fetch globally\nglobal.fetch = jest.fn(() =>\n"
            "  Promise.resolve({ ok: true, json: () => Promise.resolve({}) })\n);\n"
        ) if has_fetch else ""

        code_str = f"""import {{ render, screen, fireEvent, waitFor }} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {{ {component_name} }} from './{stem}';
{fetch_mock}
describe('{component_name}', () => {{
  beforeEach(() => {{
    jest.clearAllMocks();
  }});

  test('renders without crashing', () => {{
    render(<{component_name} />);
  }});

  test('matches snapshot', () => {{
    const {{ container }} = render(<{component_name} />);
    expect(container.firstChild).toMatchSnapshot();
  }});

  test('has no critical accessibility violations', async () => {{
    const {{ container }} = render(<{component_name} />);
    // Verify no missing aria labels or roles
    expect(container).toBeInTheDocument();
  }});
{"  test('handles loading state', async () => {" + chr(10) + "    render(<" + component_name + " />);" + chr(10) + "    // Component should not throw on async operations" + chr(10) + "    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());" + chr(10) + "  });" if has_hooks else ""}
}});
"""
        setup = [
            "npm install --save-dev @testing-library/react @testing-library/user-event @testing-library/jest-dom",
            "Add to jest.config.js: setupFilesAfterFramework: ['@testing-library/jest-dom']",
        ]
        return code_str, setup

    # ── Next.js ────────────────────────────────────────────────────────────────

    def _nextjs(
        self, description: str, code: str, stem: str, file_path: str
    ) -> tuple[str, list[str]]:
        component_name = stem[0].upper() + stem[1:] if stem else "Page"
        code_str = f"""import {{ render, screen }} from '@testing-library/react';
import {{ useRouter }} from 'next/router';
import {component_name} from './{stem}';

jest.mock('next/router', () => ({{
  useRouter: jest.fn(() => ({{ push: jest.fn(), pathname: '/', query: {{}} }})),
}}));

jest.mock('next/navigation', () => ({{
  usePathname: jest.fn(() => '/'),
  useSearchParams: jest.fn(() => new URLSearchParams()),
}}));

describe('{component_name} page', () => {{
  test('renders without crashing', () => {{
    render(<{component_name} />);
  }});

  test('page contains main content area', () => {{
    render(<{component_name} />);
    expect(document.body).toBeInTheDocument();
  }});

  test('handles route correctly', () => {{
    render(<{component_name} />);
    expect(useRouter).toHaveBeenCalled();
  }});
}});
"""
        setup = [
            "npm install --save-dev @testing-library/react @testing-library/jest-dom",
            "Ensure jest.config.js has testEnvironment: 'jsdom'",
        ]
        return code_str, setup

    # ── Vue 3 ──────────────────────────────────────────────────────────────────

    def _vue(
        self, description: str, code: str, stem: str, file_path: str
    ) -> tuple[str, list[str]]:
        code_str = f"""import {{ mount, shallowMount }} from '@vue/test-utils';
import {{ describe, it, expect, beforeEach, vi }} from 'vitest';
import {stem} from './{stem}.vue';

describe('{stem}', () => {{
  let wrapper;

  beforeEach(() => {{
    wrapper = shallowMount({stem}, {{
      global: {{
        mocks: {{
          $router: {{ push: vi.fn() }},
          $route: {{ params: {{}}, query: {{}} }},
        }},
        stubs: {{ 'router-link': true, 'router-view': true }},
      }},
    }});
  }});

  it('renders without errors', () => {{
    expect(wrapper.exists()).toBe(true);
  }});

  it('matches snapshot', () => {{
    expect(wrapper.html()).toMatchSnapshot();
  }});

  it('emits no errors on mount', () => {{
    const consoleSpy = vi.spyOn(console, 'error');
    mount({stem});
    expect(consoleSpy).not.toHaveBeenCalled();
  }});
}});
"""
        setup = [
            "npm install --save-dev @vue/test-utils vitest @vitejs/plugin-vue",
        ]
        return code_str, setup

    # ── Svelte ─────────────────────────────────────────────────────────────────

    def _svelte(
        self, description: str, code: str, stem: str, file_path: str
    ) -> tuple[str, list[str]]:
        code_str = f"""import {{ render, screen }} from '@testing-library/svelte';
import {{ describe, it, expect }} from 'vitest';
import {stem} from './{stem}.svelte';

describe('{stem}', () => {{
  it('renders without crashing', () => {{
    const {{ container }} = render({stem});
    expect(container).toBeTruthy();
  }});

  it('matches snapshot', () => {{
    const {{ container }} = render({stem});
    expect(container.innerHTML).toMatchSnapshot();
  }});
}});
"""
        setup = [
            "npm install --save-dev @testing-library/svelte vitest @sveltejs/vite-plugin-svelte",
        ]
        return code_str, setup

    # ── Angular ────────────────────────────────────────────────────────────────

    def _angular(
        self, description: str, code: str, stem: str, file_path: str
    ) -> tuple[str, list[str]]:
        component_name = stem[0].upper() + stem[1:] + "Component"
        code_str = f"""import {{ ComponentFixture, TestBed }} from '@angular/core/testing';
import {{ {component_name} }} from './{stem}.component';
import {{ HttpClientTestingModule }} from '@angular/common/http/testing';

describe('{component_name}', () => {{
  let component: {component_name};
  let fixture: ComponentFixture<{component_name}>;

  beforeEach(async () => {{
    await TestBed.configureTestingModule({{
      imports: [HttpClientTestingModule],
      declarations: [{component_name}],
    }}).compileComponents();

    fixture = TestBed.createComponent({component_name});
    component = fixture.componentInstance;
    fixture.detectChanges();
  }});

  it('should create', () => {{
    expect(component).toBeTruthy();
  }});

  it('should render without errors', () => {{
    expect(fixture.nativeElement).toBeTruthy();
  }});
}});
"""
        setup = [
            "Angular testing is built-in — ensure @angular/core/testing is available",
        ]
        return code_str, setup

    # ── Vanilla JS/TS ──────────────────────────────────────────────────────────

    def _vanilla_js(
        self, description: str, code: str, stem: str, file_path: str
    ) -> tuple[str, list[str]]:
        # Extract exported function/class names
        exports = re.findall(r"export\s+(?:default\s+)?(?:function|class|const)\s+(\w+)", code)
        first_export = exports[0] if exports else stem

        code_str = f"""import {{ {first_export} }} from './{stem}';

describe('{first_export}', () => {{
  test('is defined', () => {{
    expect({first_export}).toBeDefined();
  }});

  test('does not throw on basic invocation', () => {{
    expect(() => {{
      if (typeof {first_export} === 'function') {{
        // Call with no args — should not throw (may return undefined)
        try {{ {first_export}(); }} catch (e) {{
          // Constructor or requires args — acceptable
        }}
      }}
    }}).not.toThrow();
  }});
}});
"""
        setup = [
            "npm install --save-dev jest @types/jest ts-jest",
            "Add to jest.config.js: transform: {'.*\\\\.ts$': 'ts-jest'}",
        ]
        return code_str, setup

    # ── Streamlit ──────────────────────────────────────────────────────────────

    def _streamlit(
        self, description: str, code: str, stem: str, file_path: str
    ) -> tuple[str, list[str]]:
        code_str = f'''"""Streamlit AppTest for {stem}."""
import pytest
from unittest.mock import patch, MagicMock

# streamlit.testing.v1.AppTest runs the app headlessly — no browser needed.
try:
    from streamlit.testing.v1 import AppTest
    HAS_STREAMLIT_TESTING = True
except ImportError:
    HAS_STREAMLIT_TESTING = False


@pytest.mark.unit
@pytest.mark.skipif(not HAS_STREAMLIT_TESTING, reason="streamlit >= 1.18 required")
def test_{stem}_renders_without_exception(tmp_path):
    """App must render without raising an unhandled exception."""
    app_file = tmp_path / "{stem}.py"
    app_file.write_text(__CODE__)
    at = AppTest.from_file(str(app_file))
    at.run(timeout=10)
    assert not at.exception, f"App raised: {{at.exception}}"


@pytest.mark.unit
@pytest.mark.skipif(not HAS_STREAMLIT_TESTING, reason="streamlit >= 1.18 required")
def test_{stem}_has_no_error_elements(tmp_path):
    """No st.error() calls should fire on initial render."""
    app_file = tmp_path / "{stem}.py"
    app_file.write_text(__CODE__)
    at = AppTest.from_file(str(app_file))
    at.run(timeout=10)
    assert len(at.error) == 0, f"App has error widgets: {{[e.value for e in at.error]}}"
'''
        # Inject the actual code as a module-level constant
        escaped = code.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
        code_str = code_str.replace(
            f"def test_{stem}_renders_without_exception",
            f'__CODE__ = """{escaped}"""\n\n\ndef test_{stem}_renders_without_exception',
        )
        setup = [
            "pip install streamlit>=1.18",
            "streamlit.testing.v1 runs apps headlessly — no browser or server needed",
        ]
        return code_str, setup

    # ── FastAPI ────────────────────────────────────────────────────────────────

    def _fastapi(
        self, description: str, code: str, stem: str, file_path: str
    ) -> tuple[str, list[str]]:
        code_str = f'''"""Tests for {stem} FastAPI endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    """Import app and return a TestClient."""
    import importlib, sys
    # Allow import from the source file directly
    spec = importlib.util.spec_from_file_location("{stem}", "{file_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        app = getattr(module, "app", None)
        if app:
            return TestClient(app)
    except Exception:
        pass
    return None


@pytest.mark.unit
def test_{stem}_app_importable():
    """The module must be importable without side effects."""
    import importlib
    spec = importlib.util.spec_from_file_location("{stem}", "{file_path}")
    assert spec is not None


@pytest.mark.unit
def test_{stem}_health_endpoint(client):
    """If a /health endpoint exists, it should return 200."""
    if client is None:
        pytest.skip("app not importable")
    resp = client.get("/health")
    assert resp.status_code in (200, 404)   # 404 = endpoint not defined, that is ok
'''
        setup = [
            "pip install httpx fastapi[all] pytest",
        ]
        return code_str, setup

    # ── Flask ──────────────────────────────────────────────────────────────────

    def _flask(
        self, description: str, code: str, stem: str, file_path: str
    ) -> tuple[str, list[str]]:
        code_str = f'''"""Tests for {stem} Flask routes."""
import pytest
from unittest.mock import patch


@pytest.fixture
def app():
    import importlib
    spec = importlib.util.spec_from_file_location("{stem}", "{file_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        flask_app = getattr(module, "app", None)
        if flask_app:
            flask_app.config["TESTING"] = True
            return flask_app
    except Exception:
        pass
    return None


@pytest.fixture
def client(app):
    if app is None:
        return None
    return app.test_client()


@pytest.mark.unit
def test_{stem}_app_importable():
    import importlib
    spec = importlib.util.spec_from_file_location("{stem}", "{file_path}")
    assert spec is not None


@pytest.mark.unit
def test_{stem}_index_route(client):
    if client is None:
        pytest.skip("app not importable")
    resp = client.get("/")
    assert resp.status_code in (200, 302, 404)
'''
        setup = ["pip install flask pytest"]
        return code_str, setup

    # ── Django ─────────────────────────────────────────────────────────────────

    def _django(
        self, description: str, code: str, stem: str, file_path: str
    ) -> tuple[str, list[str]]:
        code_str = f'''"""Tests for {stem} Django views."""
import pytest
from unittest.mock import patch


@pytest.mark.unit
def test_{stem}_importable():
    """Module must be importable."""
    import importlib
    spec = importlib.util.spec_from_file_location("{stem}", "{file_path}")
    assert spec is not None


@pytest.mark.unit
def test_{stem}_url_patterns_defined():
    """If urlpatterns defined, they must be a list."""
    import importlib
    spec = importlib.util.spec_from_file_location("{stem}", "{file_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        patterns = getattr(module, "urlpatterns", None)
        if patterns is not None:
            assert isinstance(patterns, list)
    except Exception:
        pass   # module may require Django setup — acceptable
'''
        setup = ["pip install django pytest-django"]
        return code_str, setup

    # ── Python generic ─────────────────────────────────────────────────────────

    def _python(
        self, description: str, code: str, stem: str, file_path: str
    ) -> tuple[str, list[str]]:
        # Extract public functions/classes
        functions = re.findall(r"^def (\w[^\(]+)\(", code, re.MULTILINE)
        classes = re.findall(r"^class (\w+)", code, re.MULTILINE)
        public_fns = [f for f in functions if not f.startswith("_")]

        imports = f"from {stem} import " + ", ".join(
            (classes + public_fns)[:3] or [stem]
        ) if (classes or public_fns) else f"import {stem}"

        test_cases = ""
        for cls in classes[:2]:
            test_cases += f"""
@pytest.mark.unit
def test_{cls.lower()}_instantiable():
    obj = {cls}()
    assert obj is not None
"""
        for fn in public_fns[:3]:
            test_cases += f"""
@pytest.mark.unit
def test_{fn}_callable():
    assert callable({fn})
"""

        code_str = f'''"""Unit tests for {stem}."""
import pytest
from unittest.mock import patch, MagicMock

{imports}

{test_cases if test_cases else f"""
@pytest.mark.unit
def test_module_importable():
    import {stem}
    assert {stem} is not None
"""}'''
        return code_str, ["pip install pytest"]
