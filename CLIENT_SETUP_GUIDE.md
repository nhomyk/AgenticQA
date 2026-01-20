# 🚀 AgenticQA Client Setup Guide

> **⚠️ IMPORTANT:** This guide has TWO sections:
> - **For Clients:** Self-service setup (NEW - recommended!)
> - **For Providers:** Team-based onboarding (legacy)

---

## 🎯 For Clients: Self-Service Setup (Easiest)

**No installation needed. No configuration. Just 2 minutes!**

### Step 1: Open Dashboard
```
https://your-agentic-qa-domain.com/dashboard
```

You'll see the **Setup AgenticQA Pipeline** form (no login required).

### Step 2: Enter Repository URL
```
https://github.com/your-org/your-repo
```

### Step 3: Create GitHub Token
1. Go to: https://github.com/settings/tokens
2. Click **"Generate new token (classic)"** (⚠️ NOT fine-grained)
3. Give it a name: `AgenticQA`
4. Select scopes:
   - ✅ `repo` (full repository access)
   - ✅ `actions` (manage GitHub Actions)
5. Click "Generate token" and copy it

### Step 4: Complete Setup
1. Paste your GitHub token
2. Click **"✨ Setup Pipeline"**
3. Done! 🎉

**What happens:**
- Workflow file created in your repo: `.github/workflows/agentic-qa.yml`
- Pipeline triggers automatically on next push
- Results appear on your dashboard with client ID

---

## 🆔 Understanding the Client ID

After setup completes, you'll receive a **Client ID**. This is a unique identifier for your dashboard:

```
Example: client_abc123def456
```

**What it does:**
- Links your GitHub workflow runs to your dashboard
- All test results are reported under this ID
- You can have multiple repositories linked to one Client ID
- Share this ID to add team members to your dashboard

**Where to find your Client ID:**
1. Check the setup confirmation message
2. On the dashboard: Settings → Your Client ID
3. In GitHub Actions: "Run workflow" button → "Client ID for dashboard" field

### 📖 Full Self-Service Guide
See [CLIENT_SELF_SERVICE_GUIDE.md](CLIENT_SELF_SERVICE_GUIDE.md) for detailed information about:
- Monitoring pipeline execution
- Understanding analysis results  
- Triggering manual runs
- Troubleshooting
- Security & token management

---

## ▶️ Running Your Pipeline Manually

The pipeline can run automatically (on push/pull request) or manually on-demand.

### From GitHub Actions UI (Recommended)

1. Go to your repository: `https://github.com/YOUR-ORG/YOUR-REPO`
2. Click the **"Actions"** tab
3. Click **"AgenticQA Client Pipeline"** workflow (left sidebar)
4. Click the **"Run workflow"** button (top right)
5. A dropdown will appear with options:
   - **Branch**: Select `main` (or your target branch)
   - **Client ID for dashboard**: Paste your Client ID here (e.g., `client_abc123`)
6. Click **"Run workflow"** button to start

**Note:** The workflow will complete in 2-5 minutes. You'll see status updates as it runs.

### From Command Line (Advanced)

If you prefer to trigger from the terminal:

```bash
# Using GitHub CLI (recommended)
gh workflow run agentic-qa.yml \
  --repo YOUR-ORG/YOUR-REPO \
  --ref main \
  -f client_id="client_abc123"
```

Or using `curl`:

```bash
curl -X POST \
  https://api.github.com/repos/YOUR-ORG/YOUR-REPO/actions/workflows/agentic-qa.yml/dispatches \
  -H "Authorization: token YOUR_GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -d '{
    "ref": "main",
    "inputs": {
      "client_id": "client_abc123"
    }
  }'
```

### Automatic Triggers

Your pipeline runs automatically on:
- ✅ **Push to main branch**
- ✅ **Push to develop branch**
- ✅ **Pull requests** (on main or develop)

To modify these triggers, edit `.github/workflows/agentic-qa.yml` and change the `on:` section.

---

## 👥 For Providers: Team Onboarding (Legacy)

If you're onboarding clients on behalf of a team or managing multiple clients...

### Quick Start

```bash
# STEP 1: Navigate to AgenticQA directory
cd /Users/nicholashomyk/mono/AgenticQA

# STEP 2: Run onboarding script
node scripts/onboard-client.js \
  https://github.com/acme/webapp \
  YOUR_GITHUB_TOKEN \
  /optional/local/path/to/repo

# STEP 3: Share dashboard link with client
# Dashboard: http://localhost:3000?client=client_a1b2c3d4e5f6
```

**⚠️ COMMON ERROR:** If you see `Cannot find module 'scripts/onboard-client.js'`:
- Make sure you're in the AgenticQA directory: `/Users/nicholashomyk/mono/AgenticQA`
- Check your current directory: `pwd`
- If running from client directory, use Option B with full path to client repo

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

### "Actions must be from a repository owned by X" Error
This occurs when your GitHub organization has **GitHub Actions security policies** enabled that restrict which actions can run.

**Solutions:**

#### Option 1: Allow All Actions (Fastest)
1. Go to: https://github.com/organizations/YOUR-ORG-NAME/settings/actions/general
   - Replace `YOUR-ORG-NAME` with your actual organization name
2. Under **"Actions permissions"**, select: **"Allow all actions and reusable workflows"**
3. Click **"Save"**
4. Done! All workflows will now work

#### Option 2: Allow Only Approved Actions (Most Secure - Recommended)
If you want to restrict to specific actions:

1. Go to: https://github.com/organizations/YOUR-ORG-NAME/settings/actions/general
2. Under **"Actions permissions"**, select: **"Allow select actions and reusable workflows"**
3. Check these boxes:
   - ✅ "Allow actions created by GitHub"
   - ✅ "Allow actions by Marketplace verified creators"
4. Optionally add your own organization's actions:
   - Click "Add selection" and enter: `your-org/*`
5. Click **"Save"**

#### Option 3: Fix Individual Workflows (If you have external actions)
If you have existing workflows using external actions (like SonarQube, CodeQL, etc.) that are causing issues:

1. Go to your repo: `github.com/your-org/your-repo`
2. Click **"Actions"** tab
3. Find the failing workflow
4. Click the workflow file name (e.g., `sonarqube-scan.yml`)
5. Click the pencil icon (✏️) to edit
6. Either:
   - **Remove the external action** (delete those steps)
   - **Replace with built-in tools** (e.g., use `npm audit` instead of external security scan)
7. Click **"Commit changes"**

#### Why AgenticQA Works with Restrictions
The AgenticQA workflow **does NOT use external actions** - it only uses:
- `git` (built-in)
- `curl` (built-in)
- `node` (standard tool)

So even with strict policies, AgenticQA will run fine once you handle your existing actions.

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
