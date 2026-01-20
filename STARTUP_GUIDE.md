# 🚀 Quick Startup Guide

## The Problem
Localhost isn't working because the servers aren't running.

## The Solution

### Option 1: Run Both Servers (Easiest)

```bash
cd /Users/nicholashomyk/mono/AgenticQA
node start-all.js
```

This will:
- ✅ Kill any existing processes on ports 3000 and 3001
- ✅ Start API server (port 3001) - saas-api-dev.js
- ✅ Start Dashboard server (port 3000) - server.js
- ✅ Both in development mode with auto-login enabled

### Option 2: Run Servers Separately (If you need to debug)

**Terminal 1 - API Server (port 3001):**
```bash
cd /Users/nicholashomyk/mono/AgenticQA
NODE_ENV=development node saas-api-dev.js
```

**Terminal 2 - Dashboard Server (port 3000):**
```bash
cd /Users/nicholashomyk/mono/AgenticQA
NODE_ENV=development node server.js
```

## Testing the Flow

Once servers are running:

### 1. Open Dashboard
```
http://localhost:3000/public/dashboard.html
```
- Auto-login will activate automatically
- Token will be stored in localStorage

### 2. Open Settings
```
http://localhost:3000/public/settings.html
```
- Auto-login will activate automatically
- You can click "Setup Workflow File"
- This deploys the 48-line bulletproof workflow

### 3. Test API Directly (optional)
```bash
# Check if API is responding
curl http://localhost:3001/api/health

# Get GitHub status (uses auto-login token)
curl -X GET http://localhost:3001/api/github/status \
  -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE"
```

## Verify Auto-Login Works

1. Open browser Developer Tools (F12)
2. Go to Console tab
3. Open http://localhost:3000/public/dashboard.html
4. You should see:
   ```
   ✅ Token already exists in localStorage
   ```
   OR
   ```
   🔄 No token found. Attempting auto-login with demo credentials...
   ✅ Auto-login successful! Token stored.
   ```

## Demo Credentials (Auto-Login Uses These)
```
Email: demo@orbitqa.ai
Password: demo123
User ID: user_default
Org ID: org_default
```

## Default Ports
- **Dashboard**: http://localhost:3000
- **API**: http://localhost:3001

## Troubleshooting

### Port Already in Use
If you get "port already in use" error:

```bash
# Kill processes on ports 3000 and 3001
lsof -ti:3000,3001 | xargs kill -9

# Then try again
node start-all.js
```

### Module Not Found
If you get "cannot find module" errors:

```bash
cd /Users/nicholashomyk/mono/AgenticQA
npm install
node start-all.js
```

### Servers Won't Start
Check if Node.js is installed:
```bash
node --version  # Should be v18+
npm --version   # Should be v9+
```

## What's Implemented

✅ **Auto-Login**: Both dashboard.html and settings.html auto-login on page load
✅ **Token Persistence**: JWT stored in localStorage for all API calls
✅ **Backend Fallback**: Dev mode fallback to demo user if auth fails
✅ **Bulletproof Workflow**: 48-line workflow with no syntax errors
✅ **Setup Endpoint**: /api/github/setup-workflow ready to deploy workflows

## Expected Flow

```
1. User loads http://localhost:3000/public/settings.html
   ↓
2. autoLogin() runs automatically
   ↓
3. Token obtained and stored in localStorage
   ↓
4. User clicks "Setup Workflow File"
   ↓
5. Frontend sends POST /api/github/setup-workflow with token
   ↓
6. Backend authenticates (uses dev fallback if needed)
   ↓
7. 48-line bulletproof workflow deployed to GitHub
   ↓
8. First workflow run succeeds ✅
   ↓
9. Client is onboarded! 🎉
```

## Questions?

Check the browser console (F12) for detailed logs of the auto-login process.
