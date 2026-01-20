# Quick Reference - Recent Pipelines Update

## Summary of Changes

### ✅ What Changed
- **Title:** "Recent Pipelines (Last 20)" → "Recent Pipelines"
- **Data Source:** Hardcoded repo → User's connected GitHub repository
- **Pipeline Count:** 5 → 20
- **Mock Data:** Removed completely
- **Error Handling:** New dynamic error messages

### ✅ What Stayed the Same
- Dashboard layout and styling
- Refresh interval (30 seconds)
- Pipeline display format
- API endpoints
- User authentication

---

## User Experience

### Before
```
Recent Pipelines (Last 20)
├─ #142 - Full CI/CD with Safeguards [mock data]
├─ #141 - Full CI/CD with Safeguards [mock data]
└─ ... [hardcoded sample data]
```

### After
```
Recent Pipelines
├─ #1254 - Build and Test [real data from user's repo]
├─ #1253 - Security Scan [real data from user's repo]
├─ #1252 - Deploy to Staging [real data from user's repo]
└─ ... [up to 20 recent pipelines]
```

---

## How It Works

```
1. User opens dashboard
2. loadRecentPipelines() runs automatically
3. System fetches /api/github/status (gets user's repo)
4. System queries GitHub API for that repo's pipelines
5. Real pipeline results displayed (auto-refreshes every 30 seconds)
```

---

## Files Changed

| File | Type | Change |
|------|------|--------|
| public/dashboard.html | HTML/JS | Title update + dynamic loading |
| test-dashboard-ui.js | Test | Removed "Last 20" assertion |

---

## Testing Checklist

- [ ] User can see "Recent Pipelines" (without "Last 20")
- [ ] User with connected repo sees real pipelines
- [ ] User without connected repo sees setup message
- [ ] Pipelines refresh every 30 seconds
- [ ] Correct number of pipelines displayed (up to 20)
- [ ] Pipeline status colors correct (success/failed/running)
- [ ] Branch names display correctly
- [ ] Commit messages show (first 50 chars)
- [ ] Time ago formatting works
- [ ] Error messages display correctly

---

## Key Features

✅ **Real-Time Data**
- Shows actual pipeline results from user's GitHub repository
- Auto-refreshes every 30 seconds
- No mock/sample data

✅ **User-Specific**
- Each user sees their own repository's pipelines
- Requires GitHub connection in Settings
- JWT token authentication

✅ **Better Feedback**
- Clear messages when not connected
- Helpful error messages with hints
- Shows repository name in prompts

✅ **More Results**
- Now shows up to 20 pipelines (was 5)
- Easier to see recent history

---

## How to Use

### For End Users
1. Connect GitHub repository in Settings
2. Open dashboard
3. Scroll to "Recent Pipelines"
4. See actual pipeline results from your repo
5. Results update automatically every 30 seconds

### For Developers
1. Git push to your connected repository
2. Workflow triggers automatically
3. Results appear on dashboard within ~30 seconds

---

## Dependencies

✅ `/api/github/status` endpoint
- Requires: JWT authentication
- Returns: User's connected repository name

✅ GitHub API
- Endpoint: https://api.github.com/repos/{owner/repo}/actions/runs
- No authentication needed (public data)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Connect your GitHub repository..." | Go to Settings → GitHub Integration → Connect Repo |
| "Unable to fetch pipeline data..." | Check GitHub token has `repo` + `actions` scopes |
| "No recent pipelines..." | Commit & push to your main branch to trigger workflows |
| Dashboard shows old mock data | Clear browser cache or hard refresh (Cmd+Shift+R) |

---

## Before & After Code

### Before
```javascript
const response = await fetch('https://api.github.com/repos/nhomyk/AgenticQA/actions/runs?per_page=5');
```

### After
```javascript
const statusResponse = await fetch('/api/github/status', {
    headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
});
const statusData = await statusResponse.json();
const response = await fetch(`https://api.github.com/repos/${statusData.repository}/actions/runs?per_page=20`);
```

---

**Status:** ✅ Complete and Ready for Use

**Test:** `npm start` then navigate to dashboard → Recent Pipelines section
