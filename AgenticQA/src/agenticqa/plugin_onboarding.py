"""Plug-in onboarding utilities for integrating AgenticQA into external codebases."""

from __future__ import annotations

import json
import socket
import xml.etree.ElementTree as ET
from dataclasses import dataclass
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
    markers = {
        "python": (repo_root / "pyproject.toml").exists() or (repo_root / "requirements.txt").exists(),
        "node": (repo_root / "package.json").exists(),
        "github_actions": (repo_root / ".github" / "workflows").exists(),
        "docker_compose": any(repo_root.glob("docker-compose*.yml")),
    }

    if markers["python"]:
        primary = "python"
    elif markers["node"]:
        primary = "node"
    else:
        primary = "unknown"

    return {
        "primary_language": primary,
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
        workflow_path.write_text(_github_workflow_template(), encoding="utf-8")
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

    dashboard_exists = (repo_root / "dashboard" / "app.py").exists()
    checks.append({
        "name": "dashboard_app",
        "ok": dashboard_exists,
        "detail": "dashboard/app.py",
        "required": True,
        "fix_command": None if dashboard_exists else "pip install -e .[dashboard]",
        "fix_description": None if dashboard_exists else "Install dashboard dependencies, then run: streamlit run dashboard/app.py",
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


def _github_workflow_template() -> str:
    return """name: AgenticQA Plug-In\n\non:\n  workflow_dispatch:\n  push:\n    branches: [ main ]\n\njobs:\n  agenticqa-ingest:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v4\n\n      - name: Setup Python\n        uses: actions/setup-python@v5\n        with:\n          python-version: '3.11'\n\n      - name: Install AgenticQA\n        run: |\n          pip install -e .\n\n      - name: Run tests and export JUnit\n        run: |\n          pytest --junitxml=agenticqa-junit.xml || true\n\n      - name: Convert JUnit to AgenticQA input\n        run: |\n          agenticqa ingest-junit agenticqa-junit.xml --out .agenticqa/latest_input.json\n\n      - name: AgenticQA health check\n        run: |\n          agenticqa doctor\n"""
