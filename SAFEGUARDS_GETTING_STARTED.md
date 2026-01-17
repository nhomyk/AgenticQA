# 🚀 Getting Started with OrbitQA Safeguards

## Installation (Already Done ✅)

All safeguard components are installed in `src/safeguards/`. No additional npm packages required.

## Quick Start (60 seconds)

### 1. Run Tests
```bash
npm run safeguards:test
```

Expected output:
```
✅ TEST 1: Valid Agent Changes - PASSED (risk: 0.0%)
❌ TEST 2: Protected File Modification - FAILED (as expected)
❌ TEST 3: Too Many Changes - FAILED (as expected)
✅ TEST 4: High-Risk Changes - PASSED (risk score calculated)
```

### 2. View Examples
```bash
npm run safeguards:examples
```

Shows 7 different usage patterns including:
- Validate changes
- Detect blocked files
- Assess risk
- View status
- Generate compliance reports
- Export logs
- Verify integrity

### 3. Integration Patterns
```bash
npm run safeguards:integration
```

Demonstrates 6 ways to integrate with agents:
- Wrap existing agents
- Use with SDET Agent
- Use with SRE Agent
- Use with Fullstack Agent
- Batch processing
- Complete workflow

## Basic Usage (5 minutes)

### Initialize in Your Code
```javascript
const SafeguardPipeline = require('./src/safeguards/pipeline');

// Create instance
const safeguards = new SafeguardPipeline({
  enableGatekeeper: true,
  enableRollback: true,
  enableAudit: true
});
```

### Validate Agent Changes
```javascript
// Define changes
const changes = [
  { filePath: 'src/helpers.js', type: 'UPDATE' },
  { filePath: 'src/tests/helpers.test.js', type: 'CREATE' }
];

// Define agent
const agent = {
  id: 'SDET-001',
  name: 'SDET Agent',
  type: 'SDET',
  successRate: 0.94,
  confidenceScore: 0.92
};

// Process with safeguards
const result = await safeguards.processAgentChanges(changes, agent);

if (result.success) {
  console.log('✅ Changes approved');
  console.log(`   Risk score: ${(result.validation.riskScore * 100).toFixed(1)}%`);
  // Apply changes to codebase
} else {
  console.log('❌ Changes rejected:', result.validation.reason);
  // Handle rejection
}
```

### Check System Status
```javascript
const status = safeguards.getStatus();
console.log(status);

// Output:
// {
//   enabled: { gatekeeper: true, rollback: true, audit: true },
//   gatekeeper: { auditLogSize: 42, ... },
//   rollback: { rollbackCount: 2, ... },
//   audit: { totalEntries: 127, integrityStatus: { ... } }
// }
```

### Generate Compliance Report
```javascript
const report = safeguards.generateComplianceReport(
  new Date('2026-01-01'),
  new Date('2026-01-31')
);

console.log(`Total changes: ${report.totalChanges}`);
console.log(`Approved: ${report.changesApproved}`);
console.log(`Rolled back: ${report.changesRolledBack}`);
```

## Integration with Your Agents (10 minutes)

### Option A: Wrap Your Existing Agent
```javascript
const SafeAgent = require('./src/safeguards/agent-integration').SafeAgent;

// Wrap your existing agent
const safeAgent = new SafeAgent(myExistingAgent);

// Execute with safeguards
const result = await safeAgent.executeWithSafeguards(task);
```

### Option B: Use Pattern-Specific Wrappers
```javascript
// For SDET Agent
const SafeSDETAgent = require('./src/safeguards/agent-integration').SafeSDETAgent;
const safeSDET = new SafeSDETAgent(sddetAgent);
await safeSDET.generateAndValidateTests();

// For SRE Agent
const SafeSREAgent = require('./src/safeguards/agent-integration').SafeSREAgent;
const safeSRE = new SafeSREAgent(sreAgent);
await safeSRE.fixPipelineWithMonitoring();

// For Fullstack Agent
const SafeFullstackAgent = require('./src/safeguards/agent-integration').SafeFullstackAgent;
const safeFullstack = new SafeFullstackAgent(fullstackAgent);
await safeFullstack.fixComplianceIssues();
```

### Option C: Process Multiple Agents
```javascript
const BatchProcessor = require('./src/safeguards/agent-integration').SafeguardedBatchProcessor;

const processor = new BatchProcessor();
const summary = await processor.processBatch([
  sddetAgent,
  sreAgent,
  fullstackAgent
]);

console.log(`Processed: ${summary.successful}/${summary.total}`);
```

## Configuration (10 minutes)

### Protect Additional Files
```javascript
// In src/safeguards/config.js
blockedFilePatterns: [
  // Default patterns...
  
  // Add your own:
  '**/database/migrations/**',
  '**/schema/production/**',
  '**/.env.production',
  '**/secrets/**'
];
```

### Adjust Monitoring Thresholds
```javascript
// In src/safeguards/config.js
rollback: {
  thresholds: {
    errorRateIncreasePercent: 50,  // More lenient: 75
    latencyIncreasePercent: 30,    // More strict: 15
    memoryLeakMB: 100,             // Adjust as needed
    cpuSpikePercent: 40,           // Adjust as needed
    failedTestsThreshold: 5        // Adjust as needed
  }
}
```

### Enable S3 Archive (Production)
```javascript
// In src/safeguards/config.js
audit: {
  enableAuditLogging: true,
  enableS3Archive: true,
  s3Config: {
    bucket: 'my-company-audit-logs',
    region: 'us-east-1',
    kmsKeyId: 'arn:aws:kms:...'  // Encryption
  }
}
```

## Monitoring & Compliance (15 minutes)

### View Recent Audit Entries
```javascript
const recent = safeguards.auditTrail.getRecentEntries(10);
recent.forEach(entry => {
  console.log(`[${entry.iso8601}] ${entry.agent}: ${entry.action}`);
});
```

### Query Specific Changes
```javascript
// High-risk changes
const highRisk = safeguards.auditTrail.queryLogs({ minRiskScore: 0.75 });

// Agent-specific changes
const agentChanges = safeguards.auditTrail.queryLogs({ agent: 'SDET Agent' });

// Changes in date range
const dateRange = safeguards.auditTrail.queryLogs({
  startDate: new Date('2026-01-01'),
  endDate: new Date('2026-01-31')
});
```

### Export for Auditors
```javascript
// Export as JSON
const json = safeguards.exportAuditLogs('json', {
  minRiskScore: 0.5,
  limit: 1000
});
fs.writeFileSync('audit-export.json', JSON.stringify(json, null, 2));

// Export as CSV
const csv = safeguards.exportAuditLogs('csv', {
  limit: 1000
});
fs.writeFileSync('audit-export.csv', csv);
```

### Verify Audit Integrity
```javascript
const integrity = safeguards.verifyIntegrity();
console.log(`Total entries: ${integrity.totalEntries}`);
console.log(`Corrupted: ${integrity.corruptedEntries}`);
console.log(`Verified: ${integrity.integrityVerified ? '✓' : '✗'}`);
```

## CI/CD Integration

The workflow is already configured in `.github/workflows/agent-safeguards.yml`.

On every push/PR:
1. ✓ Gatekeeper validates changes
2. ✓ Risk assessment calculated
3. ✓ Changes logged
4. ✓ Deployment monitoring starts
5. ✓ Safeguards report posted

**No approval gates** (as requested) - you can enable these before production.

## Before Production

When ready to deploy to production, add:

1. **Approval Workflow**
   ```javascript
   // Create approvalGateway.js
   // Code owner review + auto-merge for low-risk
   ```

2. **Notifications**
   ```javascript
   // Slack integration for alerts
   // Email on high-risk changes
   ```

3. **Incident Creation**
   ```javascript
   // PagerDuty alerts on rollback
   // Jira tickets for failures
   ```

4. **S3 Archive**
   ```javascript
   // Long-term audit log retention
   // Encryption at rest
   ```

## Troubleshooting

### "File is protected" Error
**Problem:** Legitimate file blocked  
**Solution:** Check `blockedFilePatterns` in `src/safeguards/config.js`

```javascript
// Verify the pattern
const file = 'src/helpers.js';
const pattern = '**/helpers.js';
// If pattern matches, file is blocked
```

### "Too many changes" Error
**Problem:** Valid change rejected (> 50 files)  
**Solution:** Either:
1. Increase limit: `maxChangesPerPR: 100`
2. Split into multiple PRs

### Rollback Triggering Unexpectedly
**Problem:** Deployment auto-rolled back  
**Solution:** Check `rollback/thresholds` in config

```javascript
// Review the metrics
const degradation = safeguards.rollbackMonitor.rollbackHistory[0];
console.log(degradation.metrics);
// Adjust thresholds if too strict
```

## Advanced Usage

### Custom Gatekeeper Rules
```javascript
const gatekeeper = safeguards.gatekeeper;

// Add custom validation
const customViolation = {
  type: 'CUSTOM_RULE',
  severity: 'ERROR',
  message: 'Your custom rule text'
};
```

### Custom Metrics in Rollback Monitor
```javascript
// Override metric collection
rollbackMonitor.getErrorRate = async () => {
  const prometheus = await fetch('/metrics/error_rate');
  return prometheus.json().value;
};
```

### Custom Audit Log Storage
```javascript
// Extend AuditTrail class
class CustomAuditTrail extends AuditTrail {
  async archiveToDatabase(entry) {
    await db.auditLogs.insert(entry);
  }
}
```

## Scripts Summary

```bash
# Test the system
npm run safeguards:test

# View usage examples
npm run safeguards:examples

# See integration patterns
npm run safeguards:integration

# Verify system ready
npm run safeguards:verify
```

## Documentation

- 📖 [Full README](src/safeguards/README.md) - 450+ lines
- 📋 [Implementation Guide](SAFEGUARDS_IMPLEMENTATION.md) - Complete details
- 📊 [Summary](SAFEGUARDS_SUMMARY.md) - Quick overview
- 💻 [Examples](src/safeguards/examples.js) - 7 use cases
- 🔗 [Integration Patterns](src/safeguards/agent-integration.js) - 6 patterns

## Support

Have questions? Check:
1. `src/safeguards/README.md` - Most detailed
2. `src/safeguards/examples.js` - Working code
3. `src/safeguards/quickstart.js` - Test cases
4. `src/safeguards/agent-integration.js` - Integration patterns

## Next Steps

1. ✅ Run `npm run safeguards:test` - Verify it works
2. ✅ Review `src/safeguards/config.js` - Customize for your needs
3. ✅ Integrate with your agents - Use patterns from `agent-integration.js`
4. ✅ Test in staging - Before production deployment
5. ✅ Enable S3 archive - For production compliance
6. ✅ Add approval gates - Before going live

---

**You're all set!** The safeguards system is ready to protect your autonomous agents. 🚀
