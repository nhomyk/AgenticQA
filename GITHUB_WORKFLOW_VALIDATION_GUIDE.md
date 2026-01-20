# GitHub Workflow Validation Guide for Agents

## Problem Solved
**Issue**: GitHub API returns 404 "Workflow file not found" when sending undefined input parameters to workflow_dispatch endpoint. This is misleading - the file exists, but the inputs don't match.

**Root Cause**: Agents were sending `pipeline_name` input to workflows that only define `pipeline_type`.

**Solution**: Automatic validation system that checks workflow inputs BEFORE triggering, preventing 404 errors.

---

## Quick Start for Agents

### 1. Using the Validator in Your Code

```javascript
const GitHubWorkflowValidator = require('./github-workflow-validator');

// Create validator instance
const validator = new GitHubWorkflowValidator(githubToken, owner, repo);

// Option A: Validate inputs (get detailed report)
const validation = await validator.validateInputs('agentic-qa.yml', {
  pipeline_type: 'full'
});

if (!validation.valid) {
  console.error('Validation errors:', validation.errors);
  // Use validation.expectedInputs to know what's allowed
}

// Option B: Pre-flight check (throws error if invalid)
try {
  await validator.preflight('agentic-qa.yml', inputs);
  // Safe to trigger workflow now
} catch (error) {
  console.error('Workflow validation failed:', error.message);
}
```

### 2. Integration Points in saas-api-dev.js

The `/api/trigger-workflow` endpoint now includes automatic validation:

```javascript
// Already integrated - no changes needed!
// The endpoint now:
// 1. Checks inputs against workflow definition
// 2. Auto-skips to next workflow file if validation fails
// 3. Only triggers when inputs match
```

### 3. Using the Recovery System

```javascript
const AgentRecoverySystem = require('./agent-recovery-system');
const recovery = new AgentRecoverySystem();

// Diagnose GitHub workflow issues
const diagnosis = await recovery.diagnoseGitHubWorkflowIssue(
  token,
  'nhomyk',
  'react_project',
  'agentic-qa.yml',
  { pipeline_type: 'full', pipeline_name: 'Custom' }
);

if (!diagnosis.valid) {
  // diagnosis.filteredInputs contains corrected inputs
  console.log('Use these inputs instead:', diagnosis.filteredInputs);
}
```

---

## How It Works

### Validation Flow

```
Agent wants to trigger workflow
    ↓
Send inputs to validator
    ↓
Validator fetches workflow file from GitHub
    ↓
Validator extracts input definitions from YAML
    ↓
Validator compares inputs vs definitions
    ↓
✅ Valid: Trigger workflow
❌ Invalid: Report errors & suggest fix
```

### Key Files

| File | Purpose |
|------|---------|
| `github-workflow-validator.js` | Core validator - validates workflow inputs |
| `agent-recovery-system.js` | Recovery system with diagnostic method |
| `saas-api-dev.js` | API backend - uses validator before triggering |

---

## Common Scenarios

### Scenario 1: Adding New Input to Workflow

**Old Way** (would fail):
```javascript
// Workflow file only has 'pipeline_type'
// But you send both 'pipeline_type' and 'pipeline_name'
// → 404 error (confusing!)
```

**New Way** (with validation):
```javascript
const validation = await validator.validateInputs('agentic-qa.yml', inputs);
// Returns: { valid: false, errors: ["'pipeline_name' is not defined"] }
// Agent knows to update the workflow file first
```

### Scenario 2: Triggering with Filtered Inputs

```javascript
// Agent has all possible inputs but workflow only accepts some
const inputs = { pipeline_type: 'full', pipeline_name: 'Test', debug: true };
const diagnosis = await recovery.diagnoseGitHubWorkflowIssue(token, owner, repo, file, inputs);

if (!diagnosis.valid) {
  // Use filteredInputs that actually match the workflow
  triggerWorkflow(file, diagnosis.filteredInputs);
}
```

### Scenario 3: Testing Multiple Workflow Files

```javascript
const workflowFiles = ['agentic-qa.yml', 'ci.yml', 'test.yml'];

for (const file of workflowFiles) {
  const validation = await validator.validateInputs(file, inputs);
  if (validation.valid) {
    console.log(`✓ Workflow ${file} accepts these inputs`);
    break;
  }
}
```

---

## For Future Agent Development

### Preventive Practices

1. **Always validate before triggering**
   ```javascript
   await validator.preflight(workflowFile, inputs);
   // Then trigger with confidence
   ```

2. **Handle validation errors gracefully**
   ```javascript
   const validation = await validator.validateInputs(file, inputs);
   if (!validation.valid) {
     // Log what inputs are expected
     console.log('Expected:', validation.expectedInputs);
     // Try alternative workflow or alert user
   }
   ```

3. **Document workflow input requirements**
   - When creating workflows, add comments about inputs
   - When triggering, validate against those inputs

### Agent Skill: GitHub Workflow Diagnostic

Agents can now autonomously:
- ✅ Detect workflow input mismatches
- ✅ Self-correct by filtering invalid inputs
- ✅ Try alternative workflow files
- ✅ Report clear errors instead of confusing 404s
- ✅ Prevent blocking issues from recurring

---

## Testing the System

### Test 1: Valid Inputs
```bash
curl -X POST http://localhost:3001/api/trigger-workflow \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"pipelineType":"full", "branch":"main"}'
# Should succeed
```

### Test 2: Invalid Inputs
```bash
# If workflow doesn't support 'invalid_param'
curl -X POST http://localhost:3001/api/trigger-workflow \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"pipelineType":"full", "invalid_param":"value"}'
# Should fail gracefully with clear error
```

### Test 3: Validation Only (No Trigger)
```javascript
const validator = new GitHubWorkflowValidator(token, owner, repo);
const result = await validator.validateInputs('agentic-qa.yml', 
  { pipeline_type: 'full' }
);
console.log(result);
// { valid: true, expectedInputs: ['pipeline_type'], ... }
```

---

## Troubleshooting

### Issue: "Validation check failed for workflow, trying next..."
- The workflow file might not exist or the inputs genuinely don't match
- Check that workflow file exists in `.github/workflows/`
- Check the YAML syntax in the workflow file

### Issue: "GitHub API returned 404"
- Validation passed but GitHub still returns 404
- This usually means the workflow file really doesn't exist
- Check repository access and branch permissions

### Issue: Validator can't fetch workflow file
- Ensure GitHub token has `repo` scope
- Verify owner/repo name is correct
- Check that `.github/workflows/` directory exists

---

## Next Steps for Agents

1. **Start using the validator** in all GitHub integration code
2. **Add diagnostic calls** to recovery system when workflow issues occur
3. **Test alternative workflows** when one fails validation
4. **Report clear errors** with expected inputs when validation fails
5. **Never send undefined parameters** to GitHub API (validator prevents this)

This system ensures workflow trigger failures are caught early, reported clearly, and fixed automatically.
