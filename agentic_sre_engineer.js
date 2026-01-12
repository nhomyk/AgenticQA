  // Debug: print remotes before push
  const remotes = await git.getRemotes(true);
  console.log('Git remotes before push:', remotes);
  // Debug: print remotes before push
  const remotes = await git.getRemotes(true);
  console.log('Git remotes before push:', remotes);
// Agentic SRE Engineer - LangGraph Agent
// Automates CI/CD monitoring, version bumping, and code fixes with email notifications

const { Octokit } = require("@octokit/rest");
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

const octokit = new Octokit({ auth: GITHUB_TOKEN });
const git = simpleGit();

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
  await git.push();
  return pkg.version;
}

async function getLatestWorkflowRun() {
  const { data } = await octokit.actions.listWorkflowRunsForRepo({
    owner: REPO_OWNER,
    repo: REPO_NAME,
    branch: BRANCH,
    per_page: 1,
  });
  return data.workflow_runs[0];
}

async function getWorkflowLogs(runId) {
  const { data } = await octokit.actions.downloadWorkflowRunLogs({
    owner: REPO_OWNER,
    repo: REPO_NAME,
    run_id: runId,
  });
  return data; // This is a URL to a zip file; for demo, just return the URL
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

async function autoFixAndCommit() {
  // Example: run eslint --fix and commit changes
  const { execSync } = require("child_process");
  execSync("npx eslint . --ext .js --fix");
  await git.add(".");
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
  await git.commit("chore: auto-fix lint errors");
  await git.push();
}

async function agenticSRELoop() {
  while (true) {
    // 1. Bump version
    const newVersion = await bumpVersion();
    // 2. Wait for CI to run
    await new Promise(r => setTimeout(r, 60000)); // Wait 1 min for CI
    // 3. Get latest workflow run
    const run = await getLatestWorkflowRun();
    // 4. If failed, get logs and email
    if (run.conclusion !== "success") {
      const logsUrl = await getWorkflowLogs(run.id);
      await sendEmail(
        `CI Failed for AgenticQA v${newVersion}`,
        `Workflow failed. Logs: ${logsUrl}`
      );
      // 5. Auto-fix and commit
      await autoFixAndCommit();
      continue; // Repeat loop
    } else {
      await sendEmail(
        `CI Passed for AgenticQA v${newVersion}`,
        `All tests passed! Version: ${newVersion}`
      );
      break;
    }
  }
}

if (require.main === module) {
  agenticSRELoop().catch(console.error);
}

module.exports = { agenticSRELoop };