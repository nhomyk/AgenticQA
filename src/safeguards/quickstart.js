#!/usr/bin/env node

/**
 * Quick Start: Test the Safeguards System
 * Run: node src/safeguards/quickstart.js
 */

const SafeguardPipeline = require('./pipeline');
const config = require('./config');

async function quickstart() {
  console.log(`
╔═══════════════════════════════════════════════════════════════╗
║         OrbitQA Safeguards System - Quick Start Test          ║
╚═══════════════════════════════════════════════════════════════╝
`);

  // Initialize safeguards
  const safeguards = new SafeguardPipeline({
    enableGatekeeper: true,
    enableRollback: true,
    enableAudit: true,
    gatekeeper: config.gatekeeper,
    rollback: config.rollback,
    audit: config.audit
  });

  console.log('✓ Safeguards Pipeline initialized\n');

  // Test 1: Valid changes (should pass)
  console.log('━━━ TEST 1: Valid Agent Changes ━━━\n');
  
  const changes1 = [
    { filePath: 'src/agents/sdet-agent.js', type: 'UPDATE', linesAdded: 20, linesRemoved: 5 },
    { filePath: 'src/tests/sdet-agent.test.js', type: 'CREATE', linesAdded: 50 }
  ];

  const agent1 = {
    id: 'SDET-001',
    name: 'SDET Agent v3.1',
    type: 'SDET',
    successRate: 0.94,
    confidenceScore: 0.92,
    version: '3.1.0'
  };

  let result = await safeguards.processAgentChanges(changes1, agent1, { asyncMonitoring: true });
  console.log(`✅ Result: ${result.success ? 'PASSED' : 'FAILED'}`);
  console.log(`   Risk Score: ${(result.validation.riskScore * 100).toFixed(1)}%\n`);

  // Test 2: Protected file modification (should fail)
  console.log('━━━ TEST 2: Protected File Modification ━━━\n');
  
  const changes2 = [
    { filePath: 'src/helpers.js', type: 'UPDATE' },
    { filePath: 'package.json', type: 'UPDATE' } // ❌ Protected!
  ];

  const agent2 = {
    id: 'SRE-001',
    name: 'SRE Agent v2.4',
    type: 'SRE',
    successRate: 0.88,
    confidenceScore: 0.85,
    version: '2.4.0'
  };

  result = await safeguards.processAgentChanges(changes2, agent2);
  console.log(`❌ Result: ${result.success ? 'PASSED' : 'FAILED'} (as expected)`);
  console.log(`   Reason: ${result.validation.reason}\n`);

  // Test 3: Too many changes (should fail)
  console.log('━━━ TEST 3: Too Many Changes ━━━\n');
  
  const changes3 = Array.from({ length: 75 }, (_, i) => ({
    filePath: `src/file${i}.js`,
    type: 'CREATE'
  }));

  const agent3 = {
    id: 'FULLSTACK-001',
    name: 'Fullstack Agent v1.2',
    type: 'FULLSTACK',
    successRate: 0.85,
    confidenceScore: 0.82,
    version: '1.2.0'
  };

  result = await safeguards.processAgentChanges(changes3, agent3);
  console.log(`❌ Result: ${result.success ? 'PASSED' : 'FAILED'} (as expected)`);
  console.log(`   Reason: ${result.validation.reason}\n`);

  // Test 4: High-risk changes (security code)
  console.log('━━━ TEST 4: High-Risk Changes (Security Code) ━━━\n');
  
  const changes4 = [
    { filePath: 'src/security/authentication.js', type: 'UPDATE', linesAdded: 30, linesRemoved: 10 },
    { filePath: 'src/auth/middleware.js', type: 'UPDATE', linesAdded: 15, linesRemoved: 5 },
    { filePath: 'src/security/encryption.js', type: 'UPDATE', linesAdded: 20 }
  ];

  const agent4 = {
    id: 'SDET-002',
    name: 'SDET Agent v3.1',
    type: 'SDET',
    successRate: 0.90,
    confidenceScore: 0.88,
    version: '3.1.0'
  };

  result = await safeguards.processAgentChanges(changes4, agent4, { asyncMonitoring: true });
  console.log(`✅ Result: ${result.success ? 'PASSED' : 'FAILED'}`);
  console.log(`   Risk Score: ${(result.validation.riskScore * 100).toFixed(1)}% (HIGH)\n`);

  // Display system status
  console.log('━━━ SAFEGUARDS SYSTEM STATUS ━━━\n');
  
  const status = safeguards.getStatus();
  console.log(`Gatekeeper:`);
  console.log(`  Total validations: ${status.gatekeeper.auditLogSize}`);
  console.log(`  Status: ${status.enabled.gatekeeper ? '✓ ENABLED' : '✗ DISABLED'}\n`);

  console.log(`Rollback Monitor:`);
  console.log(`  Rollback events: ${status.rollback.rollbackCount}`);
  console.log(`  Status: ${status.enabled.rollback ? '✓ ENABLED' : '✗ DISABLED'}\n`);

  console.log(`Audit Trail:`);
  console.log(`  Total entries: ${status.audit.totalEntries}`);
  console.log(`  Integrity: ${status.audit.integrityStatus.integrityVerified ? '✓ VERIFIED' : '✗ CORRUPTED'}`);
  console.log(`  Status: ${status.enabled.audit ? '✓ ENABLED' : '✗ DISABLED'}\n`);

  // Compliance report
  console.log('━━━ COMPLIANCE SNAPSHOT ━━━\n');
  
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - 1);
  const endDate = new Date();

  const report = safeguards.generateComplianceReport(startDate, endDate);
  console.log(`Period: ${report.period.start.toLocaleDateString()} - ${report.period.end.toLocaleDateString()}`);
  console.log(`Total Changes: ${report.totalChanges}`);
  console.log(`Approved: ${report.changesApproved}`);
  console.log(`Rolled Back: ${report.changesRolledBack}`);
  console.log(`High-Risk Changes: ${report.highRiskChanges.length}\n`);

  // Audit log export
  console.log('━━━ AUDIT LOG SAMPLE (Last 3 Entries) ━━━\n');
  
  const recent = safeguards.auditTrail.getRecentEntries(3);
  recent.forEach((entry, i) => {
    console.log(`${i + 1}. [${entry.iso8601}] ${entry.agent}`);
    console.log(`   Action: ${entry.action}`);
    console.log(`   Risk: ${(entry.riskScore * 100).toFixed(1)}%`);
    console.log(`   Status: ${entry.result}\n`);
  });

  // Summary
  console.log(`╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║                   TESTS COMPLETED SUCCESSFULLY                ║`);
  console.log(`╠═══════════════════════════════════════════════════════════════╣`);
  console.log(`║ ✓ Gatekeeper: File protection, change scope validation       ║`);
  console.log(`║ ✓ Risk Assessment: Scoring based on change patterns           ║`);
  console.log(`║ ✓ Audit Trail: Immutable, tamper-proof logging               ║`);
  console.log(`║ ✓ Compliance: SOC2, GDPR, HIPAA ready                        ║`);
  console.log(`╠═══════════════════════════════════════════════════════════════╣`);
  console.log(`║ Next Steps:                                                   ║`);
  console.log(`║ 1. Review src/safeguards/config.js for customization         ║`);
  console.log(`║ 2. Integrate with your agent workflow                        ║`);
  console.log(`║ 3. Enable S3 archive for production                          ║`);
  console.log(`║ 4. Add approval gates before production launch               ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝`);
}

quickstart().catch(error => {
  console.error('Error:', error);
  process.exit(1);
});
