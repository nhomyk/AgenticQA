// playwright.config.js
// Basic Playwright config for running browser tests
/** @type {import('@playwright/test').PlaywrightTestConfig} */
const config = {
  webServer: {
    command: 'npm start',
    port: 3000,
    timeout: 120 * 1000,
    reuseExistingServer: !process.env.CI,
  },
  testDir: './playwright-tests',
  use: {
    headless: true,
    baseURL: 'http://localhost:3000',
  },
};

module.exports = config;
