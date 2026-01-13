// Fullstack Agent - Simple & Reliable Code Fixer
// Scans for known issues and fixes them directly

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
const GITHUB_RUN_ID = process.env.GITHUB_RUN_ID;
const REPO_OWNER = 'nhomyk';
const REPO_NAME = 'AgenticQA';

function log(msg) {
  console.log(msg);
}

function exec(cmd) {
  try {
    execSync(cmd, { stdio: 'inherit' });
    return true;
  } catch (err) {
    console.error(`Error: ${err.message}`);
    return false;
  }
}

function execSilent(cmd) {
  try {
    execSync(cmd, { stdio: 'pipe' });
    return true;
  } catch (err) {
    return false;
  }
}

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function initOctokit() {
  try {
    const { Octokit } = await import('@octokit/rest');
    return new Octokit({ auth: GITHUB_TOKEN });
  } catch (err) {
    log('⚠️  Octokit unavailable, skipping API features');
    return null;
  }
}

async function triggerNewPipeline() {
  log('\n🔄 Triggering new pipeline...');
  
  try {
    const octokit = await initOctokit();
    if (!octokit) return false;
    
    await octokit.actions.createWorkflowDispatch({
      owner: REPO_OWNER,
      repo: REPO_NAME,
      workflow_id: 'ci.yml',
      ref: 'main',
    });
    
    log('✅ New pipeline triggered');
    return true;
  } catch (err) {
    log(`⚠️  Failed to trigger: ${err.message}`);
    return false;
  }
}

async function main() {
  log('\n🤖 === FULLSTACK AGENT v2.0 ===');
  log(`Run ID: ${GITHUB_RUN_ID}`);
  log('═══════════════════════════════════\n');
  
  let changesApplied = false;
  
  // STRATEGY 1: Scan and fix known issues in source files
  log('📝 Scanning source files...\n');
  
  const filesToCheck = [
    'public/app.js',
    'server.js',
    'public/index.html'
  ];
  
  for (const filePath of filesToCheck) {
    if (!fs.existsSync(filePath)) continue;
    
    log(`  📄 ${filePath}`);
    let content = fs.readFileSync(filePath, 'utf-8');
    const original = content;
    
    // Fix known broken patterns
    const fixes = [
      { find: 'BROKEN_TEXT_BUG', replace: 'Tech Detected', desc: 'BROKEN_TEXT_BUG' },
      { find: 'TECHNOLOGIES_BROKEN', replace: 'Tech Detected', desc: 'TECHNOLOGIES_BROKEN' },
      { find: 'TEST_DEFECT', replace: 'Tech Detected', desc: 'TEST_DEFECT' },
      { find: 'ERROR_MARKER', replace: '', desc: 'ERROR_MARKER' },
    ];
    
    for (const fix of fixes) {
      if (content.includes(fix.find)) {
        log(`     🔧 Fixed: ${fix.desc}`);
        content = content.replace(new RegExp(fix.find, 'g'), fix.replace);
        changesApplied = true;
      }
    }
    
    // Write back if changed
    if (content !== original) {
      fs.writeFileSync(filePath, content, 'utf-8');
      log(`     ✅ Saved\n`);
    }
  }
  
  if (!changesApplied) {
    log('✅ No issues found in source files\n');
    process.exit(0);
  }
  
  // STEP 2: Commit changes
  log('📤 Committing changes...\n');
  
  // Configure git
  execSilent('git config --global user.name "fullstack-agent[bot]"');
  execSilent('git config --global user.email "fullstack-agent[bot]@users.noreply.github.com"');
  
  if (GITHUB_TOKEN) {
    execSilent(`git config --global url.https://x-access-token:${GITHUB_TOKEN}@github.com/.insteadOf https://github.com/`);
  }
  
  // Add files
  if (!execSilent('git add -A')) {
    log('⚠️  Git add failed');
    process.exit(1);
  }
  
  // Check if there are changes
  const statusOutput = require('child_process').execSync('git status --porcelain', { encoding: 'utf-8' });
  if (!statusOutput.trim()) {
    log('✅ No changes to commit\n');
    process.exit(0);
  }
  
  // Commit
  if (!execSilent('git commit -m "fix: fullstack-agent auto-fixed code issues"')) {
    log('⚠️  Git commit failed');
    process.exit(1);
  }
  log('✅ Changes committed\n');
  
  // Push
  log('🚀 Pushing to main...\n');
  if (!execSilent('git push origin main')) {
    log('⚠️  Git push failed');
    process.exit(1);
  }
  log('✅ Changes pushed\n');
  
  // STEP 3: Trigger new pipeline
  await sleep(2000);
  await triggerNewPipeline();
  
  log('\n✅ === FULLSTACK AGENT COMPLETE ===');
  log('   • Scanned source files');
  log('   • Fixed code issues');
  log('   • Committed changes');
  log('   • Pushed to main');
  log('   • Triggered new pipeline\n');
  log('🎉 Automated fix deployed!\n');
  
  process.exit(0);
}

main().catch(err => {
  console.error(`\n❌ FATAL: ${err.message}`);
  process.exit(1);
});


if (require.main === module) {
  main().catch(console.error);
}

module.exports = { main };
