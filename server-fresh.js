#!/usr/bin/env node

/**
 * AgenticQA Server - Fresh Start
 * Simplified version with proper error handling
 */

// Error handling for uncaught exceptions
process.on('uncaughtException', (err) => {
  console.error('[FATAL] Uncaught Exception:', err);
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('[FATAL] Unhandled Rejection:', reason);
  process.exit(1);
});

try {
  const express = require('express');
  const bodyParser = require('body-parser');
  const path = require('path');
  const rateLimit = require('express-rate-limit');
  const https = require('https');
  
  // Load env
  require('dotenv').config();

  // Create app
  const app = express();
  const PORT = process.env.PORT || 3000;
  const NODE_ENV = process.env.NODE_ENV || 'development';

  // Middleware
  app.use(bodyParser.json({ limit: '100kb' }));
  app.use(express.static(path.join(__dirname, 'public')));

  // Security headers
  app.use((req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('X-XSS-Protection', '1; mode=block');
    next();
  });

  // Rate limiter
  const rateLimiter = rateLimit({
    windowMs: 15000,
    max: 100,
    standardHeaders: true,
    legacyHeaders: false,
  });

  app.use('/api/', rateLimiter);

  // Health endpoint
  app.get('/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
  });

  // Workflow trigger endpoint
  app.post('/api/trigger-workflow', async (req, res) => {
    try {
      const { pipelineType = 'manual', branch = 'main' } = req.body;

      // Validate
      const validTypes = ['full', 'tests', 'security', 'accessibility', 'compliance', 'manual'];
      if (!validTypes.includes(pipelineType)) {
        return res.status(400).json({
          error: 'Invalid pipeline type',
          status: 'error'
        });
      }

      if (!branch || typeof branch !== 'string' || branch.length > 255) {
        return res.status(400).json({
          error: 'Invalid branch',
          status: 'error'
        });
      }

      if (!/^[a-zA-Z0-9._\-/]+$/.test(branch)) {
        return res.status(400).json({
          error: 'Invalid branch format',
          status: 'error'
        });
      }

      const githubToken = process.env.GITHUB_TOKEN;
      if (!githubToken) {
        return res.status(503).json({
          error: 'Service temporarily unavailable',
          status: 'error'
        });
      }

      const payload = {
        ref: branch,
        inputs: {
          pipelineType: pipelineType,
          reason: 'Triggered via dashboard'
        }
      };

      return new Promise((resolve) => {
        const payloadString = JSON.stringify(payload);
        const options = {
          hostname: 'api.github.com',
          port: 443,
          path: '/repos/nhomyk/AgenticQA/actions/workflows/ci.yml/dispatches',
          method: 'POST',
          headers: {
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': `token ${githubToken}`,
            'Content-Type': 'application/json',
            'User-Agent': 'AgenticQA-Dashboard',
            'Content-Length': Buffer.byteLength(payloadString)
          }
        };

        const githubReq = https.request(options, (githubRes) => {
          let responseBody = '';

          githubRes.on('data', (chunk) => {
            responseBody += chunk;
          });

          githubRes.on('end', () => {
            if (githubRes.statusCode === 204) {
              resolve(res.status(200).json({
                status: 'success',
                message: `Pipeline '${pipelineType}' triggered successfully on branch '${branch}'`,
                workflow: 'ci.yml',
                branch: branch,
                pipelineType: pipelineType,
                timestamp: new Date().toISOString()
              }));
            } else if (githubRes.statusCode === 401 || githubRes.statusCode === 403) {
              resolve(res.status(403).json({
                error: 'GitHub token authentication failed',
                status: 'error'
              }));
            } else if (githubRes.statusCode === 404) {
              resolve(res.status(404).json({
                error: 'GitHub workflow not found',
                status: 'error'
              }));
            } else {
              resolve(res.status(502).json({
                error: `GitHub API error: HTTP ${githubRes.statusCode}`,
                status: 'error'
              }));
            }
          });
        });

        githubReq.on('error', (error) => {
          resolve(res.status(502).json({
            error: 'Failed to communicate with GitHub API',
            status: 'error'
          }));
        });

        githubReq.write(payloadString);
        githubReq.end();
      });
    } catch (error) {
      return res.status(500).json({
        error: 'Server error',
        status: 'error'
      });
    }
  });

  // 404 handler
  app.use((req, res) => {
    res.status(404).json({ error: 'Not found' });
  });

  // Error handler
  app.use((err, req, res, next) => {
    console.error('[ERROR]', err);
    res.status(err.status || 500).json({
      error: NODE_ENV === 'production' ? 'Internal server error' : err.message
    });
  });

  // Start server
  const server = app.listen(PORT, '127.0.0.1', () => {
    console.log(`\n[${new Date().toISOString()}] ✅ Server started`);
    console.log(`   URL: http://127.0.0.1:${PORT}`);
    console.log(`   Environment: ${NODE_ENV}`);
    console.log(`   Press Ctrl+C to stop\n`);
  });

  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.error(`\n❌ Port ${PORT} is already in use`);
      console.error(`Kill it: lsof -ti:${PORT} | xargs kill -9\n`);
      process.exit(1);
    } else {
      console.error('\n❌ Server error:', err.message, '\n');
      process.exit(1);
    }
  });

  process.on('SIGINT', () => {
    console.log('\n✓ Shutting down...\n');
    server.close(() => process.exit(0));
  });

} catch (err) {
  console.error('\n❌ Failed to start server');
  console.error('Error:', err.message);
  console.error('\nDiagnostics:');
  console.error('  1. Run: npm install');
  console.error('  2. Check node_modules exists');
  console.error('  3. Check .env file (if needed)\n');
  process.exit(1);
}
