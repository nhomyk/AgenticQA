#!/bin/bash

# Test script for the new /api/trigger-workflow endpoint
# Usage: ./test-workflow-api.sh

set -e

echo "🧪 Testing Launch Pipeline API Endpoint"
echo "========================================"
echo ""

# Check if server is running
echo "1️⃣ Checking if server is running..."
if ! curl -s http://localhost:3000/health > /dev/null 2>&1; then
    echo "❌ Server is not running!"
    echo "   Start it with: npm start"
    exit 1
fi
echo "✅ Server is running"
echo ""

# Check if GITHUB_TOKEN is set
echo "2️⃣ Checking GITHUB_TOKEN environment variable..."
if [ -z "$GITHUB_TOKEN" ]; then
    echo "⚠️  GITHUB_TOKEN is not set!"
    echo "   Set it with: export GITHUB_TOKEN='your_token_here'"
    echo "   Creating GitHub token: https://github.com/settings/tokens"
    echo ""
    echo "Continuing with test (will likely fail)..."
else
    echo "✅ GITHUB_TOKEN is configured"
    # Don't show the actual token for security
    TOKEN_LENGTH=${#GITHUB_TOKEN}
    echo "   Token length: $TOKEN_LENGTH characters"
fi
echo ""

# Test the endpoint
echo "3️⃣ Testing POST /api/trigger-workflow endpoint..."
echo ""

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST http://localhost:3000/api/trigger-workflow \
    -H "Content-Type: application/json" \
    -d '{
        "pipelineType": "test",
        "branch": "main"
    }')

# Split response and status code
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

echo "HTTP Status: $HTTP_CODE"
echo "Response Body:"
echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
echo ""

# Analyze response
case $HTTP_CODE in
    200)
        echo "✅ SUCCESS: Workflow triggered!"
        echo "   The pipeline should be running now."
        echo "   Check GitHub Actions: https://github.com/nhomyk/AgenticQA/actions"
        ;;
    400)
        echo "❌ BAD REQUEST: Invalid input parameters"
        ;;
    403)
        echo "⚠️  FORBIDDEN: GitHub token authentication failed"
        echo "   Verify token has 'actions' and 'contents' scopes"
        echo "   Token scopes: https://github.com/settings/tokens"
        ;;
    404)
        echo "❌ NOT FOUND: Workflow 'ci.yml' not found"
        echo "   Verify: .github/workflows/ci.yml exists"
        ;;
    503)
        echo "⚠️  SERVICE UNAVAILABLE: GITHUB_TOKEN not configured on server"
        echo "   Set environment variable: export GITHUB_TOKEN='your_token'"
        ;;
    *)
        echo "❌ UNEXPECTED STATUS: $HTTP_CODE"
        ;;
esac

echo ""
echo "========================================"
echo "Test complete!"
