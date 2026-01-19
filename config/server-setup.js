/**
 * Production Server Setup
 * Express middleware and endpoints for production deployment
 */

const express = require('express');
const productionConfig = require('./production.config');
const APIClient = require('./api-client');
const HealthCheck = require('./health-check');

function setupProductionServer(app) {
  // Load and validate configuration
  const config = productionConfig.getConfig();
  const validation = productionConfig.validate();

  if (!validation.isValid) {
    console.error('❌ Configuration validation failed:');
    validation.errors.forEach(err => console.error(`  • ${err}`));
    process.exit(1);
  }

  // Initialize API client and health check
  const apiClient = new APIClient(config);
  const healthCheck = new HealthCheck(config, apiClient);

  // Security Headers Middleware
  app.use((req, res, next) => {
    // Strict Transport Security
    res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
    
    // Content Security Policy
    res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'");
    
    // X-Content-Type-Options
    res.setHeader('X-Content-Type-Options', 'nosniff');
    
    // X-Frame-Options
    res.setHeader('X-Frame-Options', 'SAMEORIGIN');
    
    // X-XSS-Protection
    res.setHeader('X-XSS-Protection', '1; mode=block');
    
    // Referrer-Policy
    res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
    
    // Permissions-Policy
    res.setHeader('Permissions-Policy', 'geolocation=(), microphone=(), camera=()');

    next();
  });

  // CORS Middleware
  if (config.security.enableCors) {
    app.use((req, res, next) => {
      res.setHeader('Access-Control-Allow-Origin', config.security.corsOrigin);
      res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
      res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
      res.setHeader('Access-Control-Max-Age', '3600');

      if (req.method === 'OPTIONS') {
        res.sendStatus(200);
      } else {
        next();
      }
    });
  }

  // Rate Limiting Middleware
  app.use((req, res, next) => {
    if (apiClient.isRateLimited()) {
      return res.status(429).json({
        error: 'Rate limit exceeded',
        message: `Maximum ${config.api.rateLimit} requests per minute allowed`,
        retryAfter: 60
      });
    }
    next();
  });

  // Request Timeout Middleware
  app.use((req, res, next) => {
    res.setTimeout(config.api.timeout, () => {
      res.status(408).json({ error: 'Request timeout' });
    });
    next();
  });

  // Health Check Endpoints

  /**
   * Liveness probe for Kubernetes/load balancers
   * Returns 200 if server is running
   */
  app.get('/healthz', (req, res) => {
    if (healthCheck.isAlive()) {
      res.status(200).json({ status: 'alive' });
    } else {
      res.status(503).json({ status: 'not alive' });
    }
  });

  /**
   * Readiness probe for Kubernetes/load balancers
   * Returns 200 if service is ready to handle requests
   */
  app.get('/readyz', async (req, res) => {
    const isReady = await healthCheck.isReady();
    if (isReady) {
      res.status(200).json({ status: 'ready' });
    } else {
      res.status(503).json({ status: 'not ready' });
    }
  });

  /**
   * Comprehensive health status endpoint
   * Returns detailed system health information
   */
  app.get('/health', async (req, res) => {
    try {
      const status = await healthCheck.getHealthStatus();
      const statusCode = status.status === 'healthy' ? 200 : 
                        status.status === 'degraded' ? 503 : 200;
      res.status(statusCode).json(status);
    } catch (error) {
      res.status(500).json({
        status: 'error',
        message: 'Failed to retrieve health status',
        error: error.message
      });
    }
  });

  /**
   * API metrics endpoint
   * Returns API usage and performance metrics
   */
  app.get('/api/metrics', (req, res) => {
    const rateLimit = apiClient.getRateLimitStatus();
    const errorLog = apiClient.getErrorLog();

    res.json({
      rateLimit,
      errors: {
        total: errorLog.length,
        recent5min: errorLog.filter(e => 
          Date.now() - new Date(e.timestamp).getTime() < 300000
        ).length,
        errorLog: errorLog.slice(-10)
      },
      uptime: Math.floor((Date.now() - healthCheck.startTime) / 1000)
    });
  });

  /**
   * GitHub repository information endpoint
   */
  app.get('/api/github/repo', async (req, res) => {
    try {
      const repoInfo = await apiClient.getRepoInfo();
      res.json(repoInfo);
    } catch (error) {
      res.status(500).json({
        error: 'Failed to fetch repository information',
        message: error.message
      });
    }
  });

  /**
   * Recent pipelines endpoint
   */
  app.get('/api/pipelines', async (req, res) => {
    try {
      const limit = Math.min(parseInt(req.query.limit || 20), 100);
      const pipelines = await apiClient.getRecentPipelines(limit);
      res.json(pipelines);
    } catch (error) {
      res.status(500).json({
        error: 'Failed to fetch pipelines',
        message: error.message
      });
    }
  });

  /**
   * Configuration endpoint (non-sensitive values only)
   */
  app.get('/api/config', (req, res) => {
    res.json({
      environment: config.environment,
      dashboard: config.dashboard,
      api: {
        rateLimit: config.api.rateLimit,
        timeout: config.api.timeout
      }
    });
  });

  // Error handling middleware
  app.use((error, req, res, next) => {
    console.error('Unhandled error:', error);

    res.status(500).json({
      error: 'Internal server error',
      message: config.environment.nodeEnv === 'production' ? 
        'An error occurred processing your request' : 
        error.message
    });
  });

  // 404 Handler
  app.use((req, res) => {
    res.status(404).json({
      error: 'Not found',
      path: req.path
    });
  });

  console.log('✅ Production server middleware configured');
  console.log(`   Environment: ${config.environment.nodeEnv}`);
  console.log(`   Rate Limit: ${config.api.rateLimit} req/min`);
  console.log(`   CORS Enabled: ${config.security.enableCors}`);

  return { apiClient, healthCheck, config };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = setupProductionServer;
}
