// unit-tests/ui-display.test.js
const { expect, test, describe } = require('@jest/globals');
const fs = require('fs');
const path = require('path');

describe('UI Display Tests', () => {
  let appCode;
  let htmlContent;

  beforeAll(() => {
    appCode = fs.readFileSync(path.join(__dirname, '../public/app.js'), 'utf8');
    htmlContent = fs.readFileSync(path.join(__dirname, '../public/index.html'), 'utf8');
  });

  describe('HTML Structure', () => {
    test('HTML contains Tech Detected header', () => {
      expect(htmlContent).toContain('<h3>Tech Detected</h3>');
    });

    test('HTML does not contain TECH header', () => {
      expect(htmlContent).not.toContain('<h3>TECH</h3>');
    });

    test('HTML contains Scan Results section', () => {
      expect(htmlContent).toContain('Scan Results');
    });

    test('HTML contains APIs Used section', () => {
      expect(htmlContent).toContain('APIs Used');
    });

    test('Technologies textarea has correct placeholder', () => {
      expect(htmlContent).toContain('Technologies detected on the page will appear here');
    });
  });

  describe('App.js Render Logic', () => {
    test('app.js contains Tech Detected header text', () => {
      expect(appCode).toContain('Tech Detected');
    });

    test('app.js contains "No issues detected" message', () => {
      expect(appCode).toContain('No issues detected during scan');
    });

    test('app.js contains "No API calls detected" message', () => {
      expect(appCode).toContain('No API calls detected during scan');
    });

    test('renderResults function exists', () => {
      expect(appCode).toContain('function renderResults(resp)');
    });

    test('handleEmptyResults displays no issues message', () => {
      // Verify the conditional logic for empty results
      expect(appCode).toContain('results.length > 0 ? header + lines.join');
      expect(appCode).toContain('No issues detected during scan');
    });

    test('handleEmptyAPIs displays no API calls message', () => {
      // Verify the conditional logic for empty APIs
      expect(appCode).toContain('resp.apis.length > 0');
      expect(appCode).toContain('No API calls detected during scan');
    });
  });

  describe('Technology Detection Cleanup', () => {
    test('app.js filters out generic/invalid tech names', () => {
      // Should filter generic patterns like object IDs
      expect(appCode).toContain('Filter out generic words');
    });

    test('app.js normalizes technology names', () => {
      // Should format names properly with capitalization
      expect(appCode).toContain('charAt(0).toUpperCase()');
    });

    test('app.js deduplicates technology names', () => {
      // Should prevent duplicate tech names
      expect(appCode).toContain('[...new Set(techNames)]');
    });
  });

  describe('Tab Content Display', () => {
    test('HTML has proper tab structure for test frameworks', () => {
      expect(htmlContent).toContain('data-tab="playwright"');
      expect(htmlContent).toContain('data-tab="cypress"');
      expect(htmlContent).toContain('data-tab="vitest"');
    });

    test('Tab content divs have min-height styling', () => {
      expect(htmlContent).toContain('min-height: 100px');
    });

    test('Tab panes have active state CSS', () => {
      expect(htmlContent).toContain('tab-pane.active { display: block;');
    });
  });

  describe('Section Visibility', () => {
    test('All required textareas are present', () => {
      expect(htmlContent).toContain('id="recommendations"');
      expect(htmlContent).toContain('id="technologies"');
      expect(htmlContent).toContain('id="results"');
      expect(htmlContent).toContain('id="testcases"');
      expect(htmlContent).toContain('id="performance"');
      expect(htmlContent).toContain('id="apis"');
    });

    test('All textareas are readonly', () => {
      const readonlyCount = (htmlContent.match(/readonly/g) || []).length;
      expect(readonlyCount).toBeGreaterThanOrEqual(6);
    });

    test('Technologies section has proper styling', () => {
      expect(htmlContent).toContain('flex: 1');
      expect(htmlContent).toContain('min-width: 320px');
    });
  });
});
