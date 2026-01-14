#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const PA11Y_REPORT = './pa11y-report.json';
const AUDIT_REPORT = './audit-report.json';

console.log('🔍 Running Compliance & Security Scan...\n');

try {
  // Start server
  console.log('📦 Starting development server...');
  const serverProcess = require('child_process').spawn('npm', ['start'], {
    detached: true,
    stdio: 'ignore'
  });
  serverProcess.unref();
  
  // Wait for server to start
  setTimeout(() => {
    console.log('⏳ Waiting for server to be ready...\n');
  }, 2000);

  // Run Pa11y CI
  console.log('♿ Running Pa11y accessibility tests...');
  try {
    execSync('npm run test:pa11y', { stdio: 'inherit' });
    console.log('✅ Pa11y tests passed!\n');
  } catch (error) {
    console.error('❌ Pa11y found accessibility violations\n');
    process.exitCode = 1;
  }

  // Run npm audit
  console.log('🔐 Running npm audit for security vulnerabilities...');
  try {
    execSync('npm audit --json > audit-report.json 2>&1', { stdio: 'inherit' });
    console.log('✅ No critical security vulnerabilities found!\n');
  } catch (error) {
    try {
      const auditResults = JSON.parse(fs.readFileSync('audit-report.json', 'utf-8'));
      if (auditResults.metadata?.severity === 'critical') {
        console.error('❌ Critical security vulnerabilities detected!\n');
        process.exitCode = 1;
      } else {
        console.warn('⚠️  Non-critical vulnerabilities found\n');
      }
    } catch (parseError) {
      console.error('⚠️  Could not parse audit results\n');
    }
  }

  // Summary
  console.log('\n📋 Scan Summary:');
  console.log('================');
  if (fs.existsSync(PA11Y_REPORT)) {
    console.log(`✓ Pa11y report: ${PA11Y_REPORT}`);
  }
  if (fs.existsSync(AUDIT_REPORT)) {
    console.log(`✓ Audit report: ${AUDIT_REPORT}`);
  }

  // Kill server
  process.kill(-serverProcess.pid);

} catch (error) {
  console.error('Error running compliance scan:', error.message);
  process.exitCode = 1;
}
