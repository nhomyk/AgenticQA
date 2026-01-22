# 📋 Data Integrity System - Quick Reference

## Installation & Setup

```bash
# No external dependencies needed - uses Node.js built-ins
# Copy these files to your project:
# - data-integrity-system.js
# - data-test-framework.js
# - data-validation-pipeline.js
```

## 30-Second Setup

```javascript
const { DataValidationPipeline } = require('./data-validation-pipeline');

const pipeline = new DataValidationPipeline();

// Your deployment
const result = await pipeline.deployWithValidation(
  dataBeforeDeploy,
  async (data) => {
    // Agent deployment logic
    return modifiedData;
  },
  {
    pre: {
      schema: { type: 'array', required: ['id'] },
      requiredFields: ['id'],
      createGolden: true
    }
  }
);

console.log(result.success ? '✅ Deployed' : '❌ Rolled back');
```

---

## Common Patterns

### Pattern 1: Basic Validation

```javascript
const results = await pipeline.validatePreDeployment(data, {
  schema: { type: 'array' },
  requiredFields: ['id']
});

if (!results.passed) {
  console.log('Failed:', results.errors);
  process.exit(1);
}
```

### Pattern 2: Schema + Tests

```javascript
const tests = DataTestSuites.getBasicIntegrityTests()
  .test('Custom: prices positive', (data) => data.every(r => r.price > 0));

const results = await pipeline.validatePreDeployment(data, {
  schema: mySchema,
  tests: tests.tests
});
```

### Pattern 3: Golden Dataset Comparison

```javascript
// First deployment
const pre = await pipeline.validatePreDeployment(data, {
  createGolden: true
});

// Later deployments
const post = await pipeline.validatePostDeployment(newData, {
  goldenDatasetId: pre.validations.goldenDataset.id
});
```

### Pattern 4: Snapshot Testing

```javascript
// Create baseline
await pipeline.validatePreDeployment(data, {
  snapshotName: 'user-data-baseline'
});

// Compare against baseline
const comparison = snapshots.compareSnapshot(
  'user-data-baseline',
  newData
);

console.log(comparison.matches ? '✅ Match' : '❌ Differs');
```

### Pattern 5: Full Deployment Workflow

```javascript
const result = await pipeline.deployWithValidation(
  oldData,
  deploymentFunction,
  {
    pre: { /* pre-deploy config */ },
    post: { /* post-deploy config */ },
    rollbackFn: async () => { /* rollback logic */ }
  }
);

if (!result.success && result.rolledBack) {
  console.log('Deployment failed and rolled back');
}
```

---

## Validation Checklist

### Pre-Deployment
- [ ] Schema defined
- [ ] Required fields specified
- [ ] Tests written
- [ ] Golden dataset created (if first deploy)
- [ ] Snapshot name set

### Execution
- [ ] Agent code executes successfully
- [ ] Data is returned without errors
- [ ] Logs are available for debugging

### Post-Deployment
- [ ] Schema still valid
- [ ] Checksums match (if expected)
- [ ] No anomalies detected
- [ ] Audit trail intact
- [ ] All tests pass

---

## Key APIs Quick Reference

### DataValidationPipeline

```javascript
// Main class - use this for deployments
const pipeline = new DataValidationPipeline(options);

pipeline.validatePreDeployment(data, config);     // Returns: pre-deploy results
pipeline.validatePostDeployment(data, config);    // Returns: post-deploy results
pipeline.executeDeployment(fn, data, ctx);        // Returns: deployment result
pipeline.deployWithValidation(data, fn, config);  // Returns: complete result
pipeline.getValidationReport();                    // Returns: full audit trail
```

### DataIntegritySystem

```javascript
const system = new DataIntegritySystem(options);

system.validatePreDeployment(data, context);      // Runs all pre-checks
system.validatePostDeployment(data, context);     // Runs all post-checks
system.checkDataCompleteness(data, fields);       // Returns: {isComplete, missingFields}
system.detectDuplicates(data, idField);           // Returns: {count, duplicates}
system.generateChangeReport(before, after);       // Returns: change summary
system.shouldRollback(results);                   // Returns: boolean
```

### DataTestFramework

```javascript
const tests = new DataTestFramework();

tests.test(name, fn);                             // Register a test
tests.runAll(data);                               // Returns: {total, passed, failed, allPassed}
tests.assertDataExists(data);                     // Check not empty
tests.assertFieldExists(data, field);             // Check field in all records
tests.assertNoNullFields(data, fields);           // Check required fields
tests.assertNoDuplicates(data, idField);          // Check ID uniqueness
tests.assertValidFormat(data, field, format);     // Check email/uuid/date
```

### DataTestSuites

```javascript
// Pre-built test suites
DataTestSuites.getBasicIntegrityTests();          // Core tests
DataTestSuites.getCompletenessTests(fields);      // Required field tests
DataTestSuites.getFormatTests(formats);           // Type validation
DataTestSuites.getRelationshipTests(rels);        // Foreign key tests
DataTestSuites.getConsistencyTests(rules);        // Logic consistency
DataTestSuites.getBusinessLogicTests(rules);      // Business rules
DataTestSuites.getCompleteSuite(options);         // All tests combined
```

### SnapshotTester

```javascript
const snapshots = new SnapshotTester(dir);

snapshots.createSnapshot(name, data);             // Save baseline
snapshots.compareSnapshot(name, data);            // Returns: {matches, expectedHash, actualHash}
snapshots.updateSnapshot(name, data);             // Update baseline
```

### ChecksumManager

```javascript
const csm = new ChecksumManager('sha256');

csm.createChecksums(data);                        // Returns: {dataHash, dataSize, recordCount}
csm.compare(checksums1, checksums2);              // Returns: comparison result
csm.createMerkleRoot(records);                    // Returns: merkle tree root hash
```

### AuditLogger

```javascript
const auditLog = new AuditLogger(options);

await auditLog.log(entry);                        // Save to immutable log
await auditLog.verifyIntegrity();                 // Returns: {valid, errors}
await auditLog.getByDeployment(id);               // Returns: audit entries for deployment
```

### GoldenDatasetManager

```javascript
const golden = new GoldenDatasetManager(options);

await golden.create(data, metadata);              // Returns: golden dataset ID
await golden.retrieve(id);                        // Returns: {data, metadata}
await golden.list();                              // Returns: all golden datasets
```

### AnomalyDetector

```javascript
const detector = new AnomalyDetector(options);

detector.detect(currentData, baselineStats);      // Returns: {detected, anomalies}
```

### DataReconciliator

```javascript
const reconciliator = new DataReconciliator();

await reconciliator.reconcile(expected, actual);  // Returns: {matches, differences}
```

---

## Configuration Options

### DataValidationPipeline

```javascript
{
  environment: 'production',        // or 'staging', 'development'
  rollbackOnFailure: true,          // Auto-rollback on validation failure
  enableAnomalyDetection: true,     // Detect data drift
  verboseLogging: true,             // Console output detail
  anomalyThreshold: 0.05,           // 5% change tolerance
  dataDir: '.data-integrity',       // Storage directory
  snapshotDir: '.snapshots'         // Snapshot storage
}
```

### Pre-Deployment Config

```javascript
{
  schema: {...},                    // JSON Schema for validation
  requiredFields: [],               // Fields that must exist
  idField: 'id',                    // Unique identifier field
  tests: [],                        // Custom test functions
  createGolden: false,              // Create golden baseline
  snapshotName: undefined,          // Snapshot name for comparison
  version: '1.0.0',                // Data version
  description: 'Deployment desc'   // For audit log
}
```

### Post-Deployment Config

```javascript
{
  schema: {...},                    // Schema for validation
  preDeploymentChecksums: {...},    // From pre-deploy for comparison
  preDeploymentStats: {...},        // Baseline stats for anomaly detection
  goldenDatasetId: undefined,       // Golden dataset to compare against
  tests: [],                        // Tests to re-run
  snapshotName: undefined           // Snapshot to compare against
}
```

---

## Error Codes & Messages

| Error | Cause | Action |
|-------|-------|--------|
| `Schema validation failed` | Data doesn't match schema | Fix data or schema |
| `Data checksums do not match` | Data changed unexpectedly | Investigate changes |
| `Audit trail integrity compromised` | Log was tampered | Restore from backup |
| `Record count changed by X%` | Anomaly detected | Review or update threshold |
| `Field X is missing` | Required field absent | Add missing field |
| `Found X duplicate records` | Duplicate IDs | Deduplicate |
| `Test X failed` | Custom test failed | Fix data or test |
| `Golden dataset not found` | ID invalid | Check dataset ID |

---

## Performance Tips

1. **Schema validation** - Use simple schemas for frequently validated data
2. **Checksum creation** - SHA-256 is fast (~50ms for 1MB)
3. **Audit logging** - Log selectively, not every field
4. **Snapshot testing** - Only for critical data
5. **Anomaly detection** - Tune threshold to reduce false positives

---

## Compliance Artifacts

- **Audit Logs** - `.data-integrity/audit-logs/` - Immutable, tamper-detected
- **Golden Datasets** - `.data-integrity/golden-datasets/` - Baseline comparisons
- **Snapshots** - `.snapshots/` - Point-in-time baselines
- **Validation Reports** - Generated per deployment

---

## Troubleshooting

### "Schema validation failed"
```javascript
// Print detailed errors
const validation = await validator.validate(data, schema);
console.log(validation.errors); // See specific issues
```

### "Checksums don't match"
```javascript
// Compare before/after
const comparison = csm.compare(preChecksums, postChecksums);
console.log(comparison.hashChange);      // true = data changed
console.log(comparison.sizeChange);      // true = size changed
console.log(comparison.recordCountChange); // true = count changed
```

### "Audit integrity failed"
```javascript
// Verify chain
const integrity = await auditLog.verifyIntegrity();
console.log(integrity.errors);  // See broken links
```

### "Anomalies detected"
```javascript
// Review anomalies
const anomalies = detector.detect(data, baseline);
anomalies.anomalies.forEach(a => console.log(a)); // See what changed
```

---

## Integration Examples

### With Jest

```javascript
describe('Data Validation', () => {
  test('pre-deployment validation passes', async () => {
    const results = await pipeline.validatePreDeployment(testData, config);
    expect(results.passed).toBe(true);
  });

  test('post-deployment validation passes', async () => {
    const results = await pipeline.validatePostDeployment(modifiedData, config);
    expect(results.passed).toBe(true);
  });
});
```

### With GitHub Actions

```yaml
- run: node -e "
    const pipeline = require('./data-validation-pipeline').DataValidationPipeline;
    const p = new pipeline();
    const r = await p.deployWithValidation(data, deploy, config);
    process.exit(r.success ? 0 : 1);
  "
```

### With Mocha

```javascript
describe('Data Integrity', () => {
  it('should validate pre-deployment', async () => {
    const results = await pipeline.validatePreDeployment(data, config);
    assert.ok(results.passed);
  });
});
```

---

## Command-Line Usage

```bash
# Check data integrity
node -e "
  const { DataIntegritySystem } = require('./data-integrity-system');
  const system = new DataIntegritySystem();
  const results = system.checkDataCompleteness(data, ['id', 'email']);
  console.log(results);
"

# Verify audit trail
node -e "
  const { AuditLogger } = require('./data-integrity-system');
  const log = new AuditLogger();
  const integrity = await log.verifyIntegrity();
  console.log(integrity.valid ? '✅ Valid' : '❌ Compromised');
"
```

---

## Next Steps

1. Read [DATA_INTEGRITY_SYSTEM.md](DATA_INTEGRITY_SYSTEM.md) for full documentation
2. Check examples in `data-validation-pipeline.js`
3. Review test suites in `data-test-framework.js`
4. Integrate into your CI/CD pipeline
5. Set up golden datasets for critical data

---

**Version:** 1.0.0  
**Updated:** January 2026  
**Status:** Production Ready
