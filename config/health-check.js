/**
 * Health Check Endpoint
 * Monitors system health and API connectivity
 */

class HealthCheck {
  constructor(config, apiClient) {
    this.config = config;
    this.apiClient = apiClient;
    this.startTime = Date.now();
  }

  /**
   * Get comprehensive health status
   */
  async getHealthStatus() {
    const status = {
      status: 'healthy',
      timestamp: new Date().toISOString(),
      uptime: Math.floor((Date.now() - this.startTime) / 1000),
      checks: {
        api: await this.checkGitHubAPI(),
        rateLimit: this.checkRateLimit(),
        memory: this.checkMemory(),
        performance: this.checkPerformance()
      }
    };

    // Determine overall status
    const failedChecks = Object.values(status.checks).filter(c => c.status !== 'healthy');
    status.status = failedChecks.length === 0 ? 'healthy' : 
                   failedChecks.some(c => c.status === 'critical') ? 'critical' : 'degraded';

    return status;
  }

  /**
   * Check GitHub API connectivity
   */
  async checkGitHubAPI() {
    try {
      const repoInfo = await this.apiClient.getRepoInfo();
      return {
        status: repoInfo ? 'healthy' : 'unhealthy',
        message: repoInfo ? 'GitHub API connected' : 'Failed to fetch repo info'
      };
    } catch (error) {
      return {
        status: 'unhealthy',
        message: `GitHub API error: ${error.message}`
      };
    }
  }

  /**
   * Check rate limiting status
   */
  checkRateLimit() {
    const rateLimit = this.apiClient.getRateLimitStatus();
    const utilization = (rateLimit.current / rateLimit.limit) * 100;
    
    return {
      status: utilization < 80 ? 'healthy' : 'degraded',
      utilization: `${Math.round(utilization)}%`,
      remaining: rateLimit.remaining,
      message: `${rateLimit.remaining}/${rateLimit.limit} requests remaining`
    };
  }

  /**
   * Check memory usage
   */
  checkMemory() {
    if (typeof process === 'undefined') return { status: 'unknown' };
    
    const memUsage = process.memoryUsage();
    const heapUsedPercent = (memUsage.heapUsed / memUsage.heapTotal) * 100;

    return {
      status: heapUsedPercent < 80 ? 'healthy' : 'degraded',
      heapUsed: `${Math.round(memUsage.heapUsed / 1024 / 1024)}MB`,
      heapTotal: `${Math.round(memUsage.heapTotal / 1024 / 1024)}MB`,
      utilization: `${Math.round(heapUsedPercent)}%`
    };
  }

  /**
   * Check performance metrics
   */
  checkPerformance() {
    const errorLog = this.apiClient.getErrorLog();
    const recentErrors = errorLog.filter(
      e => Date.now() - new Date(e.timestamp).getTime() < 300000 // Last 5 minutes
    );

    return {
      status: recentErrors.length < 5 ? 'healthy' : 'degraded',
      recentErrors: recentErrors.length,
      totalErrors: errorLog.length,
      message: `${recentErrors.length} errors in last 5 minutes`
    };
  }

  /**
   * Simple liveness probe (for Kubernetes/load balancers)
   */
  isAlive() {
    return true;
  }

  /**
   * Simple readiness probe (for Kubernetes/load balancers)
   */
  async isReady() {
    try {
      await this.checkGitHubAPI();
      return true;
    } catch {
      return false;
    }
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = HealthCheck;
}
