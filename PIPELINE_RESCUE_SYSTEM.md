# 🆘 CRITICAL PIPELINE RESCUE SYSTEM

## Problem Statement

The pipeline entered a critical failure state where:
1. **YAML syntax error** broke the main CI workflow
2. **SRE Agent couldn't help** - it never gets triggered if workflow is broken
3. **No recovery mechanism** existed - pipeline was stuck in failed state
4. **Manual intervention required** every time YAML broke

**Root Cause**: Multiline strings in git commit messages within workflow YAML were improperly formatted, breaking YAML parsing entirely.

## Solution Architecture

### Three-Layer Defense System

```
LAYER 1: Pipeline Rescue (Phase -1)
├─ Independent workflow (runs even if main is broken)
├─ Runs on push + every 5 minutes (cron)
├─ Detects pipeline health
├─ Triggers automated repairs
└─ Creates emergency issues if unfixable

LAYER 2: Main CI Workflow (Phase 0+)
├─ Linting Fix (auto-fix issues early)
├─ Tests & Compliance (Phases 1+)
├─ SRE Agent (Phase 3 - monitoring)
└─ Health Check (Final gate - detects loops)

LAYER 3: Circuit Breaker
├─ Limits repair attempts to 3 per hour
├─ Prevents infinite loops
├─ Creates issues for manual intervention
└─ Fails safely if too many attempts
```

## Components

### 1. Pipeline Rescue Workflow (`.github/workflows/pipeline-rescue.yml`)

**Purpose**: Independent health monitor that runs FIRST

**Features**:
- ✅ Runs independently even if main CI is broken
- ✅ Detects if main workflow is in FAILURE state
- ✅ Validates all workflow YAML files
- ✅ Runs automated repairs if broken
- ✅ Creates emergency issues for manual intervention
- ✅ Runs on push + every 5 minutes (fail-fast)

**When it runs**:
- Every push to main
- Every 5 minutes (cron schedule)
- Can be manually triggered

**What it checks**:
- Latest workflow status
- YAML syntax validity
- Repair success/failure
- Creates GitHub issue if unfixable

### 2. Repair Workflow Script (`repair-workflow.js`)

**Purpose**: Smart automated YAML repair system

**Repair Capabilities**:
- ✅ Fixes multiline string formatting
- ✅ Corrects YAML indentation errors
- ✅ Detects and removes circular job dependencies
- ✅ Validates GitHub Actions expressions
- ✅ Checks for missing required job fields

**Circuit Breaker**:
- Tracks repair attempts (max 3 per hour)
- Prevents infinite repair loops
- Reports unfixable issues clearly
- Auto-resets after 1 hour of success

**Output**:
- Auto-commits fixes to main
- Reports what was fixed
- Flags unfixable issues
- Prevents cascading failures

### 3. Main CI Workflow Enhancements (`.github/workflows/ci.yml`)

**New Final Gate Job**: `pipeline-health-check`

**Features**:
- ✅ Validates all workflow YAML files
- ✅ Detects infinite repair loops
- ✅ Reports pipeline health status
- ✅ Prevents broken workflows from propagating
- ✅ Provides clear diagnostics

**How it works**:
1. Waits for all other jobs to complete
2. Validates workflow files are syntactically correct
3. Checks for too many consecutive repairs
4. Reports status to GitHub Step Summary
5. Fails safely if issues detected (doesn't cascade)

## Workflow Execution Flow

### Scenario 1: Healthy Pipeline (Normal Flow)

```
PUSH TO MAIN
    ↓
Pipeline Rescue (✅ healthy)
    ↓
Main CI Workflow
  └─ Phase 0: Linting Fix (✅)
  └─ Phase 1: Tests (✅)
  └─ Phase 2: Fullstack Agent (✅)
  └─ Phase 3: SRE Agent (✅)
  └─ Final Gate: Health Check (✅)
    ↓
PIPELINE SUCCESS
```

### Scenario 2: YAML Broken (Rescue Triggered)

```
PUSH WITH BROKEN YAML
    ↓
Pipeline Rescue (🚨 detects failure)
    ↓
Auto-Repair System (repair-workflow.js)
  └─ Fix YAML syntax
  └─ Commit repairs
  └─ Push to main
    ↓
Main CI triggered again (with fixed YAML)
    ↓
PIPELINE RECOVERS
```

### Scenario 3: Unfixable Issue (Manual Intervention)

```
PUSH WITH UNFIXABLE ISSUE
    ↓
Pipeline Rescue (🚨 detects failure)
    ↓
Auto-Repair System (cannot fix)
    ↓
Circuit Breaker (too many attempts)
    ↓
Create Emergency Issue
    ↓
MANUAL ACTION REQUIRED
```

## Critical Improvements

### Before (Without Rescue System)

- ❌ YAML error breaks workflow
- ❌ All jobs skipped
- ❌ SRE Agent never runs
- ❌ Manual fix required
- ❌ Manual push required
- ❌ Manual retry required
- 🕐 **Downtime: ~30+ minutes**

### After (With Rescue System)

- ✅ YAML error detected immediately
- ✅ Repairs applied automatically
- ✅ All tests can proceed
- ✅ SRE Agent gets triggered
- ✅ No manual action needed
- ✅ Full pipeline completes
- 🕐 **Downtime: ~0-2 minutes**

## Key Features

### 1. **Independent Rescue Workflow**
- Runs completely independently of main CI
- Triggers even if main workflow fails to load
- Can detect and fix main workflow issues
- Prevents hard lock-ups

### 2. **Automated YAML Repair**
- Detects common YAML syntax errors
- Fixes multiline string issues
- Corrects indentation problems
- Removes circular dependencies

### 3. **Circuit Breaker Pattern**
- Prevents infinite repair loops
- Tracks repair attempts per hour
- Creates emergency issue after 3 attempts
- Auto-resets after 1 hour of stability

### 4. **Health Verification Gate**
- Final check in main pipeline
- Validates all workflows before declaring success
- Detects repair loop conditions
- Reports comprehensive status

### 5. **Emergency Alerting**
- Creates GitHub issues for unfixable problems
- Assigns to PR author
- Provides diagnostic information
- Links to workflow logs

## Configuration

### Environment Variables

```
GH_TOKEN: Automatically provided by GitHub Actions
```

### Required Permissions

In `pipeline-rescue.yml`:
```yaml
permissions:
  contents: write    # To commit repairs
  actions: write     # To check workflow status
```

### Cron Schedule

The Pipeline Rescue runs every 5 minutes:
```yaml
schedule:
  - cron: '*/5 * * * *'
```

## Usage

### Normal Operation

The system works automatically - no action needed!

- Every push triggers Pipeline Rescue
- Every 5 minutes cron checks pipeline health
- Repairs happen automatically if needed

### Manual Trigger

If needed, manually trigger the rescue workflow:

```bash
gh workflow run pipeline-rescue.yml
```

### Disable Rescue (Not Recommended)

To temporarily disable automatic rescue:
```bash
gh workflow disable .github/workflows/pipeline-rescue.yml
```

To re-enable:
```bash
gh workflow enable .github/workflows/pipeline-rescue.yml
```

## Diagnostics

### Check Repair Marker

```bash
cat .workflow-repair-marker
```

Shows:
- Current repair attempt count
- Last attempt timestamp
- Can help track repair history

### Validate Workflows

```bash
npm install -g js-yaml
js-yaml .github/workflows/ci.yml
js-yaml .github/workflows/pipeline-rescue.yml
```

### Check Rescue Logs

1. Go to: `https://github.com/nhomyk/AgenticQA/actions/workflows/pipeline-rescue.yml`
2. Click latest run
3. Check "Pipeline Health Check & Emergency Repair" job
4. Review logs and step summary

### Check Repair History

```bash
git log --oneline | grep -i "repair\|auto-fix"
```

## Emergency Procedures

### If Pipeline is Stuck

1. **Check Rescue Status**:
   - Go to Actions → Pipeline Rescue
   - See if latest run is healthy

2. **Manual Repair Option**:
   ```bash
   npm install -g js-yaml
   js-yaml .github/workflows/ci.yml
   ```
   Fix any reported errors

3. **Check Repair Marker**:
   ```bash
   cat .workflow-repair-marker
   ```
   If repair count is high, circuit breaker may have triggered

4. **Reset Repair Marker** (if truly stuck):
   ```bash
   rm .workflow-repair-marker
   git add .workflow-repair-marker
   git commit -m "reset: Clear repair marker to retry"
   git push
   ```

5. **Last Resort - Revert**:
   ```bash
   git revert HEAD
   git push
   ```

## Monitoring

### What to Watch

1. **Pipeline Rescue runs**:
   - Check `github.com/repo/actions/workflows/pipeline-rescue.yml`
   - Should see recent runs (every 5 minutes)

2. **Repair commits**:
   ```bash
   git log --oneline | grep "repair\|auto-fix"
   ```
   - Should be minimal in healthy state
   - Increase during active development

3. **Emergency issues**:
   - Check Issues tab for "CRITICAL" label
   - These indicate unfixable problems

4. **Failed health checks**:
   - Go to Actions → Main CI
   - Check final "Pipeline Health Verification" job
   - Should always pass in healthy state

## Troubleshooting

### Pipeline Rescue Not Running

**Solution**: Check if workflow is enabled
```bash
gh workflow list --all
gh workflow enable pipeline-rescue.yml
```

### Too Many Repair Attempts

**Cause**: Code keeps introducing issues
**Solution**: 
- Fix the root cause in code
- Reset repair marker: `rm .workflow-repair-marker`
- Push clean commit

### YAML Still Invalid After Repair

**Cause**: Issue is beyond auto-repair capability
**Solution**:
- Check GitHub issue created with diagnostic info
- Fix manually using the provided error details
- Verify with: `npm install -g js-yaml && js-yaml file.yml`

## Future Enhancements

- [ ] Add repair metrics/dashboard
- [ ] Expand repair capabilities for more error types
- [ ] Add Slack notifications for critical failures
- [ ] Create repair audit trail
- [ ] Add machine learning to predict failures
- [ ] Extend to other workflow files

## Summary

The **Critical Pipeline Rescue System** is a three-layer defense that ensures the pipeline can **always maintain itself**:

1. **Layer 1** (Rescue) - Independent health monitor
2. **Layer 2** (Prevention) - Early fixes before failure
3. **Layer 3** (Verification) - Final health gate

This guarantees that even if humans introduce issues, the pipeline detects them immediately and fixes them automatically. If an issue can't be auto-fixed, the system clearly flags it for human intervention.

**Result**: A self-healing, resilient CI/CD pipeline that doesn't get stuck.
