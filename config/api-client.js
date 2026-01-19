/**
 * API Client with Rate Limiting and Error Handling
 * Handles all GitHub API calls with proper error recovery
 */

class APIClient {
  constructor(config) {
    this.config = config;
    this.rateLimiter = {
      requests: [],
      limit: config.api.rateLimit,
      windowMs: 60000 // 1 minute
    };
    this.requestTimeout = config.api.timeout;
    this.errorLog = [];
  }

  /**
   * Check if rate limit is exceeded
   */
  isRateLimited() {
    const now = Date.now();
    this.rateLimiter.requests = this.rateLimiter.requests.filter(
      time => now - time < this.rateLimiter.windowMs
    );

    const allowed = this.rateLimiter.requests.length < this.rateLimiter.limit;
    if (allowed) {
      this.rateLimiter.requests.push(now);
    }
    return !allowed;
  }

  /**
   * Fetch with timeout and error handling
   */
  async fetchWithTimeout(url, options = {}) {
    if (this.isRateLimited()) {
      throw new Error('Rate limit exceeded. Please try again later.');
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.requestTimeout);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Accept': 'application/vnd.github.v3+json',
          'Authorization': `token ${this.config.github.token}`,
          ...options.headers
        }
      });

      if (!response.ok) {
        const error = new Error(`HTTP ${response.status}: ${response.statusText}`);
        error.status = response.status;
        error.response = response;
        throw error;
      }

      return response;
    } catch (error) {
      this.logError(error, url);
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }

  /**
   * Get recent pipeline runs
   */
  async getRecentPipelines(limit = 20) {
    const url = `${this.config.github.apiUrl}/repos/${this.config.github.owner}/${this.config.github.repo}/actions/runs?per_page=${limit}`;
    
    try {
      const response = await this.fetchWithTimeout(url);
      return await response.json();
    } catch (error) {
      console.error('Failed to fetch pipelines:', error.message);
      return { workflow_runs: [] };
    }
  }

  /**
   * Get repository information
   */
  async getRepoInfo() {
    const url = `${this.config.github.apiUrl}/repos/${this.config.github.owner}/${this.config.github.repo}`;
    
    try {
      const response = await this.fetchWithTimeout(url);
      return await response.json();
    } catch (error) {
      console.error('Failed to fetch repo info:', error.message);
      return null;
    }
  }

  /**
   * Log errors for monitoring
   */
  logError(error, context) {
    const errorEntry = {
      timestamp: new Date().toISOString(),
      message: error.message,
      context,
      status: error.status || 'unknown'
    };

    this.errorLog.push(errorEntry);
    
    // Keep only last 100 errors
    if (this.errorLog.length > 100) {
      this.errorLog.shift();
    }

    if (this.config.monitoring.enableErrorLogging) {
      console.error(`[${errorEntry.timestamp}] API Error:`, errorEntry);
    }
  }

  /**
   * Get error log for monitoring
   */
  getErrorLog() {
    return this.errorLog;
  }

  /**
   * Get rate limit status
   */
  getRateLimitStatus() {
    return {
      current: this.rateLimiter.requests.length,
      limit: this.rateLimiter.limit,
      remaining: this.rateLimiter.limit - this.rateLimiter.requests.length,
      windowMs: this.rateLimiter.windowMs
    };
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = APIClient;
}
