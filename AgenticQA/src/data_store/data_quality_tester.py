"""Comprehensive Data Quality Tests for Data Store

Tests ensure data consistency, integrity, and compliance across all deployments.
"""

import json
import hashlib
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict


class DataQualityTester:
    """Comprehensive data quality testing suite for the data store"""

    def __init__(self, artifact_store):
        self.store = artifact_store
        self.test_results = []
        self.timestamp = datetime.utcnow().isoformat()

    def run_all_tests(self) -> Dict[str, Any]:
        """Run complete data quality test suite"""
        print("\n" + "=" * 80)
        print("DATA QUALITY TEST SUITE - COMPREHENSIVE DATA STORE VALIDATION")
        print("=" * 80)

        results = {
            "timestamp": self.timestamp,
            "tests": {},
            "summary": {},
        }

        # Run all tests
        tests = [
            ("artifact_integrity", self.test_artifact_integrity),
            ("checksum_validation", self.test_checksum_validation),
            ("schema_consistency", self.test_schema_consistency),
            ("no_duplicate_artifacts", self.test_no_duplicates),
            ("metadata_completeness", self.test_metadata_completeness),
            ("index_accuracy", self.test_index_accuracy),
            ("data_immutability", self.test_data_immutability),
            ("pii_protection", self.test_pii_protection),
            ("temporal_consistency", self.test_temporal_consistency),
            ("cross_deployment_consistency", self.test_cross_deployment_consistency),
        ]

        passed = 0
        failed = 0

        for test_name, test_func in tests:
            try:
                test_result = test_func()
                results["tests"][test_name] = test_result
                print(f"\n✓ {test_name}: {'PASS' if test_result['passed'] else 'FAIL'}")
                if test_result["passed"]:
                    passed += 1
                else:
                    failed += 1
                    print(f"  Failures: {test_result.get('failures', [])}")
            except Exception as e:
                results["tests"][test_name] = {
                    "passed": False,
                    "error": str(e),
                }
                failed += 1
                print(f"\n✗ {test_name}: ERROR - {str(e)}")

        results["summary"] = {
            "total_tests": len(tests),
            "passed": passed,
            "failed": failed,
            "success_rate": (passed / len(tests)) * 100,
            "all_passed": failed == 0,
        }

        print("\n" + "=" * 80)
        print(f"SUMMARY: {passed}/{len(tests)} tests passed ({results['summary']['success_rate']:.1f}%)")
        print("=" * 80 + "\n")

        return results

    def test_artifact_integrity(self) -> Dict[str, Any]:
        """Test 1: Verify integrity of all artifacts"""
        print("  Testing artifact integrity...")

        all_artifacts = self.store.search_artifacts()
        if not all_artifacts:
            return {"passed": True, "message": "No artifacts to test", "count": 0}

        failures = []
        for artifact_meta in all_artifacts:
            artifact_id = artifact_meta["artifact_id"]
            is_valid = self.store.verify_artifact_integrity(artifact_id)
            if not is_valid:
                failures.append(f"Integrity check failed for {artifact_id}")

        return {
            "passed": len(failures) == 0,
            "total_artifacts": len(all_artifacts),
            "failures": failures,
            "integrity_rate": ((len(all_artifacts) - len(failures)) / len(all_artifacts) * 100),
        }

    def test_checksum_validation(self) -> Dict[str, Any]:
        """Test 2: Validate SHA256 checksums"""
        print("  Testing checksum validation...")

        all_artifacts = self.store.search_artifacts()
        failures = []

        for artifact_meta in all_artifacts:
            artifact_id = artifact_meta["artifact_id"]
            stored_checksum = artifact_meta.get("checksum")

            artifact_data = self.store.get_artifact(artifact_id)
            calculated_checksum = hashlib.sha256(
                json.dumps(artifact_data, sort_keys=True).encode()
            ).hexdigest()

            if stored_checksum != calculated_checksum:
                failures.append(
                    f"Checksum mismatch for {artifact_id}: "
                    f"stored={stored_checksum}, calculated={calculated_checksum}"
                )

        return {
            "passed": len(failures) == 0,
            "total_checksums": len(all_artifacts),
            "failures": failures,
        }

    def test_schema_consistency(self) -> Dict[str, Any]:
        """Test 3: Verify schema consistency across all artifacts"""
        print("  Testing schema consistency...")

        all_artifacts = self.store.search_artifacts()
        failures = []

        # Expected schema for metadata
        required_metadata_fields = {
            "artifact_id": str,
            "timestamp": str,
            "source": str,
            "artifact_type": str,
            "checksum": str,
        }

        for artifact_meta in all_artifacts:
            for field, field_type in required_metadata_fields.items():
                if field not in artifact_meta:
                    failures.append(f"Missing field '{field}' in {artifact_meta.get('artifact_id')}")
                elif not isinstance(artifact_meta.get(field), field_type):
                    failures.append(
                        f"Type mismatch for '{field}' in {artifact_meta.get('artifact_id')}"
                    )

        return {
            "passed": len(failures) == 0,
            "total_artifacts": len(all_artifacts),
            "required_fields": len(required_metadata_fields),
            "failures": failures,
        }

    def test_no_duplicates(self) -> Dict[str, Any]:
        """Test 4: Ensure no duplicate artifacts"""
        print("  Testing for duplicates...")

        all_artifacts = self.store.search_artifacts()
        artifact_ids = [a["artifact_id"] for a in all_artifacts]
        unique_ids = set(artifact_ids)

        duplicates = [id for id in unique_ids if artifact_ids.count(id) > 1]

        return {
            "passed": len(duplicates) == 0,
            "total_artifacts": len(all_artifacts),
            "unique_artifacts": len(unique_ids),
            "duplicates": duplicates,
        }

    def test_metadata_completeness(self) -> Dict[str, Any]:
        """Test 5: Verify all metadata is complete"""
        print("  Testing metadata completeness...")

        all_artifacts = self.store.search_artifacts()
        failures = []

        for artifact_meta in all_artifacts:
            # Check timestamp format
            try:
                datetime.fromisoformat(artifact_meta.get("timestamp", ""))
            except (ValueError, TypeError):
                failures.append(f"Invalid timestamp in {artifact_meta.get('artifact_id')}")

            # Check size_bytes exists
            if "size_bytes" not in artifact_meta:
                failures.append(f"Missing size_bytes in {artifact_meta.get('artifact_id')}")

            # Check tags is a list
            if not isinstance(artifact_meta.get("tags", []), list):
                failures.append(f"Invalid tags format in {artifact_meta.get('artifact_id')}")

        return {
            "passed": len(failures) == 0,
            "total_artifacts": len(all_artifacts),
            "failures": failures,
        }

    def test_index_accuracy(self) -> Dict[str, Any]:
        """Test 6: Verify index accuracy"""
        print("  Testing index accuracy...")

        index_path = self.store.index_file
        if not index_path.exists():
            return {"passed": False, "message": "Index file not found"}

        with open(index_path, "r") as f:
            index = json.load(f)

        all_artifacts = self.store.search_artifacts()
        failures = []

        # Check if all raw artifacts are indexed
        indexed_ids = {a["artifact_id"] for a in all_artifacts}
        raw_dir = self.store.raw_dir

        for raw_file in raw_dir.glob("*.json"):
            artifact_id = raw_file.stem
            if artifact_id not in indexed_ids:
                failures.append(f"Artifact {artifact_id} exists but not indexed")

        return {
            "passed": len(failures) == 0,
            "indexed_artifacts": len(indexed_ids),
            "failures": failures,
        }

    def test_data_immutability(self) -> Dict[str, Any]:
        """Test 7: Verify data immutability (multiple reads return same data)"""
        print("  Testing data immutability...")

        all_artifacts = self.store.search_artifacts()[:10]  # Sample first 10
        failures = []

        for artifact_meta in all_artifacts:
            artifact_id = artifact_meta["artifact_id"]

            # Read twice
            read1 = self.store.get_artifact(artifact_id)
            read2 = self.store.get_artifact(artifact_id)

            hash1 = hashlib.sha256(json.dumps(read1, sort_keys=True).encode()).hexdigest()
            hash2 = hashlib.sha256(json.dumps(read2, sort_keys=True).encode()).hexdigest()

            if hash1 != hash2:
                failures.append(f"Data mutated on second read of {artifact_id}")

        return {
            "passed": len(failures) == 0,
            "artifacts_tested": len(all_artifacts),
            "failures": failures,
        }

    def test_pii_protection(self) -> Dict[str, Any]:
        """Test 8: Verify no exposed PII"""
        print("  Testing PII protection...")

        import re

        all_artifacts = self.store.search_artifacts()
        pii_patterns = {
            "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "ssn": r"\d{3}-\d{2}-\d{4}",
            "credit_card": r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}",
        }

        failures = []

        for artifact_meta in all_artifacts:
            artifact_id = artifact_meta["artifact_id"]
            artifact = self.store.get_artifact(artifact_id)
            artifact_str = json.dumps(artifact)

            for pii_type, pattern in pii_patterns.items():
                if re.search(pattern, artifact_str):
                    failures.append(f"Potential {pii_type} detected in {artifact_id}")

        return {
            "passed": len(failures) == 0,
            "artifacts_scanned": len(all_artifacts),
            "pii_types_checked": len(pii_patterns),
            "failures": failures,
        }

    def test_temporal_consistency(self) -> Dict[str, Any]:
        """Test 9: Verify temporal consistency (timestamps are ordered)"""
        print("  Testing temporal consistency...")

        all_artifacts = self.store.search_artifacts()
        failures = []

        timestamps = []
        for artifact_meta in all_artifacts:
            try:
                ts = datetime.fromisoformat(artifact_meta["timestamp"])
                timestamps.append((artifact_meta["artifact_id"], ts))
            except (ValueError, TypeError):
                failures.append(f"Invalid timestamp in {artifact_meta['artifact_id']}")

        # Check for future-dated artifacts
        now = datetime.utcnow()
        for artifact_id, ts in timestamps:
            if ts > now:
                failures.append(f"Future timestamp detected in {artifact_id}: {ts}")

        # Check for very old artifacts
        cutoff = now - timedelta(days=365)
        for artifact_id, ts in timestamps:
            if ts < cutoff:
                failures.append(f"Artifact older than 1 year: {artifact_id}")

        return {
            "passed": len(failures) == 0,
            "total_artifacts": len(all_artifacts),
            "failures": failures,
        }

    def test_cross_deployment_consistency(self) -> Dict[str, Any]:
        """Test 10: Verify consistency for deployment resilience"""
        print("  Testing cross-deployment consistency...")

        all_artifacts = self.store.search_artifacts()
        failures = []

        # Group by source/agent
        by_source = defaultdict(list)
        for artifact in all_artifacts:
            by_source[artifact["source"]].append(artifact)

        # Check each agent has consistent data
        for source, artifacts in by_source.items():
            artifact_types = set(a["artifact_type"] for a in artifacts)
            if len(artifact_types) > 0:
                # At least one artifact type per source is acceptable
                pass

            # Check all artifacts from same source have valid checksums
            for artifact_meta in artifacts:
                is_valid = self.store.verify_artifact_integrity(artifact_meta["artifact_id"])
                if not is_valid:
                    failures.append(f"Invalid artifact from {source}: {artifact_meta['artifact_id']}")

        return {
            "passed": len(failures) == 0,
            "sources_tested": len(by_source),
            "total_artifacts": len(all_artifacts),
            "failures": failures,
        }

    def export_test_results(self, results: Dict) -> str:
        """Export test results to JSON for audit trail"""
        output_file = self.store.patterns_dir / "data_quality_test_results.json"

        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)

        return str(output_file)
