# Page snapshot

```yaml
- generic [ref=e1]:
  - heading "Agentic QA Engineer" [level=1] [ref=e2]
  - paragraph [ref=e3]: Enter a URL and submit to scan for console errors and DOM issues (results limited to 25).
  - generic [ref=e4]:
    - textbox "https://example.com" [ref=e5]
    - button "Scan" [active] [ref=e6]
  - heading "Scan Results" [level=3] [ref=e7]
  - textbox "Results will appear here (max 25 items)" [ref=e8]: "Scan: https://example.com Found: 1 (showing 1) --- 1. [ConsoleError] Failed to load resource: the server responded with a status of 404 () Fix: Check the stack trace and source; fix the script error or wrap calls in try/catch."
  - heading "Reccomended test cases for this page" [level=3] [ref=e9]
  - textbox "Recommended test cases will appear here (10 positive, 10 negative)" [ref=e10]: "Reccomended test cases for this page 1. Positive: Verify main headings render properly 2. Positive: All main links navigate to expected destinations 3. Negative: Broken links return 4xx/5xx and are reported 4. Negative: Page handles slow network (resources time out) 5. Negative: Layout does not break under long text or large images 6. Negative: Accessibility: focus order works for keyboard navigation 7. Negative: Heading structure regressions cause screen-reader confusion"
  - heading "Performance Results" [level=3] [ref=e11]
  - textbox "JMeter-like performance results will appear here" [ref=e12]: "Performance Results (simulated JMeter summary) Total Requests: 2 Failed Requests: 0 Resource Count: 1 Avg Response Time (ms): 59 Page Load Time (ms): 65 Throughput (req/sec): 30.77 Top Resources: 1. https://example.com/favicon.ico — 59ms (other)"
  - heading "APIs Used (first 10 calls)" [level=3] [ref=e13]
  - textbox "APIs used on the page will appear here (max 10)" [ref=e14]
  - heading "Playwright Example (first test case)" [level=3] [ref=e15]
  - textbox "Playwright example for the first test case will appear here" [ref=e16]: "// Playwright example for: Positive: Verify main headings render properly const { test, expect } = require('@playwright/test'); test('First test case', async ({ page }) => { await page.goto('https://example.com'); // TODO: Implement: Positive: Verify main headings render properly });"
  - heading "Cypress Example (first test case)" [level=3] [ref=e17]
  - textbox "Cypress example for the first test case will appear here" [ref=e18]: "// Cypress example for: Positive: Verify main headings render properly describe('First test case', () => { it('should run the test', () => { cy.visit('https://example.com'); // TODO: Implement: Positive: Verify main headings render properly }); });"
```