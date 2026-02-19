"""
AgenticQA Command Line Interface

Usage:
    agenticqa --help
    agenticqa execute <test_data_file>
    agenticqa patterns
    agenticqa stats
    agenticqa bootstrap
    agenticqa doctor
    agenticqa ingest-junit <junit_file>
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Type, Tuple


def _create_orchestrator():
    """Create orchestrator with backward-compatible imports."""
    try:
        from src.agents import AgentOrchestrator  # type: ignore
    except Exception:
        from agenticqa.agents import AgentOrchestrator  # type: ignore
    return AgentOrchestrator()


def _get_store_and_analyzer() -> Tuple[Type, Type]:
    """Resolve store/analyzer classes across old and new module layouts."""
    try:
        from src.data_store import PatternAnalyzer, TestArtifactStore  # type: ignore
    except Exception:
        from agenticqa.data_store import PatternAnalyzer, TestArtifactStore  # type: ignore
    return TestArtifactStore, PatternAnalyzer


def load_json_file(filepath: str) -> dict:
    """Load JSON file."""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {filepath}: {e}", file=sys.stderr)
        sys.exit(1)


def execute_command(args: argparse.Namespace) -> None:
    """Execute agents against test data."""
    test_data = load_json_file(args.test_data_file)

    print("🚀 Executing AgenticQA agents...\n")

    orchestrator = _create_orchestrator()
    results = orchestrator.execute_all_agents(test_data)

    print(json.dumps(results, indent=2, default=str))


def patterns_command(args: argparse.Namespace) -> None:
    """Display detected patterns."""
    TestArtifactStore, PatternAnalyzer = _get_store_and_analyzer()
    store = TestArtifactStore()
    analyzer = PatternAnalyzer(store)
    if hasattr(analyzer, "detect_patterns"):
        patterns = analyzer.detect_patterns()
    else:
        patterns = {
            "errors": analyzer.analyze_failure_patterns(),
            "performance": analyzer.analyze_performance_patterns(),
            "flakiness": analyzer.analyze_flakiness(),
        }

    print("📊 Detected Patterns\n")
    print(json.dumps(patterns, indent=2, default=str))


def stats_command(args: argparse.Namespace) -> None:
    """Display data store statistics."""
    TestArtifactStore, _ = _get_store_and_analyzer()
    store = TestArtifactStore()

    stats = {
        "total_artifacts": len(store.master_index),
        "storage_path": str(store.storage_dir),
        "oldest_artifact": min(
            (a.get("timestamp") for a in store.master_index.values() if a.get("timestamp")),
            default=None,
        ),
        "newest_artifact": max(
            (a.get("timestamp") for a in store.master_index.values() if a.get("timestamp")),
            default=None,
        ),
    }

    print("📈 Data Store Statistics\n")
    print(json.dumps(stats, indent=2, default=str))


def bootstrap_command(args: argparse.Namespace) -> None:
    """Bootstrap AgenticQA plug-in starter files into a repository."""
    from agenticqa.plugin_onboarding import bootstrap_project

    result = bootstrap_project(repo_root=Path(args.repo), force=args.force)
    print(
        json.dumps(
            {
                "repo_root": str(result.repo_root),
                "detected_stack": result.detected_stack,
                "created_files": [str(path) for path in result.created_files],
            },
            indent=2,
            default=str,
        )
    )


def doctor_command(args: argparse.Namespace) -> None:
    """Run plug-in health checks for dashboard readiness."""
    from agenticqa.plugin_onboarding import run_doctor

    result = run_doctor(repo_root=Path(args.repo))
    print(json.dumps({"healthy": result.healthy, "checks": result.checks}, indent=2))
    if not result.healthy:
        sys.exit(2)


def ingest_junit_command(args: argparse.Namespace) -> None:
    """Convert JUnit XML into AgenticQA JSON input payload."""
    from agenticqa.plugin_onboarding import ingest_junit

    output_path = Path(args.out) if args.out else None
    payload = ingest_junit(Path(args.junit_file), output_path=output_path)
    print(json.dumps(payload, indent=2))


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AgenticQA - Intelligent Autonomous QA Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  agenticqa execute test_data.json
  agenticqa patterns
  agenticqa stats
    agenticqa bootstrap --repo .
    agenticqa doctor --repo .
    agenticqa ingest-junit junit.xml --out .agenticqa/latest_input.json
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Execute command
    execute_parser = subparsers.add_parser("execute", help="Execute agents against test data")
    execute_parser.add_argument("test_data_file", help="JSON file with test data")
    execute_parser.set_defaults(func=execute_command)

    # Patterns command
    patterns_parser = subparsers.add_parser("patterns", help="Display detected patterns")
    patterns_parser.set_defaults(func=patterns_command)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Display data store statistics")
    stats_parser.set_defaults(func=stats_command)

    # Bootstrap command
    bootstrap_parser = subparsers.add_parser(
        "bootstrap", help="Generate plug-in files for a target repository"
    )
    bootstrap_parser.add_argument("--repo", default=".", help="Target repository path")
    bootstrap_parser.add_argument(
        "--force", action="store_true", help="Overwrite previously generated files"
    )
    bootstrap_parser.set_defaults(func=bootstrap_command)

    # Doctor command
    doctor_parser = subparsers.add_parser(
        "doctor", help="Run infrastructure and integration readiness checks"
    )
    doctor_parser.add_argument("--repo", default=".", help="Repository path")
    doctor_parser.set_defaults(func=doctor_command)

    # Ingest JUnit command
    ingest_parser = subparsers.add_parser(
        "ingest-junit", help="Convert JUnit XML into AgenticQA input JSON"
    )
    ingest_parser.add_argument("junit_file", help="Path to JUnit XML file")
    ingest_parser.add_argument("--out", help="Optional output file path")
    ingest_parser.set_defaults(func=ingest_junit_command)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
