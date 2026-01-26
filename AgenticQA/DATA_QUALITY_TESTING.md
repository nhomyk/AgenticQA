# Data Quality Testing - Ensuring Consistency Across Deployments

Comprehensive data quality testing suite ensuring data integrity, consistency, and reliability across all deployments.

## 🎯 Overview

The data quality testing system validates:
- ✅ Artifact integrity with SHA256 checksums
- ✅ Schema consistency across all metadata
- ✅ No duplicate artifacts
- ✅ Metadata completeness
- ✅ Index accuracy
- ✅ Data immutability (same on every read)
- ✅ PII protection and scanning
- ✅ Temporal consistency (no future dates, reasonable timeframes)
- ✅ Cross-deployment consistency
- ✅ Deployment readiness

## 📊 Test Suite

### 10 Comprehensive Tests

1. **Artifact Integrity** - Verify all artifacts pass integrity checks
2. **Checksum Validation** - Validate SHA256 checksums on all artifacts
3. **Schema Consistency** - Ensure consistent metadata schema
4. **No Duplicates** - Verify no duplicate artifact IDs
5. **Metadata Completeness** - All required metadata fields present
6. **Index Accuracy** - Index matches actual artifacts
7. **Data Immutability** - Data unchanged on multiple reads
8. **PII Protection** - No exposed personal information
9. **Temporal Consistency** - Timestamps are valid and reasonable
10. **Cross-Deployment Consistency** - Consistency for multi-environment reliability

## 🚀 Pipeline Integration

### Pre-Execution Data Quality Check

Validates input data BEFORE agents process it:

```python
from src.data_store.data_quality_pipeline import DataQualityValidatedPipeline

pipeline = DataQualityValidatedPipeline()

# Pre-execution validation
input_data = {
    "timestamp": "2026-01-23T10:00:00Z",
    "data": {"test_count": 150}
}

is_valid, result = pipeline.validate_input_data("QA_Assistant", input_data)
# Runs: schema validation, PII check, encryption readiness, snapshots data
```

### Post-Execution Data Quality Check

Validates output data AFTER agents process it:

```python
# Post-execution validation
execution_result = {
    "timestamp": "2026-01-23T10:00:00Z",
    "agent_name": "QA_Assistant",
    "status": "success",
    "output": {...}
}

is_valid, result = pipeline.execute_with_validation("QA_Assistant", execution_result)
# Runs: all 10 data quality tests, snapshot comparison, exports results
```

### Deployment Validation

Complete validation before deploying:

```python
deployment_result = pipeline.run_deployment_validation()
# Returns: ready_for_deployment boolean and detailed audit trail
```

## 📈 Data Flow with Quality Testing

```
Input Data
    ↓
[Pre-Execution Quality Checks]
    ↓
Agent Execution
    ↓
[Post-Execution Quality Tests - All 10 Tests]
    ↓
Data Storage & Integrity Verification
    ↓
Quality Report Export
    ↓
Ready for Deployment?
```

## 🔍 Data Quality Test Examples

```python
from src.data_store.data_quality_pipeline import DataQualityValidatedPipeline

# Create pipeline with quality testing enabled
pipeline = DataQualityValidatedPipeline(run_quality_tests=True)

# 1. Pre-execution quality check
is_valid, result = pipeline.validate_input_data("agent", input_data)
if "quality_tests" in result:
    quality = result["quality_tests"]
    print(f"Quality: {quality['summary']['passed']}/{quality['summary']['total_tests']} passed")

# 2. Post-execution quality check
is_valid, result = pipeline.execute_with_validation("agent", execution_result)
if "post_execution_quality" in result:
    quality = result["post_execution_quality"]
    if quality["summary"]["all_passed"]:
        print("✓ All data quality tests passed!")
    else:
        print(f"✗ {quality['summary']['failed']} tests failed")

# 3. Deployment validation
deployment = pipeline.run_deployment_validation()
if deployment["ready_for_deployment"]:
    print("✓ Ready for deployment to production")
else:
    print("✗ Not ready for deployment")
```

## 📋 Quality Test Results Export

All test results are automatically exported to:
- `.test-artifact-store/patterns/data_quality_test_results.json`

Contains:
- Timestamp of test run
- Individual test results with pass/fail status
- Detailed failure messages
- Summary statistics
- Deployment readiness determination

## 🛡️ Security in Quality Testing

- ✅ PII scanning with regex patterns (email, SSN, credit card, API keys)
- ✅ Checksum validation prevents tampering detection
- ✅ Immutability testing ensures data hasn't been modified
- ✅ Schema validation prevents data corruption
- ✅ Cross-deployment consistency ensures replicas match

## 📊 Deployment Readiness Criteria

Deployment is ready when:
1. ✓ All 10 data quality tests pass
2. ✓ All artifacts are accessible
3. ✓ Pattern analysis completes successfully
4. ✓ No PII leakage detected
5. ✓ Checksums validate on 100% of artifacts

## 🚀 Integration with Agents

Agents automatically use quality-validated pipeline:

```python
from src.agents import QAAssistantAgent

# Agent automatically runs quality checks
qa_agent = QAAssistantAgent()
result = qa_agent.execute(test_results)
# Runs pre/post quality validation automatically
```

## 📈 Continuous Quality Assurance

```python
# Run continuous quality checks
pipeline = DataQualityValidatedPipeline()
deployment_result = pipeline.run_deployment_validation()

if deployment_result["ready_for_deployment"]:
    # Safe to deploy
    deploy_to_production()
else:
    # Show failures and fix before deploying
    print(deployment_result["checks"]["data_quality"]["tests"])
```

## 🎯 For Production

This quality testing suite ensures:
- 🔒 **Data Integrity**: SHA256 checksums prevent tampering
- 📊 **Consistency**: All deployments see identical data
- 🛡️ **Security**: PII protection and leak detection
- ✓ **Reliability**: 10-point validation before deployment
- 📈 **Audit Trail**: Complete test history for compliance
- 🚀 **Confidence**: Deploy with certainty across environments

Run examples:
```bash
python example_data_quality_testing.py
```
