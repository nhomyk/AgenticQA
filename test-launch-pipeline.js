#!/usr/bin/env node

/**
 * Launch Pipeline Endpoint Tests
 * Tests the /api/trigger-workflow endpoint for correctness
 */

const https = require('https');
const http = require('http');
const assert = require('assert');

// Configuration
const HOST = 'localhost';
const PORT = process.env.PORT || 3000;
const PROTOCOL = process.env.PROTOCOL || 'http';

// Helper function to make HTTP requests
function makeRequest(method, path, body = null, headers = {}) {
  return new Promise((resolve, reject) => {
    const defaultHeaders = {
      'Content-Type': 'application/json',
      ...headers
    };

    let payload = null;
    if (body) {
      payload = JSON.stringify(body);
      defaultHeaders['Content-Length'] = Buffer.byteLength(payload);
    }

    const options = {
      hostname: HOST,
      port: PORT,
      path: path,
      method: method,
      headers: defaultHeaders
    };

    const client = PROTOCOL === 'https' ? https : http;
    const req = client.request(options, (res) => {
      let data = '';

      res.on('data', (chunk) => {
        data += chunk;
      });

      res.on('end', () => {
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          body: data ? JSON.parse(data) : null
        });
      });
    });

    req.on('error', reject);

    if (payload) {
      req.write(payload);
    }
    req.end();
  });
}

// Test suite
async function runTests() {
  console.log('🧪 Launch Pipeline Endpoint Tests\n');

  try {
    // Test 1: Endpoint exists and accepts POST
    console.log('Test 1: Endpoint exists and handles POST requests...');
    try {
      const res = await makeRequest('POST', '/api/trigger-workflow', {
        pipelineType: 'full',
        branch: 'main'
      });
      // Even if it fails due to missing token, endpoint should exist
      assert(res.statusCode !== 404, 'Endpoint not found (404)');
      console.log('✅ PASS: Endpoint is registered and responds to POST\n');
    } catch (err) {
      console.log(`❌ FAIL: ${err.message}\n`);
      throw err;
    }

    // Test 2: Invalid pipeline type validation
    console.log('Test 2: Rejects invalid pipeline type...');
    try {
      const res = await makeRequest('POST', '/api/trigger-workflow', {
        pipelineType: 'invalid-type',
        branch: 'main'
      });
      assert.strictEqual(res.statusCode, 400, `Expected 400, got ${res.statusCode}`);
      assert(res.body.error, 'Error message missing');
      assert(res.body.status === 'error', 'Status should be error');
      console.log('✅ PASS: Invalid pipeline type rejected\n');
    } catch (err) {
      console.log(`❌ FAIL: ${err.message}\n`);
      throw err;
    }

    // Test 3: Valid pipeline types accepted
    console.log('Test 3: Accepts valid pipeline types...');
    const validTypes = ['full', 'tests', 'security', 'accessibility', 'compliance', 'manual'];
    for (const type of validTypes) {
      try {
        const res = await makeRequest('POST', '/api/trigger-workflow', {
          pipelineType: type,
          branch: 'main'
        });
        // Should either succeed (200) or fail due to token, but not 400
        assert(res.statusCode !== 400, `Pipeline type '${type}' was rejected with 400`);
        console.log(`  ✓ ${type} accepted (status: ${res.statusCode})`);
      } catch (err) {
        console.log(`  ❌ ${type} test failed: ${err.message}`);
        throw err;
      }
    }
    console.log('✅ PASS: All valid pipeline types accepted\n');

    // Test 4: Invalid branch name rejected
    console.log('Test 4: Rejects invalid branch names...');
    const invalidBranches = [
      { name: 'feature@branch', reason: 'contains @' },
      { name: 'feature#123', reason: 'contains #' },
      { name: 'feature branch', reason: 'contains space' },
      { name: 'a'.repeat(256), reason: 'exceeds 255 chars' }
    ];

    for (const { name, reason } of invalidBranches) {
      try {
        const res = await makeRequest('POST', '/api/trigger-workflow', {
          pipelineType: 'full',
          branch: name
        });
        assert.strictEqual(res.statusCode, 400, `Expected 400 for ${reason}, got ${res.statusCode}`);
        assert(res.body.error, 'Error message missing');
        console.log(`  ✓ Rejected (${reason})`);
      } catch (err) {
        console.log(`  ❌ Failed: ${err.message}`);
        throw err;
      }
    }
    console.log('✅ PASS: Invalid branches rejected\n');

    // Test 5: Valid branch names accepted
    console.log('Test 5: Accepts valid branch names...');
    const validBranches = ['main', 'develop', 'feature/new-feature', 'bugfix/issue-123', 'release-1.0.0'];
    for (const branch of validBranches) {
      try {
        const res = await makeRequest('POST', '/api/trigger-workflow', {
          pipelineType: 'full',
          branch: branch
        });
        // Should not be 400 (validation error)
        assert(res.statusCode !== 400, `Valid branch '${branch}' rejected`);
        console.log(`  ✓ ${branch} accepted (status: ${res.statusCode})`);
      } catch (err) {
        console.log(`  ❌ ${branch} test failed: ${err.message}`);
        throw err;
      }
    }
    console.log('✅ PASS: Valid branch names accepted\n');

    // Test 6: Missing branch defaults to 'main'
    console.log('Test 6: Handles missing branch (should default to main)...');
    try {
      const res = await makeRequest('POST', '/api/trigger-workflow', {
        pipelineType: 'full'
      });
      // Should not fail validation (branch defaults to main)
      assert(res.statusCode !== 400, 'Missing branch should default to main');
      console.log('✅ PASS: Missing branch defaults to main\n');
    } catch (err) {
      console.log(`❌ FAIL: ${err.message}\n`);
      throw err;
    }

    // Test 7: Missing pipeline type defaults to 'manual'
    console.log('Test 7: Handles missing pipeline type (should default to manual)...');
    try {
      const res = await makeRequest('POST', '/api/trigger-workflow', {
        branch: 'main'
      });
      // Should not fail validation (type defaults to manual)
      assert(res.statusCode !== 400, 'Missing pipeline type should default to manual');
      console.log('✅ PASS: Missing pipeline type defaults to manual\n');
    } catch (err) {
      console.log(`❌ FAIL: ${err.message}\n`);
      throw err;
    }

    // Test 8: Response structure validation
    console.log('Test 8: Response has correct structure...');
    try {
      const res = await makeRequest('POST', '/api/trigger-workflow', {
        pipelineType: 'full',
        branch: 'main'
      });

      // Check for valid JSON response
      assert(res.body, 'Response body missing');
      
      if (res.statusCode === 200) {
        // Success response structure
        assert(res.body.status, 'Missing status field');
        assert(res.body.message, 'Missing message field');
        assert(res.body.workflow, 'Missing workflow field');
        assert(res.body.branch, 'Missing branch field');
        assert(res.body.pipelineType, 'Missing pipelineType field');
        assert(res.body.timestamp, 'Missing timestamp field');
        console.log('✅ PASS: Success response has correct structure\n');
      } else if (res.statusCode === 503) {
        // Token not configured - expected in test environment
        assert(res.body.status === 'error', 'Missing error status');
        assert(res.body.error, 'Missing error message');
        console.log('✅ PASS: Error response has correct structure (token not configured)\n');
      } else if (res.statusCode === 400) {
        // Validation error
        assert(res.body.status === 'error', 'Missing error status');
        assert(res.body.error, 'Missing error message');
        console.log('✅ PASS: Validation error response has correct structure\n');
      } else {
        console.log(`⚠️  Unexpected status ${res.statusCode} but response is valid JSON\n`);
      }
    } catch (err) {
      console.log(`❌ FAIL: ${err.message}\n`);
      throw err;
    }

    // Test 9: Endpoint not accessible via GET
    console.log('Test 9: Endpoint rejects GET requests...');
    try {
      const res = await makeRequest('GET', '/api/trigger-workflow', null);
      assert(res.statusCode !== 200, 'GET request should not succeed');
      console.log('✅ PASS: GET requests rejected\n');
    } catch (err) {
      console.log(`❌ FAIL: ${err.message}\n`);
      throw err;
    }

    // Test 10: Endpoint location (before 404 handler)
    console.log('Test 10: Endpoint is before 404 handler...');
    try {
      const res = await makeRequest('POST', '/api/trigger-workflow', {
        pipelineType: 'full',
        branch: 'main'
      });
      // If we get a 404, the endpoint wasn't reached (it's after 404 handler)
      assert(res.statusCode !== 404, 'Endpoint is being caught by 404 handler');
      console.log('✅ PASS: Endpoint is properly registered before 404 handler\n');
    } catch (err) {
      console.log(`❌ FAIL: ${err.message}\n`);
      throw err;
    }

    console.log('═══════════════════════════════════════════════════');
    console.log('✅ ALL TESTS PASSED!');
    console.log('═══════════════════════════════════════════════════\n');
    process.exit(0);
  } catch (error) {
    console.error('\n❌ TEST SUITE FAILED');
    console.error(`Error: ${error.message}\n`);
    process.exit(1);
  }
}

// Run tests with a timeout to allow server startup
setTimeout(() => {
  runTests().catch(err => {
    console.error(err);
    process.exit(1);
  });
}, 500);
