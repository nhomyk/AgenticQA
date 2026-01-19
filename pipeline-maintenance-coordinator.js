#!/usr/bin/env node

/**
 * Pipeline Maintenance & Health Monitor
 * 
 * This script runs during CI/CD pipeline to ensure pipeline health
 * and coordinates maintenance tasks across agents.
 * 
 * Used by: GitHub Actions CI/CD Pipeline
 * Called in: Phase -1 (Pipeline Rescue) and Phase 0 (Linting Fix)
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const DevOpsHealthSystem = require('./devops-health-system');

class PipelineMaintenanceCoordinator {
  constructor() {
    this.healthSystem = new DevOpsHealthSystem();
    this.startTime = Date.now();
    this.maintenanceLog = [];
  }

  /**
   * Run full pipeline maintenance cycle
   */
  async runMaintenanceCycle() {
    console.log('\n╔════════════════════════════════════════════════════════════╗');
    console.log('║          🔧 PIPELINE MAINTENANCE COORDINATOR 🔧             ║');
    console.log('║             DevOps Health & Agent Coordination              ║');
    console.log('╚════════════════════════════════════════════════════════════╝\n');

    try {
      // Step 1: Health Check
      console.log('STEP 1: Pipeline Health Diagnostic...\n');
      const health = await this.healthSystem.checkPipelineHealth();
      this.maintenanceLog.push('✅ Health check complete');

      // Step 2: Auto-repairs if needed
      if (health.status === 'critical') {
        console.log('\nSTEP 2: Applying Critical Fixes...\n');
        const fixed = await this.healthSystem.applyAutoFixes();
        this.maintenanceLog.push(`✅ Applied ${fixed ? 'auto-fixes' : 'no fixes needed'}`);
      }

      // Step 3: Dependency validation
      console.log('\nSTEP 3: Dependency Validation...\n');
      const depsValid = this.validateDependencies();
      this.maintenanceLog.push(`✅ Dependency check: ${depsValid ? 'passed' : 'failed'}`);

      // Step 4: Workflow validation  
      console.log('\nSTEP 4: Workflow Validation...\n');
      const workflowValid = this.validateWorkflows();
      this.maintenanceLog.push(`✅ Workflow check: ${workflowValid ? 'passed' : 'failed'}`);

      // Step 5: Agent coordination setup
      console.log('\nSTEP 5: Agent Coordination Setup...\n');
      this.setupAgentCoordination();
      this.maintenanceLog.push('✅ Agent coordination configured');

      // Step 6: Generate maintenance report
      console.log('\nSTEP 6: Generating Maintenance Report...\n');
      this.generateReport(health);

      // Final status
      const elapsed = Math.round((Date.now() - this.startTime) / 1000);
      console.log(`\n✅ Pipeline maintenance completed in ${elapsed}s\n`);

      return { success: true, elapsed, health };
    } catch (err) {
      console.error(`\n❌ Maintenance cycle error: ${err.message}\n`);
      return { success: false, error: err.message };
    }
  }

  /**
   * Validate dependencies are available
   */
  validateDependencies() {
    console.log('  Checking dependencies...');

    try {
      // Check critical commands
      const commands = [
        { name: 'node', cmd: 'node --version' },
        { name: 'npm', cmd: 'npm --version' },
        { name: 'git', cmd: 'git --version' }
      ];

      let allValid = true;
      for (const { name, cmd } of commands) {
        try {
          const version = execSync(cmd, { encoding: 'utf8', stdio: 'pipe' }).trim();
          console.log(`    ✅ ${name}: ${version.split('\n')[0]}`);
        } catch (err) {
          console.log(`    ❌ ${name}: NOT AVAILABLE`);
          allValid = false;
        }
      }

      // Check critical files
      const files = [
        { name: 'package.json', path: 'package.json' },
        { name: '.github/workflows/ci.yml', path: '.github/workflows/ci.yml' },
        { name: 'node_modules', path: 'node_modules' }
      ];

      for (const { name, path: filePath } of files) {
        if (fs.existsSync(filePath)) {
          console.log(`    ✅ ${name}: present`);
        } else if (name === 'node_modules') {
          console.log(`    ⚠️  ${name}: not installed (will be installed by npm ci)`);
        } else {
          console.log(`    ❌ ${name}: MISSING`);
          allValid = false;
        }
      }

      return allValid;
    } catch (err) {
      console.log(`    ❌ Error checking dependencies: ${err.message}`);
      return false;
    }
  }

  /**
   * Validate workflow files
   */
  validateWorkflows() {
    console.log('  Checking workflow files...');

    try {
      const workflowDir = path.join(process.cwd(), '.github', 'workflows');
      if (!fs.existsSync(workflowDir)) {
        console.log(`    ❌ Workflow directory not found: ${workflowDir}`);
        return false;
      }

      const files = fs.readdirSync(workflowDir).filter(f => f.endsWith('.yml') || f.endsWith('.yaml'));
      if (files.length === 0) {
        console.log('    ❌ No workflow files found');
        return false;
      }

      console.log(`    ✅ Found ${files.length} workflow file(s)`);

      let allValid = true;
      for (const file of files) {
        const filePath = path.join(workflowDir, file);
        const content = fs.readFileSync(filePath, 'utf8');

        const hasJobs = content.includes('jobs:');
        const hasOn = content.includes('on:');
        const hasTimeouts = content.includes('timeout-minutes:');

        if (hasJobs && hasOn) {
          console.log(`    ✅ ${file}: valid structure`);
        } else {
          console.log(`    ⚠️  ${file}: missing required fields`);
          allValid = false;
        }

        if (!hasTimeouts) {
          console.log(`    ⚠️  ${file}: missing timeout-minutes (potential hangs)`);
        }
      }

      return allValid;
    } catch (err) {
      console.log(`    ❌ Error validating workflows: ${err.message}`);
      return false;
    }
  }

  /**
   * Setup agent coordination
   */
  setupAgentCoordination() {
    console.log('  Setting up agent coordination...');

    try {
      // Create coordination directory
      const coordDir = '.agent-coordination';
      if (!fs.existsSync(coordDir)) {
        fs.mkdirSync(coordDir, { recursive: true });
        console.log(`    ✅ Coordination directory created`);
      }

      // Create coordination manifest
      const manifest = {
        timestamp: new Date().toISOString(),
        agents: {
          sre: {
            role: 'DevOps & Infrastructure',
            responsibilities: ['Pipeline health', 'Performance monitoring', 'Issue detection'],
            capabilities: ['auto-fix', 'health-check', 'recovery-coordination']
          },
          fullstack: {
            role: 'Code Quality & Compliance',
            responsibilities: ['Test fixing', 'Code generation', 'Compliance',],
            capabilities: ['auto-fix', 'test-generation', 'pattern-learning']
          },
          sdet: {
            role: 'Quality Assurance',
            responsibilities: ['Test analysis', 'Coverage analysis', 'Test design'],
            capabilities: ['analysis', 'test-design', 'coverage-reporting']
          },
          compliance: {
            role: 'Compliance & Security',
            responsibilities: ['Compliance scanning', 'Security review', 'Audit trail'],
            capabilities: ['scanning', 'audit', 'reporting']
          }
        },
        coordination_points: [
          'Health status file: .devops-health/status.json',
          'Recovery guides: .agent-recovery-guide.json',
          'Metrics: .devops-health/metrics.json',
          'Alerts: .devops-health/alerts.json'
        ],
        communication_flow: {
          '1': 'SRE Agent: Detect issue → Log to recovery system',
          '2': 'Error Recovery: Analyze → Generate recovery guide',
          '3': 'Fullstack Agent: Read guide → Apply learned fixes',
          '4': 'All Agents: Monitor health → Contribute metrics',
          '5': 'Loop: Continuous improvement → Better success rates'
        }
      };

      fs.writeFileSync(
        path.join(coordDir, 'manifest.json'),
        JSON.stringify(manifest, null, 2)
      );

      console.log('    ✅ Agent coordination manifest created');

      // Create agent readiness file
      const readiness = {
        timestamp: new Date().toISOString(),
        agents_ready: {
          sre: true,
          fullstack: true,
          sdet: true,
          compliance: true
        },
        pipeline_ready: true,
        maintenance_cycle: 'pre-pipeline'
      };

      fs.writeFileSync(
        path.join(coordDir, 'readiness.json'),
        JSON.stringify(readiness, null, 2)
      );

      console.log('    ✅ Agent readiness status initialized');
      return true;
    } catch (err) {
      console.log(`    ❌ Error setting up coordination: ${err.message}`);
      return false;
    }
  }

  /**
   * Generate maintenance report
   */
  generateReport(health) {
    console.log('  Generating report...');

    const report = {
      timestamp: new Date().toISOString(),
      pipeline_status: health.status,
      issues_found: health.issues.length,
      checks_performed: Object.keys(health.checks).length,
      recommendations: health.recommendations.length,
      maintenance_log: this.maintenanceLog,
      next_steps: this.generateNextSteps(health)
    };

    // Save report
    const reportPath = path.join('.devops-health', 'maintenance-report.json');
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));

    console.log(`    ✅ Report saved to: ${reportPath}`);

    // Print summary
    console.log('\n  📊 MAINTENANCE SUMMARY:');
    console.log(`    Pipeline Status: ${health.status.toUpperCase()}`);
    console.log(`    Issues Found: ${health.issues.length}`);
    console.log(`    Auto-Fixes Applied: ${report.maintenance_log.filter(l => l.includes('Applied')).length}`);
    console.log(`    Next Steps: ${report.next_steps.length}`);

    return report;
  }

  /**
   * Generate next steps based on health status
   */
  generateNextSteps(health) {
    const steps = [];

    if (health.status === 'critical') {
      steps.push('Critical issues detected - manual review recommended');
      steps.push('Check .devops-health/status.json for details');
    }

    if (health.issues.length > 0) {
      steps.push(`${health.issues.length} issue(s) found - review and address`);
    }

    if (health.recommendations.length > 0) {
      steps.push(`${health.recommendations.length} recommendations generated`);
      steps.push('Run recommended fixes before proceeding with tests');
    }

    if (health.status === 'healthy') {
      steps.push('Pipeline is healthy - proceed with CI/CD');
      steps.push('All agents ready for coordinated execution');
    }

    return steps;
  }
}

/**
 * Main execution
 */
async function main() {
  const coordinator = new PipelineMaintenanceCoordinator();
  
  const result = await coordinator.runMaintenanceCycle();

  // Exit with appropriate code
  process.exit(result.success ? 0 : 1);
}

module.exports = PipelineMaintenanceCoordinator;

if (require.main === module) {
  main().catch(err => {
    console.error(`\n❌ Fatal error: ${err.message}\n`);
    process.exit(1);
  });
}
