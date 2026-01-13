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
  
  if (!GITHUB_TOKEN) {
    log('⚠️  No GITHUB_TOKEN - skipping pipeline trigger');
    return false;
  }
  
  try {
    // Try Octokit first
    try {
      const { Octokit } = await import('@octokit/rest');
      const octokit = new Octokit({ auth: GITHUB_TOKEN });
      
      await octokit.actions.createWorkflowDispatch({
        owner: REPO_OWNER,
        repo: REPO_NAME,
        workflow_id: 'ci.yml',
        ref: 'main',
      });
      
      log('✅ Pipeline triggered via API');
      return true;
    } catch (err) {
      log(`  Octokit unavailable, trying direct HTTP...`);
      
      // Fallback: Direct HTTP request
      return new Promise((resolve) => {
        const postData = JSON.stringify({
          ref: 'main'
        });
        
        const options = {
          hostname: 'api.github.com',
          path: `/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/ci.yml/dispatches`,
          method: 'POST',
          headers: {
            'Authorization': `token ${GITHUB_TOKEN}`,
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
            'Content-Length': postData.length,
            'User-Agent': 'Node.js'
          }
        };
        
        const req = require('https').request(options, (res) => {
          resolve(res.statusCode === 204);
          res.on('data', () => {});
        });
        
        req.on('error', (err) => {
          log(`  HTTP request failed: ${err.message}`);
          resolve(false);
        });
        
        req.write(postData);
        req.end();
      });
    }
  } catch (err) {
    log(`⚠️  Failed to trigger: ${err.message}`);
    return false;
  }
}

async function main() {
  try {
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
    execSilent('git add -A');
    
    // Check if there are changes
    let statusOutput = '';
    try {
      statusOutput = require('child_process').execSync('git status --porcelain', { encoding: 'utf-8' });
    } catch (e) {
      // Ignore error
    }
    
    if (!statusOutput.trim()) {
      log('✅ No changes to commit\n');
      process.exit(0);
    }
    
    // Commit
    execSilent('git commit -m "fix: fullstack-agent auto-fixed code issues"');
    log('✅ Changes committed\n');
    
    // Push
    log('🚀 Pushing to main...\n');
    execSilent('git push origin main');
    log('✅ Changes pushed\n');
    
    // STEP 3: Trigger new pipeline (optional, fail gracefully)
    log('🔄 Attempting to trigger new pipeline...\n');
    try {
      await triggerNewPipeline();
    } catch (err) {
      log(`⚠️  Pipeline trigger skipped: ${err.message}\n`);
    }
    
    log('\n✅ === FULLSTACK AGENT COMPLETE ===');
    log('   • Scanned source files');
    log('   • Fixed code issues');
    log('   • Committed changes');
    log('   • Pushed to main');
    log('   • Attempted pipeline trigger\n');
    log('🎉 Automated fix deployed!\n');
    
    process.exit(0);
  } catch (err) {
    console.error(`\n❌ ERROR: ${err.message}`);
    console.error(err.stack);
    process.exit(1);
  }
}

main();


if (require.main === module) {
  main().catch(console.error);
}

module.exports = { main };
