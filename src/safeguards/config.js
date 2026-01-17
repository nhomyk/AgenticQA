/**
 * Safeguards Configuration
 * Default configuration for all safety mechanisms
 */

module.exports = {
  // Global safeguards settings
  enabled: true,

  gatekeeper: {
    enableFiltering: true,
    enableLogging: true,
    maxChangesPerPR: 50,
    blockedFilePatterns: [
      '**/package.json',
      '**/.env*',
      '**/auth/**',
      '**/payment/**',
      '**/*.lock',
      '**/.git/**',
      '**/node_modules/**',
      '**/.github/workflows/**'
    ],
    allowedFilePatterns: [
      '**/*.js',
      '**/*.ts',
      '**/*.jsx',
      '**/*.tsx',
      '**/*.json',
      '**/*.md',
      '**/*.yml',
      '**/*.yaml',
      '**/*.html',
      '**/*.css',
      '**/*.scss'
    ]
  },

  rollback: {
    enableMonitoring: true,
    enableLogging: true,
    monitoringDurationMs: 30 * 60 * 1000, // 30 minutes
    pollIntervalMs: 5000, // Check every 5 seconds
    thresholds: {
      errorRateIncreasePercent: 50,
      latencyIncreasePercent: 30,
      memoryLeakMB: 100,
      cpuSpikePercent: 40,
      failedTestsThreshold: 5
    }
  },

  audit: {
    enableAuditLogging: true,
    enableConsoleOutput: true,
    enableS3Archive: false,
    storagePath: './audit-logs',
    alertThreshold: 0.75, // Risk score 0-1
    maxEntriesInMemory: 10000
  }
};
