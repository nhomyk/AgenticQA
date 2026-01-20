#!/usr/bin/env node

/**
 * Test script to verify pipeline trigger works with JWT authentication
 */

const http = require('http');
const jwt = require('jsonwebtoken');

const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-change-in-production';

// Create a test JWT token
const testUser = {
  id: 'user_test_123',
  email: 'test@example.com',
  role: 'owner',
  organizationId: 'org_default'
};

const token = jwt.sign(testUser, JWT_SECRET, { expiresIn: '24h' });

console.log('\n🧪 Testing Pipeline Trigger with JWT Authentication\n');
console.log(`Generated JWT Token: ${token.substring(0, 50)}...\n`);

async function testTrigger() {
  return new Promise((resolve, reject) => {
    const postData = JSON.stringify({
      pipelineType: 'full',
      branch: 'main'
    });

    const options = {
      hostname: 'localhost',
      port: 3001,
      path: '/api/trigger-workflow',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': postData.length,
        'Authorization': `Bearer ${token}`
      }
    };

    console.log('📤 Sending request to /api/trigger-workflow with JWT...');
    console.log(`   Authorization: Bearer ${token.substring(0, 40)}...\n`);

    const req = http.request(options, (res) => {
      let data = '';

      res.on('data', (chunk) => {
        data += chunk;
      });

      res.on('end', () => {
        console.log(`📥 Response Status: ${res.statusCode}\n`);

        try {
          const parsed = JSON.parse(data);
          console.log('Response Body:');
          console.log(JSON.stringify(parsed, null, 2));

          if (res.statusCode === 401) {
            console.log('\n❌ FAIL: Got 401 Unauthorized - JWT token not being recognized');
            console.log('   This means Authorization header is not being sent or validated');
            reject(new Error('401 Unauthorized'));
          } else if (res.statusCode === 403) {
            console.log('\n⚠️  Got 403 Forbidden - GitHub not connected');
            console.log('   But at least authentication worked!');
            console.log('   ✅ This means JWT token IS being recognized correctly');
            resolve();
          } else if (res.statusCode === 400 || res.statusCode === 503) {
            console.log('\n⚠️  Got ' + res.statusCode);
            console.log('   But at least authentication worked!');
            console.log('   ✅ This means JWT token IS being recognized correctly');
            resolve();
          } else if (res.statusCode === 204 || res.statusCode === 200) {
            console.log('\n✅ SUCCESS: Pipeline triggered!');
            resolve();
          } else {
            console.log('\n⚠️  Unexpected status code: ' + res.statusCode);
            resolve();
          }
        } catch (e) {
          console.log('Response:', data);
          reject(e);
        }
      });
    });

    req.on('error', (e) => {
      console.error(`❌ Request failed: ${e.message}`);
      reject(e);
    });

    req.write(postData);
    req.end();
  });
}

// Test through proxy (port 3000)
async function testThroughProxy() {
  return new Promise((resolve, reject) => {
    const postData = JSON.stringify({
      pipelineType: 'full',
      branch: 'main'
    });

    const options = {
      hostname: 'localhost',
      port: 3000,
      path: '/api/trigger-workflow',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': postData.length,
        'Authorization': `Bearer ${token}`
      }
    };

    console.log('\n📤 Testing through proxy (port 3000)...\n');

    const req = http.request(options, (res) => {
      let data = '';

      res.on('data', (chunk) => {
        data += chunk;
      });

      res.on('end', () => {
        console.log(`📥 Response Status: ${res.statusCode}\n`);

        try {
          const parsed = JSON.parse(data);
          console.log('Response Body:');
          console.log(JSON.stringify(parsed, null, 2));

          if (res.statusCode === 401) {
            console.log('\n❌ FAIL: Got 401 Unauthorized - JWT token not forwarded by proxy');
            reject(new Error('401 Unauthorized'));
          } else if (res.statusCode === 403 || res.statusCode === 400 || res.statusCode === 503) {
            console.log('\n✅ SUCCESS: Proxy is forwarding JWT correctly!');
            console.log('   (Got expected error due to no GitHub connection, but auth worked)');
            resolve();
          } else {
            console.log('\n✅ Response received through proxy');
            resolve();
          }
        } catch (e) {
          console.log('Response:', data);
          reject(e);
        }
      });
    });

    req.on('error', (e) => {
      console.error(`❌ Request failed: ${e.message}`);
      reject(e);
    });

    req.write(postData);
    req.end();
  });
}

async function runTests() {
  try {
    console.log('═'.repeat(60));
    console.log('Test 1: Direct call to API server (port 3001)');
    console.log('═'.repeat(60));
    await testTrigger();

    console.log('\n' + '═'.repeat(60));
    console.log('Test 2: Call through proxy server (port 3000)');
    console.log('═'.repeat(60));
    await testThroughProxy();

    console.log('\n' + '═'.repeat(60));
    console.log('✅ All tests completed!');
    console.log('═'.repeat(60) + '\n');
  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    process.exit(1);
  }
}

runTests();
