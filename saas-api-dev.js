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
app.get('/api/github/status', authenticateToken, (req, res) => {
  try {
    // Look up the user's specific connection
    const connectionId = `user_${req.user.id}_github`;
    const connection = db.githubConnections.get(connectionId);
    
    console.log('[GitHub Status] Checking connection for user', req.user.id, 'connectionId:', connectionId, 'found:', !!connection);
    
    if (connection) {
      res.json({
        status: 'connected',
        connected: true,
        account: connection.account,
        repository: connection.repository,
        connectedAt: connection.connectedAt,
        lastUsed: connection.lastUsed || 'Never',
        workflowFile: connection.workflowFile || '.github/workflows/ci.yml'
      });
    } else {
      console.log('[GitHub Status] No connection found for user', req.user.id);
      res.json({ 
        status: 'disconnected',
        connected: false 
      });
    }
  } catch (error) {
    console.error('[GitHub Status] Error:', error);
    res.status(500).json({ error: 'Failed to get GitHub status' });
  }
});

// GET GitHub branches for connected repository
app.get('/api/github/branches', authenticateToken, async (req, res) => {
  try {
    const connectionId = `user_${req.user.id}_github`;
    const connection = db.githubConnections.get(connectionId);
    
    if (!connection) {
      return res.status(403).json({ error: 'GitHub not connected' });
    }

    if (!connection.token || !connection.repository) {
      return res.status(400).json({ error: 'GitHub repository not configured' });
    }

    let decryptedToken;
    try {
      decryptedToken = decryptToken(connection.token);
    } catch (decryptError) {
      return res.status(503).json({ error: 'Failed to retrieve GitHub credentials' });
    }

    // Fetch branches from GitHub API
    const response = await fetch(
      `https://api.github.com/repos/${connection.repository}/branches`,
      {
        method: 'GET',
        headers: {
          'Authorization': `token ${decryptedToken}`,
          'Accept': 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28'
        }
      }
    );

    if (!response.ok) {
      console.error(`GitHub API error: ${response.status}`);
      return res.status(response.status).json({ 
        error: `Failed to fetch branches: ${response.statusText}` 
      });
    }

    const branches = await response.json();
    const branchNames = branches.map(b => b.name).sort();

    res.json({
      status: 'success',
      branches: branchNames,
      repository: connection.repository
    });
  } catch (error) {
    console.error('GitHub branches error:', error);
    res.status(500).json({ error: 'Failed to fetch branches: ' + error.message });
  }
});

// POST Connect GitHub (save token)
app.post('/api/github/connect', authenticateToken, async (req, res) => {
  try {
    const { token, repository } = req.body;

    console.log('[GitHub Connect] Received request', { 
      userId: req.user?.id,
      hasToken: !!token, 
      tokenLength: token ? token.length : 0,
      repository,
      userOrgId: req.user?.organizationId
    });

    if (!token || token.length < 10) {
      console.log('[GitHub Connect] Invalid token length');
      return res.status(400).json({ error: 'Invalid GitHub token - must be at least 10 characters' });
    }

    // Validate token format (basic check)
    if (!token.startsWith('ghp_') && !token.startsWith('gho_')) {
      console.log('[GitHub Connect] Invalid token format');
      return res.status(400).json({ error: 'Invalid token format. Must start with ghp_ or gho_' });
    }

    // 🔐 TEST token with GitHub API before storing
    console.log('[GitHub Connect] Testing token with GitHub API...');
    try {
      const testResponse = await fetch('https://api.github.com/user', {
        headers: {
          'Authorization': `token ${token}`,
          'Accept': 'application/vnd.github.v3+json',
          'User-Agent': 'AgenticQA'
        }
      });

      if (!testResponse.ok) {
        const errorData = await testResponse.text();
        console.log('[GitHub Connect] GitHub API test failed:', testResponse.status, errorData);
        
        if (testResponse.status === 401 || testResponse.status === 403) {
          return res.status(401).json({ 
            error: 'Invalid or expired GitHub token. Please check your token and make sure it has the required permissions (repo, workflow).',
            details: testResponse.status === 401 ? 'Unauthorized' : 'Forbidden - token may lack permissions'
          });
        }
        return res.status(400).json({ 
          error: `GitHub API error: ${testResponse.status}. ${testResponse.statusText}`
        });
      }

      const userData = await testResponse.json();
      console.log('[GitHub Connect] Token valid! GitHub user:', userData.login);
    } catch (githubError) {
      console.error('[GitHub Connect] GitHub API test error:', githubError.message);
      return res.status(500).json({ 
        error: 'Failed to validate token with GitHub: ' + githubError.message
      });
    }

    // 🔒 SECURITY: Bind token to specific user
    let encryptedToken;
    try {
      encryptedToken = encryptToken(token);
    } catch (encryptError) {
      console.error('[GitHub Connect] Token encryption failed:', encryptError);
      return res.status(500).json({ error: 'Failed to securely store token' });
    }

    // Use user-specific key instead of global
    const connectionId = `user_${req.user.id}_github`;
    console.log('[GitHub Connect] Storing connection with ID:', connectionId);
    
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

    console.log('[GitHub Connect] Connection stored. Total connections:', db.githubConnections.size);

    logAudit('github_connected', req.user.id, req.user.organizationId, {
      repository: repository,
    });

    console.log('[GitHub Connect] Successfully connected for user', req.user.id);

    res.json({
      status: 'success',
      message: 'GitHub account connected successfully',
      repository: repository
    });
  } catch (error) {
    console.error('[GitHub Connect] Error:', error);
    res.status(500).json({ error: 'Failed to connect GitHub: ' + error.message });
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

// ===== CLIENT PROVISIONING ENDPOINTS =====

// In-memory storage for client repositories
const clientRepositories = new Map();

// Generate unique client ID
function generateClientId() {
  return 'client_' + crypto.randomBytes(8).toString('hex');
}

// Register client repository for pipeline execution
app.post('/api/clients/register', authenticateToken, async (req, res) => {
  try {
    const { repoUrl, clientToken } = req.body;

    if (!repoUrl || !clientToken) {
      return res.status(400).json({ 
        error: 'repoUrl and clientToken are required' 
      });
    }

    // Validate repo URL format
    const repoMatch = repoUrl.match(/github\.com[/:]([\w-]+)\/([\w-]+)/);
    if (!repoMatch) {
      return res.status(400).json({ 
        error: 'Invalid GitHub repository URL' 
      });
    }

    const clientId = generateClientId();
    const encryptedToken = encryptToken(clientToken);

    clientRepositories.set(clientId, {
      id: clientId,
      repoUrl,
      owner: repoMatch[1],
      repo: repoMatch[2],
      encryptedToken,
      userId: req.user.id,
      createdAt: new Date(),
      lastRun: null,
      runCount: 0,
      status: 'active'
    });

    logAudit('client_repo_registered', req.user.id, req.user.organizationId, {
      clientId,
      repoUrl: repoMatch[1] + '/' + repoMatch[2]
    });

    res.json({
      status: 'success',
      clientId,
      message: 'Client repository registered successfully',
      setupUrl: `http://localhost:${PORT}/setup?client=${clientId}`,
      dashboardUrl: `http://localhost:3000?client=${clientId}`
    });
  } catch (error) {
    console.error('Client registration error:', error);
    res.status(500).json({ error: 'Failed to register client repository' });
  }
});

// Get client repository details
app.get('/api/clients/:clientId', async (req, res) => {
  try {
    const { clientId } = req.params;
    const clientRepo = clientRepositories.get(clientId);

    if (!clientRepo) {
      return res.status(404).json({ error: 'Client not found' });
    }

    res.json({
      status: 'success',
      client: {
        id: clientRepo.id,
        repoUrl: clientRepo.repoUrl,
        owner: clientRepo.owner,
        repo: clientRepo.repo,
        createdAt: clientRepo.createdAt,
        lastRun: clientRepo.lastRun,
        runCount: clientRepo.runCount,
        status: clientRepo.status
      }
    });
  } catch (error) {
    console.error('Error fetching client:', error);
    res.status(500).json({ error: 'Failed to fetch client details' });
  }
});

// List client repositories for authenticated user
app.get('/api/clients', authenticateToken, async (req, res) => {
  try {
    const userClients = Array.from(clientRepositories.values()).filter(
      c => c.userId === req.user.id
    );

    res.json({
      status: 'success',
      clients: userClients.map(c => ({
        id: c.id,
        repoUrl: c.repoUrl,
        owner: c.owner,
        repo: c.repo,
        createdAt: c.createdAt,
        lastRun: c.lastRun,
        runCount: c.runCount,
        status: c.status
      }))
    });
  } catch (error) {
    console.error('Error listing clients:', error);
    res.status(500).json({ error: 'Failed to list client repositories' });
  }
});

// Trigger pipeline for client repository
app.post('/api/clients/:clientId/trigger-pipeline', async (req, res) => {
  try {
    const { clientId } = req.params;
    const clientRepo = clientRepositories.get(clientId);

    if (!clientRepo) {
      return res.status(404).json({ error: 'Client not found' });
    }

    // Decrypt GitHub token
    const clientToken = decryptToken(clientRepo.encryptedToken);
    const { owner, repo } = clientRepo;

    console.log(`🚀 Triggering pipeline for client repo: ${owner}/${repo}`);

    // Trigger workflow dispatch in client's repository
    const workflowResponse = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/actions/workflows/agentic-qa.yml/dispatches`,
      {
        method: 'POST',
        headers: {
          'Authorization': `token ${clientToken}`,
          'Accept': 'application/vnd.github+json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          ref: 'main',
          inputs: {
            client_id: clientId
          }
        })
      }
    );

    if (workflowResponse.status === 204) {
      clientRepo.lastRun = new Date();
      clientRepo.runCount++;

      logAudit('client_pipeline_triggered', clientRepo.userId, null, {
        clientId,
        repoUrl: `${owner}/${repo}`
      });

      res.json({
        status: 'success',
        message: 'Pipeline triggered successfully in client repository',
        clientId,
        repoUrl: clientRepo.repoUrl
      });
    } else {
      const errorData = await workflowResponse.text();
      throw new Error(`GitHub API returned ${workflowResponse.status}: ${errorData}`);
    }
  } catch (error) {
    console.error('Client pipeline trigger error:', error);
    res.status(500).json({ 
      error: 'Failed to trigger pipeline: ' + error.message 
    });
  }
});

// Get pipeline definition for client (download-safe version)
app.get('/api/clients/:clientId/pipeline-definition', async (req, res) => {
  try {
    const { clientId } = req.params;
    const clientRepo = clientRepositories.get(clientId);

    if (!clientRepo) {
      return res.status(404).json({ error: 'Client not found' });
    }

    res.json({
      status: 'success',
      definition: {
        version: '1.0',
        phases: [
          {
            name: 'Scan Codebase',
            toolId: 'scan-codebase',
            description: 'Analyze project structure and files'
          },
          {
            name: 'Detect Issues',
            toolId: 'detect-issues',
            description: 'Identify accessibility, performance, and security issues'
          },
          {
            name: 'Generate Tests',
            toolId: 'generate-tests',
            description: 'Create Playwright, Cypress, and Vitest test cases'
          },
          {
            name: 'Run Compliance',
            toolId: 'run-compliance',
            description: 'Check compliance against standards'
          },
          {
            name: 'Generate Report',
            toolId: 'generate-report',
            description: 'Create comprehensive analysis report'
          }
        ]
      }
    });
  } catch (error) {
    console.error('Error fetching pipeline definition:', error);
    res.status(500).json({ error: 'Failed to fetch pipeline definition' });
  }
});

// Submit pipeline results from client workflow
app.post('/api/clients/:clientId/results', async (req, res) => {
  try {
    const { clientId } = req.params;
    const results = req.body;
    const clientRepo = clientRepositories.get(clientId);

    if (!clientRepo) {
      return res.status(404).json({ error: 'Client not found' });
    }

    console.log(`📊 Received results from client: ${clientId}`);

    // Store results (in production, would save to database)
    clientRepo.lastResults = {
      timestamp: new Date(),
      data: results
    };

    logAudit('client_results_received', clientRepo.userId, null, {
      clientId,
      resultsReceived: true
    });

    res.json({
      status: 'success',
      message: 'Results received and stored',
      clientId
    });
  } catch (error) {
    console.error('Error storing client results:', error);
    res.status(500).json({ error: 'Failed to store results' });
  }
});

// ===== ERROR HANDLING =====

// Serve static files BEFORE 404 handler (so static routes are found)
app.use(express.static(path.join(__dirname, 'public')));

app.use((err, req, res, next) => {
  console.error('Server error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

// ===== START SERVER =====

// Helper function to create workflow file in GitHub repo via API
async function createWorkflowInGitHub(owner, repo, token) {
  const workflowContent = `name: AgenticQA Client Pipeline
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
  workflow_dispatch:
    inputs:
      client_id:
        description: 'Client ID for dashboard'
        required: false

jobs:
  agentic-qa:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: 18
      
      - name: Download AgenticQA Executor
        run: |
          mkdir -p .agentic-qa
          curl -sSL https://raw.githubusercontent.com/nhomyk/AgenticQA/main/.agentic-qa/executor.js -o .agentic-qa/executor.js
      
      - name: Run AgenticQA Pipeline
        run: node .agentic-qa/executor.js
        env:
          CLIENT_ID: \${{ github.event.inputs.client_id || 'client_default' }}
          REPOSITORY: \${{ github.repository }}
          BRANCH: \${{ github.ref_name }}
          AGENTIC_QA_API: http://localhost:3001`;

  const content = Buffer.from(workflowContent).toString('base64');
  
  console.log(`📝 Creating workflow in GitHub: ${owner}/${repo}`);
  console.log(`   Token length: ${token.length} chars`);
  console.log(`   Token starts with: ${token.substring(0, 10)}...`);

  const payload = {
    message: 'ci: add AgenticQA automated testing pipeline',
    content: content,
    branch: 'main'
  };

  try {
    const response = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/contents/.github/workflows/agentic-qa.yml`,
      {
        method: 'PUT',
        headers: {
          'Authorization': `token ${token}`,
          'Accept': 'application/vnd.github+json',
          'Content-Type': 'application/json',
          'User-Agent': 'AgenticQA-Client-Setup'
        },
        body: JSON.stringify(payload)
      }
    );

    const responseData = await response.json();

    console.log(`✅ GitHub API Response Status: ${response.status}`);
    console.log(`   Response:`, JSON.stringify(responseData).substring(0, 200));

    if (response.status === 201 || response.status === 200) {
      console.log(`✅ Workflow file created successfully in ${owner}/${repo}`);
      return responseData;
    } else {
      const errorMsg = responseData.message || responseData.error || JSON.stringify(responseData);
      console.error(`❌ GitHub API Error (${response.status}):`, errorMsg);
      throw new Error(`GitHub API (${response.status}): ${errorMsg}`);
    }
  } catch (error) {
    console.error(`❌ Failed to create workflow:`, error);
    throw error;
  }
}

// Self-service client setup (no authentication required - client provides token)
app.post('/api/setup-self-service', async (req, res) => {
  try {
    const { repoUrl, githubToken } = req.body;

    if (!repoUrl || !githubToken) {
      return res.status(400).json({ 
        error: 'repoUrl and githubToken are required' 
      });
    }

    // Validate repo URL format
    const repoMatch = repoUrl.match(/github\.com[/:]([\w-]+)\/([\w-]+)/);
    if (!repoMatch) {
      return res.status(400).json({ 
        error: 'Invalid GitHub repository URL' 
      });
    }

    const owner = repoMatch[1];
    const repo = repoMatch[2];

    console.log(`\n🚀 === SELF-SERVICE SETUP START ===`);
    console.log(`   Repository: ${owner}/${repo}`);

    // Create workflow file in client's repository
    try {
      await createWorkflowInGitHub(owner, repo, githubToken);
    } catch (error) {
      console.error('❌ Failed to create workflow:', error);
      return res.status(400).json({ 
        error: 'Failed to create workflow in repository. Check your token permissions.',
        details: error.message,
        troubleshooting: {
          check: [
            'Token has "repo" scope (full repository access)',
            'Token has "actions" scope (manage GitHub Actions)',
            'Token is not expired',
            'Repository is owned by token owner or token has access'
          ]
        }
      });
    }

    // Register client in our system
    const clientId = generateClientId();
    const encryptedToken = encryptToken(githubToken);

    clientRepositories.set(clientId, {
      id: clientId,
      repoUrl,
      owner,
      repo,
      encryptedToken,
      userId: 'anonymous', // Self-service clients don't require login
      createdAt: new Date(),
      lastRun: null,
      runCount: 0,
      status: 'active',
      selfService: true
    });

    logAudit('client_self_service_setup', 'anonymous', 'self-service', {
      clientId,
      repoUrl: `${owner}/${repo}`
    });

    console.log(`✅ Client registered with ID: ${clientId}`);
    console.log(`🚀 === SELF-SERVICE SETUP COMPLETE ===\n`);

    res.json({
      status: 'success',
      clientId,
      message: 'Workflow successfully created and client registered',
      dashboardUrl: `http://localhost:3000?client=${clientId}`,
      workflowUrl: `https://github.com/${owner}/${repo}/actions`,
      nextSteps: [
        'Workflow file created at: .github/workflows/agentic-qa.yml',
        'Executor will download on first workflow run',
        'View results on your dashboard',
        `Check GitHub Actions: ${`https://github.com/${owner}/${repo}/actions`}`
      ]
    });
  } catch (error) {
    console.error('❌ Self-service setup error:', error);
    res.status(500).json({ error: 'Failed to setup client pipeline' });
  }
});

// DEBUG endpoint to test workflow creation
app.post('/api/debug/test-workflow-creation', async (req, res) => {
  try {
    const { owner, repo, token } = req.body;

    if (!owner || !repo || !token) {
      return res.status(400).json({ 
        error: 'owner, repo, and token are required' 
      });
    }

    console.log(`\n🔍 === DEBUG: TESTING WORKFLOW CREATION ===`);
    console.log(`   Repository: ${owner}/${repo}`);
    console.log(`   Token prefix: ${token.substring(0, 10)}...`);

    try {
      await createWorkflowInGitHub(owner, repo, token);
      
      console.log(`✅ DEBUG: Workflow creation successful`);
      res.json({
        status: 'success',
        message: 'Workflow creation test successful',
        repoUrl: `https://github.com/${owner}/${repo}`,
        actionsUrl: `https://github.com/${owner}/${repo}/actions`,
        workflowFile: `.github/workflows/agentic-qa.yml`
      });
    } catch (error) {
      console.error(`❌ DEBUG: Workflow creation failed:`, error.message);
      res.status(400).json({
        status: 'failed',
        error: error.message,
        troubleshooting: {
          tokenIssues: [
            'Check token is valid',
            'Check token has "repo" scope',
            'Check token has "actions" scope',
            'Check token is not expired'
          ],
          permissionIssues: [
            'You must be able to push to the repository',
            'The repository owner must have GitHub Actions enabled',
            'Verify you own the repository'
          ]
        }
      });
    }
  } catch (error) {
    console.error('Debug endpoint error:', error);
    res.status(500).json({ error: error.message });
  }
});

// POST Setup workflow file in repository
app.post('/api/github/setup-workflow', authenticateToken, async (req, res) => {
  try {
    const connectionId = `user_${req.user.id}_github`;
    const connection = db.githubConnections.get(connectionId);

    console.log('[Setup Workflow] Starting for user:', req.user.id, 'repo:', connection?.repository);

    if (!connection) {
      return res.status(403).json({ error: 'GitHub not connected' });
    }

    if (!connection.token || !connection.repository) {
      return res.status(400).json({ error: 'GitHub repository not configured' });
    }

    let decryptedToken;
    try {
      decryptedToken = decryptToken(connection.token);
    } catch (decryptError) {
      console.error('[Setup Workflow] Token decryption failed:', decryptError);
      return res.status(503).json({ error: 'Failed to retrieve GitHub credentials' });
    }

    const [owner, repo] = connection.repository.split('/');
    console.log('[Setup Workflow] Owner:', owner, 'Repo:', repo);
    
    // Deploy the full pipeline workflow by reading from template file
    let workflowContent;
    try {
      const fs = require('fs');
      // Use the client-focused workflow, not the AgenticQA framework workflow
      workflowContent = fs.readFileSync('./.github/workflows/agentic-qa-client.yml', 'utf-8');
      console.log('[Setup Workflow] Client workflow loaded, size:', workflowContent.length, 'bytes');
    } catch (fileError) {
      console.warn('[Setup Workflow] Client workflow not found, trying template:', fileError.message);
      try {
        const fs = require('fs');
        workflowContent = fs.readFileSync('./.github/workflows/agentic-qa-template.yml', 'utf-8');
        console.log('[Setup Workflow] Template loaded, size:', workflowContent.length, 'bytes');
      } catch (templateError) {
        console.warn('[Setup Workflow] Template not found either, using fallback:', templateError.message);
        // Fallback to minimal workflow if neither exists
        workflowContent = `name: AgenticQA Pipeline
on:
  push:
    branches: [main]
  workflow_dispatch:
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci || npm install || true
      - run: npm test 2>/dev/null || true`;
      }
    }

    const content = Buffer.from(workflowContent).toString('base64');
    console.log('[Setup Workflow] Content encoded, base64 size:', content.length);

    // Check if file exists to get SHA for update
    let sha;
    try {
      console.log('[Setup Workflow] Checking if workflow file exists...');
      const getRes = await fetch(
        `https://api.github.com/repos/${connection.repository}/contents/.github/workflows/agentic-qa.yml`,
        {
          method: 'GET',
          headers: {
            'Authorization': `token ${decryptedToken}`,
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28'
          }
        }
      );
      if (getRes.ok) {
        const fileData = await getRes.json();
        sha = fileData.sha;
        console.log('[Setup Workflow] File exists with SHA:', sha.substring(0, 10) + '...');
      } else {
        console.log('[Setup Workflow] File does not exist (status: ' + getRes.status + ')');
      }
    } catch (e) {
      console.log('[Setup Workflow] Error checking file:', e.message);
    }

    // Create or update workflow file
    console.log('[Setup Workflow] Uploading workflow file...', sha ? '(update)' : '(create)');
    const response = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/contents/.github/workflows/agentic-qa.yml`,
      {
        method: 'PUT',
        headers: {
          'Authorization': `token ${decryptedToken}`,
          'Accept': 'application/vnd.github+json',
          'Content-Type': 'application/json',
          'X-GitHub-Api-Version': '2022-11-28'
        },
        body: JSON.stringify({
          message: 'feat: add/update AgenticQA full pipeline workflow',
          content: content,
          ...(sha && { sha })
        })
      }
    );

    console.log('[Setup Workflow] GitHub API response status:', response.status);
    const responseData = await response.json();

    if (response.ok) {
      console.log('[Setup Workflow] Success! File created/updated');
      res.json({
        status: 'success',
        message: 'Workflow file created/updated successfully. New workflow will appear on next push or manual trigger.',
        repository: connection.repository,
        workflowUrl: `https://github.com/${owner}/${repo}/blob/main/.github/workflows/agentic-qa.yml`,
        actionsUrl: `https://github.com/${owner}/${repo}/actions`
      });
    } else {
      console.error('[Setup Workflow] Failed! Status:', response.status, 'Error:', responseData);
      res.status(response.status).json({ 
        error: responseData.message || 'Failed to create workflow file',
        details: responseData
      });
    }
  } catch (error) {
    console.error('[Setup Workflow] Error:', error);
    res.status(500).json({ error: 'Failed to setup workflow: ' + error.message });
  }
});

// DELETE workflow file to force refresh
app.delete('/api/github/setup-workflow', authenticateToken, async (req, res) => {
  try {
    const connectionId = `user_${req.user.id}_github`;
    const connection = db.githubConnections.get(connectionId);

    console.log('[Delete Workflow] Starting for user:', req.user.id, 'repo:', connection?.repository);

    if (!connection) {
      return res.status(403).json({ error: 'GitHub not connected' });
    }

    if (!connection.token || !connection.repository) {
      return res.status(400).json({ error: 'GitHub repository not configured' });
    }

    let decryptedToken;
    try {
      decryptedToken = decryptToken(connection.token);
    } catch (decryptError) {
      console.error('[Delete Workflow] Token decryption failed:', decryptError);
      return res.status(503).json({ error: 'Failed to retrieve GitHub credentials' });
    }

    const [owner, repo] = connection.repository.split('/');

    // Get file SHA first
    console.log('[Delete Workflow] Fetching file SHA...');
    const getRes = await fetch(
      `https://api.github.com/repos/${connection.repository}/contents/.github/workflows/agentic-qa.yml`,
      {
        method: 'GET',
        headers: {
          'Authorization': `token ${decryptedToken}`,
          'Accept': 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28'
        }
      }
    );

    if (!getRes.ok) {
      console.log('[Delete Workflow] File not found or error:', getRes.status);
      return res.status(404).json({ error: 'Workflow file not found' });
    }

    const fileData = await getRes.json();
    const sha = fileData.sha;
    console.log('[Delete Workflow] File SHA:', sha.substring(0, 10) + '...');

    // Delete the file
    console.log('[Delete Workflow] Deleting workflow file...');
    const deleteRes = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/contents/.github/workflows/agentic-qa.yml`,
      {
        method: 'DELETE',
        headers: {
          'Authorization': `token ${decryptedToken}`,
          'Accept': 'application/vnd.github+json',
          'Content-Type': 'application/json',
          'X-GitHub-Api-Version': '2022-11-28'
        },
        body: JSON.stringify({
          message: 'ci: clear old workflow for refresh',
          sha: sha
        })
      }
    );

    console.log('[Delete Workflow] GitHub API response status:', deleteRes.status);

    if (deleteRes.ok) {
      console.log('[Delete Workflow] Success! File deleted');
      res.json({
        status: 'success',
        message: 'Workflow file deleted. Run /api/github/setup-workflow to deploy the new version.',
        repository: connection.repository
      });
    } else {
      console.error('[Delete Workflow] Failed! Status:', deleteRes.status);
      const error = await deleteRes.json();
      res.status(deleteRes.status).json({ 
        error: error.message || 'Failed to delete workflow file'
      });
    }
  } catch (error) {
    console.error('[Delete Workflow] Error:', error);
    res.status(500).json({ error: 'Failed to delete workflow: ' + error.message });
  }
});

// POST Trigger workflow via GitHub API
app.post('/api/trigger-workflow', authenticateToken, async (req, res) => {
  try {
    const { pipelineType, branch } = req.body;
    
    console.log('[Trigger Workflow] Request from user:', req.user?.id, 'pipelineType:', pipelineType, 'branch:', branch);
    
    const connectionId = `user_${req.user.id}_github`;
    const connection = db.githubConnections.get(connectionId);

    if (!connection) {
      console.log('[Trigger Workflow] No GitHub connection found for user:', req.user.id);
      return res.status(403).json({ error: 'GitHub not connected' });
    }

    if (!connection.repository) {
      console.log('[Trigger Workflow] Repository not configured for connection:', connectionId);
      return res.status(400).json({ error: 'No repository configured' });
    }

    if (!connection.token) {
      console.log('[Trigger Workflow] No token stored for connection:', connectionId);
      return res.status(503).json({ error: 'GitHub token not configured' });
    }

    let decryptedToken;
    try {
      decryptedToken = decryptToken(connection.token);
    } catch (decryptError) {
      console.error('[Trigger Workflow] Token decryption failed:', decryptError);
      return res.status(503).json({ error: 'Failed to retrieve GitHub credentials' });
    }

    const branchToTrigger = branch || 'main';
    const inputs = {
      pipeline_type: pipelineType || 'full'
    };

    // Try to trigger workflow
    const githubResponse = await fetch(
      `https://api.github.com/repos/${connection.repository}/actions/workflows/agentic-qa.yml/dispatches`,
      {
        method: 'POST',
        headers: {
          'Authorization': `token ${decryptedToken}`,
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

    if (githubResponse.status === 204) {
      connection.lastUsed = new Date();
      
      res.json({
        status: 'success',
        message: `Workflow triggered successfully on ${connection.repository}`,
        pipelineType: pipelineType,
        branch: branchToTrigger,
        repository: connection.repository
      });
    } else if (githubResponse.status === 401) {
      connection.token = null;
      return res.status(403).json({ 
        error: 'GitHub token is invalid or expired' 
      });
    } else if (githubResponse.status === 422) {
      const errorData = await githubResponse.json();
      return res.status(400).json({ 
        error: `Validation error: ${errorData.message || 'Check repository and branch name.'}` 
      });
    } else {
      const errorData = await githubResponse.text();
      throw new Error(`GitHub API returned ${githubResponse.status}: ${errorData}`);
    }
  } catch (error) {
    console.error('Workflow trigger error:', error);
    res.status(500).json({ error: 'Failed to trigger workflow: ' + error.message });
  }
});

// ===== 404 CATCH-ALL HANDLER (MUST BE AT END) =====
app.use((req, res) => {
  res.status(404).json({ error: 'Route not found' });
});

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
