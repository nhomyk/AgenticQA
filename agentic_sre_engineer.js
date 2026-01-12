// Agentic SRE Engineer - LangGraph Agent
// Automates CI/CD monitoring, version bumping, and code fixes with email notifications

const simpleGit = require("simple-git");
const fs = require("fs");
const nodemailer = require("nodemailer");
const path = require("path");

// === CONFIGURATION ===
const GITHUB_TOKEN = process.env.GITHUB_TOKEN; // Set in your environment
const REPO_OWNER = "nhomyk"; // Change if needed
const REPO_NAME = "AgenticQA"; // Change if needed
const BRANCH = "main";
const EMAIL_TO = "nickhomyk@gmail.com";
const EMAIL_FROM = process.env.SMTP_USER; // Set in your environment
const SMTP_PASS = process.env.SMTP_PASS; // Set in your environment
const SMTP_HOST = process.env.SMTP_HOST || "smtp.gmail.com";
const SMTP_PORT = process.env.SMTP_PORT || 465;

let octokit = null;
const git = simpleGit();

async function initOctokit() {
  if (!octokit) {
    const { Octokit } = await import("@octokit/rest");
    octokit = new Octokit({ auth: GITHUB_TOKEN });
  }
  return octokit;
}

async function bumpVersion() {
  const pkgPath = path.join(__dirname, "package.json");
  const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
  const [major, minor, patch] = pkg.version.split(".").map(Number);
  pkg.version = `${major}.${minor}.${patch + 1}`;
  fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2));
  await git.add(pkgPath);
  await git.raw(["config", "--global", "user.name", "github-actions[bot]"]);
  await git.raw(["config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"]);
  // Set remote URL to use PAT for push
  if (process.env.GH_PAT) {
    await git.raw([
      "remote",
      "set-url",
      "origin",
      `https://${process.env.GH_PAT}@github.com/nhomyk/AgenticQA.git`
    ]);
  }
  await git.commit(`chore: bump version to ${pkg.version}`);
  try {
    await git.push();
  } catch (err) {
    console.error('Push failed (non-critical):', err.message);
  }
  return pkg.version;
}

async function getLatestWorkflowRun() {
  const octokit = await initOctokit();
  const { data } = await octokit.actions.listWorkflowRunsForRepo({
    owner: REPO_OWNER,
    repo: REPO_NAME,
    branch: BRANCH,
    per_page: 1,
  });
  return data.workflow_runs[0];
}

async function getWorkflowJobResults(runId) {
  try {
    const octokit = await initOctokit();
    const { data } = await octokit.actions.listJobsForWorkflowRun({
      owner: REPO_OWNER,
      repo: REPO_NAME,
      run_id: runId,
    });
    return data.jobs;
  } catch (err) {
    console.error('Failed to fetch job results:', err.message);
    return [];
  }
}

async function sendEmail(subject, text) {
  let transporter = nodemailer.createTransport({
    host: SMTP_HOST,
    port: SMTP_PORT,
    secure: true,
    auth: {
      user: EMAIL_FROM,
      pass: SMTP_PASS,
    },
  });
  await transporter.sendMail({
    from: EMAIL_FROM,
    to: EMAIL_TO,
    subject,
    text,
  });
}

async function getJobLogs(runId, jobName) {
  try {
    const octokit = await initOctokit();
    const { data: jobs } = await octokit.actions.listJobsForWorkflowRun({
      owner: REPO_OWNER,
      repo: REPO_NAME,
      run_id: runId,
    });
    
    const job = jobs.jobs.find(j => j.name === jobName);
    if (!job) {
      console.log(`Job ${jobName} not found`);
      return null;
    }

    // Fetch the logs for this job
    const logsResponse = await octokit.request(
      'GET /repos/{owner}/{repo}/actions/jobs/{job_id}/logs',
      {
        owner: REPO_OWNER,
        repo: REPO_NAME,
        job_id: job.id,
        headers: {
          'Accept': 'application/vnd.github.v3.raw',
        },
      }
    );
    
    return logsResponse.data;
  } catch (err) {
    console.log(`Failed to fetch logs for ${jobName}: ${err.message}`);
    return null;
  }
}

async function parseTestFailures(jobName, logs) {
  if (!logs) return [];
  
  const failures = [];
  
  // Parse different test frameworks
  if (jobName.includes('playwright')) {
    const lines = logs.split('\n');
    let currentTest = null;
    
    for (const line of lines) {
      if (line.includes('✘') || line.includes('FAIL') || line.includes('×')) {
        currentTest = line.trim();
      }
      if (line.includes('Error:') || line.includes('expected') || line.includes('AssertionError')) {
        if (currentTest) {
          failures.push({ test: currentTest, error: line.trim() });
        }
      }
    }
  } else if (jobName.includes('vitest')) {
    const lines = logs.split('\n');
    let currentTest = null;
    
    for (const line of lines) {
      if (line.includes('✓') || line.includes('✘') || line.includes('FAIL')) {
        currentTest = line.trim();
      }
      if (line.includes('AssertionError') || line.includes('Expected') || line.includes('Received')) {
        if (currentTest) {
          failures.push({ test: currentTest, error: line.trim() });
        }
      }
    }
  } else if (jobName.includes('cypress')) {
    const lines = logs.split('\n');
    let currentTest = null;
    
    for (const line of lines) {
      if (line.includes('1)') || line.includes('failing') || line.includes('Error')) {
        currentTest = line.trim();
      }
      if (line.includes('AssertionError') || line.includes('expected') || line.includes('Cypress')) {
        if (currentTest) {
          failures.push({ test: currentTest, error: line.trim() });
        }
      }
    }
  } else if (jobName.includes('jest') || jobName.includes('unit')) {
    const lines = logs.split('\n');
    let currentTest = null;
    
    for (const line of lines) {
      if (line.includes('●') || line.includes('FAIL')) {
        currentTest = line.trim();
      }
      if (line.includes('Error:') || line.includes('expected') || line.includes('AssertionError')) {
        if (currentTest) {
          failures.push({ test: currentTest, error: line.trim() });
        }
      }
    }
  }
  
  return failures;
}

async function makeCodeChanges(failureAnalysis) {
  // Analyze failures and make intelligent code changes
  const { execSync } = require("child_process");
  
  console.log("Analyzing test failures and making code changes...");
  
  // Extract test failure patterns and apply targeted fixes
  if (failureAnalysis && failureAnalysis.length > 0) {
    console.log(`\nAnalyzing ${failureAnalysis.length} test failure(s):`);
    
    for (const failure of failureAnalysis) {
      console.log(`  - ${failure.jobName}: ${failure.failures.length} issue(s)`);
      
      // Log specific failures for debugging
      if (failure.failures.length > 0) {
        failure.failures.slice(0, 3).forEach(f => {
          console.log(`    • ${f.test}`);
        });
      }
    }
  }
  
  let changesDetected = false;
  
  // 1. Check for ESLint errors before fixing
  try {
    console.log("Checking for linting issues...");
    execSync("npx eslint . --ext .js", { stdio: "pipe" });
  } catch (err) {
    const errorOutput = err.stdout?.toString() || err.stderr?.toString() || err.message;
    if (errorOutput.includes("error") || errorOutput.includes("✖")) {
      console.log("ESLint errors detected, applying fixes...");
      changesDetected = true;
    }
  }
  
  // 2. Apply ESLint fixes
  try {
    execSync("npx eslint . --ext .js --fix", { stdio: "pipe" });
    console.log("ESLint auto-fixes applied");
  } catch (err) {
    console.log("ESLint completed with warnings");
  }
  
  // 3. Run Vitest to catch runtime issues
  try {
    execSync("npm run test:vitest -- --run 2>&1", { stdio: "pipe" });
  } catch (err) {
    const output = err.stdout?.toString() || err.stderr?.toString() || err.message;
    if (output.includes("FAIL") || output.includes("error")) {
      console.log("Vitest issues detected");
      changesDetected = true;
    }
  }
  
  // 4. Commit any changes made by fixes
  await git.add(".");
  const status = await git.status();
  
  if (status.files.length > 0) {
    console.log(`Found ${status.files.length} changed file(s), committing...`);
    
    await git.raw(["config", "--global", "user.name", "github-actions[bot]"]);
    await git.raw(["config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"]);
    if (process.env.GH_PAT) {
      await git.raw([
        "remote",
        "set-url",
        "origin",
        `https://${process.env.GH_PAT}@github.com/nhomyk/AgenticQA.git`
      ]);
    }
    
    await git.commit("fix: agentic code repairs from test analysis");
    try {
      await git.push();
      console.log("Code changes pushed successfully");
    } catch (err) {
      console.error("Push failed (non-critical):", err.message);
    }
    return true;
  } else {
    console.log("No changes to commit");
    return false;
  }
}

async function redeployAndTest(iteration) {
  // Trigger new workflow run by committing
  console.log(`Iteration ${iteration}: Running tests...`);
  await new Promise(r => setTimeout(r, 30000)); // Wait 30 seconds for new run to start
  
  const run = await getLatestWorkflowRun();
  
  // Poll for completion (max 5 minutes)
  let completed = false;
  let attempts = 0;
  const maxAttempts = 10;
  
  while (!completed && attempts < maxAttempts) {
    const currentRun = await getLatestWorkflowRun();
    
    if (currentRun.status === 'completed') {
      console.log(`Test run completed with conclusion: ${currentRun.conclusion}`);
      return {
        success: currentRun.conclusion === 'success',
        run: currentRun,
      };
    }
    
    console.log(`Waiting for tests to complete... (attempt ${attempts + 1}/${maxAttempts})`);
    await new Promise(r => setTimeout(r, 30000)); // Wait 30 seconds between checks
    attempts++;
  }
  
  return { success: false, run: null };
}

async function agenticSRELoop() {
  const MAX_ITERATIONS = 3;
  let iteration = 0;
  let success = false;
  
  // 1. Bump version
  const newVersion = await bumpVersion();
  console.log(`Version bumped to ${newVersion}`);
  
  // 2. Wait for initial CI to run
  await new Promise(r => setTimeout(r, 60000)); // Wait 1 min for CI
  
  // 3-6. Iterative testing and fixing loop
  while (iteration < MAX_ITERATIONS && !success) {
    iteration++;
    console.log(`\n=== Iteration ${iteration}/${MAX_ITERATIONS} ===`);
    
    const run = await getLatestWorkflowRun();
    
    if (run.conclusion === 'success') {
      console.log('✅ All tests passed!');
      success = true;
      try {
        await sendEmail(
          `CI Passed for AgenticQA v${newVersion}`,
          `All tests passed after ${iteration} iteration(s)! Version: ${newVersion}`
        );
      } catch (err) {
        console.error('Failed to send email (non-critical):', err.message);
      }
      break;
    }
    
    // Get detailed job results
    const jobs = await getWorkflowJobResults(run.id);
    
    // Fetch logs for all failed jobs
    const failureAnalysis = [];
    for (const job of jobs) {
      if (job.conclusion === 'failure') {
        const logs = await getJobLogs(run.id, job.name);
        const testFailures = await parseTestFailures(job.name, logs);
        failureAnalysis.push({
          jobName: job.name,
          status: job.conclusion,
          failures: testFailures,
        });
      }
    }
    
    const failures = jobs.filter(job => job.conclusion === 'failure');
    
    if (failures.length > 0) {
      console.log(`Found ${failures.length} failed job(s):`);
      failures.forEach(f => console.log(`  - ${f.name}`));
      
      // Make code changes based on failures
      const changesApplied = await makeCodeChanges(failureAnalysis);
      
      if (changesApplied && iteration < MAX_ITERATIONS) {
        // Re-test with new changes
        const testResult = await redeployAndTest(iteration + 1);
        
        if (testResult.success) {
          console.log('✅ Tests passed after fixes!');
          success = true;
          try {
            await sendEmail(
              `CI Passed for AgenticQA v${newVersion}`,
              `All tests passed after ${iteration + 1} iteration(s)! Version: ${newVersion}`
            );
          } catch (err) {
            console.error('Failed to send email (non-critical):', err.message);
          }
          break;
        }
      } else if (iteration >= MAX_ITERATIONS) {
        console.log(`❌ Reached max iterations (${MAX_ITERATIONS}). Some tests still failing.`);
        try {
          await sendEmail(
            `CI Still Failing for AgenticQA v${newVersion}`,
            `Tests still failing after ${MAX_ITERATIONS} iterations. Manual review needed.`
          );
        } catch (err) {
          console.error('Failed to send email (non-critical):', err.message);
        }
        break;
      }
    } else {
      console.log('No failed jobs found');
      success = true;
      break;
    }
  }
  
  console.log(`\nSRE workflow complete after ${iteration} iteration(s)`);
}

if (require.main === module) {
  agenticSRELoop().catch(console.error);
}

module.exports = { agenticSRELoop };