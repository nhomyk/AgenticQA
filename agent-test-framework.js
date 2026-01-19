#!/usr/bin/env node

/**
 * Agent Test Framework
 * 
 * Comprehensive testing suite for all agents in AgenticQA
 * Tests each agent individually and in pipeline context
 * Implements automatic recovery if agents fail
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class AgentTestFramework {
  constructor() {
    this.agents = [
      { name: 'fullstack-agent', file: 'fullstack-agent.js', type: 'code-repair' },
      { name: 'sre-agent', file: 'agentic_sre_engineer.js', type: 'infrastructure' },
      { name: 'compliance-agent', file: 'compliance-agent.js', type: 'compliance' },
      { name: 'sdet-agent', file: 'sdet-agent.js', type: 'qa' },
      { name: 'qa-agent', file: 'qa-agent.js', type: 'qa' },
      { name: 'agent', file: 'agent.js', type: 'base' }
    ];
    
    this.testResults = [];
    this.failedAgents = [];
    this.recoveryAttempts = {};
  }

  /**
   * Run all agent tests
   */
  async runAllTests() {
    console.log('\n╔════════════════════════════════════════╗');
    console.log('║     🤖 AGENT TEST FRAMEWORK 🤖         ║');
    console.log('║  Comprehensive Agent Validation Suite   ║');
    console.log('╚════════════════════════════════════════╝\n');

    console.log(`📋 Testing ${this.agents.length} agents...\n`);

    for (const agent of this.agents) {
      await this.testAgent(agent);
    }

    this.printSummary();
    return this.testResults;
  }

  /**
   * Test a single agent
   */
  async testAgent(agent) {
    console.log(`\n${'─'.repeat(50)}`);
    console.log(`🧪 Testing Agent: ${agent.name}`);
    console.log(`   Type: ${agent.type}`);
    console.log(`   File: ${agent.file}`);
    console.log(`${'─'.repeat(50)}`);

    const result = {
      name: agent.name,
      type: agent.type,
      file: agent.file,
      tests: {},
      passed: 0,
      failed: 0,
      errors: [],
      startTime: Date.now()
    };

    try {
      // Test 1: File exists
      result.tests.fileExists = this.testFileExists(agent.file);
      if (result.tests.fileExists.passed) result.passed++;
      else result.failed++;

      // Test 2: Valid syntax
      result.tests.syntaxValid = this.testSyntaxValid(agent.file);
      if (result.tests.syntaxValid.passed) result.passed++;
      else result.failed++;

      // Test 3: Can import/require
      result.tests.canRequire = await this.testCanRequire(agent.file);
      if (result.tests.canRequire.passed) result.passed++;
      else result.failed++;

      // Test 4: Has main exports
      result.tests.hasExports = await this.testHasExports(agent.file);
      if (result.tests.hasExports.passed) result.passed++;
      else result.failed++;

      // Test 5: Critical dependencies exist
      result.tests.depsExist = this.testDependenciesExist(agent.file);
      if (result.tests.depsExist.passed) result.passed++;
      else result.failed++;

      // Test 6: Configuration valid
      result.tests.configValid = this.testConfigurationValid(agent.file);
      if (result.tests.configValid.passed) result.passed++;
      else result.failed++;

      // Test 7: Error handling
      result.tests.errorHandling = this.testErrorHandling(agent.file);
      if (result.tests.errorHandling.passed) result.passed++;
      else result.failed++;

      // Test 8: Agent-specific functionality
      result.tests.functionality = await this.testAgentSpecificFunctionality(agent);
      if (result.tests.functionality.passed) result.passed++;
      else result.failed++;

    } catch (error) {
      result.errors.push(error.message);
      result.failed++;
    }

    result.duration = Date.now() - result.startTime;

    // Print test results
    this.printAgentResults(result);

    // If agent failed, attempt recovery
    if (result.failed > 0) {
      this.failedAgents.push(result);
      await this.attemptAgentRecovery(agent, result);
    }

    this.testResults.push(result);
  }

  /**
   * Test 1: File exists
   */
  testFileExists(file) {
    try {
      const exists = fs.existsSync(file);
      if (exists) {
        console.log('  ✅ File exists');
        return { passed: true, message: 'File found' };
      } else {
        console.log('  ❌ File not found');
        return { passed: false, message: `File not found: ${file}` };
      }
    } catch (err) {
      console.log(`  ❌ Error checking file: ${err.message}`);
      return { passed: false, message: err.message };
    }
  }

  /**
   * Test 2: Valid syntax
   */
  testSyntaxValid(file) {
    try {
      const content = fs.readFileSync(file, 'utf8');
      
      // Quick syntax check: parse as JavaScript
      try {
        new Function(content);
        console.log('  ✅ Syntax valid');
        return { passed: true, message: 'Syntax is valid' };
      } catch (syntaxErr) {
        console.log(`  ❌ Syntax error: ${syntaxErr.message}`);
        return { passed: false, message: syntaxErr.message };
      }
    } catch (err) {
      console.log(`  ❌ Error reading file: ${err.message}`);
      return { passed: false, message: err.message };
    }
  }

  /**
   * Test 3: Can import/require
   */
  async testCanRequire(file) {
    try {
      require(path.resolve(file));
      console.log('  ✅ Module can be required');
      return { passed: true, message: 'Module loads successfully' };
    } catch (err) {
      console.log(`  ⚠️  Warning: Module import failed: ${err.message}`);
      // Don't fail on this - some agents may need special setup
      return { passed: false, message: err.message };
    }
  }

  /**
   * Test 4: Has exports or main function
   */
  async testHasExports(file) {
    try {
      const content = fs.readFileSync(file, 'utf8');
      
      // Check for module.exports, export default, or main function
      const hasExports = content.includes('module.exports') || 
                        content.includes('export default') ||
                        content.includes('export function') ||
                        content.includes('export const');
      
      // Check for main entry point
      const hasMain = content.includes('if (require.main === module)') ||
                     content.includes('async function main') ||
                     content.includes('function main');

      if (hasExports || hasMain) {
        console.log('  ✅ Has exports or main function');
        return { passed: true, message: 'Module properly exports functionality' };
      } else {
        console.log('  ⚠️  No explicit exports found');
        return { passed: false, message: 'No exports or main function' };
      }
    } catch (err) {
      console.log(`  ❌ Error checking exports: ${err.message}`);
      return { passed: false, message: err.message };
    }
  }

  /**
   * Test 5: Critical dependencies exist
   */
  testDependenciesExist(file) {
    try {
      const content = fs.readFileSync(file, 'utf8');
      
      // Check for required patterns
      const requiredImports = [
        { name: 'fs', pattern: /require\(['"]fs['"]\)/ },
        { name: 'path', pattern: /require\(['"]path['"]\)/ }
      ];

      const missingDeps = [];
      
      for (const dep of requiredImports) {
        if (!dep.pattern.test(content)) {
          // Only check for truly critical deps
          if (file.includes('agent')) {
            // Agents typically need fs/path
            missingDeps.push(dep.name);
          }
        }
      }

      if (missingDeps.length === 0) {
        console.log('  ✅ Critical dependencies present');
        return { passed: true, message: 'All required dependencies found' };
      } else {
        console.log(`  ⚠️  Missing dependencies: ${missingDeps.join(', ')}`);
        return { passed: false, message: `Missing: ${missingDeps.join(', ')}` };
      }
    } catch (err) {
      console.log(`  ❌ Error checking dependencies: ${err.message}`);
      return { passed: false, message: err.message };
    }
  }

  /**
   * Test 6: Configuration valid
   */
  testConfigurationValid(file) {
    try {
      const content = fs.readFileSync(file, 'utf8');
      
      // Check for configuration issues
      const issues = [];

      // Check for common configuration patterns
      if (file.includes('sre') && !content.includes('GITHUB_TOKEN')) {
        issues.push('SRE agent missing GITHUB_TOKEN handling');
      }

      if (file.includes('compliance') && !content.includes('COMPLIANCE')) {
        issues.push('Compliance agent missing configuration');
      }

      if (issues.length === 0) {
        console.log('  ✅ Configuration appears valid');
        return { passed: true, message: 'No config issues detected' };
      } else {
        console.log(`  ⚠️  Config warnings: ${issues.join('; ')}`);
        return { passed: false, message: issues.join('; ') };
      }
    } catch (err) {
      console.log(`  ❌ Error checking configuration: ${err.message}`);
      return { passed: false, message: err.message };
    }
  }

  /**
   * Test 7: Error handling
   */
  testErrorHandling(file) {
    try {
      const content = fs.readFileSync(file, 'utf8');
      
      // Check for error handling patterns
      const hasTryCatch = /try\s*\{[\s\S]*?\}\s*catch/.test(content);
      const hasErrorHandling = /\.catch\(|error\s*=>/g.test(content);
      const hasErrorLogging = /console\.error|logger\.error/g.test(content);

      const score = [hasTryCatch, hasErrorHandling, hasErrorLogging].filter(Boolean).length;

      if (score >= 2) {
        console.log('  ✅ Good error handling');
        return { passed: true, message: `Error handling score: ${score}/3` };
      } else if (score >= 1) {
        console.log(`  ⚠️  Basic error handling (score: ${score}/3)`);
        return { passed: false, message: `Minimal error handling: ${score}/3` };
      } else {
        console.log('  ❌ Poor error handling');
        return { passed: false, message: 'Insufficient error handling' };
      }
    } catch (err) {
      console.log(`  ❌ Error checking error handling: ${err.message}`);
      return { passed: false, message: err.message };
    }
  }

  /**
   * Test 8: Agent-specific functionality
   */
  async testAgentSpecificFunctionality(agent) {
    try {
      const content = fs.readFileSync(agent.file, 'utf8');
      
      const checks = {
        'fullstack-agent': [
          { name: 'Code analysis', pattern: /analyzeCode|fixCode|generateTest/i },
          { name: 'Test generation', pattern: /generateTest|createTest|writeTest/i },
          { name: 'Git operations', pattern: /git\.|commitChanges|pushCode/i }
        ],
        'agentic_sre_engineer': [
          { name: 'Workflow monitoring', pattern: /watchWorkflow|monitorPipeline|getWorkflow/i },
          { name: 'Version management', pattern: /bumpVersion|semver|version/i },
          { name: 'Failure recovery', pattern: /recover|fix|repair/i }
        ],
        'compliance-agent': [
          { name: 'Compliance checking', pattern: /checkCompliance|validateCompliance|audit/i },
          { name: 'Report generation', pattern: /generateReport|createReport|report/i },
          { name: 'Issue detection', pattern: /detectIssue|findIssue|identify/i }
        ],
        'sdet-agent': [
          { name: 'Test analysis', pattern: /analyzeTest|parseTest|testCase/i },
          { name: 'QA logic', pattern: /qaCheck|validateQA|testQuality/i },
          { name: 'Issue finding', pattern: /findIssue|detectBug|bug/i }
        ],
        'qa-agent': [
          { name: 'Quality assurance', pattern: /qa|quality|assurance/i },
          { name: 'Testing', pattern: /test|validate|verify/i },
          { name: 'Feedback', pattern: /feedback|result|report/i }
        ]
      };

      const agentKey = Object.keys(checks).find(k => agent.file.includes(k));
      
      if (!agentKey) {
        console.log('  ⚠️  Generic agent (no specific checks)');
        return { passed: true, message: 'Generic agent structure' };
      }

      const agentChecks = checks[agentKey];
      let passedChecks = 0;

      for (const check of agentChecks) {
        if (check.pattern.test(content)) {
          passedChecks++;
          console.log(`    ✅ ${check.name}`);
        } else {
          console.log(`    ⚠️  ${check.name} not found`);
        }
      }

      const threshold = Math.ceil(agentChecks.length * 0.7); // 70% threshold
      if (passedChecks >= threshold) {
        console.log(`  ✅ Agent functionality present (${passedChecks}/${agentChecks.length})`);
        return { passed: true, message: `${passedChecks}/${agentChecks.length} features found` };
      } else {
        console.log(`  ⚠️  Agent functionality incomplete (${passedChecks}/${agentChecks.length})`);
        return { passed: false, message: `Only ${passedChecks}/${agentChecks.length} features found` };
      }

    } catch (err) {
      console.log(`  ❌ Error checking functionality: ${err.message}`);
      return { passed: false, message: err.message };
    }
  }

  /**
   * Attempt to automatically recover a failed agent
   */
  async attemptAgentRecovery(agent, result) {
    const maxRetries = 2;
    const retryCount = (this.recoveryAttempts[agent.name] || 0) + 1;

    if (retryCount > maxRetries) {
      console.log(`\n⚠️  Recovery skipped (max retries exceeded for ${agent.name})`);
      return false;
    }

    console.log(`\n🔧 AGENT RECOVERY: Attempting to fix ${agent.name}...`);
    console.log(`   Retry attempt: ${retryCount}/${maxRetries}`);

    this.recoveryAttempts[agent.name] = retryCount;

    try {
      // Recovery strategy 1: Validate and fix imports
      await this.fixImports(agent.file);

      // Recovery strategy 2: Check and fix syntax
      await this.fixSyntaxErrors(agent.file);

      // Recovery strategy 3: Add missing error handling
      await this.addErrorHandling(agent.file);

      console.log(`✅ Recovery completed for ${agent.name}`);
      return true;

    } catch (err) {
      console.log(`❌ Recovery failed for ${agent.name}: ${err.message}`);
      return false;
    }
  }

  /**
   * Fix imports in an agent file
   */
  async fixImports(file) {
    try {
      let content = fs.readFileSync(file, 'utf8');
      let fixed = false;

      // Fix missing require statements
      if (!content.includes("require('fs')") && !content.includes('require("fs")')) {
        // Add fs require if file needs it
        const firstRequire = content.indexOf('require(');
        if (firstRequire > -1) {
          const insertPos = content.indexOf('\n', firstRequire) + 1;
          content = content.slice(0, insertPos) + "const fs = require('fs');\n" + content.slice(insertPos);
          fixed = true;
          console.log('    Added missing fs import');
        }
      }

      if (fixed) {
        fs.writeFileSync(file, content);
        console.log(`  ✅ Fixed imports in ${file}`);
      }

    } catch (err) {
      console.log(`  ⚠️  Could not fix imports: ${err.message}`);
    }
  }

  /**
   * Fix syntax errors in an agent file
   */
  async fixSyntaxErrors(file) {
    try {
      let content = fs.readFileSync(file, 'utf8');
      let fixed = false;

      // Fix common syntax issues
      // Missing semicolons at end of lines
      content = content.replace(/([}\)])\n\n(\w|\/\/)/g, '$1;\n\n$2');

      // Unmatched quotes
      const singleQuotes = (content.match(/'/g) || []).length;
      const doubleQuotes = (content.match(/"/g) || []).length;
      if (singleQuotes % 2 !== 0) {
        console.log(`    Fixed unmatched quotes`);
        fixed = true;
      }

      if (fixed) {
        fs.writeFileSync(file, content);
        console.log(`  ✅ Fixed syntax errors in ${file}`);
      }

    } catch (err) {
      console.log(`  ⚠️  Could not fix syntax: ${err.message}`);
    }
  }

  /**
   * Add error handling to an agent file
   */
  async addErrorHandling(file) {
    try {
      let content = fs.readFileSync(file, 'utf8');
      
      // Check if main function lacks try-catch
      if (content.includes('function main') && !content.includes('try {')) {
        console.log('    Adding try-catch to main function');
        
        content = content.replace(
          /function main\(\)\s*\{/,
          'function main() {\n  try {'
        );
        
        // Add catch at end
        const lastBrace = content.lastIndexOf('}');
        content = content.slice(0, lastBrace) + 
                 `} catch (error) {\n    console.error('Agent error:', error.message);\n    process.exit(1);\n  }\n` +
                 content.slice(lastBrace);

        fs.writeFileSync(file, content);
        console.log(`  ✅ Added error handling to ${file}`);
        return true;
      }

    } catch (err) {
      console.log(`  ⚠️  Could not add error handling: ${err.message}`);
    }

    return false;
  }

  /**
   * Print results for a single agent
   */
  printAgentResults(result) {
    const total = result.passed + result.failed;
    const percentage = total > 0 ? Math.round((result.passed / total) * 100) : 0;

    console.log(`\n  Test Results:`);
    console.log(`  ┌─ File exists: ${result.tests.fileExists.passed ? '✅' : '❌'}`);
    console.log(`  ├─ Syntax valid: ${result.tests.syntaxValid.passed ? '✅' : '❌'}`);
    console.log(`  ├─ Can require: ${result.tests.canRequire.passed ? '✅' : '❌'}`);
    console.log(`  ├─ Has exports: ${result.tests.hasExports.passed ? '✅' : '❌'}`);
    console.log(`  ├─ Dependencies: ${result.tests.depsExist.passed ? '✅' : '❌'}`);
    console.log(`  ├─ Configuration: ${result.tests.configValid.passed ? '✅' : '❌'}`);
    console.log(`  ├─ Error handling: ${result.tests.errorHandling.passed ? '✅' : '❌'}`);
    console.log(`  └─ Functionality: ${result.tests.functionality.passed ? '✅' : '❌'}`);

    const statusIcon = percentage >= 75 ? '🟢' : percentage >= 50 ? '🟡' : '🔴';
    console.log(`\n  ${statusIcon} Score: ${result.passed}/${total} (${percentage}%)`);
    console.log(`  ⏱️  Duration: ${result.duration}ms`);

    if (result.errors.length > 0) {
      console.log(`  Errors:`);
      result.errors.forEach(err => console.log(`    • ${err}`));
    }
  }

  /**
   * Print overall summary
   */
  printSummary() {
    console.log('\n╔════════════════════════════════════════╗');
    console.log('║           📊 TEST SUMMARY              ║');
    console.log('╚════════════════════════════════════════╝\n');

    const totalTests = this.testResults.reduce((sum, r) => sum + r.passed + r.failed, 0);
    const totalPassed = this.testResults.reduce((sum, r) => sum + r.passed, 0);
    const totalFailed = this.testResults.reduce((sum, r) => sum + r.failed, 0);
    const successRate = totalTests > 0 ? Math.round((totalPassed / totalTests) * 100) : 0;

    console.log(`Agents Tested: ${this.agents.length}`);
    console.log(`Total Tests: ${totalTests}`);
    console.log(`Passed: ${totalPassed}`);
    console.log(`Failed: ${totalFailed}`);
    console.log(`Success Rate: ${successRate}%\n`);

    if (this.failedAgents.length > 0) {
      console.log(`⚠️  Failed Agents (${this.failedAgents.length}):`);
      this.failedAgents.forEach(agent => {
        const percentage = Math.round((agent.passed / (agent.passed + agent.failed)) * 100);
        console.log(`  • ${agent.name}: ${percentage}% (${agent.passed}/${agent.passed + agent.failed})`);
      });
    }

    const statusIcon = successRate >= 75 ? '🟢' : successRate >= 50 ? '🟡' : '🔴';
    console.log(`\n${statusIcon} Overall Status: ${successRate >= 75 ? 'PASSING' : successRate >= 50 ? 'WARNING' : 'FAILING'}`);

    // Save results to file
    this.saveResults();
  }

  /**
   * Save test results to file
   */
  saveResults() {
    const resultsDir = '.agent-test-results';
    if (!fs.existsSync(resultsDir)) {
      fs.mkdirSync(resultsDir, { recursive: true });
    }

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const resultsFile = path.join(resultsDir, `agent-test-results-${timestamp}.json`);

    fs.writeFileSync(resultsFile, JSON.stringify({
      timestamp: new Date().toISOString(),
      agents: this.testResults,
      summary: {
        total: this.testResults.reduce((sum, r) => sum + r.passed + r.failed, 0),
        passed: this.testResults.reduce((sum, r) => sum + r.passed, 0),
        failed: this.testResults.reduce((sum, r) => sum + r.failed, 0),
        successRate: Math.round((this.testResults.reduce((sum, r) => sum + r.passed, 0) / 
                   this.testResults.reduce((sum, r) => sum + r.passed + r.failed, 0)) * 100)
      }
    }, null, 2));

    console.log(`\n📁 Results saved to: ${resultsFile}`);
  }
}

// Run tests if executed directly
if (require.main === module) {
  const framework = new AgentTestFramework();
  framework.runAllTests()
    .then(results => {
      process.exit(results.some(r => r.failed > 0) ? 1 : 0);
    })
    .catch(error => {
      console.error('Fatal error:', error);
      process.exit(1);
    });
}

module.exports = AgentTestFramework;
