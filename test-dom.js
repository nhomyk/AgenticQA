const { chromium } = require("playwright");

async function test() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
  await page.fill("#urlInput", "http://localhost:3000");
  await page.click("#scanBtn");
  await page.waitForSelector("#results", { timeout: 30000 });
  await page.waitForTimeout(2000);
  
  // Try multiple approaches
  const recs1 = await page.inputValue("#recommendations");
  const recs2 = await page.getAttribute("#recommendations", "value");
  const recs3 = await page.evaluate(() => document.querySelector("#recommendations").value);
  const recs4 = await page.textContent("#recommendations");
  
  console.log("inputValue:", recs1?.substring(0, 100));
  console.log("getAttribute:", recs2?.substring(0, 100));
  console.log("evaluate:", recs3?.substring(0, 100));
  console.log("textContent:", recs4?.substring(0, 100));
  
  await browser.close();
}

test().catch(console.error);
