/**
 * RollbackMonitor
 * Monitors deployment metrics and triggers automatic rollback if degradation detected
 * Provides safety net for agent-generated changes in production
 */

class RollbackMonitor {
  constructor(config = {}) {
    this.config = {
      enableMonitoring: config.enableMonitoring ?? true,
      monitoringDurationMs: config.monitoringDurationMs ?? 30 * 60 * 1000, // 30 min default
      pollIntervalMs: config.pollIntervalMs ?? 5000, // 5 second checks
      thresholds: {
        errorRateIncreasePercent: config.thresholds?.errorRateIncreasePercent ?? 50,
        latencyIncreasePercent: config.thresholds?.latencyIncreasePercent ?? 30,
        memoryLeakMB: config.thresholds?.memoryLeakMB ?? 100,
        cpuSpikePercent: config.thresholds?.cpuSpikePercent ?? 40,
        failedTestsThreshold: config.thresholds?.failedTestsThreshold ?? 5
      },
      enableLogging: config.enableLogging ?? true
    };

    this.metricsBaseline = null;
    this.deployments = [];
    this.rollbackHistory = [];
  }

  /**
   * Start monitoring a deployment
   */
  async monitorDeployment(deployment) {
    if (!this.config.enableMonitoring) {
      console.log('[ROLLBACK] Monitoring disabled');
      return { monitored: false, reason: 'Monitoring disabled' };
    }

    // Record baseline metrics
    this.metricsBaseline = this.captureMetricsSnapshot();

    const startTime = Date.now();
    const monitoringDeadline = startTime + this.config.monitoringDurationMs;

    console.log(`[ROLLBACK] Starting ${(this.config.monitoringDurationMs / 1000 / 60).toFixed(1)}min monitoring for deployment ${deployment.id}`);

    // Polling loop
    while (Date.now() < monitoringDeadline) {
      const currentMetrics = this.captureMetricsSnapshot();
      const degradation = this.calculateDegradation(this.metricsBaseline, currentMetrics);

      // Check for rollback triggers
      if (this.shouldRollback(degradation)) {
        await this.triggerRollback(deployment, degradation);
        return { success: true, rolledBack: true, degradation };
      }

      // Wait before next check
      await this.sleep(this.config.pollIntervalMs);
    }

    // Monitoring completed successfully
    this.logSuccess(deployment);
    return { success: true, rolledBack: false, duration: this.config.monitoringDurationMs };
  }

  /**
   * Determine if metrics degradation warrants rollback
   */
  shouldRollback(degradation) {
    const { thresholds } = this.config;

    // Check each metric against its threshold
    const checks = {
      errorRateSpike: degradation.errorRateIncrease > thresholds.errorRateIncreasePercent,
      latencyDegradation: degradation.latencyIncrease > thresholds.latencyIncreasePercent,
      memoryLeak: degradation.memoryLeak > thresholds.memoryLeakMB,
      cpuSpike: degradation.cpuSpike > thresholds.cpuSpikePercent,
      testFailures: degradation.failedTestIncrease > thresholds.failedTestsThreshold
    };

    const triggered = Object.entries(checks)
      .filter(([_, value]) => value)
      .map(([key]) => key);

    if (triggered.length > 0) {
      degradation.triggeredChecks = triggered;
      degradation.severity = this.calculateSeverity(triggered.length);
      return true;
    }

    return false;
  }

  /**
   * Calculate degradation between baseline and current metrics
   */
  calculateDegradation(baseline, current) {
    return {
      errorRateIncrease: this.percentChange(baseline.errorRate, current.errorRate),
      latencyIncrease: this.percentChange(baseline.p95Latency, current.p95Latency),
      memoryLeak: current.memoryUsagePercent - baseline.memoryUsagePercent,
      cpuSpike: current.cpuUsagePercent - baseline.cpuUsagePercent,
      failedTestIncrease: current.failedTests - baseline.failedTests,
      timestamp: Date.now()
    };
  }

  /**
   * Calculate percent change between two values
   */
  percentChange(baseline, current) {
    if (baseline === 0) return current > 0 ? 100 : 0;
    return ((current - baseline) / baseline) * 100;
  }

  /**
   * Determine severity level
   */
  calculateSeverity(triggeredCheckCount) {
    if (triggeredCheckCount >= 4) return 'CRITICAL';
    if (triggeredCheckCount >= 3) return 'HIGH';
    if (triggeredCheckCount >= 2) return 'MEDIUM';
    return 'LOW';
  }

  /**
   * Execute rollback
   */
  async triggerRollback(deployment, degradation) {
    const rollbackId = `RB-${Date.now()}`;

    console.error(`🚨 [ROLLBACK] Triggered: ${rollbackId}`);
    console.error(`   Severity: ${degradation.severity}`);
    console.error(`   Triggers: ${degradation.triggeredChecks.join(', ')}`);
    console.error(`   Error rate increase: ${degradation.errorRateIncrease.toFixed(1)}%`);
    console.error(`   Latency increase: ${degradation.latencyIncrease.toFixed(1)}%`);
    console.error(`   Memory leak: ${degradation.memoryLeak.toFixed(1)}MB`);

    // Record rollback event
    const rollbackEntry = {
      id: rollbackId,
      timestamp: Date.now(),
      deploymentId: deployment.id,
      agentId: deployment.agentId,
      reason: degradation.triggeredChecks.join(', '),
      severity: degradation.severity,
      metrics: degradation,
      status: 'EXECUTED'
    };

    this.rollbackHistory.push(rollbackEntry);

    // Simulate rollback actions
    await this.notifyTeam(rollbackEntry);
    await this.createIncident(rollbackEntry);
    await this.disableAgent(deployment.agentId);

    if (this.config.enableLogging) {
      console.log(`[ROLLBACK] Rollback ${rollbackId} completed`);
    }

    return rollbackEntry;
  }

  /**
   * Capture current metrics snapshot
   */
  captureMetricsSnapshot() {
    // In a real implementation, this would fetch from:
    // - Prometheus/Datadog for performance metrics
    // - CI/CD pipeline for test results
    // - Application logs for errors
    // - Process monitoring for memory/CPU

    return {
      timestamp: Date.now(),
      errorRate: this.getErrorRate(),
      p95Latency: this.getP95Latency(),
      p99Latency: this.getP99Latency(),
      memoryUsagePercent: this.getMemoryUsage(),
      cpuUsagePercent: this.getCpuUsage(),
      activeConnections: this.getActiveConnections(),
      requestsPerSecond: this.getRPS(),
      databaseQueryTimeMs: this.getDatabaseQueryTime(),
      failedTests: this.getFailedTestCount(),
      passedTests: this.getPassedTestCount()
    };
  }

  /**
   * Metric collection stubs (would integrate with real monitoring)
   */
  getErrorRate() {
    // Would query Datadog/Prometheus
    return Math.random() * 5; // 0-5% error rate
  }

  getP95Latency() {
    return Math.random() * 1000 + 100; // 100-1100ms
  }

  getP99Latency() {
    return Math.random() * 2000 + 200; // 200-2200ms
  }

  getMemoryUsage() {
    return Math.random() * 80 + 20; // 20-100%
  }

  getCpuUsage() {
    return Math.random() * 60 + 10; // 10-70%
  }

  getActiveConnections() {
    return Math.floor(Math.random() * 5000 + 100);
  }

  getRPS() {
    return Math.floor(Math.random() * 10000 + 1000);
  }

  getDatabaseQueryTime() {
    return Math.random() * 500 + 50; // 50-550ms
  }

  getFailedTestCount() {
    return Math.floor(Math.random() * 3); // 0-2 failed tests
  }

  getPassedTestCount() {
    return Math.floor(Math.random() * 196) + 190; // 190-386 passed tests
  }

  /**
   * Notify team of rollback
   */
  async notifyTeam(rollbackEntry) {
    // In real implementation, would send:
    // - Slack message to #deployments
    // - Email to on-call team
    // - PagerDuty alert for critical issues

    if (this.config.enableLogging) {
      console.log(`[ROLLBACK] Notifying team about ${rollbackEntry.id}`);
    }
  }

  /**
   * Create incident ticket
   */
  async createIncident(rollbackEntry) {
    // In real implementation, would create:
    // - Jira ticket
    // - Linear issue
    // - GitHub issue

    if (this.config.enableLogging) {
      console.log(`[ROLLBACK] Creating incident for ${rollbackEntry.id}`);
    }
  }

  /**
   * Disable agent temporarily
   */
  async disableAgent(agentId) {
    // In real implementation, would:
    // - Update agent status in database
    // - Prevent agent from making further changes
    // - Schedule re-enablement after cooldown

    if (this.config.enableLogging) {
      console.log(`[ROLLBACK] Disabled agent ${agentId} for 2 hours`);
    }
  }

  /**
   * Log successful deployment
   */
  logSuccess(deployment) {
    if (this.config.enableLogging) {
      console.log(`✅ [ROLLBACK] Deployment ${deployment.id} completed monitoring successfully`);
    }
  }

  /**
   * Get rollback history
   */
  getRollbackHistory(limit = 50) {
    return this.rollbackHistory.slice(-limit);
  }

  /**
   * Sleep utility
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

module.exports = RollbackMonitor;
