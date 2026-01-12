// app.test.js
const { expect, test, describe } = require('@jest/globals');

describe('app.js UI helpers', () => {
  test('generatePlaywrightExample returns correct template', () => {
    const fn = eval(`(${require('fs').readFileSync(require('path').join(__dirname, '../public/app.js'), 'utf8').match(/function generatePlaywrightExample[\s\S]*?\n}/)[0]})`);
    const result = fn('Positive: Verify main headings render properly', 'https://example.com');
    expect(result).toContain('Playwright example for: Positive: Verify main headings render properly');
    expect(result).toContain('await page.goto');
  });

  test('generateCypressExample returns correct template', () => {
    const fn = eval(`(${require('fs').readFileSync(require('path').join(__dirname, '../public/app.js'), 'utf8').match(/function generateCypressExample[\s\S]*?\n}/)[0]})`);
    const result = fn('Positive: Verify main headings render properly', 'https://example.com');
    expect(result).toContain('Cypress example for: Positive: Verify main headings render properly');
    expect(result).toContain('cy.visit');
  });
});
