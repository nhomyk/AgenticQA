# 🎯 AgenticQA Client Provisioning System

## Overview

This implementation enables clients to run the AgenticQA pipeline against their own repositories **without installing individual GitHub Actions tools**. The system uses:

1. **API Endpoints** - Client registration and pipeline control
2. **Reusable Workflow** - Lightweight GitHub Actions template
3. **Lightweight Executor** - On-demand tool downloads and execution
4. **Dashboard Integration** - Client-specific dashboard links

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│         Client's Repository                             │
│  ┌──────────────────────────────────────────────────┐   │
│  │ .github/workflows/agentic-qa.yml                 │   │
│  │ (Provisioned via onboarding script)              │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          ↓
                          ↓ (via GitHub Actions)
┌─────────────────────────────────────────────────────────┐
│         AgenticQA Dashboard (SaaS)                       │
│  ┌──────────────────────────────────────────────────┐   │
│  │ /api/clients/[CLIENT_ID]/pipeline-definition     │   │
│  │ Downloads tool code on-demand                    │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Implementation Files

### 1. API Endpoints (`saas-api-dev.js`)

**New Endpoints Added:**

- `POST /api/clients/register` - Register a client repository
- `GET /api/clients/:clientId` - Get client details
- `GET /api/clients` - List user's clients (authenticated)
- `POST /api/clients/:clientId/trigger-pipeline` - Trigger pipeline in client's repo
- `GET /api/clients/:clientId/pipeline-definition` - Get pipeline phases
- `POST /api/clients/:clientId/results` - Receive pipeline results

**Example: Register a Client**

```javascript
POST /api/clients/register
{
  "repoUrl": "https://github.com/acme/product",
  "clientToken": "ghp_xxxxxxxxxxxx"
}

Response:
{
  "status": "success",
  "clientId": "client_a1b2c3d4e5f6",
  "setupUrl": "http://localhost:3001/setup?client=client_a1b2c3d4e5f6",
  "dashboardUrl": "http://localhost:3000?client=client_a1b2c3d4e5f6"
}
```

### 2. Client Workflow Template (`templates/client-workflow-template.yml`)

**Features:**
- Trigger on push, schedule, or manual dispatch
- Downloads executor script on-demand
- Posts results back to dashboard
- Generates GitHub Actions summary reports

**Key Sections:**
```yaml
on:
  workflow_dispatch:
    inputs:
      client_id:
        description: 'Client identifier for dashboard linking'
  push:
    branches: [main, develop]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
```

### 3. Lightweight Executor (`.agentic-qa/executor.js`)

**Execution Phases:**
1. `scan-codebase` - Analyze repository structure
2. `detect-issues` - Find accessibility, performance, and security issues
3. `generate-tests` - Create Playwright, Cypress, Vitest test cases
4. `run-compliance` - Check GDPR, SOC2, HIPAA, CCPA compliance
5. `generate-report` - Create comprehensive analysis report

**Features:**
- Downloads phase definitions from dashboard API
- Executes locally without tool installation
- Sends results back to dashboard
- Colored console output with progress tracking

### 4. Dashboard Integration (`public/dashboard.html`)

**New Client Mode Features:**
- Detects `?client=CLIENT_ID` query parameter
- Shows client-specific repository information
- Trigger pipeline directly from dashboard
- View real-time pipeline status
- Override pipeline endpoint per client

**JavaScript Functions:**
```javascript
initializeClientMode()      // Auto-detect and initialize
triggerClientPipeline()     // Trigger workflow in client's repo
```

### 5. Onboarding Script (`scripts/onboard-client.js`)

**One-Command Setup:**
```bash
node scripts/onboard-client.js https://github.com/user/repo ghp_xxxxxxxxxxxx
```

**Steps Performed:**
1. Register client with API
2. Create workflow file
3. Setup executor
4. Commit and push to repository

## Usage Flow

### For AgenticQA Provider

**Step 1: Register Client**
```bash
node scripts/onboard-client.js https://github.com/acme/product ghp_xxxxxxxxxxxx
```

Output:
```
✓ Client registered with ID: client_a1b2c3d4e5f6
✓ Created workflow file: .github/workflows/agentic-qa.yml
✓ Committed workflow file
✓ Pushed to remote repository

Next Steps:
1. Open dashboard: http://dashboard.orbitqa.ai?client=client_a1b2c3d4e5f6
2. Workflow runs on every push to main
3. View results in AgenticQA dashboard
```

### For Client

**Option 1: Automatic (on push)**
Client pushes to main branch → Workflow triggers automatically

**Option 2: Manual (from GitHub)**
1. Go to client's GitHub repository
2. Click "Actions" tab
3. Select "AgenticQA Client Pipeline"
4. Click "Run workflow"

**Option 3: Manual (from AgenticQA Dashboard)**
1. Open dashboard link: `http://dashboard.orbitqa.ai?client=CLIENT_ID`
2. Click "🚀 Trigger Client Pipeline"
3. View real-time results

## API Reference

### Register Client
```
POST /api/clients/register
Content-Type: application/json

{
  "repoUrl": "https://github.com/owner/repo",
  "clientToken": "ghp_xxxxxxxxxxxx"
}

Response (200):
{
  "status": "success",
  "clientId": "client_xxxx",
  "setupUrl": "...",
  "dashboardUrl": "..."
}
```

### Get Client Details
```
GET /api/clients/:clientId

Response (200):
{
  "status": "success",
  "client": {
    "id": "client_xxxx",
    "repoUrl": "https://github.com/owner/repo",
    "owner": "owner",
    "repo": "repo",
    "createdAt": "2026-01-20T...",
    "lastRun": "2026-01-20T...",
    "runCount": 5,
    "status": "active"
  }
}
```

### Trigger Pipeline
```
POST /api/clients/:clientId/trigger-pipeline

Response (200):
{
  "status": "success",
  "message": "Pipeline triggered successfully in client repository",
  "clientId": "client_xxxx",
  "repoUrl": "https://github.com/owner/repo"
}
```

### Get Pipeline Definition
```
GET /api/clients/:clientId/pipeline-definition

Response (200):
{
  "status": "success",
  "definition": {
    "version": "1.0",
    "phases": [
      {
        "name": "Scan Codebase",
        "toolId": "scan-codebase",
        "description": "..."
      },
      ...
    ]
  }
}
```

### Submit Results
```
POST /api/clients/:clientId/results
Content-Type: application/json

{
  "clientId": "client_xxxx",
  "status": "completed",
  "phases": { ... },
  "summary": { ... }
}

Response (200):
{
  "status": "success",
  "message": "Results received and stored",
  "clientId": "client_xxxx"
}
```

## Testing

**Run Integration Tests:**
```bash
# Start SaaS API server
npm run server:saas

# In another terminal
node scripts/test-client-integration.js
```

**Expected Output:**
```
🧪 AgenticQA Client Integration Tests

✓ API Health Check
✓ Register Client Repository
✓ Fetch Client Details
✓ Fetch Pipeline Definition
✓ Submit Pipeline Results
✓ Invalid Client Handling
✓ Validation: Missing Repo URL

📊 Test Summary
Passed: 7
Failed: 0
```

## Client Dashboard

When client opens: `http://localhost:3000?client=client_xxxx`

The dashboard shows:
- Client repository information
- Last pipeline run details
- Option to trigger pipeline
- Real-time status updates
- Results when available

## Security Considerations

1. **Token Type** - Use GitHub Personal Access Token (PAT) classic, NOT fine-grained
   - ⚠️ Go to https://github.com/settings/tokens
   - Click **"Generate new token (classic)"**
   - Required scopes: `repo` + `actions`
2. **Token Encryption** - GitHub tokens encrypted with AES-256-CBC
3. **Rate Limiting** - Auth endpoints rate-limited to 5 attempts/15 min
4. **CORS Protection** - Strict origin validation
5. **Token Scopes** - Client token requires minimal GitHub permissions
6. **In-Memory Storage** - Development mode; use database in production

## Production Deployment

For production, consider:

1. **Database Storage** - Replace in-memory Map with database
2. **Token Management** - Use secure secret management service
3. **Audit Logging** - Store all operations in audit log
4. **Result Retention** - Implement result archival strategy
5. **Metrics** - Track pipeline execution metrics
6. **Error Handling** - Implement comprehensive error recovery

## Next Steps

1. ✅ Implement API endpoints
2. ✅ Create workflow template
3. ✅ Create executor script
4. ✅ Update dashboard
5. ✅ Create onboarding script
6. 🔄 Test with actual client repository
7. 🔄 Deploy to production
8. 🔄 Monitor pipeline execution

## Troubleshooting

**"API is not running"**
```bash
npm run server:saas
```

**"Client not found"**
- Verify client ID matches registration response
- Check `http://localhost:3001/api/clients/:clientId`

**"Workflow not triggered"**
- Verify GitHub token has `actions:write` permission
- Check repository settings for branch protection

**"Results not received"**
- Check executor logs in GitHub Actions
- Verify `AGENTIC_QA_API` environment variable in workflow

---

**Status:** ✅ Implementation Complete - Ready for Testing
