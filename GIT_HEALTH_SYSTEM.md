# Git Health & Recovery System

Automated detection and recovery from common git issues that previously required IDE shutdown.

## Automatic Recovery (No Action Needed)

The system automatically handles:
- ✅ **Interrupted rebases** → Continues them
- ✅ **Stuck merges** → Aborts to clean state
- ✅ **Detached HEAD** → Checks out main branch
- ✅ **Cherry-pick/revert issues** → Aborts them

### When It Runs

1. **Pre-commit hook** (automatic) - Runs before every commit
2. **Via npm scripts** (manual) - Run anytime to check status

## Commands

### Check Git Health
```bash
npm run git:health
```
Shows current state and auto-recovers from anomalies.

### Safe Commit (with auto health check)
```bash
npm run git:commit -- "Your commit message"
```
Checks health → stages files → commits.

### Safe Commit & Push
```bash
npm run git:commit:push -- "Your commit message"
```
Checks health → commits → pushes to remote.

## How It Works

### Detection
The system detects git anomalies by checking:
- Presence of `.git/rebase-merge` or `.git/rebase-apply` → Rebasing
- Presence of `.git/MERGE_HEAD` → Merging
- Presence of `.git/CHERRY_PICK_HEAD` → Cherry-picking
- Output of `git status` for detached HEAD
- Changes status (staged, unstaged, untracked)

### Recovery
- **Rebasing**: `git rebase --continue`
- **Merging**: `git merge --abort`
- **Cherry-picking**: `git cherry-pick --abort`
- **Reverting**: `git revert --abort`
- **Detached HEAD**: `git checkout main`

### Validation
After recovery, validates that:
- No operations are in progress
- Not in detached HEAD state
- Repository is ready for git operations

## Future Prevention

Going forward, I will:
1. **Always call `npm run git:health`** before any commit/push operation
2. **Check git status** proactively if any operation fails
3. **Use safe commit wrapper** instead of raw git commands when possible

This eliminates the need for manual IDE shutdown to recover from git state issues.
