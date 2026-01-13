// app.test.js
const { expect, test, describe } = require('@jest/globals');

describe('app.js UI helpers', () => {
  test('generatePlaywrightExample returns correct template', () => {
    const fn = eval(`(${require('fs').readFileSync(require('path').join(__dirname, '../public/app.js'), 'utf8').match(/function generatePlaywrightExample[\s\S]*?\n}/)[0]})`);
    const result = fn('Positive: Verify main headings render properly', 'https://example.com', 1);
    expect(result).toContain('Test Case 1: Positive: Verify main headings render properly');
    expect(result).toContain('await page.goto');
    expect(result).toContain('const { test, expect }');
  });

  test('generateCypressExample returns correct template', () => {
    const fn = eval(`(${require('fs').readFileSync(require('path').join(__dirname, '../public/app.js'), 'utf8').match(/function generateCypressExample[\s\S]*?\n}/)[0]})`);
    const result = fn('Positive: Verify main headings render properly', 'https://example.com', 1);
    expect(result).toContain('Test case 1');
    expect(result).toContain('cy.visit');
    expect(result).toContain('describe');
  });
});
