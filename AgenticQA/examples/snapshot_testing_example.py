"""
Example: Using Snapshots in Your Pipeline

Demonstrates how to integrate snapshot testing for data quality assurance.
"""

from agenticqa import AgentOrchestrator
from agenticqa.data_store.snapshot_manager import SnapshotManager


def validate_data_quality_with_snapshots(test_data: dict) -> bool:
    """
    Execute pipeline and validate all outputs against snapshots.
    
    Returns:
        True if all outputs match snapshots, False if any changes detected
    """
    
    snapshot_mgr = SnapshotManager(".snapshots/production")
    
    # Execute agents
    orchestrator = AgentOrchestrator()
    results = orchestrator.execute_all_agents(test_data)
    
    print("🔍 Validating Agent Outputs Against Snapshots...\n")
    
    all_match = True
    
    # Validate each agent
    for agent_name in ["qa_agent", "performance_agent", "compliance_agent", "devops_agent"]:
        agent_output = results.get(agent_name, {})
        snapshot_name = f"{agent_name}_production"
        
        comparison = snapshot_mgr.compare_snapshot(snapshot_name, agent_output)
        
        if comparison["status"] == "new":
            print(f"✅ {agent_name}: BASELINE CREATED")
            snapshot_mgr.create_snapshot(snapshot_name, agent_output)
        elif comparison["matches"]:
            print(f"✅ {agent_name}: MATCHES SNAPSHOT")
        else:
            print(f"❌ {agent_name}: MISMATCH DETECTED")
            print(f"   Differences: {comparison['differences']}")
            all_match = False
    
    print(f"\n📊 Overall Result: {'✅ PASS' if all_match else '❌ FAIL'}")
    return all_match


def report_snapshot_changes() -> None:
    """Generate report of snapshot changes."""
    
    snapshot_mgr = SnapshotManager(".snapshots/production")
    snapshots = snapshot_mgr.get_all_snapshots()
    
    print(f"📋 Snapshot Report\n")
    print(f"Total Snapshots: {len(snapshots)}\n")
    
    for snapshot_name in snapshots:
        filepath = snapshot_mgr.snapshot_dir / f"{snapshot_name}.json"
        size = filepath.stat().st_size
        
        print(f"  • {snapshot_name}")
        print(f"    Size: {size} bytes")


if __name__ == "__main__":
    # Example test data
    test_data = {
        "code": "def hello(name): return f'Hello, {name}!'",
        "tests": "assert hello('World') == 'Hello, World!'",
    }
    
    # Validate with snapshots
    success = validate_data_quality_with_snapshots(test_data)
    
    # Generate report
    print("\n" + "="*50 + "\n")
    report_snapshot_changes()
    
    exit(0 if success else 1)
