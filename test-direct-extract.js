const { chromium } = require("playwright");

async function test() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
  await page.fill("#urlInput", "http://localhost:3000");
  await page.click("#scanBtn");
  
  // Wait for the scan to complete
  await page.waitForSelector("#results", { timeout: 30000 });
  await page.waitForTimeout(2000);
  
  // Extract all values
  const allValues = await page.evaluate(() => {
    return {
      results: document.querySelector("#results")?.value || "",
      testcases: document.querySelector("#testcases")?.value || "",
      performance: document.querySelector("#performance")?.value || "",
      apis: document.querySelector("#apis")?.value || "",
      playwright: document.querySelector("#playwright")?.value || "",
      cypress: document.querySelector("#cypress")?.value || "",
      recommendations: document.querySelector("#recommendations")?.value || ""
    };
  });
  
  console.log("Results length:", allValues.results.length);
  console.log("Test cases length:", allValues.testcases.length);
  console.log("Performance length:", allValues.performance.length);
  console.log("APIs length:", allValues.apis.length);
  console.log("Playwright length:", allValues.playwright.length);
  console.log("Cypress length:", allValues.cypress.length);
  console.log("Recommendations length:", allValues.recommendations.length);
  console.log("\n=== RECOMMENDATIONS ===");
  console.log(allValues.recommendations.substring(0, 200));
  
  await browser.close();
}

test().catch(console.error);
