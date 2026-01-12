// debug_scan.test.js
const { expect, test, describe } = require('@jest/globals');

describe('debug_scan.js utility functions', () => {
  const debugScan = require('../debug_scan');

  test('mapIssue returns correct object', () => {
    const result = debugScan.mapIssue('Type', 'Message', 'Recommendation');
    expect(result).toEqual({ type: 'Type', message: 'Message', recommendation: 'Recommendation' });
  });
});
