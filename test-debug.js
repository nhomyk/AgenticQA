const { chromium } = require("playwright");

async function test() {
  const browser = await chromium.launch({ headless: false }); // visible
  const page = await browser.newPage();
  
  // Intercept network to see response
  page.on("response", response => {
    if (response.url().includes("/scan")) {
      response.json().then(data => {
        console.log("Scan response recommendations:", data.recommendations ? "YES" : "NO");
      });
    }
  });
  
  await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
  await page.fill("#urlInput", "http://localhost:3000");
  await page.click("#scanBtn");
  await page.waitForSelector("#results", { timeout: 30000 });
  await page.waitForTimeout(3000);
  
  // Check if recommendations box has content
  const hasContent = await page.evaluate(() => {
    const el = document.querySelector("#recommendations");
    return el ? el.value.length > 0 : false;
  });
  
  console.log("Recommendations box has content:", hasContent);
  
  // Wait for user to close
  await page.waitForTimeout(10000);
  await browser.close();
}

test().catch(console.error);
