#!/usr/bin/env node

/**
 * Comprehensive Test Runner
 * Runs all test suites for client onboarding and dashboard functionality
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const tests = [
  {
    name: 'Client Onboarding Tests',
    file: 'test-client-onboarding.js',
    description: 'Tests client registration, pipeline operations, and data integrity'
  },
  {
    name: 'Dashboard Integration Tests',
    file: 'test-dashboard-integration.js',
    description: 'Tests dashboard functionality, UI elements, and API integration'
  },
  {
    name: 'End-to-End Integration Tests',
    file: 'test-e2e-integration.js',
    description: 'Tests complete workflows from authentication to results submission'
  }
];

const testResults = {
  totalTests: tests.length,
  passed: 0,
  failed: 0,
  details: []
};

async function runTest(testConfig) {
  return new Promise((resolve) => {
    console.log(`\n${'='.repeat(70)}`);
    console.log(`🧪 Running: ${testConfig.name}`);
    console.log(`📝 ${testConfig.description}`);
    console.log('='.repeat(70));
    console.log('');

    const testPath = path.join(__dirname, testConfig.file);
    const proc = spawn('node', [testPath], {
      cwd: __dirname,
      stdio: 'inherit',
      env: {
        ...process.env,
        PORT: process.env.PORT || '3000',
        SAAS_PORT: process.env.SAAS_PORT || '3001'
      }
    });

    proc.on('close', (code) => {
      if (code === 0) {
        testResults.passed++;
        testResults.details.push({
          test: testConfig.name,
          status: 'PASSED',
          exitCode: code
        });
        console.log(`\n✅ ${testConfig.name} PASSED\n`);
      } else {
        testResults.failed++;
        testResults.details.push({
          test: testConfig.name,
          status: 'FAILED',
          exitCode: code
        });
        console.log(`\n❌ ${testConfig.name} FAILED (exit code: ${code})\n`);
      }
      resolve(code);
    });

    proc.on('error', (err) => {
      testResults.failed++;
      testResults.details.push({
        test: testConfig.name,
        status: 'ERROR',
        error: err.message
      });
      console.log(`\n❌ Error running ${testConfig.name}: ${err.message}\n`);
      resolve(1);
    });
  });
}

async function runAllTests() {
  console.log('');
  console.log('╔' + '═'.repeat(68) + '╗');
  console.log('║' + ' COMPREHENSIVE TEST SUITE FOR CLIENT ONBOARDING & DASHBOARD '.padEnd(69) + '║');
  console.log('╚' + '═'.repeat(68) + '╝');
  console.log('');
  console.log('📋 Test Suite Overview:');
  console.log(`   Total Test Suites: ${tests.length}`);
  console.log(`   Total Test Cases: 50+`);
  console.log(`   Coverage Areas: Auth, Client Ops, Dashboard, API, E2E`);
  console.log('');

  const startTime = Date.now();

  for (const testConfig of tests) {
    await runTest(testConfig);
  }

  const duration = (Date.now() - startTime) / 1000;

  // Print final summary
  console.log('\n' + '╔' + '═'.repeat(68) + '╗');
  console.log('║' + ' TEST SUITE EXECUTION SUMMARY '.padEnd(69) + '║');
  console.log('╠' + '═'.repeat(68) + '╣');

  testResults.details.forEach((detail, index) => {
    const emoji = detail.status === 'PASSED' ? '✅' : '❌';
    const line = `║ ${emoji} ${detail.test}`.padEnd(69) + '║';
    console.log(line);
  });

  console.log('╠' + '═'.repeat(68) + '╣');
  console.log(`║ Total: ${testResults.totalTests} | Passed: ${testResults.passed} | Failed: ${testResults.failed}`.padEnd(69) + '║');
  console.log(`║ Execution Time: ${duration.toFixed(2)}s`.padEnd(69) + '║');
  console.log('╚' + '═'.repeat(68) + '╝');

  if (testResults.failed === 0) {
    console.log('\n✨ ALL TEST SUITES PASSED ✨\n');
    console.log('🎯 System Status: READY FOR DEPLOYMENT\n');
    console.log('✅ Client Onboarding:');
    console.log('   • Registration, retrieval, and listing working');
    console.log('   • Pipeline trigger endpoints functional');
    console.log('   • Results submission working correctly');
    console.log('');
    console.log('✅ Dashboard Functionality:');
    console.log('   • All UI elements properly structured');
    console.log('   • All JavaScript functions implemented');
    console.log('   • Client mode fully functional');
    console.log('   • API integration complete');
    console.log('');
    console.log('✅ End-to-End Workflows:');
    console.log('   • User authentication flow validated');
    console.log('   • Client registration tested');
    console.log('   • Pipeline execution verified');
    console.log('   • Results handling working');
    console.log('   • Data isolation maintained');
    console.log('   • Error recovery validated');
    console.log('');
    process.exit(0);
  } else {
    console.log('\n❌ SOME TEST SUITES FAILED\n');
    console.log('⚠️  Please review the failures above and fix the issues.');
    console.log('');
    process.exit(1);
  }
}

// Run all tests
runAllTests().catch(error => {
  console.error('Fatal error running tests:', error);
  process.exit(1);
});
