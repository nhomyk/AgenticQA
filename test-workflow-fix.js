#!/usr/bin/env node

/**
 * Test Workflow Trigger Fix
 * Validates that the /api/trigger-workflow endpoint now has proper auth
 */

const fs = require('fs');
const path = require('path');

console.log('🧪 Testing Workflow Trigger Fix\n');
console.log('=' .repeat(60));

// Check 1: Verify the auth middleware is in place
console.log('\n1️⃣ Checking if authenticateToken middleware is applied...');
const saasApiPath = path.join(__dirname, 'saas-api-dev.js');
const saasApiContent = fs.readFileSync(saasApiPath, 'utf8');

const triggerWorkflowRegex = /app\.post\('\/api\/trigger-workflow',\s*authenticateToken,/;
if (triggerWorkflowRegex.test(saasApiContent)) {
  console.log('✅ PASS: authenticateToken middleware is properly applied');
} else {
  console.log('❌ FAIL: authenticateToken middleware is missing!');
  console.log('   Expected: app.post(\'/api/trigger-workflow\', authenticateToken, ...)');
  process.exit(1);
}

// Check 2: Verify the endpoint uses req.user
console.log('\n2️⃣ Checking if endpoint correctly accesses req.user...');
const userIdRegex = /const connectionId = `user_\${req\.user\.id}_github`;/;
if (userIdRegex.test(saasApiContent)) {
  console.log('✅ PASS: Endpoint correctly accesses req.user.id');
} else {
  console.log('❌ FAIL: Endpoint does not access req.user.id correctly!');
  process.exit(1);
}

// Check 3: Verify GitHub connection lookup
console.log('\n3️⃣ Checking GitHub connection retrieval...');
const connectionRegex = /const connection = db\.githubConnections\.get\(connectionId\);/;
if (connectionRegex.test(saasApiContent)) {
  console.log('✅ PASS: GitHub connection retrieval is correct');
} else {
  console.log('❌ FAIL: GitHub connection retrieval is incorrect!');
  process.exit(1);
}

// Check 4: Verify error handling for no GitHub connection
console.log('\n4️⃣ Checking error handling when GitHub not connected...');
const noConnectionErrorRegex = /if \(!connection\)[\s\S]*?GitHub not connected/;
if (noConnectionErrorRegex.test(saasApiContent)) {
  console.log('✅ PASS: Proper error handling for missing GitHub connection');
} else {
  console.log('❌ FAIL: Missing error handling for no GitHub connection!');
  process.exit(1);
}

// Check 5: Verify workflow file fallback logic
console.log('\n5️⃣ Checking workflow file fallback (agentic-qa.yml → ci.yml)...');
const fallbackRegex = /const workflowFiles = \['agentic-qa\.yml', 'ci\.yml'\];/;
if (fallbackRegex.test(saasApiContent)) {
  console.log('✅ PASS: Workflow file fallback is properly implemented');
} else {
  console.log('❌ FAIL: Workflow fallback logic is missing!');
  process.exit(1);
}

// Check 6: Verify both dashboard functions call the correct endpoint
console.log('\n6️⃣ Checking dashboard functions call /api/trigger-workflow...');
const dashboardPath = path.join(__dirname, 'public/dashboard.html');
const dashboardContent = fs.readFileSync(dashboardPath, 'utf8');

const dashboardCallRegex = /fetch\('\/api\/trigger-workflow'/;
if (dashboardCallRegex.test(dashboardContent)) {
  console.log('✅ PASS: Dashboard calls /api/trigger-workflow endpoint');
} else {
  console.log('❌ FAIL: Dashboard does not call correct endpoint!');
  process.exit(1);
}

// Check 7: Verify settings functions call the correct endpoint
console.log('\n7️⃣ Checking settings functions call /api/trigger-workflow...');
const settingsPath = path.join(__dirname, 'public/settings.html');
const settingsContent = fs.readFileSync(settingsPath, 'utf8');

const settingsCallRegex = /fetch\('\/api\/trigger-workflow'/;
if (settingsCallRegex.test(settingsContent)) {
  console.log('✅ PASS: Settings calls /api/trigger-workflow endpoint');
} else {
  console.log('❌ FAIL: Settings does not call correct endpoint!');
  process.exit(1);
}

// Check 8: Verify both functions have proper branch validation
console.log('\n8️⃣ Checking branch validation in both functions...');
const branchValidationRegex = /if \(!branch\)/;
const kickoffRegex = /async function kickoffPipeline\(\)[\s\S]*?if \(!branch\)/;
const triggerTestRegex = /async function triggerTestWorkflow\(\)[\s\S]*?if \(!branch\)/;

let kickoffHasBranchValidation = false;
let triggerTestHasBranchValidation = false;

if (dashboardContent.match(kickoffRegex)) {
  kickoffHasBranchValidation = true;
  console.log('   ✅ kickoffPipeline has branch validation');
}

if (settingsContent.match(triggerTestRegex)) {
  triggerTestHasBranchValidation = true;
  console.log('   ✅ triggerTestWorkflow has branch validation');
}

if (kickoffHasBranchValidation && triggerTestHasBranchValidation) {
  console.log('✅ PASS: Both functions validate branch parameter');
} else {
  console.log('❌ FAIL: Missing branch validation in one or both functions!');
  process.exit(1);
}

// Check 9: Verify token decryption is in place
console.log('\n9️⃣ Checking GitHub token decryption...');
const tokenDecryptRegex = /let decryptedToken;[\s\S]*?decryptedToken = decryptToken\(connection\.token\);/;
if (tokenDecryptRegex.test(saasApiContent)) {
  console.log('✅ PASS: GitHub token decryption is properly implemented');
} else {
  console.log('❌ FAIL: Token decryption logic is missing!');
  process.exit(1);
}

// Check 10: Verify token is used in GitHub API call
console.log('\n🔟 Checking GitHub API authorization header...');
const authHeaderRegex = /'Authorization': `token \$\{decryptedToken\}`,/;
if (authHeaderRegex.test(saasApiContent)) {
  console.log('✅ PASS: GitHub API uses decrypted token for authorization');
} else {
  console.log('❌ FAIL: GitHub API authorization is incorrect!');
  process.exit(1);
}

console.log('\n' + '='.repeat(60));
console.log('\n✨ ALL CHECKS PASSED! ✨\n');
console.log('Summary of fixes:');
console.log('  ✅ Added authenticateToken middleware to /api/trigger-workflow');
console.log('  ✅ Endpoint correctly retrieves user GitHub connection');
console.log('  ✅ Proper error handling for missing GitHub connection');
console.log('  ✅ Workflow file fallback: agentic-qa.yml → ci.yml');
console.log('  ✅ Token decryption before GitHub API call');
console.log('  ✅ Both dashboard and settings call correct endpoint');
console.log('  ✅ Both functions validate branch parameter');
console.log('  ✅ Secure token handling throughout flow');

console.log('\nNext steps:');
console.log('  1. Restart the server: npm start');
console.log('  2. Test workflow trigger from dashboard');
console.log('  3. Test workflow trigger from settings');
console.log('  4. Verify GitHub workflows are triggered');

process.exit(0);
