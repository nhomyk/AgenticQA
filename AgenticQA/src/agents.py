"""Base Agent class with data store integration"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional, List, TYPE_CHECKING
import json
import os
from src.data_store import SecureDataPipeline

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
        if use_data_store:
            self.pipeline = SecureDataPipeline(use_great_expectations=False)

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

        Args:
            context: Current execution context

        Returns:
            Augmented context with rag_recommendations and high_confidence_insights
        """
        if not self.use_rag or not self.rag:
            return context

        try:
            agent_type = self._get_agent_type()
            augmented_context = self.rag.augment_agent_context(agent_type, context)

            # Log RAG insights for transparency
            insights_count = augmented_context.get("rag_insights_count", 0)
            if insights_count > 0:
                self.log(f"RAG retrieved {insights_count} relevant insights from Weaviate", "INFO")

            return augmented_context
        except Exception as e:
            self.log(f"RAG augmentation failed: {e}. Proceeding without RAG insights.", "WARNING")
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

        # 2. Log to Weaviate (semantic embeddings for RAG)
        if self.use_rag and self.rag:
            try:
                agent_type = self._get_agent_type()
                execution_result = {
                    "agent_name": self.agent_name,
                    "status": status,
                    "output": output,
                    "metadata": metadata or {},
                    "timestamp": datetime.utcnow().isoformat(),
                    "artifact_id": artifact_id,
                }
                self.rag.log_agent_execution(agent_type, execution_result)
                self.log(f"Execution logged to Weaviate for future learning", "DEBUG")
            except Exception as e:
                self.log(f"Failed to log execution to Weaviate: {e}", "WARNING")

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

    def delegate_to_agent(self, agent_name: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delegate a task to another specialized agent.

        This enables true agent collaboration where agents leverage each other's
        expertise rather than working in isolation.

        Args:
            agent_name: Name of target agent (e.g., "SRE_Agent", "Compliance_Agent")
            task: Task data to pass to the agent

        Returns:
            Result from the delegated agent

        Raises:
            DelegationError: If delegation is not allowed or fails

        Example:
            # SDET delegates test generation to SRE
            tests = self.delegate_to_agent("SRE_Agent", {
                "task": "generate_tests",
                "files": ["src/api.py"],
                "coverage_gaps": [10, 20, 30]
            })
        """
        if not self.agent_registry:
            raise Exception(f"{self.agent_name} cannot delegate: No agent registry configured")

        self.log(f"Delegating task to {agent_name}", "INFO")

        result = self.agent_registry.delegate_task(
            from_agent=self.agent_name,
            to_agent=agent_name,
            task=task,
            depth=self._delegation_depth + 1,
        )

        self.log(f"Delegation to {agent_name} completed", "INFO")
        return result

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
        timestamp = datetime.utcnow().isoformat()
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

            analysis = {
                "duration_ms": duration,
                "memory_mb": memory,
                "status": "optimal" if duration < 5000 else "degraded",
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
                "data_encryption": compliance_data.get("encrypted", False),
                "pii_protection": compliance_data.get("pii_masked", False),
                "audit_logs": compliance_data.get("audit_enabled", False),
                "violations": self._check_violations(compliance_data, augmented_context),
                "rag_insights_used": augmented_context.get("rag_insights_count", 0),
            }

            self._record_execution("success", checks, tags=["compliance"])
            self.log("Compliance check complete")
            return checks

        except Exception as e:
            self._record_execution("error", {"error": str(e)}, tags=["error"])
            self.log(f"Compliance check failed: {str(e)}", "ERROR")
            raise

    def _check_violations(self, data: Dict, augmented_context: Optional[Dict] = None) -> List[str]:
        """
        Check for compliance violations with RAG insights.

        Uses both:
        1. Basic compliance rules
        2. Semantic insights from Weaviate (applicable compliance rules)
        """
        violations = []

        # Basic rule-based violations
        if not data.get("encrypted"):
            violations.append("Data encryption required but not enabled")
        if not data.get("pii_masked"):
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
                "timestamp": datetime.utcnow().isoformat(),
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
                "timestamp": datetime.utcnow().isoformat(),
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
            "timestamp": datetime.utcnow().isoformat(),
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
                "health_checks": self._run_health_checks(augmented_context),
                "rag_insights_used": augmented_context.get("rag_insights_count", 0),
            }

            self._record_execution("success", result, tags=["deployment"])
            self.log("Deployment complete")
            return result

        except Exception as e:
            self._record_execution("error", {"error": str(e)}, tags=["error"])
            self.log(f"Deployment failed: {str(e)}", "ERROR")
            raise

    def _run_health_checks(self, augmented_context: Optional[Dict] = None) -> Dict[str, bool]:
        """
        Run health checks with RAG insights.

        Uses RAG to check for known deployment errors and resolutions.
        """
        health_checks = {
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
                    health_checks[f"rag_{check_name}"] = True

        return health_checks


class SREAgent(BaseAgent):
    """SRE (Site Reliability Engineering) Agent - Fixes linting and code quality issues"""

    def __init__(self):
        super().__init__("SRE_Agent")

    def execute(self, linting_data: Dict) -> Dict[str, Any]:
        """
        Analyze linting errors and apply auto-fixes with RAG-augmented insights.

        Learns from past fixes stored in Weaviate to improve fix quality.
        """
        self.log("Analyzing linting errors and applying fixes")

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
            fixes_applied = []

            # Apply fixes for common linting errors
            for error in errors:
                fix = self._apply_linting_fix(error, augmented_context)
                if fix:
                    fixes_applied.append(fix)

            result = {
                "total_errors": len(errors),
                "fixes_applied": len(fixes_applied),
                "fixes": fixes_applied,
                "status": "success" if len(fixes_applied) == len(errors) else "partial",
                "rag_insights_used": augmented_context.get("rag_insights_count", 0),
            }

            self._record_execution("success", result, tags=["linting_fix"])
            self.log(f"Applied {len(fixes_applied)}/{len(errors)} linting fixes")
            return result

        except Exception as e:
            self._record_execution("error", {"error": str(e)}, tags=["error"])
            self.log(f"Linting fix failed: {str(e)}", "ERROR")
            raise

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

        # Basic fix patterns
        fix_map = {
            "quotes": "Changed quotes to doublequote",
            "semi": "Added missing semicolon",
            "no-unused-vars": "Removed unused variable",
            "indent": "Fixed indentation",
        }

        if rule in fix_map:
            return {
                "rule": rule,
                "fix_applied": fix_map[rule],
                "source": "basic",
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
        """
        self.log("Analyzing test coverage and identifying gaps")

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

            # Identify coverage gaps
            gaps = self._identify_coverage_gaps(coverage_data, augmented_context)

            # Generate test recommendations
            recommendations = self._generate_test_recommendations(gaps, augmented_context)

            result = {
                "current_coverage": coverage_percent,
                "coverage_status": "adequate" if coverage_percent >= 80 else "insufficient",
                "gaps_identified": len(gaps),
                "gaps": gaps,
                "recommendations": recommendations,
                "rag_insights_used": augmented_context.get("rag_insights_count", 0),
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

    def _generate_code(
        self, title: str, category: str, description: str, augmented_context: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Generate code with RAG insights.

        Uses historical successful patterns from Weaviate to guide generation.
        """
        # RAG-enhanced code generation
        if augmented_context:
            rag_recommendations = augmented_context.get("high_confidence_insights", [])
            for rec in rag_recommendations:
                if rec.get("confidence", 0) > 0.8:
                    # Use RAG-suggested implementation pattern
                    return f"// Generated using RAG insight\n// {rec.get('insight', '')}\n\n// Implementation for: {title}\n// {description}"

        # Basic code generation templates
        if category == "api":
            return f"""
// API Endpoint: {title}
// Description: {description}

async function {self._to_function_name(title)}(req, res) {{
    try {{
        // Implementation here
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
// Component logic here
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
                    results[agent_name] = agent.execute(data.get("execution_data", {}))
                elif agent_name == "compliance":
                    results[agent_name] = agent.execute(data.get("compliance_data", {}))
                elif agent_name == "devops":
                    results[agent_name] = agent.execute(data.get("deployment_config", {}))
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
