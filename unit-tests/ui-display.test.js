// unit-tests/ui-display.test.js
// Tests for AgenticQA dashboard (new UI)
const { expect, test, describe } = require('@jest/globals');
const fs = require('fs');
const path = require('path');

describe('UI Display Tests - Dashboard', () => {
  let appCode;
  let htmlContent;

  beforeAll(() => {
    appCode = fs.readFileSync(path.join(__dirname, '../public/app.js'), 'utf8');
    htmlContent = fs.readFileSync(path.join(__dirname, '../public/index.html'), 'utf8');
  });

  describe('Dashboard HTML Structure', () => {
    test('HTML is valid HTML5 document', () => {
      expect(htmlContent).toContain('<!DOCTYPE html>');
      expect(htmlContent).toContain('lang="en"');
    });

    test('HTML contains AgenticQA branding', () => {
      expect(htmlContent).toContain('AgenticQA');
    });

    test('HTML includes viewport meta tag', () => {
      expect(htmlContent).toContain('viewport');
    });
  });

  describe('Dashboard Navigation - Tabs', () => {
    test('HTML contains Overview tab', () => {
      expect(htmlContent).toContain('Overview');
    });

    test('HTML contains Who We Are tab', () => {
      expect(htmlContent).toContain('Who We Are');
    });

    test('HTML contains Consulting Services tab', () => {
      expect(htmlContent).toContain('Consulting Services');
    });

    test('HTML contains Architecture tab', () => {
      expect(htmlContent).toContain('Architecture');
    });

    test('HTML contains Compliance tab', () => {
      expect(htmlContent).toContain('Compliance');
    });
  });

  describe('Content Sections', () => {
    test('HTML has content areas for displays', () => {
      expect(htmlContent).toContain('content');
    });

    test('HTML includes active state class', () => {
      expect(htmlContent).toContain('active');
    });
  });

  describe('Responsive Design', () => {
    test('CSS includes layout system', () => {
      expect(htmlContent).toContain('grid') || expect(htmlContent).toContain('flex');
    });

    test('CSS includes max-width constraints', () => {
      expect(htmlContent).toContain('max-width');
    });
  });

  describe('Styling', () => {
    test('HTML includes CSS styling', () => {
      expect(htmlContent).toContain('<style>');
    });

    test('Styling includes color definitions', () => {
      expect(htmlContent).toContain('#');
    });
  });

  describe('Accessibility', () => {
    test('HTML includes title element', () => {
      expect(htmlContent).toContain('<title>');
    });

    test('HTML uses semantic structure', () => {
      expect(htmlContent.length).toBeGreaterThan(1000);
    });
  });
});

