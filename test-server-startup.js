#!/usr/bin/env node

/**
 * Server Startup Diagnostic
 * Tests if the server can start without errors
 */

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

console.log('🧪 Server Startup Diagnostic\n');

// Check prerequisites
console.log('Checking prerequisites...\n');

const checks = [
  { name: 'Node.js', check: () => process.version },
  { name: 'npm version', check: () => require('child_process').execSync('npm -v').toString().trim() },
  { name: 'server.js exists', check: () => fs.existsSync('./server.js') ? '✓' : '✗' },
  { name: '.env exists', check: () => fs.existsSync('./.env') ? '✓' : 'Not found (will use defaults)' },
  { name: 'public/dashboard.html', check: () => fs.existsSync('./public/dashboard.html') ? '✓' : '✗' },
  { name: 'node_modules', check: () => fs.existsSync('./node_modules') ? '✓' : '✗' },
];

checks.forEach(c => {
  try {
    const result = c.check();
    console.log(`  ✓ ${c.name}: ${result}`);
  } catch (err) {
    console.log(`  ✗ ${c.name}: ${err.message}`);
  }
});

console.log('\n---\n');
console.log('Attempting to start server...\n');

// Start server
const server = spawn('node', ['server.js'], {
  cwd: process.cwd(),
  stdio: 'pipe'
});

let output = '';
let error = '';
let serverReady = false;

server.stdout.on('data', (data) => {
  output += data.toString();
  console.log(data.toString());
  if (output.includes('Server started')) {
    serverReady = true;
  }
});

server.stderr.on('data', (data) => {
  error += data.toString();
  console.error(data.toString());
});

server.on('error', (err) => {
  console.error(`\n❌ Failed to spawn server: ${err.message}`);
  process.exit(1);
});

// Wait a few seconds and check if server started
setTimeout(() => {
  if (serverReady) {
    console.log('\n✅ Server started successfully!');
    console.log('\n📝 Next steps:');
    console.log('   1. Open http://localhost:3000 in your browser');
    console.log('   2. Try clicking the buttons to test functionality');
    console.log('   3. Press Ctrl+C to stop the server\n');
  } else if (error) {
    console.log('\n❌ Server failed to start with error:');
    console.log(error);
    process.exit(1);
  } else {
    console.log('\n⏳ Server is still starting...');
    console.log('   Waiting for startup message...\n');
  }
}, 3000);
