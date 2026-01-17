/**
 * SafeguardPipeline
 * Orchestrates all safety mechanisms: gatekeeper, rollback monitor, and audit trail
 * Entry point for integrating safeguards into the agent workflow
 */

const PipelineGatekeeper = require('./gatekeeper');
const RollbackMonitor = require('./rollback-monitor');
const AuditTrail = require('./audit-trail');

class SafeguardPipeline {
  constructor(config = {}) {
    this.config = {
      enableGatekeeper: config.enableGatekeeper ?? true,
      enableRollback: config.enableRollback ?? true,
      enableAudit: config.enableAudit ?? true,
      ...config
    };

    // Initialize safeguard components
    this.gatekeeper = new PipelineGatekeeper(config.gatekeeper || {});
    this.rollbackMonitor = new RollbackMonitor(config.rollback || {});
    this.auditTrail = new AuditTrail(config.audit || {});

    this.lastValidation = null;
  }

  /**
   * Main entry point: validate and monitor agent changes
   */
  async processAgentChanges(changes, agent, context = {}) {
    console.log(`\n🔐 [SAFEGUARDS] Processing ${changes.length} changes from ${agent.name}`);

    // Step 1: Validate changes
    const validation = await this.validateChanges(changes, agent);

    if (!validation.passed) {
      console.error(`❌ [SAFEGUARDS] Validation failed: ${validation.reason}`);
      await this.auditTrail.logEvent({
        agent,
        action: 'VALIDATION_FAILED',
        changes,
        result: 'REJECTED',
        riskScore: validation.riskScore || 0,
        metadata: { reason: validation.reason, violations: validation.violations }
      });
      return { success: false, validation };
    }

    console.log(`✅ [SAFEGUARDS] Validation passed (risk: ${(validation.riskScore * 100).toFixed(1)}%)`);

    // Step 2: Log to audit trail
    const auditEntry = await this.auditTrail.logEvent({
      agent,
      action: 'CHANGES_VALIDATED',
      changes,
      result: 'APPROVED',
      riskScore: validation.riskScore,
      metadata: { violations: validation.violations }
    });

    // Step 3: Apply changes (in real flow, this would be a git commit)
    console.log(`📝 [SAFEGUARDS] Ready to apply ${changes.length} changes`);

    // Step 4: Create deployment object for monitoring
    const deployment = {
      id: `DEPLOY-${Date.now()}`,
      timestamp: Date.now(),
      agentId: agent.id,
      changes,
      version: context.version || '1.0.0',
      status: 'PENDING'
    };

    // Step 5: Start rollback monitoring (if enabled)
    if (this.config.enableRollback) {
      console.log(`📊 [SAFEGUARDS] Starting post-deployment monitoring`);

      // Monitor in background if async enabled
      if (context.asyncMonitoring) {
        this.rollbackMonitor.monitorDeployment(deployment).catch(error => {
          console.error('[SAFEGUARDS] Monitoring error:', error);
        });
      } else {
        // Wait for monitoring (useful for testing)
        const monitorResult = await this.rollbackMonitor.monitorDeployment(deployment);
        if (monitorResult.rolledBack) {
          console.error(`🚨 [SAFEGUARDS] Deployment rolled back due to metric degradation`);
          return { success: false, deployment, monitorResult };
        }
      }
    }

    return {
      success: true,
      validation,
      auditEntry,
      deployment,
      summary: `Successfully processed ${changes.length} changes from ${agent.name}`
    };
  }

  /**
   * Validate changes using gatekeeper
   */
  async validateChanges(changes, agent) {
    if (!this.config.enableGatekeeper) {
      return { passed: true, riskScore: 0 };
    }

    const result = await this.gatekeeper.validateAgentChanges(changes, agent);
    this.lastValidation = result;
    return result;
  }

  /**
   * Get safeguard status
   */
  getStatus() {
    return {
      enabled: {
        gatekeeper: this.config.enableGatekeeper,
        rollback: this.config.enableRollback,
        audit: this.config.enableAudit
      },
      gatekeeper: {
        auditLogSize: this.gatekeeper.auditLog.length,
        recentValidations: this.gatekeeper.getAuditLog(5)
      },
      rollback: {
        rollbackCount: this.rollbackMonitor.rollbackHistory.length,
        recentRollbacks: this.rollbackMonitor.getRollbackHistory(5)
      },
      audit: {
        totalEntries: this.auditTrail.entries.length,
        recentAlerts: this.auditTrail.getAlerts(5),
        integrityStatus: this.auditTrail.verifyIntegrity()
      }
    };
  }

  /**
   * Generate compliance report
   */
  generateComplianceReport(startDate, endDate) {
    return this.auditTrail.generateComplianceReport(startDate, endDate);
  }

  /**
   * Export audit logs
   */
  exportAuditLogs(format = 'json', filters = {}) {
    if (format === 'csv') {
      return this.auditTrail.exportToCSV(filters);
    }
    return this.auditTrail.exportToJSON(filters);
  }

  /**
   * Verify audit trail integrity
   */
  verifyIntegrity() {
    return this.auditTrail.verifyIntegrity();
  }

  /**
   * Reset safeguards (for testing only)
   */
  reset() {
    this.gatekeeper.reset();
    this.auditTrail.clear();
  }
}

module.exports = SafeguardPipeline;
