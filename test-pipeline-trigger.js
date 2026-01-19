#!/usr/bin/env node

/**
 * Test script to verify pipeline triggering works end-to-end
 * Usage: node test-pipeline-trigger.js
 */

const https = require('https');

// Test configuration
const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
const TEST_BRANCH = 'develop';
const TEST_TYPE = 'tests';

console.log('\n🧪 Pipeline Trigger Test\n');
console.log('━'.repeat(60));

// Step 1: Verify GitHub token
console.log('\n1️⃣  GitHub Token Status:');
if (!GITHUB_TOKEN) {
  console.log('   ❌ GITHUB_TOKEN environment variable is NOT set');
  console.log('   ⚠️  Pipeline triggering will FAIL without a valid token');
  console.log('   📝 Set it with: export GITHUB_TOKEN="ghp_xxxxx"');
} else {
  console.log(`   ✅ GITHUB_TOKEN is set (${GITHUB_TOKEN.substring(0, 10)}...)`);
}

// Step 2: Test local server endpoint
console.log('\n2️⃣  Testing Local Server Endpoint:');

const payload = {
  ref: TEST_BRANCH,
  inputs: {
    reason: `🤖 AgenticQA - Test Suite`,
    run_type: "manual"
  }
};

// Simulate what the dashboard does
const testPayload = {
  pipelineType: TEST_TYPE,
  branch: TEST_BRANCH,
  pipelineName: '🤖 AgenticQA - Test Suite'
};

console.log('   Request payload:');
console.log(`   - pipelineType: ${testPayload.pipelineType}`);
console.log(`   - branch: ${testPayload.branch}`);
console.log(`   - pipelineName: ${testPayload.pipelineName}`);

// Step 3: Test GitHub API directly
console.log('\n3️⃣  Testing GitHub API Direct Call:');
console.log('   Attempting to dispatch workflow on GitHub...\n');

if (!GITHUB_TOKEN) {
  console.log('   ⚠️  Cannot test - GITHUB_TOKEN not set');
} else {
  const payloadString = JSON.stringify(payload);
  const options = {
    hostname: "api.github.com",
    port: 443,
    path: "/repos/nhomyk/AgenticQA/actions/workflows/ci.yml/dispatches",
    method: "POST",
    headers: {
      "Accept": "application/vnd.github.v3+json",
      "Authorization": `token ${GITHUB_TOKEN}`,
      "Content-Type": "application/json",
      "User-Agent": "AgenticQA-Test",
      "Content-Length": Buffer.byteLength(payloadString)
    }
  };

  const githubReq = https.request(options, (githubRes) => {
    let responseBody = "";
    
    githubRes.on("data", (chunk) => {
      responseBody += chunk;
    });
    
    githubRes.on("end", () => {
      console.log(`   📡 GitHub API Status: ${githubRes.statusCode}`);
      
      if (githubRes.statusCode === 204) {
        console.log('   ✅ Workflow dispatch SUCCESSFUL!');
        console.log('\n   🎉 Pipeline should now be running on GitHub Actions');
        console.log('   📊 Check: https://github.com/nhomyk/AgenticQA/actions');
      } else if (githubRes.statusCode === 401 || githubRes.statusCode === 403) {
        console.log('   ❌ Authentication FAILED');
        console.log('   📝 Issue: GitHub token authentication failed');
        console.log('   💡 Fix: Verify token has "actions" and "contents" scopes');
        if (responseBody) {
          console.log(`   📋 GitHub Response: ${responseBody.substring(0, 200)}`);
        }
      } else if (githubRes.statusCode === 404) {
        console.log('   ❌ Workflow NOT FOUND');
        console.log('   📝 Issue: ci.yml workflow not found in repository');
        console.log('   💡 Fix: Ensure .github/workflows/ci.yml exists');
      } else if (githubRes.statusCode === 422) {
        console.log('   ❌ Invalid request (422)');
        console.log('   📝 Issue: Unprocessable entity');
        if (responseBody) {
          try {
            const errorData = JSON.parse(responseBody);
            console.log('   📋 Details:', errorData.message);
          } catch (e) {
            console.log(`   📋 Response: ${responseBody}`);
          }
        }
      } else {
        console.log(`   ❌ Unexpected status: ${githubRes.statusCode}`);
        if (responseBody) {
          console.log(`   📋 Response: ${responseBody.substring(0, 200)}`);
        }
      }
      
      printSummary();
    });
  });

  githubReq.on("error", (error) => {
    console.log(`   ❌ Network error: ${error.message}`);
    printSummary();
  });

  githubReq.write(payloadString);
  githubReq.end();
}

function printSummary() {
  console.log('\n' + '━'.repeat(60));
  console.log('\n📋 Troubleshooting Guide:\n');
  console.log('If pipeline fails to trigger, check:\n');
  console.log('1. GitHub Token:');
  console.log('   - Set GITHUB_TOKEN environment variable');
  console.log('   - Token must have "actions" and "contents" scopes');
  console.log('   - Create at: https://github.com/settings/tokens\n');
  console.log('2. Workflow File:');
  console.log('   - Verify .github/workflows/ci.yml exists');
  console.log('   - Check file is properly formatted YAML\n');
  console.log('3. Branch:');
  console.log(`   - Branch "${TEST_BRANCH}" must exist in repository\n`);
  console.log('4. Repository:');
  console.log('   - Workflow dispatch must be enabled');
  console.log('   - Settings > Actions > Workflows > Allow manual trigger\n');
}
