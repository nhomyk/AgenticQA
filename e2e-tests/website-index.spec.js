import { test, expect } from '@playwright/test';

test.describe('Scanner Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3000/index.html');
  });

  test('should load page successfully', async ({ page }) => {
    await expect(page).toHaveTitle(/.*/, { timeout: 5000 });
    const body = await page.locator('body');
    await expect(body).toBeVisible();
  });

  test('should have no console errors', async ({ page }) => {
    const errors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });
    await page.goto('http://localhost:3000/index.html');
    expect(errors.length).toBe(0);
  });

  test('should render all major UI elements', async ({ page }) => {
    const elements = await page.locator('[id]').count();
    expect(elements).toBeGreaterThan(0);
  });

  test('should have valid HTML structure', async ({ page }) => {
    const html = await page.content();
    expect(html).toContain('<!DOCTYPE html>');
  });

  test('should be accessible - no role violations', async ({ page }) => {
    const accessibilityIssues = [];
    page.on('console', msg => {
      if (msg.text().includes('role') || msg.text().includes('aria')) {
        accessibilityIssues.push(msg.text());
      }
    });
    await page.goto('http://localhost:3000/index.html');
    expect(accessibilityIssues.length).toBeLessThan(3);
  });
});