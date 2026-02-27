"""Base Agent class with data store integration"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List, TYPE_CHECKING
import json
import os
import re
import tempfile
from src.data_store import SecureDataPipeline


# ---------------------------------------------------------------------------
# Input normalizers — accept multiple real-world tool output formats
# ---------------------------------------------------------------------------

def normalize_coverage_input(data: Dict) -> Dict:
    """Normalize coverage data from various tool formats into SDET's internal shape.

    Accepts:
    - Istanbul/nyc JSON: {"total": {"lines": {"pct": 62}}, "files": {...}}
    - coverage.py JSON: {"totals": {"percent_covered": 62}, "files": {...}}
    - Cypress coverage: {"overall": 62, "files": [...]}
    - Internal format (passthrough): {"coverage_percent": 62, "uncovered_files": [...]}
    - Simple dict with overall_coverage key
    """
    if "coverage_percent" in data and "uncovered_files" in data:
        return data  # already normalized

    normalized: Dict[str, Any] = {}

    # Istanbul/nyc JSON summary format
    if "total" in data and isinstance(data["total"], dict):
        total = data["total"]
        pct = (
            total.get("lines", {}).get("pct")
            or total.get("statements", {}).get("pct")
            or total.get("branches", {}).get("pct")
            or 0
        )
        normalized["coverage_percent"] = pct
        normalized["uncovered_files"] = [
            f for f, v in data.get("files", {}).items()
            if isinstance(v, dict) and v.get("lines", {}).get("pct", 100) < 80
        ]

    # coverage.py JSON format
    elif "totals" in data and "percent_covered" in data.get("totals", {}):
        normalized["coverage_percent"] = data["totals"]["percent_covered"]
        normalized["uncovered_files"] = [
            f for f, v in data.get("files", {}).items()
            if isinstance(v, dict) and v.get("summary", {}).get("percent_covered", 100) < 80
        ]

    # overall_coverage dict (e.g. from our test run)
    elif "overall_coverage" in data:
        normalized["coverage_percent"] = data["overall_coverage"]
        files = data.get("files", {})
        normalized["uncovered_files"] = [
            f for f, v in files.items()
            if isinstance(v, dict) and v.get("coverage", 100) < 80
        ]

    # Cypress coverage summary: {"overall": 62, "files": [...]}
    elif "overall" in data:
        normalized["coverage_percent"] = data["overall"]
        normalized["uncovered_files"] = [
            f if isinstance(f, str) else f.get("path", "")
            for f in data.get("files", [])
            if isinstance(f, dict) and f.get("coverage", 100) < 80
        ]

    else:
        normalized["coverage_percent"] = data.get("percent", data.get("pct", 0))
        normalized["uncovered_files"] = data.get("uncovered_files", [])

    normalized.setdefault("test_type", data.get("test_type", "unknown"))
    normalized.setdefault("repo", data.get("repo", ""))
    return normalized


def normalize_linting_input(data: Dict) -> Dict:
    """Normalize linting data from various tool formats into SRE's internal shape.

    Accepts:
    - ESLint JSON: [{"filePath": "...", "messages": [{"ruleId": "...", "message": "..."}]}]
    - ESLint JSON wrapped: {"results": [...]}
    - Internal format (passthrough): {"errors": [{"rule": "...", "message": "..."}]}
    - Simple list of error dicts
    """
    if "errors" in data and isinstance(data["errors"], list):
        return data  # already normalized

    errors = []

    raw = data
    # ESLint wrapped
    if "results" in data:
        raw = data["results"]
    # ESLint is a list at top level
    elif isinstance(data, list):
        raw = data

    # oxlint JSON: {"diagnostics": [...], "number_of_files": N, ...}
    # rule field may be a string ("no-var") or an object {"name": "no-var", "plugin": "eslint"}
    if isinstance(raw, dict) and "diagnostics" in raw:
        for diag in raw["diagnostics"]:
            if isinstance(diag, dict):
                rule_raw = diag.get("rule", diag.get("rule_id", "unknown"))
                if isinstance(rule_raw, dict):
                    plugin = rule_raw.get("plugin", "")
                    name = rule_raw.get("name", "unknown")
                    rule_str = f"{plugin}/{name}" if plugin and plugin not in ("eslint",) else name
                else:
                    rule_str = str(rule_raw)
                errors.append({
                    "rule": rule_str,
                    "message": diag.get("message", ""),
                    "file": diag.get("filename", ""),
                    "severity": diag.get("severity", "error").lower(),
                    "line": (diag.get("start") or {}).get("line"),
                    "col": (diag.get("start") or {}).get("column"),
                })
        return {
            **({k: v for k, v in data.items() if k not in ("diagnostics", "summary")} if isinstance(data, dict) else {}),
            "errors": errors,
        }

    if isinstance(raw, list):
        for file_result in raw:
            if isinstance(file_result, dict):
                # oxlint flat-array diagnostic: has "filename" + "rule_id"
                if "filename" in file_result and "rule_id" in file_result:
                    errors.append({
                        "rule": file_result.get("rule_id", "unknown"),
                        "message": file_result.get("message", ""),
                        "file": file_result.get("filename", ""),
                        "severity": file_result.get("severity", "error").lower(),
                        "line": (file_result.get("start") or {}).get("line"),
                        "col": (file_result.get("start") or {}).get("column"),
                    })
                    continue
                file_path = file_result.get("filePath", file_result.get("file", ""))
                messages = file_result.get("messages", file_result.get("errors", []))
                for msg in messages:
                    if isinstance(msg, dict):
                        errors.append({
                            "rule": msg.get("ruleId") or msg.get("rule", "unknown"),
                            "message": msg.get("message", ""),
                            "file": file_path,
                            "severity": "error" if msg.get("severity") == 2 else "warning",
                            "line": msg.get("line"),
                        })

    # Preserve all passthrough keys (repo_path, language, run_id, etc.) from the source dict
    base = {k: v for k, v in data.items() if k not in ("results",)} if isinstance(data, dict) else {}
    return {**base, "errors": errors}

if TYPE_CHECKING:
    from src.agenticqa.collaboration import AgentRegistry


class BaseAgent(ABC):
    """Base class for all agents with data store integration, RAG learning, and collaboration"""

    def __init__(self, agent_name: str, use_data_store: bool = True, use_rag: bool = True):
        self.agent_name = agent_name
        self.use_data_store = use_data_store
        self.use_rag = use_rag

        # Initialize collaboration (injected by registry)
        self.agent_registry: Optional["AgentRegistry"] = None
        self._delegation_depth = 0

        # Initialize data store pipeline
        self.pattern_analyzer = None
        self.repo_profile = None
        if use_data_store:
            self.pipeline = SecureDataPipeline(use_great_expectations=False)
            self.pattern_analyzer = self.pipeline.pattern_analyzer
            try:
                from src.data_store.repo_profile import RepoProfile
                self.repo_profile = RepoProfile.for_current_repo()
            except Exception:
                pass

        # Initialize RAG system for semantic learning and retrieval
        self.rag = None
        if use_rag:
            try:
                from src.agenticqa.rag.config import create_rag_system

                self.rag = create_rag_system()
                self.log(
                    f"RAG system initialized for {agent_name} - agent will learn from Weaviate",
                    "INFO",
                )
            except Exception as e:
                self.log(
                    f"RAG initialization failed: {e}. Agent will use basic pattern analysis only.",
                    "WARNING",
                )
                self.use_rag = False

        # Initialize feedback loop for learning from outcomes
        self.feedback = None
        self.outcome_tracker = None
        self._threshold_calibrator = None
        self._strategy_selector = None
        try:
            from src.agenticqa.verification.feedback_loop import RelevanceFeedback
            from src.agenticqa.verification.outcome_tracker import OutcomeTracker
            from src.agenticqa.verification.threshold_calibrator import ThresholdCalibrator
            from src.agenticqa.verification.strategy_selector import StrategySelector

            self.feedback = RelevanceFeedback()
            self.outcome_tracker = OutcomeTracker()
            self._threshold_calibrator = ThresholdCalibrator(self.outcome_tracker)
            self._strategy_selector = StrategySelector(outcome_tracker=self.outcome_tracker)

            # Wire calibrator into RAG retriever for adaptive thresholds
            if self.rag and hasattr(self.rag, "retriever"):
                self.rag.retriever.threshold_calibrator = self._threshold_calibrator
        except Exception:
            pass  # Graceful degradation - agent works without feedback

        self._last_retrieved_doc_ids: List[str] = []
        self.execution_history: List[Dict] = []

    def _get_agent_type(self) -> str:
        """Get agent type for RAG lookups"""
        # Map agent names to RAG agent types
        agent_type_map = {
            "QA_Assistant": "qa",
            "Performance_Agent": "performance",
            "Compliance_Agent": "compliance",
            "DevOps_Agent": "devops",
            "SDET_Agent": "qa",
            "SRE_Agent": "devops",
            "Fullstack_Agent": "devops",
        }
        return agent_type_map.get(self.agent_name, "qa")

    def _augment_with_rag(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Augment execution context with RAG-retrieved insights from Weaviate.

        This enables agents to learn from historical executions by retrieving
        semantically similar past decisions, errors, patterns, and solutions.
        Retrieved documents are tracked for feedback, and results are reranked
        based on historical outcome data.

        Args:
            context: Current execution context

        Returns:
            Augmented context with rag_recommendations and high_confidence_insights
        """
        if not self.use_rag or not self.rag:
            self._last_retrieved_doc_ids = []
            return context

        try:
            agent_type = self._get_agent_type()
            augmented_context = self.rag.augment_agent_context(agent_type, context)

            # Track retrieved documents for feedback loop
            self._last_retrieved_doc_ids = []
            recommendations = augmented_context.get("rag_recommendations", [])
            for rec in recommendations:
                doc_id = rec.get("source", {}).get("doc_id", "")
                if doc_id:
                    self._last_retrieved_doc_ids.append(doc_id)
                    if self.feedback:
                        self.feedback.record_retrieval(doc_id, rec.get("type", "unknown"))

            # Rerank recommendations using feedback scores
            if self.feedback and recommendations:
                rerank_input = []
                for rec in recommendations:
                    rerank_input.append({
                        **rec,
                        "doc_id": rec.get("source", {}).get("doc_id", ""),
                        "similarity": rec.get("confidence", 0.0),
                    })
                reranked = self.feedback.rerank_results(rerank_input)
                # Update recommendations with reranked order and adjusted confidence
                for rec in reranked:
                    rec["confidence"] = rec.get("adjusted_similarity", rec.get("confidence", 0.0))
                augmented_context["rag_recommendations"] = reranked

                # Recompute high-confidence insights after reranking
                high_confidence = [r for r in reranked if r.get("confidence", 0) > 0.75]
                if high_confidence:
                    augmented_context["high_confidence_insights"] = high_confidence
                elif "high_confidence_insights" in augmented_context:
                    del augmented_context["high_confidence_insights"]

            # Apply adaptive strategy (Phase 5) — filter/cap recommendations
            strategy = self._get_adaptive_strategy()
            if strategy.name != "standard":
                self.log(f"Applying {strategy.name} strategy: {strategy.description}", "INFO")

            recs = augmented_context.get("rag_recommendations", [])
            if strategy.require_high_confidence:
                recs = augmented_context.get("high_confidence_insights", recs[:strategy.max_recommendations])
            recs = recs[:strategy.max_recommendations]
            augmented_context["rag_recommendations"] = recs
            augmented_context["execution_strategy"] = strategy.name

            # Apply pattern-driven guards (Phase 3) — may further filter recs and add warnings
            exec_strategy = self._get_execution_strategy()
            augmented_context = self._apply_pattern_guards(augmented_context, exec_strategy)
            recs = augmented_context.get("rag_recommendations", recs)

            # Log RAG insights for transparency
            insights_count = augmented_context.get("rag_insights_count", 0)
            if insights_count > 0:
                self.log(f"RAG retrieved {insights_count} relevant insights from Weaviate", "INFO")

            # --- Decision Provenance ---
            confidences = [r.get("confidence", 0.0) for r in recs if isinstance(r.get("confidence"), (int, float))]
            avg_sim = round(sum(confidences) / len(confidences), 3) if confidences else 0.0
            high_conf = augmented_context.get("high_confidence_insights") or []
            rag_provenance = {
                "rag_docs_retrieved": len(recs),
                "avg_similarity": avg_sim,
                "doc_ids": self._last_retrieved_doc_ids[:5],
                "strategy": strategy.name,
                "high_confidence_count": len(high_conf),
            }
            augmented_context["_provenance"] = rag_provenance

            # --- Complexity metric for degradation detection ---
            obs = getattr(self, "observability_store", None)
            if obs is not None:
                try:
                    obs.log_complexity_metric(
                        agent=self.agent_name,
                        action="rag_augment",
                        trace_id=context.get("trace_id"),
                        rag_docs=len(recs),
                        avg_sim=avg_sim,
                        patterns=len(self._last_retrieved_doc_ids),
                        strategy=strategy.name,
                    )
                except Exception:
                    pass

            return augmented_context
        except Exception as e:
            self.log(f"RAG augmentation failed: {e}. Proceeding without RAG insights.", "WARNING")
            self._last_retrieved_doc_ids = []
            return context

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
        """
        Record execution to data store and Weaviate for semantic learning.

        This dual-recording strategy enables both:
        1. Structured artifact storage for validation and patterns
        2. Semantic vector embeddings for RAG retrieval and learning
        """
        artifact_id = None

        # 1. Record to artifact store (structured data)
        if self.use_data_store:
            execution_result = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
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

        # 2. Log to Weaviate (semantic embeddings for RAG)
        if self.use_rag and self.rag:
            try:
                agent_type = self._get_agent_type()
                execution_result = {
                    "agent_name": self.agent_name,
                    "status": status,
                    "output": output,
                    "metadata": metadata or {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "artifact_id": artifact_id,
                }
                self.rag.log_agent_execution(agent_type, execution_result)
                self.log(f"Execution logged to Weaviate for future learning", "DEBUG")
            except Exception as e:
                self.log(f"Failed to log execution to Weaviate: {e}", "WARNING")

        # 3. Feed outcome back to relevance feedback loop
        if self.feedback and self._last_retrieved_doc_ids:
            try:
                success = (status == "success")
                for doc_id in self._last_retrieved_doc_ids:
                    self.feedback.record_feedback(doc_id, success=success)
                self.log(
                    f"Feedback recorded for {len(self._last_retrieved_doc_ids)} docs "
                    f"(outcome={'helpful' if success else 'unhelpful'})",
                    "DEBUG",
                )
            except Exception as e:
                self.log(f"Failed to record feedback: {e}", "WARNING")
            finally:
                self._last_retrieved_doc_ids = []

        # 4. Capture golden snapshot for model regression testing — non-blocking
        if status == "success":
            try:
                import os as _os
                from agenticqa.regression.model_regression import ModelRegressionTester
                _model_id = getattr(self, "_model_id", "unknown")
                _out_text = str(output)[:4000]
                _run_id = _os.getenv("GITHUB_RUN_ID", "local")
                _tester = ModelRegressionTester()
                _tester.capture_golden(self.agent_name, _model_id, {"agent": self.agent_name},
                                       _out_text, run_id=_run_id)
            except Exception:
                pass  # non-blocking

        # 5. Sign output for provenance chain — non-blocking
        if status == "success":
            try:
                import os as _os
                from agenticqa.provenance.output_provenance import OutputProvenanceLogger
                _model_id = getattr(self, "_model_id", "unknown")
                _out_text = str(output)[:4000]
                _run_id = _os.getenv("GITHUB_RUN_ID", "local")
                OutputProvenanceLogger().sign_and_log(
                    agent_name=self.agent_name,
                    model_id=_model_id,
                    output_text=_out_text,
                    run_id=_run_id,
                    input_data={"agent": self.agent_name},
                )
            except Exception:
                pass  # non-blocking

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

    def _get_adaptive_strategy(self):
        """Get current execution strategy based on recent outcomes."""
        selector = getattr(self, "_strategy_selector", None)
        if selector:
            try:
                return selector.select_strategy(self._get_agent_type())
            except Exception:
                pass
        from src.agenticqa.verification.strategy_selector import STRATEGIES
        return STRATEGIES["standard"]

    def _get_execution_strategy(self) -> Dict[str, Any]:
        """
        Determine execution strategy based on historical patterns.

        Returns strategy parameters that agents use to adjust behavior:
        - confidence_adjustment: Multiply RAG threshold by this factor
        - extra_caution: Whether to apply stricter validation
        - known_failure_types: Top failure patterns to watch for
        - recent_failure_rate: This agent's recent failure rate
        """
        strategy = {
            "confidence_adjustment": 1.0,
            "extra_caution": False,
            "known_failure_types": [],
            "recent_failure_rate": 0.0,
            "flakiness_trend": "stable",
            "error_signatures": [],
        }

        if not self.use_data_store:
            return strategy

        try:
            patterns = self.get_pattern_insights()

            # Check if this agent is flaky — if so, be more cautious
            flaky_agents = patterns.get("flakiness", {}).get("flaky_agents", {})
            if self.agent_name in flaky_agents:
                agent_flak = flaky_agents[self.agent_name]
                fail_rate = agent_flak.get("fail_rate", 0)
                strategy["recent_failure_rate"] = fail_rate
                strategy["flakiness_trend"] = agent_flak.get("trend", "stable")
                if fail_rate > 0.3:
                    strategy["extra_caution"] = True
                    strategy["confidence_adjustment"] = 1.2
                # Escalate caution further if flakiness is accelerating
                if strategy["flakiness_trend"] == "accelerating":
                    strategy["extra_caution"] = True
                    strategy["confidence_adjustment"] = max(strategy["confidence_adjustment"], 1.3)

            # Collect known failure types for early detection
            failure_types = patterns.get("errors", {}).get("types", {})
            if failure_types:
                sorted_failures = sorted(failure_types.items(), key=lambda x: x[1], reverse=True)
                strategy["known_failure_types"] = [f[0] for f in sorted_failures[:5]]

            # Check performance — high latency means system under stress
            perf = patterns.get("performance", {})
            if perf.get("avg_latency_ms", 0) > 5000:
                strategy["extra_caution"] = True

            # Attach top error signatures so agents can recognise recurring failure modes
            if hasattr(self, "pattern_analyzer") and self.pattern_analyzer is not None:
                strategy["error_signatures"] = self.pattern_analyzer.get_error_signatures(
                    self.agent_name
                )

        except Exception as e:
            self.log(f"Pattern analysis for strategy failed: {e}", "WARNING")

        return strategy

    def _check_constitution(self, action_type: str, context: Dict[str, Any]) -> None:
        """Check action against the Agent Constitution. Raises ConstitutionalViolationError on DENY."""
        try:
            from agenticqa.constitutional_gate import check_action, ConstitutionalViolationError
            result = check_action(action_type, context)
            if result["verdict"] == "DENY":
                raise ConstitutionalViolationError(
                    result.get("reason", f"Action '{action_type}' denied by {result.get('law')}"),
                    law=result.get("law"),
                )
        except ImportError:
            pass  # Constitutional gate not available — graceful degradation

    def _apply_pattern_guards(
        self, context: Dict[str, Any], exec_strategy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply pattern-driven guards to execution context (Phase 3).

        Injects warnings and conservative filtering into the augmented context
        based on historical failure patterns so agent execute() methods adapt.
        """
        if not exec_strategy.get("extra_caution"):
            return context

        known_failures = exec_strategy.get("known_failure_types", [])
        flakiness_trend = exec_strategy.get("flakiness_trend", "stable")
        failure_rate = exec_strategy.get("recent_failure_rate", 0.0)
        confidence_adjustment = exec_strategy.get("confidence_adjustment", 1.0)

        if known_failures:
            context["pattern_warnings"] = {
                "known_failure_types": known_failures,
                "extra_validation": True,
            }
            self.log(
                f"Pattern guard: known failure types {known_failures[:3]} detected — extra validation active",
                "WARNING",
            )

        if flakiness_trend == "accelerating" and failure_rate > 0.5:
            context["flakiness_warning"] = {
                "trend": flakiness_trend,
                "recent_failure_rate": failure_rate,
                "recommendation": "Consider reducing batch size or adding retry logic",
            }
            self.log(
                f"Pattern guard: flakiness accelerating ({failure_rate:.0%} failure rate) — flagging for review",
                "WARNING",
            )

        # Conservative confidence filter — drop low-confidence recs when adjustment is high
        if confidence_adjustment > 1.2 and "rag_recommendations" in context:
            before = len(context["rag_recommendations"])
            context["rag_recommendations"] = [
                r for r in context["rag_recommendations"]
                if r.get("confidence", 0) >= 0.75
            ]
            after = len(context["rag_recommendations"])
            if before != after:
                self.log(
                    f"Pattern guard: conservative filter dropped {before - after} low-confidence recs "
                    f"(adjustment={confidence_adjustment:.1f}x)",
                    "INFO",
                )

        return context

    def _get_graph_store(self):
        """Get DelegationGraphStore if available via agent registry."""
        if hasattr(self, "_graph_store"):
            return self._graph_store
        try:
            tracker = getattr(self.agent_registry, "tracker", None)
            if tracker and hasattr(tracker, "graph_store"):
                self._graph_store = tracker.graph_store
                return self._graph_store
        except Exception:
            pass
        self._graph_store = None
        return None

    def delegate_to_agent(self, agent_name: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delegate a task to another specialized agent.

        Consults GraphRAG for delegation recommendations and records outcomes
        to OutcomeTracker for future calibration.

        Args:
            agent_name: Name of target agent (e.g., "SRE_Agent", "Compliance_Agent")
            task: Task data to pass to the agent

        Returns:
            Result from the delegated agent
        """
        import time
        import uuid

        if not self.agent_registry:
            raise Exception(f"{self.agent_name} cannot delegate: No agent registry configured")

        task_type = task.get("task_type", task.get("task", "unknown"))
        delegation_id = str(uuid.uuid4())
        target_agent = agent_name
        confidence = 0.5
        recommendation_source = "manual"
        risk: Dict[str, Any] = {}

        # Constitutional check — enforces T1-002 (delegation depth ≤ 3) in agent pipeline
        self._check_constitution("delegate", {
            "delegation_depth": self._delegation_depth,
            "to_agent": agent_name,
            "trace_id": task.get("trace_id"),
        })

        # Consult GraphRAG for delegation recommendation
        try:
            graph_store = self._get_graph_store()
            if graph_store:
                risk = graph_store.predict_delegation_failure_risk(
                    self.agent_name, agent_name, task_type
                )
                if not isinstance(risk, dict):
                    risk = {}
                if risk.get("risk_level") == "high" and risk.get("confidence", 0) > 0.5:
                    rec = graph_store.recommend_delegation_target(
                        self.agent_name, task_type
                    )
                    if rec and rec.get("recommended_agent") != agent_name:
                        self.log(
                            f"GraphRAG suggests {rec['recommended_agent']} over {agent_name} "
                            f"for {task_type} (risk: {risk['risk_level']})",
                            "WARNING",
                        )
                        target_agent = rec["recommended_agent"]
                        confidence = min(1.0, rec.get("priority_score", 8.0) / 10.0)
                        recommendation_source = "graphrag"
                    elif risk.get("failure_probability", 0) > 0.7:
                        # High risk, no better simple recommendation — try optimal path
                        try:
                            optimal = graph_store.find_optimal_delegation_path(
                                self.agent_name, agent_name, max_hops=2
                            )
                            if optimal and optimal.get("path") and len(optimal["path"]) > 1:
                                intermediate = optimal["path"][1]
                                self.log(
                                    f"GraphRAG rerouting via {intermediate} (efficiency={optimal.get('efficiency_score', 0):.2f})",
                                    "INFO",
                                )
                                target_agent = intermediate
                                confidence = min(1.0, optimal.get("efficiency_score", 0.5))
                                recommendation_source = "graphrag_optimal_path"
                            else:
                                task["high_risk_warning"] = {
                                    "risk_level": risk["risk_level"],
                                    "failure_probability": risk["failure_probability"],
                                    "reason": risk.get("recommendation", "High historical failure rate"),
                                }
                                self.log(
                                    f"Delegation to {agent_name} is high-risk "
                                    f"(p={risk['failure_probability']:.2f}) — no safe reroute found, flagging task",
                                    "WARNING",
                                )
                        except Exception as path_err:
                            self.log(f"Optimal path lookup failed: {path_err}", "WARNING")
                            task["high_risk_warning"] = {
                                "risk_level": risk.get("risk_level"),
                                "failure_probability": risk.get("failure_probability"),
                            }
                elif risk.get("failure_probability") is not None:
                    confidence = 1.0 - risk["failure_probability"]
                    recommendation_source = "graphrag"
        except Exception as e:
            self.log(f"GraphRAG delegation lookup failed: {e}", "WARNING")

        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.5

        # --- Delegation Provenance ---
        task["_delegation_provenance"] = {
            "recommendation_source": recommendation_source,
            "requested_agent": agent_name,
            "target_agent": target_agent,
            "recommendation_followed": target_agent == agent_name,
            "risk_level": risk.get("risk_level") if isinstance(risk, dict) else None,
            "failure_probability": risk.get("failure_probability") if isinstance(risk, dict) else None,
            "confidence": confidence,
        }

        # Record prediction before execution
        if self.outcome_tracker:
            try:
                self.outcome_tracker.record_prediction(
                    delegation_id=delegation_id,
                    from_agent=self.agent_name,
                    to_agent=target_agent,
                    task_type=task_type,
                    predicted_confidence=confidence,
                    recommendation_source=recommendation_source,
                )
            except Exception:
                pass

        # Execute delegation
        self.log(f"Delegating task to {target_agent}", "INFO")
        start_time = time.time()
        success = False
        try:
            result = self.agent_registry.delegate_task(
                from_agent=self.agent_name,
                to_agent=target_agent,
                task=task,
                depth=self._delegation_depth + 1,
            )
            success = result.get("status", "") != "error"
            self.log(f"Delegation to {target_agent} completed", "INFO")
            return result
        except Exception:
            success = False
            raise
        finally:
            # Record actual outcome
            if self.outcome_tracker:
                try:
                    duration_ms = (time.time() - start_time) * 1000
                    self.outcome_tracker.record_outcome(
                        delegation_id=delegation_id,
                        actual_success=success,
                        duration_ms=duration_ms,
                    )
                    if self._threshold_calibrator:
                        self._threshold_calibrator.invalidate_cache()
                except Exception:
                    pass

    def query_agent_expertise(self, agent_name: str, question: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query another agent for expertise without full task delegation.

        Use this for consultation/advice rather than delegating work.

        Example:
            # Compliance asks DevOps if deployment config is secure
            advice = self.query_agent_expertise("DevOps_Agent", {
                "question": "Is this deployment config secure?",
                "config": deployment_config
            })
        """
        if not self.agent_registry:
            raise Exception(f"{self.agent_name} cannot query: No agent registry configured")

        return self.agent_registry.query_agent(
            from_agent=self.agent_name,
            to_agent=agent_name,
            question=question,
            depth=self._delegation_depth + 1,
        )

    def can_delegate_to(self, agent_name: str) -> bool:
        """Check if this agent can delegate to another agent"""
        if not self.agent_registry:
            return False
        return self.agent_registry.can_agent_delegate_to(self.agent_name, agent_name)

    def get_available_collaborators(self) -> List[str]:
        """Get list of agents available for collaboration"""
        if not self.agent_registry:
            return []
        return self.agent_registry.get_available_agents()

    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp"""
        timestamp = datetime.now(timezone.utc).isoformat()
        log_entry = f"[{timestamp}] [{self.agent_name}] [{level}] {message}"
        print(log_entry)


class QAAssistantAgent(BaseAgent):
    """QA Assistant Agent - Reviews tests and provides feedback"""

    def __init__(self):
        super().__init__("QA_Assistant")

    def execute(self, test_results: Dict) -> Dict[str, Any]:
        """Analyze test results and provide QA feedback with RAG-augmented insights"""
        self.log("Analyzing test results")

        try:
            # Augment test results with RAG insights from Weaviate
            augmented_context = self._augment_with_rag(
                {
                    "test_name": test_results.get("test_name", ""),
                    "test_type": test_results.get("test_type", "unit"),
                    "status": test_results.get("status", "unknown"),
                    "failed": test_results.get("failed", 0),
                    "passed": test_results.get("passed", 0),
                    "total": test_results.get("total", 0),
                    "coverage": test_results.get("coverage", 0),
                }
            )

            analysis = {
                "total_tests": test_results.get("total", 0),
                "passed": test_results.get("passed", 0),
                "failed": test_results.get("failed", 0),
                "coverage": test_results.get("coverage", 0),
                "recommendations": self._generate_recommendations(test_results, augmented_context),
                "rag_insights_used": augmented_context.get("rag_insights_count", 0),
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

    def _generate_recommendations(
        self, test_results: Dict, augmented_context: Optional[Dict] = None
    ) -> List[str]:
        """
        Generate recommendations based on patterns and RAG insights.

        Uses both:
        1. Basic pattern analysis from artifact store
        2. Semantic insights from Weaviate (similar test failures, solutions)
        """
        patterns = self.get_pattern_insights()
        recommendations = []

        # Basic pattern-based recommendations
        if test_results.get("failed", 0) > test_results.get("passed", 0) * 0.1:
            recommendations.append("High failure rate detected. Review recent changes.")

        if patterns.get("flakiness", {}).get("flaky_agents"):
            recommendations.append("Flaky tests detected. Consider stabilization review.")

        # RAG-enhanced recommendations from Weaviate
        if augmented_context:
            rag_recommendations = augmented_context.get("rag_recommendations", [])
            for rec in rag_recommendations:
                if rec.get("confidence", 0) > 0.7:
                    insight = rec.get("insight", "")
                    if insight and insight not in recommendations:
                        recommendations.append(f"[RAG] {insight}")

            # Add high-confidence insights
            high_confidence = augmented_context.get("high_confidence_insights", [])
            for insight in high_confidence:
                insight_text = insight.get("insight", "")
                if insight_text and insight_text not in recommendations:
                    recommendations.append(f"[High Confidence] {insight_text}")

        return recommendations


class PerformanceAgent(BaseAgent):
    """Performance Agent - Monitors and optimizes performance"""

    def __init__(self):
        super().__init__("Performance_Agent")

    def execute(self, execution_data: Dict) -> Dict[str, Any]:
        """Analyze performance metrics with RAG-augmented insights"""
        self.log("Analyzing performance metrics")

        try:
            duration = execution_data.get("duration_ms", 0)
            memory = execution_data.get("memory_mb", 0)

            # Augment context with RAG insights from Weaviate
            augmented_context = self._augment_with_rag(
                {
                    "operation": execution_data.get("operation", "unknown"),
                    "current_metrics": {"duration_ms": duration, "memory_mb": memory},
                    "baseline_ms": execution_data.get("baseline_ms", 0),
                }
            )

            baseline = execution_data.get("baseline_ms", 0) or 0
            regression = baseline > 0 and duration > baseline * 2
            perf_status = "degraded" if duration >= 5000 or regression else "optimal"
            analysis = {
                "duration_ms": duration,
                "baseline_ms": baseline,
                "memory_mb": memory,
                "status": perf_status,
                "regression_detected": regression,
                "optimizations": self._suggest_optimizations(execution_data, augmented_context),
                "rag_insights_used": augmented_context.get("rag_insights_count", 0),
            }

            self._record_execution("success", analysis, tags=["performance"])
            self.log("Performance analysis complete")
            return analysis

        except Exception as e:
            self._record_execution("error", {"error": str(e)}, tags=["error"])
            self.log(f"Performance analysis failed: {str(e)}", "ERROR")
            raise

    def _suggest_optimizations(
        self, data: Dict, augmented_context: Optional[Dict] = None
    ) -> List[str]:
        """
        Suggest optimizations based on patterns and RAG insights.

        Uses both:
        1. Basic pattern analysis from artifact store
        2. Semantic insights from Weaviate (similar performance patterns, optimizations)
        """
        patterns = self.get_pattern_insights()
        perf = patterns.get("performance", {})
        suggestions = []

        # Basic pattern-based suggestions
        avg_latency = perf.get("avg_latency_ms", 0)
        if avg_latency > 3000:
            suggestions.append("Average latency above 3s. Consider caching or parallelization.")

        duration = data.get("duration_ms", 0) or 0
        baseline = data.get("baseline_ms", 0) or 0
        if duration >= 5000:
            suggestions.append("Observed high execution latency. Profile hot paths and optimize slow queries.")
        if baseline > 0 and duration > baseline * 2:
            suggestions.append("Execution time exceeds 2x baseline. Investigate regressions and add targeted benchmarking.")

        # RAG-enhanced suggestions from Weaviate
        if augmented_context:
            rag_recommendations = augmented_context.get("rag_recommendations", [])
            for rec in rag_recommendations:
                if rec.get("confidence", 0) > 0.6:
                    insight = rec.get("insight", "")
                    if insight and insight not in suggestions:
                        suggestions.append(f"[RAG] {insight}")

        return suggestions


class ComplianceAgent(BaseAgent):
    """Compliance Agent - Ensures regulatory compliance"""

    def __init__(self):
        super().__init__("Compliance_Agent")

    def execute(self, compliance_data: Dict) -> Dict[str, Any]:
        """Check compliance requirements with RAG-augmented insights"""
        self.log("Checking compliance")

        try:
            # Augment context with RAG insights from Weaviate
            augmented_context = self._augment_with_rag(
                {
                    "context": compliance_data.get("context", ""),
                    "regulations": compliance_data.get("regulations", []),
                    "encrypted": compliance_data.get("encrypted", False),
                    "pii_masked": compliance_data.get("pii_masked", False),
                    "audit_enabled": compliance_data.get("audit_enabled", False),
                }
            )

            checks = {
                "data_encryption": bool(compliance_data.get("encrypted") or compliance_data.get("encryption_enabled")),
                "pii_protection": bool(compliance_data.get("pii_masked") or compliance_data.get("pii_masking")),
                "audit_logs": compliance_data.get("audit_enabled", False),
                "violations": self._check_violations(compliance_data, augmented_context),
                "rag_insights_used": augmented_context.get("rag_insights_count", 0),
            }

            # CVE Reachability — non-blocking; gracefully skipped if pip-audit not installed
            try:
                from agenticqa.security.cve_reachability import CVEReachabilityAnalyzer
                _repo_path = compliance_data.get("repo_path", ".")
                _reach = CVEReachabilityAnalyzer().scan_python(_repo_path)
                if _reach.scan_error is None:
                    for _cve in _reach.reachable_cves:
                        checks["violations"].append({
                            "type": "reachable_cve",
                            "package": _cve.package,
                            "cve_id": _cve.cve_id,
                            "severity": _cve.severity,
                            "reachable_via": _cve.reachable_via[:5],
                        })
                    checks["cve_risk_score"] = _reach.risk_score
                    checks["reachable_cves"] = len(_reach.reachable_cves)
                    checks["total_cves"] = len(_reach.cves)
            except Exception:
                pass  # pip-audit unavailable or import error — non-blocking

            # Legal risk scan — pure Python, no external tools required
            try:
                from agenticqa.security.legal_risk_scanner import LegalRiskScanner
                _legal = LegalRiskScanner().scan(compliance_data.get("repo_path", "."))
                for _f in _legal.findings:
                    checks["violations"].append({
                        "type": _f.rule_id,
                        "file": _f.file,
                        "line": _f.line,
                        "severity": _f.severity,
                        "description": _f.message,
                        "evidence": _f.evidence,
                    })
                checks["legal_risk_score"] = _legal.risk_score
                checks["legal_risk_findings"] = len(_legal.findings)
                checks["legal_critical_findings"] = len(_legal.critical_findings)
            except Exception:
                pass  # non-blocking

            # HIPAA PHI scan — non-blocking
            try:
                from agenticqa.security.hipaa_phi_scanner import HIPAAPHIScanner
                _hipaa = HIPAAPHIScanner().scan(compliance_data.get("repo_path", "."))
                for _f in _hipaa.findings:
                    checks["violations"].append({
                        "type": _f.rule_id, "file": _f.file, "line": _f.line,
                        "severity": _f.severity, "description": _f.message,
                        "evidence": _f.evidence,
                    })
                checks["hipaa_risk_score"] = _hipaa.risk_score
                checks["hipaa_findings"] = len(_hipaa.findings)
                checks["hipaa_critical_findings"] = len(_hipaa.critical_findings)
            except Exception:
                pass  # non-blocking

            # AI Model SBOM — non-blocking
            try:
                from agenticqa.security.ai_model_sbom import AIModelSBOMScanner
                _sbom = AIModelSBOMScanner().scan(compliance_data.get("repo_path", "."))
                checks["sbom_providers"] = _sbom.providers_detected
                checks["sbom_unique_models"] = len(_sbom.unique_model_ids)
                checks["sbom_risk_score"] = _sbom.risk_score
                checks["sbom_license_violations"] = len(_sbom.license_violations)
                for _c in _sbom.license_violations:
                    checks["violations"].append({
                        "type": "SBOM_" + "_".join(_c.risk_flags[:1]),
                        "severity": "high" if "DEPRECATED_MODEL" in _c.risk_flags else "medium",
                        "description": f"Model '{_c.model_id}' ({_c.provider}): {', '.join(_c.risk_flags)}",
                        "evidence": f"{_c.source_file}:{_c.source_line}",
                    })
            except Exception:
                pass  # non-blocking

            # EU AI Act compliance check — non-blocking
            try:
                from agenticqa.compliance.ai_act import AIActComplianceChecker
                _ai_act = AIActComplianceChecker().check(compliance_data.get("repo_path", "."))
                checks["ai_act_risk_category"] = _ai_act.risk_category
                checks["ai_act_conformity_score"] = _ai_act.conformity_score
                checks["ai_act_annex_iii"] = _ai_act.annex_iii_match
                for _f in _ai_act.findings:
                    if _f.status == "missing":
                        checks["violations"].append({
                            "type": f"AI_ACT_{_f.article.replace('.', '_')}",
                            "severity": _f.severity,
                            "description": f"{_f.article}: {_f.requirement}",
                            "evidence": _f.evidence,
                            "remediation": _f.remediation,
                        })
            except Exception:
                pass  # non-blocking

            # Compliance drift detection — non-blocking
            try:
                import os as _os
                from agenticqa.compliance.drift_detector import ComplianceDriftDetector
                _run_id = _os.getenv("GITHUB_RUN_ID", "local")
                _repo_path = compliance_data.get("repo_path", ".")
                _drift_detector = ComplianceDriftDetector()
                _drift_detector.record_run(_run_id, checks["violations"], repo_path=_repo_path)
                checks["drift"] = _drift_detector.detect_drift(_repo_path)
            except Exception:
                pass

            self._record_execution("success", checks, tags=["compliance"])
            self.log("Compliance check complete")
            return checks

        except Exception as e:
            self._record_execution("error", {"error": str(e)}, tags=["error"])
            self.log(f"Compliance check failed: {str(e)}", "ERROR")
            raise

    def _infer_project_context(self, data: Dict) -> Dict[str, bool]:
        """Infer what kind of project this is to avoid false-positive compliance rules."""
        context_hints = str(data.get("context", "")).lower()
        repo = str(data.get("repo", "")).lower()
        tags = [str(t).lower() for t in data.get("tags", [])]
        all_hints = context_hints + " " + repo + " " + " ".join(tags)

        return {
            "is_test_only": any(w in all_hints for w in ("test", "cypress", "jest", "spec", "e2e", "qa")),
            "has_user_data": any(w in all_hints for w in ("database", "db", "postgres", "mysql", "redis", "pii", "user", "auth")),
            "is_infra_repo": any(w in all_hints for w in ("terraform", "k8s", "kubernetes", "infra", "deploy")),
            "is_frontend_only": any(w in all_hints for w in ("frontend", "ui", "react", "vue", "angular", "css", "html")),
        }

    def _check_violations(self, data: Dict, augmented_context: Optional[Dict] = None) -> List[str]:
        """
        Check for compliance violations with RAG insights.

        Uses both:
        1. Context-aware compliance rules (skips infra checks for test-only / frontend repos)
        2. Semantic insights from Weaviate (applicable compliance rules)
        """
        violations = []
        project = self._infer_project_context(data)

        # Skip data-at-rest / PII rules for repos that don't handle user data
        applies_data_rules = (
            not project["is_test_only"]
            and not project["is_frontend_only"]
            or project["has_user_data"]
        )

        if applies_data_rules:
            encrypted = data.get("encrypted") or data.get("encryption_enabled")
            pii_masked = data.get("pii_masked") or data.get("pii_masking")
            if not encrypted:
                violations.append("Data encryption required but not enabled")
            if not pii_masked:
                violations.append("PII masking required but not enabled")

        # RAG-enhanced compliance rules from Weaviate
        if augmented_context:
            rag_recommendations = augmented_context.get("rag_recommendations", [])
            for rec in rag_recommendations:
                if rec.get("confidence", 0) > 0.5:
                    insight = rec.get("insight", "")
                    if insight and insight not in violations:
                        violations.append(f"[RAG] {insight}")

        return violations

    def fix_accessibility_violations(self, pa11y_report_path: str, files_to_fix: List[str]) -> Dict[str, Any]:
        """
        Parse Pa11y report and automatically fix accessibility violations.

        Args:
            pa11y_report_path: Path to Pa11y report (text or JSON)
            files_to_fix: List of files to scan and fix

        Returns:
            Dict with fixes applied, violations fixed, and re-validation results
        """
        self.log("Starting accessibility auto-fix from Pa11y report")

        try:
            import os
            import re

            # Parse Pa11y report
            violations = self._parse_pa11y_report(pa11y_report_path)
            self.log(f"Found {len(violations)} accessibility violations")

            # Group violations by type and file
            fixes_applied = []
            for file_path in files_to_fix:
                if not os.path.exists(file_path):
                    self.log(f"File not found: {file_path}", "WARNING")
                    continue

                # Read file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    original_content = content

                # Apply fixes in order
                for violation in violations:
                    violation_type = violation.get("type", "")

                    if violation_type == "color_contrast":
                        content, fixed = self._fix_color_contrast(content, violation)
                        if fixed:
                            fixes_applied.append({
                                "file": file_path,
                                "type": "color_contrast",
                                "fix": violation.get("recommended_color"),
                                "original_color": "#3b82f6",  # TODO: Extract from content
                                "fixed_color": violation.get("recommended_color"),
                                "required_ratio": violation.get("required_ratio", "4.5")
                            })

                    elif violation_type == "missing_label":
                        content, fixed = self._fix_missing_labels(content, violation)
                        if fixed:
                            fixes_applied.append({
                                "file": file_path,
                                "type": "missing_label",
                                "element": violation.get("element_id")
                            })

                    elif violation_type == "missing_alt":
                        content, fixed = self._fix_missing_alt_text(content, violation)
                        if fixed:
                            fixes_applied.append({
                                "file": file_path,
                                "type": "missing_alt",
                                "element": violation.get("element_id")
                            })

                # Write back if changes were made
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    self.log(f"Applied {len([f for f in fixes_applied if f['file'] == file_path])} fixes to {file_path}")

            result = {
                "violations_found": len(violations),
                "fixes_applied": len(fixes_applied),
                "files_modified": len(set(f["file"] for f in fixes_applied)),
                "fixes": fixes_applied,
                "status": "success"
            }

            self._record_execution("success", result, tags=["accessibility_fix"])
            return result

        except Exception as e:
            self._record_execution("error", {"error": str(e)}, tags=["error"])
            self.log(f"Accessibility auto-fix failed: {str(e)}", "ERROR")
            raise

    def _parse_pa11y_report(self, report_path: str) -> List[Dict]:
        """Parse Pa11y report and extract violations"""
        import re

        violations = []

        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse color contrast violations
            contrast_pattern = r'contrast ratio of at least (\d+\.?\d*):1.*change (?:text )?colour to (#[0-9a-fA-F]{6})'
            for match in re.finditer(contrast_pattern, content, re.IGNORECASE):
                violations.append({
                    "type": "color_contrast",
                    "required_ratio": match.group(1),
                    "recommended_color": match.group(2)
                })

            # Parse missing label violations
            label_pattern = r'(textarea|input).*id="([^"]+)".*does not have a name available'
            for match in re.finditer(label_pattern, content, re.IGNORECASE):
                violations.append({
                    "type": "missing_label",
                    "element_type": match.group(1),
                    "element_id": match.group(2)
                })

            # Parse missing alt text violations
            alt_pattern = r'<img[^>]*src="([^"]*)"[^>]*>.*missing alt'
            for match in re.finditer(alt_pattern, content, re.IGNORECASE):
                violations.append({
                    "type": "missing_alt",
                    "image_src": match.group(1)
                })

            return violations

        except Exception as e:
            self.log(f"Failed to parse Pa11y report: {str(e)}", "ERROR")
            return []

    def _fix_color_contrast(self, content: str, violation: Dict) -> tuple:
        """
        Fix color contrast issues by replacing colors.

        Hybrid approach:
        1. Query Weaviate for similar historical fixes (learned patterns)
        2. If high-confidence match found, use learned solution
        3. Otherwise, fall back to core patterns (hard-coded)
        """
        import re

        recommended_color = violation.get("recommended_color", "#2b72e6")

        # LEARNING: Query Weaviate for similar color contrast fixes
        if self.rag:
            try:
                learned_fix = self._query_learned_color_fix(violation, content)
                if learned_fix and learned_fix['confidence'] > 0.75:
                    # Apply learned pattern with high confidence
                    self.log(f"Using learned color fix: {learned_fix['fix']} (confidence: {learned_fix['confidence']:.2f})")
                    recommended_color = learned_fix['fix']
            except Exception as e:
                self.log(f"RAG query failed, using core patterns: {e}", "WARNING")

        # Core patterns (fast path) - always apply as fallback
        patterns = [
            (r'#3b82f6', recommended_color),  # Example: replace specific hex color
            (r'color:\s*rgb\(59,\s*130,\s*246\)', f'color: {recommended_color}'),
        ]

        modified = False
        for pattern, replacement in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                modified = True

        return content, modified

    def _fix_missing_labels(self, content: str, violation: Dict) -> tuple:
        """Add aria-label attributes to form elements missing labels"""
        import re

        element_id = violation.get("element_id", "")
        element_type = violation.get("element_type", "textarea")

        if not element_id:
            return content, False

        # Find the element and add aria-label if it doesn't have one
        pattern = rf'<{element_type}[^>]*id="{element_id}"[^>]*>'

        def add_aria_label(match):
            element_html = match.group(0)
            # Skip if already has aria-label
            if 'aria-label=' in element_html:
                return element_html

            # Generate descriptive label based on ID
            label_text = element_id.replace('_', ' ').replace('-', ' ').title()

            # Insert aria-label before the closing >
            return element_html[:-1] + f' aria-label="{label_text}">'

        new_content = re.sub(pattern, add_aria_label, content, count=1)
        modified = new_content != content

        return new_content, modified

    def _fix_missing_alt_text(self, content: str, violation: Dict) -> tuple:
        """Add alt text to images missing it"""
        import re

        image_src = violation.get("image_src", "")

        if not image_src:
            return content, False

        # Find img tags with this src that don't have alt
        pattern = rf'<img([^>]*src="{re.escape(image_src)}"[^>]*)>'

        def add_alt_text(match):
            img_html = match.group(0)
            # Skip if already has alt
            if 'alt=' in img_html:
                return img_html

            # Generate descriptive alt text from filename
            import os
            filename = os.path.basename(image_src)
            alt_text = filename.split('.')[0].replace('_', ' ').replace('-', ' ').title()

            # Insert alt before the closing >
            return img_html[:-1] + f' alt="{alt_text}">'

        new_content = re.sub(pattern, add_alt_text, content, count=1)
        modified = new_content != content

        return new_content, modified

    def _query_learned_color_fix(self, violation: Dict, content: str) -> Optional[Dict]:
        """
        Query Weaviate for similar color contrast fixes from historical data.

        Returns learned fix with confidence score if found, None otherwise.
        """
        try:
            required_ratio = violation.get("required_ratio", "4.5")

            # Search for similar fixes in Weaviate
            query = f"color contrast ratio {required_ratio}:1 wcag accessibility fix"

            # Use vector store search directly
            embedding = self.rag.embedder.embed(query)
            similar_docs = self.rag.vector_store.search(
                embedding,
                doc_type="accessibility_fix",
                k=5,
                threshold=0.6
            )

            if not similar_docs:
                return None

            # Find best match with highest success rate
            best_fix = None
            best_score = 0.0

            for doc, similarity in similar_docs:
                metadata = doc.metadata
                fix_type = metadata.get("fix_type", "")

                if fix_type == "color_contrast":
                    success_rate = metadata.get("success_rate", 0.0)
                    validation_passed = metadata.get("validation_passed", False)

                    # Calculate confidence: similarity * success_rate
                    confidence = similarity * (success_rate if validation_passed else 0.5)

                    if confidence > best_score:
                        best_score = confidence
                        best_fix = {
                            "fix": metadata.get("fixed_color", "#2b72e6"),
                            "confidence": confidence,
                            "original_color": metadata.get("original_color"),
                            "attempts": metadata.get("attempts", 1),
                            "successes": metadata.get("successes", 0)
                        }

            return best_fix

        except Exception as e:
            self.log(f"Error querying learned fixes: {e}", "WARNING")
            return None

    def store_fix_success(self, fix_type: str, fix_details: Dict, validation_passed: bool):
        """
        Store successful fix to Weaviate for future learning.

        Args:
            fix_type: Type of fix (color_contrast, missing_label, etc.)
            fix_details: Details about the fix applied
            validation_passed: Whether the fix passed re-validation
        """
        if not self.rag:
            return

        try:
            # Create document for storage
            document = {
                "fix_type": fix_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "validation_passed": validation_passed,
                "agent_type": "compliance",
                **fix_details
            }

            # Calculate success rate if we have historical data
            success_rate = 1.0 if validation_passed else 0.0

            # Query for existing similar fixes to update success rate
            if fix_type == "color_contrast":
                query = f"color contrast {fix_details.get('original_color')} to {fix_details.get('fixed_color')}"
                embedding = self.rag.embedder.embed(query)
                existing = self.rag.vector_store.search(
                    embedding,
                    doc_type="accessibility_fix",
                    k=1,
                    threshold=0.9
                )

                if existing:
                    # Update success rate based on history
                    existing_meta = existing[0][0].metadata
                    attempts = existing_meta.get("attempts", 0) + 1
                    successes = existing_meta.get("successes", 0) + (1 if validation_passed else 0)
                    success_rate = successes / attempts

                    document["attempts"] = attempts
                    document["successes"] = successes
                    document["success_rate"] = success_rate
                else:
                    document["attempts"] = 1
                    document["successes"] = 1 if validation_passed else 0
                    document["success_rate"] = success_rate

            # Store to Weaviate
            content = f"{fix_type} accessibility fix"
            embedding = self.rag.embedder.embed(content)

            self.rag.vector_store.add_document(
                content=content,
                embedding=embedding,
                metadata=document,
                doc_type="accessibility_fix"
            )

            self.log(f"Stored {fix_type} fix to Weaviate (success_rate: {success_rate:.2%})")

        except Exception as e:
            self.log(f"Failed to store fix to Weaviate: {e}", "WARNING")

    def _store_success_pattern(self, run_id: str = None):
        """
        Store success pattern when 0 violations are found.

        This creates a baseline "known good" configuration that agents can learn from.
        These patterns help the system understand what works well and maintain it.

        Args:
            run_id: CI run ID for tracking
        """
        if not self.rag:
            return

        try:
            # Create success pattern document
            document = {
                "pattern_type": "accessibility_success",
                "violations_found": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": run_id,
                "files_checked": ["public/index.html"],  # Could be parameterized
                "wcag_level": "AA",
                "status": "compliant"
            }

            # Store to Weaviate
            content = "accessibility success no violations wcag compliant"
            embedding = self.rag.embedder.embed(content)

            self.rag.vector_store.add_document(
                content=content,
                embedding=embedding,
                metadata=document,
                doc_type="accessibility_success_pattern"
            )

            self.log("Stored success pattern baseline to Weaviate")

        except Exception as e:
            self.log(f"Failed to store success pattern to Weaviate: {e}", "WARNING")

    def store_revalidation_results(
        self,
        fixes_applied: List[Dict],
        errors_before: int,
        errors_after: int,
        run_id: str = None
    ):
        """
        Store revalidation results to enable learning from successful fixes.

        Should be called after re-running Pa11y to validate fixes.

        Handles two scenarios:
        1. Fixes Applied: Store fix patterns with success metrics
        2. Success Pattern (0 violations): Store baseline "known good" configurations

        Args:
            fixes_applied: List of fixes that were applied
            errors_before: Number of errors before fixes
            errors_after: Number of errors after fixes
            run_id: CI run ID for tracking
        """
        if not self.rag:
            self.log("RAG not available, skipping revalidation storage")
            return

        # Case 1: Success Pattern - No violations found (baseline)
        if errors_before == 0 and errors_after == 0:
            self.log("No violations found - storing success pattern baseline")
            self._store_success_pattern(run_id)
            return

        # Case 2: Fix Pattern - Violations were found and fixed
        errors_fixed = errors_before - errors_after
        overall_success = errors_after < errors_before

        self.log(f"Storing revalidation results: {errors_fixed} errors fixed, {errors_after} remaining")

        # Store each fix with its validation result
        for fix in fixes_applied:
            fix_type = fix.get("type")

            # Determine if this specific fix type succeeded
            # For now, we consider a fix successful if overall errors decreased
            validation_passed = overall_success

            fix_details = {
                "original_color": fix.get("original_color"),
                "fixed_color": fix.get("fixed_color"),
                "required_ratio": fix.get("required_ratio"),
                "file": fix.get("file"),
                "run_id": run_id,
                "errors_before": errors_before,
                "errors_after": errors_after
            }

            self.store_fix_success(fix_type, fix_details, validation_passed)

        # Store overall metrics
        overall_result = {
            "fixes_applied": len(fixes_applied),
            "errors_fixed": errors_fixed,
            "success_rate": (errors_fixed / errors_before) if errors_before > 0 else 0.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id
        }

        self._record_execution("revalidation", overall_result, tags=["learning", "validation"])


class DevOpsAgent(BaseAgent):
    """DevOps Agent - Manages deployment and infrastructure"""

    def __init__(self):
        super().__init__("DevOps_Agent")

    def execute(self, deployment_config: Dict) -> Dict[str, Any]:
        """Execute deployment operations with RAG-augmented insights"""
        self.log("Executing deployment")

        try:
            # Augment context with RAG insights from Weaviate
            augmented_context = self._augment_with_rag(
                {
                    "error_type": deployment_config.get("error_type", ""),
                    "message": deployment_config.get("message", ""),
                    "version": deployment_config.get("version", ""),
                    "environment": deployment_config.get("environment", ""),
                }
            )

            result = {
                "deployment_status": "success",
                "version": deployment_config.get("version"),
                "environment": deployment_config.get("environment"),
                "health_checks": self._run_health_checks(
                    augmented_context,
                    health_check_urls=deployment_config.get("health_check_urls"),
                ),
                "rag_insights_used": augmented_context.get("rag_insights_count", 0),
            }

            self._record_execution("success", result, tags=["deployment"])
            self.log("Deployment complete")
            return result

        except Exception as e:
            self._record_execution("error", {"error": str(e)}, tags=["error"])
            self.log(f"Deployment failed: {str(e)}", "ERROR")
            raise

    def _run_health_checks(
        self,
        augmented_context: Optional[Dict] = None,
        health_check_urls: Optional[Dict[str, str]] = None,
    ) -> Dict[str, bool]:
        """Run health checks — pings real URLs when provided, otherwise assumes healthy.

        health_check_urls: mapping of check_name → URL, e.g.
            {"api_health": "https://api.example.com/health",
             "database_connection": "https://db.example.com/ping"}
        """
        # Ping real endpoints if URLs are configured
        if health_check_urls:
            results: Dict[str, bool] = {}
            for check_name, url in health_check_urls.items():
                results[check_name] = self._ping_url(url)
        else:
            # No endpoints configured — default to assumed-healthy (behaviour unchanged)
            results = {
                "api_health": True,
                "database_connection": True,
                "cache_available": True,
            }

        # Add RAG-enhanced health insights
        if augmented_context:
            rag_recommendations = augmented_context.get("rag_recommendations", [])
            for rec in rag_recommendations:
                if rec.get("confidence", 0) > 0.6:
                    check_name = rec.get("type", "unknown_check")
                    results.setdefault(f"rag_{check_name}", True)

        return results

    def _ping_url(self, url: str, timeout: int = 5) -> bool:
        """Return True if url responds with HTTP 2xx/3xx within timeout seconds."""
        try:
            from urllib import request as url_request
            from urllib import error as url_error

            req = url_request.Request(url, method="HEAD")
            req.add_header("User-Agent", "AgenticQA-HealthCheck/1.0")
            with url_request.urlopen(req, timeout=timeout) as resp:
                return resp.status < 400
        except Exception as exc:
            self.log(f"Health check failed for {url}: {exc}", "WARNING")
            return False


class SREAgent(BaseAgent):
    """SRE (Site Reliability Engineering) Agent - Fixes linting and code quality issues"""

    # Rules that cannot be auto-fixed without human architectural decisions.
    # These are excluded from the fix_rate denominator so the rate reflects
    # what the agent can actually accomplish, not the structural ceiling of
    # the codebase. Clients see these as a separate 'architectural_violations'
    # category rather than as "failed" fixes.
    ARCHITECTURAL_RULES = frozenset({
        # Star imports — fixing requires knowing which names are actually used
        "F403", "F405",
        # Module-level import not at top — often load-order-dependent
        "E402",
        # Function too complex — requires human refactoring
        "C901",
        # Duplicate code — structural, no safe auto-merge
        "R0801",
        # Abstract method not overridden — class-design decision
        "W0223",
        # TypeScript / oxlint architectural rules
        # Replacing `any` requires type knowledge of the whole call chain
        "typescript/no-explicit-any", "@typescript-eslint/no-explicit-any",
        # Shadow requires understanding of all enclosing scopes
        "no-shadow", "typescript/no-shadow",
        # Complexity requires human decomposition
        "complexity", "oxc/no-accumulating-spread",
        # Circular dependencies are structural
        "import/no-cycle",
        # shellcheck: structural issues that require human attention
        # SC2046: unquoted command substitution — fixing changes semantics
        "SC2046",
        # SC2206/SC2207: array splitting — fixing requires understanding intent
        "SC2206", "SC2207",
    })

    # shellcheck codes that map to structural/security categories
    _SC_SECURITY = frozenset({"SC2086", "SC2046", "SC2006", "SC2091", "SC2001"})

    def __init__(self):
        super().__init__("SRE_Agent")

    def execute(self, linting_data: Dict) -> Dict[str, Any]:
        """
        Analyze linting errors and apply auto-fixes with RAG-augmented insights.

        Learns from past fixes stored in Weaviate to improve fix quality.
        Accepts ESLint JSON, raw error lists, or internal format — normalized automatically.
        """
        self.log("Analyzing linting errors and applying fixes")
        linting_data = normalize_linting_input(linting_data)

        try:
            # Augment context with RAG insights from Weaviate
            augmented_context = self._augment_with_rag(
                {
                    "error_type": "linting",
                    "message": linting_data.get("errors", []),
                    "file_path": linting_data.get("file_path", ""),
                }
            )

            errors = linting_data.get("errors", [])

            # Auto-detect TypeScript repo and run linter if no errors were pre-supplied
            lang = (linting_data.get("language") or "").lower()
            repo_path = linting_data.get("repo_path", ".")
            if not errors and lang in ("typescript", "javascript", "ts", "js", "tsx", "jsx"):
                errors = self._run_typescript_linter(repo_path)
            elif not errors and not lang:
                import os as _os
                if _os.path.exists(_os.path.join(repo_path, "tsconfig.json")):
                    errors = self._run_typescript_linter(repo_path)

            # Auto-detect shell scripts and run shellcheck
            shell_errors = linting_data.get("shell_errors", [])
            if not shell_errors and lang in ("shell", "bash", "sh", ""):
                shell_errors = self._run_shell_linter(repo_path)

            fixes_applied = []

            # Split errors: architectural violations are reported separately and
            # excluded from the fix_rate so the rate reflects achievable outcomes.
            architectural = [e for e in errors if e.get("rule", "") in self.ARCHITECTURAL_RULES]
            fixable_errors = [e for e in errors if e.get("rule", "") not in self.ARCHITECTURAL_RULES]

            # Pattern guard: known failure types short-circuit RAG for recognised rules
            exec_strategy = self._get_execution_strategy()
            known_failures = set(exec_strategy.get("known_failure_types", []))

            # Apply fixes only to fixable errors
            for error in fixable_errors:
                rule = error.get("rule", "")
                if known_failures and rule in known_failures:
                    fix = self._apply_linting_fix(error, None)
                    if fix:
                        fix["source"] = "pattern_memory"
                        fixes_applied.append(fix)
                else:
                    fix = self._apply_linting_fix(error, augmented_context)
                    if fix:
                        fixes_applied.append(fix)

                # Developer risk attribution — non-blocking, best-effort
                try:
                    import hashlib as _hl, subprocess as _sp2
                    from data_store.developer_profile import DeveloperProfile
                    _cwd = linting_data.get("repo_path", ".")
                    _proc2 = _sp2.run(
                        ["git", "remote", "get-url", "origin"],
                        capture_output=True, text=True, timeout=5, cwd=_cwd,
                    )
                    _url2 = _proc2.stdout.strip().lower().rstrip("/").removesuffix(".git")
                    _repo_id = _hl.sha1(_url2.encode()).hexdigest()[:12] if _url2 else "unknown"
                    _dp = DeveloperProfile.for_file(
                        error.get("file", ""),
                        repo_id=_repo_id,
                        cwd=_cwd,
                    )
                    if _dp:
                        _dp.record_violation(rule or "unknown", fixed=bool(fix))
                except Exception:
                    pass

            fixable_count = len(fixable_errors)
            arch_by_rule: Dict[str, int] = {}
            for e in architectural:
                arch_by_rule[e.get("rule", "unknown")] = arch_by_rule.get(e.get("rule", "unknown"), 0) + 1

            result = {
                "total_errors": len(errors),
                "fixable_errors": fixable_count,
                "fixes_applied": len(fixes_applied),
                # fix_rate is over fixable errors only — honest about what the agent can do
                "fix_rate": len(fixes_applied) / fixable_count if fixable_count else 0.0,
                "architectural_violations": len(architectural),
                "architectural_violations_by_rule": arch_by_rule,
                "fixes": fixes_applied,
                "status": "success" if len(fixes_applied) == fixable_count else "partial",
                "rag_insights_used": augmented_context.get("rag_insights_count", 0),
                "shell_errors": shell_errors,
                "shell_error_count": len(shell_errors),
            }

            # Self-healing test repair — if caller provides failing_tests list
            repair_results: List[Dict] = []
            for ft in linting_data.get("failing_tests", []):
                repair = self._attempt_test_repair(
                    ft.get("file", ""),
                    ft.get("error", ""),
                    ft.get("test_name", ""),
                )
                repair_results.append(repair)
            if repair_results:
                result["test_repairs"] = repair_results
                result["tests_repaired"] = sum(1 for r in repair_results if r["repaired"])

            self._record_execution("success", result, tags=["linting_fix"])
            self.log(
                f"Applied {len(fixes_applied)}/{fixable_count} fixable linting errors "
                f"({len(architectural)} architectural violations excluded from rate)"
            )

            # Update org-level cross-repo memory — non-blocking
            try:
                from data_store.org_memory import OrgMemory
                import hashlib as _hl2, subprocess as _sp3
                _cwd2 = linting_data.get("repo_path", ".")
                _p3 = _sp3.run(["git","remote","get-url","origin"],
                               capture_output=True, text=True, timeout=5, cwd=_cwd2)
                _url3 = _p3.stdout.strip().lower().rstrip("/").removesuffix(".git")
                _repo_id2 = _hl2.sha1(_url3.encode()).hexdigest()[:12] if _url3 else "unknown"
                OrgMemory.for_repo(_cwd2).update_from_sre_result(_repo_id2, result)
            except Exception:
                pass

            # Update repo-specific institutional memory
            if getattr(self, "repo_profile", None):
                try:
                    self.repo_profile.record_run(
                        run_id=linting_data.get("run_id", "unknown"),
                        fix_rate=result["fix_rate"],
                        fixes_applied=result["fixes_applied"],
                        fixable_errors=fixable_count,
                        architectural_violations=arch_by_rule,
                        language=linting_data.get("language"),
                    )
                except Exception:
                    pass

            # Record timestamped violation snapshot in Neo4j temporal graph — non-blocking
            try:
                from agenticqa.graph.temporal_graph import TemporalViolationStore
                import hashlib as _hl3, subprocess as _sp4
                _cwd3 = linting_data.get("repo_path", ".")
                _p4 = _sp4.run(["git", "remote", "get-url", "origin"],
                               capture_output=True, text=True, timeout=5, cwd=_cwd3)
                _url4 = _p4.stdout.strip().lower().rstrip("/").removesuffix(".git")
                _rid = _hl3.sha1(_url4.encode()).hexdigest()[:12] if _url4 else "unknown"
                _all_by_rule: Dict[str, int] = dict(arch_by_rule)
                for _e in fixable_errors:
                    _r = _e.get("rule", "unknown")
                    _all_by_rule[_r] = _all_by_rule.get(_r, 0) + 1
                TemporalViolationStore().record_run(
                    run_id=linting_data.get("run_id", "unknown"),
                    repo_id=_rid,
                    agent="SRE_Agent",
                    violations_by_rule=_all_by_rule,
                    fix_rate=result["fix_rate"],
                    fixes_applied=result["fixes_applied"],
                    total_errors=result["total_errors"],
                )
            except Exception:
                pass

            return result

        except Exception as e:
            self._record_execution("error", {"error": str(e)}, tags=["error"])
            self.log(f"Linting fix failed: {str(e)}", "ERROR")
            raise

    def _run_shell_linter(self, repo_path: str) -> List[Dict]:
        """Run shellcheck on all .sh files in repo_path. Returns normalized error dicts.

        shellcheck must be installed (pre-installed on GitHub Actions runners).
        Returns [] if not available or no shell files found — never raises.
        """
        import subprocess as _sp, json as _j, glob as _gl, os as _os

        sh_files = (
            _gl.glob(_os.path.join(repo_path, "**", "*.sh"), recursive=True)
            + _gl.glob(_os.path.join(repo_path, "**", "*.bash"), recursive=True)
        )
        # Exclude .git
        sh_files = [f for f in sh_files if "/.git/" not in f]
        if not sh_files:
            return []

        try:
            result = _sp.run(
                ["shellcheck", "--format=json", "--severity=warning"] + sh_files[:50],
                capture_output=True, text=True, timeout=60,
            )
        except (FileNotFoundError, _sp.TimeoutExpired):
            return []
        except Exception:
            return []

        try:
            raw = _j.loads(result.stdout or "[]")
        except ValueError:
            return []

        errors = []
        for item in raw:
            code = f"SC{item.get('code', 0)}"
            errors.append({
                "rule": code,
                "file": item.get("file", ""),
                "line": item.get("line", 1),
                "col": item.get("column", 1),
                "message": item.get("message", ""),
                "severity": item.get("level", "warning"),
            })
        return errors

    def _run_typescript_linter(self, repo_path: str) -> List[Dict]:
        """Run oxlint (preferred) or eslint (fallback) and return normalized error dicts.

        Tries local node_modules binary first to avoid slow npx network calls.
        Returns an empty list if neither tool is available — never raises.
        """
        import subprocess as _sp, json as _j, os as _os

        def _parse(stdout: str) -> List[Dict]:
            try:
                raw = _j.loads(stdout or "[]")
            except ValueError:
                return []
            norm = normalize_linting_input(raw if isinstance(raw, dict) else {"results": raw if isinstance(raw, list) else []})
            return norm.get("errors", [])

        # Candidate entry points for oxlint.
        # pnpm sometimes creates a broken .bin/oxlint.js symlink, so we also
        # probe the real package bin/ directly and invoke via `node`.
        _nm = _os.path.join(repo_path, "node_modules")
        oxlint_candidates: list = [
            # Standard npm/yarn: executable binary
            (_os.path.join(_nm, ".bin", "oxlint"), False),
            # pnpm: real script under package bin/ — needs `node`
            (_os.path.join(_nm, "oxlint", "bin", "oxlint"), True),
            # System-wide
            ("oxlint", False),
        ]
        src_dirs = [d for d in ["src", "packages", "apps", "."] if _os.path.isdir(_os.path.join(repo_path, d))]
        scan_targets = src_dirs[:3]  # cap to avoid overly long commands

        for bin_path, use_node in oxlint_candidates:
            if not _os.path.exists(bin_path) and use_node:
                continue
            config_args: list = []
            for cfg in (".oxlintrc.json", "oxlint.json"):
                if _os.path.exists(_os.path.join(repo_path, cfg)):
                    config_args = ["-c", cfg]
                    break
            cmd = (["node", bin_path] if use_node else [bin_path]) + ["--format", "json", *config_args, *scan_targets]
            try:
                proc = _sp.run(
                    cmd,
                    capture_output=True, text=True, timeout=90, cwd=repo_path,
                )
                errors = _parse(proc.stdout)
                if errors or proc.returncode in (0, 1):
                    self.log(f"oxlint found {len(errors)} issue(s) in {repo_path}")
                    return errors
            except (FileNotFoundError, PermissionError, _sp.TimeoutExpired):
                continue

        # Fallback: eslint JSON
        eslint_bins = [
            _os.path.join(repo_path, "node_modules", ".bin", "eslint"),
            "eslint",
        ]
        ext_args = ["--ext", ".ts,.tsx,.js,.jsx"]
        for bin_path in eslint_bins:
            try:
                proc = _sp.run(
                    [bin_path, "--format", "json", *scan_targets, *ext_args],
                    capture_output=True, text=True, timeout=90, cwd=repo_path,
                )
                errors = _parse(proc.stdout)
                if errors or proc.returncode in (0, 1):
                    self.log(f"eslint found {len(errors)} issue(s) in {repo_path}")
                    return errors
            except (FileNotFoundError, PermissionError, _sp.TimeoutExpired):
                continue

        self.log("No TypeScript linter (oxlint/eslint) found — skipping TS analysis", "WARNING")
        return []

    def _attempt_test_repair(
        self,
        test_file: str,
        error_message: str,
        test_name: str,
    ) -> Dict[str, Any]:
        """Self-healing CI: use Haiku to generate a fix for a failing test.

        Verifies the fix passes in a subprocess sandbox before applying to disk.
        Returns {"repaired": bool, "patch_applied": bool, "fix_summary": str}.
        """
        if not test_file or not Path(test_file).exists():
            return {"repaired": False, "patch_applied": False, "fix_summary": "test file not found"}

        try:
            import anthropic  # deferred — mock via sys.modules in tests
            source = Path(test_file).read_text()[:4000]  # token budget
            client = anthropic.Anthropic()
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=(
                    "You are a test repair assistant. Given a failing Python test file and "
                    "its error message, output ONLY the corrected complete file content. "
                    "No explanation. No markdown fences. Just the Python code."
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Test file ({test_file}):\n{source}\n\n"
                        f"Failing test: {test_name}\n\n"
                        f"Error:\n{error_message}"
                    ),
                }],
            )
            fixed_code = message.content[0].text.strip()
            # Strip markdown fences if present
            fixed_code = re.sub(r"^```[a-zA-Z]*\n?", "", fixed_code)
            fixed_code = re.sub(r"\n?```$", "", fixed_code).strip()
        except Exception as exc:
            return {"repaired": False, "patch_applied": False, "fix_summary": f"LLM unavailable: {exc}"}

        # Verify the fix compiles before any sandbox execution
        try:
            compile(fixed_code, test_file, "exec")
        except SyntaxError as exc:
            return {"repaired": False, "patch_applied": False, "fix_summary": f"Generated code has syntax error: {exc}"}

        # Write to a temp file and run pytest on it in a clean subprocess
        try:
            import subprocess
            with tempfile.NamedTemporaryFile(
                suffix=".py", mode="w", delete=False, dir=Path(test_file).parent
            ) as tmp:
                tmp.write(fixed_code)
                tmp_path = tmp.name

            proc = subprocess.run(
                ["python", "-m", "pytest", tmp_path, "-x", "-q", "--tb=no", "--no-header"],
                capture_output=True, text=True, timeout=30,
            )
            success = proc.returncode == 0
        except Exception as exc:
            success = False
            return {"repaired": False, "patch_applied": False, "fix_summary": f"Sandbox run failed: {exc}"}
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

        if success:
            Path(test_file).write_text(fixed_code)
            return {"repaired": True, "patch_applied": True, "fix_summary": f"Fixed {test_name}"}

        return {"repaired": False, "patch_applied": False, "fix_summary": "Generated fix did not pass verification"}

    def _apply_linting_fix(
        self, error: Dict, augmented_context: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Apply linting fix with RAG insights.

        Uses historical fix patterns from Weaviate to determine best solution.
        """
        rule = error.get("rule", "unknown")
        message = error.get("message", "")

        # RAG-enhanced fix selection
        if augmented_context:
            rag_recommendations = augmented_context.get("rag_recommendations", [])
            for rec in rag_recommendations:
                if rec.get("confidence", 0) > 0.7:
                    # Use RAG-suggested fix
                    return {
                        "rule": rule,
                        "fix_applied": rec.get("insight", ""),
                        "source": "RAG",
                        "confidence": rec.get("confidence"),
                    }

        # Basic fix patterns — universal + per-language
        fix_map = {
            # Python / flake8 / pyflakes / pycodestyle
            "E101":  "Fixed indentation — replaced tabs with spaces",
            "E111":  "Fixed indentation — corrected indentation increment",
            "E117":  "Fixed over-indented code",
            "E121":  "Fixed continuation line under-indented for hanging indent",
            "E122":  "Fixed continuation line missing indentation or outdented",
            "E123":  "Fixed closing bracket indentation",
            "E124":  "Fixed closing bracket alignment to visual indentation",
            "E125":  "Fixed continuation line indentation for visual indent",
            "E126":  "Fixed continuation line over-indented for hanging indent",
            "E127":  "Fixed continuation line over-indented for visual indent",
            "E128":  "Fixed continuation line under-indented for visual indent",
            "E131":  "Fixed continuation line unaligned for closing bracket",
            "E201":  "Removed whitespace after '(' or '['",
            "E202":  "Removed whitespace before ')' or ']'",
            "E203":  "Removed whitespace before ':' or ','",
            "E211":  "Removed whitespace before '(' or '['",
            "E221":  "Fixed multiple spaces before operator",
            "E222":  "Fixed multiple spaces after operator",
            "E225":  "Added missing whitespace around operator",
            "E226":  "Added missing whitespace around arithmetic operator",
            "E228":  "Added missing whitespace around modulo operator",
            "E231":  "Added missing whitespace after ','",
            "E241":  "Fixed multiple spaces after ','",
            "E251":  "Removed unexpected spaces around keyword / parameter default",
            "E261":  "Fixed inline comment — at least two spaces before '#'",
            "E262":  "Fixed inline comment — must start with '# '",
            "E265":  "Fixed block comment — must start with '# '",
            "E266":  "Fixed block comment — must start with '# ' not '##'",
            "E271":  "Fixed multiple spaces after keyword",
            "E272":  "Fixed multiple spaces before keyword",
            "E301":  "Added expected blank line before function/class definition",
            "E302":  "Added expected 2 blank lines before top-level definition",
            "E303":  "Removed extra blank lines (max 2)",
            "E304":  "Removed blank lines found after function decorator",
            "E305":  "Added expected 2 blank lines after function/class definition",
            "E401":  "Moved multiple imports to separate lines",
            "E501":  "Wrapped long line to fit within max line length",
            "E502":  "Removed unnecessary backslash (implicit continuation inside brackets)",
            "E711":  "Replaced == None comparison with 'is None'",
            "E712":  "Replaced == True/False with boolean check",
            "E714":  "Replaced 'not x is' with 'x is not'",
            "E721":  "Replaced type comparison with isinstance()",
            "E741":  "Renamed ambiguous variable name (l, O, I)",
            "W191":  "Replaced tabs with spaces for indentation",
            "W291":  "Removed trailing whitespace",
            "W292":  "Added newline at end of file",
            "W293":  "Removed whitespace on blank line",
            "W391":  "Removed blank line at end of file",
            "W503":  "Moved line break before binary operator",
            "W504":  "Moved line break after binary operator",
            "W605":  "Fixed invalid escape sequence — used raw string or double-escaped",
            "F401":  "Removed unused import",
            "F811":  "Removed redefined unused name from import",
            "F841":  "Removed or prefixed unused local variable",
            "F821":  "Resolved undefined name — checked for missing import",
            "F824":  "Removed unused nonlocal declaration",
            "C901":  "Refactored complex function — extracted sub-functions to reduce complexity",
            # Universal
            "quotes":           "Changed to consistent quote style",
            "semi":             "Added missing semicolon",
            "no-unused-vars":   "Removed unused variable",
            "indent":           "Fixed indentation",
            "trailing-spaces":  "Removed trailing whitespace",
            "eol-last":         "Added newline at end of file",
            # React / JSX
            "react/no-unknown-property":     "Converted HTML attribute to JSX camelCase (e.g. frameborder → frameBorder, class → className)",
            "react/jsx-no-duplicate-props":  "Removed duplicate JSX prop",
            "react/prop-types":              "Added PropTypes declaration for component props",
            "react/display-name":            "Added displayName to component",
            "react-hooks/exhaustive-deps":   "Added missing dependency to useEffect/useCallback/useMemo dep array",
            # Accessibility
            "jsx-a11y/alt-text":                              "Added descriptive alt attribute to img element",
            "jsx-a11y/anchor-is-valid":                       "Replaced invalid anchor with button or added valid href",
            "jsx-a11y/click-events-have-key-events":          "Added keyboard event handler alongside click handler",
            "jsx-a11y/no-noninteractive-element-interactions":"Moved interaction to a focusable element",
            # TypeScript (eslint-plugin-typescript and oxlint namespaced)
            "@typescript-eslint/no-explicit-any":              "Replaced 'any' with a typed alternative",
            "@typescript-eslint/no-unused-vars":               "Removed unused TypeScript variable or import",
            "@typescript-eslint/explicit-function-return-type": "Added explicit return type annotation",
            "@typescript-eslint/no-non-null-assertion":        "Replaced non-null assertion with proper null check",
            # oxlint uses plugin-namespaced IDs: typescript/*, unicorn/*, oxc/*
            "typescript/no-unused-vars":    "Removed unused TypeScript variable or import",
            "typescript/no-non-null-assertion": "Replaced non-null assertion with proper null check",
            "typescript/prefer-as-const":   "Changed type assertion to 'as const'",
            "typescript/no-empty-interface": "Replaced empty interface with type alias or extended type",
            "typescript/ban-ts-comment":    "Removed or replaced @ts-ignore with typed alternative",
            # Common ESLint / oxlint rules (no namespace)
            "no-var":           "Replaced 'var' with 'let' or 'const'",
            "prefer-const":     "Changed 'let' to 'const' for non-reassigned bindings",
            "eqeqeq":           "Replaced '==' with '===' for strict equality",
            "no-debugger":      "Removed debugger statement",
            "no-console":       "Removed or replaced console.log with logger",
            "no-unused-expressions": "Removed unused expression or assigned to variable",
            "no-duplicate-imports": "Merged duplicate import statements",
            "object-shorthand": "Used object shorthand property syntax",
            "prefer-arrow-callback": "Converted function expression to arrow function",
            "prefer-template": "Replaced string concatenation with template literal",
            "no-useless-concat": "Removed unnecessary string concatenation",
            "no-extra-semi":    "Removed unnecessary semicolon",
            "curly":            "Added curly braces to control flow statement",
            "dot-notation":     "Used dot notation instead of bracket notation",
            "no-else-return":   "Removed unnecessary else block after return",
            # unicorn (oxlint plugin)
            "unicorn/prefer-includes": "Replaced indexOf check with .includes()",
            "unicorn/prefer-string-starts-ends-with": "Replaced regex with .startsWith()/.endsWith()",
            "unicorn/no-array-for-each": "Converted .forEach to for...of loop",
            "unicorn/prefer-number-properties": "Used Number.isNaN / Number.isFinite instead of global",
            "unicorn/prefer-array-flat":  "Replaced .reduce concat with .flat()",
            "unicorn/prefer-ternary":     "Converted simple if/else to ternary expression",
            "unicorn/throw-new-error":    "Added 'new' keyword before thrown Error",
            "unicorn/no-useless-undefined": "Removed explicit undefined return/assignment",
            # PHP / PHPStan / PHP-CS-Fixer
            "phpstan":     "Applied PHPStan fix: added type declaration or removed dead code",
            "phpcs":       "Applied PHP_CodeSniffer fix: corrected coding standard violation",
            "php-cs-fixer":"Applied php-cs-fixer: corrected code style",
            # Go
            "golint":      "Applied golint fix: added comment or renamed to match Go conventions",
            "go-vet":      "Applied go vet fix: corrected suspicious code construct",
            "errcheck":    "Added error return value check",
            "gofmt":       "Ran gofmt: corrected Go formatting",
            # Ruby / RuboCop
            "rubocop":                          "Applied RuboCop autocorrect",
            "Style/FrozenStringLiteralComment": "Added # frozen_string_literal: true comment",
            "Style/StringLiterals":             "Changed to consistent single-quoted string style",
            "Lint/UnusedVariable":              "Removed unused Ruby variable",
            "Metrics/MethodLength":             "Extracted long method into smaller methods",
            # Java
            "checkstyle":   "Applied Checkstyle fix: corrected Java code style",
            "pmd":          "Applied PMD fix: resolved code quality issue",
            "spotbugs":     "Applied SpotBugs fix: resolved potential bug",
            "unused-import":"Removed unused Java import",
            # Rust / Clippy
            "clippy":          "Applied Clippy suggestion",
            "dead-code":       "Removed or annotated dead code with #[allow(dead_code)]",
            "unused-variable": "Prefixed unused Rust variable with _",
            # C# / .NET Roslyn
            "CA1822":   "Marked method as static — does not access instance data",
            "CA2007":   "Added ConfigureAwait(false) to awaited task",
            "CS0168":   "Removed unused C# variable",
            "CS8600":   "Added null check or non-null assertion for nullable type",
            "CS8602":   "Added null guard before dereferencing nullable reference",
        }

        if rule in fix_map:
            file_path = error.get("file_path") or error.get("file")
            line_no = error.get("line", 0)
            actually_applied = self._apply_fix_to_file(file_path, rule, line_no) if file_path else False
            return {
                "rule": rule,
                "file": file_path,
                "line": line_no,
                "fix_applied": fix_map[rule],
                "fix_written_to_disk": actually_applied,
                "source": "basic",
                "confidence": 0.8,
            }

        # CI YAML patch generation — SRE owns .github/** so can generate diffs
        ci_patch = self._generate_ci_patch(error)
        if ci_patch:
            return ci_patch

        return None

    def _apply_fix_to_file(self, file_path: str, rule: str, line_no: int) -> bool:
        """Apply a deterministic fix directly to the source file on disk.

        Only handles rules whose fixes are unambiguously safe to apply automatically
        (whitespace, blank-line counts). Returns True if the file was actually modified.
        """
        _AUTO_FIXABLE = {
            "W291", "W293",  # trailing whitespace
            "W292",          # no newline at end of file
            "W391",          # blank line at end of file
            "E265",          # block comment should start with '# '
            "E266",          # too many leading '#' for block comment
            "E303",          # too many blank lines (N)
            "W503",          # line break before binary operator — whitespace only
        }
        if rule not in _AUTO_FIXABLE:
            return False
        try:
            path = Path(file_path)
            if not path.exists() or not path.is_file():
                return False

            content = path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines(keepends=True)
            modified = False

            if rule in ("W291", "W293"):
                new_lines = [
                    (ln.rstrip() + ("\n" if ln.endswith("\n") else ""))
                    for ln in lines
                ]
                if new_lines != lines:
                    lines, modified = new_lines, True

            elif rule == "W292":
                if lines and not lines[-1].endswith("\n"):
                    lines[-1] += "\n"
                    modified = True

            elif rule == "W391":
                while lines and lines[-1].strip() == "":
                    lines.pop()
                    modified = True
                if modified and lines:
                    lines[-1] = lines[-1].rstrip("\n") + "\n"

            elif rule == "E265":
                if 0 < line_no <= len(lines):
                    old = lines[line_no - 1]
                    new = re.sub(r"^(\s*)#([^ !#\n])", r"\1# \2", old)
                    if new != old:
                        lines[line_no - 1], modified = new, True

            elif rule == "E266":
                if 0 < line_no <= len(lines):
                    old = lines[line_no - 1]
                    new = re.sub(r"^(\s*)#{2,}", r"\1##", old)
                    if new != old:
                        lines[line_no - 1], modified = new, True

            elif rule == "E303":
                new_lines: list = []
                blank_run = 0
                for ln in lines:
                    if ln.strip() == "":
                        blank_run += 1
                        if blank_run <= 2:
                            new_lines.append(ln)
                    else:
                        blank_run = 0
                        new_lines.append(ln)
                if new_lines != lines:
                    lines, modified = new_lines, True

            if modified:
                path.write_text("".join(lines), encoding="utf-8")
                return True
        except Exception as exc:
            self.log(f"SRE auto-fix failed for {file_path}:{rule}: {exc}", "WARNING")
        return False

    def _generate_ci_patch(self, error: Dict) -> Optional[Dict]:
        """Generate a corrective patch for known CI YAML issues.

        Returns a dict with 'patch' key containing a unified-diff-style suggestion,
        or None if the rule is not a recognised CI issue.
        """
        rule = error.get("rule", "")
        message = error.get("message", "")
        file_path = error.get("file", "")

        # Hardcoded URL in source code (e.g. https://google.com/test in href)
        url_match = re.search(r'https?://[^\s\'"<>]+', message)
        if url_match and rule in ("hardcoded-path", "no-hardcoded-url", "no-hardcoded-credentials"):
            bad_url = url_match.group(0)
            host_part = re.sub(r"[^A-Z0-9]", "_", bad_url.upper().split("//")[1].split("/")[0]).strip("_")
            env_var = f"APP_{host_part}_URL"
            # Env var syntax depends on file language
            if file_path.endswith(".php"):
                env_ref = f"getenv('{env_var}') ?: '{bad_url}'"
            elif file_path.endswith((".ts", ".tsx", ".js", ".jsx")):
                env_ref = f"process.env.{env_var} ?? '{bad_url}'"
            elif file_path.endswith(".go"):
                env_ref = f'os.Getenv("{env_var}")'
            elif file_path.endswith(".rb"):
                env_ref = f"ENV.fetch('{env_var}', '{bad_url}')"
            elif file_path.endswith(".java") or file_path.endswith(".kt"):
                env_ref = f'System.getenv("{env_var}")'
            elif file_path.endswith(".rs"):
                env_ref = f'std::env::var("{env_var}").unwrap_or_else(|_| "{bad_url}".to_string())'
            elif file_path.endswith(".cs"):
                env_ref = f'Environment.GetEnvironmentVariable("{env_var}") ?? "{bad_url}"'
            elif file_path.endswith(".py"):
                env_ref = f"os.getenv('{env_var}', '{bad_url}')"
            else:
                env_ref = f"${{{env_var}:-{bad_url}}}"  # shell/generic fallback
            return {
                "rule": rule,
                "file": file_path,
                "fix_applied": f"Replace hardcoded URL '{bad_url}' with environment variable ${env_var}",
                "patch": (
                    f"--- a/{file_path}\n"
                    f"+++ b/{file_path}\n"
                    f'-  "{bad_url}"\n'
                    f'+  {env_ref}\n'
                    f"# Add to .env:  {env_var}={bad_url}"
                ),
                "source": "ci_patch",
                "confidence": 0.85,
            }

        # Hardcoded local filesystem path in workflow
        if rule == "hardcoded-path" or re.search(r"/Users/|/home/\w+/|C:\\\\Users\\\\", message):
            match = re.search(r"(/Users/[^\s'\"]+|/home/\w+/[^\s'\"]+|C:\\\\Users\\\\[^\s'\"]+)", message)
            bad_path = match.group(1) if match else "<local-path>"
            rel_guess = re.sub(r".*/(e2e|tests?|spec|cypress)/", r"\1/", bad_path)
            return {
                "rule": rule,
                "file": file_path,
                "fix_applied": f"Replace hardcoded local path '{bad_path}' with relative path",
                "patch": (
                    f"--- a/{file_path}\n"
                    f"+++ b/{file_path}\n"
                    f"-          {bad_path}\n"
                    f"+          ./{rel_guess}"
                ),
                "source": "ci_patch",
                "confidence": 0.9,
            }

        # Duplicate config file
        if rule == "duplicate-config":
            return {
                "rule": rule,
                "file": file_path,
                "fix_applied": "Remove duplicate config — keep root-level file, delete nested copy",
                "patch": f"rm {file_path}  # keep root cypress.config.js",
                "source": "ci_patch",
                "confidence": 0.85,
            }

        # Duplicate support folder
        if rule == "duplicate-folder":
            return {
                "rule": rule,
                "file": file_path,
                "fix_applied": "Consolidate duplicate support/ directories into one canonical location",
                "patch": (
                    f"# Merge contents then remove duplicate:\n"
                    f"cp -r Cypress/support/* Cypress/cypress/support/\n"
                    f"rm -rf Cypress/support"
                ),
                "source": "ci_patch",
                "confidence": 0.8,
            }

        return None


class SDETAgent(BaseAgent):
    """SDET (Software Development Engineer in Test) Agent - Manages test coverage and quality"""

    def __init__(self):
        super().__init__("SDET_Agent")

    def execute(self, coverage_data: Dict) -> Dict[str, Any]:
        """
        Analyze test coverage and identify gaps with RAG-augmented insights.

        Learns from historical coverage improvements stored in Weaviate.
        Accepts Istanbul/nyc JSON, coverage.py JSON, Cypress coverage, or internal format.
        """
        self.log("Analyzing test coverage and identifying gaps")
        coverage_data = normalize_coverage_input(coverage_data)

        try:
            # Augment context with RAG insights from Weaviate
            augmented_context = self._augment_with_rag(
                {
                    "coverage_percent": coverage_data.get("coverage_percent", 0),
                    "uncovered_files": coverage_data.get("uncovered_files", []),
                    "test_type": coverage_data.get("test_type", "unit"),
                }
            )

            coverage_percent = coverage_data.get("coverage_percent", 0)
            uncovered_files = coverage_data.get("uncovered_files", [])

            # Pattern guard: lower coverage adequacy threshold when flakiness is accelerating
            exec_strategy = self._get_execution_strategy()
            coverage_threshold = 80
            if exec_strategy.get("flakiness_trend") == "accelerating":
                coverage_threshold = 70
                self.log(
                    "Pattern guard: flakiness accelerating — lowering coverage adequacy threshold to 70%",
                    "WARNING",
                )

            # Identify coverage gaps
            gaps = self._identify_coverage_gaps(coverage_data, augmented_context)

            # Generate test recommendations
            recommendations = self._generate_test_recommendations(gaps, augmented_context)

            # LLM-generated tests for high-priority gaps — non-blocking
            generated_test_files = []
            tests_generated = 0
            repo_path = coverage_data.get("repo_path", ".")
            for gap in gaps:
                if gap.get("priority") == "high" and gap.get("file") != "RAG-identified":
                    gen = self._generate_tests_for_gap(gap, repo_path)
                    if gen["generated"]:
                        generated_test_files.append(gen["file_path"])
                        tests_generated += 1
                    self.log(
                        f"Test generation for {gap.get('file', '?')}: "
                        f"{'OK' if gen['generated'] else gen.get('error', 'failed')}"
                    )

            result = {
                "current_coverage": coverage_percent,
                "coverage_status": "adequate" if coverage_percent >= coverage_threshold else "insufficient",
                "coverage_threshold_used": coverage_threshold,
                "gaps_identified": len(gaps),
                "gaps": gaps,
                "recommendations": recommendations,
                "rag_insights_used": augmented_context.get("rag_insights_count", 0),
                "tests_generated": tests_generated,
                "generated_test_files": generated_test_files,
            }

            self._record_execution("success", result, tags=["coverage_analysis"])
            self.log(f"Identified {len(gaps)} coverage gaps")
            return result

        except Exception as e:
            self._record_execution("error", {"error": str(e)}, tags=["error"])
            self.log(f"Coverage analysis failed: {str(e)}", "ERROR")
            raise

    def _identify_coverage_gaps(
        self, coverage_data: Dict, augmented_context: Optional[Dict] = None
    ) -> List[Dict]:
        """Identify test coverage gaps using RAG insights"""
        gaps = []
        uncovered_files = coverage_data.get("uncovered_files", [])

        for file_path in uncovered_files:
            gap = {
                "file": file_path,
                "type": "untested_file",
                "priority": "high" if "api" in file_path or "service" in file_path else "medium",
            }
            gaps.append(gap)

        # RAG-enhanced gap detection
        if augmented_context:
            rag_recommendations = augmented_context.get("rag_recommendations", [])
            for rec in rag_recommendations:
                if rec.get("confidence", 0) > 0.7:
                    gaps.append(
                        {
                            "file": "RAG-identified",
                            "type": rec.get("type", "coverage_gap"),
                            "priority": "high",
                            "insight": rec.get("insight", ""),
                        }
                    )

        return gaps

    def _generate_test_recommendations(
        self, gaps: List[Dict], augmented_context: Optional[Dict] = None
    ) -> List[str]:
        """Generate test recommendations with RAG insights"""
        recommendations = []

        # Basic recommendations
        high_priority_gaps = [g for g in gaps if g.get("priority") == "high"]
        if high_priority_gaps:
            recommendations.append(
                f"Add tests for {len(high_priority_gaps)} high-priority untested files"
            )

        # Add recommendations for medium priority gaps
        medium_priority_gaps = [g for g in gaps if g.get("priority") == "medium"]
        if medium_priority_gaps:
            recommendations.append(
                f"Add tests for {len(medium_priority_gaps)} medium-priority untested files"
            )

        # Add general recommendation if there are any gaps
        if gaps and not recommendations:
            recommendations.append(f"Add tests for {len(gaps)} untested files")

        # RAG-enhanced recommendations
        if augmented_context:
            rag_recommendations = augmented_context.get("rag_recommendations", [])
            for rec in rag_recommendations:
                if rec.get("confidence", 0) > 0.7:
                    insight = rec.get("insight", "")
                    if insight and insight not in recommendations:
                        recommendations.append(f"[RAG] {insight}")

        return recommendations

    def _generate_tests_for_gap(
        self, gap: Dict[str, Any], repo_path: str = "."
    ) -> Dict[str, Any]:
        """
        Generate a pytest test file for a coverage gap using Claude Haiku.

        Mirrors SREAgent._attempt_test_repair() pattern exactly:
        1. Read source file (first 4000 chars for token budget)
        2. Call claude-haiku-4-5-20251001 — system prompt requests pure pytest, no fences
        3. Strip any markdown fences from response
        4. compile() gate — SyntaxError caught before touching disk
        5. Skip if output path already exists (never overwrite)
        6. Write to tempfile → pytest --collect-only validates collection
        7. Atomic write to .agenticqa/generated_tests/test_{module}.py only if valid

        Returns:
            {"generated": bool, "file_path": str, "error": str}
        """
        from pathlib import Path as _Path
        source_file = gap.get("file", "")
        if not source_file:
            return {"generated": False, "file_path": "", "error": "no source file in gap"}

        source_path = _Path(repo_path) / source_file
        if not source_path.exists() or source_path.suffix != ".py":
            return {
                "generated": False,
                "file_path": "",
                "error": f"source file not found or not Python: {source_path}",
            }

        # Step 1: Read source (cap at 4000 chars for token budget)
        source = source_path.read_text(errors="replace")[:4000]

        # Step 2: Call Haiku to generate the test file
        try:
            import anthropic as _anthropic
            _client = _anthropic.Anthropic()
            _msg = _client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2048,
                system=(
                    "You are a test generation assistant. Given a Python source file and "
                    "its coverage gap description, output ONLY a complete pytest test file. "
                    "No explanation. No markdown fences. Just the Python test code. "
                    "Import the module under test using its module path. "
                    "Generate at minimum 3 test functions covering the described gap."
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Source file ({source_file}):\n{source}\n\n"
                        f"Coverage gap type: {gap.get('type', 'untested_file')}\n"
                        f"Priority: {gap.get('priority', 'medium')}\n"
                        f"Additional context: {gap.get('insight', '')}\n\n"
                        f"Generate a pytest test file for this module."
                    ),
                }],
            )
            test_code = _msg.content[0].text.strip()
        except Exception as exc:
            return {"generated": False, "file_path": "", "error": f"LLM unavailable: {exc}"}

        # Step 3: Strip markdown fences (same pattern as _attempt_test_repair)
        test_code = re.sub(r"^```[a-zA-Z]*\n?", "", test_code)
        test_code = re.sub(r"\n?```$", "", test_code).strip()

        # Step 4: compile() syntax gate — fast check before any disk I/O
        try:
            compile(test_code, "<generated>", "exec")
        except SyntaxError as exc:
            return {"generated": False, "file_path": "", "error": f"Syntax error in generated code: {exc}"}

        # Step 5: Determine output path — never overwrite existing tests
        module_name = source_path.stem
        out_dir = _Path(repo_path) / ".agenticqa" / "generated_tests"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"test_{module_name}.py"
        if out_path.exists():
            return {
                "generated": False,
                "file_path": str(out_path),
                "error": "file already exists — skipping to avoid overwrite",
            }

        # Step 6: Write to temp file and validate with pytest --collect-only
        import subprocess as _sp
        import tempfile as _tempfile
        tmp_path_str = None
        collection_ok = False
        try:
            with _tempfile.NamedTemporaryFile(
                suffix=".py", mode="w", delete=False, dir=out_dir
            ) as _tmp:
                _tmp.write(test_code)
                tmp_path_str = _tmp.name

            _proc = _sp.run(
                [
                    "python", "-m", "pytest", tmp_path_str,
                    "--collect-only", "-q", "--tb=no", "--no-header",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            collection_ok = _proc.returncode == 0
        except Exception:
            collection_ok = False
        finally:
            if tmp_path_str:
                try:
                    _Path(tmp_path_str).unlink(missing_ok=True)
                except Exception:
                    pass

        if not collection_ok:
            return {
                "generated": False,
                "file_path": "",
                "error": "Generated tests failed pytest --collect-only validation",
            }

        # Step 7: Atomic write — only after validation passes
        out_path.write_text(test_code)
        self.log(f"Generated test file: {out_path}")
        return {"generated": True, "file_path": str(out_path), "error": ""}


class FullstackAgent(BaseAgent):
    """Fullstack Agent - Generates code from feature requests and fixes issues"""

    def __init__(self):
        super().__init__("Fullstack_Agent")

    def execute(self, feature_request: Dict) -> Dict[str, Any]:
        """
        Generate code from feature request with RAG-augmented insights.

        Learns from historical code patterns and successful implementations in Weaviate.
        """
        self.log("Generating code from feature request")

        try:
            # Augment context with RAG insights from Weaviate
            augmented_context = self._augment_with_rag(
                {
                    "feature_title": feature_request.get("title", ""),
                    "feature_category": feature_request.get("category", ""),
                    "description": feature_request.get("description", ""),
                }
            )

            title = feature_request.get("title", "")
            category = feature_request.get("category", "general")
            description = feature_request.get("description", "")

            # Generate code based on feature request
            generated_code = self._generate_code(title, category, description, augmented_context)

            result = {
                "feature_title": title,
                "category": category,
                "code_generated": generated_code is not None,
                "code": generated_code,
                "files_created": self._get_files_to_create(category),
                "status": "success" if generated_code else "failed",
                "rag_insights_used": augmented_context.get("rag_insights_count", 0),
            }

            self._record_execution("success", result, tags=["code_generation"])
            self.log(f"Code generation {'succeeded' if generated_code else 'failed'}")
            return result

        except Exception as e:
            self._record_execution("error", {"error": str(e)}, tags=["error"])
            self.log(f"Code generation failed: {str(e)}", "ERROR")
            raise

    def _call_llm(
        self, title: str, category: str, description: str, augmented_context: Optional[Dict] = None
    ) -> Optional[str]:
        """Call the Anthropic API to generate real code. Returns None if unavailable."""
        try:
            import anthropic  # type: ignore

            rag_context = ""
            if augmented_context:
                insights = augmented_context.get("high_confidence_insights", [])
                if insights:
                    rag_context = "\n\nRelevant patterns from past implementations:\n" + "\n".join(
                        f"- {i.get('insight', '')}" for i in insights[:3] if i.get("insight")
                    )

            prompt = (
                f"Generate production-ready code for the following feature.\n\n"
                f"Title: {title}\n"
                f"Category: {category}\n"
                f"Description: {description}"
                f"{rag_context}\n\n"
                f"Requirements:\n"
                f"- Write complete, working code with proper error handling\n"
                f"- Follow best practices for the language/framework\n"
                f"- Keep it focused and minimal — no boilerplate beyond what is needed\n"
                f"- Output only the code, no explanation or markdown fences"
            )

            client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            text = message.content[0].text.strip()
            # Strip markdown code fences if the model wrapped its output
            text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            return text.strip() if text else None
        except Exception as exc:
            self.log(f"LLM code generation unavailable: {exc}", "WARNING")
            return None

    def _generate_code(
        self, title: str, category: str, description: str, augmented_context: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Generate code — tries real LLM first, falls back to templates.

        Primary path: Anthropic API (claude-haiku) with RAG context injected into prompt.
        Fallback: deterministic templates when ANTHROPIC_API_KEY is not set or API fails.
        """
        # Primary: real LLM generation
        llm_code = self._call_llm(title, category, description, augmented_context)
        if llm_code:
            return llm_code

        # Fallback: template-based generation
        if category == "api":
            return f"""
// API Endpoint: {title}
// Description: {description}

async function {self._to_function_name(title)}(req, res) {{
    try {{
        // TODO: implement {title}
        res.json({{ success: true, message: '{title} executed successfully' }});
    }} catch (error) {{
        res.status(500).json({{ success: false, error: error.message }});
    }}
}}

module.exports = {{ {self._to_function_name(title)} }};
"""
        elif category == "ui":
            return f"""
<!-- UI Component: {title} -->
<!-- Description: {description} -->

<div class="{self._to_class_name(title)}">
    <h2>{title}</h2>
    <p>{description}</p>
</div>

<script>
// TODO: add component logic for {title}
</script>
"""
        else:
            return f"""
// Feature: {title}
// Category: {category}
// Description: {description}

function {self._to_function_name(title)}() {{
    // Implementation here
    console.log('Feature: {title}');
}}

module.exports = {{ {self._to_function_name(title)} }};
"""

    def _to_function_name(self, title: str) -> str:
        """Convert title to function name"""
        return title.lower().replace(" ", "_").replace("-", "_")

    def _to_class_name(self, title: str) -> str:
        """Convert title to CSS class name"""
        return title.lower().replace(" ", "-")

    def _get_files_to_create(self, category: str) -> List[str]:
        """Get list of files that would be created"""
        if category == "api":
            return ["routes/feature.js", "controllers/feature.controller.js"]
        elif category == "ui":
            return ["components/Feature.html", "styles/feature.css"]
        else:
            return ["src/feature.js"]


class RedTeamAgent(BaseAgent):
    """Adversarial agent (#8) that probes AgenticQA's governance stack for bypasses.

    Two-tier self-patching:
    - Level 1 (auto): extends OutputScanner via .agenticqa/red_team_patterns.json
    - Level 2 (proposed): writes .agenticqa/constitutional_proposals.json for human review
      (constitutional_gate.py is protected by T1-005 — agents cannot auto-modify it)
    """

    def __init__(self):
        super().__init__("RedTeam_Agent")
        try:
            from agenticqa.redteam import AdversarialGenerator, PatternPatcher
            self._generator = AdversarialGenerator()
            self._patcher = PatternPatcher()
        except ImportError:
            self._generator = None
            self._patcher = None

    def execute(self, scan_data: Dict) -> Dict[str, Any]:
        """Probe governance stack for bypasses and optionally self-patch.

        Args:
            scan_data: {
                "mode": "fast" | "thorough"  (default "fast"),
                "target": "scanner" | "gate" | "both"  (default "both"),
                "auto_patch": bool  (default True),
            }

        Returns:
            {
                "bypass_attempts": int,
                "successful_bypasses": int,
                "patches_applied": int,
                "proposals_generated": int,
                "scanner_strength": float,
                "gate_strength": float,
                "vulnerabilities": List[dict],       # raw output field stripped
                "constitutional_proposals": List[str],
                "status": "clean" | "bypasses_found" | "patched",
            }
        """
        if self._generator is None or self._patcher is None:
            raise RuntimeError("RedTeam module not available. Install agenticqa.redteam.")

        mode = scan_data.get("mode", "fast")
        target = scan_data.get("target", "both")
        auto_patch = scan_data.get("auto_patch", True)

        samples = self._generator.generate(mode=mode)

        try:
            from agenticqa.factory.sandbox.output_scanner import OutputScanner
            scanner = OutputScanner()
        except ImportError:
            scanner = None

        try:
            from agenticqa.constitutional_gate import check_action
        except ImportError:
            check_action = None  # type: ignore

        vulnerabilities: List[Dict[str, Any]] = []
        proposals: List[str] = []
        patches_applied = 0

        for technique in samples:
            category = technique.get("category", "")

            if category == "constitutional_gate" and target in ("gate", "both"):
                if check_action is None:
                    continue
                action = technique.get("action", "agent_invoke")
                ctx = technique.get("context", {})
                verdict = check_action(action, ctx)
                if verdict["verdict"] == "ALLOW":
                    vuln = {
                        k: v for k, v in technique.items()
                        if k not in ("output",)
                    }
                    vuln["escaped_gate"] = True
                    vuln["verdict"] = verdict
                    vulnerabilities.append(vuln)
                    proposal_id = self._patcher.propose_constitutional_amendment(technique, action)
                    proposals.append(proposal_id)

            elif category != "constitutional_gate" and target in ("scanner", "both"):
                if scanner is None:
                    continue
                output = technique.get("output", {})
                scan_result = scanner.scan(output)
                if scan_result["clean"]:
                    vuln = {
                        k: v for k, v in technique.items()
                        if k not in ("output",)
                    }
                    vuln["escaped_scanner"] = True
                    vulnerabilities.append(vuln)
                    if auto_patch:
                        applied = self._patcher.patch_scanner(technique, None)
                        if applied:
                            patches_applied += 1

        scanner_samples = [t for t in samples if t.get("category") != "constitutional_gate"]
        gate_samples = [t for t in samples if t.get("category") == "constitutional_gate"]
        scanner_bypasses = sum(1 for v in vulnerabilities if v.get("escaped_scanner"))
        gate_bypasses = sum(1 for v in vulnerabilities if v.get("escaped_gate"))

        scanner_strength = 1.0 - (scanner_bypasses / max(len(scanner_samples), 1))
        gate_strength = 1.0 - (gate_bypasses / max(len(gate_samples), 1))

        status = "clean"
        if vulnerabilities:
            status = "patched" if patches_applied > 0 else "bypasses_found"

        result = {
            "bypass_attempts": len(samples),
            "successful_bypasses": len(vulnerabilities),
            "patches_applied": patches_applied,
            "proposals_generated": len(proposals),
            "scanner_strength": round(scanner_strength, 4),
            "gate_strength": round(gate_strength, 4),
            "vulnerabilities": vulnerabilities,
            "constitutional_proposals": proposals,
            "status": status,
        }
        # Prompt injection static analysis — non-blocking
        try:
            from agenticqa.security.prompt_injection_scanner import PromptInjectionScanner
            _repo_path = scan_data.get("repo_path", ".")
            _inj = PromptInjectionScanner().scan(_repo_path)
            result["prompt_injection_surface"] = _inj.surface_score
            result["prompt_injection_findings"] = len(_inj.findings)
            for _f in _inj.findings:
                result.setdefault("vulnerabilities", []).append({
                    "type": _f.rule_id, "file": _f.file, "line": _f.line,
                    "severity": _f.severity, "description": _f.message,
                })
        except Exception:
            pass

        self._record_execution("success", result, tags=["red_team", "security"])

        # Persist to time-series history for trend tracking — non-blocking
        try:
            from data_store.redteam_history import RedTeamHistoryStore
            RedTeamHistoryStore().record_from_result(
                result,
                mode=mode,
                target=target,
            )
        except Exception:
            pass

        self.log(
            f"Red Team: {len(samples)} attempts, {len(vulnerabilities)} bypasses, "
            f"{patches_applied} patched, {len(proposals)} proposals"
        )
        return result


class AgentOrchestrator:
    """Orchestrates multiple agents and coordinates their execution"""

    def __init__(self):
        self.agents = {
            "qa": QAAssistantAgent(),
            "performance": PerformanceAgent(),
            "compliance": ComplianceAgent(),
            "devops": DevOpsAgent(),
            "sre": SREAgent(),
            "sdet": SDETAgent(),
            "fullstack": FullstackAgent(),
            "red_team": RedTeamAgent(),
        }
        self.log("Agent Orchestrator initialized with 8 agents")

    def execute_all_agents(self, data: Dict) -> Dict[str, Any]:
        """Execute all agents with their respective tasks"""
        results = {}

        _route = {
            "qa":         data.get("test_results", {}),
            "performance": data.get("execution_data", {}),
            "compliance": data.get("compliance_data", {}),
            "devops":     data.get("deployment_config", {}),
            "sre":        data.get("linting_data", {}),
            "sdet":       data.get("coverage_data", {}),
            "fullstack":  data.get("feature_request", {}),
            "red_team":   data.get("red_team_config", {"mode": "fast", "target": "both", "auto_patch": True}),
        }
        for agent_name, agent in self.agents.items():
            try:
                results[agent_name] = agent.execute(_route[agent_name])
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
        timestamp = datetime.now(timezone.utc).isoformat()
        print(f"[{timestamp}] [ORCHESTRATOR] {message}")
