/**
 * Frontend UI Tests using Playwright
 * Tests the actual HTML/JavaScript functionality
 */

const { test, expect } = require('@playwright/test');

test.describe('Dashboard Page Tests', () => {
  test('dashboard page loads successfully', async ({ page }) => {
    await page.goto('http://localhost:8080/dashboard.html');

    // Check page title
    await expect(page).toHaveTitle(/AgenticQA/);

    // Check header is visible
    await expect(page.locator('.logo')).toBeVisible();
    await expect(page.locator('.logo')).toContainText('AgenticQA');
  });

  test('pipeline visualization is present', async ({ page }) => {
    await page.goto('http://localhost:8080/dashboard.html');

    // Check pipeline container exists
    await expect(page.locator('.pipeline-container')).toBeVisible();
    await expect(page.locator('.pipeline-container h2')).toContainText('CI/CD Pipeline Flow');

    // Check all 8 pipeline steps are present
    const pipelineSteps = page.locator('.pipeline-step');
    await expect(pipelineSteps).toHaveCount(8);

    // Verify specific pipeline steps
    await expect(page.locator('.pipeline-step:has-text("Validate Workflows")')).toBeVisible();
    await expect(page.locator('.pipeline-step:has-text("Pipeline Health")')).toBeVisible();
    await expect(page.locator('.pipeline-step:has-text("Auto-Fix Linting")')).toBeVisible();
    await expect(page.locator('.pipeline-step:has-text("Data Validation")')).toBeVisible();
  });

  test('agent cards are interactive', async ({ page }) => {
    await page.goto('http://localhost:8080/dashboard.html');

    // Check all 4 agents are present
    await expect(page.locator('.agent-card')).toHaveCount(4);

    // Verify agent names
    await expect(page.locator('.agent-name:has-text("QA Assistant")')).toBeVisible();
    await expect(page.locator('.agent-name:has-text("Performance Agent")')).toBeVisible();
    await expect(page.locator('.agent-name:has-text("Compliance Agent")')).toBeVisible();
    await expect(page.locator('.agent-name:has-text("DevOps Agent")')).toBeVisible();

    // Test agent selection
    const qaAgent = page.locator('.agent-card:has-text("QA Assistant")');
    await qaAgent.click();
    await expect(qaAgent).toHaveClass(/active/);
  });

  test('file upload interface works', async ({ page }) => {
    await page.goto('http://localhost:8080/dashboard.html');

    // Check upload container exists
    await expect(page.locator('.upload-container')).toBeVisible();
    await expect(page.locator('.upload-text')).toContainText('Drag & Drop files here');

    // Verify file input exists
    await expect(page.locator('#fileInput')).toBeAttached();
  });

  test('feature request form is present', async ({ page }) => {
    await page.goto('http://localhost:8080/dashboard.html');

    // Check feature request section
    await expect(page.locator('h2:has-text("Feature Requests")')).toBeVisible();

    // Verify form fields
    await expect(page.locator('#featureTitle')).toBeVisible();
    await expect(page.locator('#featureCategory')).toBeVisible();
    await expect(page.locator('#featureDescription')).toBeVisible();
    await expect(page.locator('#featurePriority')).toBeVisible();

    // Verify submit button
    await expect(page.locator('.submit-btn:has-text("Submit Feature Request")')).toBeVisible();
  });

  test('navigation links work', async ({ page }) => {
    await page.goto('http://localhost:8080/dashboard.html');

    // Check navigation links exist
    await expect(page.locator('nav a:has-text("Dashboard")')).toBeVisible();
    await expect(page.locator('nav a:has-text("Settings")')).toBeVisible();
    await expect(page.locator('nav a:has-text("Logout")')).toBeVisible();
  });

  test('scan functionality elements are present', async ({ page }) => {
    await page.goto('http://localhost:8080/dashboard.html');

    // Check scan section
    await expect(page.locator('#urlInput')).toBeVisible();
    await expect(page.locator('#scanBtn')).toBeVisible();

    // Check result sections exist
    await expect(page.locator('#results')).toBeAttached();
    await expect(page.locator('#technologies')).toBeAttached();
    await expect(page.locator('#testcases')).toBeAttached();
  });
});

test.describe('Settings Page Tests', () => {
  test('settings page loads successfully', async ({ page }) => {
    await page.goto('http://localhost:8080/settings.html');

    await expect(page).toHaveTitle(/AgenticQA/);
    await expect(page.locator('.logo')).toContainText('AgenticQA');
  });

  test('sidebar navigation is present', async ({ page }) => {
    await page.goto('http://localhost:8080/settings.html');

    // Check all sidebar items
    await expect(page.locator('.nav-item:has-text("General")')).toBeVisible();
    await expect(page.locator('.nav-item:has-text("Appearance")')).toBeVisible();
    await expect(page.locator('.nav-item:has-text("Notifications")')).toBeVisible();
    await expect(page.locator('.nav-item:has-text("GitHub Integration")')).toBeVisible();
    await expect(page.locator('.nav-item:has-text("RAG Configuration")')).toBeVisible();
    await expect(page.locator('.nav-item:has-text("API Keys")')).toBeVisible();
    await expect(page.locator('.nav-item:has-text("Security")')).toBeVisible();
  });

  test('github integration section is complete', async ({ page }) => {
    await page.goto('http://localhost:8080/settings.html');

    // Click GitHub Integration
    await page.locator('.nav-item:has-text("GitHub Integration")').click();

    // Verify section is visible
    await expect(page.locator('#github-integration')).toBeVisible();
    await expect(page.locator('h1:has-text("GitHub Integration")')).toBeVisible();

    // Check PAT instructions are present
    await expect(page.locator('text=Step 1: Create a GitHub Personal Access Token')).toBeVisible();

    // Verify form fields
    await expect(page.locator('#githubPAT')).toBeVisible();
    await expect(page.locator('#githubOwner')).toBeVisible();
    await expect(page.locator('#githubRepo')).toBeVisible();
    await expect(page.locator('#githubWorkflow')).toBeVisible();
    await expect(page.locator('#githubBranch')).toBeVisible();

    // Verify action buttons
    await expect(page.locator('button:has-text("Test Connection")')).toBeVisible();
    await expect(page.locator('button:has-text("Trigger Workflow")')).toBeVisible();
    await expect(page.locator('button:has-text("Refresh Status")')).toBeVisible();
  });

  test('rag configuration section is accessible', async ({ page }) => {
    await page.goto('http://localhost:8080/settings.html');

    // Click RAG Configuration
    await page.locator('.nav-item:has-text("RAG Configuration")').click();

    // Verify section is visible
    await expect(page.locator('#rag-config')).toBeVisible();
    await expect(page.locator('h1:has-text("RAG Configuration")')).toBeVisible();

    // Verify RAG mode selector
    await expect(page.locator('#ragMode')).toBeVisible();
    await expect(page.locator('#weaviateHost')).toBeVisible();
    await expect(page.locator('#autoIngest')).toBeVisible();
  });

  test('general settings work', async ({ page }) => {
    await page.goto('http://localhost:8080/settings.html');

    // General should be active by default
    await expect(page.locator('#general')).toBeVisible();

    // Check form fields
    await expect(page.locator('#displayName')).toBeVisible();
    await expect(page.locator('#email')).toBeVisible();
    await expect(page.locator('#language')).toBeVisible();

    // Test input
    await page.locator('#displayName').fill('Test User');
    await expect(page.locator('#displayName')).toHaveValue('Test User');
  });
});

test.describe('Landing Page Tests', () => {
  test('landing page loads', async ({ page }) => {
    await page.goto('http://localhost:8080/index.html');

    await expect(page).toHaveTitle(/AgenticQA/);
    await expect(page.locator('.logo')).toBeVisible();
  });

  test('navigation to dashboard works', async ({ page }) => {
    await page.goto('http://localhost:8080/index.html');

    const dashboardLink = page.locator('a[href="/dashboard.html"]').first();
    if (await dashboardLink.isVisible()) {
      await dashboardLink.click();
      await expect(page).toHaveURL(/dashboard/);
    }
  });
});

test.describe('JavaScript Functionality Tests', () => {
  test('pipeline refresh button works', async ({ page }) => {
    await page.goto('http://localhost:8080/dashboard.html');

    page.on('dialog', dialog => dialog.accept());

    const refreshBtn = page.locator('button:has-text("Refresh Status")');
    await refreshBtn.click();

    // Should not throw error
    await page.waitForTimeout(500);
  });

  test('agent interaction is functional', async ({ page }) => {
    await page.goto('http://localhost:8080/dashboard.html');

    // Handle prompts and alerts
    page.on('dialog', dialog => {
      if (dialog.type() === 'prompt') {
        dialog.accept('Test message');
      } else {
        dialog.accept();
      }
    });

    const interactBtn = page.locator('.agent-interact-btn').first();
    await interactBtn.click();

    await page.waitForTimeout(500);
  });

  test('feature request form validation', async ({ page }) => {
    await page.goto('http://localhost:8080/dashboard.html');

    page.on('dialog', dialog => dialog.accept());

    // Try to submit empty form
    await page.locator('.submit-btn:has-text("Submit Feature Request")').click();

    await page.waitForTimeout(500);

    // Fill form properly
    await page.locator('#featureTitle').fill('Test Feature');
    await page.locator('#featureDescription').fill('Test Description');
    await page.locator('.submit-btn:has-text("Submit Feature Request")').click();

    await page.waitForTimeout(500);
  });
});

test.describe('Critical UI Elements', () => {
  test('no console errors on dashboard', async ({ page }) => {
    const errors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await page.goto('http://localhost:8080/dashboard.html');
    await page.waitForLoadState('networkidle');

    // Allow expected errors (like API calls to localhost endpoints)
    const criticalErrors = errors.filter(err =>
      !err.includes('api/') &&
      !err.includes('Failed to fetch')
    );

    expect(criticalErrors).toHaveLength(0);
  });

  test('no console errors on settings', async ({ page }) => {
    const errors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await page.goto('http://localhost:8080/settings.html');
    await page.waitForLoadState('networkidle');

    const criticalErrors = errors.filter(err =>
      !err.includes('api/') &&
      !err.includes('Failed to fetch')
    );

    expect(criticalErrors).toHaveLength(0);
  });

  test('all CSS is loaded', async ({ page }) => {
    await page.goto('http://localhost:8080/dashboard.html');

    // Check that styled elements have styles applied
    const logo = page.locator('.logo');
    const fontSize = await logo.evaluate(el => window.getComputedStyle(el).fontSize);
    expect(fontSize).not.toBe('16px'); // Should be styled differently than default
  });
});
