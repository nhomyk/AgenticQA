#!/usr/bin/env node

/**
 * Verification Script for GitHub Integration
 * Tests that all GitHub integration endpoints are properly implemented
 */

const http = require('http');

const API_BASE = 'http://localhost:3001';
const ENDPOINTS = [
  { method: 'GET', path: '/api/github/status', description: 'Check GitHub connection status' },
  { method: 'POST', path: '/api/github/connect', description: 'Connect GitHub account' },
  { method: 'POST', path: '/api/github/test', description: 'Test GitHub connection' },
  { method: 'POST', path: '/api/github/disconnect', description: 'Disconnect GitHub' },
  { method: 'POST', path: '/api/trigger-workflow', description: 'Trigger CI/CD workflow' }
];

async function testEndpoint(method, path, description) {
  return new Promise((resolve) => {
    const url = new URL(API_BASE + path);
    const options = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search,
      method: method,
      headers: {
        'Content-Type': 'application/json'
      }
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        const status = res.statusCode;
        const success = status >= 200 && status < 500; // We expect some response, not 404
        resolve({
          path,
          method,
          description,
          status,
          success: success && status !== 404,
          endpoint: status === 404 ? 'NOT FOUND' : status >= 200 && status < 300 ? 'OK' : `ERROR ${status}`,
          exists: status !== 404
        });
      });
    });

    req.on('error', (err) => {
      resolve({
        path,
        method,
        description,
        status: 'NETWORK_ERROR',
        success: false,
        endpoint: `ERROR: ${err.message}`,
        exists: false
      });
    });

    // Send empty body for POST requests
    if (method === 'POST') {
      req.write('{}');
    }
    req.end();
  });
}

async function runTests() {
  console.log('\n🧪 GitHub Integration Verification\n');
  console.log('=' .repeat(70));
  
  const results = [];
  for (const { method, path, description } of ENDPOINTS) {
    const result = await testEndpoint(method, path, description);
    results.push(result);
    
    const icon = result.exists ? '✅' : '❌';
    console.log(`${icon} ${method.padEnd(6)} ${path.padEnd(30)} - ${description}`);
    if (!result.exists) {
      console.log(`   Status: ${result.endpoint}`);
    }
  }
  
  console.log('=' .repeat(70));
  
  const allExists = results.every(r => r.exists);
  
  if (allExists) {
    console.log('\n✅ All GitHub integration endpoints are implemented!\n');
    console.log('Next steps:');
    console.log('1. Go to Dashboard Settings (⚙️)');
    console.log('2. Click "🔑 Use Personal Access Token"');
    console.log('3. Create a GitHub PAT at: https://github.com/settings/tokens');
    console.log('4. Select scopes: repo, workflow, admin:repo_hook');
    console.log('5. Paste token and repository (username/repo) in Settings');
    console.log('6. Test the connection');
    console.log('7. Try triggering a pipeline from the Dashboard\n');
  } else {
    console.log('\n❌ Some endpoints are missing. Please check server logs.\n');
    process.exit(1);
  }
}

// Check if server is running
const checkServer = () => {
  const req = http.get(API_BASE, (res) => {
    if (res.statusCode === 404 || res.statusCode === 200) {
      // Server is running
      runTests().catch(console.error);
    }
  }).on('error', (err) => {
    console.error(`\n❌ Error: Cannot connect to server at ${API_BASE}`);
    console.error(`\n   Make sure to start the server first:`);
    console.error(`   npm run dev:saas-api\n`);
    process.exit(1);
  });
};

checkServer();
