// Simple static file server for the public/ directory
// Usage: node serve-public.js

const express = require('express');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 8080;

app.use(express.static(path.join(__dirname, 'public')));

app.listen(PORT, () => {
  console.log(`Static server running at http://localhost:${PORT}`);
  console.log('Serving files from /public');
});
