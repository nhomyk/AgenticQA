#!/usr/bin/env node

const { QAAgent } = require("./agent.js");

/**
 * Main entry point for the QA Agent
 * Starts the server and runs the agent
 */
async function main() {
  const agent = new QAAgent();

  // Get URLs from command line
  // If multiple args provided, scan all; otherwise use first arg or defaults
  const args = process.argv.slice(2);
  
  let urlsToScan;
  if (args.length > 0) {
    // Single URL passed (common case)
    urlsToScan = args;
  } else {
    // No URLs passed - use defaults for CI
    urlsToScan = ["https://www.yahoo.com", "https://www.cbs.com", "https://www.github.com"];
  }

  try {
    // If single URL, scan just that one; if multiple URLs, scan all
    if (urlsToScan.length === 1) {
      const result = await agent.run(urlsToScan[0]);
    } else {
      const result = await agent.run(null); // null triggers multi-URL scanning
    }
    process.exit(0);
  } catch (error) {
    console.error("Agent execution failed:", error);
    process.exit(1);
  }
}

main();
