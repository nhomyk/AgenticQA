/* global document, fetch, window, navigator, Blob */
// Make functions globally available for onclick handlers
window.downloadScript = downloadScript;
window.downloadFromElement = downloadFromElement;
window.copyToClipboard = copyToClipboard;
window.switchTab = switchTab;
window.switchTestTab = switchTestTab;

// Get scanner elements (may not exist on dashboard page)
const resultsBox = document.getElementById("results");
const testcasesBox = document.getElementById("testcases");
const performanceBox = document.getElementById("performance");
const apisBox = document.getElementById("apis");
const playwrightBox = document.getElementById("playwright-content");
const cypressBox = document.getElementById("cypress-content");
const vitestBox = document.getElementById("vitest-content");
const recommendationsBox = document.getElementById("recommendations");
const technologiesBox = document.getElementById("technologies");


function renderResults(resp) {
  // Safety check: only render if scanner elements exist on the page
  if (!technologiesBox || !resultsBox ) {
    console.warn("Scanner elements not found on this page, skipping renderResults");
    return;
  }

  // Always show the header for technologies, even on error
  const headerT = "Technologies Detected\n\n";
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
  
  // Reset tab state to Playwright (first tab) for new results (only if tabs exist)
  const tabPanes = document.querySelectorAll(".tab-pane");
  if (tabPanes.length > 0) {
    tabPanes.forEach(pane => {
      pane.classList.remove("active");
    });
  }
  
  const tabButtons = document.querySelectorAll(".tab-button");
  if (tabButtons.length > 0) {
    tabButtons.forEach(btn => {
      btn.classList.remove("active");
    });
  }
  
  // Try to activate Playwright tab if it exists
  const playwrightPane = document.getElementById("playwright");
  if (playwrightPane) {
    playwrightPane.classList.add("active");
  }
  
  const playwrightBtn = document.querySelector("[data-tab=\"playwright\"]");
  if (playwrightBtn) {
    playwrightBtn.classList.add("active");
  }
  
  // Log for debugging
  console.log("renderResults called with:", { hasRecs: !!resp.recommendations, recsCount: resp.recommendations?.length });
  
  // Ensure results is an array
  const results = Array.isArray(resp.results) ? resp.results : [];
  const header = `Scan: ${resp.url}\nFound: ${resp.totalFound || results.length} (showing ${results.length})\n---\n`;
  const lines = results.map((r, i) => `${i+1}. [${r.type}] ${r.message}\n   Fix: ${r.recommendation}`);
  resultsBox.value = results.length > 0 ? header + lines.join("\n\n") : "No issues detected during scan.";

  // render test cases if present
  if (testcasesBox && resp.testCases && Array.isArray(resp.testCases)) {
    const headerTC = "Reccomended test cases for this page\n\n";
    const tcLines = resp.testCases.map((t, i) => `${i+1}. ${t}`);
    testcasesBox.value = headerTC + tcLines.join("\n");
  } else if (testcasesBox) {
    testcasesBox.value = "";
  }

  // render performance results if present
  if (performanceBox && resp.performanceResults) {
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
  } else if (performanceBox) {
    performanceBox.value = "";
  }

  // render APIs used if present
  if (apisBox && resp.apis && Array.isArray(resp.apis) && resp.apis.length > 0) {
    const headerA = "APIs used on this page (first 10 calls)\n\n";
    const apiLines = resp.apis.map((a, i) => `${i+1}. ${a}`);
    apisBox.value = headerA + apiLines.join("\n");
  } else if (apisBox) {
    apisBox.value = "No API calls detected during scan.";
  }

  // Render first 5 test cases with Playwright, Cypress, and Vitest examples
  if (resp.testCases && Array.isArray(resp.testCases)) {
    const numCases = Math.min(5, resp.testCases.length);
    const testCasesList = resp.testCases.slice(0, numCases);
    
    // Generate Playwright scripts
    if (playwrightBox) {
      const headerPW = "Playwright Test Cases (First 5)\n\n";
      const pwScripts = testCasesList.map((testCase, index) => 
        generatePlaywrightExample(testCase, resp.url, index + 1)
      );
      playwrightBox.value = headerPW + pwScripts.join("\n\n" + "=".repeat(60) + "\n\n");
    }
    
    // Generate Cypress scripts
    if (cypressBox) {
      const headerCY = "Cypress Test Cases (First 5)\n\n";
      const cyScripts = testCasesList.map((testCase, index) => 
        generateCypressExample(testCase, resp.url, index + 1)
      );
      cypressBox.value = headerCY + cyScripts.join("\n\n" + "=".repeat(60) + "\n\n");
    }
    
    // Generate Vitest scripts
    if (vitestBox) {
      const headerVT = "Vitest Test Cases (First 5)\n\n";
      const vtScripts = testCasesList.map((testCase, index) => 
        generateVitestExample(testCase, resp.url, index + 1)
      );
      vitestBox.value = headerVT + vtScripts.join("\n\n" + "=".repeat(60) + "\n\n");
    }
  } else if (playwrightBox && cypressBox && vitestBox) {
    playwrightBox.value = "";
    cypressBox.value = "";
    vitestBox.value = "";
  }

  // render recommendations if present
  if (recommendationsBox && resp.recommendations && Array.isArray(resp.recommendations)) {
    const headerR = "AgenticQA Engineer's Recommendations\n\n";
    const recLines = resp.recommendations.map((r, i) => `${i+1}. ${r}`);
    recommendationsBox.value = headerR + recLines.join("\n\n");
  } else if (recommendationsBox) {
    recommendationsBox.value = "";
  }


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

function downloadFromElement(elementId, filename) {
  const element = document.getElementById(elementId);
  if (!element) {
    alert(`Element with id "${elementId}" not found`);
    return;
  }
  
  const content = element.value || element.textContent || "";
  if (!content) {
    alert("No content to download");
    return;
  }
  
  downloadScript(filename, content);
}

function copyToClipboard(textOrElementId) {
  let textToCopy = textOrElementId;
  
  // If it's an element ID (string), get the text from that element
  if (typeof textOrElementId === "string" && textOrElementId.length > 0) {
    const element = document.getElementById(textOrElementId);
    if (element) {
      // For textareas and inputs, use .value; for other elements, use .textContent
      textToCopy = element.value || element.textContent || textOrElementId;
    }
  }
  
  navigator.clipboard.writeText(textToCopy).then(() => {
    alert("Script copied to clipboard!");
  }).catch(err => {
    console.error("Failed to copy:", err);
  });
}

function generatePlaywrightExample(testCase, url, caseNum) {
  return `// Playwright Test ${caseNum}: ${testCase}\nconst { test, expect } = require('@playwright/test');\n\ntest('Test ${caseNum}: ${testCase}', async ({ page }) => {\n  await page.goto('${url}');\n  // TODO: Implement: ${testCase}\n  expect(true).toBe(true);\n});`;
  }

  function generateCypressExample(testCase, url, caseNum) {
  return `// Cypress Test Case ${caseNum}: ${testCase}\ndescribe('Test case ${caseNum}', () => {\n  it('should ${testCase.toLowerCase()}', () => {\n    cy.visit('${url}');\n    // TODO: Implement: ${testCase}\n    expect(true).to.be.true;\n  });\n});`;
}

function generateVitestExample(testCase, url, caseNum) {
  return `// Vitest Test Case ${caseNum}: ${testCase}\nimport { describe, it, expect } from 'vitest';\nimport { render, screen } from '@testing-library/vue';\n\ndescribe('Test case ${caseNum}', () => {\n  it('should ${testCase.toLowerCase()}', async () => {\n    // Navigate to ${url}\n    // TODO: Implement: ${testCase}\n    expect(true).toBe(true);\n  });\n});`;
}

// Tab switching functionality
function switchTab(tabName, buttonElement) {
  // Hide all content sections
  document.querySelectorAll(".content").forEach(section => {
    section.classList.remove("active");
  });
  
  // Remove active class from all tab buttons
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.classList.remove("active");
  });
  
  // Show selected tab content
  const tabContent = document.getElementById(tabName);
  if (tabContent) {
    tabContent.classList.add("active");
  }
  
  // Mark the clicked button as active
  if (buttonElement) {
    buttonElement.classList.add("active");
  }
}

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
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initTabSwitching);
} else {
  initTabSwitching();
}

// Function to attach scanner event listener when elements are ready
function attachScannerListener() {
  const btn = document.getElementById("scanBtn");
  const input = document.getElementById("urlInput");
  const rbox = document.getElementById("results");
  
  // Only attach scanner event listeners if scanner elements exist on the page
  if (btn && input && rbox) {
    btn.addEventListener("click", async () => {
      const url = input.value.trim();
      if (!url) return alert("Please enter a URL to scan");
      rbox.value = "Scanning " + url + " ...";
      try {
        console.log("[UI] Fetch initiated for:", url);
        const resp = await fetch("/scan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) });
        console.log("[UI] Fetch response status:", resp.status);
        const data = await resp.json();
        console.log("[UI] Fetch complete. Data:", data);
        renderResults(data);
      } catch (e) {
        console.error("[UI] Error during fetch:", e);
        rbox.value = "Error scanning: " + e;
      }
    });
    console.log("[Scanner] Event listener attached successfully");
  } else {
    console.log("[Scanner] Scanner elements not ready yet. scanBtn:", !!btn, "urlInput:", !!input, "results:", !!rbox);
  }
}

// Try to attach immediately if elements are ready
attachScannerListener();

// Also try when DOM is fully loaded
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", attachScannerListener);
} else {
  // DOM is already loaded
  setTimeout(attachScannerListener, 100);
}
