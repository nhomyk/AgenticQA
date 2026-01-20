# Agent Skills Registry - GitHub Workflow Validation

## Overview
This documents the new autonomous capabilities agents have gained to prevent and solve GitHub workflow integration issues.

## New Skill: GitHub Workflow Input Validation

### Skill Summary
**Purpose**: Prevent 404 errors and workflow trigger failures by validating inputs BEFORE calling GitHub API

**Impact**: Agents can now autonomously detect, diagnose, and fix workflow parameter mismatches

**Cost**: Eliminates hours of debugging by catching issues upfront

---

## Agent Capabilities Matrix

| Capability | Enabled | Location | Usage |
|------------|---------|----------|-------|
| Validate workflow inputs | ✅ Yes | `github-workflow-validator.js` | Before any workflow trigger |
| Auto-fix input mismatches | ✅ Yes | `agent-recovery-system.js` | On validation failure |
| Diagnostic reporting | ✅ Yes | `agent-recovery-system.js` | Detailed error analysis |
| Fallback to alternate workflows | ✅ Yes | `saas-api-dev.js` | If primary fails validation |
| Pre-flight checks | ✅ Yes | Integrated in API endpoint | All workflow triggers |

---

## How Agents Use These Skills

### Skill 1: Validate Workflow Inputs

When an agent needs to trigger a workflow, it now validates the inputs first:

```javascript
// AGENT WORKFLOW
const GitHubWorkflowValidator = require('./github-workflow-validator');

async function triggerPipelineWithValidation(token, owner, repo, workflowFile, inputs) {
  // Initialize validator
  const validator = new GitHubWorkflowValidator(token, owner, repo);
  
  // Skill in action: Validate before triggering
  try {
    await validator.preflight(workflowFile, inputs);
    console.log('✓ Validation passed - safe to trigger');
    // Trigger workflow with confidence
    triggerWorkflow(token, owner, repo, workflowFile, inputs);
  } catch (error) {
    console.error('✗ Validation failed - preventing failed trigger');
    console.error(error.message);
    // Agent handles gracefully instead of wasting API calls
  }
}
```

### Skill 2: Auto-Fix Input Mismatches

When validation fails, the recovery system automatically provides corrected inputs:

```javascript
// AGENT RECOVERY
const AgentRecoverySystem = require('./agent-recovery-system');
const recovery = new AgentRecoverySystem();

async function recoverFromInputMismatch(token, owner, repo, workflowFile, inputs) {
  // Skill in action: Diagnostic + auto-fix
  const diagnosis = await recovery.diagnoseGitHubWorkflowIssue(
    token, owner, repo, workflowFile, inputs
  );
  
  if (!diagnosis.valid) {
    // Agent automatically uses corrected inputs
    console.log('Using filtered inputs:', diagnosis.filteredInputs);
    return diagnosis.filteredInputs; // Use these instead
  }
}
```

### Skill 3: Fallback to Alternate Workflows

If primary workflow doesn't exist or has incompatible inputs, try alternatives:

```javascript
// AGENT INTELLIGENT RETRY
async function triggerWithFallback(token, owner, repo, primaryWorkflow, inputs) {
  const validator = new GitHubWorkflowValidator(token, owner, repo);
  const workflowOptions = [primaryWorkflow, 'ci.yml', 'test.yml'];
  
  for (const workflow of workflowOptions) {
    // Skill in action: Try each until one passes validation
    const validation = await validator.validateInputs(workflow, inputs);
    if (validation.valid) {
      console.log(`✓ Using workflow: ${workflow}`);
      return triggerWorkflow(workflow, inputs);
    }
  }
  
  console.error('No compatible workflow found');
  throw new Error('All workflow options failed validation');
}
```

---

## Real-World Example: How This Prevented the 404 Issue

### Before (Agent-Assisted Debugging)
```
Agent 1: Trigger workflow
  ↓
❌ 404 "Workflow file not found"
  ↓
Agent 2: Investigate GitHub
  ↓ (30 mins wasted)
Agent 3: Check permissions, tokens, endpoints
  ↓ (1 hour wasted)
Humans: "That's weird, the file IS there..."
  ↓ (2+ hours wasted)
Finally: Discover input parameter mismatch

Total Cost: 3+ hours of agent/human time
```

### After (With Validation Skills)
```
Agent 1: Prepare to trigger workflow
  ↓
Validator: Check inputs against workflow file
  ↓
❌ Validation fails immediately: "pipeline_name not defined"
  ↓
Recovery System: Report clear error + suggest fix
  ↓
✅ Use filtered inputs: { pipeline_type: 'full' }
  ↓
Workflow triggers successfully

Total Cost: 30 seconds of agent time, 0 human intervention
```

---

## Technical Implementation

### Core Components

#### 1. GitHubWorkflowValidator
- **File**: `github-workflow-validator.js`
- **Methods**:
  - `getWorkflowInputs(filename)` - Fetch and parse workflow file
  - `validateInputs(filename, inputs)` - Check inputs against definition
  - `preflight(filename, inputs)` - Throws if validation fails
- **YAML Parsing**: Extracts input definitions from GitHub Actions workflows

#### 2. AgentRecoverySystem
- **File**: `agent-recovery-system.js`
- **New Method**: `diagnoseGitHubWorkflowIssue()`
- **Purpose**: Comprehensive diagnosis + suggested fixes
- **Output**: Filtered inputs, expected inputs, error messages

#### 3. Integration Point
- **File**: `saas-api-dev.js` - `/api/trigger-workflow` endpoint
- **Behavior**: Automatic validation before GitHub API call
- **Fallback**: Tries next workflow file if validation fails

#### 4. Agent Orchestrator Enhancement
- **File**: `agent-orchestrator.js`
- **New Field**: `agentCapabilities.github` tracks GitHub skills
- **New Method**: `initializeWorkflowValidator()` for setup

---

## Agent Skill Levels

### Level 1: Basic Validation (Implemented)
- ✅ Check inputs match workflow definition
- ✅ Report validation errors
- ✅ Provide expected inputs

### Level 2: Intelligent Recovery (Implemented)
- ✅ Auto-filter invalid inputs
- ✅ Try alternative workflow files
- ✅ Clear error messaging

### Level 3: Predictive Prevention (Future)
- ⏳ Pre-check workflow syntax before commit
- ⏳ Warn about misconfigurations during setup
- ⏳ Auto-update workflows when inputs change

### Level 4: Self-Healing (Future)
- ⏳ Auto-add missing inputs to workflow files
- ⏳ Auto-create compatible workflows
- ⏳ Learn from past failures

---

## For Agent Developers

### When Building New Features

**Always Validate Before Triggering**:
```javascript
const validator = new GitHubWorkflowValidator(token, owner, repo);
const validation = await validator.validateInputs(workflowFile, inputs);

if (!validation.valid) {
  // Handle gracefully - don't call GitHub API
  throw new Error(`Invalid inputs: ${validation.errors.join(', ')}`);
}

// Now safe to trigger
```

### Adding New Workflow Input Support

1. Update your workflow file `.github/workflows/xxx.yml`:
   ```yaml
   on:
     workflow_dispatch:
       inputs:
         new_parameter:
           description: 'Description'
           required: false
   ```

2. Validator automatically detects it (no code changes needed)

3. Agent can immediately use it in triggers

### Testing Your Validation Code

```bash
# Test validation directly
node -e "
const GitHubWorkflowValidator = require('./github-workflow-validator');
const v = new GitHubWorkflowValidator(process.env.GITHUB_TOKEN, 'owner', 'repo');
v.validateInputs('agentic-qa.yml', {pipeline_type: 'full'})
  .then(r => console.log(r));
"
```

---

## Monitoring & Alerts

### What Agents Should Monitor

1. **Validation Success Rate**: Should be 95%+
2. **Fallback Usage**: Track how often backup workflows are used
3. **Input Mismatches**: Log patterns in rejected inputs
4. **Recovery Time**: Monitor how fast issues are resolved

### Suggested Metrics

```javascript
// Track in agent logs
{
  validationAttempts: 150,
  validationSuccesses: 147,
  successRate: "98%",
  fallbacksUsed: 3,
  averageRecoveryTime: "2.3 seconds",
  commonErrors: ["pipeline_name not defined"]
}
```

---

## Troubleshooting

### Problem: "Workflow file not found" in validation

**Causes**:
- GitHub token doesn't have repo access
- Repository name is wrong
- Workflow file doesn't exist

**Solution**:
```javascript
try {
  await validator.preflight(workflowFile, inputs);
} catch (error) {
  if (error.message.includes('404')) {
    console.error('Workflow file missing:', workflowFile);
    // Try alternative
  }
}
```

### Problem: Validation passes but GitHub still rejects

**Cause**: GitHub API behavior changed or token permissions issue

**Solution**:
- Check GitHub token has `workflow` scope
- Verify repository access
- Check branch exists

---

## Success Metrics

### Before This System
- 🔴 GitHub API 404s: Multiple per session
- 🔴 Debug time: Hours
- 🔴 Agent intervention: Frequent
- 🔴 Resolution clarity: Low

### After This System
- 🟢 GitHub API 404s: Prevented upfront
- 🟢 Debug time: Seconds
- 🟢 Agent intervention: Autonomous
- 🟢 Resolution clarity: High

---

## Documentation References

- [GitHub Workflow Validation Guide](./GITHUB_WORKFLOW_VALIDATION_GUIDE.md)
- [Agent Recovery System](./agent-recovery-system.js)
- [Workflow Validator Implementation](./github-workflow-validator.js)
- [API Integration](./saas-api-dev.js#L972)

---

**Last Updated**: January 20, 2026  
**Status**: Production Ready  
**Agent Skill Level**: Advanced  
**Coverage**: All GitHub workflow integrations
