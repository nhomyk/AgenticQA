/**
 * AgenticQA Data Integrity CI/CD Integration
 * Integrates data validation into the deployment pipeline
 */

const {
  DataIntegritySystem,
  SchemaValidator,
  ChecksumManager,
  AuditLogger,
  GoldenDatasetManager,
  AnomalyDetector,
  DataReconciliator
} = require('./data-integrity-system');

const {
  DataTestFramework,
  DataTestSuites,
  SnapshotTester
} = require('./data-test-framework');

/**
 * CI/CD Data Validation Pipeline
 */
class DataValidationPipeline {
  constructor(options = {}) {
    this.options = {
      environment: options.environment || 'production',
      rollbackOnFailure: options.rollbackOnFailure !== false,
      enableAnomalyDetection: options.enableAnomalyDetection !== false,
      verboseLogging: options.verboseLogging !== false,
      ...options
    };

    this.integritySystem = new DataIntegritySystem(options);
    this.testFramework = new DataTestFramework();
    this.snapshotTester = new SnapshotTester(options.snapshotDir);

    this.deploymentId = this.generateDeploymentId();
    this.preDeploymentState = null;
    this.validationResults = {
      pre: null,
      post: null
    };

    console.log(`\n🔐 Data Validation Pipeline initialized`);
    console.log(`   Deployment ID: ${this.deploymentId}`);
    console.log(`   Environment: ${this.options.environment}\n`);
  }

  /**
   * Generate unique deployment ID
   */
  generateDeploymentId() {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const random = Math.random().toString(36).substring(2, 8);
    return `deploy-${timestamp}-${random}`;
  }

  /**
   * Phase 1: Pre-Deployment Validation
   */
  async validatePreDeployment(data, options = {}) {
    console.log('\n═══════════════════════════════════════════════════════');
    console.log('PHASE 1: PRE-DEPLOYMENT VALIDATION');
    console.log('═══════════════════════════════════════════════════════\n');

    // Store pre-deployment state
    this.preDeploymentState = {
      data,
      timestamp: new Date().toISOString(),
      ...options
    };

    // Configure validation context
    const validationContext = {
      deploymentId: this.deploymentId,
      version: options.version || '1.0.0',
      description: options.description || 'Automated deployment',
      schema: options.schema,
      requiredFields: options.requiredFields || ['id'],
      idField: options.idField || 'id',
      tests: options.tests || [],
      createGolden: options.createGolden || false,
      ...options
    };

    // Run pre-deployment validation
    const preResults = await this.integritySystem.validatePreDeployment(data, validationContext);

    // Run additional data tests
    if (options.dataTests) {
      console.log('\n📋 Running custom data tests...');
      const testResults = await options.dataTests.runAll(data);
      preResults.validations.customTests = testResults;

      if (!testResults.allPassed) {
        preResults.passed = false;
        preResults.errors.push(`Custom tests failed: ${testResults.failed} failures`);
      }
    }

    // Create data snapshot for later comparison
    if (options.snapshotName) {
      console.log(`\n📸 Creating data snapshot: ${options.snapshotName}`);
      this.snapshotTester.createSnapshot(options.snapshotName, data);
    }

    // Extract baseline statistics for anomaly detection
    if (this.options.enableAnomalyDetection) {
      const array = Array.isArray(data) ? data : [data];
      preResults.baselineStats = {
        recordCount: array.length,
        averageSize: JSON.stringify(data).length / array.length,
        timestamp: new Date().toISOString()
      };
    }

    this.validationResults.pre = preResults;

    if (!preResults.passed && this.options.rollbackOnFailure) {
      throw new Error('Pre-deployment validation failed - deployment blocked');
    }

    return preResults;
  }

  /**
   * Phase 2: Deployment (Agent execution)
   */
  async executeDeployment(deploymentFn, data, context = {}) {
    console.log('\n═══════════════════════════════════════════════════════');
    console.log('PHASE 2: DEPLOYMENT EXECUTION');
    console.log('═══════════════════════════════════════════════════════\n');

    console.log('🚀 Executing deployment...\n');

    try {
      const result = await Promise.resolve(deploymentFn(data, context));
      console.log('✅ Deployment completed successfully\n');
      return result;
    } catch (error) {
      console.log(`\n❌ Deployment failed: ${error.message}\n`);
      throw error;
    }
  }

  /**
   * Phase 3: Post-Deployment Validation
   */
  async validatePostDeployment(data, options = {}) {
    console.log('\n═══════════════════════════════════════════════════════');
    console.log('PHASE 3: POST-DEPLOYMENT VALIDATION');
    console.log('═══════════════════════════════════════════════════════\n');

    // Prepare validation context with pre-deployment data
    const validationContext = {
      deploymentId: this.deploymentId,
      schema: options.schema || this.preDeploymentState.schema,
      preDeploymentChecksums: this.validationResults.pre?.validations?.checksums,
      preDeploymentStats: this.validationResults.pre?.baselineStats,
      preDeploymentData: this.preDeploymentState.data,
      goldenDatasetId: this.validationResults.pre?.validations?.goldenDataset?.id,
      tests: options.tests || this.preDeploymentState.tests,
      ...options
    };

    // Run post-deployment validation
    const postResults = await this.integritySystem.validatePostDeployment(data, validationContext);

    // Compare snapshots if created
    if (this.preDeploymentState.snapshotName) {
      console.log(`\n📸 Comparing data snapshot: ${this.preDeploymentState.snapshotName}`);
      const snapshotComparison = this.snapshotTester.compareSnapshot(
        this.preDeploymentState.snapshotName,
        data
      );
      postResults.validations.snapshotComparison = snapshotComparison;

      if (!snapshotComparison.matches) {
        postResults.warnings.push(`Data snapshot mismatch: ${snapshotComparison.message || 'Hash differs'}`);
      } else {
        console.log('     ✅ Snapshot matches baseline');
      }
    }

    // Run additional data tests (same tests as pre-deployment)
    if (this.preDeploymentState.tests) {
      console.log('\n📋 Running post-deployment data tests...');
      const testResults = await this.testFramework.runAll(data);
      postResults.validations.postTests = testResults;

      if (!testResults.allPassed) {
        postResults.passed = false;
        postResults.errors.push(`Post-deployment tests failed: ${testResults.failed} failures`);
      }
    }

    this.validationResults.post = postResults;

    // Determine if rollback is needed
    const shouldRollback = await this.integritySystem.shouldRollback(postResults);

    return {
      ...postResults,
      shouldRollback,
      deploymentId: this.deploymentId
    };
  }

  /**
   * Complete deployment workflow
   */
  async deployWithValidation(preData, deploymentFn, options = {}) {
    try {
      // Phase 1: Pre-deployment validation
      console.log('\n🔍 Starting pre-deployment validation...');
      const preResults = await this.validatePreDeployment(preData, options.pre || {});

      if (!preResults.passed) {
        console.log('\n🚫 Pre-deployment validation failed - aborting deployment');
        return {
          success: false,
          phase: 'pre-deployment',
          results: preResults
        };
      }

      // Phase 2: Execute deployment
      console.log('\n🚀 Proceeding with deployment...');
      const deploymentResult = await this.executeDeployment(
        deploymentFn,
        preData,
        options.deployment || {}
      );

      // Phase 3: Post-deployment validation
      console.log('\n✅ Validating post-deployment state...');
      const postResults = await this.validatePostDeployment(
        deploymentResult,
        options.post || {}
      );

      if (postResults.shouldRollback) {
        console.log('\n🔄 ROLLBACK TRIGGERED - Deployment validation failed');
        
        if (options.rollbackFn) {
          console.log('🔧 Executing rollback...');
          await options.rollbackFn();
          console.log('✅ Rollback completed');
        }

        return {
          success: false,
          phase: 'post-deployment',
          results: postResults,
          rolledBack: true
        };
      }

      // Success
      console.log('\n═══════════════════════════════════════════════════════');
      console.log('✅ DEPLOYMENT SUCCESSFUL - ALL VALIDATIONS PASSED');
      console.log('═══════════════════════════════════════════════════════\n');

      return {
        success: true,
        deploymentId: this.deploymentId,
        preResults,
        postResults,
        summary: this.generateDeploymentSummary()
      };

    } catch (error) {
      console.log(`\n❌ Deployment error: ${error.message}\n`);

      return {
        success: false,
        error: error.message,
        deploymentId: this.deploymentId
      };
    }
  }

  /**
   * Generate deployment summary report
   */
  generateDeploymentSummary() {
    const pre = this.validationResults.pre;
    const post = this.validationResults.post;

    return {
      deploymentId: this.deploymentId,
      timestamp: new Date().toISOString(),
      preDeployment: {
        validations: Object.keys(pre?.validations || {}).length,
        passed: pre?.passed,
        errors: pre?.errors?.length || 0
      },
      postDeployment: {
        validations: Object.keys(post?.validations || {}).length,
        passed: post?.passed,
        errors: post?.errors?.length || 0,
        warnings: post?.warnings?.length || 0
      },
      dataIntegrity: {
        checksumMatch: post?.validations?.checksumComparison?.matches,
        snapshotMatch: post?.validations?.snapshotComparison?.matches,
        anomaliesDetected: post?.validations?.anomalies?.detected,
        auditIntegrityVerified: post?.validations?.auditIntegrity?.valid
      }
    };
  }

  /**
   * Get detailed validation report
   */
  async getValidationReport() {
    return {
      deploymentId: this.deploymentId,
      timestamp: new Date().toISOString(),
      preDeployment: this.validationResults.pre,
      postDeployment: this.validationResults.post,
      auditTrail: await this.integritySystem.auditLog.getByDeployment(this.deploymentId)
    };
  }
}

/**
 * Deployment validator helper
 */
class DeploymentValidator {
  /**
   * Validate agent-generated data
   */
  static validateAgentOutput(agentOutput, schema) {
    const validator = new SchemaValidator();
    return validator.validate(agentOutput, schema);
  }

  /**
   * Create pre-defined validation config for common scenarios
   */
  static getComplianceValidationConfig() {
    return {
      schema: {
        type: 'array',
        required: ['id', 'timestamp', 'status', 'checksum']
      },
      requiredFields: ['id', 'timestamp', 'status', 'checksum', 'findings'],
      fieldFormats: {
        id: 'uuid',
        timestamp: 'iso-date',
        checksum: 'sha256'
      },
      idField: 'id'
    };
  }

  /**
   * Create snapshot-based validation
   */
  static createSnapshotValidation(snapshotName) {
    return {
      snapshotName,
      createGolden: false
    };
  }
}

module.exports = {
  DataValidationPipeline,
  DeploymentValidator,
  DataIntegritySystem,
  DataTestFramework,
  DataTestSuites,
  SnapshotTester
};
