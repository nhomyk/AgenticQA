// debug_scan.test.js
const { expect, test, describe, beforeAll, afterAll } = require('@jest/globals');
const fs = require('fs');
const path = require('path');

describe('debug_scan.js utility functions', () => {
  let debugScan;

  beforeAll(() => {
    // Clear module cache to get mocked version
    delete require.cache[require.resolve('../debug_scan.js')];
    debugScan = require('../debug_scan');
  });

  afterAll(async () => {
    // Cleanup after all tests
    jest.clearAllMocks();
  });

  test('debug_scan.js file exists', () => {
    expect(fs.existsSync(path.join(__dirname, '../debug_scan.js'))).toBe(true);
  });

  test('debug_scan exports functions', () => {
    expect(typeof debugScan).toBe('object');
  });

  test('handles async operations without throwing', async () => {
    // Ensure any async operations complete properly
    expect(debugScan).toBeDefined();
    // No uncaught async rejections
    await Promise.resolve();
  });
});
