#!/usr/bin/env node

/**
 * AgenticQA Client Onboarding Script
 * Provisions a client repository to run the AgenticQA pipeline
 * 
 * Usage: node scripts/onboard-client.js <repo_url> <github_token>
 * Example: node scripts/onboard-client.js https://github.com/user/repo ghp_xxxxxxxxxxxx
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const { execSync } = require('child_process');

const args = process.argv.slice(2);
const REPO_URL = args[0];
const GITHUB_TOKEN = args[1];
const DASHBOARD_API = process.env.DASHBOARD_API || 'http://localhost:3001';

const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m'
};

function log(level, message) {
  const prefix = {
    'INFO': `${colors.blue}ℹ${colors.reset}`,
    'SUCCESS': `${colors.green}✓${colors.reset}`,
    'WARN': `${colors.yellow}⚠${colors.reset}`,
    'ERROR': `${colors.red}✗${colors.reset}`
  }[level] || 'INFO';

  console.log(`${prefix} ${message}`);
}

function error(message) {
  console.error(`${colors.red}✗${colors.reset} ${message}`);
  process.exit(1);
}

async function registerClient() {
  log('INFO', 'Registering client repository...');

  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      repoUrl: REPO_URL,
      clientToken: GITHUB_TOKEN
    });

    const url = new URL('/api/clients/register', DASHBOARD_API);
    const options = {
      hostname: url.hostname,
      port: url.port || (url.protocol === 'https:' ? 443 : 80),
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const result = JSON.parse(data);
          if (res.statusCode === 200) {
            resolve(result);
          } else {
            reject(new Error(result.error || `HTTP ${res.statusCode}`));
          }
        } catch (e) {
          reject(new Error(`Failed to parse response: ${e.message}`));
        }
      });
    });

    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

function createWorkflowFile() {
  log('INFO', 'Creating workflow file...');

  const workflowDir = '.github/workflows';
  const workflowFile = path.join(workflowDir, 'agentic-qa.yml');

  // Create directory if it doesn't exist
  if (!fs.existsSync(workflowDir)) {
    fs.mkdirSync(workflowDir, { recursive: true });
    log('SUCCESS', `Created directory: ${workflowDir}`);
  }

  // Read template
  const templatePath = path.join(__dirname, '..', 'templates', 'client-workflow-template.yml');
  if (!fs.existsSync(templatePath)) {
    error(`Workflow template not found at ${templatePath}`);
  }

  const template = fs.readFileSync(templatePath, 'utf8');

  // Write workflow file
  fs.writeFileSync(workflowFile, template);
  log('SUCCESS', `Created workflow file: ${workflowFile}`);

  return workflowFile;
}

function commitAndPushWorkflow() {
  log('INFO', 'Committing and pushing workflow...');

  try {
    // Check if we're in a git repository
    execSync('git status > /dev/null 2>&1');

    // Add workflow file
    execSync('git add .github/workflows/agentic-qa.yml');
    log('SUCCESS', 'Staged workflow file');

    // Commit
    execSync('git commit -m "ci: add AgenticQA automated testing pipeline"');
    log('SUCCESS', 'Committed workflow file');

    // Push
    execSync('git push origin main');
    log('SUCCESS', 'Pushed to remote repository');
  } catch (e) {
    log('WARN', 'Git operations failed (repository may not be initialized)');
    log('INFO', 'Please manually commit and push:');
    console.log('  git add .github/workflows/agentic-qa.yml');
    console.log('  git commit -m "ci: add AgenticQA automated testing pipeline"');
    console.log('  git push origin main');
  }
}

async function setupExecutor(clientId) {
  log('INFO', 'Setting up pipeline executor...');

  try {
    const execDir = '.agentic-qa';
    if (!fs.existsSync(execDir)) {
      fs.mkdirSync(execDir, { recursive: true });
    }

    // Download executor script from dashboard or use local one
    const executorPath = path.join(__dirname, '..', '.agentic-qa', 'executor.js');
    const targetPath = path.join(execDir, 'executor.js');

    if (fs.existsSync(executorPath)) {
      fs.copyFileSync(executorPath, targetPath);
      log('SUCCESS', `Setup executor script: ${targetPath}`);
    } else {
      log('WARN', `Could not find executor script at ${executorPath}`);
      log('INFO', 'The executor will be downloaded when the workflow runs');
    }
  } catch (e) {
    log('WARN', `Failed to setup executor: ${e.message}`);
  }
}

async function main() {
  console.log(`\n${colors.bright}🤖 AgenticQA Client Onboarding${colors.reset}\n`);

  // Validate inputs
  if (!REPO_URL || !GITHUB_TOKEN) {
    error('Usage: node scripts/onboard-client.js <repo_url> <github_token>');
  }

  // Parse repo URL
  const repoMatch = REPO_URL.match(/github\.com[/:]([\w-]+)\/([\w-]+)/);
  if (!repoMatch) {
    error('Invalid GitHub repository URL');
  }

  const owner = repoMatch[1];
  const repo = repoMatch[2];

  console.log(`Repository: ${colors.cyan}${owner}/${repo}${colors.reset}`);
  console.log(`Dashboard API: ${colors.cyan}${DASHBOARD_API}${colors.reset}\n`);

  try {
    // Step 1: Register client
    console.log(`${colors.bright}Step 1: Register Client Repository${colors.reset}`);
    const registration = await registerClient();
    const clientId = registration.clientId;

    log('SUCCESS', `Client registered with ID: ${colors.cyan}${clientId}${colors.reset}`);
    console.log();

    // Step 2: Create workflow file
    console.log(`${colors.bright}Step 2: Create Workflow File${colors.reset}`);
    createWorkflowFile();
    console.log();

    // Step 3: Setup executor
    console.log(`${colors.bright}Step 3: Setup Pipeline Executor${colors.reset}`);
    await setupExecutor(clientId);
    console.log();

    // Step 4: Commit and push
    console.log(`${colors.bright}Step 4: Commit and Push${colors.reset}`);
    commitAndPushWorkflow();
    console.log();

    // Summary
    console.log(`${colors.bright}✅ Onboarding Complete!${colors.reset}\n`);
    console.log(`${colors.green}Next Steps:${colors.reset}`);
    console.log(`1. Open your dashboard: ${colors.cyan}${DASHBOARD_API}?client=${clientId}${colors.reset}`);
    console.log(`2. The workflow will run on every push to main branch`);
    console.log(`3. Trigger manually from GitHub Actions tab in your repository`);
    console.log(`4. View real-time results in the AgenticQA dashboard\n`);

    console.log(`${colors.cyan}Client ID: ${clientId}${colors.reset}`);
    console.log(`${colors.cyan}Dashboard URL: ${DASHBOARD_API}?client=${clientId}${colors.reset}\n`);

  } catch (err) {
    error(`Onboarding failed: ${err.message}`);
  }
}

main();
