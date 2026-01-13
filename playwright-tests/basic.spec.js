// basic.spec.js
const { test, expect } = require('@playwright/test');

test.describe('AgenticQA Dashboard', () => {
  test('loads homepage and UI elements', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('h1')).toHaveText('AgenticQA');
    // Need to navigate to scanner tab to see scanner elements
    await page.click('button:has-text("Scanner")');
    await expect(page.locator('#urlInput')).toBeVisible();
    await expect(page.locator('#scanBtn')).toBeVisible();
    await expect(page.locator('#results')).toBeVisible();
    await expect(page.locator('#testcases')).toBeVisible();
    await expect(page.locator('#performance')).toBeVisible();
    await expect(page.locator('#apis')).toBeVisible();
    // Playwright tab container exists and is active by default
    await expect(page.locator('#playwright')).toHaveClass(/tab-pane/);
    await expect(page.locator('#playwright')).toHaveClass(/active/);
    // Test that tab elements exist (Cypress and Vitest are hidden by default)
    await expect(page.locator('#cypress')).toHaveClass(/tab-pane/);
    await expect(page.locator('#vitest')).toHaveClass(/tab-pane/);
    // Test tab switching
    await page.click('[data-tab="cypress"]');
    await expect(page.locator('#cypress')).toHaveClass(/active/);
    await page.click('[data-tab="vitest"]');
    await expect(page.locator('#vitest')).toHaveClass(/active/);
  });
});
