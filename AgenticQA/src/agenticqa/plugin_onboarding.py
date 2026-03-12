"""Plug-in onboarding utilities for integrating AgenticQA into external codebases."""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass

try:
    import defusedxml.ElementTree as ET  # XXE-safe XML parser
except ImportError:
    import xml.etree.ElementTree as ET  # type: ignore[no-redef]
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class BootstrapResult:
    repo_root: Path
    created_files: List[Path]
    detected_stack: Dict[str, Any]


@dataclass
class DoctorResult:
    healthy: bool
    checks: List[Dict[str, Any]]


def detect_stack(repo_root: Path) -> Dict[str, Any]:
    # ── Language markers ────────────────────────────────────────────────────────
    has_python = (repo_root / "pyproject.toml").exists() or (repo_root / "requirements.txt").exists()
    has_php    = (repo_root / "composer.json").exists() or bool(list(repo_root.glob("src/**/*.php"))[:1])
    has_go     = (repo_root / "go.mod").exists()
    has_ruby   = (repo_root / "Gemfile").exists() or (repo_root / "Rakefile").exists()
    has_java   = (repo_root / "pom.xml").exists() or bool(list(repo_root.glob("build.gradle*"))[:1])
    has_rust   = (repo_root / "Cargo.toml").exists()
    has_csharp = bool(list(repo_root.glob("**/*.csproj"))[:1]) or bool(list(repo_root.glob("**/*.sln"))[:1])

    # Node: package.json at root OR nested up to 3 levels deep (e.g. tests/e2e/package.json)
    has_node = (
        (repo_root / "package.json").exists()
        or bool(list(repo_root.glob("*/package.json"))[:1])
        or bool(list(repo_root.glob("*/*/package.json"))[:1])
    )

    # ── Test framework markers ───────────────────────────────────────────────────
    has_pytest    = has_python and (
        (repo_root / "pytest.ini").exists()
        or (repo_root / "conftest.py").exists()
        or bool(list(repo_root.glob("tests/**/*.py"))[:1])
    )
    has_phpunit   = (repo_root / "phpunit.xml").exists() or (repo_root / "phpunit.xml.dist").exists()
    has_jest      = bool(list(repo_root.glob("jest.config*"))[:1]) or bool(list(repo_root.glob("**/*.test.js"))[:1])
    has_cypress   = (
        (repo_root / "cypress.config.js").exists()
        or (repo_root / "cypress.config.ts").exists()
        or bool(list(repo_root.glob("**/*.cy.js"))[:1])
        or bool(list(repo_root.glob("**/*.cy.ts"))[:1])
    )
    has_playwright = bool(list(repo_root.glob("**/playwright.config*"))[:1])
    has_rspec     = bool(list(repo_root.glob("spec/**/*_spec.rb"))[:1])
    has_junit_java = bool(list(repo_root.glob("**/*Test.java"))[:1]) or bool(list(repo_root.glob("**/*Tests.java"))[:1])
    has_go_test   = bool(list(repo_root.glob("**/*_test.go"))[:1])
    has_cargo_test = has_rust and bool(list(repo_root.glob("tests/**/*.rs"))[:1])
    has_dotnet_test = has_csharp and bool(list(repo_root.glob("**/*Tests.cs"))[:1])

    markers = {
        # Languages
        "python":     has_python,
        "php":        has_php,
        "node":       has_node,
        "go":         has_go,
        "ruby":       has_ruby,
        "java":       has_java,
        "rust":       has_rust,
        "csharp":     has_csharp,
        # Test frameworks
        "pytest":     has_pytest,
        "phpunit":    has_phpunit,
        "jest":       has_jest,
        "cypress":    has_cypress,
        "playwright": has_playwright,
        "rspec":      has_rspec,
        "junit":      has_junit_java,
        "go_test":    has_go_test,
        "cargo_test": has_cargo_test,
        "dotnet_test": has_dotnet_test,
        # Infrastructure
        "github_actions": (repo_root / ".github" / "workflows").exists(),
        "docker_compose": any(repo_root.glob("docker-compose*.yml")) or any(repo_root.glob("compose*.yaml")),
    }

    # Primary language priority: Python > PHP > Go > Java > Ruby > Rust > C# > JS > unknown
    if has_python:       primary = "python"
    elif has_php:        primary = "php"
    elif has_go:         primary = "go"
    elif has_java:       primary = "java"
    elif has_ruby:       primary = "ruby"
    elif has_rust:       primary = "rust"
    elif has_csharp:     primary = "csharp"
    elif has_node:       primary = "javascript"
    else:                primary = "unknown"

    # Primary test framework (most specific first)
    if has_phpunit:       test_framework = "phpunit"
    elif has_pytest:      test_framework = "pytest"
    elif has_rspec:       test_framework = "rspec"
    elif has_junit_java:  test_framework = "junit"
    elif has_go_test:     test_framework = "go_test"
    elif has_cargo_test:  test_framework = "cargo_test"
    elif has_dotnet_test: test_framework = "dotnet_test"
    elif has_cypress:     test_framework = "cypress"
    elif has_playwright:  test_framework = "playwright"
    elif has_jest:        test_framework = "jest"
    else:                 test_framework = "unknown"

    return {
        "primary_language": primary,
        "test_framework": test_framework,
        **markers,
    }


def bootstrap_project(repo_root: Path, force: bool = False) -> BootstrapResult:
    repo_root = repo_root.resolve()
    stack = detect_stack(repo_root)
    created_files: List[Path] = []

    config_dir = repo_root / ".agenticqa"
    samples_dir = config_dir / "samples"
    config_dir.mkdir(exist_ok=True)
    samples_dir.mkdir(exist_ok=True)

    config_path = config_dir / "config.json"
    if force or not config_path.exists():
        config = {
            "schema_version": "1.0.0",
            "created_at": datetime.now(UTC).isoformat(),
            "repo_root": str(repo_root),
            "project": {
                "primary_language": stack["primary_language"],
                "auto_detected": stack,
            },
            "pipeline": {
                "junit_glob": ["**/junit*.xml", "**/test-results*.xml"],
                "coverage_glob": ["**/coverage.xml"],
            },
            "dashboard": {
                "requires": ["neo4j", "streamlit"],
                "neo4j": {
                    "host": "localhost",
                    "port": 7687,
                },
            },
        }
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        created_files.append(config_path)

    sample_input_path = samples_dir / "agenticqa_input.json"
    if force or not sample_input_path.exists():
        sample_input = {
            "test_results": {
                "total": 100,
                "passed": 97,
                "failed": 3,
                "pass_rate": 97.0,
            },
            "quality_signal": {
                "language": stack["primary_language"],
                "source": "bootstrap_sample",
            },
        }
        sample_input_path.write_text(json.dumps(sample_input, indent=2), encoding="utf-8")
        created_files.append(sample_input_path)

    workflow_path = repo_root / ".github" / "workflows" / "agenticqa.yml"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    if force or not workflow_path.exists():
        workflow_path.write_text(_github_workflow_template(stack), encoding="utf-8")
        created_files.append(workflow_path)

    return BootstrapResult(repo_root=repo_root, created_files=created_files, detected_stack=stack)


def _check_tcp(host: str, port: int, timeout: float = 1.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            return False


def run_doctor(repo_root: Path) -> DoctorResult:
    repo_root = repo_root.resolve()
    checks: List[Dict[str, Any]] = []

    config_path = repo_root / ".agenticqa" / "config.json"
    config_ok = config_path.exists()
    checks.append({
        "name": "agenticqa_config",
        "ok": config_ok,
        "detail": str(config_path),
        "required": True,
        "fix_command": None if config_ok else "agenticqa bootstrap --repo .",
        "fix_description": None if config_ok else "Run bootstrap to create .agenticqa/config.json",
    })

    compose_exists = any(repo_root.glob("docker-compose*.yml"))
    checks.append({
        "name": "docker_compose_file",
        "ok": compose_exists,
        "detail": "docker-compose*.yml",
        "required": False,
        "fix_command": None if compose_exists else "docker compose -f docker-compose.weaviate.yml up -d",
        "fix_description": None if compose_exists else "Start required infrastructure (Weaviate)",
    })

    neo4j_reachable = _check_tcp("127.0.0.1", 7687)
    checks.append({
        "name": "neo4j_bolt",
        "ok": neo4j_reachable,
        "detail": "127.0.0.1:7687",
        "required": False,
        "fix_command": None if neo4j_reachable else "docker run -d -p 7687:7687 -p 7474:7474 -e NEO4J_AUTH=none neo4j:5",
        "fix_description": None if neo4j_reachable else "Start Neo4j — required for graph-powered routing recommendations",
    })

    api_reachable = _check_tcp("127.0.0.1", 8000)
    checks.append({
        "name": "agenticqa_api",
        "ok": api_reachable,
        "detail": "127.0.0.1:8000",
        "required": False,
        "fix_command": None if api_reachable else "uvicorn agent_api:app --host 0.0.0.0 --port 8000",
        "fix_description": None if api_reachable else "Start the AgenticQA API server (optional — needed for constitution endpoint)",
    })

    healthy = all(item["ok"] for item in checks if item.get("required", True))
    return DoctorResult(healthy=healthy, checks=checks)


def ingest_junit(junit_path: Path, output_path: Optional[Path] = None) -> Dict[str, Any]:
    junit_path = junit_path.resolve()
    root = ET.fromstring(junit_path.read_text(encoding="utf-8"))

    # Support both <testsuites> and single <testsuite>
    testsuite_nodes: List[ET.Element]
    if root.tag == "testsuite":
        testsuite_nodes = [root]
    else:
        testsuite_nodes = list(root.findall("testsuite"))

    total = sum(int(node.attrib.get("tests", 0)) for node in testsuite_nodes)
    failures = sum(int(node.attrib.get("failures", 0)) for node in testsuite_nodes)
    errors = sum(int(node.attrib.get("errors", 0)) for node in testsuite_nodes)
    skipped = sum(int(node.attrib.get("skipped", 0)) for node in testsuite_nodes)

    failed = failures + errors
    passed = max(0, total - failed - skipped)
    pass_rate = round((passed / total) * 100.0, 2) if total else 0.0

    payload = {
        "ingested_at": datetime.now(UTC).isoformat(),
        "source": str(junit_path),
        "test_results": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "pass_rate": pass_rate,
        },
    }

    if output_path:
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return payload


def _github_workflow_template(stack: Optional[Dict[str, Any]] = None) -> str:
    stack = stack or {}
    primary = stack.get("primary_language", "unknown")
    framework = stack.get("test_framework", "unknown")

    if primary == "php" or stack.get("php"):
        setup_steps = """\
      - name: Setup PHP
        uses: shivammathur/setup-php@v2
        with:
          php-version: '8.2'
          extensions: pdo, pdo_sqlite, mbstring
          coverage: xdebug

      - name: Install Composer dependencies
        run: composer install --no-interaction --prefer-dist"""
        test_steps = """\
      - name: Run PHPUnit tests
        run: composer test -- --log-junit agenticqa-junit.xml || true"""

    elif primary == "go" or stack.get("go"):
        setup_steps = """\
      - name: Setup Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.22'"""
        test_steps = """\
      - name: Run Go tests
        run: go test ./... -v 2>&1 | go-junit-report > agenticqa-junit.xml || true"""

    elif primary == "java" or stack.get("java"):
        build_tool = "mvn" if (Path(".") / "pom.xml").exists() else "gradle"
        if build_tool == "mvn":
            setup_steps = """\
      - name: Setup Java
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '21'
          cache: 'maven'"""
            test_steps = """\
      - name: Run Maven tests
        run: mvn test --no-transfer-progress || true"""
        else:
            setup_steps = """\
      - name: Setup Java
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '21'
          cache: 'gradle'"""
            test_steps = """\
      - name: Run Gradle tests
        run: ./gradlew test || true"""

    elif primary == "ruby" or stack.get("ruby"):
        setup_steps = """\
      - name: Setup Ruby
        uses: ruby/setup-ruby@v1
        with:
          ruby-version: '3.3'
          bundler-cache: true"""
        test_steps = """\
      - name: Run RSpec tests
        run: bundle exec rspec --format RspecJunitFormatter --out agenticqa-junit.xml || true"""

    elif primary == "rust" or stack.get("rust"):
        setup_steps = """\
      - name: Setup Rust
        uses: dtolnay/rust-toolchain@stable
        with:
          components: clippy"""
        test_steps = """\
      - name: Run Cargo tests
        run: cargo test -- --format junit > agenticqa-junit.xml 2>&1 || cargo test || true"""

    elif primary == "csharp" or stack.get("csharp"):
        setup_steps = """\
      - name: Setup .NET
        uses: actions/setup-dotnet@v4
        with:
          dotnet-version: '8.0'"""
        test_steps = """\
      - name: Run .NET tests
        run: dotnet test --logger "junit;LogFilePath=agenticqa-junit.xml" || true"""

    elif primary == "javascript" or stack.get("node"):
        setup_steps = """\
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci || yarn install --frozen-lockfile"""
        if framework == "cypress":
            test_steps = """\
      - name: Run Cypress tests
        run: npx cypress run --reporter junit --reporter-options mochaFile=agenticqa-junit.xml || true"""
        else:
            test_steps = """\
      - name: Run tests
        run: npx jest --reporters=jest-junit || npm test || true
        env:
          JEST_JUNIT_OUTPUT_FILE: agenticqa-junit.xml"""

    else:  # Python default
        setup_steps = """\
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install AgenticQA
        run: pip install -e ."""
        test_steps = """\
      - name: Run tests and export JUnit
        run: pytest --junitxml=agenticqa-junit.xml || true"""

    return f"""\
name: AgenticQA Plug-In

on:
  workflow_dispatch:
  push:
    branches: [ main ]

jobs:
  agenticqa-ingest:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

{setup_steps}

{test_steps}

      - name: Convert JUnit to AgenticQA input
        run: |
          agenticqa ingest-junit agenticqa-junit.xml --out .agenticqa/latest_input.json

      - name: AgenticQA health check
        run: |
          agenticqa doctor
"""
