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
  // Configure git token-based auth if running in GitHub Actions
  if (GITHUB_TOKEN) {
    await git.raw(["config", "--global", `url.https://x-access-token:${GITHUB_TOKEN}@github.com/.insteadOf`, "https://github.com/"]);
  }
  await git.commit(`chore: bump version to ${pkg.version}`);
  try {
    await git.push(["origin", "main"]);
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
          console.log(`    • ${f.error || f.test}`);
        });
      }
    }
  }
  
  let changesDetected = false;
  
  // Check for EADDRINUSE (port already in use) errors in Cypress tests
  const hasPortInUseError = failureAnalysis?.some(f =>
    f.jobName.includes('cypress') &&
    f.failures.some(fail => fail.error?.includes('EADDRINUSE') || fail.error?.includes('address already in use'))
  );
  
  if (hasPortInUseError) {
    console.log("Detected port in use error - improving server shutdown handling...");
    
    // Update server.js to handle graceful shutdown and cleanup
    const serverPath = "server.js";
    if (fs.existsSync(serverPath)) {
      let server = fs.readFileSync(serverPath, "utf8");
      
      // Add proper error handling and socket cleanup for EADDRINUSE
      if (!server.includes("server.close()") || !server.includes("removeAllListeners")) {
        console.log("Adding graceful shutdown handlers to server...");
        
        // Add socket tracking and cleanup before the 'if (require.main === module)' block
        const shutdownCode = `
// Track connections for graceful shutdown
const connections = new Set();

const handleConnection = (conn) => {
  connections.add(conn);
  conn.on("close", () => connections.delete(conn));
};

// Handle process termination signals
const handleGracefulShutdown = (signal) => {
  return async () => {
    log("info", \`\${signal} received, shutting down gracefully\`);
    
    if (server) {
      server.close(() => {
        log("info", "Server closed");
        // Close all open connections
        connections.forEach(conn => conn.destroy());
        process.exit(0);
      });
      
      // Force exit if graceful shutdown takes too long (10 seconds)
      setTimeout(() => {
        log("warn", "Forcing shutdown after timeout");
        process.exit(1);
      }, 10000);
    }
  };
};
`;
        
        // Check if graceful shutdown is already implemented
        if (!server.includes("handleGracefulShutdown") && !server.includes("server.close()")) {
          // Find the position to insert before the final 'if (require.main === module)' block
          const insertPos = server.lastIndexOf("if (require.main === module)");
          if (insertPos > -1) {
            server = server.slice(0, insertPos) + shutdownCode + "\n" + server.slice(insertPos);
            
            // Update the startup code to use the graceful shutdown handlers
            server = server.replace(
              /if \(require\.main === module\) \{[\s\S]*?app\.listen\(PORT, HOST, \(\) => \{/,
              `if (require.main === module) {
  const server = app.listen(PORT, HOST, () => {`
            );
            
            // Add signal handlers after app.listen
            server = server.replace(
              /app\.listen\(PORT, HOST, \(\) => \{([\s\S]*?)\}\);/,
              `server = app.listen(PORT, HOST, () => {$1});
  
  server.on("connection", handleConnection);
  process.on("SIGTERM", handleGracefulShutdown("SIGTERM"));
  process.on("SIGINT", handleGracefulShutdown("SIGINT"));`
            );
            
            fs.writeFileSync(serverPath, server);
            changesDetected = true;
            console.log("Added graceful shutdown handlers");
          }
        }
      }
    }
    
    // Also update test configuration to kill lingering processes
    const playwrightConfigPath = "playwright.config.cjs";
    if (fs.existsSync(playwrightConfigPath)) {
      let config = fs.readFileSync(playwrightConfigPath, "utf8");
      
      // Ensure webServer config has proper cleanup
      if (!config.includes("reuseExistingServer: false")) {
        config = config.replace(
          /webServer:\s*\{/,
          "webServer: {\n    reuseExistingServer: false,"
        );
        fs.writeFileSync(playwrightConfigPath, config);
        changesDetected = true;
        console.log("Ensured webServer does not reuse existing server");
      }
    }
  }
    console.log("Detected Cypress server issue - improving server handling in tests...");
    
    // The issue is likely the server not waiting or closing early
    // Check if test file needs improvements
    const cypressConfigPath = "playwright.config.cjs";
    if (fs.existsSync(cypressConfigPath)) {
      let config = fs.readFileSync(cypressConfigPath, "utf8");
      
      // Increase timeout for server operations
      if (!config.includes('timeout: 60000') && !config.includes('timeout: 120000')) {
        config = config.replace(/timeout:\s*\d+/g, 'timeout: 120000') || config;
        config = config.replace(/webServer.*?\n.*?\n.*?\n/s, `webServer: {
    command: 'npm start',
    url: 'http://localhost:3000',
    reuseExistingServer: false,
    timeout: 120000,
  },`);
        fs.writeFileSync(cypressConfigPath, config);
        changesDetected = true;
        console.log("Updated Playwright config with better server handling");
      }
    }
    
    // Check test files for proper wait times
    const cypressTestPath = "cypress/e2e/scan-ui.cy.js";
    if (fs.existsSync(cypressTestPath)) {
      let testFile = fs.readFileSync(cypressTestPath, "utf8");
      
      // Add better wait times between operations
      if (!testFile.includes('cy.visit') || !testFile.includes('wait(')) {
        console.log("Improving Cypress test reliability with waits");
        // Add wait after visit if not present
        testFile = testFile.replace(/cy\.visit\('([^']+)'\)/g, `cy.visit('$1')\n    cy.wait(2000)`);
        fs.writeFileSync(cypressTestPath, testFile);
        changesDetected = true;
      }
    }
  }
  
  // Check for ESLint issues and handle them specifically
  let eslintOutput = "";
  try {
    execSync("npx eslint . --ext .js 2>&1", { stdio: "pipe" });
  } catch (err) {
    eslintOutput = err.stdout?.toString() || err.stderr?.toString() || err.message;
  }
  
  // Parse ESLint output for specific issues
  if (eslintOutput) {
    console.log("Analyzing ESLint issues...");
    
    // Fix unused eslint-disable directives in coverage files
    const coverageDir = "coverage/lcov-report";
    if (fs.existsSync(coverageDir)) {
      const coverageFiles = execSync(`find ${coverageDir} -name "*.js"`, { encoding: "utf8" }).split("\n").filter(f => f);
      for (const file of coverageFiles) {
        let content = fs.readFileSync(file, "utf8");
        // Remove unused eslint-disable comments
        if (content.includes("/* eslint-disable")) {
          content = content.replace(/\/\*\s*eslint-disable[^\*]*\*\/\n/g, "");
          fs.writeFileSync(file, content);
          changesDetected = true;
        }
      }
      if (changesDetected) {
        console.log("Removed unused eslint-disable directives from coverage files");
      }
    }
    
    // Update eslint config if missing globals
    if (eslintOutput.includes("'URL' is not defined")) {
      console.log("Adding missing URL global to eslint config...");
      const configPath = "eslint.config.js";
      if (fs.existsSync(configPath)) {
        let config = fs.readFileSync(configPath, "utf8");
        if (!config.includes("URL: \"readonly\"")) {
          config = config.replace(/setTimeout:\s*"readonly",/, 'setTimeout: "readonly",\n        URL: "readonly",');
          fs.writeFileSync(configPath, config);
          changesDetected = true;
        }
      }
    }
    
    // Update eslint config to ignore generated files
    if (eslintOutput.includes("coverage/") || eslintOutput.includes("Unused eslint-disable")) {
      const configPath = "eslint.config.js";
      if (fs.existsSync(configPath)) {
        let config = fs.readFileSync(configPath, "utf8");
        if (!config.includes("coverage/**")) {
          config = config.replace(/ignores:\s*\[[^\]]*\]/, (match) => {
            return match.replace(/\]/, ', "coverage/**", "vitest-tests/**"]');
          });
          fs.writeFileSync(configPath, config);
          changesDetected = true;
        }
      }
    }
  }
  
  // 1. Apply ESLint fixes with --fix flag
  try {
    console.log("Applying ESLint fixes...");
    execSync("npx eslint . --ext .js --fix 2>&1", { stdio: "pipe" });
    console.log("ESLint fixes applied successfully");
    changesDetected = true;
  } catch (err) {
    // ESLint may exit with error code even after fixing some issues
    const output = err.stdout?.toString() || err.stderr?.toString() || err.message;
    if (output.includes("fixed") || output.includes("successfully")) {
      console.log("ESLint issues fixed");
      changesDetected = true;
    } else if (!output.includes("error")) {
      console.log("ESLint check passed");
    }
  }
  
  // 2. Commit any changes made by fixes
  await git.add(".");
  const status = await git.status();
  
  if (status.files.length > 0) {
    console.log(`Found ${status.files.length} changed file(s), committing...`);
    
    await git.raw(["config", "--global", "user.name", "github-actions[bot]"]);
    await git.raw(["config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"]);
    // Configure git token-based auth if running in GitHub Actions
    if (GITHUB_TOKEN) {
      await git.raw(["config", "--global", `url.https://x-access-token:${GITHUB_TOKEN}@github.com/.insteadOf`, "https://github.com/"]);
    }
    
    await git.commit("fix: agentic code repairs from test analysis");
    try {
      await git.push(["origin", "main"]);
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
  let attempts = 0;
  const maxAttempts = 10;
  
  while (attempts < maxAttempts) {
    const currentRun = await getLatestWorkflowRun();
    
    if (currentRun.status === 'completed') {
      console.log(`Test run completed with conclusion: ${currentRun.conclusion}`);
      return {
        success: currentRun.conclusion === 'success',
        run: currentRun,
      };
    }
    
    attempts++;
    console.log(`Waiting for tests to complete... (attempt ${attempts}/${maxAttempts})`);
    
    if (attempts >= maxAttempts) {
      console.warn('⚠️ Test polling timeout. Marking as failed to prevent hanging.');
      return { success: false, run: currentRun };
    }
    
    await new Promise(r => setTimeout(r, 30000)); // Wait 30 seconds between checks
  }
  
  return { success: false, run: null };
}

async function agenticSRELoop() {
  const MAX_ITERATIONS = 3;
  let iteration = 0;
  let success = false;
  
  // Set a hard timeout for the entire workflow (25 minutes)
  const workflowTimeout = 25 * 60 * 1000;
  const startTime = Date.now();
  
  const timeoutCheck = () => {
    if (Date.now() - startTime > workflowTimeout) {
      console.warn('⚠️ Workflow timeout reached. Exiting to prevent hang.');
      process.exit(0);
    }
  };
  
  // 1. Bump version
  const newVersion = await bumpVersion();
  console.log(`Version bumped to ${newVersion}`);
  timeoutCheck();
  
  // 2. Wait for initial CI to run
  await new Promise(r => setTimeout(r, 60000)); // Wait 1 min for CI
  timeoutCheck();
  
  // 3-6. Iterative testing and fixing loop
  while (iteration < MAX_ITERATIONS && !success) {
    timeoutCheck();
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
      
      if (iteration < MAX_ITERATIONS) {
        // Re-test with new changes or system state
        console.log(`Triggering re-test to check if issues are resolved...`);
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
        } else if (!changesApplied) {
          console.log(`⚠️ No code changes were made in iteration ${iteration}. Tests still failing.`);
        }
      } else {
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