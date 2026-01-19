# Quick Start: GitHub Integration

Get the GitHub Integration working in 5 minutes.

## Prerequisites

- orbitQA Dashboard running
- GitHub account with repository access

## Step 1: Start the Server (if not running)

```bash
npm run dev:saas-api
# Server will start on http://localhost:3001
```

## Step 2: Create GitHub Personal Access Token

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Name: `orbitQA Pipeline`
4. Scopes: ✅ repo, ✅ workflow, ✅ admin:repo_hook
5. Generate and **COPY** the token

## Step 3: Connect GitHub in Dashboard

1. Open Dashboard: http://localhost:3001/dashboard.html
2. Click ⚙️ Settings (top right)
3. GitHub Integration tab → "🔑 Use Personal Access Token"
4. **Paste Token**: `ghp_xxxxxxxxxxxxxxxxxxxx`
5. **Repository**: `username/repository` (e.g., `nicholashomyk/AgenticQA`)
6. Click "💾 Save Token"
7. You should see ✅ "GitHub Connected"

## Step 4: Test the Connection

1. In Settings, click "🧪 Test Connection"
2. Should show ✅ "GitHub connection test passed"

## Step 5: Trigger Your First Pipeline

1. Go back to Dashboard
2. Scroll to "Pipeline Control" section
3. Click "🚀 Launch Pipeline"
4. Check GitHub Actions: https://github.com/YOUR_USERNAME/YOUR_REPO/actions

Done! 🎉

## Troubleshooting

**Can't find Settings?**
- Click ⚙️ in top right of dashboard

**Token doesn't work?**
- Make sure token was generated in last step and not expired
- Check scopes: repo, workflow, admin:repo_hook
- Try creating a new token

**Can't trigger pipeline?**
- Ensure `.github/workflows/ci.yml` exists in your repo
- Try testing connection first (see Step 4)

## What's Happening

When you click "🚀 Launch Pipeline":

1. Dashboard sends request to backend: `/api/trigger-workflow`
2. Backend reads your GitHub token (saved in Settings)
3. Backend calls GitHub API to dispatch workflow
4. GitHub Actions runs your `ci.yml` workflow
5. You can monitor it at: github.com/YOUR_REPO/actions

## Documentation

- Full setup guide: See `GITHUB_INTEGRATION_SETUP.md`
- Implementation details: See `GITHUB_INTEGRATION_COMPLETE.md`
- Verify endpoints: `node verify-github-integration.js`

## Questions?

Check the full documentation files for:
- Security best practices
- Production deployment
- Error messages explained
- Multiple repository setup
- Custom workflows

**Status:** ✅ Ready to use!
