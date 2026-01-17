/**
 * Agent Integration Pattern
 * How to integrate safeguards into your SDET, SRE, and Fullstack agents
 */

const SafeguardPipeline = require('./src/safeguards/pipeline');

/**
 * Pattern 1: Wrap Agent Execution
 * 
 * Add this wrapper to any agent that modifies code
 */
class SafeAgent {
  constructor(agent, safeguardConfig = {}) {
    this.agent = agent;
    this.safeguards = new SafeguardPipeline(safeguardConfig);
  }

  /**
   * Execute agent with safety checks
   */
  async executeWithSafeguards(task, context = {}) {
    console.log(`\n🔐 [SAFE-AGENT] Executing ${this.agent.name} with safeguards\n`);

    try {
      // Step 1: Agent generates changes
      const changes = await this.agent.execute(task);

      // Step 2: Validate with safeguards
      const result = await this.safeguards.processAgentChanges(
        changes,
        {
          id: this.agent.id,
          name: this.agent.name,
          type: this.agent.type,
          successRate: this.agent.successRate,
          confidenceScore: this.agent.confidenceScore
        },
        context
      );

      if (!result.success) {
        console.error(`❌ Safeguards rejected changes: ${result.validation.reason}`);
        return {
          success: false,
          error: result.validation.reason,
          violations: result.validation.violations
        };
      }

      // Step 3: Apply changes
      console.log(`✅ Safeguards approved - applying ${changes.length} changes`);
      const applyResult = await this.agent.applyChanges(changes);

      return {
        success: true,
        changes: changes.length,
        deployment: result.deployment,
        auditEntry: result.auditEntry
      };
    } catch (error) {
      console.error(`❌ [SAFE-AGENT] Error:`, error.message);
      return { success: false, error: error.message };
    }
  }
}

/**
 * Pattern 2: Use with SDET Agent
 */
class SafeSDETAgent {
  constructor(sddetAgent) {
    this.sdet = sddetAgent;
    this.safeguards = new SafeguardPipeline();
  }

  async generateAndValidateTests() {
    const testChanges = await this.sdet.generateTests();
    
    const result = await this.safeguards.processAgentChanges(
      testChanges,
      {
        id: 'SDET-001',
        name: 'SDET Agent v3.1',
        type: 'SDET',
        successRate: 0.94,
        confidenceScore: 0.92
      }
    );

    return {
      validated: result.success,
      changes: testChanges,
      riskScore: result.validation?.riskScore,
      violations: result.validation?.violations
    };
  }
}

/**
 * Pattern 3: Use with SRE Agent (Pipeline Fixing)
 */
class SafeSREAgent {
  constructor(sreAgent) {
    this.sre = sreAgent;
    this.safeguards = new SafeguardPipeline({
      enableRollback: true,
      rollback: {
        monitoringDurationMs: 10 * 60 * 1000 // 10 min for SRE changes
      }
    });
  }

  async fixPipelineWithMonitoring() {
    const fixes = await this.sre.detectAndFixIssues();
    
    const result = await this.safeguards.processAgentChanges(
      fixes,
      {
        id: 'SRE-001',
        name: 'SRE Agent v2.4',
        type: 'SRE',
        successRate: 0.88,
        confidenceScore: 0.85
      },
      { asyncMonitoring: true } // Monitor in background
    );

    return {
      success: result.success,
      fixes: fixes.length,
      monitoring: result.deployment,
      riskScore: result.validation?.riskScore
    };
  }
}

/**
 * Pattern 4: Use with Fullstack Agent (Compliance Fixes)
 */
class SafeFullstackAgent {
  constructor(fullstackAgent) {
    this.fullstack = fullstackAgent;
    this.safeguards = new SafeguardPipeline({
      enableRollback: true,
      rollback: {
        monitoringDurationMs: 20 * 60 * 1000 // 20 min for compliance
      }
    });
  }

  async fixComplianceIssues(framework) {
    const fixes = await this.fullstack.autoFixCompliance(framework);
    
    const result = await this.safeguards.processAgentChanges(
      fixes,
      {
        id: 'FULLSTACK-001',
        name: 'Fullstack Agent v1.2',
        type: 'FULLSTACK',
        successRate: 0.85,
        confidenceScore: 0.82
      }
    );

    // Generate compliance report
    const report = this.safeguards.generateComplianceReport(
      new Date(Date.now() - 24 * 60 * 60 * 1000), // Last 24 hours
      new Date()
    );

    return {
      success: result.success,
      fixes: fixes.length,
      riskScore: result.validation?.riskScore,
      complianceStatus: report
    };
  }
}

/**
 * Pattern 5: Batch Processing with Safeguards
 * 
 * For processing multiple PRs or agents in sequence
 */
class SafeguardedBatchProcessor {
  constructor() {
    this.safeguards = new SafeguardPipeline();
    this.results = [];
  }

  async processBatch(agents) {
    console.log(`\n📦 Processing batch of ${agents.length} agents\n`);

    for (const agent of agents) {
      try {
        const changes = await agent.generateChanges();
        
        const result = await this.safeguards.processAgentChanges(
          changes,
          agent.getMetadata()
        );

        this.results.push({
          agent: agent.name,
          success: result.success,
          changes: changes.length,
          riskScore: result.validation?.riskScore,
          reason: result.validation?.reason
        });
      } catch (error) {
        this.results.push({
          agent: agent.name,
          success: false,
          error: error.message
        });
      }
    }

    return this.getProcessingSummary();
  }

  getProcessingSummary() {
    const successful = this.results.filter(r => r.success).length;
    const failed = this.results.length - successful;

    return {
      total: this.results.length,
      successful,
      failed,
      details: this.results,
      complianceReport: this.safeguards.generateComplianceReport(
        new Date(Date.now() - 24 * 60 * 60 * 1000),
        new Date()
      )
    };
  }
}

/**
 * Pattern 6: Real-world Integration Example
 * 
 * Complete workflow with all safeguards enabled
 */
async function completeWorkflowExample() {
  console.log('=== Complete Workflow with Safeguards ===\n');

  // Initialize safeguards
  const safeguards = new SafeguardPipeline({
    enableGatekeeper: true,
    enableRollback: true,
    enableAudit: true
  });

  // Simulate agent execution
  const agents = [
    {
      id: 'SDET-001',
      name: 'Test Generation Agent',
      type: 'SDET',
      successRate: 0.94,
      confidenceScore: 0.92,
      generateChanges: async () => [
        { filePath: 'src/tests/unit.test.js', type: 'CREATE', linesAdded: 100 },
        { filePath: 'src/tests/e2e.test.js', type: 'CREATE', linesAdded: 80 }
      ]
    },
    {
      id: 'SRE-001',
      name: 'Pipeline Fixer Agent',
      type: 'SRE',
      successRate: 0.88,
      confidenceScore: 0.85,
      generateChanges: async () => [
        { filePath: '.eslintrc.js', type: 'UPDATE', linesAdded: 5, linesRemoved: 3 },
        { filePath: 'jest.config.js', type: 'UPDATE', linesAdded: 10, linesRemoved: 8 }
      ]
    }
  ];

  // Process each agent
  for (const agent of agents) {
    console.log(`\n🤖 Processing ${agent.name}...`);
    
    const changes = await agent.generateChanges();
    const result = await safeguards.processAgentChanges(changes, agent);

    if (result.success) {
      console.log(`✅ ${agent.name}: APPROVED`);
      console.log(`   Changes: ${changes.length}`);
      console.log(`   Risk: ${(result.validation.riskScore * 100).toFixed(1)}%`);
    } else {
      console.log(`❌ ${agent.name}: REJECTED`);
      console.log(`   Reason: ${result.validation.reason}`);
    }
  }

  // Get status
  console.log('\n📊 System Status:\n');
  const status = safeguards.getStatus();
  console.log(`Total audit entries: ${status.audit.totalEntries}`);
  console.log(`Rollback events: ${status.rollback.rollbackCount}`);
  console.log(`Audit integrity: ${status.audit.integrityStatus.integrityVerified ? '✓' : '✗'}`);

  // Export audit logs
  console.log('\n📝 Exporting audit logs...\n');
  const logs = safeguards.exportAuditLogs('json', { limit: 5 });
  console.log(`Exported ${logs.entries.length} audit entries`);

  // Generate compliance report
  console.log('\n📋 Compliance Report:\n');
  const report = safeguards.generateComplianceReport(
    new Date(Date.now() - 24 * 60 * 60 * 1000),
    new Date()
  );
  console.log(`Total changes: ${report.totalChanges}`);
  console.log(`Approved: ${report.changesApproved}`);
  console.log(`Rolled back: ${report.changesRolledBack}`);
}

// Export all patterns
module.exports = {
  SafeAgent,
  SafeSDETAgent,
  SafeSREAgent,
  SafeFullstackAgent,
  SafeguardedBatchProcessor,
  completeWorkflowExample
};

// Run example if executed directly
if (require.main === module) {
  completeWorkflowExample().catch(console.error);
}
