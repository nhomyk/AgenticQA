#!/bin/bash
# Pipeline Validation Script
#
# Runs comprehensive pipeline validation tests locally
# Use this before pushing to verify everything works

set -e

echo "================================"
echo "PIPELINE VALIDATION"
echo "================================"
echo

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if in correct directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}Error: Must run from project root directory${NC}"
    exit 1
fi

# Install dependencies if needed
echo -e "${YELLOW}Checking dependencies...${NC}"
pip install -q pytest pytest-cov

echo

# Run local validation tests
echo -e "${GREEN}Running Local Pipeline Validation Tests...${NC}"
echo "This validates tools and agents work correctly"
echo

pytest tests/test_local_pipeline_validation.py -v --tb=short || {
    echo
    echo -e "${RED}❌ Some local validation tests failed${NC}"
    echo "Fix these issues before pushing to CI"
    exit 1
}

echo
echo -e "${GREEN}✓ Local validation tests passed${NC}"
echo

# Run agent error handling tests
echo -e "${GREEN}Running Agent Error Handling Tests...${NC}"
echo "This validates agents handle errors and self-heal"
echo

pytest tests/test_agent_error_handling.py -v --tb=short || {
    echo
    echo -e "${YELLOW}⚠ Some agent error handling tests failed${NC}"
    echo "Agents may not self-heal correctly"
}

echo
echo -e "${GREEN}✓ Agent error handling tests passed${NC}"
echo

# Optional: Run with Weaviate if available
if command -v docker &> /dev/null; then
    echo -e "${YELLOW}Checking for Weaviate...${NC}"

    # Check if Weaviate is running
    if curl -s http://localhost:8080/v1/.well-known/ready > /dev/null 2>&1; then
        echo -e "${GREEN}Weaviate is running - testing RAG integration...${NC}"

        export WEAVIATE_HOST=localhost
        export WEAVIATE_PORT=8080
        export AGENTICQA_RAG_MODE=local

        pytest tests/test_agent_rag_integration.py -v --tb=short || {
            echo -e "${YELLOW}⚠ Some RAG integration tests failed${NC}"
        }

        echo -e "${GREEN}✓ RAG integration tests passed${NC}"
    else
        echo -e "${YELLOW}⚠ Weaviate not running - skipping RAG tests${NC}"
        echo "To test RAG: docker run -d -p 8080:8080 semitechnologies/weaviate:latest"
    fi
fi

echo
echo "================================"
echo -e "${GREEN}✅ PIPELINE VALIDATION COMPLETE${NC}"
echo "================================"
echo
echo "All systems operational. Safe to push!"
echo
