# Recent Pipelines Update - Visual Guide

## Architecture Change

### BEFORE: Hardcoded Repository
```
┌─────────────────────────────────────┐
│     Dashboard (port 3000)           │
│                                     │
│   Recent Pipelines (Last 20)        │
│   ├─ #142 - CI/CD [MOCK]            │
│   ├─ #141 - CI/CD [MOCK]            │
│   ├─ #140 - Tests [MOCK]            │
│   └─ #139 - Security [MOCK]         │
│                                     │
│  (Hardcoded: nhomyk/AgenticQA)      │
│                                     │
└──────────────┬──────────────────────┘
               │
         GitHub API
               │
      nhomyk/AgenticQA  ← ALWAYS THIS REPO
      (5 recent runs)
```

### AFTER: User's Repository
```
┌─────────────────────────────────────┐
│     Dashboard (port 3000)           │
│                                     │
│     Recent Pipelines                │ ← No "(Last 20)"
│     ├─ #1254 - Build [REAL]         │
│     ├─ #1253 - Security [REAL]      │
│     ├─ #1252 - Deploy [REAL]        │
│     └─ #1251 - Tests [REAL]         │
│                                     │
│  (Dynamic: User's connected repo)   │
│                                     │
└──────────────┬──────────────────────┘
               │
         /api/github/status
         (get user's repo)
               │
         GitHub API
               │
      user-owner/user-repo ← DYNAMIC
      (20 recent runs)
```

---

## Data Flow

### BEFORE
```
User Dashboard
      ↓
fetch('https://api.github.com/repos/nhomyk/AgenticQA/actions/runs?per_page=5')
      ↓
GitHub API
      ↓
Mock data if fails
      ↓
Display 5 sample pipelines
```

### AFTER
```
User Dashboard
      ↓
1. Get user's GitHub repo:
   fetch('/api/github/status', { auth: JWT })
      ↓
   saas-api-dev.js returns: { repository: "owner/repo" }
      ↓
2. Get that repo's pipelines:
   fetch('https://api.github.com/repos/owner/repo/actions/runs?per_page=20')
      ↓
   GitHub API returns: [real pipeline data]
      ↓
3. Display 20 actual pipelines from user's repo
```

---

## Component Changes

### Header Title
```html
<!-- BEFORE -->
<h2 class="card-title">Recent Pipelines (Last 20)</h2>

<!-- AFTER -->
<h2 class="card-title">Recent Pipelines</h2>
```

### Function Logic
```javascript
// BEFORE (3 lines)
const response = await fetch('https://api.github.com/repos/nhomyk/AgenticQA/actions/runs?per_page=5');
// Use fallback mock data if error
displayMockPipelines();

// AFTER (7 lines)
// 1. Get connected repo
const statusResponse = await fetch('/api/github/status', {...});
const statusData = await statusResponse.json();

// 2. Get that repo's pipelines
const response = await fetch(`https://api.github.com/repos/${statusData.repository}/actions/runs?per_page=20`);
// Show helpful error messages
```

---

## State Handling

### Before
```
Always → GitHub API → Display or Show Mock
         (single source)
```

### After
```
Request → Get Repo → Use Repo → GitHub API → Display
  ↓         ↓          ↓          ↓
Check   Check if   Validate   Show Error
Auth    Connected  & Parse     Message
```

---

## Error Messages

### BEFORE
- "Loading..."
- [Sample data] or error

### AFTER
```
No Connection:
"Connect your GitHub repository in Settings to see pipeline results."

API Error:
"Unable to fetch pipeline data. Check that your GitHub token has the correct permissions."

No Pipelines:
"No recent pipelines. Commit and push to owner/repo to trigger a pipeline."

Unexpected Error:
"Error loading pipeline data: [actual error message]"
```

---

## Configuration Changes

### Request Parameters

**Before:**
```
Repository: nhomyk/AgenticQA (hardcoded)
Results: 5 pipelines
Refresh: 30 seconds
Data: Mock/fallback if unavailable
```

**After:**
```
Repository: user's connected repo (dynamic)
Results: 20 pipelines
Refresh: 30 seconds
Data: Only real data from GitHub API
```

---

## User Experience Flow

### Before
```
User Opens Dashboard
    ↓
Sees "Recent Pipelines (Last 20)"
    ↓
Sees sample/mock data
    ↓
Data not relevant to user's work
```

### After
```
User Opens Dashboard
    ↓
Sees "Recent Pipelines"
    ↓
Sees actual pipelines from their repo
    ↓
Data is relevant and actionable
    ↓
Can see build status, branches, commits
```

---

## API Endpoint Usage

### Before
- GitHub API only
- No backend involvement
- Hardcoded repository

### After
- **Step 1:** Backend endpoint: `/api/github/status`
  - Gets user's connected repo
  - Requires JWT auth
  
- **Step 2:** GitHub API endpoint
  - Fetches pipelines for that repo
  - No auth needed (public)

---

## Performance Comparison

| Aspect | Before | After | Impact |
|--------|--------|-------|--------|
| API Calls | 1 | 2 | +1 call (~50ms) |
| Data Accuracy | Mock | Real | Major improvement |
| Pipeline Count | 5 | 20 | 4x more visibility |
| Auth Required | No | Yes | Better security |
| User-Specific | No | Yes | Better UX |

---

## File Size Changes

| File | Before | After | Change |
|------|--------|-------|--------|
| dashboard.html | ~75KB | ~73KB | -2KB (removed mock data function) |
| test-dashboard-ui.js | ~12KB | ~12KB | No change |

---

## Removal Summary

### Deleted Code
```javascript
// REMOVED: Mock data function (~50 lines)
function displayMockPipelines() {
    const mockPipelines = [
        { run_number: 142, ... },
        { run_number: 141, ... },
        // ... sample data
    ];
    // ... display logic
}
```

### Added Code
```javascript
// ADDED: Dynamic repo fetching (~15 lines)
const statusResponse = await fetch('/api/github/status', {...});
const statusData = await statusResponse.json();
if (!statusData.connected || !statusData.repository) {
    // Show helpful message
}
const response = await fetch(`https://api.github.com/repos/${statusData.repository}/actions/runs?per_page=20`);
```

---

## Feature Comparison Matrix

| Feature | Before | After |
|---------|--------|-------|
| Show Real Data | ✗ | ✓ |
| User-Specific | ✗ | ✓ |
| Hardcoded Repo | ✓ | ✗ |
| Mock Fallback | ✓ | ✗ |
| Up to 5 Results | ✓ | ✗ |
| Up to 20 Results | ✗ | ✓ |
| Error Messages | Generic | Specific |
| "(Last 20)" Label | ✓ | ✗ |

---

## Testing Before/After

### Test Case 1: User with Connected Repo
- **Before:** Sees mock data
- **After:** Sees real pipelines from their repo ✓

### Test Case 2: User without Connected Repo
- **Before:** Sees mock data anyway
- **After:** Helpful message to connect ✓

### Test Case 3: GitHub API Error
- **Before:** Shows mock data silently
- **After:** Explains the problem ✓

---

**Summary:** The change makes the dashboard more relevant, accurate, and user-specific by displaying real pipeline results from each user's connected GitHub repository instead of hardcoded sample data.
