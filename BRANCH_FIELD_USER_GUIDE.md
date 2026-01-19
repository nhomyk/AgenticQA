# Branch Field - User Guide

## What Changed?

### Before ❌
- Branch was a text input field
- Users could type any branch name (including typos)
- Branch was optional
- No warning when deploying to production (main branch)

### After ✅
- Branch is now a dropdown with available branches
- Only valid branches can be selected
- Branch field is now required
- Warning appears before main branch deployment

---

## How to Use

### On the Dashboard

**Step 1: Select Pipeline Type**
```
Dropdown: "Full CI/CD Pipeline"
          "Tests Only"
          "Security Scan"
          etc.
```

**Step 2: Select Branch**
```
Dropdown: "main (protected)" ← Read-only, cannot type
          "develop"
          "staging"
```
- Required field (marked with *)
- Choose only from available branches
- Shows "(protected)" for protected branches

**Step 3: Launch Pipeline**

*If you selected non-main branch:*
- Click "🚀 Launch Pipeline"
- Pipeline launches immediately ✅

*If you selected "main":*
- Click "🚀 Launch Pipeline"
- ⚠️ Warning modal appears:

```
╔════════════════════════════════════╗
║ ⚠️  Main Branch Warning             ║
├────────────────────────────────────┤
║                                    ║
║ You are about to trigger a         ║
║ pipeline on the main branch.       ║
║                                    ║
║ This will deploy to production.    ║
║ Please ensure:                     ║
║                                    ║
║ ✓ All tests are passing            ║
║ ✓ Code has been reviewed           ║
║ ✓ Changes are production-ready     ║
║                                    ║
║ Are you sure you want to continue? ║
│                                    │
│  [Cancel]  [Yes, Deploy to Main]   │
╚════════════════════════════════════╝
```

**What to do:**
- Review the safety checklist
- Click "Cancel" if you want to select a different branch
- Click "Yes, Deploy to Main" only if everything is ready

---

### On the Settings Page

When testing GitHub connection:

**Step 1: Enter GitHub Token**
- Paste your GitHub Personal Access Token
- Click "Save Token"

**Step 2: Select Branch for Test**
```
Dropdown: "main (protected)" ← Read-only, cannot type
          "develop"
          "staging"
```
- Choose the branch to test with
- Required field

**Step 3: Test Trigger**

*If you selected non-main branch:*
- Click "Test Trigger"
- Test runs immediately ✅

*If you selected "main":*
- Click "Test Trigger"
- ⚠️ Same warning modal appears
- Must confirm before test runs

---

## Why These Changes?

### Safety
🛡️ **Main branch warning prevents accidents**
- Deploying to main affects production
- Warning ensures you're ready
- Checklist reminds you of requirements

### Reliability
✅ **Dropdown prevents typos**
- No more invalid branch names
- Only branches that exist in GitHub
- Automatic fallback to defaults

### Usability
🎯 **Clear indication of requirements**
- Branch field marked as required (*)
- Help text explains implications
- Protected branches clearly marked

### Professional
👔 **Production-grade safety**
- Forces explicit confirmation
- Documents deployment requirements
- Audit trail of safety checks

---

## Common Tasks

### Deploying to a Feature Branch
1. Select branch dropdown
2. Choose your feature branch (e.g., "feature/new-ui")
3. Click "Launch Pipeline"
4. Pipeline triggers immediately (no warning)

### Testing Before Production
1. Ensure all changes are merged to develop
2. Test pipeline on "develop" branch first
3. Verify all checks pass
4. Then deploy to "main" branch
5. Confirm with warning modal

### Quick Hotfix
1. Create and test on hotfix branch
2. Select "main" branch
3. Confirm all tests passing
4. Click "Launch Pipeline"
5. Review safety checklist
6. Click "Yes, Deploy to Main"

### Rolling Back
1. Cannot directly rollback (use GitHub)
2. Create new branch with reverted changes
3. Deploy that branch to production

---

## Troubleshooting

### Q: Why is the branch dropdown empty?
**A:** 
- Make sure GitHub is connected in Settings
- Check your GitHub token is valid
- Verify your repository is configured
- Fallback branches (main, develop) should always appear

### Q: Can I type in the branch field?
**A:** 
- No, it's read-only by design
- Only available branches can be selected
- This prevents typos and invalid names

### Q: How do I select a new branch?
**A:**
1. Make sure branch exists in GitHub
2. Wait for `/api/github/branches` to fetch latest
3. Refresh page if needed
4. New branches should appear in dropdown

### Q: Why do I need to confirm for main branch?
**A:**
- Main branch deployments affect production
- Warning ensures you're ready
- Safety checklist confirms prerequisites
- Prevents accidental deployments

### Q: Can I skip the warning?
**A:**
- No, warning is mandatory for main branch
- Click "Cancel" to select different branch
- Click "Yes, Deploy to Main" to proceed
- This ensures deliberate decisions

---

## Safety Checklist Explained

Before clicking "Yes, Deploy to Main" make sure:

### ✓ All tests are passing
- Unit tests pass
- Integration tests pass
- E2E tests pass
- No failing CI/CD checks

### ✓ Code has been reviewed
- Pull request reviewed
- At least one approval
- All comments addressed
- No unresolved discussions

### ✓ Changes are production-ready
- No debug code
- No TODO comments for blockers
- Performance acceptable
- Backwards compatible (if needed)

---

## Feature Comparison

| Feature | Before | After |
|---------|--------|-------|
| Input Type | Text field | Dropdown |
| Valid Branches | User-typed | GitHub-sourced |
| Typo Protection | None | Full |
| Optional? | Yes | No |
| Main Warning | None | Always |
| Confirmation | No | Required |
| Safety Checklist | No | Yes |
| Production Safe | Low | High |

---

## Best Practices

✅ **DO:**
- Always test on develop first
- Review safety checklist before confirming
- Ensure all tests pass before main deployment
- Use feature branches for development
- Merge to develop for testing
- Deploy to main only when ready

❌ **DON'T:**
- Rush through the warning modal
- Skip the safety checklist
- Deploy directly to main from features
- Deploy with failing tests
- Deploy without code review
- Bypass the confirmation (you can't)

---

## Example Workflows

### Standard Development
```
1. Create feature branch
2. Make changes
3. Push to feature branch
4. Create Pull Request
5. Get code review
6. Merge to develop
7. Test on develop branch
   ├─ Select "develop" in dropdown
   ├─ Launch pipeline
   └─ Verify results ✅
8. Merge to main
9. Deploy to main branch
   ├─ Select "main" in dropdown
   ├─ Click "Launch Pipeline"
   ├─ Review warning modal ⚠️
   ├─ Check safety checklist
   └─ Click "Yes, Deploy to Main" ✅
```

### Emergency Hotfix
```
1. Create hotfix branch
2. Make critical fix
3. Push to hotfix branch
4. Quick code review
5. Deploy to main
   ├─ Select "main" in dropdown
   ├─ Click "Launch Pipeline"
   ├─ Review warning ⚠️
   ├─ Confirm critical fix is tested
   └─ Click "Yes, Deploy to Main" ✅
```

---

## Getting Help

If you have questions:
1. Check this guide
2. Ask your team lead
3. Review GitHub issues
4. Check server logs: `npm start`
5. Browser console for errors: F12

---

**Remember**: The main branch warning isn't a bug—it's a feature! ✅  
It's there to keep production safe. Use it wisely! 🚀
