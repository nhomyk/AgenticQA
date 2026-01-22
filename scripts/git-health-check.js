#!/usr/bin/env node
/**
 * Git Health Check - Auto-detects and recovers from git anomalies
 * Prevents manual IDE shutdowns by handling detached HEAD, rebases, merges, etc.
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = process.cwd();
const GIT_DIR = path.join(REPO_ROOT, '.git');

function runCommand(cmd, options = {}) {
  try {
    return execSync(cmd, { 
      encoding: 'utf-8',
      cwd: REPO_ROOT,
      stdio: options.stdio || 'pipe',
      ...options
    }).trim();
  } catch (error) {
    if (options.throwOnError !== false) throw error;
    return error.stdout?.trim() || '';
  }
}

function getGitState() {
  const status = runCommand('git status', { throwOnError: false });
  
  return {
    isRebasing: fs.existsSync(path.join(GIT_DIR, 'rebase-merge')) || 
                fs.existsSync(path.join(GIT_DIR, 'rebase-apply')),
    isMerging: fs.existsSync(path.join(GIT_DIR, 'MERGE_HEAD')),
    isCherryPicking: fs.existsSync(path.join(GIT_DIR, 'CHERRY_PICK_HEAD')),
    isReverting: fs.existsSync(path.join(GIT_DIR, 'REVERT_HEAD')),
    isDetached: status.includes('detached HEAD'),
    hasUnstagedChanges: status.includes('Changes not staged'),
    hasUntrackedFiles: status.includes('Untracked files'),
    hasStagedChanges: status.includes('Changes to be committed'),
    currentBranch: runCommand('git rev-parse --abbrev-ref HEAD', { throwOnError: false })
  };
}

function recoverFromAnomalies(state) {
  const issues = [];
  
  // Handle interrupted rebase
  if (state.isRebasing) {
    console.log('🔄 Detected interrupted rebase - attempting to continue...');
    try {
      runCommand('git rebase --continue');
      console.log('✅ Rebase continued successfully');
    } catch (error) {
      issues.push('Rebase recovery failed - manual intervention needed');
      console.error(`❌ ${issues[issues.length - 1]}`);
    }
  }
  
  // Handle interrupted merge
  if (state.isMerging) {
    console.log('⚠️  Detected interrupted merge - aborting to clean state...');
    try {
      runCommand('git merge --abort');
      console.log('✅ Merge aborted');
    } catch (error) {
      issues.push('Merge abort failed');
      console.error(`❌ ${issues[issues.length - 1]}`);
    }
  }
  
  // Handle cherry-pick
  if (state.isCherryPicking) {
    console.log('⚠️  Detected interrupted cherry-pick - aborting...');
    try {
      runCommand('git cherry-pick --abort');
      console.log('✅ Cherry-pick aborted');
    } catch (error) {
      issues.push('Cherry-pick abort failed');
      console.error(`❌ ${issues[issues.length - 1]}`);
    }
  }
  
  // Handle revert
  if (state.isReverting) {
    console.log('⚠️  Detected interrupted revert - aborting...');
    try {
      runCommand('git revert --abort');
      console.log('✅ Revert aborted');
    } catch (error) {
      issues.push('Revert abort failed');
      console.error(`❌ ${issues[issues.length - 1]}`);
    }
  }
  
  // Handle detached HEAD
  if (state.isDetached && !state.isRebasing) {
    console.log('⚠️  Detected detached HEAD - checking out main branch...');
    try {
      runCommand('git checkout main');
      console.log('✅ Checked out main branch');
    } catch (error) {
      issues.push('Detached HEAD recovery failed - branch checkout failed');
      console.error(`❌ ${issues[issues.length - 1]}`);
    }
  }
  
  return issues;
}

function validateState(state) {
  const blockers = [];
  
  if (state.isRebasing || state.isMerging || state.isCherryPicking || state.isReverting) {
    blockers.push('Git operation in progress (rebase/merge/cherry-pick/revert)');
  }
  
  if (state.isDetached) {
    blockers.push('Detached HEAD state detected');
  }
  
  return blockers;
}

function main(options = {}) {
  console.log('\n🔍 Checking git health...\n');
  
  const state = getGitState();
  console.log(`📍 Current branch: ${state.currentBranch}`);
  console.log(`📊 State: ${JSON.stringify({ 
    rebasing: state.isRebasing,
    merging: state.isMerging,
    detached: state.isDetached,
    staged: state.hasStagedChanges,
    untracked: state.hasUntrackedFiles
  })}\n`);
  
  const recoveryIssues = recoverFromAnomalies(state);
  const remainingBlockers = validateState(getGitState());
  
  if (remainingBlockers.length > 0) {
    console.log('\n❌ Git health check FAILED - blockers remain:\n');
    remainingBlockers.forEach(issue => console.log(`   • ${issue}`));
    
    if (options.exitOnFailure !== false) {
      process.exit(1);
    }
    return false;
  }
  
  console.log('✅ Git health check PASSED - repository is ready for operations\n');
  return true;
}

// Export for programmatic use
module.exports = { getGitState, recoverFromAnomalies, validateState, runCommand };

// Run if executed directly
if (require.main === module) {
  const result = main({ exitOnFailure: process.argv.includes('--exit-on-failure') !== false });
  process.exit(result ? 0 : 1);
}
