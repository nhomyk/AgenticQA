"""
Integration of Code Change Tracking with AgenticQA Pipeline

Demonstrates how to use before/after snapshots within the complete pipeline
to ensure code changes are safe and beneficial.
"""

from typing import Dict, Any, Callable, Optional
from agenticqa import AgentOrchestrator, DataQualityValidatedPipeline
from agenticqa.data_store.code_change_tracker import CodeChangeTracker, ChangeImpactReport


class SafeCodeChangeExecutor:
    """
    Safely execute code changes with automatic before/after validation.

    Ensures:
    - All metrics are captured before change
    - Code change is applied
    - All metrics are captured after change
    - Change is analyzed and safety determined
    - Automatic rollback if degradation detected
    """

    def __init__(self):
        """Initialize executor."""
        self.tracker = CodeChangeTracker()
        self.orchestrator = AgentOrchestrator()
        self.pipeline = DataQualityValidatedPipeline()

    def execute_safe_change(
        self,
        change_name: str,
        test_data: Dict[str, Any],
        change_function: Callable,
        rollback_function: Optional[Callable] = None,
        allow_performance_regression: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a code change with before/after validation.

        Args:
            change_name: Name of the code change
            test_data: Test data to validate against
            change_function: Function that applies the code change
            rollback_function: Function to rollback the change if needed
            allow_performance_regression: Allow slower execution if quality improved

        Returns:
            Analysis results with deployment recommendation

        Example:
            >>> def apply_optimization():
            ...     agent.optimize_algorithm()
            >>>
            >>> executor = SafeCodeChangeExecutor()
            >>> results = executor.execute_safe_change(
            ...     "optimize_qa_agent",
            ...     test_data,
            ...     apply_optimization,
            ...     rollback_function=agent.restore_original
            ... )
        """

        print(f"\n🔒 SAFE CODE CHANGE EXECUTION: {change_name}\n")

        # Phase 1: Capture BEFORE state
        print("📸 Phase 1: Capturing BEFORE snapshot...")
        before_results = self.orchestrator.execute_all_agents(test_data)
        before_metrics = self._extract_metrics(before_results)

        change_id = self.tracker.start_change(change_name, before_metrics)

        # Phase 2: Apply code change
        print(f"\n⚙️  Phase 2: Applying code change...")
        try:
            change_function()
            print("✅ Code change applied successfully")
        except Exception as e:
            print(f"❌ Failed to apply change: {e}")
            return {"status": "failed", "error": str(e)}

        # Phase 3: Capture AFTER state
        print(f"\n📸 Phase 3: Capturing AFTER snapshot...")
        after_results = self.orchestrator.execute_all_agents(test_data)
        after_metrics = self._extract_metrics(after_results)

        # Phase 4: Analyze impact
        print(f"\n📊 Phase 4: Analyzing impact...")
        analysis = self.tracker.end_change(after_metrics, change_id)

        # Phase 5: Report and decide
        print(f"\n📋 Phase 5: Deployment decision...")
        report = ChangeImpactReport.generate_report(analysis)
        print(report)

        # Phase 6: Automatic rollback if needed
        if not analysis.safe_to_deploy and rollback_function:
            print(f"\n⚠️  Phase 6: Triggering automatic rollback...")
            rollback_function()
            print("✅ System restored to previous state")

        return {
            "change_id": change_id,
            "metrics": analysis.to_dict(),
            "safe_to_deploy": analysis.safe_to_deploy,
            "reason": analysis.reason,
        }

    def _extract_metrics(self, agent_results: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metrics from agent execution results."""
        metrics = {
            "quality_score": self._calculate_quality_score(agent_results),
            "execution_time_ms": agent_results.get("execution_time_ms", 0),
            "tests_passed": agent_results.get("qa_agent", {}).get("tests_passed", 0),
            "tests_failed": agent_results.get("qa_agent", {}).get("tests_failed", 0),
            "compliance_score": agent_results.get("compliance_agent", {}).get(
                "compliance_score", 0
            ),
        }
        return metrics

    def _calculate_quality_score(self, results: Dict[str, Any]) -> float:
        """Calculate overall quality score from agent results."""
        scores = []

        if "qa_agent" in results and "quality_score" in results["qa_agent"]:
            scores.append(results["qa_agent"]["quality_score"])

        if "performance_agent" in results and "status" in results["performance_agent"]:
            perf_status = results["performance_agent"]["status"]
            scores.append(100.0 if perf_status == "passed" else 50.0)

        if "compliance_agent" in results and "compliance_score" in results["compliance_agent"]:
            scores.append(results["compliance_agent"]["compliance_score"])

        return sum(scores) / len(scores) if scores else 0.0


class ChangeHistoryAnalyzer:
    """Analyze patterns in code changes over time."""

    def __init__(self, tracker: CodeChangeTracker):
        """Initialize analyzer."""
        self.tracker = tracker

    def get_change_statistics(self) -> Dict[str, Any]:
        """Get statistics about all changes."""
        changes = self.tracker.list_changes()

        successful_changes = 0
        failed_changes = 0
        avg_quality_delta = 0

        for change_id in changes:
            analysis = self.tracker.get_change_analysis(change_id)
            if analysis:
                if isinstance(analysis, dict):
                    if analysis.get("safe_to_deploy"):
                        successful_changes += 1
                    else:
                        failed_changes += 1

                    quality_delta = analysis.get("quality_delta", 0)
                    avg_quality_delta += quality_delta

        total_changes = len(changes)

        return {
            "total_changes": total_changes,
            "successful_changes": successful_changes,
            "failed_changes": failed_changes,
            "success_rate": (successful_changes / total_changes * 100) if total_changes > 0 else 0,
            "average_quality_delta": avg_quality_delta / total_changes if total_changes > 0 else 0,
        }

    def generate_summary_report(self) -> str:
        """Generate summary of all code changes."""
        stats = self.get_change_statistics()

        report = []
        report.append("=" * 80)
        report.append("📈 CODE CHANGE HISTORY SUMMARY")
        report.append("=" * 80)
        report.append("")
        report.append(f"Total Changes: {stats['total_changes']}")
        report.append(f"Successful: {stats['successful_changes']} ✅")
        report.append(f"Failed: {stats['failed_changes']} ❌")
        report.append(f"Success Rate: {stats['success_rate']:.1f}%")
        report.append(f"Avg Quality Delta: {stats['average_quality_delta']:+.1f}%")
        report.append("")
        report.append("=" * 80)

        return "\n".join(report)
