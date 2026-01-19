// OrbitQA SaaS API Server
// Multi-tenant backend for dashboard, authentication, and result management

const express = require('express');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
const pg = require('pg');
const cors = require('cors');
const dotenv = require('dotenv');
const path = require('path');
const fs = require('fs');

dotenv.config();

const app = express();
const PORT = process.env.SAAS_PORT || 3001;
const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-change-in-production';
const DB_URL = process.env.DATABASE_URL || 'postgresql://postgres:postgres@localhost:5432/orbitqa_saas';

// Middleware
app.use(cors());
app.use(express.json());

// Database connection pool
const pool = new pg.Pool({
  connectionString: DB_URL,
});

pool.on('error', (err) => {
  console.error('Unexpected error on idle client', err);
});

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

// ===== AUTH ENDPOINTS =====

// Register new user
app.post('/api/auth/register', async (req, res) => {
  try {
    const { email, password, name, organization } = req.body;

    if (!email || !password || !name || !organization) {
      return res.status(400).json({ error: 'Missing required fields' });
    }

    // Check if user exists
    const userExists = await pool.query(
      'SELECT id FROM users WHERE email = $1',
      [email]
    );

    if (userExists.rows.length > 0) {
      return res.status(409).json({ error: 'User already exists' });
    }

    // Hash password
    const hashedPassword = await bcrypt.hash(password, 10);

    // Create user
    const result = await pool.query(
      'INSERT INTO users (email, password_hash, name, organization, role) VALUES ($1, $2, $3, $4, $5) RETURNING id, email, name, organization, role',
      [email, hashedPassword, name, organization, 'admin']
    );

    const user = result.rows[0];

    // Generate token
    const token = jwt.sign(
      { id: user.id, email: user.email, role: user.role, organization: user.organization },
      JWT_SECRET,
      { expiresIn: '7d' }
    );

    res.json({ token, user });
  } catch (error) {
    console.error('Registration error:', error);
    res.status(500).json({ error: 'Registration failed' });
  }
});

// Login
app.post('/api/auth/login', async (req, res) => {
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({ error: 'Email and password required' });
    }

    // Get user
    const result = await pool.query(
      'SELECT id, email, password_hash, name, role, organization FROM users WHERE email = $1',
      [email]
    );

    if (result.rows.length === 0) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const user = result.rows[0];

    // Verify password
    const validPassword = await bcrypt.compare(password, user.password_hash);

    if (!validPassword) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    // Generate token
    const token = jwt.sign(
      { id: user.id, email: user.email, role: user.role, organization: user.organization },
      JWT_SECRET,
      { expiresIn: '7d' }
    );

    res.json({
      token,
      user: {
        id: user.id,
        email: user.email,
        name: user.name,
        role: user.role,
        organization: user.organization,
      },
    });
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ error: 'Login failed' });
  }
});

// Verify token
app.get('/api/auth/me', authenticateToken, async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT id, email, name, role, organization, created_at FROM users WHERE id = $1',
      [req.user.id]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'User not found' });
    }

    res.json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch user' });
  }
});

// ===== TEST RUNS ENDPOINTS =====

// Create test run
app.post('/api/test-runs', authenticateToken, async (req, res) => {
  try {
    const { url, browsers, name, description } = req.body;

    if (!url) {
      return res.status(400).json({ error: 'URL required' });
    }

    const result = await pool.query(
      `INSERT INTO test_runs 
       (user_id, organization, url, name, description, status, browsers, started_at) 
       VALUES ($1, $2, $3, $4, $5, $6, $7, NOW()) 
       RETURNING *`,
      [req.user.id, req.user.organization, url, name || url, description || '', 'pending', JSON.stringify(browsers || ['chromium', 'firefox'])]
    );

    // Trigger agent scan asynchronously
    triggerAgentScan(result.rows[0].id, url, browsers);

    res.status(201).json(result.rows[0]);
  } catch (error) {
    console.error('Test run creation error:', error);
    res.status(500).json({ error: 'Failed to create test run' });
  }
});

// Get test runs
app.get('/api/test-runs', authenticateToken, async (req, res) => {
  try {
    const { limit = 50, offset = 0, status } = req.query;

    let query = 'SELECT * FROM test_runs WHERE user_id = $1';
    const params = [req.user.id];

    if (status) {
      query += ` AND status = $${params.length + 1}`;
      params.push(status);
    }

    query += ` ORDER BY created_at DESC LIMIT $${params.length + 1} OFFSET $${params.length + 2}`;
    params.push(parseInt(limit), parseInt(offset));

    const result = await pool.query(query, params);

    res.json({
      runs: result.rows,
      total: result.rows.length,
    });
  } catch (error) {
    console.error('Test runs fetch error:', error);
    res.status(500).json({ error: 'Failed to fetch test runs' });
  }
});

// Get single test run
app.get('/api/test-runs/:id', authenticateToken, async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT * FROM test_runs WHERE id = $1 AND user_id = $2',
      [req.params.id, req.user.id]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Test run not found' });
    }

    res.json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch test run' });
  }
});

// Get test run results
app.get('/api/test-runs/:id/results', authenticateToken, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT * FROM test_results 
       WHERE test_run_id = $1 
       AND test_run_id IN (SELECT id FROM test_runs WHERE user_id = $2)
       ORDER BY created_at DESC`,
      [req.params.id, req.user.id]
    );

    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch results' });
  }
});

// Update test run result
app.post('/api/test-runs/:id/results', authenticateToken, async (req, res) => {
  try {
    const { browser, issues, technologies, performance, apis, recommendations, status } = req.body;

    const result = await pool.query(
      `INSERT INTO test_results 
       (test_run_id, browser, issues, technologies, performance, apis, recommendations, status) 
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8) 
       RETURNING *`,
      [
        req.params.id,
        browser,
        JSON.stringify(issues),
        JSON.stringify(technologies),
        JSON.stringify(performance),
        JSON.stringify(apis),
        JSON.stringify(recommendations),
        status || 'completed',
      ]
    );

    // Update parent test run status if all browsers done
    await updateTestRunStatus(req.params.id);

    res.status(201).json(result.rows[0]);
  } catch (error) {
    console.error('Result creation error:', error);
    res.status(500).json({ error: 'Failed to save result' });
  }
});

// Delete test run
app.delete('/api/test-runs/:id', authenticateToken, async (req, res) => {
  try {
    await pool.query(
      'DELETE FROM test_results WHERE test_run_id = $1',
      [req.params.id]
    );

    await pool.query(
      'DELETE FROM test_runs WHERE id = $1 AND user_id = $2',
      [req.params.id, req.user.id]
    );

    res.json({ success: true });
  } catch (error) {
    res.status(500).json({ error: 'Failed to delete test run' });
  }
});

// ===== TEAM ENDPOINTS =====

// Get organization members
app.get('/api/team/members', authenticateToken, authorizeRole('admin', 'owner'), async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT id, email, name, role, created_at FROM users WHERE organization = $1',
      [req.user.organization]
    );

    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch team members' });
  }
});

// Invite team member
app.post('/api/team/members', authenticateToken, authorizeRole('admin', 'owner'), async (req, res) => {
  try {
    const { email, name, role = 'member' } = req.body;

    if (!email || !name) {
      return res.status(400).json({ error: 'Email and name required' });
    }

    // Generate temporary password
    const tempPassword = Math.random().toString(36).slice(2, 15);
    const hashedPassword = await bcrypt.hash(tempPassword, 10);

    const result = await pool.query(
      `INSERT INTO users (email, password_hash, name, organization, role) 
       VALUES ($1, $2, $3, $4, $5) 
       RETURNING id, email, name, role`,
      [email, hashedPassword, name, req.user.organization, role]
    );

    // TODO: Send invitation email with temporary password

    res.status(201).json({
      user: result.rows[0],
      tempPassword, // In production, send via email only
    });
  } catch (error) {
    if (error.code === '23505') {
      return res.status(409).json({ error: 'User already exists' });
    }
    res.status(500).json({ error: 'Failed to invite user' });
  }
});

// Update team member role
app.patch('/api/team/members/:id', authenticateToken, authorizeRole('admin', 'owner'), async (req, res) => {
  try {
    const { role } = req.body;

    const result = await pool.query(
      'UPDATE users SET role = $1 WHERE id = $2 AND organization = $3 RETURNING id, email, name, role',
      [role, req.params.id, req.user.organization]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'User not found' });
    }

    res.json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: 'Failed to update user' });
  }
});

// Remove team member
app.delete('/api/team/members/:id', authenticateToken, authorizeRole('admin', 'owner'), async (req, res) => {
  try {
    await pool.query(
      'DELETE FROM users WHERE id = $1 AND organization = $2 AND id != $3',
      [req.params.id, req.user.organization, req.user.id]
    );

    res.json({ success: true });
  } catch (error) {
    res.status(500).json({ error: 'Failed to remove user' });
  }
});

// ===== SETTINGS ENDPOINTS =====

// Get organization settings
app.get('/api/settings', authenticateToken, async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT * FROM organization_settings WHERE organization = $1',
      [req.user.organization]
    );

    if (result.rows.length === 0) {
      // Create default settings
      const defaultResult = await pool.query(
        `INSERT INTO organization_settings (organization, webhook_url, api_key) 
         VALUES ($1, NULL, $2) 
         RETURNING *`,
        [req.user.organization, generateApiKey()]
      );
      return res.json(defaultResult.rows[0]);
    }

    res.json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch settings' });
  }
});

// Update organization settings
app.patch('/api/settings', authenticateToken, authorizeRole('admin', 'owner'), async (req, res) => {
  try {
    const { webhook_url } = req.body;

    const result = await pool.query(
      `UPDATE organization_settings 
       SET webhook_url = $1, updated_at = NOW() 
       WHERE organization = $2 
       RETURNING *`,
      [webhook_url, req.user.organization]
    );

    res.json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ error: 'Failed to update settings' });
  }
});

// Get API key
app.get('/api/settings/api-key', authenticateToken, authorizeRole('admin', 'owner'), async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT api_key FROM organization_settings WHERE organization = $1',
      [req.user.organization]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Settings not found' });
    }

    res.json({ api_key: result.rows[0].api_key });
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch API key' });
  }
});

// Regenerate API key
app.post('/api/settings/api-key/regenerate', authenticateToken, authorizeRole('admin', 'owner'), async (req, res) => {
  try {
    const newKey = generateApiKey();

    const result = await pool.query(
      `UPDATE organization_settings 
       SET api_key = $1, updated_at = NOW() 
       WHERE organization = $2 
       RETURNING api_key`,
      [newKey, req.user.organization]
    );

    res.json({ api_key: result.rows[0].api_key });
  } catch (error) {
    res.status(500).json({ error: 'Failed to regenerate key' });
  }
});

// ===== HEALTH & STATUS =====

app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// ===== HELPER FUNCTIONS =====

function generateApiKey() {
  return 'sk_' + require('crypto').randomBytes(24).toString('hex');
}

async function updateTestRunStatus(testRunId) {
  const result = await pool.query(
    'SELECT COUNT(*) as total, SUM(CASE WHEN status = \'completed\' THEN 1 ELSE 0 END) as completed FROM test_results WHERE test_run_id = $1',
    [testRunId]
  );

  const row = result.rows[0];
  let status = 'running';

  if (parseInt(row.total) > 0 && parseInt(row.total) === parseInt(row.completed)) {
    status = 'completed';
  }

  await pool.query(
    'UPDATE test_runs SET status = $1, completed_at = NOW() WHERE id = $2',
    [status, testRunId]
  );
}

function triggerAgentScan(runId, url, browsers) {
  // Queue async job to run agent
  // This would integrate with the QA Agent
  console.log(`Queuing agent scan: runId=${runId}, url=${url}, browsers=${browsers}`);
  
  // TODO: Implement job queue (Bull, RabbitMQ, etc)
  // For now, this is a placeholder
}

// ===== START SERVER =====

async function startServer() {
  try {
    // Test database connection
    await pool.query('SELECT NOW()');
    console.log('✅ Database connected');

    // Initialize database schema
    await initializeDatabase();

    app.listen(PORT, () => {
      console.log(`🚀 SaaS API running on http://localhost:${PORT}`);
      console.log(`📊 Environment: ${process.env.NODE_ENV || 'development'}`);
    });
  } catch (error) {
    console.error('❌ Failed to start server:', error);
    process.exit(1);
  }
}

async function initializeDatabase() {
  const schema = fs.readFileSync(path.join(__dirname, 'saas-db-schema.sql'), 'utf8');
  
  try {
    await pool.query(schema);
    console.log('✅ Database schema initialized');
  } catch (error) {
    if (error.message.includes('already exists')) {
      console.log('✅ Database schema already exists');
    } else {
      throw error;
    }
  }
}

// Handle graceful shutdown
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, shutting down gracefully...');
  await pool.end();
  process.exit(0);
});

startServer();

module.exports = app;
