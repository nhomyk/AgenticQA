#!/usr/bin/env node

/**
 * Pipeline Phase Validator
 * 
 * Validates each phase left-to-right and coordinates fixes
 * Acts as a bridge between phases to ensure sequential healing
 * 
 * Key Principle:
 * - Each phase depends on previous phase
 * - If phase N fails, it should be fixed before phase N+1
 * - Early phases (rescue, lint) prevent cascade failures in later phases
 */

const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const { promisify } = require('util');

const execAsync = promisify(exec);

// Phase definitions in order of execution
const PIPELINE_PHASES = [
  {
    id: -1,
    name: 'Pipeline Rescue',
    command: 'node pipeline-maintenance-coordinator.js',
    critical: true,
    description: 'Health check & emergency repair',
  },
  {
    id: 0,
    name: 'Linting Fix',
    command: 'npx eslint . --ext .js --fix && npm run lint',
    critical: true,
    description: 'Auto-fix linting errors',
  },
  {
    id: 1,
    name: 'Unit Tests',
    command: 'npm run test:unit',
    critical: false,
    description: 'Jest unit tests',
  },
  {
    id: 2,
    name: 'Integration Tests',
    command: 'npm run test:integration',
    critical: false,
    description: 'Playwright E2E tests',
  },
];

class PipelinePhaseValidator {
  constructor() {
    this.phases = PIPELINE_PHASES;
    this.results = [];
    this.failureLog = {};
    this.statusFile = '.phase-validation-status.json';
  }

  /**
   * Validate a single phase
   */
  async validatePhase(phase) {
    console.log(`\n${'='.repeat(60)}`);
    console.log(`🔍 Validating Phase ${phase.id}: ${phase.name}`);
    console.log(`   ${phase.description}`);
    console.log(`${'='.repeat(60)}`);

    const startTime = Date.now();

    try {
      // Check prerequisites
      await this.checkPrerequisites(phase);

      // Run validation command
      console.log(`   Running: ${phase.command}`);
      const { stdout, stderr } = await execAsync(phase.command, {
        timeout: 120000, // 2 minute timeout per phase
        cwd: process.cwd(),
      });

      const duration = ((Date.now() - startTime) / 1000).toFixed(2);

      const result = {
        phase: phase.id,
        name: phase.name,
        status: 'passed',
        duration: `${duration}s`,
        timestamp: new Date().toISOString(),
        output: stdout.substring(0, 500), // First 500 chars
      };

      this.results.push(result);
      console.log(`✅ Phase ${phase.id} PASSED (${duration}s)`);

      return result;
    } catch (error) {
      const duration = ((Date.now() - startTime) / 1000).toFixed(2);

      const result = {
        phase: phase.id,
        name: phase.name,
        status: 'failed',
        duration: `${duration}s`,
        timestamp: new Date().toISOString(),
        error: error.message,
        stderr: error.stderr ? error.stderr.substring(0, 500) : '',
      };

      this.results.push(result);
      this.failureLog[phase.id] = error.message;

      console.log(`❌ Phase ${phase.id} FAILED (${duration}s)`);
      console.log(`   Error: ${error.message}`);

      // If critical phase fails, stop and report
      if (phase.critical) {
        console.log(`   ⚠️  CRITICAL PHASE FAILURE - Pipeline blocked`);
        throw new Error(
          `Critical phase ${phase.id} (${phase.name}) failed. Pipeline cannot continue.`
        );
      }

      return result;
    }
  }

  /**
   * Check phase prerequisites
   */
  async checkPrerequisites(phase) {
    // Always ensure dependencies are installed
    if (!fs.existsSync('node_modules')) {
      console.log('   📦 Installing dependencies...');
      await execAsync('npm install --legacy-peer-deps', { timeout: 60000 });
    }

    // Check if previous critical phases passed
    if (phase.id > -1) {
      const criticalPhasesPassed = this.results
        .filter((r) => PIPELINE_PHASES.find((p) => p.id === r.phase && p.critical))
        .every((r) => r.status === 'passed');

      if (!criticalPhasesPassed) {
        throw new Error('Previous critical phase did not pass. Cannot proceed.');
      }
    }
  }

  /**
   * Run all phases in sequence
   */
  async validateAllPhases() {
    console.log('\n');
    console.log('╔' + '═'.repeat(58) + '╗');
    console.log('║' + '  🚀 PIPELINE PHASE VALIDATOR - LEFT-TO-RIGHT  '.padEnd(59) + '║');
    console.log('║' + '  Sequential validation with error recovery    '.padEnd(59) + '║');
    console.log('╚' + '═'.repeat(58) + '╝');

    for (const phase of this.phases) {
      try {
        await this.validatePhase(phase);
      } catch (error) {
        console.error(`\n🛑 Pipeline validation stopped: ${error.message}`);
        this.saveStatus();
        process.exit(1);
      }
    }

    this.saveStatus();
    this.printSummary();
  }

  /**
   * Save validation status
   */
  saveStatus() {
    const status = {
      timestamp: new Date().toISOString(),
      totalPhases: this.phases.length,
      passedPhases: this.results.filter((r) => r.status === 'passed').length,
      failedPhases: this.results.filter((r) => r.status === 'failed').length,
      results: this.results,
      failureLog: this.failureLog,
    };

    fs.writeFileSync(this.statusFile, JSON.stringify(status, null, 2));
    console.log(`\n📊 Status saved to ${this.statusFile}`);
  }

  /**
   * Print validation summary
   */
  printSummary() {
    const passed = this.results.filter((r) => r.status === 'passed').length;
    const failed = this.results.filter((r) => r.status === 'failed').length;
    const total = this.results.length;

    console.log('\n');
    console.log('╔' + '═'.repeat(58) + '╗');
    console.log('║' + '  📋 VALIDATION SUMMARY                       '.padEnd(59) + '║');
    console.log('╚' + '═'.repeat(58) + '╝');

    console.log(`\nTotal Phases: ${total}`);
    console.log(`✅ Passed: ${passed}`);
    console.log(`❌ Failed: ${failed}`);
    console.log(`📊 Success Rate: ${((passed / total) * 100).toFixed(1)}%`);

    if (failed === 0) {
      console.log('\n🎉 All phases validated successfully!');
      console.log('✅ Pipeline is ready for deployment\n');
      process.exit(0);
    } else {
      console.log('\n⚠️  Some phases failed. Review errors above.\n');
      process.exit(1);
    }
  }
}

// Run validator if executed directly
if (require.main === module) {
  const validator = new PipelinePhaseValidator();
  validator.validateAllPhases().catch((error) => {
    console.error('❌ Fatal error:', error.message);
    process.exit(1);
  });
}

module.exports = PipelinePhaseValidator;
