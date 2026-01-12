// jest.config.js
module.exports = {
  testEnvironment: "node",
  testMatch: ["**/unit-tests/**/*.test.js"],
  collectCoverage: true,
  collectCoverageFrom: ["server.js", "debug_scan.js", "public/app.js"],
};
