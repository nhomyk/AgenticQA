# GitHub Integration Setup Guide

## Overview

The Dashboard now includes a complete GitHub integration that allows clients to trigger CI/CD pipelines directly from the web interface. This guide explains how to set it up and use it.

## System Architecture

```
Dashboard (Settings Page)
    ↓
GitHub Connection API (/api/github/*)
    ↓
Token Storage (Backend)
    ↓
GitHub REST API (Dispatch Workflows)
    ↓
CI/CD Pipeline Execution
```

## Prerequisites

Before connecting your GitHub account, you'll need:

1. A GitHub account with admin/push access to the repository
2. A GitHub Personal Access Token (PAT) with appropriate permissions
3. A CI/CD workflow file at `.github/workflows/ci.yml` in your repository

## Step 1: Create a GitHub Personal Access Token

### Via Fine-Grained Tokens (Recommended - More Secure)

1. Go to: https://github.com/settings/tokens?type=beta
2. Click "Generate new token"
3. Name it: `orbitQA Pipeline`
4. Set expiration: 90 days
5. Select "Only select repositories"
6. Choose your repository
7. Under "Permissions", grant:
   - **Actions**: Read and write
   - **Contents**: Read-only

### Via Classic Personal Access Token (Simpler)

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Name it: `orbitQA Pipeline`
4. Select scopes:
   - ☑️ `repo` - Full control of private repositories
   - ☑️ `workflow` - Update GitHub Actions and workflows
   - ☑️ `admin:repo_hook` - Full control of repository hooks
5. Click "Generate token"
6. **Copy and save it somewhere secure** - you won't see it again!

## Step 2: Connect GitHub in orbitQA Dashboard

### Using the Settings Page

1. Log in to the orbitQA Dashboard at `http://localhost:3001` (or your deployment URL)
2. Click the ⚙️ Settings button in the top right
3. In the "GitHub Integration" tab:
   - Click "🔑 Use Personal Access Token (Advanced)"
   - Paste your Personal Access Token in the field
   - Enter your repository (format: `username/repository`)
   - Click "💾 Save Token"

### Result

Once connected, you should see:
- ✅ Green "GitHub Connected" status
- Account name displayed
- Repository information
- "Test Connection" button for verification

## Step 3: Create Your CI/CD Workflow

You need a workflow file at `.github/workflows/ci.yml` that accepts workflow dispatch events:

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  workflow_dispatch:
    inputs:
      pipeline_type:
        description: 'Type of pipeline to run'
        required: false
        default: 'full'
        type: choice
        options:
          - full
          - tests
          - security

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Determine Pipeline Type
        id: pipeline
        run: |
          PIPELINE_TYPE="${{ inputs.pipeline_type }}"
          echo "Pipeline Type: ${PIPELINE_TYPE:-full}"
      
      - name: Run Full CI/CD
        if: ${{ inputs.pipeline_type == 'full' || !inputs.pipeline_type }}
        run: |
          npm install
          npm run lint
          npm test
          npm run build
          npm run security-scan
      
      - name: Run Tests Only
        if: ${{ inputs.pipeline_type == 'tests' }}
        run: |
          npm install
          npm test
      
      - name: Run Security Scan Only
        if: ${{ inputs.pipeline_type == 'security' }}
        run: |
          npm run security-scan
```

## Step 4: Launch Pipelines from Dashboard

### On the Dashboard Page

1. Scroll to the "Pipeline Control" section
2. Select the pipeline type from the dropdown:
   - **Full CI/CD Pipeline** - Runs all phases
   - **Tests Only** - Runs only tests
   - **Security Scan** - Runs only security checks
3. (Optional) Change the branch if needed
4. Click "🚀 Launch Pipeline"
5. Monitor the status - you should see:
   - ✅ Success message with confirmation
   - Pipeline status updates in the activity feed
   - Workflow run in GitHub Actions

### Troubleshooting

**"GitHub is not connected"**
- Go to Settings → GitHub Integration
- Click "🔑 Use Personal Access Token"
- Enter your token and repository

**"Workflow file not found"**
- Make sure `.github/workflows/ci.yml` exists in your repository
- Check the file path and permissions

**"Token is invalid or expired"**
- Generate a new Personal Access Token in GitHub
- Update it in Settings → GitHub Integration
- Previous token will be replaced

**"Validation error: Branch doesn't exist"**
- Make sure the branch exists in your repository
- Default is `main`, but you can use any branch

## API Endpoints Reference

### Check GitHub Connection Status
```
GET /api/github/status
Response: { connected: boolean, account: string, repository: string, lastUsed: date }
```

### Connect GitHub
```
POST /api/github/connect
Body: { token: string, repository: string }
Response: { status: 'success', message: string, repository: string }
```

### Test GitHub Connection
```
POST /api/github/test
Response: { status: 'success', message: string, account: string }
```

### Disconnect GitHub
```
POST /api/github/disconnect
Response: { status: 'success', message: string }
```

### Trigger Workflow
```
POST /api/trigger-workflow
Body: { pipelineType: 'full|tests|security', branch: string }
Response: { status: 'success', message: string, repository: string, workflowId: string }
```

## Security Considerations

### Token Security

- ✅ **Tokens are Encrypted** - GitHub tokens are encrypted using AES-256-CBC before storage
- ✅ **Never Exposed** - Tokens are never logged or exposed in error messages
- ✅ **HTTPS Only** - All GitHub API calls use HTTPS encryption
- ✅ **Temporary Access** - Tokens are decrypted only when needed, then discarded
- ✅ **Audit Trail** - All token operations are logged for security monitoring

### Token Storage

In development (local testing):
- Tokens are encrypted in-memory

In production (deployment):
- Ensure `ENCRYPTION_KEY` environment variable is set
- Tokens are encrypted before storage in database
- Key rotation can be performed without exposing tokens

### Recommendations

1. ✅ Use fine-grained tokens with minimal permissions
2. ✅ Set 90-day expiration on tokens
3. ✅ Create separate tokens for different environments
4. ✅ Monitor workflow runs for suspicious activity
5. ✅ Enable HTTPS for all production deployments
6. ✅ Implement rate limiting (recommended)
7. ✅ Rotate encryption keys periodically
8. ✅ Monitor audit logs for failed token operations

## Multi-Repository Support

Current implementation supports one repository connection per deployment. To support multiple repositories:

1. Modify token storage to support multiple entries
2. Update UI to include repository selector
3. Store repository-specific tokens separately
4. Update workflow trigger to use selected repository

## Deployment to Production

When deploying to production:

1. **Store Tokens Securely**
   ```javascript
   // Implement encryption for token storage
   const crypto = require('crypto');
   const encryptedToken = encrypt(token, process.env.ENCRYPTION_KEY);
   ```

2. **Use Environment Variables**
   ```
   GITHUB_ENCRYPTION_KEY=your-encryption-key
   GITHUB_WEBHOOK_SECRET=your-webhook-secret
   ```

3. **Add Rate Limiting**
   ```javascript
   const rateLimit = require('express-rate-limit');
   app.use('/api/trigger-workflow', rateLimit({
     windowMs: 60 * 1000,
     max: 10  // Max 10 requests per minute
   }));
   ```

4. **Enable HTTPS**
   - Always use HTTPS for production
   - Certificate must be valid and current

5. **Add Monitoring**
   - Log all workflow triggers
   - Set up alerts for failed triggers
   - Monitor GitHub API rate limits

## Examples

### Example 1: Trigger Full Pipeline
```javascript
const response = await fetch('/api/trigger-workflow', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    pipelineType: 'full',
    branch: 'main'
  })
});
// Response: { status: 'success', message: '✅ Workflow triggered...' }
```

### Example 2: Trigger Tests Only
```javascript
const response = await fetch('/api/trigger-workflow', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    pipelineType: 'tests',
    branch: 'develop'
  })
});
```

### Example 3: Check Connection Status
```javascript
const status = await fetch('/api/github/status').then(r => r.json());
if (status.connected) {
  console.log(`Connected to: ${status.account}/${status.repository}`);
} else {
  console.log('GitHub not connected');
}
```

## Support & Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| 403 Forbidden | Check token permissions in GitHub |
| 404 Not Found | Verify repository and workflow file exist |
| 422 Unprocessable | Branch doesn't exist or wrong format |
| 401 Unauthorized | Token is expired or invalid |
| 503 Service Unavailable | GitHub API is experiencing issues |

### Testing

Run the workflow test from Settings → GitHub Integration → "Test Trigger" to verify:
1. Token is valid
2. Repository is accessible
3. Workflow file exists
4. API connectivity is working

### Debug Mode

Add to browser console to enable verbose logging:
```javascript
localStorage.setItem('DEBUG_GITHUB_API', 'true');
```

Then check browser console for detailed API request/response information.

## Next Steps

1. ✅ Set up Personal Access Token
2. ✅ Connect GitHub in Settings
3. ✅ Test the connection
4. ✅ Trigger your first pipeline from the dashboard
5. ✅ Monitor the workflow in GitHub Actions
6. ✅ Configure additional pipeline types as needed
7. ✅ Set up production-grade security

## Support Resources

- GitHub API Documentation: https://docs.github.com/en/rest
- GitHub Actions Documentation: https://docs.github.com/en/actions
- orbitQA Dashboard: See built-in Help page
- Dashboard Settings: For configuration and troubleshooting
