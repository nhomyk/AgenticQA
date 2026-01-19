/**
 * Production Configuration
 * Load environment variables and provide defaults for production deployments
 */

class ProductionConfig {
  constructor() {
    this.loadConfig();
  }

  loadConfig() {
    this.github = {
      token: process.env.GITHUB_TOKEN || '',
      owner: process.env.GITHUB_OWNER || 'nhomyk',
      repo: process.env.GITHUB_REPO || 'AgenticQA',
      apiUrl: 'https://api.github.com'
    };

    this.api = {
      port: parseInt(process.env.API_PORT || '3000'),
      rateLimit: parseInt(process.env.API_RATE_LIMIT || '60'),
      timeout: parseInt(process.env.API_TIMEOUT || '30000')
    };

    this.dashboard = {
      refreshInterval: parseInt(process.env.DASHBOARD_REFRESH_INTERVAL || '30000'),
      pipelineLimit: parseInt(process.env.DASHBOARD_PIPELINE_LIMIT || '20')
    };

    this.security = {
      enableCors: this.parseBoolean(process.env.ENABLE_CORS, true),
      corsOrigin: process.env.CORS_ORIGIN || '*',
      secureHeaders: this.parseBoolean(process.env.SECURE_HEADERS, true)
    };

    this.monitoring = {
      enableErrorLogging: this.parseBoolean(process.env.ENABLE_ERROR_LOGGING, true),
      errorLogLevel: process.env.ERROR_LOG_LEVEL || 'error',
      performanceMonitoring: this.parseBoolean(process.env.PERFORMANCE_MONITORING, true)
    };

    this.environment = {
      nodeEnv: process.env.NODE_ENV || 'production',
      logLevel: process.env.LOG_LEVEL || 'info'
    };
  }

  parseBoolean(value, defaultValue = false) {
    if (typeof value === 'boolean') return value;
    if (typeof value === 'string') return value.toLowerCase() === 'true';
    return defaultValue;
  }

  validate() {
    const errors = [];

    if (!this.github.token) {
      errors.push('GITHUB_TOKEN environment variable is required for production');
    }

    if (this.security.enableCors && this.security.corsOrigin === '*') {
      console.warn('⚠️  Warning: CORS is enabled with wildcard origin. Restrict in production.');
    }

    if (this.api.rateLimit < 10) {
      errors.push('API_RATE_LIMIT should be at least 10 requests per minute');
    }

    return {
      isValid: errors.length === 0,
      errors
    };
  }

  getConfig() {
    return {
      github: this.github,
      api: this.api,
      dashboard: this.dashboard,
      security: this.security,
      monitoring: this.monitoring,
      environment: this.environment
    };
  }
}

module.exports = new ProductionConfig();
