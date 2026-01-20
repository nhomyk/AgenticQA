#!/usr/bin/env node

/**
 * AgenticQA Client Integration Test
 * Validates the client provisioning and pipeline execution flow
 */

const http = require('http');
const path = require('path');

const API_BASE = 'http://localhost:3001';

const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m'
};

let testResults = {
  passed: 0,
  failed: 0,
  tests: []
};

function log(level, message, data = null) {
  const prefix = {
    'INFO': `${colors.blue}ℹ${colors.reset}`,
    'SUCCESS': `${colors.green}✓${colors.reset}`,
    'WARN': `${colors.yellow}⚠${colors.reset}`,
    'ERROR': `${colors.red}✗${colors.reset}`,
    'TEST': `${colors.cyan}→${colors.reset}`
  }[level] || 'INFO';

  console.log(`${prefix} ${message}`);
  if (data) console.log('   ', JSON.stringify(data, null, 2));
}

async function makeRequest(method, endpoint, body = null) {
  return new Promise((resolve, reject) => {
    const url = new URL(endpoint, API_BASE);
    const options = {
      hostname: url.hostname,
      port: url.port || 3001,
      path: url.pathname + url.search,
      method,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer test-token'
      }
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve({
            status: res.statusCode,
            headers: res.headers,
            body: JSON.parse(data)
          });
        } catch {
          resolve({
            status: res.statusCode,
            headers: res.headers,
            body: data
          });
        }
      });
    });

    req.on('error', reject);
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

async function test(name, fn) {
  log('TEST', name);
  try {
    await fn();
    testResults.passed++;
    testResults.tests.push({ name, status: 'PASSED' });
    log('SUCCESS', `${name} passed`);
  } catch (error) {
    testResults.failed++;
    testResults.tests.push({ name, status: 'FAILED', error: error.message });
    log('ERROR', `${name} failed: ${error.message}`);
  }
  console.log();
}

async function main() {
  console.log(`\n${colors.bright}🧪 AgenticQA Client Integration Tests${colors.reset}\n`);
  console.log(`API Base: ${colors.cyan}${API_BASE}${colors.reset}\n`);

  // Test 1: Check if API is running
  await test('API Health Check', async () => {
    try {
      const response = await makeRequest('GET', '/health');
      if (response.status !== 200) throw new Error(`Health check failed: ${response.status}`);
    } catch {
      throw new Error('API is not running. Start the server with: npm run server:saas');
    }
  });

  let clientId = null;
  const testRepo = 'https://github.com/test-org/test-repo';
  const testToken = 'ghp_test_token_12345';

  // Test 2: Register client repository
  await test('Register Client Repository', async () => {
    const response = await makeRequest('POST', '/api/clients/register', {
      repoUrl: testRepo,
      clientToken: testToken
    });

    if (response.status !== 200) throw new Error(`Expected 200, got ${response.status}`);
    if (!response.body.clientId) throw new Error('No clientId in response');
    if (!response.body.setupUrl) throw new Error('No setupUrl in response');

    clientId = response.body.clientId;
    log('INFO', `Registered client: ${colors.cyan}${clientId}${colors.reset}`);
  });

  // Test 3: Fetch client details
  await test('Fetch Client Details', async () => {
    const response = await makeRequest('GET', `/api/clients/${clientId}`);

    if (response.status !== 200) throw new Error(`Expected 200, got ${response.status}`);
    if (response.body.client.repoUrl !== testRepo) throw new Error('Repository URL mismatch');
    if (response.body.client.status !== 'active') throw new Error('Client not active');
  });

  // Test 4: Fetch pipeline definition
  await test('Fetch Pipeline Definition', async () => {
    const response = await makeRequest('GET', `/api/clients/${clientId}/pipeline-definition`);

    if (response.status !== 200) throw new Error(`Expected 200, got ${response.status}`);
    if (!response.body.definition.phases || response.body.definition.phases.length === 0) {
      throw new Error('No phases in pipeline definition');
    }

    log('INFO', `Pipeline has ${colors.cyan}${response.body.definition.phases.length}${colors.reset} phases`);
  });

  // Test 5: Submit results
  await test('Submit Pipeline Results', async () => {
    const results = {
      status: 'completed',
      totalIssues: 5,
      phases: {
        'scan': { status: 'completed' },
        'detect': { status: 'completed' },
        'generate': { status: 'completed' }
      }
    };

    const response = await makeRequest('POST', `/api/clients/${clientId}/results`, results);

    if (response.status !== 200) throw new Error(`Expected 200, got ${response.status}`);
  });

  // Test 6: Invalid client
  await test('Invalid Client Handling', async () => {
    const response = await makeRequest('GET', '/api/clients/invalid_client_id');

    if (response.status !== 404) throw new Error(`Expected 404, got ${response.status}`);
  });

  // Test 7: Missing repo URL
  await test('Validation: Missing Repo URL', async () => {
    const response = await makeRequest('POST', '/api/clients/register', {
      clientToken: testToken
      // repoUrl is missing
    });

    if (response.status !== 400) throw new Error(`Expected 400, got ${response.status}`);
  });

  // Print summary
  console.log(`\n${colors.bright}📊 Test Summary${colors.reset}\n`);
  console.log(`${colors.green}Passed: ${testResults.passed}${colors.reset}`);
  console.log(`${colors.red}Failed: ${testResults.failed}${colors.reset}`);
  console.log(`Total: ${testResults.passed + testResults.failed}\n`);

  // Print test details
  if (testResults.tests.length > 0) {
    console.log(`${colors.bright}Test Details:${colors.reset}`);
    testResults.tests.forEach(test => {
      const status = test.status === 'PASSED' ? `${colors.green}✓${colors.reset}` : `${colors.red}✗${colors.reset}`;
      console.log(`${status} ${test.name}`);
      if (test.error) console.log(`  ${colors.red}Error: ${test.error}${colors.reset}`);
    });
  }

  process.exit(testResults.failed > 0 ? 1 : 0);
}

main().catch(err => {
  log('ERROR', `Test suite error: ${err.message}`);
  process.exit(1);
});
