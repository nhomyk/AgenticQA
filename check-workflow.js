#!/usr/bin/env node

// Simple workflow checker - no external dependencies

const https = require('https');

function makeRequest(url) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { 'User-Agent': 'Node.js' } }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(e);
        }
      });
    }).on('error', reject);
  });
}

async function checkWorkflow() {
  console.log('🔍 Checking workflow status...\n');
  
  try {
    const runs = await makeRequest('https://api.github.com/repos/nhomyk/AgenticQA/actions/runs?per_page=3');
    
    if (!runs.workflow_runs || runs.workflow_runs.length === 0) {
      console.log('No runs found');
      return;
    }
    
    for (let i = 0; i < Math.min(2, runs.workflow_runs.length); i++) {
      const run = runs.workflow_runs[i];
      console.log(`Run #${i + 1}: ${run.name}`);
      console.log(`  Status: ${run.status}`);
      console.log(`  Conclusion: ${run.conclusion}`);
      console.log(`  Created: ${run.created_at}`);
      console.log(`  Updated: ${run.updated_at}`);
      
      // Check jobs in this run
      const jobsUrl = run.jobs_url;
      const jobs = await makeRequest(jobsUrl);
      
      if (jobs.jobs) {
        console.log(`  Jobs:`);
        for (const job of jobs.jobs) {
          console.log(`    • ${job.name}: ${job.conclusion} (${job.status})`);
        }
      }
      console.log('');
    }
  } catch (err) {
    console.error('Error:', err.message);
  }
}

checkWorkflow();
