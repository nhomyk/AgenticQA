const { chromium } = require("playwright");

async function test() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
  await page.fill("#urlInput", "http://localhost:3000");
  await page.click("#scanBtn");
  await page.waitForSelector("#results", { timeout: 30000 });
  await page.waitForTimeout(2000);
  
  const recs = await page.inputValue("#recommendations");
  console.log("=== RECOMMENDATIONS ===");
  console.log(recs);
  console.log("=== END ===");
  console.log("Length:", recs?.length || 0);
  
  await browser.close();
}

test().catch(console.error);
