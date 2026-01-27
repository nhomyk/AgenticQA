// Combined dashboard and static server for AgenticQA
// Usage: node start-all.js

const express = require('express');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 8080;

// Serve static files from public/
app.use(express.static(path.join(__dirname, 'public')));

// Example API endpoint (customize as needed)
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', time: new Date().toISOString() });
});

// Fallback: serve index.html for any unknown route (SPA support)
app.get(/^\/.*$/, (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`AgenticQA dashboard running at http://localhost:${PORT}`);
  console.log('Serving files from /public');
});
