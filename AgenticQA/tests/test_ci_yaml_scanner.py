"""Unit tests for CIYAMLInjectionScanner."""
import pytest
from pathlib import Path
from agenticqa.security.ci_yaml_scanner import CIYAMLInjectionScanner, CIScanResult


@pytest.fixture
def scanner():
    return CIYAMLInjectionScanner()


def write_yaml(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content)
    return str(p)


@pytest.mark.unit
def test_clean_workflow_no_findings(scanner, tmp_path):
    path = write_yaml(tmp_path, "ci.yml", """
name: CI
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@8ade135a41bc03ea155e62e844d188df1ea18608
      - run: echo "hello"
""")
    result = scanner.scan_file(path)
    critical = [f for f in result.findings if f.severity == "critical"]
    assert critical == []


@pytest.mark.unit
def test_expression_injection_detected(scanner, tmp_path):
    path = write_yaml(tmp_path, "inject.yml", """
name: Injection Test
on: [pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo "${{ github.event.issue.title }}"
""")
    result = scanner.scan_file(path)
    types = [f.attack_type for f in result.findings]
    assert "EXPRESSION_INJECTION" in types
    critical = [f for f in result.findings if f.severity == "critical"]
    assert critical


@pytest.mark.unit
def test_head_ref_injection_detected(scanner, tmp_path):
    path = write_yaml(tmp_path, "headref.yml", """
on: pull_request
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: git checkout ${{ github.head_ref }}
""")
    result = scanner.scan_file(path)
    assert any(f.attack_type == "EXPRESSION_INJECTION" for f in result.findings)


@pytest.mark.unit
def test_unpinned_action_detected(scanner, tmp_path):
    path = write_yaml(tmp_path, "unpinned.yml", """
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
""")
    result = scanner.scan_file(path)
    assert any(f.attack_type == "UNPINNED_ACTION" for f in result.findings)


@pytest.mark.unit
def test_pinned_action_no_finding(scanner, tmp_path):
    path = write_yaml(tmp_path, "pinned.yml", """
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@8ade135a41bc03ea155e62e844d188df1ea18608
""")
    result = scanner.scan_file(path)
    assert not any(f.attack_type == "UNPINNED_ACTION" for f in result.findings)


@pytest.mark.unit
def test_self_hosted_runner_detected(scanner, tmp_path):
    path = write_yaml(tmp_path, "selfhosted.yml", """
on: push
jobs:
  build:
    runs-on: [self-hosted, linux]
    steps:
      - run: echo hi
""")
    result = scanner.scan_file(path)
    assert any(f.attack_type == "SELF_HOSTED_RUNNER" for f in result.findings)


@pytest.mark.unit
def test_pull_request_target_detected(scanner, tmp_path):
    path = write_yaml(tmp_path, "prtarget.yml", """
on:
  pull_request_target:
    types: [opened]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""")
    result = scanner.scan_file(path)
    assert any(f.attack_type == "PULL_REQUEST_WRITE" for f in result.findings)


@pytest.mark.unit
def test_is_safe_false_on_critical(scanner, tmp_path):
    path = write_yaml(tmp_path, "bad.yml", """
on: pull_request
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo "${{ github.event.pull_request.title }}"
""")
    result = scanner.scan_file(path)
    assert result.is_safe is False


@pytest.mark.unit
def test_scan_directory(scanner, tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "clean.yml").write_text("on: push\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@8ade135a41bc03ea155e62e844d188df1ea18608\n")
    (workflows / "bad.yml").write_text('on: pull_request\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo "${{ github.head_ref }}"\n')
    results = scanner.scan_directory(str(tmp_path))
    assert len(results) == 2
    bad = next(r for r in results if "bad" in r.path)
    assert not bad.is_safe


@pytest.mark.unit
def test_risk_score_zero_clean_file(scanner, tmp_path):
    path = write_yaml(tmp_path, "ok.yml", """
on: push
jobs:
  b:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@8ade135a41bc03ea155e62e844d188df1ea18608
      - run: pytest tests/ -m unit
""")
    result = scanner.scan_file(path)
    critical = [f for f in result.findings if f.severity == "critical"]
    assert not critical
