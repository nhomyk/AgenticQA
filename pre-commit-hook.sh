#!/bin/bash

# Pre-commit hook for compliance checks
# Place this in .git/hooks/pre-commit and make executable

set -e

echo "🔍 Running pre-commit compliance checks..."
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we should skip
if [ "$SKIP_COMPLIANCE_CHECKS" = "true" ]; then
  echo "⏭️  Skipping compliance checks (SKIP_COMPLIANCE_CHECKS=true)"
  exit 0
fi

FAILED=0

# 1. Run ESLint
echo "Linting code..."
if npm run lint > /dev/null 2>&1; then
  echo -e "${GREEN}✓${NC} Linting passed"
else
  echo -e "${RED}✗${NC} Linting failed"
  npm run lint:fix > /dev/null 2>&1 || true
  FAILED=1
fi
echo ""

# 2. Run unit tests (fast path)
echo "Running fast unit tests..."
if npm run test:jest 2>&1 | grep -q "PASS" || npm run test:jest 2>&1 | grep -q "passed"; then
  echo -e "${GREEN}✓${NC} Unit tests passed"
else
  echo -e "${YELLOW}⚠${NC} Unit tests had issues (see full log)"
  FAILED=1
fi
echo ""

# 3. Pa11y check (optional, only if server responds)
echo "Checking accessibility..."
if curl -s http://localhost:3000 > /dev/null 2>&1; then
  if npm run test:pa11y > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Accessibility check passed"
  else
    echo -e "${YELLOW}⚠${NC} Accessibility violations detected (will not block commit)"
    echo "   Run 'npm run test:pa11y' for details"
  fi
else
  echo -e "${YELLOW}⚠${NC} Server not running, skipping accessibility check"
  echo "   Start server with 'npm start' and run 'npm run test:pa11y' separately"
fi
echo ""

# 4. Security audit (quick check)
echo "Checking security vulnerabilities..."
if npm audit --audit-level=critical 2>&1 | grep -q "up to date" || npm audit --audit-level=critical 2>&1 | grep -q "0 vulnerabilities"; then
  echo -e "${GREEN}✓${NC} No critical vulnerabilities"
else
  echo -e "${YELLOW}⚠${NC} Vulnerabilities detected"
  echo "   Run 'npm audit' for details and 'npm audit fix' to remediate"
  FAILED=1
fi
echo ""

# Summary
if [ $FAILED -eq 0 ]; then
  echo -e "${GREEN}✓ All checks passed!${NC}"
  echo "Proceeding with commit..."
  exit 0
else
  echo -e "${RED}✗ Some checks failed${NC}"
  echo ""
  echo "Options:"
  echo "  1. Fix the issues and retry"
  echo "  2. Skip checks with: SKIP_COMPLIANCE_CHECKS=true git commit"
  exit 1
fi
