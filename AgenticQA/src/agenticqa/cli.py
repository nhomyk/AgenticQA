"""
AgenticQA Command Line Interface

Usage:
    agenticqa --help
    agenticqa execute <test_data_file>
    agenticqa patterns
    agenticqa stats
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Any

from agenticqa.agents import AgentOrchestrator
from agenticqa.data_store import TestArtifactStore, PatternAnalyzer


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
    
    orchestrator = AgentOrchestrator()
    results = orchestrator.execute_all_agents(test_data)
    
    print(json.dumps(results, indent=2, default=str))


def patterns_command(args: argparse.Namespace) -> None:
    """Display detected patterns."""
    store = TestArtifactStore()
    analyzer = PatternAnalyzer(store)
    patterns = analyzer.detect_patterns()
    
    print("📊 Detected Patterns\n")
    print(json.dumps(patterns, indent=2, default=str))


def stats_command(args: argparse.Namespace) -> None:
    """Display data store statistics."""
    store = TestArtifactStore()
    
    stats = {
        "total_artifacts": len(store.master_index),
        "storage_path": str(store.storage_dir),
        "oldest_artifact": min(
            (a.get("timestamp") for a in store.master_index.values() if a.get("timestamp")),
            default=None
        ),
        "newest_artifact": max(
            (a.get("timestamp") for a in store.master_index.values() if a.get("timestamp")),
            default=None
        ),
    }
    
    print("📈 Data Store Statistics\n")
    print(json.dumps(stats, indent=2, default=str))


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
        """
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
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()
