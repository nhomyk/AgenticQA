/**
 * Safeguards Usage Example
 * Demonstrates how to integrate safeguards into your agent workflow
 */

const SafeguardPipeline = require('./pipeline');
const safeguardsConfig = require('./config');

// Initialize safeguards with custom config
const safeguards = new SafeguardPipeline({
  enableGatekeeper: true,
  enableRollback: true,
  enableAudit: true,
  gatekeeper: safeguardsConfig.gatekeeper,
  rollback: safeguardsConfig.rollback,
  audit: safeguardsConfig.audit
});

/**
 * Example 1: Simple agent change validation
 */
async function exampleValidateChanges() {
  console.log('\n=== Example 1: Validate Agent Changes ===\n');

  const changes = [
    {
      filePath: 'src/utils/helpers.js',
      type: 'UPDATE',
      linesAdded: 15,
      linesRemoved: 5
    },
    {
      filePath: 'src/tests/helpers.test.js',
      type: 'CREATE',
      linesAdded: 50
    }
  ];

  const agent = {
    id: 'SDET-001',
    name: 'SDET Agent',
    type: 'SDET',
    successRate: 0.92,
    confidenceScore: 0.88,
    version: '3.1.0'
  };

  const result = await safeguards.processAgentChanges(changes, agent);
  console.log('\nResult:', JSON.stringify(result, null, 2));
}

/**
 * Example 2: Detect blocked file modifications
 */
async function exampleBlockedFiles() {
  console.log('\n=== Example 2: Detect Blocked File Modifications ===\n');

  const changes = [
    {
      filePath: 'src/utils/helpers.js',
      type: 'UPDATE'
    },
    {
      filePath: 'package.json', // ❌ Blocked!
      type: 'UPDATE'
    }
  ];

  const agent = {
    id: 'SDET-001',
    name: 'SDET Agent',
    type: 'SDET',
    successRate: 0.92,
    confidenceScore: 0.88
  };

  const result = await safeguards.processAgentChanges(changes, agent);
  console.log('\nValidation Result:');
  console.log(`Passed: ${result.validation.passed}`);
  console.log(`Reason: ${result.validation.reason}`);
  console.log(`Violations: ${result.validation.violations.map(v => v.message).join('\n  ')}`);
}

/**
 * Example 3: Too many changes
 */
async function exampleTooManyChanges() {
  console.log('\n=== Example 3: Detect Too Many Changes ===\n');

  const changes = [];
  for (let i = 0; i < 75; i++) {
    changes.push({
      filePath: `src/file${i}.js`,
      type: 'CREATE'
    });
  }

  const agent = {
    id: 'SRE-001',
    name: 'SRE Agent',
    type: 'SRE',
    successRate: 0.88,
    confidenceScore: 0.85
  };

  const result = await safeguards.processAgentChanges(changes, agent);
  console.log('\nValidation Result:');
  console.log(`Passed: ${result.validation.passed}`);
  console.log(`Reason: ${result.validation.reason}`);
}

/**
 * Example 4: View safeguard status
 */
function exampleStatus() {
  console.log('\n=== Example 4: Safeguard Status ===\n');

  const status = safeguards.getStatus();
  console.log(JSON.stringify(status, null, 2));
}

/**
 * Example 5: Generate compliance report
 */
function exampleComplianceReport() {
  console.log('\n=== Example 5: Compliance Report ===\n');

  const startDate = new Date();
  startDate.setDate(startDate.getDate() - 7); // Last 7 days

  const endDate = new Date();

  const report = safeguards.generateComplianceReport(startDate, endDate);
  console.log(JSON.stringify(report, null, 2));
}

/**
 * Example 6: Export audit logs
 */
function exampleExportLogs() {
  console.log('\n=== Example 6: Export Audit Logs ===\n');

  // Export as JSON
  const jsonLogs = safeguards.exportAuditLogs('json', {
    limit: 10
  });
  console.log('JSON Export (first 10 entries):');
  console.log(JSON.stringify(jsonLogs, null, 2));

  // Export as CSV
  const csvLogs = safeguards.exportAuditLogs('csv', {
    limit: 10
  });
  console.log('\nCSV Export:');
  console.log(csvLogs);
}

/**
 * Example 7: Verify integrity
 */
function exampleVerifyIntegrity() {
  console.log('\n=== Example 7: Verify Audit Trail Integrity ===\n');

  const integrity = safeguards.verifyIntegrity();
  console.log(JSON.stringify(integrity, null, 2));
}

/**
 * Run all examples
 */
async function runAllExamples() {
  try {
    await exampleValidateChanges();
    await exampleBlockedFiles();
    await exampleTooManyChanges();
    exampleStatus();
    exampleComplianceReport();
    exampleExportLogs();
    exampleVerifyIntegrity();
  } catch (error) {
    console.error('Error running examples:', error);
  }
}

// Export for use as module
module.exports = {
  safeguards,
  exampleValidateChanges,
  exampleBlockedFiles,
  exampleTooManyChanges,
  exampleStatus,
  exampleComplianceReport,
  exampleExportLogs,
  exampleVerifyIntegrity,
  runAllExamples
};

// Run examples if executed directly
if (require.main === module) {
  runAllExamples();
}
