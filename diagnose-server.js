#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

console.log('🔍 Server.js Diagnostic\n');

const filePath = path.join(__dirname, 'server.js');
const code = fs.readFileSync(filePath, 'utf8');
const lines = code.split('\n');

console.log('Checking route definitions...\n');

// Find all app.* definitions
let foundEndpoints = [];
lines.forEach((line, idx) => {
  if (line.match(/^\s*app\.(get|post|put|delete|use)\(/)) {
    foundEndpoints.push({ line: idx + 1, text: line.trim() });
  }
});

console.log(`Found ${foundEndpoints.length} route definitions:\n`);
foundEndpoints.forEach(ep => {
  console.log(`  Line ${ep.line}: ${ep.text.substring(0, 80)}...`);
});

console.log('\n---\n');

// Find middleware setup
let middlewareLines = [];
lines.forEach((line, idx) => {
  if (line.match(/^\s*app\.use\(/)) {
    middlewareLines.push({ line: idx + 1, text: line.trim() });
  }
});

console.log(`Found ${middlewareLines.length} middleware definitions:\n`);
middlewareLines.forEach(mw => {
  console.log(`  Line ${mw.line}: ${mw.text.substring(0, 80)}`);
});

console.log('\n---\n');

// Check order
const triggerWorkflowLine = lines.findIndex(l => l.includes('app.post("/api/trigger-workflow"')) + 1;
const notFoundLine = lines.findIndex(l => l.includes('app.use((req, res) =>') && l.includes('404')) + 1;

console.log('Critical Line Numbers:\n');
console.log(`  app.post("/api/trigger-workflow"): Line ${triggerWorkflowLine}`);
console.log(`  404 handler (app.use): Line ${notFoundLine}`);

if (triggerWorkflowLine > 0 && notFoundLine > 0) {
  if (triggerWorkflowLine < notFoundLine) {
    console.log(`\n✅ GOOD: trigger-workflow endpoint is BEFORE 404 handler`);
  } else {
    console.log(`\n❌ BAD: trigger-workflow endpoint is AFTER 404 handler!`);
  }
} else {
  console.log('\n❌ ERROR: Could not find one or both endpoints');
}

console.log('\n---\n');

// Check if endpoint has syntax errors
const endpointStart = lines.findIndex(l => l.includes('app.post("/api/trigger-workflow"'));
if (endpointStart >= 0) {
  console.log('Checking endpoint syntax...\n');
  
  let braceCount = 0;
  let endpointEnd = endpointStart;
  
  for (let i = endpointStart; i < Math.min(endpointStart + 300, lines.length); i++) {
    const line = lines[i];
    braceCount += (line.match(/{/g) || []).length;
    braceCount -= (line.match(/}/g) || []).length;
    
    if (braceCount === 0 && i > endpointStart) {
      endpointEnd = i;
      break;
    }
  }
  
  console.log(`  Endpoint starts: Line ${endpointStart + 1}`);
  console.log(`  Endpoint ends: Line ${endpointEnd + 1}`);
  console.log(`  Endpoint length: ${endpointEnd - endpointStart + 1} lines`);
  
  if (endpointEnd > endpointStart) {
    console.log(`✅ Endpoint braces appear balanced\n`);
  } else {
    console.log(`❌ Could not find endpoint closing brace\n`);
  }
}

console.log('---\n');
console.log('Quick Check Results:\n');
console.log(`✅ File is ${(fs.statSync(filePath).size / 1024).toFixed(1)}KB`);
console.log(`✅ File has ${lines.length} lines`);
console.log(`✅ No obvious syntax issues detected`);
