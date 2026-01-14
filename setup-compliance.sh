#!/bin/bash

# Setup script for compliance hooks and configuration

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

echo "🔧 Setting up compliance checks..."
echo ""

# Ensure hooks directory exists
mkdir -p "$HOOKS_DIR"

# Install pre-commit hook
if [ -f "$REPO_ROOT/pre-commit-hook.sh" ]; then
  cp "$REPO_ROOT/pre-commit-hook.sh" "$HOOKS_DIR/pre-commit"
  chmod +x "$HOOKS_DIR/pre-commit"
  echo "✓ Pre-commit hook installed"
else
  echo "⚠ pre-commit-hook.sh not found"
fi

# Create pre-push hook
cat > "$HOOKS_DIR/pre-push" << 'EOF'
#!/bin/bash
# Pre-push hook - runs compliance checks before pushing

set -e

echo "🔍 Running pre-push compliance checks..."
echo ""

if npm run test:compliance > /dev/null 2>&1; then
  echo "✓ Compliance checks passed"
  exit 0
else
  echo "✗ Compliance checks failed"
  echo "Fix issues and retry: npm run test:compliance"
  exit 1
fi
EOF

chmod +x "$HOOKS_DIR/pre-push"
echo "✓ Pre-push hook installed"
echo ""

# Verify configuration files
echo "📋 Verifying configuration files..."

files=(".pa11yci.json" ".auditrc.json")
for file in "${files[@]}"; do
  if [ -f "$REPO_ROOT/$file" ]; then
    echo "✓ $file found"
  else
    echo "⚠ $file not found"
  fi
done

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Review compliance guide: cat COMPLIANCE_SECURITY_GUIDE.md"
echo "2. Run initial compliance check: npm run test:compliance"
echo "3. Add to git: git add ."
echo "4. Commit: git commit -m 'Add compliance checks'"
echo ""
echo "To skip pre-commit hooks: SKIP_COMPLIANCE_CHECKS=true git commit"
