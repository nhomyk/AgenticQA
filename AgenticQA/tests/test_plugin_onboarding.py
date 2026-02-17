"""Tests for plug-in onboarding workflow."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agenticqa.plugin_onboarding import bootstrap_project, detect_stack, ingest_junit, run_doctor


def test_detect_stack_python_and_node(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    stack = detect_stack(tmp_path)

    assert stack["python"] is True
    assert stack["node"] is True
    assert stack["primary_language"] == "python"


def test_bootstrap_project_generates_files(tmp_path):
    result = bootstrap_project(tmp_path)

    created = {path.relative_to(tmp_path).as_posix() for path in result.created_files}
    assert ".agenticqa/config.json" in created
    assert ".agenticqa/samples/agenticqa_input.json" in created
    assert ".github/workflows/agenticqa.yml" in created

    config = json.loads((tmp_path / ".agenticqa" / "config.json").read_text(encoding="utf-8"))
    assert config["schema_version"] == "1.0.0"


def test_ingest_junit_xml(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(
        """
        <testsuites>
          <testsuite name="suite-a" tests="5" failures="1" errors="1" skipped="1"/>
        </testsuites>
        """.strip(),
        encoding="utf-8",
    )

    out_file = tmp_path / ".agenticqa" / "latest_input.json"
    payload = ingest_junit(junit, out_file)

    assert payload["test_results"]["total"] == 5
    assert payload["test_results"]["failed"] == 2
    assert payload["test_results"]["passed"] == 2
    assert out_file.exists()


def test_doctor_reports_missing_components(tmp_path):
    result = run_doctor(tmp_path)
    assert result.healthy is False
    check_names = {check["name"] for check in result.checks}
    assert "agenticqa_config" in check_names
    assert "neo4j_bolt" in check_names
