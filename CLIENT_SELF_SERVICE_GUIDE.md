# 🎯 AgenticQA Self-Service Client Guide

For clients who want to use AgenticQA independently without provider assistance.

## Quick Start (2 Minutes)

### 1. Open the Setup Page
```
https://your-agentic-qa-domain.com/dashboard
```

You'll see the **Setup AgenticQA Pipeline** form.

### 2. Enter Your Repository URL
```
https://github.com/your-organization/your-repo
```

### 3. Create a GitHub Token
1. Go to: https://github.com/settings/tokens
2. Click **"Generate new token (classic)"** (⚠️ NOT fine-grained)
3. Give it a name: `AgenticQA`
4. Select these scopes:
   - ✅ `repo` - Full control of repositories
   - ✅ `actions` - Manage GitHub Actions
5. Click "Generate token"
6. Copy the token (displayed only once!)

### 4. Paste Token and Submit
```
1. Paste your token in the "GitHub Personal Access Token" field
2. Click "✨ Setup Pipeline"
3. Wait for confirmation...
```

### 5. Done! 🎉
Your repository now has:
- ✅ `.github/workflows/agentic-qa.yml` - Automated pipeline
- ✅ `.agentic-qa/executor.js` - Pipeline executor (downloads on first run)

**Next Step:** Push a change to GitHub and the pipeline runs automatically!

---

## Understanding the Setup Flow

### What Happens Behind the Scenes

```
┌─────────────────────────────────────┐
│ Client Opens Setup Page             │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ Enters GitHub Repo & Personal Token │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ AgenticQA API Creates Workflow File │
│ in Client's Repository (via GitHub) │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ Workflow File Committed & Pushed    │
│ to Client's Main Branch             │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ Client ID Generated for Tracking    │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ Dashboard Link Provided for Results │
└─────────────────────────────────────┘
```

### What Gets Created

**Workflow File Location:**
```
your-repo/.github/workflows/agentic-qa.yml
```

**Executor Location:**
```
your-repo/.agentic-qa/executor.js
```

---

## Triggering Pipelines

### Option 1: Automatic (Recommended)
Every time you push to GitHub, the pipeline runs automatically:
```bash
git push origin main
# ↓ Workflow triggers automatically
```

### Option 2: Manual from GitHub
1. Go to: `https://github.com/your-org/your-repo/actions`
2. Click **"AgenticQA Client Pipeline"**
3. Click **"Run workflow"**
4. Select branch and click **"Run workflow"**

### Option 3: Dashboard
1. Open your dashboard link from setup
2. Click **"🚀 Trigger Client Pipeline"**
3. Workflow starts in GitHub Actions

---

## Monitoring Pipeline Execution

### Real-Time Logs
```
1. Go to your repository's Actions tab
2. Click the running workflow
3. Expand each step to see logs:
   - 📥 Checkout Repository
   - 🔧 Setup Node.js
   - 📦 Download AgenticQA Executor
   - 🔍 Run AgenticQA Pipeline
   - 📤 Upload Results to Dashboard
   - 📝 Create Summary Report
```

### Expected Duration
- **First run:** 3-5 minutes (downloads executor)
- **Subsequent runs:** 2-3 minutes (cached executor)

---

## Pipeline Analysis

### What Your Code Is Analyzed For

#### 1. **Codebase Structure**
- File organization
- Technology stack detection
- Directory patterns

#### 2. **Issues Detected**
- Security vulnerabilities
- Accessibility problems
- Performance bottlenecks
- Missing configurations

#### 3. **Test Generation**
- Playwright test templates
- Cypress test templates
- Vitest test templates

#### 4. **Compliance Checks**
- ✅ GDPR compliance
- ✅ SOC2 requirements
- ✅ HIPAA standards
- ✅ CCPA compliance
- ✅ LGPD compliance
- ✅ PCI-DSS compliance
- ✅ ISO 27001 standards

#### 5. **Recommendations**
- Best practices
- Security improvements
- Performance suggestions
- Testing guidance

---

## Viewing Results

### On Dashboard
After pipeline completes, results appear at:
```
https://your-agentic-qa-domain.com/dashboard?client=CLIENT_ID
```

**Visible:**
- Phase execution status
- Issues found with severity levels
- Test cases generated
- Compliance scores
- Actionable recommendations

### GitHub Actions Summary
Each workflow execution creates a summary report in GitHub Actions with:
- Total issues found
- Compliance status
- Generated test templates
- Next recommended actions

---

## Troubleshooting

### ❌ "Setup failed - unauthorized"
**Cause:** Token doesn't have required permissions
**Solution:**
1. Go to https://github.com/settings/tokens
2. Check token has `repo` ✅ and `actions` ✅ scopes
3. If not, create a new token with correct scopes
4. Try setup again

### ❌ "Workflow didn't run"
**Cause:** GitHub Actions not enabled
**Solution:**
1. Go to your repo settings
2. Find "Actions" section
3. Ensure "Actions permissions" is set to enabled
4. Try pushing a new commit

### ❌ "Invalid repository URL"
**Cause:** URL format incorrect
**Solution:**
Valid URLs:
- ✅ `https://github.com/user/repo`
- ✅ `git@github.com:user/repo.git`
- ❌ `github.com/user/repo` (missing https://)
- ❌ `https://github.com/user/repo/` (trailing slash)

### ❌ "Results not appearing"
**Cause:** Workflow hasn't completed or results uploading
**Solution:**
1. Check GitHub Actions page - is workflow still running?
2. Wait 30 seconds after workflow completes
3. Refresh dashboard browser page
4. Check browser console for errors (F12)

### ❌ "Token error: Cannot authenticate"
**Cause:** Token expired or revoked
**Solution:**
1. Go to https://github.com/settings/tokens
2. Verify token still exists and hasn't expired
3. If expired, create a new token
4. Run setup again with new token

---

## Security

### Token Safety
- ⚠️ Never commit your token to version control
- ✅ Token is encrypted when stored
- ✅ Only used to create workflow file once
- ✅ Token scopes are limited (`repo` + `actions` only)

### What AgenticQA Can Access
With your token, AgenticQA can:
- ✅ Create workflow files in your repository
- ✅ Trigger GitHub Actions workflows
- ✅ Read your repository structure (for analysis)

AgenticQA **cannot**:
- ❌ Delete your repository
- ❌ Push commits (except workflow file during setup)
- ❌ Access private data outside the repository
- ❌ Modify repository settings

### Revoking Access
To stop AgenticQA at any time:
1. Go to https://github.com/settings/tokens
2. Find your token
3. Click "Delete"
4. Remove `.github/workflows/agentic-qa.yml` from your repo (optional)

---

## Advanced Usage

### Environment Variables in Workflow
The workflow passes these to the executor:
```bash
CLIENT_ID        # Your unique client identifier
REPOSITORY       # owner/repo format
BRANCH           # Current branch name
AGENTIC_QA_API   # Dashboard API endpoint
```

### Custom Branch Triggers
Edit `.github/workflows/agentic-qa.yml` to change which branches trigger:
```yaml
on:
  push:
    branches: [main, develop, staging]  # Add/remove branches
```

### Scheduled Runs
Schedule daily scans by modifying the workflow:
```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
```

---

## FAQ

**Q: How often should I run the pipeline?**
A: Automatically on every push (recommended) or weekly for just reviews.

**Q: Can I share the dashboard link with my team?**
A: Yes! Use `?client=CLIENT_ID` to share results with anyone.

**Q: What if I want to change my repository?**
A: You'll need to run setup again with the new repository URL.

**Q: Does AgenticQA make commits to my repo?**
A: Only the initial workflow file. Then it only reads and analyzes.

**Q: Can I customize the analysis?**
A: The executor is in `.agentic-qa/executor.js` - advanced users can customize phases.

**Q: How do I see historical results?**
A: Check your GitHub Actions history for all previous runs and their logs.

---

## Support

For issues or questions:
1. Check Troubleshooting section above
2. Review GitHub Actions logs for detailed errors
3. Contact support with your client ID

---

**Ready to get started?**

→ [Open Setup Page](https://your-agentic-qa-domain.com/dashboard)

