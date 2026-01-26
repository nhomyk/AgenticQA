"""
Example: Safe Code Change with Before/After Snapshots

Demonstrates how to safely apply code changes with automatic validation
and rollback protection.
"""

from agenticqa.data_store.change_executor import SafeCodeChangeExecutor, ChangeHistoryAnalyzer
from agenticqa.data_store.code_change_tracker import CodeChangeTracker


class MockAgent:
    """Mock agent for demonstration."""
    
    def __init__(self):
        self.optimized = False
        self.original_algorithm = "slow_algorithm"
    
    def optimize_algorithm(self):
        """Apply optimization."""
        print("  → Optimizing algorithm...")
        self.optimized = True
    
    def restore_original(self):
        """Restore original algorithm."""
        print("  → Restoring original algorithm...")
        self.optimized = False


def example_safe_code_change():
    """
    Example: Safely optimize QA agent with before/after validation.
    """
    print("🔒 EXAMPLE: Safe Code Change with Automatic Rollback\n")
    
    # Setup
    executor = SafeCodeChangeExecutor()
    agent = MockAgent()
    
    test_data = {
        "code": "def add(a, b): return a + b",
        "tests": "assert add(2, 3) == 5",
    }
    
    # Define change function
    def apply_optimization():
        agent.optimize_algorithm()
    
    # Define rollback function (called if change is unsafe)
    def rollback():
        agent.restore_original()
    
    # Execute safe change
    results = executor.execute_safe_change(
        change_name="optimize_qa_algorithm",
        test_data=test_data,
        change_function=apply_optimization,
        rollback_function=rollback,
    )
    
    print("\n📋 Results:")
    print(f"  Change ID: {results.get('change_id')}")
    print(f"  Safe to Deploy: {results.get('safe_to_deploy')}")
    print(f"  Reason: {results.get('reason')}")
    
    return results


def example_change_history():
    """
    Example: Analyze patterns in code changes over time.
    """
    print("\n\n📈 EXAMPLE: Analyzing Change History\n")
    
    tracker = CodeChangeTracker()
    analyzer = ChangeHistoryAnalyzer(tracker)
    
    # Show statistics
    summary = analyzer.generate_summary_report()
    print(summary)
    
    # List all changes
    changes = tracker.list_changes()
    print(f"\nTracked Changes: {len(changes)}")
    for change_id in changes[:5]:  # Show first 5
        analysis = tracker.get_change_analysis(change_id)
        if analysis:
            status = "✅ Deployed" if analysis.get("safe_to_deploy") else "❌ Blocked"
            print(f"  {change_id}: {status}")


def example_rollback_scenario():
    """
    Example: Rollback when code change degrades quality.
    """
    print("\n\n🔄 EXAMPLE: Automatic Rollback on Degradation\n")
    
    executor = SafeCodeChangeExecutor()
    agent = MockAgent()
    
    test_data = {
        "code": "def multiply(a, b): return a * b",
        "tests": "assert multiply(2, 3) == 6",
    }
    
    def bad_change():
        print("  → Applying risky change...")
        agent.optimized = True
        # This might degrade performance
    
    def emergency_rollback():
        print("  → ⚠️  Change degraded quality!")
        print("  → 🔄 Automatically rolling back...")
        agent.restore_original()
    
    # Execute change (may trigger rollback)
    results = executor.execute_safe_change(
        change_name="risky_optimization",
        test_data=test_data,
        change_function=bad_change,
        rollback_function=emergency_rollback,
    )
    
    if not results.get("safe_to_deploy"):
        print("\n✅ Safety mechanism prevented bad deployment!")
        print(f"Reason: {results.get('reason')}")


if __name__ == "__main__":
    # Run examples
    example_safe_code_change()
    example_change_history()
    example_rollback_scenario()
