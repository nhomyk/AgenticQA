#!/usr/bin/env node
/**
 * Safe Git Commit Wrapper
 * Automatically detects and fixes git state issues before committing
 * Usage: node scripts/git-safe-commit.js "commit message" [--push]
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = process.cwd();
const args = process.argv.slice(2);
const commitMessage = args[0];
const shouldPush = args.includes('--push');

if (!commitMessage) {
  console.error('❌ Error: Commit message required');
  console.error('Usage: npm run git:commit -- "Your commit message" [--push]');
  process.exit(1);
}

function run(cmd) {
  try {
    return execSync(cmd, { 
      encoding: 'utf-8',
      cwd: REPO_ROOT,
      stdio: 'pipe'
    }).trim();
  } catch (error) {
    throw error;
  }
}

function ensureGitHealth() {
  console.log('🔍 Ensuring git health...');
  try {
    require('./git-health-check.js');
    console.log('✅ Git health verified');
  } catch (error) {
    console.error('❌ Git health check failed');
    throw error;
  }
}

function commit(message) {
  console.log(`📝 Committing: "${message}"`);
  try {
    run(`git add -A`);
    run(`git commit -m "${message}"`);
    console.log('✅ Commit successful');
    return true;
  } catch (error) {
    console.error('❌ Commit failed:', error.message);
    throw error;
  }
}

function pushChanges() {
  console.log('🚀 Pushing to remote...');
  try {
    run('git push');
    console.log('✅ Push successful');
  } catch (error) {
    console.error('❌ Push failed:', error.message);
    throw error;
  }
}

async function main() {
  try {
    ensureGitHealth();
    commit(commitMessage);
    
    if (shouldPush) {
      pushChanges();
    }
    
    console.log('\n✅ All operations completed successfully\n');
  } catch (error) {
    console.error(`\n❌ Operation failed: ${error.message}\n`);
    process.exit(1);
  }
}

main();
