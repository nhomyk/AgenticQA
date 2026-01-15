#!/usr/bin/env node
/**
 * Automatic Post-Push Workflow Verification
 * This script checks if the pushed code triggered any workflow runs and monitors their status
 * Usage: node post-push-verify.js
 */

const https = require('https');
const { execSync } = require('child_process');

const REPO_OWNER = 'nhomyk';
const REPO_NAME = 'AgenticQA';
const CHECK_INTERVAL = 3000; // 3 seconds
const MAX_WAIT_TIME = 120000; // 2 minutes

let latestCommitSha = null;

function getLatestCommitSha() {
  try {
    return execSync('git rev-parse HEAD', { encoding: 'utf8' }).trim();
  } catch (e) {
    return null;
  }
}

function makeGitHubRequest(path) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'api.github.com',
      port: 443,
      path,
      method: 'GET',
      headers: {
        'User-Agent': 'AgenticQA-PostPushVerify',
        'Accept': 'application/vnd.github.v3+json'
      }
    };

    https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(new Error(`Failed to parse response: ${e.message}`));
        }
      });
    }).on('error', reject).end();
  });
}

async function checkWorkflowStatus() {
  if (!latestCommitSha) {
    latestCommitSha = getLatestCommitSha();
    if (!latestCommitSha) {
      console.log('❌ Could not get latest commit SHA');
      return { status: 'error' };
    }
  }

  try {
    // Get recent CI runs
    const ciRuns = await makeGitHubRequest(
      `/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/ci.yml/runs?per_page=3`
    );

    if (!ciRuns.workflow_runs || ciRuns.workflow_runs.length === 0) {
      return { status: 'pending', message: 'No runs found yet' };
    }

    // Find run matching our commit
    const matchingRun = ciRuns.workflow_runs.find(r => 
      r.head_sha === latestCommitSha
    );

    if (!matchingRun) {
      const latest = ciRuns.workflow_runs[0];
      return {
        status: 'pending',
        message: `Waiting for run to appear (latest: #${latest.run_number} for commit ${latest.head_sha.substring(0, 7)})`
      };
    }

    return {
      status: matchingRun.status,
      conclusion: matchingRun.conclusion,
      runNumber: matchingRun.run_number,
      runId: matchingRun.id,
      headCommit: matchingRun.head_commit.message
    };

  } catch (err) {
    return { status: 'error', error: err.message };
  }
}

async function wait() {
  console.log('\n📊 POST-PUSH WORKFLOW VERIFICATION\n');
  console.log(`Latest commit: ${latestCommitSha || 'detecting...'}\n`);

  const startTime = Date.now();
  let lastResult = null;
  let checks = 0;

  while (Date.now() - startTime < MAX_WAIT_TIME) {
    const result = await checkWorkflowStatus();
    checks++;

    if (result.status === 'error') {
      console.log(`⚠️  Error: ${result.error}`);
    } else if (result.status === 'pending') {
      process.stdout.write(`\r⏳ [${checks}] Waiting for CI workflow... ${result.message || ''}`);
    } else if (result.status === 'in_progress') {
      console.log(`\n✅ CI Workflow triggered - Run #${result.runNumber}`);
      console.log(`   Status: IN PROGRESS`);
      console.log(`   Commit: ${result.headCommit}\n`);
      
      console.log('⏳ Waiting for completion...');
      lastResult = result;
    } else if (result.status === 'completed') {
      if (result.conclusion === 'success') {
        console.log(`\n✅ CI WORKFLOW SUCCEEDED`);
        console.log(`   Run #${result.runNumber}`);
        console.log(`   Status: ${result.conclusion}`);
        return { success: true, result };
      } else {
        console.log(`\n❌ CI WORKFLOW FAILED`);
        console.log(`   Run #${result.runNumber}`);
        console.log(`   Conclusion: ${result.conclusion}`);
        return { success: false, result };
      }
    }

    if (result.status !== 'pending') {
      lastResult = result;
    }

    await new Promise(resolve => setTimeout(resolve, CHECK_INTERVAL));
  }

  console.log('\n⏱️  Timeout waiting for workflow completion');
  if (lastResult) {
    console.log(`Last status: ${lastResult.status} / ${lastResult.conclusion || 'pending'}\n`);
  }

  return { success: null, timeout: true };
}

// Run if called directly
if (require.main === module) {
  wait()
    .then(result => {
      if (result.success === true) {
        console.log('\n🎉 All systems operational!\n');
        process.exit(0);
      } else if (result.success === false) {
        console.log('\n⚠️  Check the workflow logs for details\n');
        console.log(`View at: https://github.com/${REPO_OWNER}/${REPO_NAME}/actions/runs/${result.result.runId}\n`);
        process.exit(1);
      } else {
        console.log('\nCould not verify workflow completion. Check GitHub Actions manually.\n');
        process.exit(0);
      }
    })
    .catch(err => {
      console.error('\n❌ Error:', err.message, '\n');
      process.exit(1);
    });
}

module.exports = { checkWorkflowStatus, wait, getLatestCommitSha };
