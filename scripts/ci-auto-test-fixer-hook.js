#!/usr/bin/env node

/**
 * CI/CD Pipeline Hook - Auto Test Fixer
 * 
 * Integrated into GitHub Actions workflow to automatically detect and fix
 * test framework issues before they cause pipeline failures
 * 
 * Runs in: Phase 3 (post-test-generation, pre-test-execution)
 */

const AutomatedTestFixer = require('./automated-test-fixer');

async function runTestFixerHook() {
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║     🔧 CI/CD AUTO TEST FIXER HOOK                          ║');
  console.log('║     Automatically repairing test framework issues...       ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  const fixer = new AutomatedTestFixer();

  try {
    const result = await fixer.execute();

    if (result.status === 'success') {
      console.log('✅ Test framework auto-repair completed successfully');
      console.log(`   Applied ${result.fixesApplied} fix(es) across test frameworks\n`);
      
      // If fixes were applied, tests should now pass
      if (result.fixesApplied > 0) {
        console.log('📋 Tests ready to execute. Pipeline will proceed.\n');
        process.exit(0);
      }
    } else {
      console.log('⚠️ Test fixer encountered issues, but proceeding with tests\n');
      process.exit(0);
    }
  } catch (error) {
    console.error('❌ Critical error in test fixer hook:', error.message);
    console.log('\n⚠️ Proceeding with tests anyway (hook should not block pipeline)\n');
    process.exit(0);
  }
}

// Execute hook
runTestFixerHook();

module.exports = runTestFixerHook;
