/**
 * Dashboard API Tests
 * Tests for GitHub Actions and agent API integration
 */

const http = require('http');
const https = require('https');

// Test Results
const results = {
  passed: 0,
  failed: 0,
  tests: [],
  details: []
};

// Helper: HTTP request wrapper
function makeRequest(options) {
  return new Promise((resolve, reject) => {
    const client = options.protocol === 'https:' ? https : http;
    const req = client.request(options, (res) => {
      let data = '';
      res.on('data', chunk => (data += chunk));
      res.on('end', () => {
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          body: data,
          success: res.statusCode >= 200 && res.statusCode < 300
        });
      });
    });
    req.on('error', reject);
    if (options.body) req.write(options.body);
    req.end();
  });
}

// Helper: Assert function
function assert(condition, message) {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
}

// Helper: Test wrapper
async function test(name, fn) {
  try {
    await fn();
    results.passed++;
    results.tests.push({ name, status: 'PASS', error: null });
    console.log(`✅ ${name}`);
  } catch (error) {
    results.failed++;
    results.tests.push({ name, status: 'FAIL', error: error.message });
    results.details.push({ name, error: error.message });
    console.error(`❌ ${name}: ${error.message}`);
  }
}

// ======================
// GITHUB API TESTS
// ======================

async function testGitHubAPI() {
  console.log('\n🔗 GITHUB ACTIONS API TESTS');
  console.log('═'.repeat(50));

  await test('GitHub API is reachable', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    assert(response.success, `GitHub API returned ${response.statusCode}`);
  });

  await test('Can fetch workflow runs', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/actions/runs?per_page=20',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    assert(response.success, `Workflow API returned ${response.statusCode}`);
    
    const data = JSON.parse(response.body);
    assert(data.workflow_runs, 'Missing workflow_runs in response');
    assert(Array.isArray(data.workflow_runs), 'workflow_runs is not an array');
  });

  await test('Workflow run data structure', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/actions/runs?per_page=1',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    
    const data = JSON.parse(response.body);
    const run = data.workflow_runs[0];
    
    assert(run.run_number, 'Missing run_number');
    assert(run.status, 'Missing status');
    assert(run.conclusion !== undefined, 'Missing conclusion');
    assert(run.name, 'Missing workflow name');
    assert(run.head_branch, 'Missing branch');
    assert(run.head_commit, 'Missing commit info');
    assert(run.updated_at, 'Missing timestamp');
  });

  await test('Pagination parameter works', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/actions/runs?per_page=5',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    
    const data = JSON.parse(response.body);
    assert(data.workflow_runs.length <= 5, 'Pagination not working');
  });

  await test('Workflow status values are valid', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/actions/runs?per_page=20',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    
    const data = JSON.parse(response.body);
    const validStatuses = ['queued', 'in_progress', 'completed', 'requested', 'waiting'];
    
    data.workflow_runs.forEach(run => {
      assert(
        validStatuses.includes(run.status),
        `Invalid status: ${run.status}`
      );
    });
  });

  await test('Workflow conclusion values are valid', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/actions/runs?per_page=20',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    
    const data = JSON.parse(response.body);
    const validConclusions = ['success', 'failure', 'neutral', 'cancelled', 'timed_out', 'action_required', null];
    
    data.workflow_runs.forEach(run => {
      assert(
        validConclusions.includes(run.conclusion),
        `Invalid conclusion: ${run.conclusion}`
      );
    });
  });

  await test('Repository exists and is accessible', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    
    assert(response.success, `Repository API returned ${response.statusCode}`);
    const data = JSON.parse(response.body);
    assert(data.name === 'AgenticQA', 'Repository name mismatch');
  });

  await test('CI workflow file exists', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/contents/.github/workflows/ci.yml',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    
    assert(response.statusCode === 200, `CI workflow not found (${response.statusCode})`);
  });

  await test('Validate workflow response content type', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/actions/runs?per_page=1',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    
    assert(
      response.headers['content-type'].includes('application/json'),
      'Response is not JSON'
    );
  });
}

// ======================
// WORKFLOW DISPATCH TESTS
// ======================

async function testWorkflowDispatch() {
  console.log('\n🚀 WORKFLOW DISPATCH API TESTS');
  console.log('═'.repeat(50));

  await test('Workflow dispatch endpoint exists', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/actions/workflows/ci.yml/dispatches',
      method: 'POST',
      headers: {
        'User-Agent': 'Dashboard-Test',
        'Accept': 'application/vnd.github.v3+json'
      },
      protocol: 'https:',
      body: JSON.stringify({
        ref: 'main',
        inputs: {}
      })
    });
    
    // Endpoint should exist (may return 401 without auth, 204 with auth)
    assert([204, 401, 403].includes(response.statusCode),
      `Unexpected status: ${response.statusCode}`
    );
  });

  await test('Can list all workflows', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/actions/workflows',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    
    assert(response.success, `Workflows API returned ${response.statusCode}`);
    const data = JSON.parse(response.body);
    assert(data.workflows, 'Missing workflows array');
    assert(data.workflows.length > 0, 'No workflows found');
  });

  await test('CI workflow is in workflows list', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/actions/workflows',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    
    const data = JSON.parse(response.body);
    const ciWorkflow = data.workflows.find(w => 
      w.name.includes('CI') || w.path.includes('ci.yml')
    );
    assert(ciWorkflow, 'CI workflow not found in workflows list');
  });
}

// ======================
// LOCAL SERVER TESTS
// ======================

async function testLocalServer() {
  console.log('\n🌐 LOCAL SERVER TESTS');
  console.log('═'.repeat(50));

  await test('Dashboard page is served', async () => {
    try {
      const response = await makeRequest({
        hostname: 'localhost',
        port: 3000,
        path: '/dashboard.html',
        method: 'GET',
        protocol: 'http:'
      });
      
      assert(response.statusCode === 200, `Dashboard returned ${response.statusCode}`);
      assert(response.body.includes('spiralQA.ai Dashboard'), 'Dashboard page not found');
    } catch (error) {
      // Server might not be running, skip this test
      throw new Error('Local server not running on localhost:3000 - skipping');
    }
  });

  await test('Dashboard has correct content type', async () => {
    try {
      const response = await makeRequest({
        hostname: 'localhost',
        port: 3000,
        path: '/dashboard.html',
        method: 'GET',
        protocol: 'http:'
      });
      
      assert(response.headers['content-type'].includes('text/html'),
        'Content-Type is not HTML'
      );
    } catch (error) {
      throw new Error('Local server not running - skipping');
    }
  });

  await test('Index page links to dashboard', async () => {
    try {
      const response = await makeRequest({
        hostname: 'localhost',
        port: 3000,
        path: '/index.html',
        method: 'GET',
        protocol: 'http:'
      });
      
      assert(response.body.includes('/dashboard.html'), 'Dashboard link not found in index');
    } catch (error) {
      throw new Error('Local server not running - skipping');
    }
  });
}

// ======================
// DATA VALIDATION TESTS
// ======================

async function testDataValidation() {
  console.log('\n✅ DATA VALIDATION TESTS');
  console.log('═'.repeat(50));

  await test('Timestamp format is valid ISO 8601', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/actions/runs?per_page=1',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    
    const data = JSON.parse(response.body);
    const run = data.workflow_runs[0];
    const timestamp = new Date(run.updated_at);
    
    assert(!isNaN(timestamp.getTime()), 'Invalid timestamp format');
  });

  await test('Run numbers are positive integers', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/actions/runs?per_page=20',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    
    const data = JSON.parse(response.body);
    data.workflow_runs.forEach(run => {
      assert(Number.isInteger(run.run_number) && run.run_number > 0,
        `Invalid run number: ${run.run_number}`
      );
    });
  });

  await test('Commit messages are not empty', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/actions/runs?per_page=20',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    
    const data = JSON.parse(response.body);
    data.workflow_runs.forEach(run => {
      assert(
        run.head_commit && run.head_commit.message,
        'Empty commit message'
      );
    });
  });

  await test('Branch names follow git naming conventions', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/actions/runs?per_page=20',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    
    const data = JSON.parse(response.body);
    const branchRegex = /^[a-zA-Z0-9._\-/]+$/;
    
    data.workflow_runs.forEach(run => {
      assert(branchRegex.test(run.head_branch),
        `Invalid branch name: ${run.head_branch}`
      );
    });
  });
}

// ======================
// RATE LIMITING TESTS
// ======================

async function testRateLimiting() {
  console.log('\n⚙️ API RATE LIMITING TESTS');
  console.log('═'.repeat(50));

  await test('API returns rate limit headers', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/actions/runs?per_page=1',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    
    assert(response.headers['x-ratelimit-limit'],
      'Missing X-RateLimit-Limit header'
    );
    assert(response.headers['x-ratelimit-remaining'],
      'Missing X-RateLimit-Remaining header'
    );
  });

  await test('Rate limit is reasonable', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/actions/runs?per_page=1',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    
    const limit = parseInt(response.headers['x-ratelimit-limit']);
    assert(limit >= 60, `Rate limit too low: ${limit}`);
  });

  await test('Remaining requests are tracked', async () => {
    const response = await makeRequest({
      hostname: 'api.github.com',
      port: 443,
      path: '/repos/nhomyk/AgenticQA/actions/runs?per_page=1',
      method: 'GET',
      headers: { 'User-Agent': 'Dashboard-Test' },
      protocol: 'https:'
    });
    
    const remaining = parseInt(response.headers['x-ratelimit-remaining']);
    assert(remaining >= 0, `Invalid remaining count: ${remaining}`);
  });
}

// ======================
// RUN ALL TESTS
// ======================

async function runAllTests() {
  console.log('\n╔════════════════════════════════════════════╗');
  console.log('║   DASHBOARD API COMPREHENSIVE TEST SUITE   ║');
  console.log('╚════════════════════════════════════════════╝\n');

  await testGitHubAPI();
  await testWorkflowDispatch();
  await testLocalServer();
  await testDataValidation();
  await testRateLimiting();

  // Print summary
  console.log('\n╔════════════════════════════════════════════╗');
  console.log('║          TEST RESULTS SUMMARY              ║');
  console.log('╚════════════════════════════════════════════╝\n');

  console.log(`✅ PASSED: ${results.passed}`);
  console.log(`❌ FAILED: ${results.failed}`);
  console.log(`📊 TOTAL:  ${results.passed + results.failed}`);
  console.log(`📈 SUCCESS RATE: ${((results.passed / (results.passed + results.failed)) * 100).toFixed(2)}%\n`);

  if (results.failed > 0) {
    console.log('❌ FAILED TESTS:');
    results.details.forEach(detail => {
      console.log(`   • ${detail.name}: ${detail.error}`);
    });
  }

  process.exit(results.failed > 0 ? 1 : 0);
}

// Execute tests
runAllTests().catch(error => {
  console.error('Test suite error:', error);
  process.exit(1);
});
