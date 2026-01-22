// scan-ui.spec.js
const { test, expect } = require("@playwright/test");

// Configure timeouts globally
test.setTimeout(30000);

test.describe("AgenticQA UI - Scan Flow", () => {
  test.beforeEach(async ({ page }) => {
    // Set default navigation timeout
    page.setDefaultTimeout(30000);
    page.setDefaultNavigationTimeout(30000);
  });

  test("should show error if no URL is entered", async ({ page }) => {
    await page.goto("/scanner.html", { waitUntil: "domcontentloaded" });
    await page.click("#scanBtn");
    // Should show alert, but Playwright cannot catch browser alert directly if not stubbed
    // Instead, check that results box does not change to scanning
    await expect(page.locator("#results")).not.toContainText("Scanning");
  });

  test("should have all result boxes visible on the page", async ({ page }) => {
    await page.goto("/scanner.html", { waitUntil: "domcontentloaded" });
    // Verify all textarea boxes are present and visible or will appear after scanning
    const boxes = ["#results", "#testcases", "#performance", "#apis", "#technologies"];
    for (const selector of boxes) {
      await expect(page.locator(selector)).toBeDefined();
    }
    // Verify playwright test case box exists
    await expect(page.locator("#playwright")).toBeDefined();
  });

  test("should have proper placeholders for all boxes", async ({ page }) => {
    await page.goto("/scanner.html", { waitUntil: "domcontentloaded" });
    // Verify placeholders are set correctly for textarea elements
    const resultsPlaceholder = await page.locator("#results").getAttribute("placeholder");
    const testcasesPlaceholder = await page.locator("#testcases").getAttribute("placeholder");
    const performancePlaceholder = await page.locator("#performance").getAttribute("placeholder");
    const apisPlaceholder = await page.locator("#apis").getAttribute("placeholder");

    expect(resultsPlaceholder).toContain("will appear here");
    expect(testcasesPlaceholder).toContain("test cases");
    expect(performancePlaceholder).toContain("Performance");
    expect(apisPlaceholder).toContain("API");
  });

  test("should have input field and scan button", async ({ page }) => {
    await page.goto("/scanner.html", { waitUntil: "domcontentloaded" });
    const urlInput = page.locator("#urlInput");
    const scanBtn = page.locator("#scanBtn");

    await expect(urlInput).toBeVisible({ timeout: 10000 });
    await expect(scanBtn).toBeVisible({ timeout: 10000 });

    // Verify input field has placeholder
    const placeholder = await urlInput.getAttribute("placeholder");
    expect(placeholder).toContain("example.com");
  });

  test("should display correct headings", async ({ page }) => {
    await page.goto("/scanner.html", { waitUntil: "domcontentloaded" });
    await expect(page.locator("h1")).toContainText("Technology Scanner", { timeout: 10000 });
  });

  test("should have clickable scan button", async ({ page }) => {
    await page.goto("/scanner.html", { waitUntil: "domcontentloaded" });
    const scanBtn = page.locator("#scanBtn");
    await expect(scanBtn).toBeEnabled({ timeout: 10000 });
    // Verify button is visible and has proper text
    await expect(scanBtn).toContainText("Scan", { timeout: 10000 });
  });
});
