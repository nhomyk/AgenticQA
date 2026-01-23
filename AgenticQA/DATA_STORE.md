# Data Store - Secure Test Artifact Repository

A comprehensive data validation and storage system for test execution artifacts and agent results with deep security checks.

## 🏗️ Architecture

```
Pre-Deployment
    ↓
[Great Expectations] → Validate input data
    ↓ (store result in Test Artifact Store)
[Agent Execution]    → Run transformation (traced by OpenTelemetry)
    ↓ (store execution in Test Artifact Store)
[Great Expectations] → Validate output data
    ↓ (store result in Test Artifact Store)
[Integrity Checks]   → Compare pre/post snapshots
    ↓ (store check result in Test Artifact Store)
[Dagster Asset]      → Register asset lineage
    ↓ (store in asset graph)
[Test Artifact Store] → Unified index of all artifacts
```

## 📦 Storage Layers

### 1. **Test Artifact Store** (Primary - Unstructured)
- Location: `.test-artifact-store/`
- Stores raw execution data, metadata, and analysis patterns
- Master index for searchable access
- SHA256 checksums for integrity verification

### 2. **Great Expectations** (Data Quality)
- Validates schema compliance, null checks, value constraints
- Stores validation results in `great_expectations/`
- Pre/post execution validation

### 3. **Security Validation** (Deep Integrity)
- PII detection (email, SSN, credit card, API keys)
- Schema compliance validation
- Data immutability checks
- Encryption readiness verification

### 4. **Pattern Analysis** (Intelligence)
- Failure pattern detection
- Performance trend analysis
- Flakiness identification
- Compiled data insights for smarter agents

## 🚀 Quick Start

```python
from src.data_store import SecureDataPipeline

# Initialize pipeline
pipeline = SecureDataPipeline()

# Execute with full validation
execution_result = {
    "timestamp": "2026-01-23T10:00:00.000Z",
    "agent_name": "QA_Assistant",
    "status": "success",
    "output": {"test_count": 42, "passed": 40}
}

success, result = pipeline.execute_with_validation(
    "QA_Assistant",
    execution_result
)

if success:
    # Analyze accumulated patterns
    patterns = pipeline.analyze_patterns()
```

## 🔐 Security Features

- ✅ **Immutability**: SHA256 checksums on all stored data
- ✅ **PII Detection**: Automatic scanning for sensitive data
- ✅ **Schema Validation**: Type checking and required field enforcement
- ✅ **Integrity Verification**: Detect tampering on retrieval
- ✅ **Encryption Ready**: All data can be encrypted before storage

## 📊 Files

- `artifact_store.py` - Central repository for artifacts
- `great_expectations_validator.py` - Data quality validation
- `security_validator.py` - Deep security checks
- `pattern_analyzer.py` - Pattern discovery and analysis
- `secure_pipeline.py` - Complete validation workflow

## 🔄 Usage Example

See `example_data_store_usage.py` for full implementation.
