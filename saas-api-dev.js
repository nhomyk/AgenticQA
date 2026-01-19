// OrbitQA SaaS API Server - Development Mode
// In-memory version for local development (no database required)

const express = require('express');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
const cors = require('cors');
const dotenv = require('dotenv');
const path = require('path');

dotenv.config();

const app = express();
const PORT = process.env.SAAS_PORT || 3001;
const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-change-in-production';

// Middleware
app.use(cors());
app.use(express.json());

// Serve static files from public directory
app.use(express.static(path.join(__dirname, 'public')));

// In-memory storage (reset on server restart)
const db = {
  users: new Map(),
  organizations: new Map(),
  testRuns: new Map(),
  testResults: new Map(),
  apiKeys: new Map(),
  auditLogs: new Map(),
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
    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({ error: 'Email and password required' });
    }

    const user = Array.from(db.users.values()).find(u => u.email === email);
    if (!user) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const isValid = await bcrypt.compare(password, user.password);
    if (!isValid) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

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

// ===== ERROR HANDLING =====

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
