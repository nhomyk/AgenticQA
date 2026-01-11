const scanBtn = document.getElementById('scanBtn');
const urlInput = document.getElementById('urlInput');
const resultsBox = document.getElementById('results');
const testcasesBox = document.getElementById('testcases');
const performanceBox = document.getElementById('performance');

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
