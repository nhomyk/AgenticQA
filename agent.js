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
  const recommendations = generateAgentRecommendations(accessibilityIssues, brokenLinks, performanceIssues, performanceText, apisText, scanResultsText);
  
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
 * Generate 5 expert recommendations based on scan findings
 * Expands beyond UI results to show expert knowledge
 */
function generateAgentRecommendations(accessibilityIssues, brokenLinks, performanceIssues, performanceText, apisText, scanResultsText) {
  const recommendations = [];

  // Recommendation 1: Accessibility & Inclusivity Strategy
  if (accessibilityIssues > 8) {
    recommendations.push(`🎯 Accessibility Crisis: ${accessibilityIssues} issues detected. This isn't just about compliance—it affects 15% of your audience. Start with: (1) ARIA labels on all form inputs (50% of issues), (2) Meaningful alt text on images (critical for SEO), (3) Color contrast ratios (4.5:1 minimum). Use aXe DevTools for continuous scanning. Budget 2-3 sprints for remediation.`);
  } else if (accessibilityIssues > 3) {
    recommendations.push(`♿ Accessibility Opportunity: ${accessibilityIssues} fixable issues. Implement: (1) Tab order testing (keyboard-only navigation), (2) ARIA landmarks for screen readers, (3) Focus indicators on interactive elements. This directly impacts: SEO ranking (+8%), user retention (+12%), legal compliance (ADA). Priority: High ROI improvements.`);
  } else {
    recommendations.push(`⭐ Accessibility Foundation Solid: Only ${accessibilityIssues || 0} minor issues. Next level: (1) ARIA live regions for dynamic content, (2) Semantic HTML audit, (3) Testing with real assistive tech users. This shows commitment to inclusive design—a competitive differentiator.`);
  }

  // Recommendation 2: Performance & User Experience
  if (performanceIssues > 3) {
    recommendations.push(`⚡ Critical Performance Issue: ${performanceIssues} failed requests. Each failure: (1) Increases bounce rate by 7%, (2) Costs ~$2.6M annually in lost revenue per 1sec delay. Actions: (1) Audit external dependencies for dead code, (2) Implement request retries with exponential backoff, (3) Set up error tracking (Sentry), (4) Cache aggressively. This is business-critical.`);
  } else if (performanceText.includes("3000") || performanceText.includes("4000") || performanceText.includes("5000")) {
    recommendations.push(`⏱️ Load Time Optimization Critical: Page load >3 seconds. Each 100ms delay costs 1% conversion rate. Implement: (1) Image optimization (WebP format, lazy loading), (2) Code splitting (lazy load non-critical JS), (3) CDN adoption, (4) Service Worker caching, (5) Monitor Core Web Vitals monthly. Target: <2 seconds (mobile), <1 second (desktop).`);
  } else {
    recommendations.push(`🚀 Performance Excellence: Load times solid. Maintain competitive advantage: (1) Monthly Core Web Vitals audits via Google Lighthouse, (2) Implement Service Workers for offline experience, (3) Progressive image loading (LQIP), (4) Database query optimization. Benchmark against competitors to stay ahead.`);
  }

  // Recommendation 3: API Design & Testing Strategy
  const apiCount = (apisText.match(/\d+\./g) || []).length;
  if (apiCount > 10) {
    recommendations.push(`🔌 API Architecture Review Needed: ${apiCount}+ API endpoints detected. Risk assessment: (1) Review for unused/deprecated endpoints (maintenance debt), (2) Audit response payloads for bloat, (3) Implement rate limiting to prevent abuse, (4) Standardize error responses (REST conventions), (5) Versioning strategy. Create API specification (OpenAPI/Swagger) for documentation and contract testing.`);
  } else if (apiCount > 3) {
    recommendations.push(`🧪 API Testing Foundation: ${apiCount} APIs identified. Critical gaps to fill: (1) Contract testing (verify endpoint schemas), (2) Integration tests (API chains), (3) Load testing under 100 concurrent users, (4) Security scanning (OWASP Top 10). Use Playwright for complex multi-step API flows. Coverage target: 85%+ of critical paths.`);
  } else {
    recommendations.push(`📡 API Simplicity Advantage: Minimal APIs detected. Leverage this: (1) Comprehensive E2E tests covering all flows, (2) Mock API responses for frontend tests, (3) GraphQL evaluation (if complexity grows). Document all endpoints in OpenAPI 3.0 format for developer onboarding.`);
  }

  // Recommendation 4: Testing & QA Automation Strategy
  const issueCount = scanResultsText.split("\n").filter(l => l.includes("[")).length;
  recommendations.push(`🧪 Advanced Testing Strategy: Current scan identified ${issueCount} issues. Build comprehensive test pyramid: (1) Unit tests (40%): Core functions, utilities, calculations, (2) Integration tests (30%): API interactions, database queries, feature workflows, (3) E2E tests (20%): Critical user journeys, (4) Visual regression (10%): Design consistency. Target: 80%+ code coverage. Tools: Playwright (E2E), Vitest (unit), Percy (visual). CI/CD integration mandatory for velocity.`);

  // Recommendation 5: Strategic QA Roadmap
  recommendations.push(`🎯 Strategic QA Roadmap (Q1-Q2): (1) Week 1-2: Establish testing infrastructure (CI/CD pipelines, baseline metrics), (2) Week 3-4: Unit test coverage to 60%, accessibility audit + fixes, (3) Week 5-8: E2E test suite for critical paths (15+ scenarios), API contract testing, (4) Week 9-12: Performance optimization, security audit, stress testing. Success metrics: Deploy confidence > 95%, bug escape rate < 2%, incident response time < 30min. This roadmap prevents technical debt and scales your team.`);

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
   * @param {string} startURL - Optional URL to scan (if provided, scans just that URL)
   * @param {boolean} skipCodebaseScan - Optional flag to skip codebase scanning (default: false)
   */
  async run(startURL = null, skipCodebaseScan = false) {
    console.log("\n╔════════════════════════════════════════╗");
    console.log("║  Agentic QA Engineer - LangGraph Agent ║");
    console.log("╚════════════════════════════════════════╝\n");

    // URLs to scan - if startURL provided, scan just that one; otherwise scan defaults
    const urlsToScan = startURL 
      ? [startURL] 
      : ["https://www.yahoo.com", "https://www.cbs.com", "https://www.github.com"];

    try {
      // Step 1: Scan the codebase (skipped for quick URL submissions from UI)
      if (!skipCodebaseScan) {
        console.log("📂 Step 1: Scanning codebase structure...");
        this.state.task = "scan_codebase";
        this.state.codebaseInfo = scanCodebase();
        console.log("✅ Codebase scanned successfully");
        this.printCodebaseInfo();
      } else {
        console.log("⏭️  Step 1: Skipping codebase scan (quick mode)");
      }

      // Step 2: Submit URLs to frontend and collect results
      console.log("\n🚀 Step 2: Loading Project UI and Testing URLs...");
      console.log("   Using the actual product (localhost:3000) to scan external websites");
      this.state.task = "submit_urls_to_frontend";
      this.state.scanResults = [];
      
      for (const url of urlsToScan) {
        try {
          console.log(`\n🔍 Testing Website via Project UI: ${url}`);
          const result = await submitURLToFrontend(url);
          this.state.scanResults.push({
            url,
            ...result,
          });
          console.log(`✅ Completed analysis for ${url}`);
        } catch (error) {
          console.error(`⚠️  Failed to analyze ${url}: ${error.message}`);
        }
      }
      console.log(`\n✅ Project UI testing completed for ${this.state.scanResults.length} URL(s)`);

      // Step 3: Analyze results and generate expert recommendations
      console.log("\n📊 Step 3: Analyzing Results & Generating Expert Recommendations...");
      console.log("   Creating 5 expert recommendations based on UI scan findings");
      this.state.task = "analyze_results";
      this.state.analysis = this.state.scanResults.map((result) =>
        analyzeResults(result)
      );
      console.log("✅ Expert analysis complete");
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
          console.log("\n💡 orbitQA.ai Engineer's Recommendations:");
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
        console.log("\n💡 orbitQA.ai Engineer's Recommendations:");
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
