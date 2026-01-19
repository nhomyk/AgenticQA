#!/usr/bin/env node

/**
 * DevOps Pipeline Health & Maintenance System
 * 
 * This system monitors and maintains the AgenticQA CI/CD pipeline health.
 * Agents use this to detect, diagnose, and heal pipeline issues.
 * 
 * Features:
 * - Pipeline health monitoring
 * - Automatic issue detection and categorization
 * - Self-healing mechanisms
 * - Performance optimization
 * - Resource management
 * - Workflow repair automation
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class DevOpsHealthSystem {
  constructor() {
    this.logDir = '.devops-health';
    this.statusFile = path.join(this.logDir, 'status.json');
    this.metricsFile = path.join(this.logDir, 'metrics.json');
    this.alertsFile = path.join(this.logDir, 'alerts.json');
    this.initializeSystem();
  }

  /**
   * Initialize the health monitoring system
   */
  initializeSystem() {
    if (!fs.existsSync(this.logDir)) {
      fs.mkdirSync(this.logDir, { recursive: true });
    }

    if (!fs.existsSync(this.statusFile)) {
      fs.writeFileSync(this.statusFile, JSON.stringify({
        initialized: new Date().toISOString(),
        pipeline_status: 'initializing',
        agent_status: {},
        job_health: {},
        last_check: null
      }, null, 2));
    }

    if (!fs.existsSync(this.metricsFile)) {
      fs.writeFileSync(this.metricsFile, JSON.stringify({
        total_runs: 0,
        successful_runs: 0,
        failed_runs: 0,
        average_duration_seconds: 0,
        job_timings: {},
        error_patterns: {}
      }, null, 2));
    }

    if (!fs.existsSync(this.alertsFile)) {
      fs.writeFileSync(this.alertsFile, JSON.stringify({
        active_alerts: [],
        resolved_alerts: [],
        alert_history: []
      }, null, 2));
    }
  }

  /**
   * CORE DEVOPS FUNCTION: Check pipeline health
   */
  async checkPipelineHealth() {
    console.log('\n🏥 === DEVOPS HEALTH CHECK ===\n');

    const health = {
      timestamp: new Date().toISOString(),
      checks: {},
      issues: [],
      recommendations: [],
      status: 'healthy'
    };

    // Check 1: Package.json validity
    console.log('📦 Checking package.json...');
    const pkgCheck = this.validatePackageJson();
    health.checks.package_json = pkgCheck;
    if (!pkgCheck.valid) {
      health.status = 'degraded';
      health.issues.push(...pkgCheck.errors);
    }

    // Check 2: Workflow file validity
    console.log('🔄 Checking workflow files...');
    const workflowCheck = this.validateWorkflows();
    health.checks.workflows = workflowCheck;
    if (!workflowCheck.valid) {
      health.status = 'critical';
      health.issues.push(...workflowCheck.errors);
    }

    // Check 3: Dependencies
    console.log('📚 Checking dependencies...');
    const depsCheck = this.checkDependencies();
    health.checks.dependencies = depsCheck;
    if (!depsCheck.valid) {
      health.status = 'degraded';
      health.issues.push(...depsCheck.errors);
    }

    // Check 4: Node modules cache
    console.log('💾 Checking node_modules cache...');
    const cacheCheck = this.checkCacheStatus();
    health.checks.cache = cacheCheck;

    // Check 5: Git configuration
    console.log('🔐 Checking git configuration...');
    const gitCheck = this.validateGitConfig();
    health.checks.git_config = gitCheck;
    if (!gitCheck.valid) {
      health.issues.push(...gitCheck.errors);
    }

    // Check 6: Environment variables
    console.log('🔑 Checking environment variables...');
    const envCheck = this.validateEnvironmentVars();
    health.checks.environment = envCheck;

    // Check 7: Docker configuration
    console.log('🐳 Checking Docker setup...');
    const dockerCheck = this.checkDockerSetup();
    health.checks.docker = dockerCheck;

    // Check 8: File permissions
    console.log('🔒 Checking file permissions...');
    const permCheck = this.checkFilePermissions();
    health.checks.file_permissions = permCheck;

    // Generate recommendations
    health.recommendations = this.generateRecommendations(health.issues);

    // Report status
    this.reportHealth(health);

    return health;
  }

  /**
   * Validate package.json structure and contents
   */
  validatePackageJson() {
    const result = { valid: true, errors: [], warnings: [] };

    try {
      const pkgPath = path.join(process.cwd(), 'package.json');
      if (!fs.existsSync(pkgPath)) {
        result.valid = false;
        result.errors.push('❌ package.json not found');
        return result;
      }

      const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));

      // Check version format
      if (!pkg.version || !/^\d+\.\d+\.\d+/.test(pkg.version)) {
        result.valid = false;
        result.errors.push(`❌ Invalid version format: "${pkg.version}". Expected semver (e.g., 0.9.1)`);
      }

      // Check required scripts
      const requiredScripts = ['start', 'test:jest', 'test:vitest', 'test:playwright'];
      for (const script of requiredScripts) {
        if (!pkg.scripts || !pkg.scripts[script]) {
          result.warnings.push(`⚠️  Missing script: "${script}"`);
        }
      }

      // Check dependencies
      if (!pkg.dependencies || Object.keys(pkg.dependencies).length === 0) {
        result.warnings.push('⚠️  No dependencies specified');
      }

      if (!pkg.devDependencies || Object.keys(pkg.devDependencies).length === 0) {
        result.warnings.push('⚠️  No devDependencies specified');
      }

      return result;
    } catch (err) {
      result.valid = false;
      result.errors.push(`❌ Failed to parse package.json: ${err.message}`);
      return result;
    }
  }

  /**
   * Validate workflow YAML files
   */
  validateWorkflows() {
    const result = { valid: true, errors: [], warnings: [], files_checked: 0 };

    try {
      const workflowDir = path.join(process.cwd(), '.github', 'workflows');
      if (!fs.existsSync(workflowDir)) {
        result.valid = false;
        result.errors.push('❌ .github/workflows directory not found');
        return result;
      }

      const files = fs.readdirSync(workflowDir).filter(f => f.endsWith('.yml') || f.endsWith('.yaml'));
      result.files_checked = files.length;

      if (files.length === 0) {
        result.valid = false;
        result.errors.push('❌ No workflow files found');
        return result;
      }

      for (const file of files) {
        const filePath = path.join(workflowDir, file);
        const content = fs.readFileSync(filePath, 'utf8');

        // Basic YAML validation
        if (!content.includes('jobs:') && !content.includes('on:')) {
          result.errors.push(`❌ Invalid workflow file: ${file}`);
          result.valid = false;
        }

        // Check for required fields
        if (!content.includes('runs-on:')) {
          result.warnings.push(`⚠️  ${file}: Missing 'runs-on' field`);
        }

        // Check for timeout settings
        if (!content.includes('timeout-minutes:')) {
          result.warnings.push(`⚠️  ${file}: Missing 'timeout-minutes' configuration`);
        }
      }

      if (result.valid) {
        result.warnings.push(`✅ ${files.length} workflow file(s) validated`);
      }

      return result;
    } catch (err) {
      result.valid = false;
      result.errors.push(`❌ Error validating workflows: ${err.message}`);
      return result;
    }
  }

  /**
   * Check dependencies installation
   */
  checkDependencies() {
    const result = { valid: true, errors: [], warnings: [], status: 'unknown' };

    try {
      // Check if npm ci was successful
      const packageLockPath = path.join(process.cwd(), 'package-lock.json');
      if (!fs.existsSync(packageLockPath)) {
        result.warnings.push('⚠️  package-lock.json not found - consider running npm ci');
        result.status = 'missing-lock';
      }

      // Check node_modules
      const nodeModulesPath = path.join(process.cwd(), 'node_modules');
      if (!fs.existsSync(nodeModulesPath)) {
        result.valid = false;
        result.errors.push('❌ node_modules not found - run npm ci');
        result.status = 'not-installed';
      } else {
        result.status = 'installed';
        result.warnings.push('✅ Dependencies appear to be installed');
      }

      return result;
    } catch (err) {
      result.valid = false;
      result.errors.push(`❌ Error checking dependencies: ${err.message}`);
      return result;
    }
  }

  /**
   * Check cache status
   */
  checkCacheStatus() {
    const result = { valid: true, cache_location: '', size_mb: 0 };

    try {
      const nodeModulesPath = path.join(process.cwd(), 'node_modules');
      if (fs.existsSync(nodeModulesPath)) {
        const stats = this.getDirectorySize(nodeModulesPath);
        result.cache_location = nodeModulesPath;
        result.size_mb = Math.round(stats / 1024 / 1024);
        result.summary = `✅ Cache: ${result.size_mb}MB`;
      } else {
        result.valid = false;
        result.summary = '❌ Cache not found';
      }
      return result;
    } catch (err) {
      return { valid: false, error: err.message };
    }
  }

  /**
   * Validate git configuration
   */
  validateGitConfig() {
    const result = { valid: true, errors: [], warnings: [] };

    try {
      const gitDir = path.join(process.cwd(), '.git');
      if (!fs.existsSync(gitDir)) {
        result.valid = false;
        result.errors.push('❌ .git directory not found - not a git repository');
        return result;
      }

      // Check for .gitignore
      const gitignorePath = path.join(process.cwd(), '.gitignore');
      if (!fs.existsSync(gitignorePath)) {
        result.warnings.push('⚠️  .gitignore file not found');
      } else {
        result.warnings.push('✅ .gitignore present');
      }

      return result;
    } catch (err) {
      result.errors.push(`❌ Error validating git config: ${err.message}`);
      result.valid = false;
      return result;
    }
  }

  /**
   * Validate required environment variables
   */
  validateEnvironmentVars() {
    const result = { required: [], optional: [], missing: [], configured: [] };

    const required = ['GITHUB_TOKEN'];
    const optional = ['OPENAI_API_KEY', 'GH_PAT', 'NPM_TOKEN'];

    for (const key of required) {
      if (process.env[key]) {
        result.configured.push(`✅ ${key}`);
      } else {
        result.missing.push(`❌ ${key} (REQUIRED)`);
      }
    }

    for (const key of optional) {
      if (process.env[key]) {
        result.configured.push(`✅ ${key}`);
      } else {
        result.missing.push(`⚠️  ${key} (optional)`);
      }
    }

    return result;
  }

  /**
   * Check Docker setup
   */
  checkDockerSetup() {
    const result = { available: false, version: null, errors: [] };

    try {
      const version = execSync('docker --version', { encoding: 'utf8', stdio: 'pipe' });
      result.available = true;
      result.version = version.trim();
      result.summary = `✅ Docker available: ${result.version}`;
    } catch (err) {
      result.available = false;
      result.errors.push('⚠️  Docker not available or not in PATH');
      result.summary = '⚠️  Docker unavailable (optional)';
    }

    return result;
  }

  /**
   * Check file permissions
   */
  checkFilePermissions() {
    const result = { valid: true, files_checked: 0, issues: [] };

    try {
      const criticalFiles = [
        'package.json',
        '.github/workflows/ci.yml',
        'server.js'
      ];

      for (const file of criticalFiles) {
        const filePath = path.join(process.cwd(), file);
        if (fs.existsSync(filePath)) {
          result.files_checked++;
          try {
            fs.accessSync(filePath, fs.constants.R_OK);
          } catch (err) {
            result.valid = false;
            result.issues.push(`❌ Cannot read: ${file}`);
          }
        }
      }

      return result;
    } catch (err) {
      result.issues.push(`❌ Error checking permissions: ${err.message}`);
      result.valid = false;
      return result;
    }
  }

  /**
   * Generate recommendations based on issues
   */
  generateRecommendations(issues) {
    const recommendations = [];

    for (const issue of issues) {
      if (issue.includes('version')) {
        recommendations.push({
          severity: 'CRITICAL',
          issue: 'Invalid package version',
          fix: 'Update package.json version to valid semver (X.Y.Z)',
          command: 'npm version patch'
        });
      }

      if (issue.includes('node_modules')) {
        recommendations.push({
          severity: 'HIGH',
          issue: 'Dependencies not installed',
          fix: 'Install dependencies',
          command: 'npm ci'
        });
      }

      if (issue.includes('workflow')) {
        recommendations.push({
          severity: 'CRITICAL',
          issue: 'Invalid workflow files',
          fix: 'Validate and fix .github/workflows/*.yml files',
          command: 'node repair-workflow.js'
        });
      }

      if (issue.includes('git')) {
        recommendations.push({
          severity: 'HIGH',
          issue: 'Git configuration problem',
          fix: 'Initialize git repository',
          command: 'git init && git add . && git commit -m "initial"'
        });
      }
    }

    return recommendations;
  }

  /**
   * Report health status
   */
  reportHealth(health) {
    console.log('\n📊 === HEALTH CHECK RESULTS ===\n');
    console.log(`Status: ${health.status.toUpperCase()}`);
    console.log(`Time: ${health.timestamp}\n`);

    if (health.issues.length > 0) {
      console.log('⚠️  Issues Found:');
      health.issues.forEach(issue => console.log(`  ${issue}`));
      console.log();
    }

    console.log('✅ Checks Performed:');
    console.log(`  - Package validation: ${health.checks.package_json.valid ? '✅' : '❌'}`);
    console.log(`  - Workflow validation: ${health.checks.workflows.valid ? '✅' : '❌'}`);
    console.log(`  - Dependencies: ${health.checks.dependencies.valid ? '✅' : '❌'}`);
    console.log(`  - Git config: ${health.checks.git_config.valid ? '✅' : '❌'}`);
    console.log(`  - Docker: ${health.checks.docker.available ? '✅' : 'ℹ️  Optional'}`);

    if (health.recommendations.length > 0) {
      console.log('\n💡 Recommendations:');
      health.recommendations.forEach((rec, i) => {
        console.log(`  ${i + 1}. [${rec.severity}] ${rec.issue}`);
        console.log(`     Fix: ${rec.fix}`);
        console.log(`     Run: ${rec.command}\n`);
      });
    }

    // Save status file
    this.saveStatus(health);
  }

  /**
   * Save health status to file
   */
  saveStatus(health) {
    try {
      fs.writeFileSync(this.statusFile, JSON.stringify(health, null, 2));
      console.log(`\n💾 Health report saved to: ${this.statusFile}`);
    } catch (err) {
      console.error(`Error saving status: ${err.message}`);
    }
  }

  /**
   * Get directory size recursively
   */
  getDirectorySize(dirPath) {
    let size = 0;
    try {
      const files = fs.readdirSync(dirPath);
      for (const file of files) {
        const filePath = path.join(dirPath, file);
        const stat = fs.statSync(filePath);
        if (stat.isDirectory()) {
          size += this.getDirectorySize(filePath);
        } else {
          size += stat.size;
        }
      }
    } catch (err) {
      // Ignore permission errors
    }
    return size;
  }

  /**
   * Apply automatic fixes
   */
  async applyAutoFixes() {
    console.log('\n🔧 === AUTO-FIX MODE ===\n');

    const fixes = [
      { name: 'Fix package.json version', fn: () => this.fixPackageVersion() },
      { name: 'Install dependencies', fn: () => this.fixDependencies() },
      { name: 'Fix git configuration', fn: () => this.fixGitConfig() }
    ];

    let applied = 0;
    for (const fix of fixes) {
      try {
        console.log(`Applying: ${fix.name}...`);
        const result = fix.fn();
        if (result) {
          applied++;
          console.log(`✅ ${fix.name} applied\n`);
        }
      } catch (err) {
        console.log(`⚠️  ${fix.name} failed: ${err.message}\n`);
      }
    }

    console.log(`\n✅ Applied ${applied}/${fixes.length} auto-fixes`);
    return applied > 0;
  }

  /**
   * Fix package.json version
   */
  fixPackageVersion() {
    try {
      const pkgPath = path.join(process.cwd(), 'package.json');
      const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));

      if (!/^\d+\.\d+\.\d+/.test(pkg.version)) {
        pkg.version = '0.9.1';
        fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2));
        return true;
      }
      return false;
    } catch (err) {
      return false;
    }
  }

  /**
   * Fix dependencies
   */
  fixDependencies() {
    try {
      execSync('npm ci', { stdio: 'inherit' });
      return true;
    } catch (err) {
      return false;
    }
  }

  /**
   * Fix git configuration
   */
  fixGitConfig() {
    try {
      execSync('git init', { stdio: 'pipe' });
      return true;
    } catch (err) {
      return false;
    }
  }
}

/**
 * Main execution
 */
async function main() {
  const system = new DevOpsHealthSystem();

  const args = process.argv.slice(2);
  const command = args[0] || 'check';

  switch (command) {
    case 'check':
      await system.checkPipelineHealth();
      break;

    case 'auto-fix':
      await system.checkPipelineHealth();
      await system.applyAutoFixes();
      break;

    default:
      console.log('DevOps Health System - Usage:');
      console.log('  node devops-health-system.js check    # Check pipeline health');
      console.log('  node devops-health-system.js auto-fix  # Auto-fix issues');
  }
}

module.exports = DevOpsHealthSystem;

if (require.main === module) {
  main().catch(console.error);
}
