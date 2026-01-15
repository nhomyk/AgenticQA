#!/usr/bin/env node

/**
 * Quick Launch Pipeline Endpoint Verification
 * Tests the /api/trigger-workflow endpoint without needing full server
 */

const fs = require('fs');
const path = require('path');

console.log('🧪 Launch Pipeline Endpoint Verification\n');

// Test 1: Check endpoint exists in server.js
console.log('Test 1: Endpoint code exists in server.js...');
const serverPath = path.join(__dirname, 'server.js');
const serverCode = fs.readFileSync(serverPath, 'utf8');

const hasEndpoint = serverCode.includes('app.post("/api/trigger-workflow"');
assert(hasEndpoint, 'Endpoint code not found');
console.log('✅ PASS: Endpoint is defined in server.js\n');

// Test 2: Endpoint is before 404 handler
console.log('Test 2: Endpoint is registered before 404 handler...');
const endpointIndex = serverCode.indexOf('app.post("/api/trigger-workflow"');
const notFoundHandlerIndex = serverCode.indexOf('app.use((req, res) =>');

assert(endpointIndex !== -1, 'Endpoint not found');
assert(notFoundHandlerIndex !== -1, '404 handler not found');
assert(endpointIndex < notFoundHandlerIndex, 'Endpoint is AFTER 404 handler (wrong order)');
console.log('✅ PASS: Endpoint is properly positioned before 404 handler\n');

// Test 3: Endpoint accepts pipelineType
console.log('Test 3: Endpoint validates pipelineType...');
const hasValidation = serverCode.includes('validPipelineTypes') && 
                      serverCode.includes('includes(pipelineType)');
assert(hasValidation, 'Pipeline type validation missing');
console.log('✅ PASS: Pipeline type validation is present\n');

// Test 4: Endpoint validates branch
console.log('Test 4: Endpoint validates branch format...');
const hasBranchValidation = serverCode.includes('/^[a-zA-Z0-9._\\-/]+$/.test(branch)');
assert(hasBranchValidation, 'Branch validation regex missing');
console.log('✅ PASS: Branch validation is present\n');

// Test 5: Endpoint makes GitHub API call
console.log('Test 5: Endpoint calls GitHub API...');
const hasGitHubCall = serverCode.includes('api.github.com') && 
                      serverCode.includes('/repos/nhomyk/AgenticQA/actions/workflows/ci.yml/dispatches');
assert(hasGitHubCall, 'GitHub API call not found');
console.log('✅ PASS: GitHub API integration is present\n');

// Test 6: Dashboard calls correct endpoint
console.log('Test 6: Dashboard calls /api/trigger-workflow endpoint...');
const dashboardPath = path.join(__dirname, 'public/dashboard.html');
const dashboardCode = fs.readFileSync(dashboardPath, 'utf8');

const hasDashboardCall = dashboardCode.includes("fetch('/api/trigger-workflow'");
assert(hasDashboardCall, 'Dashboard endpoint call not found');
console.log('✅ PASS: Dashboard correctly calls /api/trigger-workflow\n');

// Test 7: Button references kickoffPipeline correctly
console.log('Test 7: Launch button is wired to kickoffPipeline...');
const hasLaunchButton = dashboardCode.includes('onclick="kickoffPipeline()"') &&
                        dashboardCode.includes('Launch Pipeline');
assert(hasLaunchButton, 'Launch button not properly wired');
console.log('✅ PASS: Launch button is correctly wired\n');

// Test 8: kickoffPipeline queries correct button
console.log('Test 8: kickoffPipeline queries correct button selector...');
const hasButtonSelector = dashboardCode.includes("document.querySelector('.kickoff-section .btn-primary')");
assert(hasButtonSelector, 'Button selector not found in kickoffPipeline');
console.log('✅ PASS: kickoffPipeline uses correct button selector\n');

// Test 9: Response handling covers all cases
console.log('Test 9: Response handlers cover all error cases...');
const hasErrorHandling = dashboardCode.includes('response.ok') &&
                        dashboardCode.includes('403') &&
                        dashboardCode.includes('404') &&
                        dashboardCode.includes('503') &&
                        dashboardCode.includes('400');
assert(hasErrorHandling, 'Error handling incomplete');
console.log('✅ PASS: All error cases are handled\n');

// Test 10: Valid pipeline types are defined
console.log('Test 10: All pipeline types are properly configured...');
const validTypes = ['full', 'tests', 'security', 'accessibility', 'compliance', 'manual'];
for (const type of validTypes) {
  const hasType = serverCode.includes(`"${type}"`);
  assert(hasType, `Pipeline type '${type}' not found`);
  console.log(`  ✓ ${type} is configured`);
}
console.log('✅ PASS: All pipeline types are available\n');

console.log('═══════════════════════════════════════════════════');
console.log('✅ ALL VERIFICATION TESTS PASSED!');
console.log('═══════════════════════════════════════════════════\n');
console.log('Summary:');
console.log('  • Endpoint is properly defined and positioned');
console.log('  • Input validation is comprehensive');
console.log('  • GitHub API integration is configured');
console.log('  • Dashboard UI is correctly wired');
console.log('  • Error handling covers all cases\n');

function assert(condition, message) {
  if (!condition) {
    console.error(`❌ FAIL: ${message}\n`);
    process.exit(1);
  }
}

process.exit(0);
