const scanBtn = document.getElementById("scanBtn");
const urlInput = document.getElementById("urlInput");
const resultsBox = document.getElementById("results");
const testcasesBox = document.getElementById("testcases");
const performanceBox = document.getElementById("performance");
const apisBox = document.getElementById("apis");
const playwrightBox = document.getElementById("playwright");
const cypressBox = document.getElementById("cypress");
const vitestBox = document.getElementById("vitest");
const recommendationsBox = document.getElementById("recommendations");


function renderResults(resp) {
  if (!resp) return;
  if (resp.error) {
    resultsBox.value = "Error: " + resp.error;
    return;
  }
  
  // Reset tab state to Playwright (first tab) for new results
  document.querySelectorAll(".tab-pane").forEach(pane => {
    pane.classList.remove("active");
  });
  document.querySelectorAll(".tab-button").forEach(btn => {
    btn.classList.remove("active");
  });
  document.getElementById("playwright").classList.add("active");
  document.querySelector('[data-tab="playwright"]').classList.add("active");
  
  // Log for debugging
  console.log("renderResults called with:", { hasRecs: !!resp.recommendations, recsCount: resp.recommendations?.length });
  
  // Ensure results is an array
  const results = Array.isArray(resp.results) ? resp.results : [];
  const header = `Scan: ${resp.url}\nFound: ${resp.totalFound || results.length} (showing ${results.length})\n---\n`;
  const lines = results.map((r, i) => `${i+1}. [${r.type}] ${r.message}\n   Fix: ${r.recommendation}`);
  resultsBox.value = header + lines.join("\n\n");

  // render test cases if present
  if (resp.testCases && Array.isArray(resp.testCases)) {
    const headerTC = "Reccomended test cases for this page\n\n";
    const tcLines = resp.testCases.map((t, i) => `${i+1}. ${t}`);
    testcasesBox.value = headerTC + tcLines.join("\n");
  } else {
    testcasesBox.value = "";
  }

  // render performance results if present
  if (resp.performanceResults) {
    const p = resp.performanceResults;
    const headerP = "Performance Results (simulated JMeter summary)\n\n";
    const lines = [];
    lines.push(`Total Requests: ${p.totalRequests}`);
    lines.push(`Failed Requests: ${p.failedRequests}`);
    lines.push(`Resource Count: ${p.resourceCount}`);
    lines.push(`Avg Response Time (ms): ${p.avgResponseTimeMs}`);
    lines.push(`Page Load Time (ms): ${p.loadTimeMs}`);
    lines.push(`Throughput (req/sec): ${p.throughputReqPerSec}`);
    lines.push("\nTop Resources:");
    if (Array.isArray(p.topResources)) {
      p.topResources.forEach((r, i) => lines.push(`${i+1}. ${r.name} — ${r.timeMs}ms (${r.type})`));
    }
    performanceBox.value = headerP + lines.join("\n");
  } else {
    performanceBox.value = "";
  }

  // render APIs used if present
  if (resp.apis && Array.isArray(resp.apis) && resp.apis.length > 0) {
    const headerA = "APIs used on this page (first 10 calls)\n\n";
    const apiLines = resp.apis.map((a, i) => `${i+1}. ${a}`);
    apisBox.value = headerA + apiLines.join("\n");
  } else {
    apisBox.value = "";
  }

  // Playwright, Cypress, and Vitest examples for first test case
  if (resp.testCases && Array.isArray(resp.testCases) && resp.testCases.length > 0) {
    const firstCase = resp.testCases[0] || "";
    playwrightBox.value = generatePlaywrightExample(firstCase, resp.url);
    cypressBox.value = generateCypressExample(firstCase, resp.url);
    vitestBox.value = generateVitestExample(firstCase, resp.url);
  } else {
    playwrightBox.value = "";
    cypressBox.value = "";
    vitestBox.value = "";
  }

  // render recommendations if present
  if (resp.recommendations && Array.isArray(resp.recommendations)) {
    const headerR = "AgenticQA Engineer's Recommendations\n\n";
    const recLines = resp.recommendations.map((r, i) => `${i+1}. ${r}`);
    recommendationsBox.value = headerR + recLines.join("\n\n");
  } else {
    recommendationsBox.value = "";
  }

}

function generatePlaywrightExample(testCase, url) {
  // Simple mapping for demo purposes
  return `// Playwright example for: ${testCase}\nconst { test, expect } = require('@playwright/test');\n\ntest('First test case', async ({ page }) => {\n  await page.goto('${url}');\n  // TODO: Implement: ${testCase}\n});`;
}

function generateCypressExample(testCase, url) {
  // Simple mapping for demo purposes
  return `// Cypress example for: ${testCase}\ndescribe('First test case', () => {\n  it('should run the test', () => {\n    cy.visit('${url}');\n    // TODO: Implement: ${testCase}\n  });\n});`;
}

function generateVitestExample(testCase, url) {
  // Simple mapping for demo purposes
  return `// Vitest example for: ${testCase}\nimport { describe, it, expect } from 'vitest';\nimport { render, screen } from '@testing-library/vue';\n\ndescribe('First test case', () => {\n  it('should ${testCase.toLowerCase()}', async () => {\n    // Navigate to ${url}\n    // TODO: Implement: ${testCase}\n    expect(true).toBe(true);\n  });\n});`;
}

// Tab switching functionality
document.querySelectorAll(".tab-button").forEach(button => {
  button.addEventListener("click", () => {
    const tabName = button.getAttribute("data-tab");
    
    // Hide all tab panes
    document.querySelectorAll(".tab-pane").forEach(pane => {
      pane.classList.remove("active");
    });
    
    // Remove active class from all buttons
    document.querySelectorAll(".tab-button").forEach(btn => {
      btn.classList.remove("active");
    });
    
    // Show selected tab pane and mark button as active
    document.getElementById(tabName).classList.add("active");
    button.classList.add("active");
  });
});

scanBtn.addEventListener("click", async () => {
  const url = urlInput.value.trim();
  if (!url) return alert("Please enter a URL to scan");
  resultsBox.value = "Scanning " + url + " ...";
  try {
    console.log("[UI] Fetch initiated for:", url);
    const resp = await fetch("/scan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) });
    console.log("[UI] Fetch response status:", resp.status);
    const data = await resp.json();
    console.log("[UI] Fetch complete. Data:", data);
    renderResults(data);
  } catch (e) {
    console.error("[UI] Error during fetch:", e);
    resultsBox.value = "Error scanning: " + e;
  }
});
