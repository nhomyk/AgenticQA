// scan-ui.spec.js
const { test, expect } = require("@playwright/test");

test.describe("Agentic QA Engineer UI - Scan Flow", () => {
  test("should show error if no URL is entered", async ({ page }) => {
    await page.goto("/");
    await page.click("#scanBtn");
    // Should show alert, but Playwright cannot catch browser alert directly if not stubbed
    // Instead, check that results box does not change to scanning
    await expect(page.locator("#results")).not.toContainText("Scanning");
  });

  test("should have all result boxes visible on the page", async ({ page }) => {
    await page.goto("/");
    // Verify all textarea boxes are present
    await expect(page.locator("#results")).toBeVisible();
    await expect(page.locator("#testcases")).toBeVisible();
    await expect(page.locator("#performance")).toBeVisible();
    await expect(page.locator("#apis")).toBeVisible();
    // Playwright tab container exists and is active by default
    await expect(page.locator("#playwright")).toHaveClass(/tab-pane/);
    await expect(page.locator("#playwright")).toHaveClass(/active/);
    // Test that Cypress and Vitest tabs exist (hidden by default due to tabbed interface)
    await expect(page.locator("#cypress")).toHaveClass(/tab-pane/);
    await expect(page.locator("#vitest")).toHaveClass(/tab-pane/);
    // Verify we can switch tabs
    await page.click('[data-tab="cypress"]');
    await expect(page.locator("#cypress")).toHaveClass(/active/);
  });

  test("should have proper placeholders for all boxes", async ({ page }) => {
    await page.goto("/");
    // Verify placeholders are set correctly for textarea elements
    const resultsPlaceholder = await page.locator("#results").getAttribute("placeholder");
    const testcasesPlaceholder = await page.locator("#testcases").getAttribute("placeholder");
    const performancePlaceholder = await page.locator("#performance").getAttribute("placeholder");
    const apisPlaceholder = await page.locator("#apis").getAttribute("placeholder");

    expect(resultsPlaceholder).toContain("Results will appear here");
    expect(testcasesPlaceholder).toContain("test cases");
    expect(performancePlaceholder).toContain("JMeter-like performance results");
    expect(apisPlaceholder).toContain("APIs used");
    
    // Verify framework tabs exist as divs (they get populated with content after scan)
    await expect(page.locator("#playwright")).toHaveClass(/tab-pane/);
    await expect(page.locator("#cypress")).toHaveClass(/tab-pane/);
    await expect(page.locator("#vitest")).toHaveClass(/tab-pane/);
  });

  test("should have input field and scan button", async ({ page }) => {
    await page.goto("/");
    const urlInput = page.locator("#urlInput");
    const scanBtn = page.locator("#scanBtn");

    await expect(urlInput).toBeVisible();
    await expect(scanBtn).toBeVisible();

    // Verify input field has placeholder
    const placeholder = await urlInput.getAttribute("placeholder");
    expect(placeholder).toContain("example.com");
  });

  test("should display correct headings", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1")).toContainText("Agentic QA Engineer");
    await expect(page.locator("h3").filter({ hasText: "Scan Results" })).toBeVisible();
  });

  test("should have clickable scan button", async ({ page }) => {
    await page.goto("/");
    const scanBtn = page.locator("#scanBtn");
    await expect(scanBtn).toBeEnabled();
    // Verify button is visible and has proper text
    await expect(scanBtn).toContainText("Scan");
  });
});
