# Testing Custom Pipeline Name Feature

## Quick Start

### 1. Kill any hanging processes
```bash
lsof -ti:3001 | xargs kill -9 2>/dev/null; true
```

### 2. Start the server
```bash
npm start
```

### 3. Run the test script

In a new terminal, run:

```bash
# Set up your GitHub token and repository
export GITHUB_TOKEN="ghp_your_actual_token_here"
export GITHUB_REPO="your-org/your-repo"
export CUSTOM_PIPELINE_NAME="🚀 My Custom Pipeline Name"

# Run the test
node test-custom-pipeline-name.js
```

## What the test does

1. ✅ Logs into the OrbitQA API with demo credentials
2. ✅ Connects your GitHub repository
3. ✅ Triggers a workflow with a custom pipeline name
4. ✅ Provides verification steps for GitHub Actions

## Expected Results

- API returns `status: 'success'`
- Workflow file is auto-deployed with `pipeline_name` input support
- GitHub Actions shows the custom pipeline name in the run summary

## Manual Testing (if you prefer)

### Step 1: Get your JWT token
```bash
curl -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@orbitqa.ai",
    "password": "demo123"
  }'
```

Copy the `token` from the response.

### Step 2: Connect GitHub
```bash
curl -X POST http://localhost:3001/api/github/connect \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "token": "ghp_your_github_token",
    "repository": "your-org/your-repo"
  }'
```

### Step 3: Trigger workflow with custom name
```bash
curl -X POST http://localhost:3001/api/trigger-workflow \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "pipelineType": "full",
    "branch": "main",
    "pipelineName": "🚀 My Custom Pipeline"
  }'
```

### Step 4: Verify in GitHub

1. Go to: `https://github.com/your-org/your-repo/actions`
2. Look for a run titled with your custom name
3. Click to see the workflow summary with your custom pipeline name

## Troubleshooting

### Error: "GitHub not connected"
- Make sure you've called `/api/github/connect` first with your token and repository

### Error: "Workflow file not found"
- The auto-deploy should have created it, but you can verify by checking `.github/workflows/agentic-qa.yml` exists in your repo

### Custom name not appearing in GitHub Actions
- This means the workflow file was deployed but the `run-name` might not be using it
- Check the GitHub Actions logs for the `PIPELINE_NAME` environment variable value

## Key Code Changes

The `/api/trigger-workflow` endpoint now:

1. **Auto-deploys workflow** with `pipeline_name` input before triggering
2. **Accepts custom names** via `pipelineName` in the request body
3. **Sets environment variables** so the workflow can display the custom name
4. **Validates inputs** before sending to GitHub (non-blocking)

The workflow file includes:
```yaml
on:
  workflow_dispatch:
    inputs:
      pipeline_name:
        description: 'Custom pipeline name'
        required: false
        default: 'AgenticQA Pipeline'
        type: string

env:
  PIPELINE_NAME: ${{ github.event.inputs.pipeline_name || 'AgenticQA Pipeline' }}
```

This allows the custom name to be displayed in the GitHub Actions summary.
