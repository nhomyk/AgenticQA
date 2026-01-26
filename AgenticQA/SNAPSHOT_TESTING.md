# Snapshot Testing for Data Quality

## Overview

Snapshot testing is a critical feature of AgenticQA that ensures **data accuracy, correctness, and consistency** across all deployments. Each time your pipeline runs, snapshots capture the exact outputs from your agents and data store, then compare future runs against these baselines to detect any unintended changes.

## Why Snapshots Matter

**Without Snapshots:**
- ❌ Silent data corruption goes undetected
- ❌ Agent behavior changes without warning
- ❌ Quality regressions are discovered too late
- ❌ Compliance audits reveal inconsistencies

**With Snapshots:**
- ✅ Catch data changes immediately
- ✅ Ensure agent outputs remain consistent
- ✅ Prevent quality regressions
- ✅ Maintain compliance audit trails
- ✅ Detect performance degradation

## How It Works

### 1. Baseline Creation

First run captures initial snapshots:
```python
from agenticqa import AgentOrchestrator, SnapshotManager

orchestrator = AgentOrchestrator()
results = orchestrator.execute_all_agents(test_data)

manager = SnapshotManager()
manager.create_snapshot("qa_baseline", results["qa_agent"])
```

**Snapshot stored as:**
```json
{
  "timestamp": "2026-01-26T10:30:00.000Z",
  "name": "qa_baseline",
  "hash": "a3f5c21e4d9b8f1c2e3a4b5c6d7e8f9...",
  "data": { ... }
}
```

### 2. Verification

Subsequent runs compare against baseline:
```python
comparison = manager.compare_snapshot("qa_baseline", new_results["qa_agent"])

if comparison["matches"]:
    print("✅ QA output unchanged")
else:
    print(f"❌ Changes detected: {comparison['differences']}")
```

### 3. Deployment Decision

Snapshots inform deployment safety:
- ✅ **All match**: Safe to deploy
- ⚠️ **Some changes**: Review and approve
- ❌ **Major changes**: Block deployment

## Key Features

### SHA256 Hashing
Each snapshot includes a unique hash:
```python
snapshot_hash = "a3f5c21e4d9b8f1c2e3a4b5c6d7e8f9..."  # 64-char SHA256
```

Identical outputs produce identical hashes. Any change produces different hash.

### Difference Detection
When snapshots don't match, detailed differences are reported:
```python
{
  "only_in_stored": {...},     # Fields that disappeared
  "only_in_current": {...},    # New fields added
  "changed_values": {          # Fields with different values
    "status": {
      "stored": "passed",
      "current": "failed"
    }
  }
}
```

### Snapshot Storage
Snapshots are stored as JSON files:
```
.snapshots/
├── qa_agent_output.json
├── performance_agent_output.json
├── compliance_agent_output.json
├── devops_agent_output.json
└── pipeline_execution.json
```

## Usage Examples

### Example 1: Basic Snapshot Testing

```python
from agenticqa import SnapshotManager, AgentOrchestrator

# Setup
manager = SnapshotManager(".snapshots/production")
orchestrator = AgentOrchestrator()

# Execute
results = orchestrator.execute_all_agents(test_data)

# Verify
for agent_name in ["qa_agent", "performance_agent", "compliance_agent", "devops_agent"]:
    output = results[agent_name]
    comparison = manager.compare_snapshot(f"{agent_name}_snapshot", output)
    
    if not comparison["matches"]:
        print(f"⚠️  {agent_name} output changed!")
        print(comparison["differences"])
```

### Example 2: Snapshot-Validated Pipeline

```python
from agenticqa import SnapshotValidatingPipeline

pipeline = SnapshotValidatingPipeline(".snapshots/pipeline")

# Execute with snapshot validation
results = pipeline.validate_with_snapshots(test_data)

# Generate report
report = pipeline.generate_validation_report(results)
print(report)

if not results["all_validations_passed"]:
    exit(1)  # Prevent deployment
```

### Example 3: Pytest Integration

```python
import pytest
from agenticqa import SnapshotManager, AgentOrchestrator

@pytest.fixture
def snapshot_manager():
    return SnapshotManager(".snapshots/tests")

def test_qa_agent_snapshot(snapshot_manager):
    """Ensure QA agent output remains consistent."""
    orchestrator = AgentOrchestrator()
    results = orchestrator.execute_all_agents(test_data)
    
    qa_output = results["qa_agent"]
    comparison = snapshot_manager.compare_snapshot("qa_output", qa_output)
    
    if comparison["status"] == "new":
        snapshot_manager.create_snapshot("qa_output", qa_output)
    else:
        assert comparison["matches"], f"QA output changed: {comparison['differences']}"
```

## Running Snapshot Tests

### Command Line

```bash
# Run all snapshot tests
pytest tests/test_pipeline_snapshots.py -v

# Run specific snapshot test
pytest tests/test_pipeline_snapshots.py::TestAgentOutputSnapshots::test_qa_agent_output_snapshot -v

# Run with snapshot markers
pytest -m snapshot -v
```

### In Your CI/CD Pipeline

```yaml
# GitHub Actions example
- name: Run snapshot tests
  run: |
    pip install pytest
    pytest tests/test_pipeline_snapshots.py -v
    
- name: Check snapshots
  run: python -m agenticqa.data_store.snapshot_manager --check
```

### With Example Script

```bash
# Run example with snapshot validation
python examples/snapshot_testing_example.py
```

## Understanding Snapshot Output

### ✅ Snapshot Matches (First Run)
```
✅ qa_agent: new
Snapshot created
```
Baseline is established.

### ✅ Snapshot Matches (Subsequent Runs)
```
✅ qa_agent: match
Tests: 5 passed, 0 failed
Status: passed
```
Everything is consistent. Safe to deploy.

### ⚠️ Snapshot Mismatch
```
❌ qa_agent: mismatch
Changed values:
  status: "passed" → "failed"
  tests_failed: 0 → 1
```
Something changed. Review and decide whether to:
- **Update snapshot** if the change is intentional
- **Revert code** if the change is unintended
- **Block deployment** until resolved

## When to Update Snapshots

Update snapshots when:
- ✅ You intentionally improved agent behavior
- ✅ You fixed a compliance issue
- ✅ You optimized performance significantly
- ✅ You updated test data intentionally

Don't update snapshots when:
- ❌ Something broke unexpectedly
- ❌ Data quality decreased
- ❌ Performance regressed
- ❌ You're unsure about the change

## Snapshot Best Practices

### 1. Version Control
Commit snapshots to git (in a `.snapshots/` directory):
```bash
git add .snapshots/
git commit -m "Update snapshots for new agent improvements"
```

### 2. Review Changes
Always review snapshot diffs before committing:
```bash
git diff .snapshots/qa_agent_output.json
```

### 3. Create Baselines
Establish baselines early and update deliberately:
```python
# First run creates baselines
manager.create_snapshot("qa_baseline", initial_results)
```

### 4. Monitor Trends
Track snapshot changes over time to identify patterns:
```python
snapshots = manager.get_all_snapshots()
print(f"Total snapshots: {len(snapshots)}")
```

### 5. Fail Fast
Configure CI/CD to fail if snapshots don't match:
```python
if not comparison["matches"]:
    raise AssertionError(f"Snapshot mismatch: {comparison['differences']}")
```

## Integration with Data Quality Testing

Snapshots work alongside the 10-point data quality test suite:

| Feature | Snapshots | Data Quality Tests |
|---------|-----------|-------------------|
| **Detects** | Output changes | Missing data, corruption |
| **Purpose** | Ensure consistency | Ensure integrity |
| **Triggers** | Compare hashes | Run validations |
| **Failing** | Block deployment | Alert + block |

Together they ensure **comprehensive quality assurance**.

## Troubleshooting

### Snapshot Files Keep Changing

**Problem:** Snapshots always show as different
```
status: mismatch
```

**Solution:** 
- Check for timestamp fields (exclude from snapshots)
- Verify random seeds are fixed
- Ensure test data is deterministic

```python
# Remove non-deterministic fields
snapshot_data = {
    k: v for k, v in results.items() 
    if k not in ["timestamp", "execution_id"]
}
```

### Snapshots Too Large

**Problem:** Snapshot files are huge
```
snapshot_output.json (5.2 MB)
```

**Solution:**
- Snapshot only critical fields
- Use separate snapshots for different concerns
- Compress snapshot data

### Snapshot Comparisons Failing Unexpectedly

**Problem:** Snapshots report mismatch despite no code changes

**Solution:**
- Check for floating-point precision issues
- Verify object ordering (use `sort_keys=True`)
- Review timestamp handling

## API Reference

### SnapshotManager

```python
manager = SnapshotManager(".snapshots")

# Create snapshot
hash = manager.create_snapshot("name", data)

# Compare snapshots
result = manager.compare_snapshot("name", current_data)
# Returns: {"matches": bool, "status": "match|mismatch|new", "differences": {...}}

# Get all snapshots
snapshots = manager.get_all_snapshots()

# Delete snapshot
manager.delete_snapshot("name")
```

### SnapshotValidatingPipeline

```python
pipeline = SnapshotValidatingPipeline(".snapshots")

# Validate with snapshots
results = pipeline.validate_with_snapshots(test_data)
# Returns: {"all_validations_passed": bool, "snapshots_validated": [...], ...}

# Generate report
report = pipeline.generate_validation_report(results)
```

## Next Steps

1. **Enable snapshots** in your pipeline
2. **Create baselines** for all agents
3. **Run tests** to ensure consistency
4. **Integrate with CI/CD** for automatic validation
5. **Monitor snapshots** for data quality trends

Snapshots are your safety net for data accuracy and quality! 🎯

