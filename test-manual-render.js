const { chromium } = require("playwright");

async function test() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
  
  // Manually call renderResults with test data
  await page.evaluate(() => {
    const testData = {
      url: "http://localhost:3000",
      results: [{type: "test", message: "test message", recommendation: "test rec"}],
      totalFound: 1,
      testCases: ["Test 1"],
      performanceResults: {loadTimeMs: 100},
      apis: ["api1"],
      recommendations: ["Recommendation 1", "Recommendation 2", "Recommendation 3"]
    };
    
    // Call renderResults
    window.renderResults(testData);
  });
  
  // Extract values
  const values = await page.evaluate(() => {
    return {
      results: document.querySelector("#results")?.value?.substring(0, 100),
      recommendations: document.querySelector("#recommendations")?.value
    };
  });
  
  console.log("Results (first 100 chars):", values.results);
  console.log("Recommendations length:", values.recommendations?.length || 0);
  console.log("Recommendations (first 200):", values.recommendations?.substring(0, 200) || "EMPTY");
  
  await browser.close();
}

test().catch(console.error);
