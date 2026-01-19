// OrbitQA SaaS API Server - Development Mode
// In-memory version for local development (no database required)

const express = require('express');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
const cors = require('cors');
const dotenv = require('dotenv');
const path = require('path');
const crypto = require('crypto');

dotenv.config();

const app = express();
const PORT = process.env.SAAS_PORT || 3001;
const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-change-in-production';
const NODE_ENV = process.env.NODE_ENV || 'development';

// 🚨 CRITICAL: Validate security configuration
if (NODE_ENV === 'production') {
  if (!process.env.JWT_SECRET || process.env.JWT_SECRET === 'dev-secret-change-in-production') {
    console.error('🔴 CRITICAL: JWT_SECRET must be set in production!');
    process.exit(1);
  }
  if (process.env.JWT_SECRET.length < 32) {
    console.error('🔴 CRITICAL: JWT_SECRET must be at least 32 characters!');
    process.exit(1);
  }
  console.log('✅ Security: JWT_SECRET validation passed');
}

// Encryption key for GitHub tokens and sensitive data
// IMPORTANT: In production, set ENCRYPTION_KEY environment variable
const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY ? 
  Buffer.from(process.env.ENCRYPTION_KEY, 'hex') : 
  crypto.randomBytes(32);

// Encryption functions for GitHub tokens
function encryptToken(plainText) {
  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv('aes-256-cbc', ENCRYPTION_KEY, iv);
  let encrypted = cipher.update(plainText, 'utf8', 'hex');
  encrypted += cipher.final('hex');
  return iv.toString('hex') + ':' + encrypted;
}

function decryptToken(encryptedText) {
  try {
    const parts = encryptedText.split(':');
    if (parts.length !== 2) throw new Error('Invalid encrypted format');
    
    const iv = Buffer.from(parts[0], 'hex');
    const decipher = crypto.createDecipheriv('aes-256-cbc', ENCRYPTION_KEY, iv);
    let decrypted = decipher.update(parts[1], 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    return decrypted;
  } catch (error) {
    console.error('Token decryption failed:', error.message);
    throw new Error('Failed to decrypt token');
  }
}

// 🔒 SECURITY: Simple in-memory rate limiting for auth endpoints
class RateLimiter {
  constructor(maxAttempts = 5, windowMs = 15 * 60 * 1000) {
    this.maxAttempts = maxAttempts;
    this.windowMs = windowMs;
    this.attempts = new Map();
  }

  check(key) {
    const now = Date.now();
    const record = this.attempts.get(key) || { count: 0, resetTime: now + this.windowMs };

    if (now > record.resetTime) {
      // Window expired, reset
      record.count = 0;
      record.resetTime = now + this.windowMs;
    }

    record.count++;
    this.attempts.set(key, record);

    return {
      allowed: record.count <= this.maxAttempts,
      remaining: Math.max(0, this.maxAttempts - record.count),
      resetTime: record.resetTime
    };
  }
}

const loginLimiter = new RateLimiter(5, 15 * 60 * 1000); // 5 attempts per 15 minutes

// Middleware
// 🔒 SECURITY: Restrict CORS to specific origins
const corsOptions = {
  origin: (origin, callback) => {
    const allowedOrigins = process.env.ALLOWED_ORIGINS 
      ? process.env.ALLOWED_ORIGINS.split(',')
      : ['http://localhost:3001', 'http://127.0.0.1:3001'];
    
    // Allow requests without origin (same-origin, direct access)
    if (!origin) {
      return callback(null, true);
    }
    
    if (allowedOrigins.includes(origin)) {
      callback(null, true);
    } else {
      if (NODE_ENV === 'production') {
        console.warn(`⚠️  CORS: Rejected request from origin: ${origin}`);
      }
      callback(new Error('Not allowed by CORS'));
    }
  },
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
  allowedHeaders: ['Content-Type', 'Authorization'],
};

app.use(cors(corsOptions));
app.use(express.json());

// In-memory storage (reset on server restart)
const db = {
  users: new Map(),
  organizations: new Map(),
  testRuns: new Map(),
  testResults: new Map(),
  apiKeys: new Map(),
  auditLogs: new Map(),
  githubConnections: new Map(), // New: GitHub integration storage
};

// Create default test account
const defaultOrg = {
  id: 'org_default',
  name: 'Default Organization',
  createdAt: new Date(),
};

const defaultUser = {
  id: 'user_default',
  email: 'demo@orbitqa.ai',
  password: bcrypt.hashSync('demo123', 10),
  name: 'Demo User',
  role: 'owner',
  organizationId: defaultOrg.id,
  createdAt: new Date(),
};

db.organizations.set(defaultOrg.id, defaultOrg);
db.users.set(defaultUser.id, defaultUser);

// ===== AUTH MIDDLEWARE =====

function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) return res.sendStatus(401);

  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) return res.sendStatus(403);
    req.user = user;
    next();
  });
}

function authorizeRole(...roles) {
  return (req, res, next) => {
    if (!roles.includes(req.user.role)) {
      return res.status(403).json({ error: 'Insufficient permissions' });
    }
    next();
  };
}

// ===== HELPER FUNCTIONS =====

function generateId(prefix) {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

function generateToken(user) {
  return jwt.sign(
    { id: user.id, email: user.email, role: user.role, organizationId: user.organizationId },
    JWT_SECRET,
    { expiresIn: '24h' }
  );
}

function logAudit(action, userId, organizationId, details) {
  db.auditLogs.set(generateId('audit'), {
    action,
    userId,
    organizationId,
    details,
    timestamp: new Date(),
  });
}

// ===== ROUTES =====

// Root path - redirect to login
app.get('/', (req, res) => {
  res.redirect('/login.html');
});

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    timestamp: new Date(),
    mode: 'development (in-memory)',
    uptime: process.uptime(),
  });
});

// ===== AUTHENTICATION ROUTES =====

app.post('/api/auth/register', async (req, res) => {
  try {
    const { email, password, name, organization } = req.body;

    // Validate input
    if (!email || !password || !name) {
      return res.status(400).json({ error: 'Missing required fields' });
    }

    // Check if user exists
    const existingUser = Array.from(db.users.values()).find(u => u.email === email);
    if (existingUser) {
      return res.status(400).json({ error: 'Email already exists' });
    }

    // Create organization
    const orgId = generateId('org');
    const newOrg = {
      id: orgId,
      name: organization || `${name}'s Organization`,
      createdAt: new Date(),
    };
    db.organizations.set(orgId, newOrg);

    // Hash password
    const hashedPassword = await bcrypt.hash(password, 10);

    // Create user
    const userId = generateId('user');
    const newUser = {
      id: userId,
      email,
      password: hashedPassword,
      name,
      role: 'owner',
      organizationId: orgId,
      createdAt: new Date(),
    };
    db.users.set(userId, newUser);

    logAudit('user_registered', userId, orgId, { email });

    const token = generateToken(newUser);
    res.status(201).json({
      message: 'Account created successfully',
      token,
      user: {
        id: newUser.id,
        email: newUser.email,
        name: newUser.name,
        role: newUser.role,
      },
    });
  } catch (error) {
    console.error('Registration error:', error);
    res.status(500).json({ error: 'Registration failed' });
  }
});

app.post('/api/auth/login', async (req, res) => {
  try {
    // 🔒 SECURITY: Rate limiting on login
    const clientIp = req.ip || req.connection.remoteAddress;
    const identifier = `login_${req.body.email || clientIp}`;
    const rateLimitCheck = loginLimiter.check(identifier);

    if (!rateLimitCheck.allowed) {
      return res.status(429).json({ 
        error: 'Too many login attempts. Please try again later.',
        retryAfter: Math.ceil((rateLimitCheck.resetTime - Date.now()) / 1000)
      });
    }

    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({ error: 'Email and password required' });
    }

    const user = Array.from(db.users.values()).find(u => u.email === email);
    if (!user) {
      // Generic message - don't reveal if email exists
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const isValid = await bcrypt.compare(password, user.password);
    if (!isValid) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    // Reset rate limit on successful login
    loginLimiter.attempts.delete(identifier);

    logAudit('user_login', user.id, user.organizationId, { email });

    const token = generateToken(user);
    res.json({
      message: 'Login successful',
      token,
      user: {
        id: user.id,
        email: user.email,
        name: user.name,
        role: user.role,
      },
    });
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ error: 'Login failed' });
  }
});

app.get('/api/auth/me', authenticateToken, (req, res) => {
  const user = db.users.get(req.user.id);
  if (!user) {
    return res.status(404).json({ error: 'User not found' });
  }

  res.json({
    id: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
    organizationId: user.organizationId,
  });
});

app.post('/api/auth/verify', authenticateToken, (req, res) => {
  res.json({ valid: true, user: req.user });
});

// ===== TEST RUN ROUTES =====

app.post('/api/test-runs', authenticateToken, (req, res) => {
  try {
    const { url, testType, browsers } = req.body;

    if (!url) {
      return res.status(400).json({ error: 'URL is required' });
    }

    const testRunId = generateId('test');
    const newTestRun = {
      id: testRunId,
      organizationId: req.user.organizationId,
      userId: req.user.id,
      url,
      testType: testType || 'full',
      browsers: browsers || ['chromium', 'firefox', 'webkit'],
      status: 'pending',
      createdAt: new Date(),
      startedAt: null,
      completedAt: null,
      resultCount: 0,
    };

    db.testRuns.set(testRunId, newTestRun);
    logAudit('test_run_created', req.user.id, req.user.organizationId, { url, testType });

    // Simulate test starting
    setTimeout(() => {
      const run = db.testRuns.get(testRunId);
      if (run) {
        run.status = 'running';
        run.startedAt = new Date();
      }
    }, 500);

    res.status(201).json(newTestRun);
  } catch (error) {
    console.error('Test run creation error:', error);
    res.status(500).json({ error: 'Failed to create test run' });
  }
});

app.get('/api/test-runs', authenticateToken, (req, res) => {
  try {
    const testRuns = Array.from(db.testRuns.values()).filter(
      t => t.organizationId === req.user.organizationId
    );

    const sortedRuns = testRuns.sort((a, b) => b.createdAt - a.createdAt);
    res.json(sortedRuns);
  } catch (error) {
    console.error('Test runs fetch error:', error);
    res.status(500).json({ error: 'Failed to fetch test runs' });
  }
});

app.get('/api/test-runs/:id', authenticateToken, (req, res) => {
  try {
    const testRun = db.testRuns.get(req.params.id);

    if (!testRun) {
      return res.status(404).json({ error: 'Test run not found' });
    }

    if (testRun.organizationId !== req.user.organizationId) {
      return res.status(403).json({ error: 'Access denied' });
    }

    res.json(testRun);
  } catch (error) {
    console.error('Test run fetch error:', error);
    res.status(500).json({ error: 'Failed to fetch test run' });
  }
});

app.get('/api/test-runs/:id/results', authenticateToken, (req, res) => {
  try {
    const testRun = db.testRuns.get(req.params.id);

    if (!testRun) {
      return res.status(404).json({ error: 'Test run not found' });
    }

    if (testRun.organizationId !== req.user.organizationId) {
      return res.status(403).json({ error: 'Access denied' });
    }

    // Generate sample results
    const results = testRun.browsers.map(browser => ({
      id: generateId('result'),
      testRunId: req.params.id,
      browser,
      status: testRun.status === 'completed' ? 'passed' : 'pending',
      passedTests: Math.floor(Math.random() * 50 + 30),
      failedTests: Math.floor(Math.random() * 5),
      skippedTests: Math.floor(Math.random() * 3),
      duration: Math.floor(Math.random() * 30 + 10),
      timestamp: new Date(),
    }));

    res.json(results);
  } catch (error) {
    console.error('Results fetch error:', error);
    res.status(500).json({ error: 'Failed to fetch results' });
  }
});

app.delete('/api/test-runs/:id', authenticateToken, authorizeRole('owner', 'admin', 'member'), (req, res) => {
  try {
    const testRun = db.testRuns.get(req.params.id);

    if (!testRun) {
      return res.status(404).json({ error: 'Test run not found' });
    }

    if (testRun.organizationId !== req.user.organizationId) {
      return res.status(403).json({ error: 'Access denied' });
    }

    db.testRuns.delete(req.params.id);
    logAudit('test_run_deleted', req.user.id, req.user.organizationId, { testRunId: req.params.id });

    res.json({ message: 'Test run deleted successfully' });
  } catch (error) {
    console.error('Test run deletion error:', error);
    res.status(500).json({ error: 'Failed to delete test run' });
  }
});

// ===== TEAM ROUTES =====

app.get('/api/team/members', authenticateToken, (req, res) => {
  try {
    const members = Array.from(db.users.values()).filter(
      u => u.organizationId === req.user.organizationId
    );

    res.json(
      members.map(m => ({
        id: m.id,
        name: m.name,
        email: m.email,
        role: m.role,
        createdAt: m.createdAt,
      }))
    );
  } catch (error) {
    console.error('Team members fetch error:', error);
    res.status(500).json({ error: 'Failed to fetch team members' });
  }
});

app.post('/api/team/members', authenticateToken, authorizeRole('owner', 'admin'), async (req, res) => {
  try {
    const { email, name, role } = req.body;

    if (!email || !name) {
      return res.status(400).json({ error: 'Email and name required' });
    }

    const existingUser = Array.from(db.users.values()).find(u => u.email === email);
    if (existingUser) {
      return res.status(400).json({ error: 'User already exists' });
    }

    const tempPassword = Math.random().toString(36).substr(2, 9);
    const hashedPassword = await bcrypt.hash(tempPassword, 10);

    const userId = generateId('user');
    const newMember = {
      id: userId,
      email,
      password: hashedPassword,
      name,
      role: role || 'member',
      organizationId: req.user.organizationId,
      createdAt: new Date(),
    };

    db.users.set(userId, newMember);
    logAudit('member_invited', req.user.id, req.user.organizationId, { email, role });

    res.status(201).json({
      message: 'Member invited successfully',
      member: {
        id: newMember.id,
        name: newMember.name,
        email: newMember.email,
        role: newMember.role,
      },
      tempPassword,
    });
  } catch (error) {
    console.error('Member invitation error:', error);
    res.status(500).json({ error: 'Failed to invite member' });
  }
});

app.delete('/api/team/members/:id', authenticateToken, authorizeRole('owner', 'admin'), (req, res) => {
  try {
    const member = db.users.get(req.params.id);

    if (!member) {
      return res.status(404).json({ error: 'Member not found' });
    }

    if (member.organizationId !== req.user.organizationId) {
      return res.status(403).json({ error: 'Access denied' });
    }

    if (member.role === 'owner') {
      return res.status(400).json({ error: 'Cannot remove organization owner' });
    }

    db.users.delete(req.params.id);
    logAudit('member_removed', req.user.id, req.user.organizationId, { memberId: req.params.id });

    res.json({ message: 'Member removed successfully' });
  } catch (error) {
    console.error('Member removal error:', error);
    res.status(500).json({ error: 'Failed to remove member' });
  }
});

// ===== ORGANIZATION ROUTES =====

app.get('/api/settings', authenticateToken, (req, res) => {
  try {
    const org = db.organizations.get(req.user.organizationId);

    if (!org) {
      return res.status(404).json({ error: 'Organization not found' });
    }

    res.json({
      id: org.id,
      name: org.name,
      createdAt: org.createdAt,
      memberCount: Array.from(db.users.values()).filter(
        u => u.organizationId === org.id
      ).length,
    });
  } catch (error) {
    console.error('Settings fetch error:', error);
    res.status(500).json({ error: 'Failed to fetch settings' });
  }
});

app.get('/api/settings/api-key', authenticateToken, (req, res) => {
  try {
    const apiKey = Array.from(db.apiKeys.values()).find(
      k => k.organizationId === req.user.organizationId
    );

    if (apiKey) {
      res.json({ apiKey: apiKey.key });
    } else {
      const newKey = generateId('key');
      db.apiKeys.set(newKey, {
        key: newKey,
        organizationId: req.user.organizationId,
        createdAt: new Date(),
      });
      res.json({ apiKey: newKey });
    }
  } catch (error) {
    console.error('API key fetch error:', error);
    res.status(500).json({ error: 'Failed to fetch API key' });
  }
});

app.post('/api/settings/api-key/regenerate', authenticateToken, authorizeRole('owner', 'admin'), (req, res) => {
  try {
    const oldKey = Array.from(db.apiKeys.values()).find(
      k => k.organizationId === req.user.organizationId
    );

    if (oldKey) {
      db.apiKeys.delete(Array.from(db.apiKeys.entries()).find(e => e[1] === oldKey)[0]);
    }

    const newKey = generateId('key');
    db.apiKeys.set(newKey, {
      key: newKey,
      organizationId: req.user.organizationId,
      createdAt: new Date(),
    });

    logAudit('api_key_regenerated', req.user.id, req.user.organizationId, {});

    res.json({ apiKey: newKey });
  } catch (error) {
    console.error('API key regeneration error:', error);
    res.status(500).json({ error: 'Failed to regenerate API key' });
  }
});

// ===== GITHUB INTEGRATION =====

// GET GitHub connection status
app.get('/api/github/status', (req, res) => {
  try {
    const connection = Array.from(db.githubConnections.values()).pop();
    
    if (connection) {
      res.json({
        connected: true,
        account: connection.account,
        repository: connection.repository,
        lastUsed: connection.lastUsed || 'Never',
        workflowFile: connection.workflowFile || '.github/workflows/ci.yml'
      });
    } else {
      res.json({ connected: false });
    }
  } catch (error) {
    console.error('GitHub status error:', error);
    res.status(500).json({ error: 'Failed to get GitHub status' });
  }
});

// POST Connect GitHub (save token)
app.post('/api/github/connect', (req, res) => {
  try {
    const { token, repository } = req.body;

    if (!token || token.length < 10) {
      return res.status(400).json({ error: 'Invalid GitHub token' });
    }

    // Validate token format (basic check)
    if (!token.startsWith('ghp_') && !token.startsWith('gho_')) {
      return res.status(400).json({ error: 'Invalid token format. Must start with ghp_ or gho_' });
    }

    // 🔒 SECURITY: Bind token to specific user
    let encryptedToken;
    try {
      encryptedToken = encryptToken(token);
    } catch (encryptError) {
      console.error('Token encryption failed:', encryptError);
      return res.status(500).json({ error: 'Failed to securely store token' });
    }

    // Use user-specific key instead of global
    const connectionId = `user_${req.user.id}_github`;
    db.githubConnections.set(connectionId, {
      id: connectionId,
      userId: req.user.id, // 🔒 Associate with specific user
      token: encryptedToken,
      repository: repository || 'unknown',
      account: repository ? repository.split('/')[0] : 'unknown',
      workflowFile: '.github/workflows/ci.yml',
      connectedAt: new Date(),
      lastUsed: null,
    });

    logAudit('github_connected', req.user.id, req.user.organizationId, {
      repository: repository,
    });

    res.json({
      status: 'success',
      message: 'GitHub account connected successfully',
      repository: repository
    });
  } catch (error) {
    console.error('GitHub connection error:', error);
    res.status(500).json({ error: 'Failed to connect GitHub' });
  }
});

// POST Test GitHub connection
app.post('/api/github/test', (req, res) => {
  try {
    const connection = Array.from(db.githubConnections.values()).pop();
    
    if (!connection) {
      return res.status(403).json({ error: 'GitHub not connected' });
    }

    // In a real app, we'd make a test API call to GitHub
    // For now, just verify we have a token
    if (connection.token && connection.token.length > 10) {
      logAudit('github_test_passed', 'system', 'default', {
        repository: connection.repository,
      });

      res.json({
        status: 'success',
        message: 'GitHub connection test passed',
        account: connection.account
      });
    } else {
      throw new Error('Invalid token stored');
    }
  } catch (error) {
    console.error('GitHub test error:', error);
    res.status(500).json({ error: 'GitHub connection test failed: ' + error.message });
  }
});

// POST Disconnect GitHub
app.post('/api/github/disconnect', (req, res) => {
  try {
    // Find and delete the connection
    let found = false;
    for (const [key, conn] of db.githubConnections.entries()) {
      db.githubConnections.delete(key);
      found = true;
      break;
    }

    if (!found) {
      return res.status(404).json({ error: 'GitHub connection not found' });
    }

    logAudit('github_disconnected', 'system', 'default', {});

    res.json({
      status: 'success',
      message: 'GitHub account disconnected'
    });
  } catch (error) {
    console.error('GitHub disconnect error:', error);
    res.status(500).json({ error: 'Failed to disconnect GitHub' });
  }
});

// POST Trigger workflow via GitHub API
app.post('/api/trigger-workflow', async (req, res) => {
  try {
    const { pipelineType, branch } = req.body;
    
    // 🔒 SECURITY: Get token specific to this user
    const connectionId = `user_${req.user.id}_github`;
    const connection = db.githubConnections.get(connectionId);

    if (!connection) {
      return res.status(403).json({ error: 'GitHub not connected. Go to Settings to connect your account.' });
    }

    if (!connection.repository) {
      return res.status(400).json({ error: 'No repository configured' });
    }

    if (!connection.token) {
      return res.status(503).json({ error: 'GitHub token not configured. Please reconnect GitHub.' });
    }

    // ⚠️ SECURITY: Decrypt the token before using
    let decryptedToken;
    try {
      decryptedToken = decryptToken(connection.token);
    } catch (decryptError) {
      console.error('Token decryption failed:', decryptError);
      return res.status(503).json({ error: 'Failed to retrieve GitHub credentials. Please reconnect.' });
    }

    const branchToTrigger = branch || 'main';
    
    // Map pipeline types to workflow inputs
    const pipelineInputs = {
      full: { pipeline_type: 'full' },
      tests: { pipeline_type: 'tests' },
      security: { pipeline_type: 'security' }
    };

    const inputs = pipelineInputs[pipelineType] || pipelineInputs.full;

    try {
      // Call GitHub API to trigger the workflow
      const githubResponse = await fetch(
        `https://api.github.com/repos/${connection.repository}/actions/workflows/ci.yml/dispatches`,
        {
          method: 'POST',
          headers: {
            'Authorization': `token ${decryptedToken}`, // ✅ Use decrypted token
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            ref: branchToTrigger,
            inputs: inputs
          })
        }
      );

      // Check response status
      if (githubResponse.status === 204) {
        // Success - GitHub returns 204 No Content
        connection.lastUsed = new Date();
        
        logAudit('workflow_triggered', req.user.id, req.user.organizationId, {
          repository: connection.repository,
          pipelineType: pipelineType,
          branch: branchToTrigger,
          status: 'success'
        });

        res.json({
          status: 'success',
          message: `✅ Workflow triggered successfully on ${connection.repository} (${branchToTrigger})`,
          pipelineType: pipelineType,
          branch: branchToTrigger,
          repository: connection.repository,
          workflowId: `gh-${Date.now()}`
        });
      } else if (githubResponse.status === 404) {
        // Workflow file not found
        return res.status(404).json({ 
          error: 'Workflow file not found. Make sure .github/workflows/ci.yml exists in your repository.' 
        });
      } else if (githubResponse.status === 401) {
        // Invalid token
        connection.token = null; // Clear the invalid token
        return res.status(403).json({ 
          error: 'GitHub token is invalid or expired. Please reconnect GitHub in Settings.' 
        });
      } else if (githubResponse.status === 422) {
        // Validation error (e.g., branch doesn't exist)
        const errorData = await githubResponse.json();
        return res.status(400).json({ 
          error: `Validation error: ${errorData.message || 'Check repository and branch name.'}` 
        });
      } else {
        const errorData = await githubResponse.text();
        throw new Error(`GitHub API returned ${githubResponse.status}: ${errorData}`);
      }
    } catch (githubError) {
      console.error('GitHub API error:', githubError);
      
      logAudit('workflow_trigger_failed', req.user.id, req.user.organizationId, {
        repository: connection.repository,
        pipelineType: pipelineType,
        branch: branchToTrigger,
        error: githubError.message
      });

      res.status(503).json({ 
        error: `Failed to reach GitHub API: ${githubError.message}` 
      });
    }
  } catch (error) {
    console.error('Workflow trigger error:', error);
    res.status(500).json({ error: 'Failed to trigger workflow: ' + error.message });
  }
});

// ===== ERROR HANDLING =====

// Serve static files BEFORE 404 handler (so static routes are found)
app.use(express.static(path.join(__dirname, 'public')));

app.use((err, req, res, next) => {
  console.error('Server error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

app.use((req, res) => {
  res.status(404).json({ error: 'Route not found' });
});

// ===== START SERVER =====

app.listen(PORT, () => {
  console.log(`\n✅ SaaS API Server running on http://localhost:${PORT}`);
  console.log(`📊 Mode: Development (In-Memory Storage)`);
  console.log(`🔐 Default Credentials:`);
  console.log(`   Email: demo@orbitqa.ai`);
  console.log(`   Password: demo123\n`);
});

process.on('SIGTERM', () => {
  console.log('Server shutting down...');
  process.exit(0);
});
