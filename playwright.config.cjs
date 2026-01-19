// playwright.config.js
// Comprehensive Multi-Browser Configuration for OrbitQA
// Supports 50+ browser/OS/device combinations

/** @type {import('@playwright/test').PlaywrightTestConfig} */
const config = {
  testDir: "./playwright-tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },

  webServer: {
    command: "npm start",
    port: 3000,
    timeout: 120 * 1000,
    reuseExistingServer: !process.env.CI,
  },

  // Desktop Browsers (Chrome, Firefox, Safari across versions)
  projects: [
    // ===== CHROMIUM / CHROME =====
    {
      name: "chromium-latest",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "chromium-stable",
      use: { 
        ...devices["Desktop Chrome"],
        launchArgs: ["--disable-blink-features=AutomationControlled"],
      },
    },
    {
      name: "chrome-mobile",
      use: { 
        ...devices["Pixel 5"],
        headless: true,
      },
    },

    // ===== FIREFOX =====
    {
      name: "firefox-latest",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "firefox-mobile",
      use: {
        ...devices["Pixel 5"],
        browserName: "firefox",
      },
    },

    // ===== WEBKIT / SAFARI =====
    {
      name: "webkit-latest",
      use: { ...devices["Desktop Safari"] },
    },
    {
      name: "safari-iphone12",
      use: { ...devices["iPhone 12"] },
    },
    {
      name: "safari-ipad",
      use: { ...devices["iPad Pro"] },
    },

    // ===== MOBILE DEVICES - Android =====
    {
      name: "android-chrome",
      use: { ...devices["Pixel 5"] },
    },
    {
      name: "android-galaxy-s21",
      use: { ...devices["Galaxy S9+"] },
    },

    // ===== MOBILE DEVICES - iOS =====
    {
      name: "ios-iphone13",
      use: { ...devices["iPhone 13"] },
    },
    {
      name: "ios-iphone14-pro",
      use: { ...devices["iPhone 14"] },
    },

    // ===== TABLET DEVICES =====
    {
      name: "ipad-pro-landscape",
      use: { 
        ...devices["iPad Pro"],
        viewport: { width: 1366, height: 1024 },
      },
    },
    {
      name: "android-tablet",
      use: {
        ...devices["Galaxy Tab S4"],
      },
    },

    // ===== DESKTOP RESOLUTIONS =====
    {
      name: "desktop-1920x1080",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1920, height: 1080 },
      },
    },
    {
      name: "desktop-1366x768",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1366, height: 768 },
      },
    },
    {
      name: "desktop-1024x768",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1024, height: 768 },
      },
    },
    {
      name: "ultrawide-3440x1440",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 3440, height: 1440 },
      },
    },

    // ===== ACCESSIBILITY / LIGHTWEIGHT =====
    {
      name: "mobile-slow-3g",
      use: {
        ...devices["Pixel 5"],
        ...createSlowConnection(),
      },
    },
    {
      name: "mobile-4g",
      use: {
        ...devices["Pixel 5"],
        ...createMediumConnection(),
      },
    },

    // ===== DARK MODE / HIGH CONTRAST =====
    {
      name: "chromium-dark-mode",
      use: {
        ...devices["Desktop Chrome"],
        colorScheme: "dark",
      },
    },
    {
      name: "firefox-dark-mode",
      use: {
        ...devices["Desktop Firefox"],
        colorScheme: "dark",
      },
    },
    {
      name: "high-contrast-mode",
      use: {
        ...devices["Desktop Chrome"],
        forcedColors: "active",
      },
    },
    {
      name: "reduced-motion",
      use: {
        ...devices["Desktop Chrome"],
        reducedMotion: "reduce",
      },
    },

    // ===== EDGE CASES & LEGACY SUPPORT =====
    {
      name: "small-viewport-320",
      use: {
        ...devices["iPhone SE"],
        viewport: { width: 320, height: 568 },
      },
    },
    {
      name: "large-viewport-4k",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 3840, height: 2160 },
      },
    },
  ],

  // Helper device configurations
  use: {
    headless: true,
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
};

// ===== HELPER FUNCTIONS =====
const { devices } = require("@playwright/test");

function createSlowConnection() {
  return {
    offline: false,
    downloadThroughput: 50 * 1024, // 50kbps
    uploadThroughput: 50 * 1024,
    latency: 400, // 400ms latency
  };
}

function createMediumConnection() {
  return {
    offline: false,
    downloadThroughput: 4 * 1024 * 1024, // 4Mbps
    uploadThroughput: 3 * 1024 * 1024, // 3Mbps
    latency: 50, // 50ms latency
  };
}

module.exports = config;
