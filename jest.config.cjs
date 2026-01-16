// jest.config.js
module.exports = {
  testEnvironment: "node",
  testMatch: ["**/unit-tests/**/*.test.js"],
  collectCoverage: true,
  collectCoverageFrom: ["server.js", "debug_scan.js", "public/app.js"],
  testTimeout: 30000,
  forceExit: true,
  detectOpenHandles: false,
  clearMocks: true,
  // Prevent "Cannot log after tests are done" errors
  maxWorkers: 1,
  // Mock browser-related operations
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
};
