#!/usr/bin/env node

/**
 * Agent Recovery & Auto-Fix System
 * 
 * When agents fail, this system automatically repairs them
 * and ensures the pipeline can continue
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const GitHubWorkflowValidator = require('./github-workflow-validator');

class AgentRecoverySystem {
  constructor() {
    this.recoveryDir = '.agent-recovery';
    this.logFile = path.join(this.recoveryDir, 'recovery-log.json');
    this.recoveryStrategies = [
      'fix-imports',
      'add-error-handling',
      'validate-exports',
      'restore-backup',
      'regenerate-from-template'
    ];
    
    this.ensureRecoveryDir();
  }

  /**
   * Ensure recovery directory exists
   */
  ensureRecoveryDir() {
    if (!fs.existsSync(this.recoveryDir)) {
      fs.mkdirSync(this.recoveryDir, { recursive: true });
    }
  }

  /**
   * Detect agent failures
   */
  detectAgentFailures() {
    console.log('\n🔍 Detecting agent failures...\n');
    
    const agents = [
      'fullstack-agent.js',
      'agentic_sre_engineer.js',
      'compliance-agent.js',
      'sdet-agent.js',
      'qa-agent.js'
    ];

    const failures = [];

    for (const agent of agents) {
      if (!fs.existsSync(agent)) {
        failures.push({
          agent,
          type: 'missing-file',
          severity: 'critical'
        });
        continue;
      }

      const issues = this.analyzeAgent(agent);
      if (issues.length > 0) {
        failures.push({
          agent,
          type: 'functional-issues',
          severity: issues.some(i => i.severity === 'critical') ? 'critical' : 'warning',
          issues
        });
      }
    }

    return failures;
  }

  /**
   * Analyze an agent for issues
   */
  analyzeAgent(agentFile) {
    const issues = [];
    const content = fs.readFileSync(agentFile, 'utf8');

    // Check for syntax errors
    try {
      new Function(content);
    } catch (err) {
      issues.push({
        type: 'syntax-error',
        message: err.message,
        severity: 'critical'
      });
    }

    // Check for missing error handling
    if (!/try\s*\{[\s\S]*?\}\s*catch/.test(content)) {
      issues.push({
        type: 'missing-error-handling',
        message: 'No try-catch blocks found',
        severity: 'warning'
      });
    }

    // Check for proper exports
    if (!content.includes('module.exports') && 
        !content.includes('export default') &&
        !content.includes('if (require.main === module)')) {
      issues.push({
        type: 'missing-exports',
        message: 'No module exports or main entry point',
        severity: 'warning'
      });
    }

    // Check for missing dependencies
    if (agentFile.includes('sre') && !content.includes('GITHUB_TOKEN')) {
      issues.push({
        type: 'missing-config',
        message: 'SRE agent missing GITHUB_TOKEN reference',
        severity: 'warning'
      });
    }

    return issues;
  }

  /**
   * Attempt recovery for a failed agent
   */
  async recoverAgent(agentName) {
    console.log(`\n${'═'.repeat(50)}`);
    console.log(`🔧 RECOVERING AGENT: ${agentName}`);
    console.log(`${'═'.repeat(50)}\n`);

    const recoveryLog = {
      agent: agentName,
      timestamp: new Date().toISOString(),
      strategies: [],
      success: false
    };

    try {
      // Strategy 1: Fix imports
      const strategy1 = await this.fixImports(agentName);
      recoveryLog.strategies.push(strategy1);

      // Strategy 2: Add error handling
      const strategy2 = await this.addErrorHandling(agentName);
      recoveryLog.strategies.push(strategy2);

      // Strategy 3: Validate exports
      const strategy3 = await this.validateExports(agentName);
      recoveryLog.strategies.push(strategy3);

      // Strategy 4: Test agent functionality
      const strategy4 = await this.testAgentFunctionality(agentName);
      recoveryLog.strategies.push(strategy4);

      // Check if recovery succeeded
      const successfulStrategies = recoveryLog.strategies.filter(s => s.success).length;
      recoveryLog.success = successfulStrategies >= 2;

      if (recoveryLog.success) {
        console.log(`\n✅ Recovery successful for ${agentName}`);
      } else {
        console.log(`\n⚠️  Recovery partially successful for ${agentName}`);
      }

    } catch (error) {
      console.log(`\n❌ Recovery failed for ${agentName}: ${error.message}`);
      recoveryLog.error = error.message;
    }

    this.logRecoveryAttempt(recoveryLog);
    return recoveryLog.success;
  }

  /**
   * Strategy 1: Fix imports
   */
  async fixImports(agentFile) {
    const strategy = {
      name: 'fix-imports',
      success: false,
      changes: []
    };

    try {
      let content = fs.readFileSync(agentFile, 'utf8');
      const originalContent = content;

      // Add missing fs import
      if (!content.includes("require('fs')") && !content.includes('require("fs")')) {
        const lines = content.split('\n');
        let insertIndex = 0;
        
        // Find first require statement
        for (let i = 0; i < lines.length; i++) {
          if (lines[i].includes('require(')) {
            insertIndex = i;
            break;
          }
        }
        
        if (insertIndex > 0) {
          lines.splice(insertIndex, 0, "const fs = require('fs');");
          content = lines.join('\n');
          strategy.changes.push('Added fs import');
        }
      }

      // Add missing path import
      if (!content.includes("require('path')") && !content.includes('require("path")')) {
        if (content.includes('path.') || content.includes('__dirname')) {
          const lines = content.split('\n');
          let insertIndex = 0;
          
          for (let i = 0; i < lines.length; i++) {
            if (lines[i].includes('require(')) {
              insertIndex = i + 1;
              break;
            }
          }
          
          lines.splice(insertIndex, 0, "const path = require('path');");
          content = lines.join('\n');
          strategy.changes.push('Added path import');
        }
      }

      if (content !== originalContent) {
        fs.writeFileSync(agentFile, content);
        strategy.success = true;
        console.log(`  ✅ Fixed imports: ${strategy.changes.join(', ')}`);
      } else {
        console.log('  ℹ️  No import changes needed');
        strategy.success = true;
      }

    } catch (err) {
      console.log(`  ❌ Error fixing imports: ${err.message}`);
    }

    return strategy;
  }

  /**
   * Strategy 2: Add error handling
   */
  async addErrorHandling(agentFile) {
    const strategy = {
      name: 'add-error-handling',
      success: false,
      changes: []
    };

    try {
      let content = fs.readFileSync(agentFile, 'utf8');
      const originalContent = content;

      // Check if main/async function has try-catch
      if (content.includes('async function') && !content.includes('try {')) {
        // Add try-catch wrapper
        content = content.replace(
          /async function (\w+)\(\) \{/,
          'async function $1() {\n  try {'
        );
        
        // Find the matching closing brace and add catch
        const lines = content.split('\n');
        let braceCount = 0;
        let foundFunction = false;
        let functionEndLine = -1;

        for (let i = 0; i < lines.length; i++) {
          if (lines[i].includes('async function') && lines[i].includes('try {')) {
            foundFunction = true;
          }

          if (foundFunction) {
            braceCount += (lines[i].match(/{/g) || []).length;
            braceCount -= (lines[i].match(/}/g) || []).length;

            if (braceCount === 0 && i > 0) {
              functionEndLine = i;
              break;
            }
          }
        }

        if (functionEndLine > 0) {
          lines.splice(functionEndLine, 0, 
            `  } catch (error) {`,
            `    console.error('Agent error:', error.message);`,
            `    process.exit(1);`,
            `  }`
          );
          content = lines.join('\n');
          strategy.changes.push('Added try-catch to async function');
          strategy.success = true;
        }
      }

      if (content !== originalContent) {
        fs.writeFileSync(agentFile, content);
        console.log(`  ✅ Added error handling: ${strategy.changes.join(', ')}`);
      } else {
        console.log('  ℹ️  Error handling already present or not needed');
        strategy.success = true;
      }

    } catch (err) {
      console.log(`  ❌ Error adding error handling: ${err.message}`);
    }

    return strategy;
  }

  /**
   * Strategy 3: Validate exports
   */
  async validateExports(agentFile) {
    const strategy = {
      name: 'validate-exports',
      success: false,
      changes: []
    };

    try {
      let content = fs.readFileSync(agentFile, 'utf8');
      const originalContent = content;

      // Check if has main entry point
      const hasMainEntry = content.includes('if (require.main === module)');
      const hasExports = content.includes('module.exports');

      if (!hasMainEntry && !hasExports) {
        // Add main entry point at end of file
        if (!content.endsWith('\n')) {
          content += '\n';
        }

        // Find the main function or create one
        if (content.includes('async function agenticSRELoop')) {
          content += `\nif (require.main === module) {
  agenticSRELoop().catch(console.error);
}
`;
          strategy.changes.push('Added main entry point for agenticSRELoop');
          strategy.success = true;
        } else if (content.includes('async function')) {
          // Generic async function
          const match = content.match(/async function (\w+)\(/);
          if (match) {
            content += `\nif (require.main === module) {
  ${match[1]}().catch(console.error);
}
`;
            strategy.changes.push(`Added main entry point for ${match[1]}`);
            strategy.success = true;
          }
        }
      } else {
        console.log('  ℹ️  Module already has exports or main entry');
        strategy.success = true;
      }

      if (content !== originalContent) {
        fs.writeFileSync(agentFile, content);
        console.log(`  ✅ Validated exports: ${strategy.changes.join(', ')}`);
      }

    } catch (err) {
      console.log(`  ❌ Error validating exports: ${err.message}`);
    }

    return strategy;
  }

  /**
   * Strategy 4: Test agent functionality
   */
  async testAgentFunctionality(agentFile) {
    const strategy = {
      name: 'test-functionality',
      success: false,
      message: ''
    };

    try {
      // Syntax check
      const content = fs.readFileSync(agentFile, 'utf8');
      
      try {
        new Function(content);
        strategy.success = true;
        strategy.message = 'Syntax is valid';
        console.log(`  ✅ Agent syntax is valid`);
      } catch (syntaxErr) {
        strategy.message = syntaxErr.message;
        console.log(`  ❌ Syntax error: ${syntaxErr.message}`);
      }

    } catch (err) {
      console.log(`  ❌ Error testing functionality: ${err.message}`);
      strategy.message = err.message;
    }

    return strategy;
  }

  /**
   * Log recovery attempt
   */
  logRecoveryAttempt(recoveryLog) {
    let logs = [];
    
    if (fs.existsSync(this.logFile)) {
      try {
        logs = JSON.parse(fs.readFileSync(this.logFile, 'utf8'));
      } catch (err) {
        logs = [];
      }
    }

    logs.push(recoveryLog);
    
    // Keep only last 100 logs
    if (logs.length > 100) {
      logs = logs.slice(-100);
    }

    fs.writeFileSync(this.logFile, JSON.stringify(logs, null, 2));
  }

  /**
   * Run complete recovery sequence
   */
  async runRecoverySequence() {
    console.log('\n╔════════════════════════════════════════╗');
    console.log('║    🔧 AGENT RECOVERY SEQUENCE         ║');
    console.log('╚════════════════════════════════════════╝');

    // Detect failures
    const failures = this.detectAgentFailures();

    if (failures.length === 0) {
      console.log('\n✅ No agent failures detected');
      console.log('All agents are functioning normally\n');
      return true;
    }

    console.log(`\n⚠️  Detected ${failures.length} agent failure(s):`);
    failures.forEach(f => {
      console.log(`  • ${f.agent}: ${f.type} (${f.severity})`);
      if (f.issues) {
        f.issues.forEach(i => console.log(`    - ${i.type}: ${i.message}`));
      }
    });

    // Attempt recovery
    const criticalFailures = failures.filter(f => f.severity === 'critical');
    const recoveryResults = [];

    for (const failure of criticalFailures) {
      const success = await this.recoverAgent(failure.agent);
      recoveryResults.push({ agent: failure.agent, success });
    }

    // Summary
    console.log('\n╔════════════════════════════════════════╗');
    console.log('║       📊 RECOVERY SUMMARY             ║');
    console.log('╚════════════════════════════════════════╝\n');

    const successCount = recoveryResults.filter(r => r.success).length;
    const totalCount = recoveryResults.length;

    console.log(`Recovery attempts: ${successCount}/${totalCount}`);
    recoveryResults.forEach(r => {
      const icon = r.success ? '✅' : '❌';
      console.log(`  ${icon} ${r.agent}`);
    });

    const allSuccessful = successCount === totalCount;
    console.log(`\n${allSuccessful ? '✅' : '⚠️'} Recovery ${allSuccessful ? 'successful' : 'partially successful'}\n`);

    return allSuccessful;
  }

  /**
   * Diagnose and auto-fix GitHub API parameter mismatches
   * This prevents 404 errors from sending undefined workflow inputs
   */
  async diagnoseGitHubWorkflowIssue(token, owner, repo, workflowFilename, inputsSent) {
    console.log(`\n🔍 GitHub Workflow Diagnostic`);
    console.log(`Repository: ${owner}/${repo}`);
    console.log(`Workflow: ${workflowFilename}`);
    console.log(`Inputs being sent:`, Object.keys(inputsSent));

    try {
      const validator = new GitHubWorkflowValidator(token, owner, repo);
      const validation = await validator.validateInputs(workflowFilename, inputsSent);

      if (!validation.valid) {
        console.error('❌ ISSUE DETECTED: Invalid workflow inputs');
        console.error('Errors:', validation.errors);
        
        // Auto-fix: provide filtered inputs
        const filteredInputs = {};
        for (const input of validation.expectedInputs) {
          if (inputsSent.hasOwnProperty(input)) {
            filteredInputs[input] = inputsSent[input];
          }
        }

        console.log('\n🔧 AUTO-FIX: Filtering invalid inputs');
        console.log('Expected inputs:', validation.expectedInputs);
        console.log('Filtered inputs to send:', filteredInputs);
        
        return {
          valid: false,
          errors: validation.errors,
          filteredInputs: filteredInputs,
          recommendation: 'Use filteredInputs instead of original inputs'
        };
      } else {
        console.log('✅ All inputs are valid');
        if (validation.warnings.length > 0) {
          console.log('⚠️ Warnings:', validation.warnings);
        }
        return { valid: true, warnings: validation.warnings };
      }
    } catch (error) {
      console.error('Error during diagnostic:', error.message);
      return { valid: false, error: error.message };
    }
  }
}

// Run if executed directly
if (require.main === module) {
  const recovery = new AgentRecoverySystem();
  recovery.runRecoverySequence()
    .then(success => process.exit(success ? 0 : 1))
    .catch(err => {
      console.error('Fatal error:', err);
      process.exit(1);
    });
}

module.exports = AgentRecoverySystem;
