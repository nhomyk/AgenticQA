// jest.setup.js - Global test setup

// Mock Puppeteer globally
jest.mock('puppeteer', () => ({
  launch: jest.fn().mockResolvedValue({
    newPage: jest.fn().mockResolvedValue({
      goto: jest.fn().mockResolvedValue(),
      evaluate: jest.fn().mockResolvedValue([]),
      evaluateHandle: jest.fn().mockResolvedValue({}),
      content: jest.fn().mockResolvedValue('<html></html>'),
      metrics: jest.fn().mockResolvedValue({
        JSHeapUsedSize: 0,
        JSHeapTotalSize: 0,
      }),
      close: jest.fn().mockResolvedValue(),
    }),
    close: jest.fn().mockResolvedValue(),
  }),
  executablePath: jest.fn().mockReturnValue('/mock/chrome'),
}));

// Suppress console warnings during tests
global.console = {
  ...console,
  warn: jest.fn(),
  error: jest.fn(),
  log: jest.fn(),
};

// Handle unhandled promise rejections
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// Set test environment
process.env.NODE_ENV = 'test';
process.env.PORT = '3000';
