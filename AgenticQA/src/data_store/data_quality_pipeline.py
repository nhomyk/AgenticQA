"""Data Quality Testing Integration with Secure Pipeline"""

from typing import Dict, Any, Tuple
from datetime import datetime

from .artifact_store import TestArtifactStore
from .data_quality_tester import DataQualityTester
from .secure_pipeline import SecureDataPipeline


class DataQualityValidatedPipeline(SecureDataPipeline):
    """Enhanced pipeline with comprehensive data quality testing"""

    def __init__(self, use_great_expectations: bool = True, run_quality_tests: bool = True):
        super().__init__(use_great_expectations)
        self.quality_tester = DataQualityTester(self.artifact_store)
        self.run_quality_tests = run_quality_tests
        self.quality_test_results = None

    def validate_input_data(self, agent_name: str, input_data: Dict[str, Any]) -> Tuple[bool, Dict]:
        """Pre-execution validation with data quality checks"""
        # Run standard validation
        is_valid, validation_result = super().validate_input_data(agent_name, input_data)

        if not is_valid:
            return is_valid, validation_result

        # Add data quality checks if enabled
        if self.run_quality_tests:
            print(f"Running pre-execution data quality checks for {agent_name}...")
            quality_result = self.quality_tester.run_all_tests()
            self.quality_test_results = quality_result

            validation_result["quality_tests"] = quality_result

            if not quality_result["summary"]["all_passed"]:
                print(
                    f"⚠️ Quality tests: {quality_result['summary']['failed']} "
                    f"test(s) failed. Proceeding with caution."
                )

        return is_valid, validation_result

    def execute_with_validation(
        self, agent_name: str, execution_result: Dict[str, Any]
    ) -> Tuple[bool, Dict]:
        """Post-execution validation with data quality verification"""
        # Run standard post-execution validation
        is_valid, pipeline_result = super().execute_with_validation(agent_name, execution_result)

        # Run post-execution quality tests
        if self.run_quality_tests:
            print(f"Running post-execution data quality checks...")
            quality_result = self.quality_tester.run_all_tests()
            self.quality_test_results = quality_result

            pipeline_result["post_execution_quality"] = quality_result
            pipeline_result["stages"]["data_quality_tests"] = quality_result["summary"][
                "all_passed"
            ]

            # Export results for audit trail
            export_path = self.quality_tester.export_test_results(quality_result)
            pipeline_result["quality_report_exported"] = export_path

            if not quality_result["summary"]["all_passed"]:
                print(
                    f"⚠️ Post-execution quality: {quality_result['summary']['failed']} "
                    f"test(s) failed"
                )
                pipeline_result["quality_warnings"] = [
                    f"{test}: {details.get('failures', [])}"
                    for test, details in quality_result["tests"].items()
                    if not details.get("passed", False)
                ]

        return is_valid, pipeline_result

    def run_deployment_validation(self) -> Dict[str, Any]:
        """Run comprehensive validation before deployment"""
        print("\n" + "=" * 80)
        print("DEPLOYMENT VALIDATION - ENSURING DATA CONSISTENCY ACROSS ENVIRONMENTS")
        print("=" * 80 + "\n")

        deployment_result = {
            "timestamp": datetime.utcnow().isoformat(),
            "validation_type": "deployment",
            "checks": {},
        }

        # Run all quality tests
        print("1. Running comprehensive data quality tests...")
        quality_results = self.quality_tester.run_all_tests()
        deployment_result["checks"]["data_quality"] = quality_results

        # Verify all artifacts are accessible
        print("\n2. Verifying artifact accessibility...")
        all_artifacts = self.artifact_store.search_artifacts()
        accessibility_check = {
            "total_artifacts": len(all_artifacts),
            "accessible": 0,
            "inaccessible": [],
        }

        for artifact_meta in all_artifacts:
            try:
                self.artifact_store.get_artifact(artifact_meta["artifact_id"])
                accessibility_check["accessible"] += 1
            except Exception as e:
                accessibility_check["inaccessible"].append(
                    {
                        "artifact_id": artifact_meta["artifact_id"],
                        "error": str(e),
                    }
                )

        deployment_result["checks"]["artifact_accessibility"] = accessibility_check

        # Verify pattern analysis works
        print("\n3. Verifying pattern analysis...")
        try:
            patterns = self.pattern_analyzer.analyze_failure_patterns()
            deployment_result["checks"]["pattern_analysis"] = {
                "status": "success",
                "patterns": patterns,
            }
        except Exception as e:
            deployment_result["checks"]["pattern_analysis"] = {
                "status": "failed",
                "error": str(e),
            }

        # Overall deployment readiness
        print("\n4. Computing deployment readiness...")
        data_quality_passed = quality_results["summary"]["all_passed"]
        accessibility_ok = len(accessibility_check["inaccessible"]) == 0
        patterns_ok = deployment_result["checks"]["pattern_analysis"]["status"] == "success"

        deployment_result["ready_for_deployment"] = (
            data_quality_passed and accessibility_ok and patterns_ok
        )

        print("\n" + "=" * 80)
        print("DEPLOYMENT VALIDATION SUMMARY")
        print("=" * 80)
        print(f"Data Quality: {'✓ PASS' if data_quality_passed else '✗ FAIL'}")
        print(f"Artifact Accessibility: {'✓ PASS' if accessibility_ok else '✗ FAIL'}")
        print(f"Pattern Analysis: {'✓ PASS' if patterns_ok else '✗ FAIL'}")
        print(
            f"\n{'✓ READY FOR DEPLOYMENT' if deployment_result['ready_for_deployment'] else '✗ NOT READY FOR DEPLOYMENT'}"
        )
        print("=" * 80 + "\n")

        # Export results
        export_path = self.quality_tester.export_test_results(deployment_result)
        deployment_result["export_path"] = export_path

        return deployment_result
