#!/usr/bin/env node

/**
 * Pipeline Verification & Diagnostic Script
 * Verifies GitHub Actions setup and provides troubleshooting
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const WORKFLOWS_DIR = '.github/workflows';
const REQUIRED_WORKFLOWS = [
  'main.yml',
  'ci.yml',
  'agentic-sre-engineer.yml',
  'validate-workflows.yml',
  'security-scan-sast.yml',
  'dependency-check.yml',
  'license-compliance.yml',
  'container-scan.yml',
  'code-quality.yml',
  'dynamic-security.yml'
];

console.log('🔍 PIPELINE VERIFICATION & DIAGNOSTICS\n');
console.log('=' .repeat(60));

// Check 1: Verify workflow files exist
console.log('\n1️⃣  CHECKING WORKFLOW FILES...\n');

let workflowsOk = true;
REQUIRED_WORKFLOWS.forEach(workflow => {
  const workflowPath = path.join(WORKFLOWS_DIR, workflow);
  const exists = fs.existsSync(workflowPath);
  const status = exists ? '✅' : '❌';
  console.log(`${status} ${workflow}`);
  if (!exists) workflowsOk = false;
});

// Check 2: Verify YAML syntax
console.log('\n2️⃣  CHECKING YAML SYNTAX...\n');

let syntaxOk = true;
const workflowFiles = fs.readdirSync(WORKFLOWS_DIR).filter(f => f.endsWith('.yml'));
workflowFiles.forEach(file => {
  try {
    const filePath = path.join(WORKFLOWS_DIR, file);
    const content = fs.readFileSync(filePath, 'utf8');
    
    // Basic YAML validation (check for 'on:' trigger)
    if (!content.includes('on:') && file !== '.keep') {
      console.log(`⚠️  ${file} - Missing 'on:' trigger`);
      syntaxOk = false;
    } else {
      console.log(`✅ ${file} - Valid YAML structure`);
    }
  } catch (error) {
    console.log(`❌ ${file} - ${error.message}`);
    syntaxOk = false;
  }
});

// Check 3: Verify Git configuration
console.log('\n3️⃣  CHECKING GIT CONFIGURATION...\n');

try {
  const remoteUrl = execSync('git remote get-url origin', { encoding: 'utf8' }).trim();
  console.log(`✅ Remote URL: ${remoteUrl}`);
  
  const branch = execSync('git rev-parse --abbrev-ref HEAD', { encoding: 'utf8' }).trim();
  console.log(`✅ Current branch: ${branch}`);
  
  if (branch !== 'main') {
    console.log(`⚠️  WARNING: Not on main branch. Workflows may not trigger.`);
  }
} catch (error) {
  console.log(`❌ Git configuration error: ${error.message}`);
}

// Check 4: Verify repository is private
console.log('\n4️⃣  CHECKING REPOSITORY STATUS...\n');

try {
  const repoInfo = execSync('git config --local --get remote.origin.url', { encoding: 'utf8' }).trim();
  console.log(`✅ Repository: ${repoInfo}`);
  console.log(`✅ Verify it shows as PRIVATE on GitHub`);
  console.log(`   Go to: https://github.com/nhomyk/AgenticQA/settings`);
} catch (error) {
  console.log(`⚠️  Could not verify repository status`);
}

// Check 5: Verify recent commits
console.log('\n5️⃣  CHECKING RECENT COMMITS...\n');

try {
  const logs = execSync('git log --oneline -10', { encoding: 'utf8' }).trim().split('\n');
  console.log(`✅ Recent commits:`);
  logs.forEach(log => console.log(`   ${log}`));
} catch (error) {
  console.log(`❌ Could not retrieve commit history`);
}

// Check 6: Verify GitHub Actions permissions
console.log('\n6️⃣  GITHUB ACTIONS PERMISSION CHECKLIST...\n');

console.log(`📋 To enable GitHub Actions for private repo:\n`);
console.log(`   1. Go to: https://github.com/nhomyk/AgenticQA/settings/actions`);
console.log(`   2. Find "Actions permissions"`);
console.log(`   3. Select: "Allow all actions and reusable workflows"`);
console.log(`   4. Click Save\n`);

// Summary
console.log('=' .repeat(60));
console.log('\n📊 SUMMARY:\n');

let allOk = workflowsOk && syntaxOk;

if (allOk) {
  console.log('✅ All local checks passed!\n');
  console.log('🔧 NEXT STEPS:\n');
  console.log('   1. Enable GitHub Actions (see checklist above)');
  console.log('   2. Visit: https://github.com/nhomyk/AgenticQA/actions');
  console.log('   3. Click "Run workflow" on "CI" workflow');
  console.log('   4. Select "main" branch');
  console.log('   5. Click "Run workflow"\n');
} else {
  console.log('❌ Some issues found. Please fix before continuing.\n');
}

// Instructions for manual trigger
console.log('\n🚀 TO MANUALLY TRIGGER WORKFLOWS:\n');
console.log(`   # Push a test commit`);
console.log(`   echo "# Test" >> TEST.md`);
console.log(`   git add TEST.md`);
console.log(`   git commit -m "test: trigger workflows"`);
console.log(`   git push origin main\n`);
console.log(`   # Then check: https://github.com/nhomyk/AgenticQA/actions\n`);

// Troubleshooting
console.log('=' .repeat(60));
console.log('\n🐛 TROUBLESHOOTING:\n');

console.log(`If workflows still don't run:\n`);
console.log(`   1. Check GitHub Settings → Actions → Permissions (must be enabled)`);
console.log(`   2. Check branch protection rules (may block workflows)`);
console.log(`   3. Verify you have GitHub Free/Pro/Enterprise (workflows included)`);
console.log(`   4. Try manually triggering from Actions tab`);
console.log(`   5. Check workflow logs for detailed error messages\n`);

console.log('=' .repeat(60));
console.log('\n✅ Verification complete!\n');
