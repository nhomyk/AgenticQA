#!/usr/bin/env python3
"""
Neo4j Analytics Examples for AgenticQA

Demonstrates powerful graph queries for agent delegation analysis.

Usage:
    python examples/neo4j_analytics.py

Prerequisites:
    1. Start Neo4j: docker-compose -f docker-compose.weaviate.yml up neo4j
    2. Install dependencies: pip install neo4j
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agenticqa.graph import DelegationGraphStore
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint


console = Console()


def print_section(title: str):
    """Print a section header"""
    console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
    console.print(f"[bold yellow]{title}[/bold yellow]")
    console.print(f"[bold cyan]{'='*60}[/bold cyan]\n")


def example_1_most_delegated_agents(store: DelegationGraphStore):
    """Example 1: Find most delegated-to agents"""
    print_section("Example 1: Most Delegated-To Agents")

    results = store.get_most_delegated_agents(limit=5)

    if not results:
        console.print("[yellow]No delegation data found. Run some agents first![/yellow]")
        return

    table = Table(title="Top 5 Most Delegated-To Agents")
    table.add_column("Agent", style="cyan")
    table.add_column("Delegations", justify="right", style="green")
    table.add_column("Avg Duration (ms)", justify="right", style="yellow")
    table.add_column("Success Rate", justify="right", style="magenta")

    for row in results:
        agent = row["agent"]
        count = row["delegation_count"]
        avg_duration = row.get("avg_duration_ms") or 0
        successes = row.get("successes", 0)
        success_rate = (successes / count * 100) if count > 0 else 0

        table.add_row(
            agent,
            str(count),
            f"{avg_duration:.0f}",
            f"{success_rate:.1f}%"
        )

    console.print(table)


def example_2_delegation_chains(store: DelegationGraphStore):
    """Example 2: Analyze delegation chains"""
    print_section("Example 2: Delegation Chains (Multi-Hop Delegations)")

    results = store.find_delegation_chains(min_length=2, limit=10)

    if not results:
        console.print("[yellow]No delegation chains found.[/yellow]")
        return

    table = Table(title="Delegation Chains")
    table.add_column("Origin", style="cyan")
    table.add_column("Destination", style="green")
    table.add_column("Chain Length", justify="right", style="yellow")
    table.add_column("Total Duration (ms)", justify="right", style="magenta")

    for row in results:
        table.add_row(
            row["origin"],
            row["destination"],
            str(row["chain_length"]),
            f"{row.get('total_duration_ms', 0):.0f}"
        )

    console.print(table)


def example_3_circular_delegations(store: DelegationGraphStore):
    """Example 3: Detect circular delegations (should be none!)"""
    print_section("Example 3: Circular Delegation Detection")

    results = store.find_circular_delegations()

    if not results:
        console.print("[bold green]✓ No circular delegations detected! Guardrails working.[/bold green]")
    else:
        console.print(f"[bold red]✗ Found {len(results)} circular delegations![/bold red]")
        for row in results:
            console.print(f"  Cycle: {' -> '.join(row['cycle'])}")


def example_4_success_rates(store: DelegationGraphStore):
    """Example 4: Delegation success rates by agent pair"""
    print_section("Example 4: Delegation Success Rates by Agent Pair")

    results = store.get_delegation_success_rate_by_pair(limit=10)

    if not results:
        console.print("[yellow]No delegation pairs found.[/yellow]")
        return

    table = Table(title="Agent Pair Success Rates")
    table.add_column("From Agent", style="cyan")
    table.add_column("To Agent", style="green")
    table.add_column("Total", justify="right", style="yellow")
    table.add_column("Success Rate", justify="right", style="magenta")
    table.add_column("Avg Duration (ms)", justify="right", style="blue")

    for row in results:
        success_rate = row.get("success_rate", 0) * 100
        avg_duration = row.get("avg_duration_ms", 0)

        # Color code success rate
        if success_rate >= 90:
            rate_color = "green"
        elif success_rate >= 70:
            rate_color = "yellow"
        else:
            rate_color = "red"

        table.add_row(
            row["from_agent"],
            row["to_agent"],
            str(row["total"]),
            f"[{rate_color}]{success_rate:.1f}%[/{rate_color}]",
            f"{avg_duration:.0f}"
        )

    console.print(table)


def example_5_bottleneck_agents(store: DelegationGraphStore):
    """Example 5: Find bottleneck agents"""
    print_section("Example 5: Bottleneck Agents (Slow Delegations)")

    results = store.find_bottleneck_agents(slow_threshold_ms=1000.0, min_count=2)

    if not results:
        console.print("[bold green]✓ No bottlenecks detected![/bold green]")
        return

    table = Table(title="Bottleneck Agents")
    table.add_column("Agent", style="cyan")
    table.add_column("Slow Delegations", justify="right", style="yellow")
    table.add_column("Avg Duration (ms)", justify="right", style="red")
    table.add_column("P95 Duration (ms)", justify="right", style="magenta")
    table.add_column("Max Duration (ms)", justify="right", style="blue")

    for row in results:
        table.add_row(
            row["agent"],
            str(row["slow_delegations"]),
            f"{row['avg_duration']:.0f}",
            f"{row.get('p95_duration', 0):.0f}",
            f"{row.get('max_duration', 0):.0f}"
        )

    console.print(table)


def example_6_graphrag_recommendation(store: DelegationGraphStore):
    """Example 6: GraphRAG - Recommend delegation target"""
    print_section("Example 6: GraphRAG Delegation Recommendation")

    # Try to recommend where SDET should delegate for test generation
    recommendation = store.recommend_delegation_target(
        from_agent="SDET_Agent",
        task_type="generate_tests",
        acceptable_duration_ms=5000.0,
        min_success_count=2
    )

    if recommendation:
        console.print(Panel.fit(
            f"[bold green]Recommended Agent:[/bold green] {recommendation['recommended_agent']}\n"
            f"[bold yellow]Success Count:[/bold yellow] {recommendation['success_count']}\n"
            f"[bold cyan]Avg Duration:[/bold cyan] {recommendation['avg_duration']:.0f}ms\n"
            f"[bold magenta]Priority Score:[/bold magenta] {recommendation['priority_score']:.2f}",
            title="GraphRAG Recommendation",
            border_style="green"
        ))
    else:
        console.print("[yellow]No recommendation available (need more historical data)[/yellow]")


def example_7_database_stats(store: DelegationGraphStore):
    """Example 7: Overall database statistics"""
    print_section("Example 7: Database Statistics")

    stats = store.get_database_stats()

    console.print(Panel.fit(
        f"[bold cyan]Total Agents:[/bold cyan] {stats.get('total_agents', 0)}\n"
        f"[bold green]Total Executions:[/bold green] {stats.get('total_executions', 0)}\n"
        f"[bold yellow]Total Delegations:[/bold yellow] {stats.get('total_delegations', 0)}",
        title="Neo4j Database Stats",
        border_style="cyan"
    ))


def main():
    """Run all analytics examples"""
    console.print(Panel.fit(
        "[bold cyan]AgenticQA Neo4j Analytics Examples[/bold cyan]\n\n"
        "This script demonstrates powerful graph queries for analyzing\n"
        "agent collaboration patterns and delegation chains.",
        border_style="green"
    ))

    # Connect to Neo4j
    console.print("\n[yellow]Connecting to Neo4j...[/yellow]")
    store = DelegationGraphStore()

    try:
        store.connect()
        console.print("[bold green]✓ Connected to Neo4j[/bold green]")

        # Run examples
        example_1_most_delegated_agents(store)
        example_2_delegation_chains(store)
        example_3_circular_delegations(store)
        example_4_success_rates(store)
        example_5_bottleneck_agents(store)
        example_6_graphrag_recommendation(store)
        example_7_database_stats(store)

        # Summary
        console.print("\n[bold green]All examples completed successfully![/bold green]")
        console.print("\n[cyan]Next steps:[/cyan]")
        console.print("  1. Open Neo4j Browser: http://localhost:7474")
        console.print("  2. Run custom Cypher queries (see docs/NEO4J_SCHEMA.md)")
        console.print("  3. Visualize agent collaboration networks")

    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")
        console.print("\n[yellow]Make sure Neo4j is running:[/yellow]")
        console.print("  docker-compose -f docker-compose.weaviate.yml up neo4j")
        return 1

    finally:
        store.close()

    return 0


if __name__ == "__main__":
    try:
        # Check if rich is installed
        import rich
    except ImportError:
        print("Installing rich for better output...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "rich"])
        # Re-import after installation
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        console = Console()

    sys.exit(main())
