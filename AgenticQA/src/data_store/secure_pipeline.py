"""Secure data pipeline with full validation workflow"""

from typing import Dict, Any, Tuple

from .artifact_store import TestArtifactStore
from .security_validator import DataSecurityValidator
from .pattern_analyzer import PatternAnalyzer

try:
    from .great_expectations_validator import AgentDataValidator, GREAT_EXPECTATIONS_AVAILABLE

except ImportError:
    AgentDataValidator = None
    GREAT_EXPECTATIONS_AVAILABLE = False


class SecureDataPipeline:
    """Full pipeline: validation → storage → analysis"""

    def __init__(self, use_great_expectations: bool = True):
        self.artifact_store = TestArtifactStore()
        self.security_validator = DataSecurityValidator()
        self.pattern_analyzer = PatternAnalyzer(self.artifact_store)

        if use_great_expectations and GREAT_EXPECTATIONS_AVAILABLE and AgentDataValidator:
            self.ge_validator = AgentDataValidator()
        else:
            self.ge_validator = None

    def _normalize_validation_args(
        self, agent_name_or_input: Any, input_data: Any = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Normalize legacy/new validation call signatures.

        Supported signatures:
        - validate_input_data(agent_name: str, input_data: dict)
        - validate_input_data(input_data: dict)
        - validate_input_data(input_data: dict, agent_name: str)
        """
        if isinstance(agent_name_or_input, str) and isinstance(input_data, dict):
            return agent_name_or_input, input_data

        if isinstance(agent_name_or_input, dict) and input_data is None:
            return "unknown", agent_name_or_input

        if isinstance(agent_name_or_input, dict) and isinstance(input_data, str):
            return input_data, agent_name_or_input

        raise TypeError(
            "validate_input_data() expects (agent_name: str, input_data: dict) "
            "or (input_data: dict[, agent_name: str])"
        )

    def validate_input_data(
        self, agent_name_or_input: Any, input_data: Any = None
    ) -> Tuple[bool, Dict]:
        """Pre-execution validation for schema, PII, and encryption readiness."""
        agent_name, payload = self._normalize_validation_args(agent_name_or_input, input_data)

        pipeline_result = {"agent": agent_name, "stages": {}}

        schema = {
            "timestamp": "str",
            "agent_name": "str",
            "status": "str",
            "output": "dict",
        }
        schema_valid, errors = self.security_validator.validate_schema_compliance(payload, schema)
        pipeline_result["stages"]["schema_validation"] = schema_valid
        if not schema_valid:
            pipeline_result["errors"] = errors
            return False, pipeline_result

        pii_valid, pii_found = self.security_validator.validate_no_pii_leakage(payload)
        pipeline_result["stages"]["pii_check"] = pii_valid
        if not pii_valid:
            pipeline_result["pii_warnings"] = pii_found
            return False, pipeline_result

        encrypt_valid, msg = self.security_validator.validate_encryption_ready(payload)
        pipeline_result["stages"]["encryption_ready"] = encrypt_valid
        pipeline_result["encryption_message"] = msg

        return True, pipeline_result

    def execute_with_validation(
        self, agent_name: str, execution_result: Dict[str, Any]
    ) -> Tuple[bool, Dict]:
        """Full pipeline with all validations"""

        # Stage 1-3: Shared pre-execution validation
        pre_valid, pipeline_result = self.validate_input_data(agent_name, execution_result)
        if not pre_valid:
            return False, pipeline_result

        encrypt_valid = pipeline_result["stages"].get("encryption_ready", False)

        # Stage 4: Great Expectations validation
        ge_success = True
        if self.ge_validator:
            try:
                ge_result = self.ge_validator.validate_agent_execution(agent_name, execution_result)
                ge_success = ge_result.get("success", True)
                pipeline_result["stages"]["great_expectations"] = ge_success
            except Exception as e:
                pipeline_result["stages"]["great_expectations"] = False
                pipeline_result["ge_error"] = str(e)
                ge_success = False
        else:
            pipeline_result["stages"]["great_expectations"] = "skipped"

        # Stage 5: Store artifact
        artifact_id = self.artifact_store.store_artifact(
            artifact_data=execution_result,
            artifact_type="execution",
            source=agent_name,
            tags=[execution_result.get("status")],
        )
        pipeline_result["artifact_id"] = artifact_id

        # Stage 6: Verify integrity
        integrity_valid = self.artifact_store.verify_artifact_integrity(artifact_id)
        pipeline_result["stages"]["integrity_verified"] = integrity_valid

        success_checks = [
            pipeline_result["stages"].get("schema_validation", False),
            pipeline_result["stages"].get("pii_check", False),
            encrypt_valid,
            integrity_valid,
        ]
        if self.ge_validator:
            success_checks.append(ge_success)

        pipeline_result["success"] = all(success_checks)

        return pipeline_result["success"], pipeline_result

    def analyze_patterns(self) -> Dict:
        """Run all pattern analyses"""
        return {
            "errors": self.pattern_analyzer.analyze_failure_patterns(),
            "performance": self.pattern_analyzer.analyze_performance_patterns(),
            "flakiness": self.pattern_analyzer.analyze_flakiness(),
        }
