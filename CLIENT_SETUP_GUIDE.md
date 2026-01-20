# 🚀 AgenticQA Client Setup Guide

## Quick Start

### For AgenticQA Team

Onboard a client repository in 3 steps:

```bash
# STEP 1: Navigate to AgenticQA directory
#         ⚠️ This is REQUIRED - run from /Users/nicholashomyk/mono/AgenticQA
cd /Users/nicholashomyk/mono/AgenticQA

# STEP 2: Get the client's GitHub token (Personal Access Token)
#         Required scopes: repo, actions
#         Token will look like: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# STEP 3: Run the onboarding script with YOUR_GITHUB_TOKEN
node scripts/onboard-client.js \
  https://github.com/acme/webapp \
  YOUR_GITHUB_TOKEN

# Example with actual token:
# node scripts/onboard-client.js \
#   https://github.com/nhomyk/react_project \
#   ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# STEP 4: Share the dashboard link with client
# Dashboard: http://localhost:3000?client=client_a1b2c3d4e5f6
```

**⚠️ COMMON ERROR:** If you see `Cannot find module 'scripts/onboard-client.js'`:
- Make sure you're in the AgenticQA directory: `/Users/nicholashomyk/mono/AgenticQA`
- Check your current directory: `pwd`
- Run `cd /Users/nicholashomyk/mono/AgenticQA` first, then try the command again

### For Clients

Once onboarded, you can run the pipeline in three ways:

**Option 1: On Every Push (Automatic)**
```bash
git push origin main
# ↓ Workflow triggers automatically ↓
# Check GitHub Actions tab for progress
```

**Option 2: Manual from GitHub**
1. Go to your repository
2. Click "Actions" tab
3. Select "AgenticQA Client Pipeline"
4. Click "Run workflow"
5. Monitor progress in real-time

**Option 3: From AgenticQA Dashboard**
1. Open your dashboard link
2. Click "🚀 Trigger Client Pipeline"
3. View results as they stream in

---

## What Happens When Pipeline Runs

### Phase 1: Scan Codebase
- Analyzes your repository structure
- Counts files and detects technologies
- Checks directory organization

### Phase 2: Detect Issues  
- Security vulnerabilities
- Accessibility problems
- Performance bottlenecks
- Missing configurations

### Phase 3: Generate Tests
- Playwright test templates
- Cypress test templates
- Vitest test templates
- Test case suggestions

### Phase 4: Run Compliance
- GDPR compliance check
- SOC2 requirements
- HIPAA standards
- CCPA compliance
- LGPD compliance
- PCI-DSS compliance
- ISO 27001 standards

### Phase 5: Generate Report
- Comprehensive analysis
- Recommendations for improvements
- Risk assessment
- Action items

---

## Dashboard Features

### View Client Repository Info
```
Client ID: client_a1b2c3d4e5f6
Repository: https://github.com/acme/webapp
Status: 🟢 Active (5 runs)
```

### Trigger Pipeline
Click "🚀 Trigger Client Pipeline" to:
- Queue a new pipeline run
- Execute in your repository context
- Stream results to dashboard

### Monitor Results
- Real-time phase execution status
- Issue count and severity
- Test cases generated
- Compliance scores
- Recommendations

---

## Environment Setup

### GitHub Token Generation

⚠️ **IMPORTANT: Use "Generate new token (classic)" - NOT the newer fine-grained token option**

1. Go to https://github.com/settings/tokens
2. Click **"Generate new token (classic)"** (not "New token")
3. Give it a name: `AgenticQA Test Token`
4. Select these scopes:
   - ✅ `repo` - Full control of repositories
   - ✅ `actions` - Manage GitHub Actions
5. Scroll to bottom and click "Generate token"
6. Copy the token immediately (you'll only see it once!)
7. Never commit this token to version control

**Why classic?** The classic token type has simpler configuration and works perfectly for AgenticQA. Fine-grained tokens require additional setup that isn't necessary for this use case.

### Local Development

```bash
# Clone AgenticQA
git clone https://github.com/nhomyk/AgenticQA.git
cd AgenticQA

# Install dependencies
npm install

# Start SaaS server
npm run server:saas
# Server runs on http://localhost:3001

# Start dashboard
npm start
# Dashboard runs on http://localhost:3000

# Run onboarding script
node scripts/onboard-client.js <repo_url> <token>
```

---

## Workflow File Location

After onboarding, a new file appears in your repository:

```
your-repo/
├── .github/
│   └── workflows/
│       └── agentic-qa.yml  ← Added by onboarding script
```

This file:
- Runs automatically on pushes to main
- Can be manually triggered from Actions tab
- Downloads AgenticQA executor on first run
- Uploads results to dashboard

---

## Understanding Dashboard Links

Each client gets a unique dashboard link:

```
http://localhost:3000?client=client_a1b2c3d4e5f6
                              └─────────────────┘
                                    │
                                Unique to each client
```

This URL:
- Shows your specific repository
- Displays your pipeline history
- Allows triggering pipelines
- Shows only your results (secure)

---

## Troubleshooting

### "Pipeline didn't trigger"
1. Check GitHub token has correct scopes
2. Verify repository is public or token has access
3. Check GitHub Actions is enabled in repository settings

### "Can't see results on dashboard"
1. Wait 30 seconds for results to upload
2. Check `AGENTIC_QA_API` environment variable
3. Verify workflow file exists: `.github/workflows/agentic-qa.yml`
4. Check GitHub Actions tab for workflow logs

### "Token error"
1. Generate new token with correct scopes
2. Ensure `repo` and `actions` scopes are selected
3. Re-run onboarding script with new token

### "Can't access dashboard"
1. Verify dashboard is running: `npm start`
2. Check browser console for errors
3. Try incognito mode to clear cache

---

## Next Steps

1. ✅ Repository onboarded
2. Run first pipeline (manual or automatic)
3. Review results on dashboard
4. Fix identified issues
5. Re-run pipeline to track improvements
6. Integrate into CI/CD pipeline
7. Set up alerts/notifications

---

## Support

For help:
- Check GitHub Actions logs: `Actions` tab in your repository
- Review dashboard results
- Check AgenticQA server logs (if self-hosted)
- Contact support with your client ID

---

**Happy Testing! 🎉**
