#!/usr/bin/env node

/**
 * Test script to verify the /api/setup-self-service endpoint is working
 * This tests both direct calls to port 3001 and proxied calls through port 3000
 */

const http = require('http');

// Test data
const testData = {
  repoUrl: 'https://github.com/nhomyk/test-repo',
  githubToken: 'test_token_12345'
};

async function makeRequest(hostname, port, path, method, data) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: hostname,
      port: port,
      path: path,
      method: method,
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': 'Test-Client/1.0'
      }
    };

    const req = http.request(options, (res) => {
      let responseData = '';
      
      res.on('data', (chunk) => {
        responseData += chunk;
      });
      
      res.on('end', () => {
        try {
          const parsed = JSON.parse(responseData);
          resolve({
            status: res.statusCode,
            headers: res.headers,
            body: parsed
          });
        } catch (e) {
          resolve({
            status: res.statusCode,
            headers: res.headers,
            body: responseData
          });
        }
      });
    });

    req.on('error', (e) => {
      reject(e);
    });

    if (data) {
      req.write(JSON.stringify(data));
    }
    req.end();
  });
}

async function runTests() {
  console.log('\n🧪 Testing /api/setup-self-service endpoint\n');
  
  // Test 1: Direct call to SaaS API server (port 3001)
  console.log('📌 Test 1: Direct call to port 3001 (SaaS API)');
  try {
    const response1 = await makeRequest('localhost', 3001, '/api/setup-self-service', 'POST', testData);
    console.log(`   Status: ${response1.status}`);
    console.log(`   Response: ${JSON.stringify(response1.body).substring(0, 200)}...`);
    
    if (response1.status === 400) {
      console.log('   ✅ Endpoint is reachable on port 3001 (expected 400 for invalid token)\n');
    } else if (response1.status === 404) {
      console.log('   ❌ Endpoint NOT FOUND on port 3001\n');
    } else {
      console.log('   ✅ Endpoint responded (status: ' + response1.status + ')\n');
    }
  } catch (error) {
    console.log(`   ❌ Error: ${error.message}\n`);
  }

  // Test 2: Proxied call through dashboard server (port 3000)
  console.log('📌 Test 2: Proxied call through port 3000 (Dashboard)');
  try {
    const response2 = await makeRequest('localhost', 3000, '/api/setup-self-service', 'POST', testData);
    console.log(`   Status: ${response2.status}`);
    console.log(`   Response: ${JSON.stringify(response2.body).substring(0, 200)}...`);
    
    if (response2.status === 400 || response2.status === 200) {
      console.log('   ✅ Endpoint is accessible through proxy on port 3000\n');
    } else if (response2.status === 503) {
      console.log('   ⚠️  SaaS API server not available on port 3001\n');
    } else if (response2.status === 404) {
      console.log('   ❌ Endpoint NOT FOUND through proxy\n');
    } else {
      console.log('   ⚠️  Unexpected status: ' + response2.status + '\n');
    }
  } catch (error) {
    console.log(`   ❌ Error: ${error.message}\n`);
  }

  // Test 3: Check health endpoints
  console.log('📌 Test 3: Health check on port 3000');
  try {
    const healthResponse = await makeRequest('localhost', 3000, '/health', 'GET');
    console.log(`   Status: ${healthResponse.status}`);
    if (healthResponse.status === 200) {
      console.log('   ✅ Dashboard server is running\n');
    }
  } catch (error) {
    console.log(`   ❌ Error: ${error.message} (Dashboard server may not be running)\n`);
  }

  console.log('✅ Test complete!\n');
}

runTests().catch(error => {
  console.error('Test failed:', error);
  process.exit(1);
});
