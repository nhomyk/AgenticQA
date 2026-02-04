# GitHub Secrets Setup - Detailed Guide 🔐

## Step-by-Step Instructions for Adding Weaviate Secrets

### Part 1: Navigate to Secrets Settings

#### Option A: Direct URL (Fastest)
1. Open this URL in your browser:
   ```
   https://github.com/nhomyk/AgenticQA/settings/secrets/actions
   ```
2. You should see "Actions secrets and variables" page
3. Skip to Part 2 below

#### Option B: Manual Navigation
1. Go to your repository: https://github.com/nhomyk/AgenticQA

2. **Click "Settings"** tab (top navigation bar, far right)
   ```
   Code | Issues | Pull requests | Actions | Projects | Wiki | Security | Insights | Settings
                                                                                          ↑ HERE
   ```

3. **In the left sidebar**, scroll down and find:
   ```
   Security
     ↓
   Secrets and variables  ← Click this
     ↓
   Actions  ← Click this
   ```

4. You should now see the **"Actions secrets and variables"** page

---

### Part 2: Add Secret #1 - WEAVIATE_HOST

#### Step 1: Start Adding Secret
1. Look for a green button that says **"New repository secret"** (top right)
2. Click it

#### Step 2: Fill in Secret Details
You'll see a form with two fields:

**Field 1: Name**
```
Name *
[                              ]  ← Enter: WEAVIATE_HOST
```
- Type exactly: `WEAVIATE_HOST`
- ⚠️ **Important:** All uppercase, underscore between words
- ⚠️ **Must match exactly** - GitHub secrets are case-sensitive!

**Field 2: Secret**
```
Secret *
[                              ]  ← Paste your cluster hostname
```
- Paste your Weaviate cluster hostname
- ✅ **Correct format:** `cluster-name-xxxxx.weaviate.network`
- ❌ **Wrong format:** `https://cluster-name-xxxxx.weaviate.network` (no https://)

**Example:**
```
Name: WEAVIATE_HOST
Secret: agenticqa-main-abc12345.weaviate.network
```

#### Step 3: Save Secret
1. Click the green **"Add secret"** button at the bottom
2. You should see a success message: "Secret WEAVIATE_HOST was added"
3. The secret will now appear in the list (value will be hidden as `***`)

---

### Part 3: Add Secret #2 - WEAVIATE_API_KEY

#### Step 1: Add Another Secret
1. Click **"New repository secret"** button again (same green button)

#### Step 2: Fill in API Key
**Field 1: Name**
```
Name *
[                              ]  ← Enter: WEAVIATE_API_KEY
```
- Type exactly: `WEAVIATE_API_KEY`

**Field 2: Secret**
```
Secret *
[                              ]  ← Paste your API key from Weaviate
```
- Go back to Weaviate Cloud dashboard
- Copy your API key (should start with `WCD...`)
- Paste it here

**Example:**
```
Name: WEAVIATE_API_KEY
Secret: WCDsomeVeryLongStringOfCharacters1234567890abcdef
```

#### Step 3: Save Secret
1. Click **"Add secret"** button
2. Success message: "Secret WEAVIATE_API_KEY was added"

---

### Part 4: Add Secret #3 - AGENTICQA_RAG_MODE

#### Step 1: Add Final Secret
1. Click **"New repository secret"** button one more time

#### Step 2: Fill in Mode
**Field 1: Name**
```
Name *
[                              ]  ← Enter: AGENTICQA_RAG_MODE
```
- Type exactly: `AGENTICQA_RAG_MODE`

**Field 2: Secret**
```
Secret *
[                              ]  ← Enter: cloud
```
- Type exactly: `cloud` (all lowercase)
- This tells AgenticQA to use Weaviate Cloud mode

**Example:**
```
Name: AGENTICQA_RAG_MODE
Secret: cloud
```

#### Step 3: Save Secret
1. Click **"Add secret"** button
2. Success message: "Secret AGENTICQA_RAG_MODE was added"

---

### Part 5: Verify All Secrets Are Added

You should now see **3 secrets** in the list:

```
Repository secrets

Name                      Updated
AGENTICQA_RAG_MODE       now
WEAVIATE_API_KEY         now
WEAVIATE_HOST            now

[New repository secret]
```

**✅ Checklist - All 3 secrets should be present:**
- [ ] `AGENTICQA_RAG_MODE`
- [ ] `WEAVIATE_API_KEY`
- [ ] `WEAVIATE_HOST`

---

## Troubleshooting

### Issue: "New repository secret" button is grayed out
**Solution:** You need admin/write permissions on the repository
- Check that you're logged into the correct GitHub account
- Verify you own or have access to the repository

### Issue: Can't find "Settings" tab
**Solution:** Settings tab only appears if you have write access
- Make sure you're looking at YOUR repository: https://github.com/nhomyk/AgenticQA
- Not viewing someone else's fork

### Issue: Typo in secret name
**Solution:** Delete and recreate
1. Click on the secret name in the list
2. Click red "Delete secret" button
3. Re-add with correct spelling

### Issue: Forgot to remove `https://` from WEAVIATE_HOST
**Solution:** Update the secret
1. Click "Update" next to WEAVIATE_HOST in the list
2. Change the value to remove `https://`
3. Save

---

## Visual Guide - What Each Screen Looks Like

### Screen 1: Repository Settings Page
```
┌─────────────────────────────────────────────────────┐
│ nhomyk / AgenticQA                          Settings│
├─────────────────────────────────────────────────────┤
│                                                       │
│ General                                               │
│ Access                                                │
│ Code and automation                                   │
│   ↓                                                   │
│ Security                                              │
│   Code security and analysis                          │
│   Deploy keys                                         │
│   Secrets and variables  ← Click here                │
│     Actions  ← Then click here                        │
│   Environments                                        │
│                                                       │
└─────────────────────────────────────────────────────┘
```

### Screen 2: Actions Secrets Page
```
┌─────────────────────────────────────────────────────┐
│ Actions secrets and variables                        │
├─────────────────────────────────────────────────────┤
│                                                       │
│ Secrets  Variables                                    │
│                                                       │
│ Repository secrets                  [New repository  │
│                                          secret]  ←   │
│                                                       │
│ (Empty list if no secrets yet)                       │
│                                                       │
└─────────────────────────────────────────────────────┘
```

### Screen 3: New Secret Form
```
┌─────────────────────────────────────────────────────┐
│ Actions secrets / New secret                         │
├─────────────────────────────────────────────────────┤
│                                                       │
│ Name *                                                │
│ ┌───────────────────────────────────────────┐       │
│ │ WEAVIATE_HOST                             │       │
│ └───────────────────────────────────────────┘       │
│                                                       │
│ Secret *                                              │
│ ┌───────────────────────────────────────────┐       │
│ │ cluster-name-abc123.weaviate.network      │       │
│ └───────────────────────────────────────────┘       │
│                                                       │
│                        [Add secret]  [Cancel]        │
│                                                       │
└─────────────────────────────────────────────────────┘
```

### Screen 4: Secrets List (After Adding All 3)
```
┌─────────────────────────────────────────────────────┐
│ Actions secrets and variables                        │
├─────────────────────────────────────────────────────┤
│                                                       │
│ Secrets  Variables                                    │
│                                                       │
│ Repository secrets                  [New repository  │
│                                          secret]      │
│                                                       │
│ Name                      Updated    [Update]        │
│ AGENTICQA_RAG_MODE       now         Update Remove  │
│ WEAVIATE_API_KEY         now         Update Remove  │
│ WEAVIATE_HOST            now         Update Remove  │
│                                                       │
└─────────────────────────────────────────────────────┘
```

---

## Quick Reference Card

Copy this for your reference:

```
SECRET 1:
  Name:   WEAVIATE_HOST
  Value:  [your-cluster].weaviate.network
  Format: hostname only (no https://)

SECRET 2:
  Name:   WEAVIATE_API_KEY
  Value:  WCD[your-api-key]
  Format: full key from Weaviate dashboard

SECRET 3:
  Name:   AGENTICQA_RAG_MODE
  Value:  cloud
  Format: lowercase word "cloud"
```

---

## What Happens Next?

After adding all 3 secrets:

1. **GitHub will use these in CI/CD**
   - Secrets are encrypted at rest
   - Only visible to workflow runs
   - Never exposed in logs

2. **Next CI run will connect to Weaviate**
   - Push any change to trigger pipeline
   - Or manually trigger from Actions tab

3. **Check logs for success**
   - Look for: "✅ Connected to Weaviate"
   - Look for: "✅ Success pattern stored to Weaviate!"

4. **Verify data in Weaviate**
   - Go to Weaviate Cloud → Your cluster → Query
   - Collection `AgenticQADocuments` will appear
   - Data populates after first CI run

---

## Security Notes

✅ **Safe Practices:**
- Secrets are encrypted by GitHub
- Only accessible to repository workflows
- Not visible in logs or pull requests
- Can be rotated anytime

❌ **Never:**
- Share API keys in code comments
- Commit secrets to git
- Post secrets in issues/PRs
- Share secrets publicly

🔄 **Rotating Keys:**
If you need to change your API key:
1. Generate new key in Weaviate Cloud
2. Update `WEAVIATE_API_KEY` secret in GitHub
3. Old key can be deleted in Weaviate

---

## Need Help?

**Common Questions:**

**Q: Can I test secrets locally?**
A: Yes! Set environment variables:
```bash
export WEAVIATE_HOST="your-cluster.weaviate.network"
export WEAVIATE_API_KEY="WCD..."
export AGENTICQA_RAG_MODE="cloud"
```

**Q: How do I know if secrets are working?**
A: Check next CI run logs for "✅ Connected to Weaviate"

**Q: Can I see the secret values after adding?**
A: No, GitHub hides them for security. You can only update or delete.

**Q: Do I need to restart anything after adding secrets?**
A: No, next workflow run will automatically use them.

---

**Status:** ✅ When all 3 secrets are added, your setup is complete!

**Next Step:** Trigger a CI run and watch the magic happen! 🚀
