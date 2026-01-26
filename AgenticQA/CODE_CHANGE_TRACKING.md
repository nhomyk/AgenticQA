# Code Change Tracking with Before/After Snapshots

## Overview

Code change tracking is a **safety mechanism** that captures data state before and after code changes, analyzes metrics to detect improvements or degradation, and automatically **prevents risky deployments** through intelligent rollback.

This ensures developers can confidently deploy code changes knowing the system will catch regressions automatically.

## How It Works

### 5-Phase Safe Change Execution

```
Phase 1: CAPTURE BEFORE
  └─ Run agents, collect metrics baseline

Phase 2: APPLY CHANGE  
  └─ Execute code modification

Phase 3: CAPTURE AFTER
  └─ Run agents again, collect new metrics

Phase 4: ANALYZE IMPACT
  └─ Compare before/after metrics
  └─ Calculate deltas and improvements
  └─ Determine deployment safety

Phase 5: DECISION & ROLLBACK
  └─ ✅ Safe → Deploy change
  └─ ❌ Unsafe → Automatic rollback to before state
```

## Key Metrics Tracked

### Quality Score
```
Before: 85.0%
After:  92.0%
Delta:  +7.0%  ✅ Improved
```

### Performance (Execution Time)
```
Before: 150.0ms
After:  120.0ms
Delta:  +30.0ms  ✅ Faster
```

### Test Results
```
Before: 95 passed, 5 failed
After:  98 passed, 2 failed
Status: ✅ Improved
```

### Compliance Score
```
Before: 90.0%
After:  92.0%
Status: ✅ Maintained
```

## Deployment Safety Rules

### ✅ SAFE TO DEPLOY
- ✅ Quality improved AND tests improved
- ✅ Quality improved AND no compliance loss
- ✅ All metrics improved significantly

### ⚠️ REVIEW REQUIRED
- ⚠️ Mixed results (some better, some worse)
- ⚠️ Minor quality loss but tests improved
- ⚠️ Performance slower but quality much better

### ❌ AUTOMATIC ROLLBACK
- ❌ Tests failing after change
- ❌ Compliance score decreased
- ❌ Quality degraded significantly (>10%)
- ❌ Any safety/security metric decreased

## Usage Examples

### Example 1: Basic Safe Change Execution

```python
from agenticqa import SafeCodeChangeExecutor

executor = SafeCodeChangeExecutor()
agent = MyAgent()

def apply_optimization():
    agent.optimize_algorithm()

def rollback():
    agent.restore_original()

results = executor.execute_safe_change(
    change_name="optimize_qa_agent",
    test_data=test_data,
    change_function=apply_optimization,
    rollback_function=rollback,
)

if results["safe_to_deploy"]:
    print("✅ Change is safe - deployed!")
else:
    print(f"❌ Change blocked: {results['reason']}")
```

### Example 2: Manual Before/After Snapshots

```python
from agenticqa import CodeChangeTracker, AgentOrchestrator

tracker = CodeChangeTracker()
orchestrator = AgentOrchestrator()

# Capture BEFORE
before_results = orchestrator.execute_all_agents(test_data)
change_id = tracker.start_change("my_optimization", before_results)

# Apply change
apply_code_change()

# Capture AFTER
after_results = orchestrator.execute_all_agents(test_data)
analysis = tracker.end_change(after_results, change_id)

# Review impact
from agenticqa import ChangeImpactReport
report = ChangeImpactReport.generate_report(analysis)
print(report)
```

### Example 3: Track Multiple Changes

```python
from agenticqa import CodeChangeTracker, ChangeHistoryAnalyzer

tracker = CodeChangeTracker()
analyzer = ChangeHistoryAnalyzer(tracker)

# Show statistics
stats = analyzer.get_change_statistics()
print(f"Success rate: {stats['success_rate']:.1f}%")
print(f"Avg quality delta: {stats['average_quality_delta']:+.1f}%")

# Generate summary
summary = analyzer.generate_summary_report()
print(summary)
```

## Understanding the Impact Report

```
================================================================================
📊 CODE CHANGE IMPACT ANALYSIS REPORT
================================================================================

Change: optimize_qa_agent
Timestamp: 2026-01-26T10:30:00

Verdict: ✅ SAFE TO DEPLOY
Reason: ✅ All metrics improved - safe to deploy

📈 QUALITY METRICS:
  Before: 85.0%
  After:  92.0%
  Delta:  +7.0%
  Status: ✅ Improved

⚡ PERFORMANCE METRICS:
  Before: 150.00ms
  After:  120.00ms
  Delta:  +30.00ms
  Status: ✅ Faster

✔️ TEST METRICS:
  Before: 95 passed, 5 failed
  After:  98 passed, 2 failed
  Status: ✅ Improved

🔒 COMPLIANCE:
  Before: 90.0%
  After:  92.0%
  Status: ✅ Maintained

================================================================================
```

## Storage Structure

Changes are stored with full audit trail:

```
.code_changes/
├── optimize_qa_agent_20260126_103000_before.json    # Before snapshot
├── optimize_qa_agent_20260126_103000_after.json     # After snapshot
└── optimize_qa_agent_20260126_103000_analysis.json  # Impact analysis
```

Each file includes:
- Timestamp
- Data snapshot
- SHA256 hash
- All metrics

## Integration with CI/CD

### GitHub Actions

```yaml
- name: Validate code changes
  run: |
    python -c "
    from agenticqa import SafeCodeChangeExecutor
    executor = SafeCodeChangeExecutor()
    results = executor.execute_safe_change(...)
    exit(0 if results['safe_to_deploy'] else 1)
    "
```

### GitLab CI

```yaml
validate_changes:
  script:
    - python examples/code_change_tracking_example.py
  allow_failure: false
```

### Jenkins

```groovy
stage('Validate Changes') {
    steps {
        sh '''
            python -m pytest tests/test_code_change_tracking.py -v
        '''
    }
}
```

## Automatic Rollback Examples

### Scenario 1: Quality Degradation

```python
# Before: 85% quality
# After:  70% quality (15% drop)

Analysis:
  Quality degraded significantly (−15.0%)
  → Automatic rollback triggered
  → System restored to before state
  → ❌ Deployment blocked
```

### Scenario 2: Test Failures

```python
# Before: 5 tests failed
# After:  25 tests failed

Analysis:
  Tests failing after change - 25 failures detected
  → Automatic rollback triggered
  → System restored to before state
  → ❌ Deployment blocked
```

### Scenario 3: Compliance Risk

```python
# Before: 90% compliance
# After:  75% compliance

Analysis:
  Compliance score decreased - security risk
  → Automatic rollback triggered
  → System restored to before state
  → ❌ Deployment blocked
```

## API Reference

### CodeChangeTracker

```python
tracker = CodeChangeTracker(".code_changes")

# Start tracking
change_id = tracker.start_change("my_change", before_metrics)

# End tracking
analysis = tracker.end_change(after_metrics, change_id)

# Retrieve analysis
analysis = tracker.get_change_analysis(change_id)

# List all changes
changes = tracker.list_changes()

# Rollback
tracker.rollback_change(restore_function)
```

### SafeCodeChangeExecutor

```python
executor = SafeCodeChangeExecutor()

# Execute with validation
results = executor.execute_safe_change(
    change_name="my_change",
    test_data=test_data,
    change_function=my_change_func,
    rollback_function=my_rollback_func,
    allow_performance_regression=False,
)
```

### ChangeHistoryAnalyzer

```python
analyzer = ChangeHistoryAnalyzer(tracker)

# Get statistics
stats = analyzer.get_change_statistics()

# Generate report
report = analyzer.generate_summary_report()
```

### BeforeAfterMetrics

```python
metrics = BeforeAfterMetrics(
    change_name="my_change",
    before_quality_score=85.0,
    after_quality_score=92.0,
    # ... other metrics
)

# Convert to dictionary
data = metrics.to_dict()

# Convert to JSON
json_str = metrics.to_json()
```

## Best Practices

### 1. Always Define Rollback Function
```python
def rollback():
    agent.restore_original()  # Must restore to before state

executor.execute_safe_change(
    ...,
    rollback_function=rollback,
)
```

### 2. Use Meaningful Change Names
```python
# Good
"optimize_qa_algorithm_v2"
"fix_compliance_false_positive"
"refactor_performance_agent"

# Avoid
"change1"
"update"
"test_change"
```

### 3. Monitor Historical Trends
```python
analyzer = ChangeHistoryAnalyzer(tracker)
stats = analyzer.get_change_statistics()

if stats["success_rate"] < 80:
    alert("High failure rate detected in code changes")
```

### 4. Review Blocked Changes
```python
for change_id in tracker.list_changes():
    analysis = tracker.get_change_analysis(change_id)
    if not analysis["safe_to_deploy"]:
        print(f"Investigate: {change_id}")
        print(f"Reason: {analysis['reason']}")
```

## Troubleshooting

### Change Metrics Not Capturing

**Problem**: Before/after metrics are the same

**Solution**:
- Ensure test data is deterministic
- Verify change function is being executed
- Check that agents are actually being run

```python
def apply_change():
    print("Applying change...")  # Verify execution
    agent.optimize()
    print("Change applied!")
```

### Unexpected Rollbacks

**Problem**: Safe changes are being rolled back

**Solution**:
- Review the impact report to see what metric failed
- Adjust thresholds if needed
- Check compliance score tracking

```python
analysis = tracker.get_change_analysis(change_id)
print(analysis["reason"])  # Shows why it was rolled back
```

### Large Change ID Directories

**Problem**: Too many change files accumulating

**Solution**:
- Archive old changes periodically
- Use cleanup script
- Implement retention policy

## Next Steps

1. **Enable change tracking** for all code deployments
2. **Define rollback functions** for critical agents
3. **Monitor success rates** with history analyzer
4. **Integrate with CI/CD** for automated validation
5. **Review blocked changes** to improve code quality

Before/After snapshots are your **deployment safety net** — they prevent regressions automatically! 🛡️

