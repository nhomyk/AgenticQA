// basic.spec.js
const { test, expect } = require('@playwright/test');

test.describe('AgenticQA Dashboard', () => {
  test('loads homepage and UI elements', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('h1')).toHaveText('AgenticQA');
    // Verify homepage has scanner link
    await expect(page.locator('a:has-text("Technology Scanner")')).toBeVisible();
  });
});

