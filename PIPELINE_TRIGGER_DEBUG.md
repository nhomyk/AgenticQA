# 🐛 Pipeline Trigger Debugging Guide

## Problem
Launch Pipeline button shows connection status JSON but never submits to GitHub Actions.

## Root Causes & Solutions

### 1. ❌ GitHub Token Not Configured

**Symptoms:**
- Button click shows error about GitHub token
- Response status: 503
- Error message: "GitHub token not configured"

**How to Fix:**
```bash
# Option A: Set as environment variable
export GITHUB_TOKEN="ghp_your_personal_access_token"

# Option B: Use Dashboard Settings
1. Open AgenticQA Dashboard
2. Go to Settings tab
3. Connect your GitHub account
4. Add your Personal Access Token (PAT)
```

**Token Requirements:**
- Minimum scopes: `actions` + `contents`
- Can be created at: https://github.com/settings/tokens/new

---

### 2. ❌ GitHub Workflow Not Found

**Symptoms:**
- Response status: 404
- Error: "Workflow 'ci.yml' not found"

**How to Fix:**
1. Verify `.github/workflows/ci.yml` exists in repository
2. Check file is valid YAML
3. Workflow must be on the branch you're triggering

---

### 3. ❌ GitHub Token Authentication Failed

**Symptoms:**
- Response status: 403
- Error: "GitHub token authentication failed"

**How to Fix:**
1. Generate new token at https://github.com/settings/tokens/new
2. Ensure scopes include:
   - ✅ `actions` - To trigger workflows
   - ✅ `contents` - To access repository
3. Update token in Settings or environment variable

---

### 4. ❌ Invalid Branch Name

**Symptoms:**
- Response status: 400
- Error: "Invalid branch" or "Invalid branch format"

**How to Fix:**
1. Verify branch exists: `git branch -a`
2. Branch name must be alphanumeric with `-`, `_`, `.` or `/`
3. Select from dropdown in dashboard

---

### 5. ❌ Network/CORS Issues

**Symptoms:**
- Fetch fails before reaching server
- Browser console shows CORS error
- No response from dashboard

**How to Fix:**
1. Check server is running: `lsof -i :3000`
2. Verify HTTPS settings if accessing over HTTPS
3. Check browser console for network errors (F12 > Network tab)

---

## Debugging Steps

### Step 1: Check Browser Console
```javascript
// Browser DevTools Console (F12 > Console tab)
// Look for logs starting with [Pipeline Kickoff]

// Should show:
// [Pipeline Kickoff] Starting pipeline trigger...
// [Pipeline Kickoff] GitHub connection check result: { isConnected: true }
// [Pipeline Kickoff] Calling /api/trigger-workflow endpoint...
// [Pipeline Kickoff] Response received { status: 200, ok: true }
// [Pipeline Kickoff] ✅ Pipeline triggered successfully!
```

### Step 2: Check Server Logs
```bash
# Terminal where server is running
# Look for logs starting with 🚀 or ✅

# Should show:
# 🚀 Trigger workflow request received
# ✅ Workflow dispatch successful!

# If seeing ❌ or ⚠️, check the error message
```

### Step 3: Run Test Script
```bash
cd /Users/nicholashomyk/mono/AgenticQA

# Set token first
export GITHUB_TOKEN="ghp_your_token"

# Run test
node test-pipeline-trigger.js
```

### Step 4: Check Network Tab
```
1. Open DevTools (F12)
2. Go to Network tab
3. Click "Launch Pipeline" button
4. Look for these requests:

   Request 1: GET /api/github/status
   Expected response:
   {
     "status": "connected",
     "repository": "nhomyk/AgenticQA",
     "connectedAt": "2026-01-19T..."
   }

   Request 2: POST /api/trigger-workflow
   Expected response:
   {
     "status": "success",
     "message": "Pipeline 'tests' triggered successfully...",
     "workflow": "ci.yml"
   }
```

---

## Common Issues & Fixes

| Issue | Status Code | Solution |
|-------|-------------|----------|
| Token missing | 503 | Set GITHUB_TOKEN or configure in Settings |
| Token invalid | 403 | Generate new token at github.com/settings/tokens |
| Workflow not found | 404 | Check .github/workflows/ci.yml exists |
| Invalid branch | 400 | Use valid branch name from dropdown |
| Server error | 500 | Check server logs, restart server |

---

## Testing the Full Flow

### Manual Test (Using curl)
```bash
# 1. Check GitHub connection
curl http://localhost:3000/api/github/status

# Expected:
# {"status":"connected","repository":"nhomyk/AgenticQA",...}

# 2. Trigger workflow
curl -X POST http://localhost:3000/api/trigger-workflow \
  -H "Content-Type: application/json" \
  -d '{
    "pipelineType": "tests",
    "branch": "develop",
    "pipelineName": "Manual Test Pipeline"
  }'

# Expected:
# {"status":"success","message":"Pipeline 'tests' triggered...",...}
```

### Verify Pipeline Ran
After triggering, check GitHub Actions:
- URL: https://github.com/nhomyk/AgenticQA/actions
- Look for new run with your pipeline name
- Should start within 10 seconds

---

## When It Works ✅

You should see:
1. Button shows "⏳ Launching..." briefly
2. Success alert appears: "✅ Pipeline 'tests' triggered successfully..."
3. Button returns to "🚀 Launch Pipeline"
4. New pipeline appears in "Recent Pipelines" section
5. GitHub Actions shows new workflow run

---

## Getting Help

If still stuck:
1. Check console logs (F12 > Console)
2. Check network requests (F12 > Network)
3. Run `node test-pipeline-trigger.js` and share output
4. Share server logs from terminal
5. Verify token has correct scopes

---

## New Logging Available

As of this update, the dashboard includes enhanced logging:

**Frontend Logs** (Browser Console):
```
[Pipeline Kickoff] Starting pipeline trigger
[GitHub Connection Check] status: connected
[Pipeline Kickoff] Calling /api/trigger-workflow endpoint...
[Pipeline Kickoff] Response received
[Pipeline Kickoff] ✅ Pipeline triggered successfully!
```

**Server Logs**:
```
🚀 Trigger workflow request received
📋 Preparing GitHub workflow dispatch
📡 GitHub API response received
✅ Workflow dispatch successful!
```

Enable these in browser DevTools:
- Open DevTools (F12)
- Go to Console tab
- Click button to see all logs
- Share the console output for debugging
