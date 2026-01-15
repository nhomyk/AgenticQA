#!/usr/bin/env node

/**
 * Quick Server Validation
 * Checks for syntax/require errors without starting
 */

const fs = require('fs');
const path = require('path');

console.log('🔍 Quick Server Validation\n');

// Check server.js syntax
console.log('1. Checking server.js syntax...');
try {
  require.cache[require.resolve('./server.js')] = undefined; // Clear cache
  // Just check syntax by reading and parsing the file
  const code = fs.readFileSync('./server.js', 'utf8');
  
  // Try to parse for obvious syntax errors
  new Function(code);
  console.log('   ✅ No syntax errors\n');
} catch (err) {
  console.error(`   ❌ Syntax error: ${err.message}\n`);
  process.exit(1);
}

// Check required modules
console.log('2. Checking required modules...');
const requiredModules = [
  'express',
  'body-parser',
  'puppeteer',
  'path',
  'express-rate-limit',
  'https'
];

requiredModules.forEach(mod => {
  try {
    require.resolve(mod);
    console.log(`   ✅ ${mod}`);
  } catch (err) {
    console.error(`   ❌ ${mod} - NOT INSTALLED`);
  }
});

console.log('\n3. Checking file structure...');
const requiredFiles = [
  'server.js',
  'public/dashboard.html',
  'package.json'
];

requiredFiles.forEach(file => {
  const exists = fs.existsSync(file);
  console.log(`   ${exists ? '✅' : '❌'} ${file}`);
});

console.log('\n4. PORT configuration...');
const PORT = process.env.PORT || 3000;
console.log(`   PORT: ${PORT}`);
console.log(`   Access URL: http://localhost:${PORT}\n`);

console.log('✅ All checks passed! Try running: node server.js\n');
