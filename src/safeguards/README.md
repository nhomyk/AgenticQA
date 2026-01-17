# OrbitQA Safeguards System

Enterprise-grade protection for autonomous AI agents in your CI/CD pipeline. This system provides file protection, risk assessment, automatic rollback, and immutable audit trails—without blocking your build process.

## Overview

The Safeguards System consists of three interconnected components:

```
┌─────────────────────────────────────────────────────┐
│         SafeguardPipeline (Main Orchestrator)      │
└─────────────────┬───────────────────────────────────┘
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
    ┌────────┐ ┌────────┐ ┌──────────┐
    │ Gate   │ │Rollback│ │  Audit   │
    │ keeper │ │Monitor │ │  Trail   │
    └────────┘ └────────┘ └──────────┘
```

## Components

### 1. PipelineGatekeeper
Validates agent changes before they're applied to your codebase.

**Features:**
- ✓ File whitelisting/blacklisting (protect critical files)
- ✓ Change scope limits (prevent massive sweeping changes)
- ✓ Risk scoring (assess change complexity)
- ✓ Pattern matching (flexible file protection)

**Protected Files (Default):**
```
- **/package.json       (Dependencies)
- **/.env*              (Secrets)
- **/auth/**            (Authentication)
- **/payment/**         (PCI-DSS compliance)
- **/*.lock             (Lock files)
- **/.github/workflows/**  (CI/CD config)
```

**Usage:**
```javascript
const PipelineGatekeeper = require('./src/safeguards/gatekeeper');

const gatekeeper = new PipelineGatekeeper();
const changes = [
  { filePath: 'src/helpers.js', type: 'UPDATE' },
  { filePath: 'src/tests/helpers.test.js', type: 'CREATE' }
];

const agent = {
  id: 'SDET-001',
  name: 'SDET Agent',
  type: 'SDET',
  successRate: 0.92,
  confidenceScore: 0.88
};

const validation = await gatekeeper.validateAgentChanges(changes, agent);
console.log(validation); // { passed: true, riskScore: 0.15 }
```

### 2. RollbackMonitor
Monitors production metrics after deployment and triggers automatic rollback if degradation is detected.

**Monitored Metrics:**
- Error rate increase (threshold: 50%)
- Latency degradation (P95, threshold: 30%)
- Memory leaks (threshold: 100MB)
- CPU spikes (threshold: 40%)
- Failed tests (threshold: 5+)

**Usage:**
```javascript
const RollbackMonitor = require('./src/safeguards/rollback-monitor');

const monitor = new RollbackMonitor({
  monitoringDurationMs: 30 * 60 * 1000, // 30 minutes
  thresholds: {
    errorRateIncreasePercent: 50,
    latencyIncreasePercent: 30,
    memoryLeakMB: 100
  }
});

const deployment = {
  id: 'DEPLOY-123',
  agentId: 'SDET-001',
  changes: [...],
  status: 'DEPLOYED'
};

const result = await monitor.monitorDeployment(deployment);
// { success: true, rolledBack: false, duration: 1800000 }
```

### 3. AuditTrail
Immutable, cryptographically-signed audit log for compliance.

**Features:**
- ✓ Tamper-proof signatures (SHA-256)
- ✓ Organized storage (yearly/monthly/daily logs)
- ✓ High-risk alerts (automatic notification)
- ✓ Compliance reports (SOC2, GDPR, HIPAA)
- ✓ Export to JSON/CSV
- ✓ Integrity verification

**Usage:**
```javascript
const AuditTrail = require('./src/safeguards/audit-trail');

const audit = new AuditTrail({
  storagePath: './audit-logs',
  enableS3Archive: false, // Enable for production
  alertThreshold: 0.75 // Alert on high-risk operations
});

// Log an event
const entry = await audit.logEvent({
  agent: { name: 'SDET Agent', type: 'SDET' },
  action: 'CHANGES_VALIDATED',
  changes: [...],
  result: 'APPROVED',
  riskScore: 0.15
});

// Query logs
const highRiskChanges = audit.queryLogs({ minRiskScore: 0.75 });

// Generate compliance report
const report = audit.generateComplianceReport(startDate, endDate);

// Verify integrity
const integrity = audit.verifyIntegrity();
```

## SafeguardPipeline (Main Integration Point)

Orchestrates all three components in a single workflow.

```javascript
const SafeguardPipeline = require('./src/safeguards/pipeline');
const config = require('./src/safeguards/config');

const safeguards = new SafeguardPipeline({
  enableGatekeeper: true,
  enableRollback: true,
  enableAudit: true,
  ...config
});

// Process agent changes (validation + monitoring + logging)
const result = await safeguards.processAgentChanges(
  changes,  // Array of Change objects
  agent,    // Agent object with metadata
  { version: '1.0.0', asyncMonitoring: true }
);

if (!result.success) {
  console.error('Validation failed:', result.validation.reason);
  // Reject the changes
} else {
  console.log('Changes validated and monitoring started');
  // Apply changes to codebase
}
```

## Configuration

Edit `src/safeguards/config.js` to customize behavior:

```javascript
module.exports = {
  gatekeeper: {
    maxChangesPerPR: 50,
    blockedFilePatterns: [
      '**/package.json',
      '**/.env*',
      // Add your own patterns
    ],
    allowedFilePatterns: [
      '**/*.js',
      '**/*.ts',
      // Add your own patterns
    ]
  },

  rollback: {
    enableMonitoring: true,
    monitoringDurationMs: 30 * 60 * 1000,
    thresholds: {
      errorRateIncreasePercent: 50,
      latencyIncreasePercent: 30,
      memoryLeakMB: 100,
      cpuSpikePercent: 40,
      failedTestsThreshold: 5
    }
  },

  audit: {
    enableAuditLogging: true,
    storagePath: './audit-logs',
    enableS3Archive: false,
    alertThreshold: 0.75
  }
};
```

## CI/CD Integration

The system integrates with GitHub Actions (without approval gates for now):

```yaml
# .github/workflows/agent-safeguards.yml

- name: Run Gatekeeper Validation
  run: node src/safeguards/gatekeeper.js

- name: Risk Assessment
  run: node src/safeguards/examples.js

- name: Audit Trail Logging
  run: node src/safeguards/audit-trail.js

- name: Start Deployment Monitoring
  run: node src/safeguards/rollback-monitor.js
```

See `.github/workflows/agent-safeguards.yml` for the complete workflow.

## Running Examples

Test the safeguards system:

```bash
node src/safeguards/examples.js
```

Examples included:
1. ✓ Validate agent changes
2. ✓ Detect blocked file modifications
3. ✓ Detect too many changes
4. ✓ View safeguard status
5. ✓ Generate compliance report
6. ✓ Export audit logs (JSON/CSV)
7. ✓ Verify audit trail integrity

## Risk Scoring

The Gatekeeper calculates risk scores (0-1.0) based on:

| Factor | Risk Impact | Description |
|--------|------------|-------------|
| Security code modified | +0.3 | Touching auth/security code |
| Multiple directories | +0.2 | Modifying 4+ unrelated directories |
| Deletions | +0.15 | Files being deleted |
| Test infrastructure | +0.1 | Modifying jest/playwright config |
| Low success rate | +0.2 | Agent success rate < 85% |
| High success rate | -0.1 | Agent success rate > 95% |

**Risk Levels:**
- **Low (0.0-0.3):** Auto-approved, logged
- **Medium (0.3-0.6):** Logged, monitored
- **High (0.6-0.8):** Logged, monitored, alerts sent
- **Critical (0.8-1.0):** Requires manual review (when enabled in prod)

## Audit Log Storage

Logs are organized by date:

```
audit-logs/
├── index.json                 (Master index)
├── 2024-01/
│   ├── 2024-01-01.ndjson     (All entries for Jan 1)
│   ├── 2024-01-02.ndjson
│   └── ...
├── 2024-02/
│   └── ...
```

Each entry is signed with SHA-256:

```json
{
  "id": "AUDIT-1705513200123-abc123def",
  "timestamp": 1705513200123,
  "iso8601": "2024-01-17T12:00:00.123Z",
  "agent": "SDET Agent",
  "action": "CHANGES_VALIDATED",
  "changes": [...],
  "result": "APPROVED",
  "riskScore": 0.15,
  "signature": "a1b2c3d4e5f6..." // Tamper-proof
}
```

## Compliance Reports

Generate compliance reports for auditors:

```javascript
const report = safeguards.generateComplianceReport(
  new Date('2024-01-01'),
  new Date('2024-01-31')
);

// Output includes:
// - Total changes processed
// - Approval rates
// - Rollback events
// - Agent breakdown
// - High-risk operations
// - SOC2/GDPR/HIPAA compliance status
```

## Roadmap: Pre-Production Features

When you're ready for production, add:

1. **Mandatory Approval Workflow**
   - Code owner review required for high-risk changes
   - GitHub PR approval integration
   - Configurable approval thresholds

2. **Advanced Integrations**
   - Slack notifications for alerts
   - PagerDuty incident creation
   - Datadog/Prometheus metrics
   - S3 archive for long-term retention

3. **Enhanced Monitoring**
   - Custom metric integrations
   - Canary deployments
   - Blue-green deployment support
   - Feature flag integration

4. **Advanced Analytics**
   - Agent performance trends
   - Risk pattern analysis
   - Anomaly detection
   - Predictive rollback

## Troubleshooting

**Problem:** Gatekeeper rejecting legitimate changes

**Solution:** 
1. Check `blockedFilePatterns` in config
2. Verify file path matches pattern exactly
3. Add exception patterns if needed

---

**Problem:** Rollback triggering incorrectly

**Solution:**
1. Increase thresholds in rollback config
2. Check baseline metric capture
3. Enable logging for detailed diagnostics

---

**Problem:** Audit logs growing too large

**Solution:**
1. Archive old logs to S3 (`enableS3Archive: true`)
2. Reduce `maxEntriesInMemory` if needed
3. Implement log rotation policy

## Support

For questions about the safeguards system:
- 📖 See `/src/safeguards/examples.js` for usage patterns
- 🔧 Check `src/safeguards/config.js` for configuration
- 📝 Review audit logs in `audit-logs/` for compliance

---

**Note:** This system validates and monitors agent changes but does NOT require approval before deployment (as requested). Approval gates will be enabled before production deployment.
