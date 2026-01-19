#!/usr/bin/env node

/**
 * DevOps Pipeline Verification & Testing System
 * 
 * This script performs comprehensive verification that all DevOps fixes
 * are working correctly before deploying to production.
 * 
 * Usage: node pipeline-verification.js
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class PipelineVerification {
  constructor() {
    this.tests = [];
    this.passed = 0;
    this.failed = 0;
    this.warnings = 0;
  }

  /**
   * Run all verification tests
   */
  async runAllTests() {
    console.log('\n╔════════════════════════════════════════════════════════════╗');
    console.log('║          🧪 PIPELINE VERIFICATION SYSTEM 🧪               ║');
    console.log('║              Comprehensive DevOps Testing                  ║');
    console.log('╚════════════════════════════════════════════════════════════╝\n');

    // Configuration tests
    console.log('📋 TEST SUITE 1: Configuration Validation\n');
    this.testPackageJson();
    this.testWorkflowFile();
    this.testVersionFormat();
    this.testDependencies();

    // System tests
    console.log('\n🔧 TEST SUITE 2: System Configuration\n');
    this.testGitConfig();
    this.testFileStructure();
    this.testNodeVersion();

    // DevOps system tests
    console.log('\n🏗️  TEST SUITE 3: DevOps Health System\n');
    this.testHealthSystem();
    this.testMaintenanceCoordinator();
    this.testAgentIntegration();

    // Agent tests
    console.log('\n🤖 TEST SUITE 4: Agent Integration\n');
    this.testSREAgentImports();
    this.testFullstackAgentImports();
    this.testErrorRecoveryIntegration();

    // Workflow tests
    console.log('\n⚙️  TEST SUITE 5: Workflow Structure\n');
    this.testJobDependencies();
    this.testTimeoutConfiguration();
    this.testCacheConfiguration();

    // Report results
    this.generateReport();
  }

  /**
   * Test package.json validity
   */
  testPackageJson() {
    const testName = 'package.json validation';
    try {
      const pkgPath = path.join(process.cwd(), 'package.json');
      if (!fs.existsSync(pkgPath)) {
        this.fail(testName, 'package.json not found');
        return;
      }

      const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));

      // Check version format
      if (!/^\d+\.\d+\.\d+/.test(pkg.version)) {
        this.fail(testName, `Invalid version format: ${pkg.version}`);
        return;
      }

      // Check required scripts
      const requiredScripts = ['start', 'test:jest', 'test:vitest', 'test:playwright'];
      const missingScripts = requiredScripts.filter(s => !pkg.scripts?.[s]);
      if (missingScripts.length > 0) {
        this.warn(testName, `Missing scripts: ${missingScripts.join(', ')}`);
      }

      this.pass(testName);
    } catch (err) {
      this.fail(testName, err.message);
    }
  }

  /**
   * Test workflow file validity
   */
  testWorkflowFile() {
    const testName = 'workflow file validation';
    try {
      const workflowPath = path.join(process.cwd(), '.github/workflows/ci.yml');
      if (!fs.existsSync(workflowPath)) {
        this.fail(testName, 'ci.yml workflow not found');
        return;
      }

      const content = fs.readFileSync(workflowPath, 'utf8');

      // Check workflow name
      if (!content.includes('name:')) {
        this.fail(testName, 'Workflow missing name field');
        return;
      }

      // Check required sections
      const required = ['on:', 'jobs:', 'runs-on:', 'steps:'];
      const missing = required.filter(r => !content.includes(r));
      if (missing.length > 0) {
        this.fail(testName, `Missing required fields: ${missing.join(', ')}`);
        return;
      }

      // Check timeout configurations
      const timeoutCount = (content.match(/timeout-minutes:/g) || []).length;
      if (timeoutCount < 5) {
        this.warn(testName, `Only ${timeoutCount} timeout-minutes configured, expected 10+`);
      } else {
        this.pass(testName);
      }
    } catch (err) {
      this.fail(testName, err.message);
    }
  }

  /**
   * Test version format
   */
  testVersionFormat() {
    const testName = 'version format validation';
    try {
      const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
      const version = pkg.version;

      // Check for known bad versions
      if (version === '0.9.NaN' || version.includes('NaN')) {
        this.fail(testName, `Invalid version: ${version}`);
        return;
      }

      if (/^\d+\.\d+\.\d+$/.test(version)) {
        this.pass(testName, `Valid version: ${version}`);
      } else if (/^\d+\.\d+\.\d+(-\w+)?(\+\w+)?$/.test(version)) {
        this.pass(testName, `Pre-release version: ${version}`);
      } else {
        this.fail(testName, `Invalid semver format: ${version}`);
      }
    } catch (err) {
      this.fail(testName, err.message);
    }
  }

  /**
   * Test dependencies
   */
  testDependencies() {
    const testName = 'dependencies check';
    try {
      const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));

      if (!pkg.dependencies || Object.keys(pkg.dependencies).length === 0) {
        this.warn(testName, 'No dependencies specified');
      } else if (!pkg.devDependencies || Object.keys(pkg.devDependencies).length === 0) {
        this.warn(testName, 'No devDependencies specified');
      } else {
        this.pass(testName);
      }
    } catch (err) {
      this.fail(testName, err.message);
    }
  }

  /**
   * Test git configuration
   */
  testGitConfig() {
    const testName = 'git configuration';
    try {
      const gitDir = path.join(process.cwd(), '.git');
      if (!fs.existsSync(gitDir)) {
        this.fail(testName, '.git directory not found');
        return;
      }

      const gitignorePath = path.join(process.cwd(), '.gitignore');
      if (!fs.existsSync(gitignorePath)) {
        this.warn(testName, '.gitignore not found');
      } else {
        this.pass(testName);
      }
    } catch (err) {
      this.fail(testName, err.message);
    }
  }

  /**
   * Test file structure
   */
  testFileStructure() {
    const testName = 'file structure validation';
    try {
      const requiredDirs = [
        '.github',
        '.github/workflows',
        'public',
        'src'
      ];

      const requiredFiles = [
        'package.json',
        '.github/workflows/ci.yml',
        'server.js'
      ];

      const missingDirs = requiredDirs.filter(d => !fs.existsSync(d));
      const missingFiles = requiredFiles.filter(f => !fs.existsSync(f));

      if (missingDirs.length > 0 || missingFiles.length > 0) {
        this.fail(testName, `Missing: ${[...missingDirs, ...missingFiles].join(', ')}`);
        return;
      }

      this.pass(testName);
    } catch (err) {
      this.fail(testName, err.message);
    }
  }

  /**
   * Test Node version
   */
  testNodeVersion() {
    const testName = 'Node.js version';
    try {
      const version = process.version;
      const majorVersion = parseInt(version.substring(1));

      if (majorVersion >= 14) {
        this.pass(testName, `Node ${version}`);
      } else {
        this.fail(testName, `Node version too old: ${version}, need 14+`);
      }
    } catch (err) {
      this.fail(testName, err.message);
    }
  }

  /**
   * Test health system exists
   */
  testHealthSystem() {
    const testName = 'DevOps health system';
    try {
      if (!fs.existsSync('devops-health-system.js')) {
        this.fail(testName, 'devops-health-system.js not found');
        return;
      }

      const content = fs.readFileSync('devops-health-system.js', 'utf8');
      if (!content.includes('class DevOpsHealthSystem')) {
        this.fail(testName, 'DevOpsHealthSystem class not found');
        return;
      }

      const requiredMethods = [
        'checkPipelineHealth',
        'validatePackageJson',
        'validateWorkflows',
        'validateEnvironmentVars'
      ];

      const missingMethods = requiredMethods.filter(m => !content.includes(m));
      if (missingMethods.length > 0) {
        this.warn(testName, `Missing methods: ${missingMethods.join(', ')}`);
      } else {
        this.pass(testName);
      }
    } catch (err) {
      this.fail(testName, err.message);
    }
  }

  /**
   * Test maintenance coordinator
   */
  testMaintenanceCoordinator() {
    const testName = 'pipeline maintenance coordinator';
    try {
      if (!fs.existsSync('pipeline-maintenance-coordinator.js')) {
        this.fail(testName, 'pipeline-maintenance-coordinator.js not found');
        return;
      }

      const content = fs.readFileSync('pipeline-maintenance-coordinator.js', 'utf8');
      if (!content.includes('class PipelineMaintenanceCoordinator')) {
        this.fail(testName, 'PipelineMaintenanceCoordinator class not found');
        return;
      }

      const requiredMethods = [
        'runMaintenanceCycle',
        'validateDependencies',
        'validateWorkflows',
        'setupAgentCoordination'
      ];

      const missingMethods = requiredMethods.filter(m => !content.includes(m));
      if (missingMethods.length > 0) {
        this.warn(testName, `Missing methods: ${missingMethods.join(', ')}`);
      } else {
        this.pass(testName);
      }
    } catch (err) {
      this.fail(testName, err.message);
    }
  }

  /**
   * Test agent integration
   */
  testAgentIntegration() {
    const testName = 'agent integration setup';
    try {
      const coordDir = '.agent-coordination';
      if (!fs.existsSync(coordDir)) {
        this.warn(testName, '.agent-coordination directory will be created at runtime');
      } else {
        const manifest = path.join(coordDir, 'manifest.json');
        const readiness = path.join(coordDir, 'readiness.json');

        if (!fs.existsSync(manifest) || !fs.existsSync(readiness)) {
          this.warn(testName, 'Coordination files not yet created (normal before pipeline)');
        } else {
          this.pass(testName);
        }
      }
    } catch (err) {
      this.fail(testName, err.message);
    }
  }

  /**
   * Test SRE Agent imports
   */
  testSREAgentImports() {
    const testName = 'SRE Agent imports';
    try {
      const content = fs.readFileSync('agentic_sre_engineer.js', 'utf8');

      const requiredImports = [
        'DevOpsHealthSystem',
        'ErrorRecoveryHandler',
        'error-recovery-handler'
      ];

      const missingImports = requiredImports.filter(i => !content.includes(i));
      if (missingImports.length > 0) {
        this.fail(testName, `Missing imports: ${missingImports.join(', ')}`);
        return;
      }

      if (content.includes('const DevOpsHealthSystem = require')) {
        this.pass(testName);
      } else {
        this.fail(testName, 'DevOpsHealthSystem not properly imported');
      }
    } catch (err) {
      this.fail(testName, err.message);
    }
  }

  /**
   * Test Fullstack Agent imports
   */
  testFullstackAgentImports() {
    const testName = 'Fullstack Agent imports';
    try {
      const content = fs.readFileSync('fullstack-agent.js', 'utf8');

      const requiredImports = [
        'DevOpsHealthSystem',
        'devops-health-system'
      ];

      const missingImports = requiredImports.filter(i => !content.includes(i));
      if (missingImports.length > 0) {
        this.fail(testName, `Missing imports: ${missingImports.join(', ')}`);
        return;
      }

      this.pass(testName);
    } catch (err) {
      this.fail(testName, err.message);
    }
  }

  /**
   * Test error recovery integration
   */
  testErrorRecoveryIntegration() {
    const testName = 'error recovery integration';
    try {
      const files = [
        'agentic_sre_engineer.js',
        'fullstack-agent.js',
        'error-recovery-handler.js'
      ];

      let integrated = 0;
      for (const file of files) {
        const content = fs.readFileSync(file, 'utf8');
        if (content.includes('ErrorRecoveryHandler')) {
          integrated++;
        }
      }

      if (integrated >= 2) {
        this.pass(testName);
      } else {
        this.warn(testName, `Only ${integrated} agents have error recovery integrated`);
      }
    } catch (err) {
      this.fail(testName, err.message);
    }
  }

  /**
   * Test job dependencies
   */
  testJobDependencies() {
    const testName = 'workflow job dependencies';
    try {
      const content = fs.readFileSync('.github/workflows/ci.yml', 'utf8');

      // Check for basic dependencies
      if (content.includes('needs:')) {
        // Check for circular dependencies
        if (content.match(/needs:.*needs:/)) {
          this.warn(testName, 'Potential circular dependencies detected');
        } else {
          this.pass(testName);
        }
      } else {
        this.warn(testName, 'No job dependencies defined');
      }
    } catch (err) {
      this.fail(testName, err.message);
    }
  }

  /**
   * Test timeout configuration
   */
  testTimeoutConfiguration() {
    const testName = 'timeout configuration';
    try {
      const content = fs.readFileSync('.github/workflows/ci.yml', 'utf8');
      const lines = content.split('\n');

      let timeoutCount = 0;
      let jobCount = 0;

      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes('runs-on:')) {
          jobCount++;
          // Check if next few lines have timeout
          let hasTimeout = false;
          for (let j = i - 3; j <= i + 3; j++) {
            if (j >= 0 && j < lines.length && lines[j].includes('timeout-minutes:')) {
              hasTimeout = true;
              timeoutCount++;
              break;
            }
          }
        }
      }

      if (timeoutCount >= 8) {
        this.pass(testName, `${timeoutCount}/${jobCount} jobs have timeouts`);
      } else {
        this.warn(testName, `Only ${timeoutCount}/${jobCount} jobs have timeouts`);
      }
    } catch (err) {
      this.fail(testName, err.message);
    }
  }

  /**
   * Test cache configuration
   */
  testCacheConfiguration() {
    const testName = 'npm cache configuration';
    try {
      const content = fs.readFileSync('.github/workflows/ci.yml', 'utf8');

      if (content.includes("cache: 'npm'")) {
        const cacheCount = (content.match(/cache:\s*['"]npm['"]/g) || []).length;
        if (cacheCount >= 3) {
          this.pass(testName, `npm cache configured in ${cacheCount} jobs`);
        } else {
          this.warn(testName, `npm cache only in ${cacheCount} jobs, expected 3+`);
        }
      } else {
        this.fail(testName, 'npm cache not configured');
      }
    } catch (err) {
      this.fail(testName, err.message);
    }
  }

  /**
   * Record pass
   */
  pass(name, details = '') {
    this.passed++;
    const msg = details ? ` (${details})` : '';
    console.log(`✅ PASS: ${name}${msg}`);
  }

  /**
   * Record fail
   */
  fail(name, reason = '') {
    this.failed++;
    const msg = reason ? `: ${reason}` : '';
    console.log(`❌ FAIL: ${name}${msg}`);
  }

  /**
   * Record warning
   */
  warn(name, reason = '') {
    this.warnings++;
    const msg = reason ? `: ${reason}` : '';
    console.log(`⚠️  WARN: ${name}${msg}`);
  }

  /**
   * Generate final report
   */
  generateReport() {
    const total = this.passed + this.failed + this.warnings;
    const passRate = this.passed / (total || 1);
    const status = this.failed === 0 ? '🟢 PASSED' : '🔴 FAILED';

    console.log('\n╔════════════════════════════════════════════════════════════╗');
    console.log('║                    VERIFICATION REPORT                     ║');
    console.log('╚════════════════════════════════════════════════════════════╝\n');

    console.log(`Status: ${status}`);
    console.log(`Passed:  ${this.passed}/${total}`);
    console.log(`Failed:  ${this.failed}/${total}`);
    console.log(`Warnings: ${this.warnings}/${total}`);
    console.log(`Pass Rate: ${(passRate * 100).toFixed(1)}%\n`);

    if (this.failed === 0 && this.warnings === 0) {
      console.log('✅ All systems ready for deployment!\n');
      return 0;
    } else if (this.failed === 0) {
      console.log('⚠️  Some warnings detected. Review and proceed with caution.\n');
      return 1;
    } else {
      console.log('❌ Critical failures detected. Fix before deployment.\n');
      return 2;
    }
  }
}

/**
 * Main execution
 */
async function main() {
  try {
    const verification = new PipelineVerification();
    await verification.runAllTests();
    const exitCode = verification.generateReport();
    process.exit(exitCode);
  } catch (err) {
    console.error(`\nFatal error: ${err.message}\n`);
    process.exit(2);
  }
}

module.exports = PipelineVerification;

if (require.main === module) {
  main();
}
