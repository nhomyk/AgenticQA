# Data Loss Prevention & Backup Strategy

## 🛡️ Protections Implemented

### 1. **Git Hooks** (Local Protection)
- **Pre-push hook**: Prevents direct pushes to `main` branch
  - Enforces pull request workflow
  - Must use `git push origin feature-branch` and create PR

### 2. **Automated Daily Backups**
Run the backup script daily:
```bash
./create-daily-backup.sh
```
This creates a `backup/main-YYYY-MM-DD` branch on GitHub with the current state.

### 3. **GitHub Branch Protection Rules** (Required)
Set these up on GitHub.com:

1. Go to: Settings → Branches → Add Rule
2. Apply to branch: `main`
3. Enable:
   - ✅ **Require a pull request before merging**
   - ✅ **Require status checks to pass before merging**
   - ✅ **Require code reviews before merging** (1 reviewer min)
   - ✅ **Restrict who can push to matching branches** (only yourself)
   - ✅ **Prevent force pushes**

## 🔄 Recommended Workflow

1. **Create feature branch**:
   ```bash
   git checkout -b feature/my-changes
   ```

2. **Make changes and commit**:
   ```bash
   git add .
   git commit -m "feat: description"
   ```

3. **Create PR on GitHub** (don't push directly to main)
   ```bash
   git push origin feature/my-changes
   ```

4. **Merge via GitHub UI** (with review)

## 📦 Emergency Recovery

If something goes wrong:

1. **View recent backups**:
   ```bash
   git branch -r | grep backup/
   ```

2. **Restore from backup**:
   ```bash
   git reset --hard origin/backup/main-YYYY-MM-DD
   git push origin main --force-with-lease
   ```

3. **View commit history**:
   ```bash
   git reflog
   git log --all --oneline
   ```

## 🚨 What's Protected Against

✅ Accidental force pushes to main  
✅ Direct commits to main (use feature branches)  
✅ Data loss (daily backups)  
✅ Unauthorized changes (branch protection)  
✅ Lost commits (git reflog + backup branches)  

## ⚡ Quick Automation

Add to crontab to run daily backup automatically:

```bash
crontab -e
# Add line:
0 9 * * * cd /Users/nicholashomyk/mono/AgenticQA && ./create-daily-backup.sh
```

This runs the backup at 9 AM daily.
