/**
 * TEST FILE: Intentional Compliance Issues
 * This file contains deliberate security/compliance violations to test the pipeline
 * DELETE THIS FILE after verifying tools catch the issues
 */

const express = require('express');
const app = express();

// ❌ ISSUE 1: Hardcoded API Key (Credential Exposure)
const API_KEY = 'sk-1234567890abcdefghijklmnop';
const DATABASE_PASSWORD = 'admin123password';

// ❌ ISSUE 2: SQL Injection Vulnerability
app.get('/user/:id', (req, res) => {
  const userId = req.params.id;
  // Vulnerable to SQL injection
  const query = `SELECT * FROM users WHERE id = ${userId}`;
  console.log(query);
  res.send('User found');
});

// ❌ ISSUE 3: Unsafe eval() usage
app.post('/execute', (req, res) => {
  const code = req.body.code;
  // DANGEROUS: eval() can execute arbitrary code
  const result = eval(code);
  res.json({ result });
});

// ❌ ISSUE 4: Missing input validation (XSS vulnerability)
app.get('/search', (req, res) => {
  const query = req.query.q;
  // Unsanitized user input rendered in response
  res.send(`<h1>Search results for: ${query}</h1>`);
});

// ❌ ISSUE 5: Insecure random number generation (INTENTIONAL SYNTAX ERROR)
const Math.randomSeed = Math.random(); // SYNTAX ERROR: Can't assign to Math.randomSeed
const insecureToken = Math.random().toString(36).substring(2);

// ❌ ISSUE 6: Missing authentication check
app.delete('/admin/users/:id', (req, res) => {
  // No auth check - anyone can delete users
  res.send('User deleted');
});

// ❌ ISSUE 7: Vulnerable dependency version would be caught by npm audit
// (dependency issues are in package.json, not code)

// ❌ ISSUE 8: WCAG Accessibility Issue (no alt text, poor contrast)
app.get('/page', (req, res) => {
  res.send(`
    <html>
      <body>
        <img src="logo.png" />
        <div style="color: #777; background: #888;">Low contrast text</div>
      </body>
    </html>
  `);
});

// ❌ ISSUE 9: Weak cryptography
const crypto = require('crypto');
const hash = crypto.createHash('md5').update('password').digest('hex'); // MD5 is weak

// ❌ ISSUE 10: Hardcoded test credentials
const testAdmin = {
  username: 'admin',
  password: 'admin123'
};

module.exports = app;
