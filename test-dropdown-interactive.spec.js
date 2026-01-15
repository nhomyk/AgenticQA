/**
 * Dropdown Interactive Tests (Playwright)
 * Tests dropdown menu visibility, interaction, and navigation
 */

import { test, expect } from '@playwright/test';

test.describe('Products Dropdown Menu', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3000');
  });

  test('should display dropdown button', async ({ page }) => {
    const dropdownBtn = page.locator('.dropdown-btn');
    await expect(dropdownBtn).toBeVisible();
    await expect(dropdownBtn).toContainText('Products');
  });

  test('should initially hide dropdown menu', async ({ page }) => {
    const dropdownMenu = page.locator('.dropdown-menu');
    const isVisible = await dropdownMenu.isVisible().catch(() => false);
    expect(isVisible || (await dropdownMenu.evaluate(el => getComputedStyle(el).display === 'none'))).toBeTruthy();
  });

  test('should show dropdown menu on button hover', async ({ page }) => {
    const dropdownBtn = page.locator('.dropdown-btn');
    await dropdownBtn.hover();
    
    const dropdownMenu = page.locator('.dropdown-menu');
    await expect(dropdownMenu).toBeVisible();
  });

  test('should keep menu visible when hovering over it', async ({ page }) => {
    const dropdownBtn = page.locator('.dropdown-btn');
    const dropdownMenu = page.locator('.dropdown-menu');
    
    // Hover over button to show menu
    await dropdownBtn.hover();
    await expect(dropdownMenu).toBeVisible();
    
    // Move to menu without leaving the element
    await dropdownMenu.hover();
    await expect(dropdownMenu).toBeVisible();
  });

  test('should contain orbitQA product link', async ({ page }) => {
    const dropdownBtn = page.locator('.dropdown-btn');
    await dropdownBtn.hover();
    
    const orbitQALink = page.locator('a:has-text("orbitQA")').first();
    await expect(orbitQALink).toBeVisible();
  });

  test('should navigate to product page when clicking orbitQA link', async ({ page }) => {
    const dropdownBtn = page.locator('.dropdown-btn');
    await dropdownBtn.hover();
    
    const orbitQALink = page.locator('a:has-text("orbitQA")').first();
    await orbitQALink.click();
    
    // Wait for navigation
    await page.waitForLoadState('networkidle');
    
    // Check URL or heading
    expect(page.url()).toContain('product');
    const heading = page.locator('h1:has-text("orbitQA")');
    await expect(heading).toBeVisible();
  });

  test('should verify product file exists at correct path', async ({ page }) => {
    const dropdownBtn = page.locator('.dropdown-btn');
    await dropdownBtn.hover();
    
    const spiralQALink = page.locator('a[href*="product"]').first();
    const href = await spiralQALink.getAttribute('href');
    
    // Attempt to fetch the file
    const response = await page.request.get(`http://localhost:3000${href}`);
    expect(response.status()).toBe(200);
  });

  test('should not hide dropdown menu when moving from button to menu', async ({ page }) => {
    const dropdownBtn = page.locator('.dropdown-btn');
    const dropdownMenu = page.locator('.dropdown-menu');
    
    await dropdownBtn.hover();
    await expect(dropdownMenu).toBeVisible();
    
    // Get button position
    const buttonBox = await dropdownBtn.boundingBox();
    const menuBox = await dropdownMenu.boundingBox();
    
    // Move mouse to the space between button and menu (should not hide if properly coded)
    await page.mouse.move(buttonBox.x + buttonBox.width / 2, buttonBox.y + buttonBox.height + 5);
    
    // Small delay to ensure no unintended hover-off
    await page.waitForTimeout(100);
    
    // Menu should still be visible (or at least the link should be clickable)
    const spiralQALink = page.locator('a:has-text("spiralQA")').first();
    const isClickable = await spiralQALink.isVisible().catch(() => false);
    expect(isClickable).toBeTruthy();
  });

  test('should hide dropdown menu when clicking elsewhere', async ({ page }) => {
    const dropdownBtn = page.locator('.dropdown-btn');
    const dropdownMenu = page.locator('.dropdown-menu');
    
    // Show menu
    await dropdownBtn.hover();
    await expect(dropdownMenu).toBeVisible();
    
    // Click elsewhere
    const body = page.locator('body');
    await body.click({ force: true });
    
    // Menu should be hidden (or not visible by default)
    const isHidden = !(await dropdownMenu.isVisible().catch(() => false));
    expect(isHidden || await dropdownMenu.evaluate(el => getComputedStyle(el).display === 'none')).toBeTruthy();
  });

  test('should have all dropdown links pointing to valid files', async ({ page }) => {
    const dropdownBtn = page.locator('.dropdown-btn');
    await dropdownBtn.hover();
    
    const dropdownLinks = page.locator('.dropdown-menu a');
    const linkCount = await dropdownLinks.count();
    
    expect(linkCount).toBeGreaterThan(0);
    
    for (let i = 0; i < linkCount; i++) {
      const link = dropdownLinks.nth(i);
      const href = await link.getAttribute('href');
      
      // Each link should have an href
      expect(href).toBeTruthy();
      
      // Each link should lead to a valid response
      const response = await page.request.get(`http://localhost:3000${href}`, { ignoreHTTPSErrors: true }).catch(() => null);
      expect(response?.status()).toBe(200);
    }
  });

  test('should maintain dropdown styling', async ({ page }) => {
    const dropdownBtn = page.locator('.dropdown-btn');
    
    // Check initial styles
    const btnStyle = await dropdownBtn.evaluate(el => window.getComputedStyle(el));
    expect(btnStyle.cursor).toBe('pointer');
    
    // Check hover color changes
    await dropdownBtn.hover();
    const hoverStyle = await dropdownBtn.evaluate(el => window.getComputedStyle(el));
    expect(hoverStyle.color).toBeTruthy();
  });
});
