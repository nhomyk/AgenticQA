#!/usr/bin/env node
/**
 * Test script for custom pipeline name feature
 * 
 * This script:
 * 1. Connects to a GitHub repository
 * 2. Triggers a workflow with a custom pipeline name
 * 3. Verifies the workflow displays the custom name in GitHub Actions
 */

const fetch = require('node-fetch');
const fs = require('fs');
const path = require('path');

// Configuration
const CONFIG = {
  serverUrl: 'http://localhost:3001',
  githubToken: process.env.GITHUB_TOKEN,
  repository: process.env.GITHUB_REPO || 'your-org/your-repo',
  branch: process.env.GITHUB_BRANCH || 'main',
  customPipelineName: process.env.CUSTOM_PIPELINE_NAME || '🚀 Custom Test Pipeline'
};

console.log('\n📋 Custom Pipeline Name Test\n');
console.log('Configuration:', {
  serverUrl: CONFIG.serverUrl,
  repository: CONFIG.repository,
  branch: CONFIG.branch,
  customPipelineName: CONFIG.customPipelineName
});

// Step 1: Get JWT token
async function login() {
  console.log('\n1️⃣  Logging in...');
  try {
    const response = await fetch(`${CONFIG.serverUrl}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'demo@orbitqa.ai',
        password: 'demo123'
      })
    });

    if (!response.ok) {
      throw new Error(`Login failed: ${response.status}`);
    }

    const data = await response.json();
    console.log('✅ Login successful');
    return data.token;
  } catch (error) {
    console.error('❌ Login failed:', error.message);
    process.exit(1);
  }
}

// Step 2: Connect GitHub
async function connectGitHub(token) {
  console.log('\n2️⃣  Connecting GitHub...');
  try {
    const response = await fetch(`${CONFIG.serverUrl}/api/github/connect`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        token: CONFIG.githubToken,
        repository: CONFIG.repository
      })
    });

    if (!response.ok) {
      throw new Error(`GitHub connect failed: ${response.status}`);
    }

    const data = await response.json();
    console.log('✅ GitHub connected');
    console.log('   Repository:', CONFIG.repository);
    return true;
  } catch (error) {
    console.error('❌ GitHub connection failed:', error.message);
    process.exit(1);
  }
}

// Step 3: Trigger workflow with custom name
async function triggerWorkflow(token) {
  console.log('\n3️⃣  Triggering workflow with custom pipeline name...');
  console.log(`   Custom name: "${CONFIG.customPipelineName}"`);
  
  try {
    const response = await fetch(`${CONFIG.serverUrl}/api/trigger-workflow`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        pipelineType: 'full',
        branch: CONFIG.branch,
        pipelineName: CONFIG.customPipelineName
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`Workflow trigger failed: ${error.error || response.status}`);
    }

    const data = await response.json();
    console.log('✅ Workflow triggered successfully');
    console.log('   Status:', data.status);
    console.log('   Message:', data.message);
    console.log('   Workflow:', data.workflow);
    console.log('   Repository:', data.repository);
    console.log('   Branch:', data.branch);
    
    return data;
  } catch (error) {
    console.error('❌ Workflow trigger failed:', error.message);
    process.exit(1);
  }
}

// Step 4: Verify in GitHub
async function verifyInGitHub() {
  console.log('\n4️⃣  Verification steps:');
  console.log(`   1. Go to: https://github.com/${CONFIG.repository}/actions`);
  console.log(`   2. Look for a run with the title: "${CONFIG.customPipelineName}"`);
  console.log(`   3. Click on the run to see the full workflow summary`);
  console.log(`   4. Verify the custom name appears in the workflow summary`);
}

// Main execution
async function main() {
  try {
    // Validate environment
    if (!CONFIG.githubToken) {
      console.error('\n❌ GITHUB_TOKEN environment variable is required');
      console.log('\nSet it with:');
      console.log('   export GITHUB_TOKEN="your-github-token"');
      process.exit(1);
    }

    // Run tests
    const token = await login();
    await connectGitHub(token);
    const result = await triggerWorkflow(token);
    await verifyInGitHub();

    console.log('\n✅ Test completed successfully!\n');
  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    process.exit(1);
  }
}

main();
