"""
AgenticQA Data Quality Testing - Snapshot Integration

Extends the data quality pipeline to include comprehensive snapshot validation
to ensure data accuracy, correctness, and consistency across all deployments.
"""

from datetime import datetime
from typing import Dict, List, Any
from agenticqa.data_store.snapshot_manager import SnapshotManager
from agenticqa.data_store.data_quality_tester import DataQualityTester


class SnapshotValidatingPipeline:
    """
    Pipeline with integrated snapshot validation for comprehensive quality assurance.
    
    This ensures:
    - Agent outputs are consistent and predictable
    - Data store artifacts maintain structural integrity
    - Quality metrics remain within expected ranges
    """
    
    def __init__(self, snapshot_dir: str = ".snapshots/pipeline"):
        """
        Initialize snapshot validating pipeline.
        
        Args:
            snapshot_dir: Directory for storing snapshots
        """
        self.snapshot_mgr = SnapshotManager(snapshot_dir)
        self.quality_tester = DataQualityTester()
        self.validation_results: Dict[str, Any] = {}
    
    def validate_with_snapshots(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute pipeline with comprehensive snapshot validation.
        
        Args:
            test_data: Test data to process
            
        Returns:
            Validation results including snapshot comparisons and quality metrics
        """
        from agenticqa import AgentOrchestrator
        
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "snapshots_validated": [],
            "quality_checks_passed": 0,
            "quality_checks_failed": 0,
            "agent_outputs_match": True,
            "all_validations_passed": True,
        }
        
        # Execute agents
        orchestrator = AgentOrchestrator()
        agent_results = orchestrator.execute_all_agents(test_data)
        
        # Validate each agent output against snapshots
        for agent_name in ["qa_agent", "performance_agent", "compliance_agent", "devops_agent"]:
            agent_output = agent_results.get(agent_name, {})
            
            comparison = self.snapshot_mgr.compare_snapshot(
                f"{agent_name}_snapshot",
                agent_output
            )
            
            if comparison["status"] == "new":
                self.snapshot_mgr.create_snapshot(
                    f"{agent_name}_snapshot",
                    agent_output
                )
            
            snapshot_entry = {
                "agent": agent_name,
                "status": comparison["status"],
                "matches": comparison["matches"],
            }
            
            if not comparison["matches"]:
                results["agent_outputs_match"] = False
                results["all_validations_passed"] = False
                snapshot_entry["differences"] = comparison["differences"]
            
            results["snapshots_validated"].append(snapshot_entry)
        
        # Run quality tests
        quality_results = self.quality_tester.run_all_tests(test_data, agent_results)
        
        results["quality_checks_passed"] = quality_results.get("passed_tests", 0)
        results["quality_checks_failed"] = quality_results.get("failed_tests", 0)
        
        if quality_results.get("failed_tests", 0) > 0:
            results["all_validations_passed"] = False
        
        return results
    
    def generate_validation_report(self, validation_results: Dict[str, Any]) -> str:
        """
        Generate human-readable validation report.
        
        Args:
            validation_results: Results from validate_with_snapshots
            
        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 70)
        report.append("🔍 DATA QUALITY & SNAPSHOT VALIDATION REPORT")
        report.append("=" * 70)
        report.append("")
        
        # Overall status
        status = "✅ PASSED" if validation_results["all_validations_passed"] else "❌ FAILED"
        report.append(f"Overall Status: {status}")
        report.append(f"Timestamp: {validation_results['timestamp']}")
        report.append("")
        
        # Snapshot validation results
        report.append("📸 SNAPSHOT VALIDATION RESULTS:")
        report.append("-" * 70)
        
        for snapshot in validation_results["snapshots_validated"]:
            agent = snapshot["agent"]
            matches = "✅" if snapshot["matches"] else "❌"
            report.append(f"  {matches} {agent}: {snapshot['status']}")
            
            if "differences" in snapshot:
                diff = snapshot["differences"]
                if diff.get("changed_values"):
                    report.append(f"      Changed: {list(diff['changed_values'].keys())}")
        
        report.append("")
        
        # Quality test results
        report.append("✔️  QUALITY TEST RESULTS:")
        report.append("-" * 70)
        report.append(f"  Passed: {validation_results['quality_checks_passed']}")
        report.append(f"  Failed: {validation_results['quality_checks_failed']}")
        report.append("")
        
        # Recommendation
        if validation_results["all_validations_passed"]:
            report.append("✅ RECOMMENDATION: Safe to deploy")
        else:
            report.append("❌ RECOMMENDATION: Do not deploy - fix issues first")
        
        report.append("=" * 70)
        
        return "\n".join(report)
