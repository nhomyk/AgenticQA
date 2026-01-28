#!/bin/bash
# Trigger Pipeline Validation Workflow
#
# Manually triggers the pipeline-validation.yml workflow
# to test the CI/CD pipeline health on-demand

set -e

echo "================================"
echo "TRIGGER PIPELINE VALIDATION"
echo "================================"
echo

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if gh CLI is available
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: gh CLI not found${NC}"
    echo "Install with: brew install gh"
    echo "Then authenticate: gh auth login"
    exit 1
fi

# Check authentication
if ! gh auth status &> /dev/null; then
    echo -e "${RED}Error: Not authenticated with GitHub${NC}"
    echo "Run: gh auth login"
    exit 1
fi

echo -e "${GREEN}Triggering Pipeline Validation Workflow...${NC}"
echo

# Ask for test level
echo "Select test level:"
echo "  1) quick      - Fast validation (5-10 min)"
echo "  2) full       - Complete validation (15-20 min) [default]"
echo "  3) comprehensive - Extended validation (30+ min)"
echo
read -p "Enter choice (1-3) [2]: " choice

case $choice in
    1)
        TEST_LEVEL="quick"
        ;;
    3)
        TEST_LEVEL="comprehensive"
        ;;
    *)
        TEST_LEVEL="full"
        ;;
esac

echo
echo -e "${YELLOW}Test Level: $TEST_LEVEL${NC}"
echo

# Trigger workflow
echo "Triggering workflow..."
gh workflow run pipeline-validation.yml \
    -f test_level="$TEST_LEVEL" \
    -f notify_on_failure=true

if [ $? -eq 0 ]; then
    echo
    echo -e "${GREEN}✓ Workflow triggered successfully!${NC}"
    echo
    echo "View progress:"
    echo "  gh run list --workflow=pipeline-validation.yml"
    echo
    echo "Watch in real-time:"
    echo "  gh run watch"
    echo
    echo "Or visit:"
    echo "  https://github.com/nhomyk/AgenticQA/actions/workflows/pipeline-validation.yml"
else
    echo
    echo -e "${RED}✗ Failed to trigger workflow${NC}"
    exit 1
fi

echo
echo "================================"
echo -e "${GREEN}Validation workflow started!${NC}"
echo "================================"
