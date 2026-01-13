const { Octokit } = require('@octokit/rest');

const token = process.env.GITHUB_TOKEN || process.env.GH_PAT;

if (!token) {
  console.log('❌ No GitHub token available');
  console.log('Set GITHUB_TOKEN or GH_PAT environment variable');
  process.exit(1);
}

const octokit = new Octokit({ auth: token });

(async () => {
  try {
    console.log('📋 Checking workflow runs...\n');
    
    const runs = await octokit.actions.listWorkflowRuns({
      owner: 'nhomyk',
      repo: 'AgenticQA',
      workflow_id: 'ci.yml',
      per_page: 10
    });
    
    console.log(`Found ${runs.data.workflow_runs.length} recent runs:\n`);
    
    runs.data.workflow_runs.forEach((run, idx) => {
      console.log(`${idx + 1}. Run #${run.id}`);
      console.log(`   Name: ${run.name}`);
      console.log(`   Status: ${run.status}`);
      console.log(`   Conclusion: ${run.conclusion}`);
      console.log(`   Created: ${run.created_at}`);
      console.log(`   Head Branch: ${run.head_branch}`);
      console.log(`   Head Commit: ${run.head_sha.substring(0, 7)}\n`);
    });
    
    // Check the most recent run's jobs
    if (runs.data.workflow_runs.length > 0) {
      const latestRun = runs.data.workflow_runs[0];
      console.log(`\n📊 Jobs in latest run (#${latestRun.id}):\n`);
      
      const jobs = await octokit.actions.listJobsForWorkflowRun({
        owner: 'nhomyk',
        repo: 'AgenticQA',
        run_id: latestRun.id
      });
      
      jobs.data.jobs.forEach(job => {
        console.log(`  • ${job.name}`);
        console.log(`    Status: ${job.status}`);
        console.log(`    Conclusion: ${job.conclusion}`);
      });
    }
    
  } catch (err) {
    console.error('❌ Error:', err.message);
    if (err.status === 401) {
      console.log('\n🔑 Token authentication failed. Verify the token has:');
      console.log('   - repo:status');
      console.log('   - repo:read');
      console.log('   - actions:read');
    }
  }
})();
