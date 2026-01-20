#!/usr/bin/env node
// Simple dual-server startup script
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

const projectRoot = __dirname;

// Kill processes on ports 3000 and 3001
require('child_process').execSync('lsof -ti:3000,3001 | xargs kill -9 2>/dev/null || true');

console.log('🚀 Starting OrbitQA servers...\n');

// Start saas-api-dev.js on port 3001
const apiProcess = spawn('node', ['saas-api-dev.js'], {
  cwd: projectRoot,
  env: { ...process.env, NODE_ENV: 'development' },
  stdio: 'inherit'
});

// Start server.js on port 3000 after 2 seconds
setTimeout(() => {
  const dashboardProcess = spawn('node', ['server.js'], {
    cwd: projectRoot,
    env: { ...process.env, NODE_ENV: 'development' },
    stdio: 'inherit'
  });

  dashboardProcess.on('error', (err) => {
    console.error('❌ Dashboard server error:', err);
    process.exit(1);
  });
}, 2000);

apiProcess.on('error', (err) => {
  console.error('❌ API server error:', err);
  process.exit(1);
});

// Handle signals
process.on('SIGINT', () => {
  console.log('\n🛑 Shutting down servers...');
  apiProcess.kill();
  process.exit(0);
});
