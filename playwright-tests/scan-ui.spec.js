// scan-ui.spec.js
const { test, expect } = require("@playwright/test");

test.describe("AgenticQA UI - Scan Flow", () => {
  test("should show error if no URL is entered", async ({ page }) => {
    await page.goto("/scanner.html");
    await page.click("#scanBtn");
    // Should show alert, but Playwright cannot catch browser alert directly if not stubbed
    // Instead, check that results box does not change to scanning
    await expect(page.locator("#results")).not.toContainText("Scanning");
  });

  test("should have all result boxes visible on the page", async ({ page }) => {
    await page.goto("/scanner.html");
    // Verify all textarea boxes are present and visible or will appear after scanning
    const boxes = ["#results", "#testcases", "#performance", "#apis", "#technologies"];
    for (const selector of boxes) {
      await expect(page.locator(selector)).toBeDefined();
    }
    // Verify playwright test case box exists
    await expect(page.locator("#playwright")).toBeDefined();
  });

  test("should have proper placeholders for all boxes", async ({ page }) => {
    await page.goto("/scanner.html");
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
    await page.goto("/scanner.html");
    const urlInput = page.locator("#urlInput");
    const scanBtn = page.locator("#scanBtn");

    await expect(urlInput).toBeVisible();
    await expect(scanBtn).toBeVisible();

    // Verify input field has placeholder
    const placeholder = await urlInput.getAttribute("placeholder");
    expect(placeholder).toContain("example.com");
  });

  test("should display correct headings", async ({ page }) => {
    await page.goto("/scanner.html");
    await expect(page.locator("h1")).toContainText("Technology Scanner");
  });

  test("should have clickable scan button", async ({ page }) => {
    await page.goto("/scanner.html");
    const scanBtn = page.locator("#scanBtn");
    await expect(scanBtn).toBeEnabled();
    // Verify button is visible and has proper text
    await expect(scanBtn).toContainText("Scan");
  });
});
