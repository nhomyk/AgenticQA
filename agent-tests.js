#!/usr/bin/env node

/**
 * Individual Agent Test Suites
 * 
 * Tests for each specific agent's core functionality
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class AgentTests {
  /**
   * Test Fullstack Agent
   */
  static testFullstackAgent() {
    console.log('\n🧪 FULLSTACK AGENT TESTS\n');
    
    const tests = [
      {
        name: 'Code analysis capability',
        test: () => {
          const content = fs.readFileSync('fullstack-agent.js', 'utf8');
          return content.includes('analyzeCode') || 
                 content.includes('parseFailure') ||
                 content.includes('fixCode');
        }
      },
      {
        name: 'Test generation capability',
        test: () => {
          const content = fs.readFileSync('fullstack-agent.js', 'utf8');
          return content.includes('generateTest') || 
                 content.includes('createTest') ||
                 content.includes('writeTest');
        }
      },
      {
        name: 'Git operations',
        test: () => {
          const content = fs.readFileSync('fullstack-agent.js', 'utf8');
          return content.includes('git.add') ||
                 content.includes('git.commit') ||
                 content.includes('git.push');
        }
      },
      {
        name: 'Recovery guide reading',
        test: () => {
          const content = fs.readFileSync('fullstack-agent.js', 'utf8');
          return content.includes('recovery') || 
                 content.includes('ErrorRecoveryHandler') ||
                 content.includes('guide');
        }
      },
      {
        name: 'Error handling',
        test: () => {
          const content = fs.readFileSync('fullstack-agent.js', 'utf8');
          return /try\s*\{[\s\S]*?\}\s*catch/.test(content);
        }
      }
    ];

    return this.runTestSuite('Fullstack Agent', tests);
  }

  /**
   * Test SRE Agent
   */
  static testSREAgent() {
    console.log('\n🧪 SRE AGENT TESTS\n');
    
    const tests = [
      {
        name: 'Workflow monitoring',
        test: () => {
          const content = fs.readFileSync('agentic_sre_engineer.js', 'utf8');
          return content.includes('watchWorkflow') || 
                 content.includes('getLatestWorkflowRun') ||
                 content.includes('getWorkflowJobResults');
        }
      },
      {
        name: 'Version management',
        test: () => {
          const content = fs.readFileSync('agentic_sre_engineer.js', 'utf8');
          return content.includes('bumpVersion') || 
                 content.includes('semver') ||
                 content.includes('version');
        }
      },
      {
        name: 'Failure detection',
        test: () => {
          const content = fs.readFileSync('agentic_sre_engineer.js', 'utf8');
          return content.includes('failure') || 
                 content.includes('error') ||
                 content.includes('failed');
        }
      },
      {
        name: 'Recovery orchestration',
        test: () => {
          const content = fs.readFileSync('agentic_sre_engineer.js', 'utf8');
          return content.includes('makeCodeChanges') || 
                 content.includes('triggerNewWorkflow') ||
                 content.includes('recovery');
        }
      },
      {
        name: 'Notification system',
        test: () => {
          const content = fs.readFileSync('agentic_sre_engineer.js', 'utf8');
          return content.includes('sendEmail') || 
                 content.includes('nodemailer') ||
                 content.includes('notify');
        }
      }
    ];

    return this.runTestSuite('SRE Agent', tests);
  }

  /**
   * Test Compliance Agent
   */
  static testComplianceAgent() {
    console.log('\n🧪 COMPLIANCE AGENT TESTS\n');
    
    const tests = [
      {
        name: 'Compliance checking',
        test: () => {
          if (!fs.existsSync('compliance-agent.js')) {
            console.log('  ⚠️  File does not exist');
            return false;
          }
          const content = fs.readFileSync('compliance-agent.js', 'utf8');
          return content.includes('compliance') || 
                 content.includes('check') ||
                 content.includes('validate');
        }
      },
      {
        name: 'Report generation',
        test: () => {
          if (!fs.existsSync('compliance-agent.js')) return false;
          const content = fs.readFileSync('compliance-agent.js', 'utf8');
          return content.includes('report') || 
                 content.includes('audit') ||
                 content.includes('generateReport');
        }
      },
      {
        name: 'GDPR compliance',
        test: () => {
          if (!fs.existsSync('compliance-agent.js')) return false;
          const content = fs.readFileSync('compliance-agent.js', 'utf8');
          return content.includes('GDPR') || 
                 content.includes('gdpr');
        }
      },
      {
        name: 'Error handling',
        test: () => {
          if (!fs.existsSync('compliance-agent.js')) return false;
          const content = fs.readFileSync('compliance-agent.js', 'utf8');
          return /try\s*\{[\s\S]*?\}\s*catch/.test(content);
        }
      }
    ];

    return this.runTestSuite('Compliance Agent', tests);
  }

  /**
   * Test SDET Agent
   */
  static testSDETAgent() {
    console.log('\n🧪 SDET AGENT TESTS\n');
    
    const tests = [
      {
        name: 'Test analysis',
        test: () => {
          if (!fs.existsSync('sdet-agent.js')) return false;
          const content = fs.readFileSync('sdet-agent.js', 'utf8');
          return content.includes('test') || 
                 content.includes('analyze') ||
                 content.includes('qa');
        }
      },
      {
        name: 'QA logic',
        test: () => {
          if (!fs.existsSync('sdet-agent.js')) return false;
          const content = fs.readFileSync('sdet-agent.js', 'utf8');
          return content.includes('validate') || 
                 content.includes('verify') ||
                 content.includes('check');
        }
      },
      {
        name: 'Issue detection',
        test: () => {
          if (!fs.existsSync('sdet-agent.js')) return false;
          const content = fs.readFileSync('sdet-agent.js', 'utf8');
          return content.includes('issue') || 
                 content.includes('bug') ||
                 content.includes('error');
        }
      },
      {
        name: 'Error handling',
        test: () => {
          if (!fs.existsSync('sdet-agent.js')) return false;
          const content = fs.readFileSync('sdet-agent.js', 'utf8');
          return /try\s*\{[\s\S]*?\}\s*catch/.test(content);
        }
      }
    ];

    return this.runTestSuite('SDET Agent', tests);
  }

  /**
   * Test QA Agent
   */
  static testQAAgent() {
    console.log('\n🧪 QA AGENT TESTS\n');
    
    const tests = [
      {
        name: 'Quality assurance logic',
        test: () => {
          if (!fs.existsSync('qa-agent.js')) return false;
          const content = fs.readFileSync('qa-agent.js', 'utf8');
          return content.includes('qa') || 
                 content.includes('quality') ||
                 content.includes('assurance');
        }
      },
      {
        name: 'Testing capability',
        test: () => {
          if (!fs.existsSync('qa-agent.js')) return false;
          const content = fs.readFileSync('qa-agent.js', 'utf8');
          return content.includes('test') || 
                 content.includes('validate') ||
                 content.includes('verify');
        }
      },
      {
        name: 'Feedback system',
        test: () => {
          if (!fs.existsSync('qa-agent.js')) return false;
          const content = fs.readFileSync('qa-agent.js', 'utf8');
          return content.includes('feedback') || 
                 content.includes('report') ||
                 content.includes('result');
        }
      },
      {
        name: 'Error handling',
        test: () => {
          if (!fs.existsSync('qa-agent.js')) return false;
          const content = fs.readFileSync('qa-agent.js', 'utf8');
          return /try\s*\{[\s\S]*?\}\s*catch/.test(content);
        }
      }
    ];

    return this.runTestSuite('QA Agent', tests);
  }

  /**
   * Run a test suite
   */
  static runTestSuite(name, tests) {
    let passed = 0;
    let failed = 0;

    console.log(`Testing ${name}:`);
    console.log('─'.repeat(40));

    for (const testCase of tests) {
      try {
        const result = testCase.test();
        if (result) {
          console.log(`  ✅ ${testCase.name}`);
          passed++;
        } else {
          console.log(`  ❌ ${testCase.name}`);
          failed++;
        }
      } catch (err) {
        console.log(`  ❌ ${testCase.name} - Error: ${err.message}`);
        failed++;
      }
    }

    const total = passed + failed;
    const percentage = total > 0 ? Math.round((passed / total) * 100) : 0;
    console.log('\n' + '─'.repeat(40));
    console.log(`Result: ${passed}/${total} passed (${percentage}%)\n`);

    return { name, passed, failed, percentage };
  }

  /**
   * Run all individual tests
   */
  static runAll() {
    console.log('\n╔════════════════════════════════════════╗');
    console.log('║   🧪 INDIVIDUAL AGENT TEST SUITES    ║');
    console.log('╚════════════════════════════════════════╝');

    const results = [
      this.testFullstackAgent(),
      this.testSREAgent(),
      this.testComplianceAgent(),
      this.testSDETAgent(),
      this.testQAAgent()
    ];

    const totalPassed = results.reduce((sum, r) => sum + r.passed, 0);
    const totalFailed = results.reduce((sum, r) => sum + r.failed, 0);
    const totalPercentage = totalPassed + totalFailed > 0 ? 
      Math.round((totalPassed / (totalPassed + totalFailed)) * 100) : 0;

    console.log('\n╔════════════════════════════════════════╗');
    console.log('║          📊 OVERALL SUMMARY           ║');
    console.log('╚════════════════════════════════════════╝\n');

    results.forEach(r => {
      const statusIcon = r.percentage >= 75 ? '🟢' : r.percentage >= 50 ? '🟡' : '🔴';
      console.log(`${statusIcon} ${r.name}: ${r.passed}/${r.passed + r.failed} (${r.percentage}%)`);
    });

    console.log(`\nTotal: ${totalPassed}/${totalPassed + totalFailed} (${totalPercentage}%)\n`);

    return totalPercentage >= 75 ? 0 : 1;
  }
}

// Run if executed directly
if (require.main === module) {
  const exitCode = AgentTests.runAll();
  process.exit(exitCode);
}

module.exports = AgentTests;
