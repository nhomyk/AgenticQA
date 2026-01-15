#!/usr/bin/env node

/**
 * Comprehensive Server Troubleshooting Guide
 */

const fs = require('fs');
const path = require('path');
const net = require('net');

console.log('\n╔═══════════════════════════════════════════════════════════════╗');
console.log('║         AgenticQA Server - Troubleshooting Guide              ║');
console.log('╚═══════════════════════════════════════════════════════════════╝\n');

// Step 1: Environment check
console.log('STEP 1: Environment Check');
console.log('─────────────────────────────────────────');
console.log(`Node version: ${process.version}`);
console.log(`Working directory: ${process.cwd()}`);
console.log(`Platform: ${process.platform}\n`);

// Step 2: File check
console.log('STEP 2: File Verification');
console.log('─────────────────────────────────────────');

const criticalFiles = [
  'server.js',
  'public/dashboard.html',
  'package.json',
  'node_modules'
];

let allFilesOk = true;
criticalFiles.forEach(f => {
  const exists = fs.existsSync(f);
  console.log(`${exists ? '✅' : '❌'} ${f}`);
  if (!exists) allFilesOk = false;
});

if (!allFilesOk) {
  console.log('\n❌ Missing critical files!\n');
  process.exit(1);
}
console.log();

// Step 3: Port check
console.log('STEP 3: Port Availability');
console.log('─────────────────────────────────────────');

const PORT = process.env.PORT || 3000;

function checkPort(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    
    server.once('error', (err) => {
      if (err.code === 'EADDRINUSE') {
        resolve({ port, available: false });
      } else {
        resolve({ port, available: true });
      }
    });
    
    server.once('listening', () => {
      server.close();
      resolve({ port, available: true });
    });
    
    server.listen(port, 'localhost');
  });
}

checkPort(PORT).then(result => {
  if (result.available) {
    console.log(`✅ Port ${PORT} is available\n`);
    printInstructions();
  } else {
    console.log(`❌ Port ${PORT} is already in use!\n`);
    console.log('FIX: Kill the process using this port:');
    console.log(`    lsof -ti:${PORT} | xargs kill -9\n`);
    console.log('Or use a different port:');
    console.log(`    PORT=3001 node server.js\n`);
  }
});

function printInstructions() {
  console.log('STEP 4: Starting the Server');
  console.log('─────────────────────────────────────────\n');
  
  console.log('✅ Everything looks good!\n');
  console.log('To start the server, run:\n');
  console.log(`    cd ${process.cwd()}`);
  console.log('    node server.js\n');
  console.log('Then open in your browser:');
  console.log(`    http://localhost:${PORT}\n`);
  console.log('If that doesn\'t work, try:');
  console.log('    http://127.0.0.1:' + PORT + '\n');
  
  console.log('DEBUGGING:');
  console.log('─────────────────────────────────────────');
  console.log('If the server won\'t start:');
  console.log('  1. Check for error messages when running: node server.js');
  console.log('  2. Run: npm install  (to reinstall dependencies)');
  console.log('  3. Run: node validate-server.js  (to check syntax)\n');
  
  console.log('If you can\'t reach localhost:');
  console.log('  1. Check the server is actually running');
  console.log('  2. Try: curl http://localhost:' + PORT);
  console.log('  3. Try: curl http://127.0.0.1:' + PORT + '\n');
}
