/**
 * Data Integrity Integration Examples
 * Real-world usage patterns for AgenticQA agents
 */

const {
  DataValidationPipeline,
  DataTestSuites,
  DeploymentValidator
} = require('./data-validation-pipeline');

// ============================================================================
// EXAMPLE 1: Fullstack Agent Integration
// ============================================================================

class FullstackAgentWithDataValidation {
  async executeWithValidation(context) {
    const pipeline = new DataValidationPipeline({
      environment: context.environment || 'production'
    });

    // Get input data
    const inputData = await this.loadInputData(context);

    // Pre-deployment validation
    console.log('\n🔍 [Fullstack Agent] Starting data validation...');
    const preResults = await pipeline.validatePreDeployment(inputData, {
      schema: {
        type: 'array',
        required: ['id', 'type', 'changes']
      },
      requiredFields: ['id', 'type', 'changes'],
      idField: 'id',
      dataTests: DataTestSuites.getBasicIntegrityTests(),
      createGolden: context.createGolden || false,
      snapshotName: 'fullstack-agent-input'
    });

    if (!preResults.passed) {
      console.log('❌ Input data validation failed');
      return { success: false, error: preResults.errors };
    }

    // Execute agent logic
    console.log('\n🚀 [Fullstack Agent] Executing agent logic...');
    const modifiedData = await this.processData(inputData);

    // Post-deployment validation
    console.log('\n✅ [Fullstack Agent] Validating output...');
    const postResults = await pipeline.validatePostDeployment(modifiedData, {
      schema: {
        type: 'array',
        required: ['id', 'type', 'changes', 'processedAt']
      },
      preDeploymentChecksums: preResults.validations.checksums
    });

    if (postResults.shouldRollback) {
      console.log('❌ Output validation failed - rollback triggered');
      return { success: false, error: postResults.errors, rolledBack: true };
    }

    return {
      success: true,
      data: modifiedData,
      validationReport: await pipeline.getValidationReport()
    };
  }

  async loadInputData(context) {
    // Load from file, database, or context
    return context.data || [];
  }

  async processData(data) {
    // Your agent's actual logic
    return data.map(item => ({
      ...item,
      processedAt: new Date().toISOString(),
      status: 'processed'
    }));
  }
}

// ============================================================================
// EXAMPLE 2: SDET Agent Integration
// ============================================================================

class SDETAgentWithDataValidation {
  async generateTestsWithValidation(context) {
    const pipeline = new DataValidationPipeline();

    // Input: test findings/requirements
    const testRequirements = await this.loadTestRequirements(context);

    // Pre-validation: ensure requirements are valid
    const preResults = await pipeline.validatePreDeployment(testRequirements, {
      schema: {
        type: 'array',
        required: ['testId', 'functionality', 'priority']
      },
      requiredFields: ['testId', 'functionality'],
      idField: 'testId',
      dataTests: DataTestSuites.getCompletenessTests(['testId', 'functionality'])
    });

    if (!preResults.passed) {
      console.log('Invalid test requirements');
      return { success: false };
    }

    // Generate tests
    const generatedTests = await this.generateTests(testRequirements);

    // Post-validation: ensure generated tests are valid
    const postResults = await pipeline.validatePostDeployment(generatedTests, {
      schema: {
        type: 'array',
        required: ['id', 'name', 'code']
      }
    });

    return {
      success: !postResults.shouldRollback,
      tests: generatedTests,
      metrics: postResults.validations
    };
  }

  async loadTestRequirements(context) {
    return context.requirements || [];
  }

  async generateTests(requirements) {
    // SDET logic here
    return requirements.map(req => ({
      id: req.testId,
      name: `Test: ${req.functionality}`,
      code: `describe('${req.functionality}', () => { /* test code */ });`,
      priority: req.priority,
      generatedAt: new Date().toISOString()
    }));
  }
}

// ============================================================================
// EXAMPLE 3: Compliance Agent Integration
// ============================================================================

class ComplianceAgentWithDataValidation {
  async validateComplianceWithIntegrity(context) {
    const pipeline = new DataValidationPipeline();

    // Load compliance data
    const complianceData = await this.loadComplianceData(context);

    // Pre-deployment: validate input data
    const preResults = await pipeline.validatePreDeployment(complianceData, {
      schema: {
        type: 'array',
        required: ['id', 'standard', 'status', 'findings']
      },
      requiredFields: ['id', 'standard', 'status'],
      idField: 'id',
      dataTests: DataTestSuites.getCompleteSuite({
        requiredFields: ['id', 'standard', 'status', 'checkDate'],
        fieldFormats: {
          id: 'uuid',
          checkDate: 'iso-date'
        },
        businessRules: [
          {
            name: 'Status must be valid',
            validate: (record) => ['compliant', 'non-compliant', 'unknown'].includes(record.status)
          }
        ]
      }),
      createGolden: true,
      snapshotName: 'compliance-baseline'
    });

    if (!preResults.passed) {
      return { success: false, errors: preResults.errors };
    }

    // Compliance analysis
    const complianceResults = await this.analyzeCompliance(complianceData);

    // Post-deployment: validate results
    const postResults = await pipeline.validatePostDeployment(complianceResults, {
      schema: {
        type: 'array',
        required: ['id', 'standard', 'status', 'findings', 'checksum']
      },
      goldenDatasetId: preResults.validations.goldenDataset?.id,
      snapshotName: 'compliance-baseline'
    });

    if (postResults.shouldRollback) {
      console.log('Compliance validation failed - rolling back');
      return { success: false, rolledBack: true };
    }

    return {
      success: true,
      results: complianceResults,
      auditTrail: postResults.validations.auditIntegrity
    };
  }

  async loadComplianceData(context) {
    return context.data || [];
  }

  async analyzeCompliance(data) {
    return data.map(item => ({
      ...item,
      checksum: require('crypto').createHash('sha256').update(JSON.stringify(item)).digest('hex'),
      findings: [],
      analyzedAt: new Date().toISOString()
    }));
  }
}

// ============================================================================
// EXAMPLE 4: Multi-Agent Orchestration with Data Validation
// ============================================================================

class AgentOrchestrationWithValidation {
  async orchestrateAgents(initialData, agents, context = {}) {
    const pipeline = new DataValidationPipeline({
      environment: context.environment || 'production'
    });

    let currentData = initialData;
    const validationResults = [];

    console.log('\n🎭 [Orchestration] Starting multi-agent workflow with validation\n');

    for (let i = 0; i < agents.length; i++) {
      const agent = agents[i];
      console.log(`\n▶️  Agent ${i + 1}/${agents.length}: ${agent.name}`);

      // Pre-validate input for this agent
      const preResult = await pipeline.validatePreDeployment(currentData, {
        schema: agent.inputSchema,
        requiredFields: agent.requiredFields,
        idField: agent.idField || 'id'
      });

      if (!preResult.passed) {
        console.log(`❌ Input validation failed for ${agent.name}`);
        return { success: false, failedAtAgent: agent.name };
      }

      // Execute agent
      try {
        currentData = await agent.execute(currentData);
      } catch (error) {
        console.log(`❌ Agent ${agent.name} failed: ${error.message}`);
        return { success: false, error: error.message, failedAtAgent: agent.name };
      }

      // Post-validate output
      const postResult = await pipeline.validatePostDeployment(currentData, {
        schema: agent.outputSchema
      });

      validationResults.push({
        agent: agent.name,
        preValidation: preResult.passed,
        postValidation: !postResult.shouldRollback
      });

      if (postResult.shouldRollback) {
        console.log(`❌ Output validation failed for ${agent.name}`);
        return { success: false, failedAtAgent: agent.name, shouldRollback: true };
      }

      console.log(`✅ ${agent.name} completed and validated`);
    }

    console.log('\n✅ [Orchestration] All agents completed successfully');

    return {
      success: true,
      finalData: currentData,
      validationResults,
      deploymentId: pipeline.deploymentId
    };
  }
}

// ============================================================================
// EXAMPLE 5: Report Generation with Data Validation
// ============================================================================

class ReportGeneratorWithValidation {
  async generateReport(reportType, data, context = {}) {
    const pipeline = new DataValidationPipeline();

    // Define report schema
    const reportSchema = this.getReportSchema(reportType);

    // Pre-validate input
    const preResults = await pipeline.validatePreDeployment(data, {
      schema: reportSchema,
      requiredFields: this.getRequiredFields(reportType),
      idField: 'id',
      createGolden: context.createGolden || false
    });

    if (!preResults.passed) {
      throw new Error(`Invalid report input: ${preResults.errors.join(', ')}`);
    }

    // Generate report
    const report = await this.compileReport(reportType, data);

    // Validate generated report
    const postResults = await pipeline.validatePostDeployment(report, {
      schema: this.getOutputSchema(reportType)
    });

    if (postResults.shouldRollback) {
      throw new Error('Generated report validation failed');
    }

    return {
      report,
      metadata: {
        generatedAt: new Date().toISOString(),
        reportType,
        validations: postResults.validations
      }
    };
  }

  getReportSchema(type) {
    const schemas = {
      'compliance': {
        type: 'array',
        required: ['id', 'status', 'findings']
      },
      'security': {
        type: 'array',
        required: ['id', 'severity', 'vulnerability']
      },
      'coverage': {
        type: 'object',
        required: ['totalCoverage', 'linesCovered', 'filesAnalyzed']
      }
    };
    return schemas[type] || { type: 'object' };
  }

  getRequiredFields(type) {
    const fields = {
      'compliance': ['id', 'standard', 'status'],
      'security': ['id', 'severity', 'vulnerability', 'remediation'],
      'coverage': ['totalCoverage', 'linesCovered']
    };
    return fields[type] || [];
  }

  getOutputSchema(type) {
    return this.getReportSchema(type);
  }

  async compileReport(type, data) {
    // Report generation logic
    return Array.isArray(data) ? data : [data];
  }
}

// ============================================================================
// EXAMPLE 6: Database Migration with Data Validation
// ============================================================================

class DatabaseMigrationWithValidation {
  async migrateData(sourceTable, targetTable, context = {}) {
    const pipeline = new DataValidationPipeline();

    // Load source data
    const sourceData = await this.loadSourceData(sourceTable);

    // Pre-validate source data
    console.log('📊 Validating source data...');
    const preResults = await pipeline.validatePreDeployment(sourceData, {
      schema: context.sourceSchema,
      requiredFields: context.requiredFields,
      createGolden: true,
      version: context.version || '1.0.0',
      description: `Migration from ${sourceTable} to ${targetTable}`
    });

    if (!preResults.passed) {
      throw new Error(`Source data validation failed: ${preResults.errors.join(', ')}`);
    }

    // Transform data
    console.log('🔄 Transforming data...');
    const transformedData = await this.transformData(sourceData, context.mapping);

    // Post-validate transformed data
    console.log('✅ Validating transformed data...');
    const postResults = await pipeline.validatePostDeployment(transformedData, {
      schema: context.targetSchema,
      preDeploymentChecksums: preResults.validations.checksums,
      goldenDatasetId: preResults.validations.goldenDataset?.id
    });

    if (postResults.shouldRollback) {
      throw new Error('Transformed data validation failed - migration aborted');
    }

    // Write to target
    console.log('💾 Writing to target...');
    await this.writeTargetData(targetTable, transformedData);

    return {
      success: true,
      recordsMigrated: transformedData.length,
      validationReport: postResults
    };
  }

  async loadSourceData(table) {
    // Load from database
    return [];
  }

  async transformData(data, mapping) {
    return data.map(record => {
      const transformed = {};
      for (const [source, target] of Object.entries(mapping)) {
        transformed[target] = record[source];
      }
      return transformed;
    });
  }

  async writeTargetData(table, data) {
    // Write to database
  }
}

// ============================================================================
// Usage Examples
// ============================================================================

async function runExamples() {
  // Example 1: Fullstack Agent
  const fullstackAgent = new FullstackAgentWithDataValidation();
  const result1 = await fullstackAgent.executeWithValidation({
    environment: 'production',
    createGolden: true,
    data: [{
      id: '1',
      type: 'test',
      changes: ['update field A', 'add field B']
    }]
  });

  // Example 2: SDET Agent
  const sdetAgent = new SDETAgentWithDataValidation();
  const result2 = await sdetAgent.generateTestsWithValidation({
    requirements: [{
      testId: '1',
      functionality: 'User login',
      priority: 'high'
    }]
  });

  // Example 3: Compliance Agent
  const complianceAgent = new ComplianceAgentWithDataValidation();
  const result3 = await complianceAgent.validateComplianceWithIntegrity({
    data: [{
      id: 'audit-123',
      standard: 'SOC2',
      status: 'compliant',
      findings: [],
      checkDate: new Date().toISOString()
    }]
  });

  // Example 4: Multi-Agent Orchestration
  const orchestrator = new AgentOrchestrationWithValidation();
  const agents = [
    {
      name: 'Data Cleaner',
      execute: async (data) => data,
      inputSchema: { type: 'array' },
      outputSchema: { type: 'array' }
    },
    {
      name: 'Data Transformer',
      execute: async (data) => data,
      inputSchema: { type: 'array' },
      outputSchema: { type: 'array' }
    }
  ];
  const result4 = await orchestrator.orchestrateAgents([], agents, {
    environment: 'production'
  });

  console.log('\n=== RESULTS ===');
  console.log('Fullstack Agent:', result1.success ? '✅' : '❌');
  console.log('SDET Agent:', result2.success ? '✅' : '❌');
  console.log('Compliance Agent:', result3.success ? '✅' : '❌');
  console.log('Orchestration:', result4.success ? '✅' : '❌');
}

module.exports = {
  FullstackAgentWithDataValidation,
  SDETAgentWithDataValidation,
  ComplianceAgentWithDataValidation,
  AgentOrchestrationWithValidation,
  ReportGeneratorWithValidation,
  DatabaseMigrationWithValidation,
  runExamples
};
