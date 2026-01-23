#!/bin/bash
# Create daily backup branches

BACKUP_BRANCH="backup/main-$(date +%Y-%m-%d)"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo "📦 Creating backup: $BACKUP_BRANCH"
git branch "$BACKUP_BRANCH" || echo "Backup branch already exists for today"
git push origin "$BACKUP_BRANCH" -f --quiet

echo "✅ Backup created successfully"
