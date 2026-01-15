#!/usr/bin/env node

/**
 * Minimal Server - Bypass Puppeteer & Complex Setup
 * Use this to test basic connectivity
 */

const express = require('express');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

console.log('\n🚀 Starting Minimal Server (No Puppeteer)\n');

// Serve static files
app.use(express.static(path.join(__dirname, 'public')));

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Basic API test
app.get('/api/test', (req, res) => {
  res.json({ message: 'API working', status: 'success' });
});

// Dashboard
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public/dashboard.html'));
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Not found' });
});

// Start server
const server = app.listen(PORT, '127.0.0.1', () => {
  console.log(`✅ Minimal server running at http://localhost:${PORT}`);
  console.log(`\n📝 Test URLs:`);
  console.log(`   Dashboard:  http://localhost:${PORT}`);
  console.log(`   Health:     http://localhost:${PORT}/health`);
  console.log(`   API Test:   http://localhost:${PORT}/api/test\n`);
  console.log('Press Ctrl+C to stop\n');
});

server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.error(`❌ Port ${PORT} is already in use`);
    console.error(`Kill it with: lsof -ti:${PORT} | xargs kill -9\n`);
  } else {
    console.error(`❌ Server error: ${err.message}\n`);
  }
  process.exit(1);
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\n✓ Shutting down...\n');
  server.close(() => process.exit(0));
});
