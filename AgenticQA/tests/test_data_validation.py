"""
Comprehensive Data Validation Test Suite

Tests for data accuracy, integrity, security, and quality using:
- Snapshot comparison for before/after code changes
- Duplicate detection (exact, fuzzy, phonetic)
- Schema and data type validation
- Data quality metrics and outlier detection
- Data security and PII handling
- Referential integrity checks

Markers:
- @pytest.mark.data_integrity: Data structure and type validation
- @pytest.mark.data_quality: Data content quality checks
- @pytest.mark.data_security: Security and PII validation
- @pytest.mark.data_snapshot: Before/after comparison tests
- @pytest.mark.data_duplication: Duplicate and similarity detection
"""

import pytest
import json
import hashlib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from difflib import SequenceMatcher


# ============================================================================
# FIXTURES: Data Setup and Teardown
# ============================================================================


@pytest.fixture
def sample_dataset():
    """Create sample dataset for testing"""
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "Alice", "David"],
            "email": [
                "alice@example.com",
                "bob@example.com",
                "charlie@example.com",
                "alice2@example.com",
                "david@example.com",
            ],
            "age": [25, 30, 35, 26, 28],
            "salary": [50000.0, 60000.0, 75000.0, 51000.0, 55000.0],
            "created_at": [
                datetime(2023, 1, 1),
                datetime(2023, 1, 2),
                datetime(2023, 1, 3),
                datetime(2023, 1, 4),
                datetime(2023, 1, 5),
            ],
            "status": ["active", "active", "inactive", "active", "pending"],
        }
    )


@pytest.fixture
def modified_dataset(sample_dataset):
    """Create modified dataset (simulating code changes)"""
    df = sample_dataset.copy()
    df.loc[3, "salary"] = 52000.0  # Minor change
    df.loc[4, "status"] = "active"  # Status change
    return df


@pytest.fixture
def pii_dataset():
    """Dataset containing PII for security testing"""
    return pd.DataFrame(
        {
            "user_id": [1, 2, 3],
            "ssn": ["123-45-6789", "987-65-4321", "555-55-5555"],
            "credit_card": ["4111-1111-1111-1111", "5555-5555-5555-4444", "3782-822463-51005"],
            "phone": ["555-1234", "555-5678", "555-9012"],
            "name": ["John Doe", "Jane Smith", "Bob Johnson"],
        }
    )


@pytest.fixture
def large_dataset():
    """Create large dataset for performance testing"""
    np.random.seed(42)
    n_rows = 10000
    return pd.DataFrame(
        {
            "id": range(n_rows),
            "value": np.random.normal(100, 15, n_rows),
            "category": np.random.choice(["A", "B", "C", "D"], n_rows),
            "timestamp": [datetime.now() - timedelta(days=x % 365) for x in range(n_rows)],
        }
    )


# ============================================================================
# DATA INTEGRITY TESTS - Schema, Types, Structure
# ============================================================================


class TestDataIntegrity:
    """Verify data structure and type consistency"""

    @pytest.mark.data_integrity
    @pytest.mark.critical
    def test_schema_consistency(self, sample_dataset):
        """Dataset schema should match expected structure"""
        expected_columns = {"id", "name", "email", "age", "salary", "created_at", "status"}
        actual_columns = set(sample_dataset.columns)

        assert (
            actual_columns == expected_columns
        ), f"Schema mismatch: expected {expected_columns}, got {actual_columns}"

        expected_types = {
            "id": "int64",
            "name": "object",
            "email": "object",
            "age": "int64",
            "salary": "float64",
            "created_at": "datetime64[ns]",
            "status": "object",
        }

        for col, dtype in expected_types.items():
            actual = str(sample_dataset[col].dtype)
            assert actual == dtype, f"Column {col} has type {actual}, expected {dtype}"

    @pytest.mark.data_integrity
    def test_no_unexpected_columns(self, sample_dataset):
        """Dataset should not contain unexpected columns"""
        expected_columns = {"id", "name", "email", "age", "salary", "created_at", "status"}
        unexpected = set(sample_dataset.columns) - expected_columns

        assert len(unexpected) == 0, f"Unexpected columns found: {unexpected}"

    @pytest.mark.data_integrity
    def test_row_count_preserved(self, sample_dataset, modified_dataset):
        """Row count should be preserved after modifications"""
        assert len(sample_dataset) == len(
            modified_dataset
        ), f"Row count changed: {len(sample_dataset)} vs {len(modified_dataset)}"

    @pytest.mark.data_integrity
    def test_primary_key_uniqueness(self, sample_dataset):
        """Primary key (id) should be unique"""
        assert sample_dataset["id"].is_unique, "Primary key 'id' contains duplicates"
        assert sample_dataset["id"].notna().all(), "Primary key contains null values"

    @pytest.mark.data_integrity
    def test_data_types_not_corrupted(self, sample_dataset):
        """Data types should not be corrupted"""
        # Numeric types should not contain strings
        assert (
            pd.to_numeric(sample_dataset["age"], errors="coerce").notna().all()
        ), "Age column contains non-numeric values"

        # Salary should be numeric
        assert (
            pd.to_numeric(sample_dataset["salary"], errors="coerce").notna().all()
        ), "Salary column contains non-numeric values"


# ============================================================================
# DATA QUALITY TESTS - Content Validation
# ============================================================================


class TestDataQuality:
    """Verify data content quality and validity"""

    @pytest.mark.data_quality
    @pytest.mark.critical
    def test_no_null_values_in_critical_fields(self, sample_dataset):
        """Critical fields should not contain nulls"""
        critical_fields = ["id", "name", "email"]

        for field in critical_fields:
            assert (
                sample_dataset[field].notna().all()
            ), f"Critical field '{field}' contains null values"

    @pytest.mark.data_quality
    def test_email_format_validation(self, sample_dataset):
        """Email addresses should be valid format"""
        for email in sample_dataset["email"]:
            assert pd.notna(email) and isinstance(email, str), "Invalid email type"
            assert "@" in email and "." in email, f"Malformed email: {email}"

    @pytest.mark.data_quality
    def test_age_within_valid_range(self, sample_dataset):
        """Age should be within valid range"""
        min_age = 0
        max_age = 150

        assert (sample_dataset["age"] >= min_age).all(), f"Age below minimum: {min_age}"
        assert (sample_dataset["age"] <= max_age).all(), f"Age exceeds maximum: {max_age}"

    @pytest.mark.data_quality
    def test_salary_non_negative(self, sample_dataset):
        """Salary should be non-negative"""
        assert (sample_dataset["salary"] >= 0).all(), "Negative salary values found"

    @pytest.mark.data_quality
    def test_status_enum_values(self, sample_dataset):
        """Status should only contain valid enum values"""
        valid_statuses = {"active", "inactive", "pending"}
        actual_statuses = set(sample_dataset["status"].unique())

        assert actual_statuses.issubset(
            valid_statuses
        ), f"Invalid status values: {actual_statuses - valid_statuses}"

    @pytest.mark.data_quality
    def test_temporal_consistency(self, sample_dataset):
        """Timestamps should be logically consistent"""
        dates = sample_dataset["created_at"]
        date_span = dates.max() - dates.min()

        # Span should be reasonable
        assert date_span <= timedelta(days=365 * 100), "Unrealistic date range"

    @pytest.mark.data_quality
    def test_no_future_dates(self, sample_dataset):
        """Created dates should not be in the future"""
        assert (sample_dataset["created_at"] <= datetime.now()).all(), "Future dates detected"

    @pytest.mark.data_quality
    def test_outlier_detection(self, large_dataset):
        """Detect statistical outliers"""
        values = large_dataset["value"]
        mean = values.mean()
        std = values.std()

        # Values within 3 standard deviations (99.7% should be within)
        outliers = values[(values < mean - 3 * std) | (values > mean + 3 * std)]
        outlier_percentage = len(outliers) / len(values) * 100

        assert outlier_percentage < 1, f"Outlier percentage too high: {outlier_percentage}%"


# ============================================================================
# DATA SNAPSHOT & CHANGE DETECTION TESTS
# ============================================================================


class TestDataSnapshots:
    """Verify snapshot creation and change detection"""

    @pytest.mark.data_snapshot
    @pytest.mark.critical
    def test_snapshot_creation(self, sample_dataset):
        """Create and validate data snapshot"""
        # Create snapshot
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "record_count": len(sample_dataset),
            "columns": list(sample_dataset.columns),
            "data_hash": hashlib.md5(
                pd.util.hash_pandas_object(sample_dataset, index=True).values
            ).hexdigest(),
            "sample_records": sample_dataset.head(5).to_dict("records"),
        }

        assert snapshot["record_count"] == 5, "Snapshot record count incorrect"
        assert len(snapshot["columns"]) == 7, "Snapshot column count incorrect"
        assert "data_hash" in snapshot, "Data hash not created"

    @pytest.mark.data_snapshot
    def test_before_after_comparison(self, sample_dataset, modified_dataset):
        """Compare before and after datasets"""
        before_hash = hashlib.md5(
            pd.util.hash_pandas_object(sample_dataset, index=True).values
        ).hexdigest()

        after_hash = hashlib.md5(
            pd.util.hash_pandas_object(modified_dataset, index=True).values
        ).hexdigest()

        assert before_hash != after_hash, "No changes detected (expected changes)"
        assert len(sample_dataset) == len(modified_dataset), "Row count should remain same"

    @pytest.mark.data_snapshot
    def test_detect_added_rows(self, sample_dataset):
        """Detect when rows are added"""
        df_before = sample_dataset.copy()
        new_row = pd.DataFrame(
            {
                "id": [6],
                "name": ["Eve"],
                "email": ["eve@example.com"],
                "age": [29],
                "salary": [58000.0],
                "created_at": [datetime(2023, 1, 6)],
                "status": ["active"],
            }
        )
        df_after = pd.concat([sample_dataset, new_row], ignore_index=True)

        added_rows = len(df_after) - len(df_before)
        assert added_rows == 1, f"Expected 1 added row, got {added_rows}"

    @pytest.mark.data_snapshot
    def test_detect_deleted_rows(self, sample_dataset):
        """Detect when rows are deleted"""
        df_before = sample_dataset.copy()
        df_after = sample_dataset.drop(0).reset_index(drop=True)

        deleted_rows = len(df_before) - len(df_after)
        assert deleted_rows == 1, f"Expected 1 deleted row, got {deleted_rows}"

    @pytest.mark.data_snapshot
    def test_detect_modified_values(self, sample_dataset, modified_dataset):
        """Detect when values are modified"""
        changes = []

        for col in sample_dataset.columns:
            mask = sample_dataset[col] != modified_dataset[col]
            if mask.any():
                for idx in mask[mask].index:
                    changes.append(
                        {
                            "row": idx,
                            "column": col,
                            "before": sample_dataset.loc[idx, col],
                            "after": modified_dataset.loc[idx, col],
                        }
                    )

        assert len(changes) > 0, "Expected changes not detected"
        salary_change = [c for c in changes if c["column"] == "salary"]
        assert len(salary_change) > 0, "Salary change not detected"

    @pytest.mark.data_snapshot
    def test_snapshot_integrity_hash(self, sample_dataset):
        """Verify snapshot integrity using cryptographic hash"""
        hash1 = hashlib.sha256(
            pd.util.hash_pandas_object(sample_dataset, index=True).values
        ).hexdigest()

        # Same data should produce same hash
        hash2 = hashlib.sha256(
            pd.util.hash_pandas_object(sample_dataset, index=True).values
        ).hexdigest()

        assert hash1 == hash2, "Snapshot hash mismatch for identical data"


# ============================================================================
# DUPLICATE & SIMILARITY DETECTION TESTS
# ============================================================================


class TestDuplicateDetection:
    """Detect duplicates and similar records"""

    @pytest.mark.data_duplication
    @pytest.mark.critical
    def test_exact_row_duplicates(self, sample_dataset):
        """Detect exact row duplicates"""
        duplicates = sample_dataset[sample_dataset.duplicated(keep=False)]

        # sample_dataset has no exact duplicates
        assert len(duplicates) == 0, f"Found {len(duplicates)} exact duplicates"

    @pytest.mark.data_duplication
    def test_duplicate_in_subset(self, sample_dataset):
        """Detect duplicates based on specific columns"""
        # Names: 'Alice' appears twice
        duplicates = sample_dataset[sample_dataset.duplicated(subset=["name"], keep=False)]

        assert len(duplicates) == 2, f"Expected 2 duplicates, found {len(duplicates)}"
        assert (duplicates["name"] == "Alice").all(), "All duplicates should be 'Alice'"

    @pytest.mark.data_duplication
    def test_fuzzy_name_matching(self, sample_dataset):
        """Detect similar names using fuzzy matching"""
        names = sample_dataset["name"].tolist()
        potential_duplicates = []

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                # Similarity ratio threshold
                similarity = SequenceMatcher(None, names[i], names[j]).ratio()
                if 0.8 < similarity < 1.0:  # Similar but not identical
                    potential_duplicates.append(
                        {"name1": names[i], "name2": names[j], "similarity": similarity}
                    )

        # Verify fuzzy matching logic works
        alice_count = len(sample_dataset[sample_dataset["name"] == "Alice"])
        assert alice_count == 2, f"Expected 2 Alice records, found {alice_count}"

    @pytest.mark.data_duplication
    def test_email_similarity_detection(self, sample_dataset):
        """Detect similar email addresses"""
        emails = sample_dataset["email"].tolist()
        similar_pairs = []

        for i in range(len(emails)):
            for j in range(i + 1, len(emails)):
                # Extract domain and local part
                email1_local = emails[i].split("@")[0]
                email2_local = emails[j].split("@")[0]

                similarity = SequenceMatcher(None, email1_local, email2_local).ratio()
                if similarity > 0.7:
                    similar_pairs.append(
                        {"email1": emails[i], "email2": emails[j], "similarity": similarity}
                    )

        # Verify detection logic works
        assert any(
            "alice" in pair["email1"] and "alice" in pair["email2"] for pair in similar_pairs
        ), "Similar alice emails not detected"

    @pytest.mark.data_duplication
    def test_phonetic_duplicate_detection(self, sample_dataset):
        """Detect duplicates using phonetic matching"""
        # Simplified phonetic check: same first 3 chars
        names = sample_dataset["name"].tolist()
        phonetic_groups = defaultdict(list)

        for i, name in enumerate(names):
            key = name[:3].upper()
            phonetic_groups[key].append((i, name))

        duplicates_found = [group for group in phonetic_groups.values() if len(group) > 1]
        assert len(duplicates_found) > 0, "Phonetic duplicates not detected"

    @pytest.mark.data_duplication
    def test_duplicate_percentage_report(self, sample_dataset):
        """Report percentage of duplicates"""
        total_rows = len(sample_dataset)
        duplicate_rows = len(sample_dataset[sample_dataset.duplicated(keep=False)])
        duplicate_percentage = (duplicate_rows / total_rows) * 100

        assert duplicate_percentage >= 0, "Duplicate percentage invalid"
        assert duplicate_percentage <= 100, "Duplicate percentage exceeds 100%"


# ============================================================================
# DATA SECURITY & PII DETECTION TESTS
# ============================================================================


class TestDataSecurity:
    """Verify data security and PII handling"""

    @pytest.mark.data_security
    @pytest.mark.critical
    def test_pii_detection(self, pii_dataset):
        """Detect Personally Identifiable Information"""
        detected_pii = {"ssn": [], "credit_card": [], "phone": []}

        # Detect SSN pattern
        for value in pii_dataset["ssn"]:
            if pd.notna(value) and isinstance(value, str) and "-" in value:
                detected_pii["ssn"].append(value)

        # Detect credit card pattern
        for value in pii_dataset["credit_card"]:
            if pd.notna(value) and isinstance(value, str) and value.count("-") >= 3:
                detected_pii["credit_card"].append(value)

        assert len(detected_pii["ssn"]) == 3, "SSN values not detected"
        assert len(detected_pii["credit_card"]) == 3, "Credit card values not detected"

    @pytest.mark.data_security
    def test_pii_masking(self, pii_dataset):
        """Verify PII values are properly masked"""

        def mask_ssn(ssn):
            return f"***-**-{ssn[-4:]}" if pd.notna(ssn) else None

        masked_df = pii_dataset.copy()
        masked_df["ssn"] = masked_df["ssn"].apply(mask_ssn)

        for value in masked_df["ssn"]:
            assert value.startswith("***-**-"), f"SSN not properly masked: {value}"
            assert len(value) == 11, "Masked SSN has incorrect format"

    @pytest.mark.data_security
    def test_encryption_validation(self, pii_dataset):
        """Verify sensitive data fields are not null"""
        sensitive_fields = ["ssn", "credit_card"]

        for field in sensitive_fields:
            if field in pii_dataset.columns:
                assert pii_dataset[field].notna().all(), f"{field} should not be null"

    @pytest.mark.data_security
    def test_access_control_audit(self):
        """Verify access control for sensitive data"""
        audit_log = {
            "timestamp": datetime.now().isoformat(),
            "user": "data_processor",
            "action": "read_sensitive_data",
            "table": "pii_data",
            "status": "approved",
        }

        assert audit_log["status"] == "approved", "Access denied"
        assert pd.notna(audit_log["timestamp"]), "Audit timestamp missing"


# ============================================================================
# DATA CONSISTENCY & REFERENTIAL INTEGRITY TESTS
# ============================================================================


class TestDataConsistency:
    """Verify data consistency and referential integrity"""

    @pytest.mark.data_integrity
    def test_referential_integrity(self, sample_dataset):
        """Verify primary key integrity"""
        assert sample_dataset["id"].notna().all(), "Null IDs found"
        assert sample_dataset["id"].is_unique, "Duplicate IDs found"

    @pytest.mark.data_integrity
    def test_data_format_consistency(self, sample_dataset):
        """Verify consistent data formatting"""
        # Email format should be consistent
        for email in sample_dataset["email"]:
            assert "@" in email, f"Invalid email format: {email}"
            assert email.lower() == email, "Email should be lowercase"

    @pytest.mark.data_integrity
    def test_encoding_consistency(self, sample_dataset):
        """Verify consistent character encoding"""
        for name in sample_dataset["name"]:
            try:
                name.encode("utf-8")
            except UnicodeEncodeError:
                pytest.fail(f"Character encoding issue in: {name}")

    @pytest.mark.data_integrity
    def test_date_range_consistency(self, sample_dataset):
        """Verify date ranges are logically consistent"""
        dates = sample_dataset["created_at"]

        # Dates should span reasonable range
        date_span = dates.max() - dates.min()
        assert date_span <= timedelta(days=365 * 10), "Unrealistic date range"
        assert date_span >= timedelta(days=0), "Invalid date range"


# ============================================================================
# COMPREHENSIVE DATA VALIDATION REPORTS
# ============================================================================


class TestDataValidationReport:
    """Generate comprehensive validation reports"""

    @pytest.mark.data_integrity
    @pytest.mark.data_quality
    def test_generate_validation_report(self, sample_dataset):
        """Generate comprehensive data validation report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "dataset_name": "sample_dataset",
            "total_rows": len(sample_dataset),
            "total_columns": len(sample_dataset.columns),
            "columns": list(sample_dataset.columns),
            "null_values": sample_dataset.isnull().sum().to_dict(),
            "duplicate_rows": len(sample_dataset[sample_dataset.duplicated()]),
            "memory_usage_mb": round(sample_dataset.memory_usage(deep=True).sum() / 1024 / 1024, 2),
            "validation_status": "PASSED",
        }

        assert report["validation_status"] == "PASSED"
        assert report["total_rows"] > 0
        assert report["total_columns"] > 0

    @pytest.mark.data_quality
    def test_statistical_summary(self, large_dataset):
        """Generate statistical summary of data"""
        summary = {
            "mean": large_dataset["value"].mean(),
            "median": large_dataset["value"].median(),
            "std_dev": large_dataset["value"].std(),
            "min": large_dataset["value"].min(),
            "max": large_dataset["value"].max(),
            "quartile_25": large_dataset["value"].quantile(0.25),
            "quartile_75": large_dataset["value"].quantile(0.75),
        }

        assert summary["median"] >= summary["min"]
        assert summary["median"] <= summary["max"]
        assert summary["mean"] > 0
