// server.test.js
const { expect, test, describe } = require('@jest/globals');
const path = require('path');

describe('server.js utility functions', () => {
  const server = require('../server');

  test('normalizeUrl adds http if missing', () => {
    const { normalizeUrl } = server;
    expect(normalizeUrl('example.com')).toBe('http://example.com');
    expect(normalizeUrl('https://secure.com')).toBe('https://secure.com');
    expect(normalizeUrl('http://plain.com')).toBe('http://plain.com');
  });

  test('mapIssue returns correct object', () => {
    const { mapIssue } = server;
    const result = mapIssue('Type', 'Message', 'Recommendation');
    expect(result).toEqual({ type: 'Type', message: 'Message', recommendation: 'Recommendation' });
  });
});
