# Change Detection & Pipeline Re-Run Workflow

## Overview
Both the **Fullstack Agent** and **SRE Agent** now implement intelligent change detection to avoid unnecessary pipeline re-runs.

## Change Detection Logic

### Fullstack Agent (`fullstack-agent.js`)
**When to Re-Run:**
- ✅ Only triggers pipeline re-run if code changes are committed and pushed
- ✅ Checks `git status --porcelain` to detect actual file modifications
- ✅ No re-run if no changes are needed (e.g., tests already passing)

**Behavior:**
```
1. Scan source files & code quality
2. Run code coverage analysis
3. Generate missing tests if needed
4. Add & commit changes (if any)
5. Only if changes exist:
   - Push to main branch
   - Trigger new pipeline
   - Display: "PIPELINE RE-RUN TRIGGERED"
6. If no changes:
   - Skip push and re-run
   - Display: "NO PIPELINE RE-RUN TRIGGERED"
   - Exit successfully
```

### SRE Agent (`agentic_sre_engineer.js`)
**When to Re-Run:**
- ✅ Only runs code fixes if test failures are detected
- ✅ Tracks `codeChangesApplied` flag during fix iterations
- ✅ Only triggers re-run if changes are successfully pushed
- ✅ Early exit if no failures found (`failureAnalysis.length === 0`)

**Behavior:**
```
1. Fetch failed job logs from pipeline
2. If no failures:
   - Log: "No failures found to analyze"
   - Exit early (no changes, no re-run)
3. If failures found:
   - Bump version
   - Iteratively apply code fixes
   - If changes committed & pushed:
     - Set codeChangesApplied = true
     - Trigger pipeline re-run
   - If no changes made:
     - codeChangesApplied = false
     - No re-run triggered
4. Final summary:
   - Display code change status
   - Display re-run status
```

## Benefits

1. **Efficiency**: No wasted pipeline runs when nothing changed
2. **Cost Reduction**: Fewer unnecessary CI/CD executions
3. **Smart Iteration**: Tests pass → no re-run; tests fail → fix & re-run once
4. **Clear Logging**: Always shows whether changes were made and if re-run was triggered

## Implementation Details

### Fullstack Agent
- Uses `git status --porcelain` to check for staged/unstaged changes
- Exit early with no re-run if `statusOutput.trim().length === 0`
- Only calls `triggerNewPipeline()` if changes exist

### SRE Agent
- Checks `failureAnalysis.length === 0` for early exit
- Sets `codeChangesApplied = true` when changes are pushed
- Displays final summary with change and re-run status

## Pipeline Flow Example

### Scenario 1: Tests Pass, No Fixes Needed
```
Fullstack Agent checks code coverage → No issues found
                          ↓
                    No changes made
                          ↓
                    Exit successfully
                          ↓
            NO PIPELINE RE-RUN TRIGGERED ✓
```

### Scenario 2: Tests Fail, SRE Fixes Issues
```
Pipeline runs → Tests fail
            ↓
    SRE Agent analyzes failures
            ↓
    Fixes applied & committed
            ↓
    Changes pushed to main
            ↓
    PIPELINE RE-RUN TRIGGERED ✓
            ↓
    New pipeline run validates fixes
```

### Scenario 3: Fullstack Agent Adds Missing Tests
```
Fullstack Agent scans coverage
            ↓
    Missing tests detected
            ↓
    Tests generated & committed
            ↓
    Changes pushed to main
            ↓
    PIPELINE RE-RUN TRIGGERED ✓
            ↓
    New tests run in pipeline
```

## Workflow Sequence

1. **Initial Pipeline Run**
   - All tests execute
   - Coverage analyzed
   - Jobs complete

2. **SRE Agent Analysis** (if failures detected)
   - Analyzes failed job logs
   - Applies code fixes
   - Commits changes (if any)
   - Triggers re-run (if changes made)

3. **Fullstack Agent Validation** (after initial suite)
   - Verifies code quality
   - Generates test coverage
   - Triggers re-run (if changes made)

## Monitoring

Check the following for change detection status:

### In SRE Agent Output:
```
=== SRE AGENT SUMMARY ===
✅ CODE CHANGES DETECTED
✅ WORKFLOW RE-RUN: TRIGGERED
```

or

```
=== SRE AGENT SUMMARY ===
ℹ️ NO CODE CHANGES MADE
ℹ️ NO RE-RUN TRIGGERED
```

### In Fullstack Agent Output:
```
ℹ️  NO CODE CHANGES MADE
ℹ️  NO PIPELINE RE-RUN TRIGGERED
```

or

```
✓ PIPELINE RE-RUN TRIGGERED
```

## Related Files

- `fullstack-agent.js` - Change detection on commit push
- `agentic_sre_engineer.js` - Change tracking during fix iterations
- `.github/workflows/` - Pipeline definitions
