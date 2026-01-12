// basic.spec.js
const { test, expect } = require('@playwright/test');

test.describe('Agentic QA Engineer UI', () => {
  test('loads homepage and UI elements', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('h1')).toHaveText('Agentic QA Engineer');
    await expect(page.locator('#urlInput')).toBeVisible();
    await expect(page.locator('#scanBtn')).toBeVisible();
    await expect(page.locator('#results')).toBeVisible();
    await expect(page.locator('#testcases')).toBeVisible();
    await expect(page.locator('#performance')).toBeVisible();
    await expect(page.locator('#apis')).toBeVisible();
    await expect(page.locator('#playwright')).toBeVisible();
    await expect(page.locator('#cypress')).toBeVisible();
  });
});
