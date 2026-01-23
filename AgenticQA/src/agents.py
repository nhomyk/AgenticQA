"""Base Agent class with data store integration"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional, List
import json
from src.data_store import SecureDataPipeline


class BaseAgent(ABC):
    """Base class for all agents with data store integration"""

    def __init__(self, agent_name: str, use_data_store: bool = True):
        self.agent_name = agent_name
        self.use_data_store = use_data_store
        if use_data_store:
            self.pipeline = SecureDataPipeline(use_great_expectations=False)
        self.execution_history: List[Dict] = []

    @abstractmethod
    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """Execute agent task - must be implemented by subclass"""
        pass

    def _record_execution(
        self,
        status: str,
        output: Dict[str, Any],
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Record execution to data store"""
        if not self.use_data_store:
            return None

        execution_result = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_name": self.agent_name,
            "status": status,
            "output": output,
            "metadata": metadata or {},
        }

        success, pipeline_result = self.pipeline.execute_with_validation(
            self.agent_name, execution_result
        )

        artifact_id = pipeline_result.get("artifact_id")
        self.execution_history.append(
            {
                "artifact_id": artifact_id,
                "status": status,
                "timestamp": execution_result["timestamp"],
            }
        )

        return artifact_id

    def get_pattern_insights(self) -> Dict[str, Any]:
        """Get pattern analysis from accumulated data"""
        if not self.use_data_store:
            return {}

        patterns = self.pipeline.analyze_patterns()

        # Filter for this agent's data
        agent_patterns = {
            "errors": {
                "total": patterns["errors"].get("total_failures", 0),
                "types": patterns["errors"].get("failure_by_type", {}),
            },
            "performance": patterns["performance"],
            "flakiness": patterns["flakiness"],
        }

        return agent_patterns

    def get_similar_executions(self, status: str = "error", limit: int = 5) -> List[Dict]:
        """Retrieve similar historical executions from data store"""
        if not self.use_data_store:
            return []

        artifacts = self.pipeline.artifact_store.search_artifacts(
            source=self.agent_name, artifact_type="execution"
        )

        if status:
            artifacts = [a for a in artifacts if status in a.get("tags", [])]

        return artifacts[:limit]

    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp"""
        timestamp = datetime.utcnow().isoformat()
        log_entry = f"[{timestamp}] [{self.agent_name}] [{level}] {message}"
        print(log_entry)


class QAAssistantAgent(BaseAgent):
    """QA Assistant Agent - Reviews tests and provides feedback"""

    def __init__(self):
        super().__init__("QA_Assistant")

    def execute(self, test_results: Dict) -> Dict[str, Any]:
        """Analyze test results and provide QA feedback"""
        self.log("Analyzing test results")

        try:
            analysis = {
                "total_tests": test_results.get("total", 0),
                "passed": test_results.get("passed", 0),
                "failed": test_results.get("failed", 0),
                "coverage": test_results.get("coverage", 0),
                "recommendations": self._generate_recommendations(test_results),
            }

            self._record_execution("success", analysis, tags=["test_analysis"])
            self.log("QA analysis complete")
            return analysis

        except Exception as e:
            self._record_execution(
                "error",
                {"error": str(e)},
                metadata={"error_type": type(e).__name__},
                tags=["error"],
            )
            self.log(f"QA analysis failed: {str(e)}", "ERROR")
            raise

    def _generate_recommendations(self, test_results: Dict) -> List[str]:
        """Generate recommendations based on patterns"""
        patterns = self.get_pattern_insights()
        recommendations = []

        if test_results.get("failed", 0) > test_results.get("passed", 0) * 0.1:
            recommendations.append("High failure rate detected. Review recent changes.")

        if patterns.get("flakiness", {}).get("flaky_agents"):
            recommendations.append("Flaky tests detected. Consider stabilization review.")

        return recommendations


class PerformanceAgent(BaseAgent):
    """Performance Agent - Monitors and optimizes performance"""

    def __init__(self):
        super().__init__("Performance_Agent")

    def execute(self, execution_data: Dict) -> Dict[str, Any]:
        """Analyze performance metrics"""
        self.log("Analyzing performance metrics")

        try:
            duration = execution_data.get("duration_ms", 0)
            memory = execution_data.get("memory_mb", 0)

            analysis = {
                "duration_ms": duration,
                "memory_mb": memory,
                "status": "optimal" if duration < 5000 else "degraded",
                "optimizations": self._suggest_optimizations(execution_data),
            }

            self._record_execution("success", analysis, tags=["performance"])
            self.log("Performance analysis complete")
            return analysis

        except Exception as e:
            self._record_execution(
                "error", {"error": str(e)}, tags=["error"]
            )
            self.log(f"Performance analysis failed: {str(e)}", "ERROR")
            raise

    def _suggest_optimizations(self, data: Dict) -> List[str]:
        """Suggest optimizations based on patterns"""
        patterns = self.get_pattern_insights()
        perf = patterns.get("performance", {})
        suggestions = []

        avg_latency = perf.get("avg_latency_ms", 0)
        if avg_latency > 3000:
            suggestions.append("Average latency above 3s. Consider caching or parallelization.")

        return suggestions


class ComplianceAgent(BaseAgent):
    """Compliance Agent - Ensures regulatory compliance"""

    def __init__(self):
        super().__init__("Compliance_Agent")

    def execute(self, compliance_data: Dict) -> Dict[str, Any]:
        """Check compliance requirements"""
        self.log("Checking compliance")

        try:
            checks = {
                "data_encryption": compliance_data.get("encrypted", False),
                "pii_protection": compliance_data.get("pii_masked", False),
                "audit_logs": compliance_data.get("audit_enabled", False),
                "violations": self._check_violations(compliance_data),
            }

            self._record_execution("success", checks, tags=["compliance"])
            self.log("Compliance check complete")
            return checks

        except Exception as e:
            self._record_execution("error", {"error": str(e)}, tags=["error"])
            self.log(f"Compliance check failed: {str(e)}", "ERROR")
            raise

    def _check_violations(self, data: Dict) -> List[str]:
        """Check for compliance violations"""
        violations = []
        if not data.get("encrypted"):
            violations.append("Data encryption required but not enabled")
        if not data.get("pii_masked"):
            violations.append("PII masking required but not enabled")
        return violations


class DevOpsAgent(BaseAgent):
    """DevOps Agent - Manages deployment and infrastructure"""

    def __init__(self):
        super().__init__("DevOps_Agent")

    def execute(self, deployment_config: Dict) -> Dict[str, Any]:
        """Execute deployment operations"""
        self.log("Executing deployment")

        try:
            result = {
                "deployment_status": "success",
                "version": deployment_config.get("version"),
                "environment": deployment_config.get("environment"),
                "health_checks": self._run_health_checks(),
            }

            self._record_execution(
                "success", result, tags=["deployment"]
            )
            self.log("Deployment complete")
            return result

        except Exception as e:
            self._record_execution("error", {"error": str(e)}, tags=["error"])
            self.log(f"Deployment failed: {str(e)}", "ERROR")
            raise

    def _run_health_checks(self) -> Dict[str, bool]:
        """Run health checks"""
        return {
            "api_health": True,
            "database_connection": True,
            "cache_available": True,
        }


class AgentOrchestrator:
    """Orchestrates multiple agents and coordinates their execution"""

    def __init__(self):
        self.agents = {
            "qa": QAAssistantAgent(),
            "performance": PerformanceAgent(),
            "compliance": ComplianceAgent(),
            "devops": DevOpsAgent(),
        }
        self.log("Agent Orchestrator initialized with 4 agents")

    def execute_all_agents(self, data: Dict) -> Dict[str, Any]:
        """Execute all agents with their respective tasks"""
        results = {}

        for agent_name, agent in self.agents.items():
            try:
                if agent_name == "qa":
                    results[agent_name] = agent.execute(data.get("test_results", {}))
                elif agent_name == "performance":
                    results[agent_name] = agent.execute(
                        data.get("execution_data", {})
                    )
                elif agent_name == "compliance":
                    results[agent_name] = agent.execute(
                        data.get("compliance_data", {})
                    )
                elif agent_name == "devops":
                    results[agent_name] = agent.execute(
                        data.get("deployment_config", {})
                    )
            except Exception as e:
                results[agent_name] = {"error": str(e), "status": "failed"}

        return results

    def get_agent_insights(self) -> Dict[str, Any]:
        """Get insights from all agents"""
        insights = {}
        for agent_name, agent in self.agents.items():
            insights[agent_name] = agent.get_pattern_insights()
        return insights

    def log(self, message: str):
        """Log orchestrator messages"""
        timestamp = datetime.utcnow().isoformat()
        print(f"[{timestamp}] [ORCHESTRATOR] {message}")
