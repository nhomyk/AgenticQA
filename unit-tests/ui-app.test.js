const { expect, test, describe } = require('@jest/globals');
const fs = require('fs');

describe('UI App (app.js)', () => {
  test('app.js file exists', () => {
    expect(fs.existsSync('public/app.js')).toBe(true);
  });
  
  test('app.js contains required functions', () => {
    const appCode = fs.readFileSync('public/app.js', 'utf-8');
    expect(appCode.includes('function')).toBe(true);
  });
  
  test('index.html is valid', () => {
    const html = fs.readFileSync('public/index.html', 'utf-8');
    expect(html).toContain('DOCTYPE');
    expect(html).toContain('html');
  });
});