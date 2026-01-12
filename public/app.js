const scanBtn = document.getElementById('scanBtn');
const urlInput = document.getElementById('urlInput');
const resultsBox = document.getElementById('results');
const testcasesBox = document.getElementById('testcases');
const performanceBox = document.getElementById('performance');
const apisBox = document.getElementById('apis');
const playwrightBox = document.getElementById('playwright');
const cypressBox = document.getElementById('cypress');


function renderResults(resp) {
  if (!resp) return;
  if (resp.error) {
    resultsBox.value = 'Error: ' + resp.error;
    return;
  }
  const header = `Scan: ${resp.url}\nFound: ${resp.totalFound} (showing ${resp.results.length})\n---\n`;
  const lines = resp.results.map((r, i) => `${i+1}. [${r.type}] ${r.message}\n   Fix: ${r.recommendation}`);
  resultsBox.value = header + lines.join('\n\n');

  // render test cases if present
  if (resp.testCases && Array.isArray(resp.testCases)) {
    const headerTC = 'Reccomended test cases for this page\n\n';
    const tcLines = resp.testCases.map((t, i) => `${i+1}. ${t}`);
    testcasesBox.value = headerTC + tcLines.join('\n');
  } else {
    testcasesBox.value = '';
  }

  // render performance results if present
  if (resp.performanceResults) {
    const p = resp.performanceResults;
    const headerP = 'Performance Results (simulated JMeter summary)\n\n';
    const lines = [];
    lines.push(`Total Requests: ${p.totalRequests}`);
    lines.push(`Failed Requests: ${p.failedRequests}`);
    lines.push(`Resource Count: ${p.resourceCount}`);
    lines.push(`Avg Response Time (ms): ${p.avgResponseTimeMs}`);
    lines.push(`Page Load Time (ms): ${p.loadTimeMs}`);
    lines.push(`Throughput (req/sec): ${p.throughputReqPerSec}`);
    lines.push('\nTop Resources:');
    p.topResources.forEach((r, i) => lines.push(`${i+1}. ${r.name} — ${r.timeMs}ms (${r.type})`));
    performanceBox.value = headerP + lines.join('\n');
  } else {
    performanceBox.value = '';
  }

  // render APIs used if present
  if (resp.apis && Array.isArray(resp.apis) && resp.apis.length > 0) {
    const headerA = 'APIs used on this page (first 10 calls)\n\n';
    const apiLines = resp.apis.map((a, i) => `${i+1}. ${a}`);
    apisBox.value = headerA + apiLines.join('\n');
  } else {
    apisBox.value = '';
  }

  // Playwright and Cypress examples for first test case
  if (resp.testCases && resp.testCases.length > 0) {
    const firstCase = resp.testCases[0] || '';
    playwrightBox.value = generatePlaywrightExample(firstCase, resp.url);
    cypressBox.value = generateCypressExample(firstCase, resp.url);
  } else {
    playwrightBox.value = '';
    cypressBox.value = '';
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

scanBtn.addEventListener('click', async () => {
  const url = urlInput.value.trim();
  if (!url) return alert('Please enter a URL to scan');
  resultsBox.value = 'Scanning ' + url + ' ...';
  try {
    const resp = await fetch('/scan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) });
    const data = await resp.json();
    renderResults(data);
  } catch (e) {
    resultsBox.value = 'Error scanning: ' + e;
  }
});
