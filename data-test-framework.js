/**
 * AgenticQA Data Testing Framework
 * Comprehensive pre/post-deployment data validation tests
 */

class DataTestFramework {
  constructor() {
    this.tests = [];
    this.testResults = [];
  }

  /**
   * Register a test
   */
  test(name, fn) {
    this.tests.push({ name, fn });
    return this;
  }

  /**
   * Run all tests
   */
  async runAll(data) {
    console.log('\n🧪 [DATA TESTS] Running validation tests\n');
    
    this.testResults = [];
    let passed = 0;
    let failed = 0;

    for (const test of this.tests) {
      try {
        const result = await Promise.resolve(test.fn(data));
        
        if (result === true || result === undefined) {
          console.log(`  ✅ ${test.name}`);
          this.testResults.push({ name: test.name, status: 'passed' });
          passed++;
        } else {
          console.log(`  ❌ ${test.name}`);
          this.testResults.push({ name: test.name, status: 'failed', error: result });
          failed++;
        }
      } catch (error) {
        console.log(`  ❌ ${test.name}: ${error.message}`);
        this.testResults.push({ 
          name: test.name, 
          status: 'failed', 
          error: error.message 
        });
        failed++;
      }
    }

    const summary = {
      total: this.tests.length,
      passed,
      failed,
      allPassed: failed === 0
    };

    console.log(`\n📊 Test Results: ${passed}/${this.tests.length} passed\n`);

    return summary;
  }

  /**
   * Assertion helper: data exists
   */
  assertDataExists(data) {
    return data !== null && data !== undefined && 
           (Array.isArray(data) ? data.length > 0 : Object.keys(data).length > 0);
  }

  /**
   * Assertion helper: field exists
   */
  assertFieldExists(data, fieldName) {
    const array = Array.isArray(data) ? data : [data];
    return array.every(record => fieldName in record);
  }

  /**
   * Assertion helper: no null fields
   */
  assertNoNullFields(data, requiredFields) {
    const array = Array.isArray(data) ? data : [data];
    return array.every(record => 
      requiredFields.every(field => record[field] !== null && record[field] !== undefined)
    );
  }

  /**
   * Assertion helper: no duplicates
   */
  assertNoDuplicates(data, idField) {
    const array = Array.isArray(data) ? data : [data];
    const ids = array.map(r => r[idField]);
    return new Set(ids).size === ids.length;
  }

  /**
   * Assertion helper: valid format
   */
  assertValidFormat(data, field, format) {
    const array = Array.isArray(data) ? data : [data];
    
    return array.every(record => {
      const value = record[field];
      
      if (format === 'email') {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
      } else if (format === 'uuid') {
        return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
      } else if (format === 'iso-date') {
        return !isNaN(Date.parse(value));
      } else if (format === 'numeric') {
        return !isNaN(value);
      }
      
      return true;
    });
  }
}

/**
 * Pre-defined data test suites
 */
class DataTestSuites {
  /**
   * Basic integrity tests
   */
  static getBasicIntegrityTests() {
    const tests = new DataTestFramework();

    tests.test('Data is not empty', (data) => {
      return tests.assertDataExists(data);
    });

    tests.test('No null or undefined values in critical fields', (data) => {
      return tests.assertNoNullFields(data, ['id', 'createdAt', 'updatedAt']);
    });

    tests.test('No duplicate IDs', (data) => {
      return tests.assertNoDuplicates(data, 'id');
    });

    tests.test('Record count is positive', (data) => {
      const array = Array.isArray(data) ? data : [data];
      return array.length > 0;
    });

    return tests;
  }

  /**
   * Data completeness tests
   */
  static getCompletenessTests(requiredFields = []) {
    const tests = new DataTestFramework();

    for (const field of requiredFields) {
      tests.test(`Field '${field}' exists in all records`, (data) => {
        return tests.assertFieldExists(data, field);
      });

      tests.test(`Field '${field}' has no null values`, (data) => {
        return tests.assertNoNullFields(data, [field]);
      });
    }

    return tests;
  }

  /**
   * Format validation tests
   */
  static getFormatTests(fieldFormats = {}) {
    const tests = new DataTestFramework();

    for (const [field, format] of Object.entries(fieldFormats)) {
      tests.test(`Field '${field}' has valid ${format} format`, (data) => {
        return tests.assertValidFormat(data, field, format);
      });
    }

    return tests;
  }

  /**
   * Relationship integrity tests
   */
  static getRelationshipTests(relationships = []) {
    const tests = new DataTestFramework();

    for (const rel of relationships) {
      tests.test(`Foreign key relationship: ${rel.field} → ${rel.targetField}`, (data) => {
        const array = Array.isArray(data) ? data : [data];
        return array.every(record => {
          const fkValue = record[rel.field];
          return fkValue !== null && fkValue !== undefined;
        });
      });
    }

    return tests;
  }

  /**
   * Data consistency tests
   */
  static getConsistencyTests(consistencyRules = []) {
    const tests = new DataTestFramework();

    for (const rule of consistencyRules) {
      tests.test(`Consistency rule: ${rule.name}`, (data) => {
        const array = Array.isArray(data) ? data : [data];
        return array.every(record => rule.check(record));
      });
    }

    return tests;
  }

  /**
   * Business logic tests
   */
  static getBusinessLogicTests(businessRules = []) {
    const tests = new DataTestFramework();

    for (const rule of businessRules) {
      tests.test(`Business rule: ${rule.name}`, (data) => {
        const array = Array.isArray(data) ? data : [data];
        return array.every(record => rule.validate(record));
      });
    }

    return tests;
  }

  /**
   * Complete test suite (all categories)
   */
  static getCompleteSuite(options = {}) {
    const suites = [
      this.getBasicIntegrityTests()
    ];

    if (options.requiredFields) {
      const completenessTests = this.getCompletenessTests(options.requiredFields);
      suites.push(completenessTests.tests);
    }

    if (options.fieldFormats) {
      const formatTests = this.getFormatTests(options.fieldFormats);
      suites.push(formatTests.tests);
    }

    if (options.relationships) {
      const relTests = this.getRelationshipTests(options.relationships);
      suites.push(relTests.tests);
    }

    if (options.consistencyRules) {
      const consTests = this.getConsistencyTests(options.consistencyRules);
      suites.push(consTests.tests);
    }

    if (options.businessRules) {
      const bizTests = this.getBusinessLogicTests(options.businessRules);
      suites.push(bizTests.tests);
    }

    // Combine all tests
    const combined = new DataTestFramework();
    for (const suite of suites) {
      combined.tests = [...combined.tests, ...suite.tests];
    }

    return combined;
  }
}

/**
 * Snapshot testing for data
 */
class SnapshotTester {
  constructor(snapshotDir = '.snapshots') {
    this.snapshotDir = snapshotDir;
    this.snapshots = new Map();

    if (!require('fs').existsSync(snapshotDir)) {
      require('fs').mkdirSync(snapshotDir, { recursive: true });
    }
  }

  /**
   * Create a snapshot
   */
  createSnapshot(name, data) {
    const crypto = require('crypto');
    const hash = crypto.createHash('sha256')
      .update(JSON.stringify(data))
      .digest('hex');

    const snapshot = {
      name,
      hash,
      data,
      createdAt: new Date().toISOString()
    };

    const fs = require('fs');
    const path = require('path');
    const filepath = path.join(this.snapshotDir, `${name}.json`);
    
    fs.writeFileSync(filepath, JSON.stringify(snapshot, null, 2));
    this.snapshots.set(name, snapshot);

    return snapshot;
  }

  /**
   * Compare against snapshot
   */
  compareSnapshot(name, data) {
    const fs = require('fs');
    const path = require('path');
    const filepath = path.join(this.snapshotDir, `${name}.json`);

    if (!fs.existsSync(filepath)) {
      return {
        matches: false,
        error: `Snapshot not found: ${name}`,
        message: 'Run .createSnapshot() first to create baseline'
      };
    }

    const savedSnapshot = JSON.parse(fs.readFileSync(filepath, 'utf-8'));
    const crypto = require('crypto');
    const currentHash = crypto.createHash('sha256')
      .update(JSON.stringify(data))
      .digest('hex');

    return {
      matches: currentHash === savedSnapshot.hash,
      expectedHash: savedSnapshot.hash,
      actualHash: currentHash,
      snapshotCreatedAt: savedSnapshot.createdAt
    };
  }

  /**
   * Update snapshot (accept new data as baseline)
   */
  updateSnapshot(name, data) {
    return this.createSnapshot(name, data);
  }
}

module.exports = {
  DataTestFramework,
  DataTestSuites,
  SnapshotTester
};
