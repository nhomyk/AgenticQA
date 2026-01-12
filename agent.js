const { readFileSync, readdirSync, statSync } = require("fs");
const { join } = require("path");
const { chromium } = require("playwright");

/**
 * Tool: Scan Codebase
 * Recursively scans the project directory and returns file structure and content
 */
function scanCodebase(directory = ".", depth = 0, maxDepth = 2) {
  const ignoreDirs = [
    "node_modules",
    ".git",
    "coverage",
    "test-results",
    ".next",
    "dist",
    "build",
  ];
  const ignoreFiles = [".env", ".env.local", ".DS_Store"];

  if (depth > maxDepth) return {};

  const files = {};
  const dir = join(directory);

  try {
    const entries = readdirSync(dir);

    entries.forEach((entry) => {
      if (
        ignoreDirs.includes(entry) ||
        ignoreFiles.includes(entry) ||
        entry.startsWith(".")
      ) {
        return;
      }

      const fullPath = join(dir, entry);
      const stat = statSync(fullPath);

      if (stat.isDirectory()) {
        files[entry] = scanCodebase(fullPath, depth + 1, maxDepth);
      } else {
        try {
          const content = readFileSync(fullPath, "utf-8");
          const lines = content.split("\n");
          files[entry] = {
            type: "file",
            size: content.length,
            lines: lines.length,
            preview: lines.slice(0, 20).join("\n"),
          };
        } catch (e) {
          files[entry] = { type: "file", error: "Unable to read" };
        }
      }
    });
  } catch (e) {
    return { error: "Unable to read directory" };
  }

  return files;
}

/**
 * Tool: Submit URL to Frontend
 * Uses Playwright to interact with the frontend UI and submit a URL for scanning
 */
async function submitURLToFrontend(url, baseURL = "http://localhost:3000") {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    console.log(`\n🌐 Navigating to ${baseURL}...`);
    await page.goto(baseURL, { waitUntil: "networkidle" });

    console.log(`📝 Filling URL input with: ${url}`);
    await page.fill("#urlInput", url);
    await page.waitForTimeout(500);

    console.log("🔍 Clicking scan button...");
    await page.click("#scanBtn");

    // Wait for results to appear
    console.log("⏳ Waiting for scan results...");
    await page.waitForSelector("#results", { timeout: 30000 });
    await page.waitForTimeout(2000);

    // Extract all results using page.evaluate to properly get dynamically set values
    const results = await page.evaluate(() => {
      return {
        scanResults: document.querySelector("#results")?.value || "",
        testCases: document.querySelector("#testcases")?.value || "",
        performanceResults: document.querySelector("#performance")?.value || "",
        apis: document.querySelector("#apis")?.value || "",
        playwrightExample: document.querySelector("#playwright")?.value || "",
        cypressExample: document.querySelector("#cypress")?.value || "",
        recommendations: document.querySelector("#recommendations")?.value || "",
      };
    });

    results.timestamp = new Date().toISOString();

    console.log("\n✅ Scan completed successfully!");
    console.log(`📊 Results obtained at: ${results.timestamp}`);

    return results;
  } catch (error) {
    console.error("❌ Error during frontend interaction:", error.message);
    throw error;
  } finally {
    await browser.close();
  }
}

/**
 * Tool: Analyze Results
 * Processes and summarizes the scan results
 */
function analyzeResults(results) {
  // Parse the raw results to generate recommendations
  const scanResultsText = results.scanResults || "";
  const performanceText = results.performanceResults || "";
  const apisText = results.apis || "";
  
  // Count issues by type
  const accessibilityIssues = (scanResultsText.match(/\[MissingAlt\]|\[EmptyAlt\]|\[MissingLabel\]|\[HeadingOrder\]/g) || []).length;
  const brokenLinks = (scanResultsText.match(/\[BadHref\]|\[BrokenImage\]/g) || []).length;
  const performanceIssues = (scanResultsText.match(/\[RequestFailed\]/g) || []).length;
  
  // Generate recommendations based on findings
  const recommendations = generateAgentRecommendations(accessibilityIssues, brokenLinks, performanceIssues, performanceText, apisText);
  
  return {
    summary: {
      scanTime: results.timestamp,
      resultsCount: scanResultsText.split("\n").length,
      testCasesCount: results.testCases ? results.testCases.split("\n").length : 0,
      apiDetected: apisText ? apisText.split("\n").filter((l) => l.trim()).length : 0,
      hasPerformanceData: !!performanceText && performanceText.length > 0,
      hasRecommendations: recommendations.length > 0,
    },
    sections: {
      scanResults: scanResultsText.substring(0, 500),
      testCasesPreview: results.testCases?.split("\n").slice(0, 3).join("\n"),
      apisDetected: apisText?.split("\n").slice(0, 5).join("\n"),
      playwrightGenerated: !!results.playwrightExample && results.playwrightExample.length > 0,
      cypressGenerated: !!results.cypressExample && results.cypressExample.length > 0,
      recommendations: recommendations,
    },
  };
}

/**
 * Generate recommendations based on scan findings
 */
function generateAgentRecommendations(accessibilityIssues, brokenLinks, performanceIssues, performanceText, apisText) {
  const recommendations = [];

  // Recommendation 1: Accessibility
  if (accessibilityIssues > 5) {
    recommendations.push(`🎯 Critical: Fix ${accessibilityIssues} accessibility issues including missing alt text and labels. This blocks ~15% of users with disabilities and hurts SEO. Start with ARIA labels on form inputs and descriptive alt text on all images.`);
  } else if (accessibilityIssues > 0) {
    recommendations.push(`✅ Good: Address ${accessibilityIssues} remaining accessibility issues to reach WCAG 2.1 AA compliance. Add ARIA landmarks to improve screen reader navigation and ensure keyboard users can access all interactive elements.`);
  } else {
    recommendations.push(`⭐ Excellent: Strong accessibility foundation detected. Continue by implementing ARIA live regions for dynamic content and testing with real assistive technology users to ensure true inclusive design.`);
  }

  // Recommendation 2: Performance & Reliability
  if (performanceIssues > 3 || brokenLinks > 2) {
    recommendations.push(`⚡ Performance: Reduce ${performanceIssues + brokenLinks} failing requests by auditing external dependencies, verifying CORS headers, and implementing retry logic. Each failed request reduces trust and increases bounce rate by ~7%.`);
  } else if (performanceText.includes("5000") || performanceText.includes("4000") || performanceText.includes("3000")) {
    recommendations.push(`⚡ Performance: Page load time is high. Implement lazy loading for images, enable gzip compression, minify CSS/JS, and consider a CDN. Target <2 second load time to improve conversion rates and SEO ranking.`);
  } else {
    recommendations.push(`⚡ Performance: Load times are solid. Monitor Core Web Vitals monthly using Google Lighthouse. Implement Service Workers for offline capability and progressive image loading to maintain competitive advantage.`);
  }

  // Recommendation 3: Testing & Coverage
  const apiCount = (apisText.match(/\d+\./g) || []).length;
  recommendations.push(`🧪 Testing: Create automated tests for ${apiCount || "key"} API endpoints and critical user flows. Implement Cypress for E2E testing and Playwright for API testing. Target 80%+ coverage to catch regressions and reduce production bugs by 60%.`);

  return recommendations;
}

/**
 * LangGraph Agent for Agentic QA Engineer
 * Main agent that orchestrates the scanning and testing workflow
 */
class QAAgent {
  constructor() {
    this.state = {
      task: null,
      codebaseInfo: null,
      scanResults: null,
      analysis: null,
    };
  }

  /**
   * Initialize and run the agent
   */
  async run(startURL = null) {
    console.log("\n╔════════════════════════════════════════╗");
    console.log("║  Agentic QA Engineer - LangGraph Agent ║");
    console.log("╚════════════════════════════════════════╝\n");

    // URLs to scan - if startURL provided, scan just that one; otherwise scan defaults
    const urlsToScan = startURL 
      ? [startURL] 
      : ["https://www.yahoo.com", "https://www.cbs.com", "https://www.github.com"];

    try {
      // Step 1: Scan the codebase
      console.log("📂 Step 1: Scanning codebase structure...");
      this.state.task = "scan_codebase";
      this.state.codebaseInfo = scanCodebase();
      console.log("✅ Codebase scanned successfully");
      this.printCodebaseInfo();

      // Step 2: Submit URLs to frontend and collect results
      console.log("\n🚀 Step 2: Submitting URLs to frontend for scanning...");
      this.state.task = "submit_urls_to_frontend";
      this.state.scanResults = [];
      
      for (const url of urlsToScan) {
        try {
          console.log(`\n🔍 Scanning URL: ${url}`);
          const result = await submitURLToFrontend(url);
          this.state.scanResults.push({
            url,
            ...result,
          });
          console.log(`✅ Completed scan for ${url}`);
        } catch (error) {
          console.error(`⚠️  Failed to scan ${url}: ${error.message}`);
        }
      }
      console.log(`\n✅ Frontend interaction completed for ${this.state.scanResults.length} URL(s)`);

      // Step 3: Analyze results
      console.log("\n📊 Step 3: Analyzing scan results...");
      this.state.task = "analyze_results";
      this.state.analysis = this.state.scanResults.map((result) =>
        analyzeResults(result)
      );
      console.log("✅ Results analyzed");
      this.printAnalysis();

      return this.state;
    } catch (error) {
      console.error("\n❌ Agent failed:", error.message);
      throw error;
    }
  }

  printCodebaseInfo() {
    console.log("\n📋 Codebase Structure:");
    console.log("─".repeat(50));

    const printTree = (obj, indent = "") => {
      Object.entries(obj).forEach(([key, value]) => {
        if (typeof value === "object" && value !== null) {
          if (value.type === "file") {
            console.log(
              `${indent}📄 ${key} (${value.lines} lines, ${value.size} bytes)`
            );
          } else {
            console.log(`${indent}📁 ${key}/`);
            printTree(value, indent + "  ");
          }
        }
      });
    };

    printTree(this.state.codebaseInfo);
  }

  printAnalysis() {
    console.log("\n" + "═".repeat(60));
    console.log("📊 SCAN RESULTS SUMMARY");
    console.log("═".repeat(60));

    if (Array.isArray(this.state.analysis)) {
      this.state.analysis.forEach((analysis, index) => {
        const url = this.state.scanResults[index]?.url || "Unknown";
        const { summary, sections } = analysis;

        console.log(`\n📍 URL ${index + 1}: ${url}`);
        console.log("─".repeat(60));
        console.log(`Scan Time: ${summary.scanTime}`);
        console.log(`Issues Found: ${summary.resultsCount}`);
        console.log(`Test Cases Generated: ${summary.testCasesCount}`);
        console.log(`APIs Detected: ${summary.apiDetected}`);
        console.log(`Performance Data: ${summary.hasPerformanceData ? "Yes" : "No"}`);
        console.log(`Has Recommendations: ${summary.hasRecommendations ? "Yes" : "No"}`);

        if (sections.recommendations && sections.recommendations.length > 0) {
          console.log("\n💡 AgenticQA Engineer's Recommendations:");
          sections.recommendations.forEach((rec, i) => {
            if (rec.trim()) {
              console.log(`\n  ${i + 1}. ${rec}`);
            }
          });
        }

        console.log("\n🧪 Code Generation Status:");
        console.log(`Playwright Example: ${sections.playwrightGenerated ? "✅ Generated" : "❌ Not generated"}`);
        console.log(`Cypress Example: ${sections.cypressGenerated ? "✅ Generated" : "❌ Not generated"}`);
      });
    } else {
      const { summary, sections } = this.state.analysis;

      console.log("\n📝 Scan Summary:");
      console.log("─".repeat(60));
      console.log(`Scan Time: ${summary.scanTime}`);
      console.log(`Issues Found: ${summary.resultsCount}`);
      console.log(`Test Cases Generated: ${summary.testCasesCount}`);
      console.log(`APIs Detected: ${summary.apiDetected}`);
      console.log(`Performance Data: ${summary.hasPerformanceData ? "Yes" : "No"}`);

      if (sections.recommendations && sections.recommendations.length > 0) {
        console.log("\n💡 AgenticQA Engineer's Recommendations:");
        sections.recommendations.forEach((rec, i) => {
          if (rec.trim()) {
            console.log(`\n  ${i + 1}. ${rec}`);
          }
        });
      }

      console.log("\n🧪 Code Generation Status:");
      console.log(`Playwright Example: ${sections.playwrightGenerated ? "✅ Generated" : "❌ Not generated"}`);
      console.log(`Cypress Example: ${sections.cypressGenerated ? "✅ Generated" : "❌ Not generated"}`);
    }

    console.log("\n" + "═".repeat(60));
  }
}

module.exports = { QAAgent, scanCodebase, submitURLToFrontend, analyzeResults };
