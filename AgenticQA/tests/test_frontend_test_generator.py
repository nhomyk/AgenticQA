"""Unit tests for FrontendTestGenerator and FrameworkDetector."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from agenticqa.testing.frontend_test_generator import (
    Framework,
    FrameworkDetection,
    FrameworkDetector,
    FrontendTestGenerator,
    GeneratedFrontendTest,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def detect(repo_path=".", file_path="") -> FrameworkDetection:
    return FrameworkDetector().detect(repo_path, file_path)


def write_pkg(tmp_path: Path, deps: dict) -> Path:
    pkg = {"dependencies": deps, "devDependencies": {}}
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    return tmp_path


def generate(
    desc="Add a button",
    code="export function MyBtn() { return <button>click</button>; }",
    file_path="src/MyBtn.tsx",
    repo_path=".",
    detection=None,
) -> GeneratedFrontendTest:
    return FrontendTestGenerator().generate(desc, code, file_path, repo_path, detection)


# ── FrameworkDetector ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_detect_react_from_package_json(tmp_path):
    write_pkg(tmp_path, {"react": "^18.0.0", "react-dom": "^18.0.0"})
    d = FrameworkDetector().detect(str(tmp_path), "src/App.tsx")
    assert d.framework == Framework.REACT


@pytest.mark.unit
def test_detect_nextjs_from_package_json(tmp_path):
    write_pkg(tmp_path, {"next": "^14.0.0", "react": "^18.0.0"})
    d = FrameworkDetector().detect(str(tmp_path), "pages/index.tsx")
    assert d.framework == Framework.NEXTJS


@pytest.mark.unit
def test_detect_vue_from_package_json(tmp_path):
    write_pkg(tmp_path, {"vue": "^3.0.0"})
    d = FrameworkDetector().detect(str(tmp_path), "src/App.vue")
    assert d.framework == Framework.VUE


@pytest.mark.unit
def test_detect_angular_from_package_json(tmp_path):
    write_pkg(tmp_path, {"@angular/core": "^17.0.0"})
    d = FrameworkDetector().detect(str(tmp_path), "src/app.component.ts")
    assert d.framework == Framework.ANGULAR


@pytest.mark.unit
def test_detect_svelte_from_package_json(tmp_path):
    write_pkg(tmp_path, {"svelte": "^4.0.0"})
    d = FrameworkDetector().detect(str(tmp_path), "src/App.svelte")
    assert d.framework == Framework.SVELTE


@pytest.mark.unit
def test_detect_python_from_py_extension(tmp_path):
    d = FrameworkDetector().detect(str(tmp_path), "src/utils.py")
    assert d.framework == Framework.PYTHON
    assert d.test_runner == "pytest"


@pytest.mark.unit
def test_detect_fastapi_from_file_content(tmp_path):
    f = tmp_path / "api.py"
    f.write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    d = FrameworkDetector().detect(str(tmp_path), "api.py")
    assert d.framework == Framework.FASTAPI


@pytest.mark.unit
def test_detect_flask_from_file_content(tmp_path):
    f = tmp_path / "app.py"
    f.write_text("from flask import Flask\napp = Flask(__name__)\n")
    d = FrameworkDetector().detect(str(tmp_path), "app.py")
    assert d.framework == Framework.FLASK


@pytest.mark.unit
def test_detect_streamlit_from_file_content(tmp_path):
    f = tmp_path / "dashboard.py"
    f.write_text("import streamlit as st\nst.title('Hello')\n")
    d = FrameworkDetector().detect(str(tmp_path), "dashboard.py")
    assert d.framework == Framework.STREAMLIT


@pytest.mark.unit
def test_detect_nextjs_takes_priority_over_react(tmp_path):
    write_pkg(tmp_path, {"next": "^14", "react": "^18"})
    d = FrameworkDetector().detect(str(tmp_path), "pages/index.tsx")
    assert d.framework == Framework.NEXTJS


@pytest.mark.unit
def test_detect_uses_vitest_when_in_deps(tmp_path):
    pkg = {"dependencies": {"react": "^18"}, "devDependencies": {"vitest": "^1.0"}}
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    d = FrameworkDetector().detect(str(tmp_path), "src/App.tsx")
    assert d.test_runner == "vitest"


@pytest.mark.unit
def test_detect_fallback_python_when_no_package_json(tmp_path):
    d = FrameworkDetector().detect(str(tmp_path), "")
    assert d.framework == Framework.PYTHON


@pytest.mark.unit
def test_detection_has_required_fields(tmp_path):
    write_pkg(tmp_path, {"react": "^18"})
    d = FrameworkDetector().detect(str(tmp_path), "src/App.tsx")
    assert d.framework
    assert d.test_runner
    assert d.test_command
    assert d.file_extension
    assert 0.0 <= d.confidence <= 1.0


# ── FrontendTestGenerator — output structure ───────────────────────────────────

@pytest.mark.unit
def test_generate_returns_generated_test():
    det = FrameworkDetection(Framework.PYTHON, "pytest",
                             "python -m pytest", "_test.py", 0.9)
    result = generate(detection=det)
    assert isinstance(result, GeneratedFrontendTest)


@pytest.mark.unit
def test_generate_test_filename_matches_extension():
    det = FrameworkDetection(Framework.REACT, "jest",
                             "npx jest", ".test.tsx", 0.9)
    result = generate(file_path="src/Button.tsx", detection=det)
    assert result.test_filename.endswith(".test.tsx")


@pytest.mark.unit
def test_generate_test_code_is_non_empty():
    det = FrameworkDetection(Framework.PYTHON, "pytest",
                             "python -m pytest", "_test.py", 0.9)
    result = generate(detection=det)
    assert len(result.test_code) > 50


@pytest.mark.unit
def test_generate_test_command_set():
    det = FrameworkDetection(Framework.REACT, "jest",
                             "npx jest --passWithNoTests", ".test.tsx", 0.9)
    result = generate(detection=det)
    assert result.test_command == "npx jest --passWithNoTests"


# ── React generator ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_react_test_imports_testing_library():
    det = FrameworkDetection(Framework.REACT, "jest",
                             "npx jest", ".test.tsx", 0.9)
    result = generate(
        code="import React from 'react'; export function Btn() { return <button/>; }",
        file_path="src/Btn.tsx",
        detection=det,
    )
    assert "@testing-library/react" in result.test_code


@pytest.mark.unit
def test_react_test_renders_without_crash():
    det = FrameworkDetection(Framework.REACT, "jest", "npx jest", ".test.tsx", 0.9)
    result = generate(file_path="src/Card.tsx", detection=det)
    assert "renders without crashing" in result.test_code


@pytest.mark.unit
def test_react_test_mocks_fetch_when_used():
    det = FrameworkDetection(Framework.REACT, "jest", "npx jest", ".test.tsx", 0.9)
    result = generate(
        code="export function Fetcher() { fetch('/api/data'); return null; }",
        file_path="src/Fetcher.tsx",
        detection=det,
    )
    assert "fetch" in result.test_code.lower()


# ── Vue generator ──────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_vue_test_imports_test_utils():
    det = FrameworkDetection(Framework.VUE, "vitest", "npx vitest run", ".spec.ts", 0.9)
    result = generate(file_path="src/MyComp.vue", detection=det)
    assert "@vue/test-utils" in result.test_code


@pytest.mark.unit
def test_vue_test_has_mount():
    det = FrameworkDetection(Framework.VUE, "vitest", "npx vitest run", ".spec.ts", 0.9)
    result = generate(file_path="src/MyComp.vue", detection=det)
    assert "mount" in result.test_code.lower()


# ── Angular generator ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_angular_test_imports_testbed():
    det = FrameworkDetection(Framework.ANGULAR, "ng test", "npx ng test", ".spec.ts", 0.9)
    result = generate(file_path="src/my.component.ts", detection=det)
    assert "TestBed" in result.test_code


# ── Streamlit generator ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_streamlit_test_uses_apptest():
    det = FrameworkDetection(Framework.STREAMLIT, "pytest",
                             "python -m pytest", "_test.py", 0.9)
    result = generate(
        code="import streamlit as st\nst.title('Hello')\n",
        file_path="dashboard.py",
        detection=det,
    )
    assert "AppTest" in result.test_code


@pytest.mark.unit
def test_streamlit_test_checks_no_exception():
    det = FrameworkDetection(Framework.STREAMLIT, "pytest",
                             "python -m pytest", "_test.py", 0.9)
    result = generate(code="import streamlit as st\n", file_path="app.py", detection=det)
    assert "exception" in result.test_code.lower()


# ── FastAPI generator ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_fastapi_test_uses_testclient():
    det = FrameworkDetection(Framework.FASTAPI, "pytest",
                             "python -m pytest", "_test.py", 0.9)
    result = generate(
        code="from fastapi import FastAPI\napp = FastAPI()\n",
        file_path="api.py",
        detection=det,
    )
    assert "TestClient" in result.test_code


# ── Python generic generator ───────────────────────────────────────────────────

@pytest.mark.unit
def test_python_test_extracts_public_functions():
    det = FrameworkDetection(Framework.PYTHON, "pytest",
                             "python -m pytest", "_test.py", 0.9)
    result = generate(
        code="def compute_score(x):\n    return x * 2\n\ndef _private():\n    pass\n",
        file_path="scorer.py",
        detection=det,
    )
    assert "compute_score" in result.test_code
    # Private function should not be tested
    assert "_private" not in result.test_code


@pytest.mark.unit
def test_python_test_extracts_classes():
    det = FrameworkDetection(Framework.PYTHON, "pytest",
                             "python -m pytest", "_test.py", 0.9)
    result = generate(
        code="class MyScorer:\n    def score(self):\n        return 1.0\n",
        file_path="scorer.py",
        detection=det,
    )
    assert "MyScorer" in result.test_code


# ── Setup instructions ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_react_setup_instructions_not_empty():
    det = FrameworkDetection(Framework.REACT, "jest", "npx jest", ".test.tsx", 0.9)
    result = generate(detection=det)
    assert len(result.setup_instructions) >= 1


@pytest.mark.unit
def test_python_setup_instructions_has_pytest():
    det = FrameworkDetection(Framework.PYTHON, "pytest",
                             "python -m pytest", "_test.py", 0.9)
    result = generate(detection=det)
    assert any("pytest" in s.lower() for s in result.setup_instructions)
