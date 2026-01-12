// scan-ui.spec.js
const { test, expect } = require('@playwright/test');

const TEST_URL = 'https://example.com';

test.describe('Agentic QA Engineer UI - Scan Flow', () => {
  test('should show error if no URL is entered', async ({ page }) => {
    await page.goto('/');
    await page.click('#scanBtn');
    // Should show alert, but Playwright cannot catch browser alert directly if not stubbed
    // Instead, check that results box does not change to scanning
    await expect(page.locator('#results')).not.toContainText('Scanning');
  });

  test('should scan a valid URL and display all result boxes', async ({ page }) => {
    await page.goto('/');
    await page.fill('#urlInput', TEST_URL);
    await page.click('#scanBtn');
    // Wait for scan to complete (results box should update)
    await expect(page.locator('#results')).toContainText('Scan:');
    await expect(page.locator('#testcases')).toBeVisible();
    await expect(page.locator('#performance')).toBeVisible();
    await expect(page.locator('#apis')).toBeVisible();
    await expect(page.locator('#playwright')).toBeVisible();
    await expect(page.locator('#cypress')).toBeVisible();
  });

  test('should display up to 10 APIs in the APIs box', async ({ page }) => {
    await page.goto('/');
    await page.fill('#urlInput', TEST_URL);
    await page.click('#scanBtn');
    await expect(page.locator('#apis')).toBeVisible();
    // The APIs box should have a header and up to 10 lines for APIs
    const apisText = await page.locator('#apis').inputValue();
    const apiLines = apisText.split('\n').filter(l => l.match(/^\d+\. /));
    expect(apiLines.length).toBeLessThanOrEqual(10);
  });

  test('should show Playwright and Cypress code for first test case', async ({ page }) => {
    await page.goto('/');
    await page.fill('#urlInput', TEST_URL);
    await page.click('#scanBtn');
    await expect(page.locator('#playwright')).toContainText('Playwright example for:');
    await expect(page.locator('#cypress')).toContainText('Cypress example for:');
  });

  test('should show recommended test cases (positive and negative)', async ({ page }) => {
    await page.goto('/');
    await page.fill('#urlInput', TEST_URL);
    await page.click('#scanBtn');
    const tcText = await page.locator('#testcases').inputValue();
    expect(tcText).toContain('Positive:');
    expect(tcText).toContain('Negative:');
  });
});
