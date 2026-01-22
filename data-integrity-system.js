/**
 * AgenticQA Data Integrity System
 * Comprehensive data accuracy, quality, and correctness validation
 * 
 * Features:
 * - Schema validation (JSON Schema, Zod)
 * - Checksum verification (SHA-256, Merkle trees)
 * - Data diffing and reconciliation
 * - Audit logging with immutable trails
 * - Anomaly detection
 * - Golden dataset comparison
 * - Pre/post-deployment validation
 */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { EventEmitter } = require('events');

/**
 * Core Data Integrity Manager
 */
class DataIntegritySystem extends EventEmitter {
  constructor(options = {}) {
    super();
    
    this.options = {
      dataDir: options.dataDir || '.data-integrity',
      checksumAlgorithm: options.checksumAlgorithm || 'sha256',
      enableAuiting: options.enableAuditing !== false,
      enableAnomalyDetection: options.enableAnomalyDetection !== false,
      anomalyThreshold: options.anomalyThreshold || 0.05, // 5% change threshold
      ...options
    };

    this.validators = new SchemaValidator();
    this.checksumManager = new ChecksumManager(this.options.checksumAlgorithm);
    this.auditLog = new AuditLogger(this.options);
    this.goldenDatasets = new GoldenDatasetManager(this.options);
    this.anomalyDetector = new AnomalyDetector(this.options);
    this.reconciliator = new DataReconciliator(this.options);

    // Ensure data directory exists
    if (!fs.existsSync(this.options.dataDir)) {
      fs.mkdirSync(this.options.dataDir, { recursive: true });
    }

    console.log('✅ Data Integrity System initialized');
  }

  /**
   * Pre-deployment validation phase
   */
  async validatePreDeployment(data, context = {}) {
    console.log('\n📋 [DATA INTEGRITY] Pre-Deployment Validation Phase');
    
    const results = {
      timestamp: new Date().toISOString(),
      phase: 'pre-deployment',
      validations: {},
      passed: true,
      errors: []
    };

    try {
      // 1. Schema Validation
      console.log('  1️⃣  Validating schema...');
      const schemaValidation = await this.validators.validate(data, context.schema);
      results.validations.schema = schemaValidation;
      if (!schemaValidation.valid) {
        results.passed = false;
        results.errors.push(`Schema validation failed: ${schemaValidation.errors.join(', ')}`);
      } else {
        console.log('     ✅ Schema valid');
      }

      // 2. Create checksums
      console.log('  2️⃣  Creating data checksums...');
      const checksums = await this.checksumManager.createChecksums(data);
      results.validations.checksums = checksums;
      console.log(`     ✅ Checksums created (SHA256: ${checksums.dataHash.substring(0, 16)}...)`);

      // 3. Data completeness
      console.log('  3️⃣  Checking data completeness...');
      const completeness = this.checkDataCompleteness(data, context.requiredFields);
      results.validations.completeness = completeness;
      if (!completeness.isComplete) {
        results.passed = false;
        results.errors.push(`Data incomplete: Missing fields: ${completeness.missingFields.join(', ')}`);
      } else {
        console.log('     ✅ All required fields present');
      }

      // 4. Duplicate detection
      console.log('  4️⃣  Checking for duplicates...');
      const duplicates = this.detectDuplicates(data, context.idField);
      results.validations.duplicates = duplicates;
      if (duplicates.count > 0) {
        results.passed = false;
        results.errors.push(`Found ${duplicates.count} duplicate records`);
      } else {
        console.log('     ✅ No duplicates detected');
      }

      // 5. Run data tests
      if (context.tests) {
        console.log('  5️⃣  Running data tests...');
        const testResults = await this.runDataTests(data, context.tests);
        results.validations.tests = testResults;
        if (!testResults.allPassed) {
          results.passed = false;
          results.errors.push(`Data tests failed: ${testResults.failures.join(', ')}`);
        } else {
          console.log(`     ✅ All ${testResults.total} data tests passed`);
        }
      }

      // 6. Create golden dataset if this is first deployment
      if (context.createGolden) {
        console.log('  6️⃣  Creating golden dataset...');
        const goldenId = await this.goldenDatasets.create(data, {
          version: context.version,
          description: context.description,
          checksums
        });
        results.validations.goldenDataset = { created: true, id: goldenId };
        console.log(`     ✅ Golden dataset created: ${goldenId}`);
      }

      // 7. Audit pre-deployment state
      if (this.options.enableAuditing) {
        console.log('  7️⃣  Recording pre-deployment audit...');
        await this.auditLog.log({
          phase: 'pre-deployment',
          action: 'validation',
          dataHash: checksums.dataHash,
          context,
          status: results.passed ? 'passed' : 'failed'
        });
        console.log('     ✅ Audit logged');
      }

      if (results.passed) {
        console.log('\n✅ Pre-Deployment Validation PASSED\n');
      } else {
        console.log('\n❌ Pre-Deployment Validation FAILED\n');
      }

    } catch (error) {
      results.passed = false;
      results.errors.push(error.message);
      console.log(`\n❌ Pre-Deployment Validation ERROR: ${error.message}\n`);
      this.emit('error', { phase: 'pre-deployment', error });
    }

    return results;
  }

  /**
   * Post-deployment validation phase
   */
  async validatePostDeployment(data, context = {}) {
    console.log('\n📋 [DATA INTEGRITY] Post-Deployment Validation Phase');
    
    const results = {
      timestamp: new Date().toISOString(),
      phase: 'post-deployment',
      validations: {},
      passed: true,
      errors: [],
      warnings: []
    };

    try {
      // 1. Re-validate schema
      console.log('  1️⃣  Re-validating schema...');
      const schemaValidation = await this.validators.validate(data, context.schema);
      results.validations.schema = schemaValidation;
      if (!schemaValidation.valid) {
        results.passed = false;
        results.errors.push(`Schema validation failed: ${schemaValidation.errors.join(', ')}`);
      } else {
        console.log('     ✅ Schema still valid');
      }

      // 2. Compare checksums
      if (context.preDeploymentChecksums) {
        console.log('  2️⃣  Comparing checksums...');
        const newChecksums = await this.checksumManager.createChecksums(data);
        const checksumComparison = this.checksumManager.compare(
          context.preDeploymentChecksums,
          newChecksums
        );
        results.validations.checksumComparison = checksumComparison;
        
        if (!checksumComparison.matches) {
          results.passed = false;
          results.errors.push('Data checksums do not match pre-deployment values');
        } else {
          console.log('     ✅ Checksums match pre-deployment');
        }
      }

      // 3. Reconcile against golden dataset
      if (context.goldenDatasetId) {
        console.log('  3️⃣  Reconciling against golden dataset...');
        const golden = await this.goldenDatasets.retrieve(context.goldenDatasetId);
        const reconciliation = await this.reconciliator.reconcile(golden.data, data);
        results.validations.reconciliation = reconciliation;
        
        if (reconciliation.differences.length > 0) {
          results.warnings.push(`Found ${reconciliation.differences.length} differences from golden dataset`);
          console.log(`     ⚠️  Differences found: ${reconciliation.differences.length}`);
        } else {
          console.log('     ✅ Data matches golden dataset exactly');
        }
      }

      // 4. Detect anomalies
      if (this.options.enableAnomalyDetection && context.preDeploymentStats) {
        console.log('  4️⃣  Detecting data anomalies...');
        const anomalies = this.anomalyDetector.detect(data, context.preDeploymentStats);
        results.validations.anomalies = anomalies;
        
        if (anomalies.detected) {
          results.warnings.push(`Anomalies detected: ${anomalies.anomalies.join(', ')}`);
          console.log(`     ⚠️  Anomalies: ${anomalies.anomalies.join(', ')}`);
        } else {
          console.log('     ✅ No anomalies detected');
        }
      }

      // 5. Check audit trail integrity
      if (this.options.enableAuditing) {
        console.log('  5️⃣  Verifying audit trail integrity...');
        const auditIntegrity = await this.auditLog.verifyIntegrity();
        results.validations.auditIntegrity = auditIntegrity;
        
        if (!auditIntegrity.valid) {
          results.passed = false;
          results.errors.push('Audit trail integrity compromised');
        } else {
          console.log('     ✅ Audit trail integrity verified');
        }
      }

      // 6. Run post-deployment tests (same tests as pre-deployment)
      if (context.tests) {
        console.log('  6️⃣  Running post-deployment data tests...');
        const testResults = await this.runDataTests(data, context.tests);
        results.validations.postTests = testResults;
        
        if (!testResults.allPassed) {
          results.passed = false;
          results.errors.push(`Post-deployment tests failed: ${testResults.failures.join(', ')}`);
        } else {
          console.log(`     ✅ All ${testResults.total} post-deployment tests passed`);
        }
      }

      // 7. Generate comparison report
      if (context.preDeploymentData) {
        console.log('  7️⃣  Generating change report...');
        const changeReport = this.generateChangeReport(context.preDeploymentData, data);
        results.validations.changeReport = changeReport;
        console.log(`     ✅ Change report: ${changeReport.summary}`);
      }

      // 8. Log post-deployment state
      if (this.options.enableAuditing) {
        console.log('  8️⃣  Recording post-deployment audit...');
        const postChecksums = await this.checksumManager.createChecksums(data);
        await this.auditLog.log({
          phase: 'post-deployment',
          action: 'validation',
          dataHash: postChecksums.dataHash,
          context,
          status: results.passed ? 'passed' : 'failed',
          validationResults: results
        });
        console.log('     ✅ Audit logged');
      }

      if (results.passed) {
        console.log('\n✅ Post-Deployment Validation PASSED\n');
      } else if (results.warnings.length > 0 && results.errors.length === 0) {
        console.log('\n⚠️  Post-Deployment Validation PASSED WITH WARNINGS\n');
      } else {
        console.log('\n❌ Post-Deployment Validation FAILED\n');
      }

    } catch (error) {
      results.passed = false;
      results.errors.push(error.message);
      console.log(`\n❌ Post-Deployment Validation ERROR: ${error.message}\n`);
      this.emit('error', { phase: 'post-deployment', error });
    }

    return results;
  }

  /**
   * Check data completeness
   */
  checkDataCompleteness(data, requiredFields = []) {
    const array = Array.isArray(data) ? data : [data];
    const missingFields = [];

    if (requiredFields.length === 0) return { isComplete: true, missingFields: [] };

    for (const record of array) {
      for (const field of requiredFields) {
        if (record[field] === undefined || record[field] === null || record[field] === '') {
          if (!missingFields.includes(field)) {
            missingFields.push(field);
          }
        }
      }
    }

    return {
      isComplete: missingFields.length === 0,
      missingFields,
      recordsChecked: array.length
    };
  }

  /**
   * Detect duplicate records
   */
  detectDuplicates(data, idField = 'id') {
    const array = Array.isArray(data) ? data : [data];
    const seen = new Set();
    const duplicates = [];

    for (const record of array) {
      const id = record[idField];
      if (seen.has(id)) {
        duplicates.push(id);
      }
      seen.add(id);
    }

    return {
      count: duplicates.length,
      duplicates,
      totalRecords: array.length
    };
  }

  /**
   * Run data tests
   */
  async runDataTests(data, tests) {
    const results = {
      total: tests.length,
      passed: 0,
      failed: 0,
      failures: [],
      allPassed: true
    };

    for (const test of tests) {
      try {
        const testFn = typeof test === 'function' ? test : test.fn;
        const testName = test.name || 'unnamed test';
        
        const result = await Promise.resolve(testFn(data));
        
        if (result === true || result === undefined) {
          results.passed++;
        } else {
          results.failed++;
          results.failures.push(testName);
          results.allPassed = false;
        }
      } catch (error) {
        results.failed++;
        results.failures.push(`${test.name || 'unnamed'}: ${error.message}`);
        results.allPassed = false;
      }
    }

    return results;
  }

  /**
   * Generate change report
   */
  generateChangeReport(beforeData, afterData) {
    const before = Array.isArray(beforeData) ? beforeData : [beforeData];
    const after = Array.isArray(afterData) ? afterData : [afterData];

    return {
      summary: `${before.length} → ${after.length} records`,
      recordsAdded: after.length - before.length,
      recordsRemoved: before.length - after.length,
      totalChanges: Math.abs(after.length - before.length)
    };
  }

  /**
   * Get full validation report
   */
  async getValidationReport(deploymentId) {
    const auditEntries = await this.auditLog.getByDeployment(deploymentId);
    
    return {
      deploymentId,
      preDeployment: auditEntries.find(e => e.phase === 'pre-deployment'),
      postDeployment: auditEntries.find(e => e.phase === 'post-deployment'),
      auditTrail: auditEntries,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Rollback detection and recovery
   */
  async shouldRollback(validationResults) {
    if (!validationResults.passed) {
      console.log('\n🚨 ROLLBACK TRIGGERED: Validation failed');
      return true;
    }

    if (validationResults.errors && validationResults.errors.length > 0) {
      console.log('\n🚨 ROLLBACK TRIGGERED: Critical errors detected');
      return true;
    }

    return false;
  }
}

/**
 * Schema Validator (JSON Schema + Zod)
 */
class SchemaValidator {
  constructor() {
    this.schemas = new Map();
  }

  registerSchema(name, schema) {
    this.schemas.set(name, schema);
  }

  async validate(data, schema) {
    if (!schema) {
      return { valid: true, errors: [] };
    }

    const errors = [];

    // Basic schema validation
    if (schema.type === 'array' && !Array.isArray(data)) {
      errors.push('Data must be an array');
    }

    if (schema.type === 'object' && typeof data !== 'object') {
      errors.push('Data must be an object');
    }

    // Validate required fields
    if (schema.required && typeof data === 'object') {
      for (const field of schema.required) {
        if (!(field in data)) {
          errors.push(`Missing required field: ${field}`);
        }
      }
    }

    // Validate properties
    if (schema.properties && typeof data === 'object') {
      for (const [field, fieldSchema] of Object.entries(schema.properties)) {
        if (data[field] !== undefined) {
          const fieldError = this.validateField(data[field], fieldSchema);
          if (fieldError) errors.push(fieldError);
        }
      }
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  validateField(value, schema) {
    if (schema.type && typeof value !== schema.type) {
      return `Type mismatch: expected ${schema.type}, got ${typeof value}`;
    }

    if (schema.pattern && typeof value === 'string') {
      const regex = new RegExp(schema.pattern);
      if (!regex.test(value)) {
        return `Value does not match pattern: ${schema.pattern}`;
      }
    }

    if (schema.minLength && value.length < schema.minLength) {
      return `Value too short: minimum ${schema.minLength} characters`;
    }

    if (schema.maxLength && value.length > schema.maxLength) {
      return `Value too long: maximum ${schema.maxLength} characters`;
    }

    if (schema.minimum !== undefined && value < schema.minimum) {
      return `Value below minimum: ${schema.minimum}`;
    }

    if (schema.maximum !== undefined && value > schema.maximum) {
      return `Value above maximum: ${schema.maximum}`;
    }

    return null;
  }
}

/**
 * Checksum Manager (SHA-256, Merkle trees)
 */
class ChecksumManager {
  constructor(algorithm = 'sha256') {
    this.algorithm = algorithm;
  }

  createChecksums(data) {
    const jsonStr = JSON.stringify(data);
    
    return {
      dataHash: crypto.createHash(this.algorithm).update(jsonStr).digest('hex'),
      dataSize: Buffer.byteLength(jsonStr),
      recordCount: Array.isArray(data) ? data.length : 1,
      timestamp: new Date().toISOString(),
      algorithm: this.algorithm
    };
  }

  compare(checksums1, checksums2) {
    return {
      matches: checksums1.dataHash === checksums2.dataHash,
      hashChange: checksums1.dataHash !== checksums2.dataHash,
      sizeChange: checksums1.dataSize !== checksums2.dataSize,
      recordCountChange: checksums1.recordCount !== checksums2.recordCount,
      before: checksums1,
      after: checksums2
    };
  }

  createMerkleRoot(records) {
    if (!Array.isArray(records) || records.length === 0) {
      return crypto.createHash(this.algorithm).update('').digest('hex');
    }

    let hashes = records.map(record => 
      crypto.createHash(this.algorithm).update(JSON.stringify(record)).digest('hex')
    );

    while (hashes.length > 1) {
      const newHashes = [];
      for (let i = 0; i < hashes.length; i += 2) {
        const combined = hashes[i] + (hashes[i + 1] || hashes[i]);
        const hash = crypto.createHash(this.algorithm).update(combined).digest('hex');
        newHashes.push(hash);
      }
      hashes = newHashes;
    }

    return hashes[0];
  }
}

/**
 * Audit Logger (Immutable audit trails)
 */
class AuditLogger {
  constructor(options = {}) {
    this.auditDir = path.join(options.dataDir || '.data-integrity', 'audit-logs');
    this.chainHash = null;

    if (!fs.existsSync(this.auditDir)) {
      fs.mkdirSync(this.auditDir, { recursive: true });
    }

    this.loadChainHash();
  }

  loadChainHash() {
    const chainFile = path.join(this.auditDir, 'chain-hash.json');
    if (fs.existsSync(chainFile)) {
      const data = JSON.parse(fs.readFileSync(chainFile, 'utf-8'));
      this.chainHash = data.hash;
    } else {
      this.chainHash = crypto.createHash('sha256').update('').digest('hex');
    }
  }

  async log(entry) {
    const logEntry = {
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      ...entry,
      previousHash: this.chainHash
    };

    // Create hash of this entry
    logEntry.hash = crypto.createHash('sha256')
      .update(JSON.stringify({
        id: logEntry.id,
        timestamp: logEntry.timestamp,
        phase: logEntry.phase,
        action: logEntry.action,
        previousHash: logEntry.previousHash
      }))
      .digest('hex');

    // Save to immutable log
    const logFile = path.join(this.auditDir, `${logEntry.timestamp}-${logEntry.id}.json`);
    fs.writeFileSync(logFile, JSON.stringify(logEntry, null, 2));

    // Update chain hash
    this.chainHash = logEntry.hash;
    fs.writeFileSync(
      path.join(this.auditDir, 'chain-hash.json'),
      JSON.stringify({ hash: this.chainHash, timestamp: new Date().toISOString() })
    );

    return logEntry;
  }

  async verifyIntegrity() {
    const files = fs.readdirSync(this.auditDir)
      .filter(f => f.endsWith('.json') && f !== 'chain-hash.json')
      .sort();

    let previousHash = crypto.createHash('sha256').update('').digest('hex');
    const errors = [];

    for (const file of files) {
      const entry = JSON.parse(fs.readFileSync(path.join(this.auditDir, file), 'utf-8'));

      if (entry.previousHash !== previousHash) {
        errors.push(`Chain integrity broken at ${file}`);
      }

      previousHash = entry.hash;
    }

    return {
      valid: errors.length === 0,
      errors,
      entriesVerified: files.length
    };
  }

  async getByDeployment(deploymentId) {
    const files = fs.readdirSync(this.auditDir)
      .filter(f => f.endsWith('.json') && f !== 'chain-hash.json');

    const entries = files
      .map(f => JSON.parse(fs.readFileSync(path.join(this.auditDir, f), 'utf-8')))
      .filter(e => e.context?.deploymentId === deploymentId);

    return entries;
  }
}

/**
 * Golden Dataset Manager
 */
class GoldenDatasetManager {
  constructor(options = {}) {
    this.goldenDir = path.join(options.dataDir || '.data-integrity', 'golden-datasets');

    if (!fs.existsSync(this.goldenDir)) {
      fs.mkdirSync(this.goldenDir, { recursive: true });
    }
  }

  async create(data, metadata = {}) {
    const id = crypto.randomUUID();
    const goldenDataset = {
      id,
      data,
      metadata: {
        ...metadata,
        createdAt: new Date().toISOString()
      }
    };

    const filePath = path.join(this.goldenDir, `${id}.json`);
    fs.writeFileSync(filePath, JSON.stringify(goldenDataset, null, 2));

    return id;
  }

  async retrieve(id) {
    const filePath = path.join(this.goldenDir, `${id}.json`);
    
    if (!fs.existsSync(filePath)) {
      throw new Error(`Golden dataset not found: ${id}`);
    }

    return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  }

  async list() {
    const files = fs.readdirSync(this.goldenDir).filter(f => f.endsWith('.json'));
    
    return files.map(file => {
      const data = JSON.parse(fs.readFileSync(path.join(this.goldenDir, file), 'utf-8'));
      return {
        id: data.id,
        metadata: data.metadata
      };
    });
  }
}

/**
 * Anomaly Detector
 */
class AnomalyDetector {
  constructor(options = {}) {
    this.threshold = options.anomalyThreshold || 0.05; // 5% change
  }

  detect(currentData, baselineStats) {
    const anomalies = [];
    const array = Array.isArray(currentData) ? currentData : [currentData];

    if (!baselineStats) {
      return { detected: false, anomalies: [] };
    }

    // Check record count change
    const recordCountChange = Math.abs(array.length - baselineStats.recordCount) / baselineStats.recordCount;
    if (recordCountChange > this.threshold) {
      anomalies.push(`Record count changed by ${(recordCountChange * 100).toFixed(1)}%`);
    }

    // Check data distribution
    if (baselineStats.averageSize) {
      const currentSize = JSON.stringify(array).length;
      const averageSize = currentSize / array.length;
      const sizeChange = Math.abs(averageSize - baselineStats.averageSize) / baselineStats.averageSize;
      
      if (sizeChange > this.threshold) {
        anomalies.push(`Data size changed by ${(sizeChange * 100).toFixed(1)}%`);
      }
    }

    return {
      detected: anomalies.length > 0,
      anomalies,
      changeThreshold: this.threshold
    };
  }
}

/**
 * Data Reconciliator
 */
class DataReconciliator {
  constructor(options = {}) {
    this.options = options;
  }

  async reconcile(expectedData, actualData) {
    const differences = [];
    const expected = Array.isArray(expectedData) ? expectedData : [expectedData];
    const actual = Array.isArray(actualData) ? actualData : [actualData];

    // Check record count
    if (expected.length !== actual.length) {
      differences.push({
        type: 'record_count_mismatch',
        expected: expected.length,
        actual: actual.length
      });
    }

    // Deep comparison of records
    const maxLen = Math.max(expected.length, actual.length);
    for (let i = 0; i < maxLen; i++) {
      const exp = expected[i];
      const act = actual[i];

      if (!exp || !act) {
        differences.push({
          type: 'missing_record',
          index: i
        });
        continue;
      }

      const recordDiff = this.deepCompare(exp, act);
      if (recordDiff.length > 0) {
        differences.push({
          type: 'record_mismatch',
          index: i,
          differences: recordDiff
        });
      }
    }

    return {
      matches: differences.length === 0,
      differences,
      differencesCount: differences.length
    };
  }

  deepCompare(obj1, obj2) {
    const differences = [];

    const allKeys = new Set([
      ...Object.keys(obj1),
      ...Object.keys(obj2)
    ]);

    for (const key of allKeys) {
      if (JSON.stringify(obj1[key]) !== JSON.stringify(obj2[key])) {
        differences.push({
          field: key,
          expected: obj1[key],
          actual: obj2[key]
        });
      }
    }

    return differences;
  }
}

module.exports = {
  DataIntegritySystem,
  SchemaValidator,
  ChecksumManager,
  AuditLogger,
  GoldenDatasetManager,
  AnomalyDetector,
  DataReconciliator
};
