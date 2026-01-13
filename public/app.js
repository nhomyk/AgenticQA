/* global document, fetch, window, navigator, Blob */
// Make functions globally available for onclick handlers
window.downloadScript = downloadScript;
window.copyToClipboard = copyToClipboard;

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
const technologiesBox = document.getElementById("technologies");


function renderResults(resp) {
  // Always show the header for technologies, even on error
  const headerT = "Tech Detected\n\n";
  let techNames = [];
  if (resp && Array.isArray(resp.technologies)) {
    techNames = resp.technologies.slice();
  }
  // Extract technology names from technologyUrls
  if (resp && Array.isArray(resp.technologyUrls)) {
    resp.technologyUrls.forEach(url => {
      // Heuristic: extract framework/library name from URL
      let match = url.match(/([\w-]+)(?:[./@-])/i);
      if (match && match[1]) {
        let name = match[1].replace(/_/g, " ");
        // Filter out generic words
        if (!["cdn", "js", "css", "lib", "dist", "static", "assets", "min", "main", "bundle", "v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10"].includes(name.toLowerCase())) {
          techNames.push(name.charAt(0).toUpperCase() + name.slice(1));
        }
      }
    });
  }
  // Deduplicate and sort
  techNames = [...new Set(techNames)].sort();
  technologiesBox.value = headerT + (techNames.length ? techNames.join(", ") : "None detected");
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
  document.querySelector("[data-tab=\"playwright\"]").classList.add("active");
  
  // Log for debugging
  console.log("renderResults called with:", { hasRecs: !!resp.recommendations, recsCount: resp.recommendations?.length });
  
  // Ensure results is an array
  const results = Array.isArray(resp.results) ? resp.results : [];
  const header = `Scan: ${resp.url}\nFound: ${resp.totalFound || results.length} (showing ${results.length})\n---\n`;
  const lines = results.map((r, i) => `${i+1}. [${r.type}] ${r.message}\n   Fix: ${r.recommendation}`);
  resultsBox.value = results.length > 0 ? header + lines.join("\n\n") : "No issues detected during scan.";

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
    apisBox.value = "No API calls detected during scan.";
  }

  // Render first 5 test cases with Playwright, Cypress, and Vitest examples
  if (resp.testCases && Array.isArray(resp.testCases)) {
    const numCases = Math.min(5, resp.testCases.length);
    renderTestCaseScripts(resp.testCases.slice(0, numCases), resp.url);
  } else {
    playwrightBox.innerHTML = "";
    cypressBox.innerHTML = "";
    vitestBox.innerHTML = "";
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

function renderTestCaseScripts(testCases, url) {
  const frameworks = [
    { id: "playwright", name: "Playwright", generator: generatePlaywrightExample },
    { id: "cypress", name: "Cypress", generator: generateCypressExample },
    { id: "vitest", name: "Vitest", generator: generateVitestExample }
  ];

  frameworks.forEach(framework => {
    const container = document.getElementById(framework.id);
    container.innerHTML = "";
    
    testCases.forEach((testCase, index) => {
      const script = framework.generator(testCase, url, index + 1);
      const scriptDiv = document.createElement("div");
      scriptDiv.className = "test-case-script";
      
      const h4 = document.createElement("h4");
      h4.textContent = `Test Case ${index + 1}: ${testCase.substring(0, 50)}${testCase.length > 50 ? "..." : ""}`;
      scriptDiv.appendChild(h4);
      
      const textarea = document.createElement("textarea");
      textarea.readOnly = true;
      textarea.value = script;
      scriptDiv.appendChild(textarea);
      
      const buttonDiv = document.createElement("div");
      buttonDiv.className = "test-case-buttons";
      
      const downloadBtn = document.createElement("button");
      downloadBtn.textContent = "Download";
      downloadBtn.addEventListener("click", () => {
        downloadScript(`${framework.name}-test-${index + 1}.js`, textarea.value);
      });
      buttonDiv.appendChild(downloadBtn);
      
      const copyBtn = document.createElement("button");
      copyBtn.textContent = "Copy";
      copyBtn.addEventListener("click", () => {
        copyToClipboard(textarea.value);
      });
      buttonDiv.appendChild(copyBtn);
      
      scriptDiv.appendChild(buttonDiv);
      container.appendChild(scriptDiv);
    });
  });
}

function downloadScript(filename, content) {
  const blob = new Blob([content], { type: "text/plain" });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    alert("Script copied to clipboard!");
  }).catch(err => {
    console.error("Failed to copy:", err);
  });
}

function generatePlaywrightExample(testCase, url, caseNum) {
  return `// Playwright Test Case ${caseNum}: ${testCase}\nconst { test, expect } = require('@playwright/test');\n\ntest('Test case ${caseNum}: ${testCase}', async ({ page }) => {\n  await page.goto('${url}');\n  // TODO: Implement: ${testCase}\n  expect(true).toBe(true);\n});`;
}

function generateCypressExample(testCase, url, caseNum) {
  return `// Cypress Test Case ${caseNum}: ${testCase}\ndescribe('Test case ${caseNum}', () => {\n  it('should ${testCase.toLowerCase()}', () => {\n    cy.visit('${url}');\n    // TODO: Implement: ${testCase}\n    expect(true).to.be.true;\n  });\n});`;
}

function generateVitestExample(testCase, url, caseNum) {
  return `// Vitest Test Case ${caseNum}: ${testCase}\nimport { describe, it, expect } from 'vitest';\nimport { render, screen } from '@testing-library/vue';\n\ndescribe('Test case ${caseNum}', () => {\n  it('should ${testCase.toLowerCase()}', async () => {\n    // Navigate to ${url}\n    // TODO: Implement: ${testCase}\n    expect(true).toBe(true);\n  });\n});`;
}

// Tab switching functionality
function initTabSwitching() {
  const buttons = document.querySelectorAll(".tab-button");
  if (buttons.length === 0) {
    console.warn("No tab-button elements found, tab switching not available");
    return;
  }
  
  buttons.forEach(button => {
    button.addEventListener("click", () => {
      const tabName = button.getAttribute("data-tab");
      if (!tabName) {
        console.warn("Tab button missing data-tab attribute");
        return;
      }
      
      // Hide all tab panes
      document.querySelectorAll(".tab-pane").forEach(pane => {
        pane.classList.remove("active");
      });
      
      // Remove active class from all buttons
      document.querySelectorAll(".tab-button").forEach(btn => {
        btn.classList.remove("active");
      });
      
      // Show selected tab pane and mark button as active
      const tabPane = document.getElementById(tabName);
      if (tabPane) {
        tabPane.classList.add("active");
      } else {
        console.warn(`Tab pane with id="${tabName}" not found`);
      }
      button.classList.add("active");
    });
  });
}

// Initialize tab switching when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initTabSwitching);
} else {
  initTabSwitching();
}

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
