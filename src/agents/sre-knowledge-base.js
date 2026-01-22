/**
 * SRE Agent Knowledge Base
 * 
 * Comprehensive database of known pipeline failures and remediation strategies
 * Enables agents to autonomously diagnose and fix issues across all pipeline phases
 */

const knowledgeBase = {
  pipelinePhases: {
    'phase-0-emergency-repair': {
      name: 'Emergency Repair System',
      triggers: [
        'Missing artifact directories',
        'Missing configuration files',
        'Missing .gitkeep files',
        'Uninitialized directories'
      ],
      solutions: [
        'Create test-failures directory with .gitkeep',
        'Create compliance-artifacts directory with .gitkeep',
        'Create .pa11yci.json with default config',
        'Create placeholder summary.json files',
        'Run src/agents/sre-pipeline-emergency-repair.js'
      ],
      autoFix: true
    },

    'phase-1-accessibility-scan': {
      name: 'Pa11y Accessibility Scanning',
      triggers: [
        'pa11y-report.json not found',
        'Pa11y command fails',
        'Chromium sandbox errors',
        'Port already in use'
      ],
      solutions: [
        'Ensure .pa11yci.json exists with proper config',
        'Use --no-sandbox --disable-setuid-sandbox flags',
        'Create test-failures directory before running',
        'Kill process on port 3000 if server hanging',
        'Run pa11y-ci with retry logic'
      ],
      autoFix: true
    },

    'phase-1-compliance-agent': {
      name: 'Compliance Agent Validation',
      triggers: [
        'Compliance checks failing',
        'GDPR/CCPA validation errors',
        'License audit failures',
        'Policy generation errors'
      ],
      solutions: [
        'Ensure compliance-audit-report.md exists',
        'Check that licenses.json is properly formatted',
        'Verify PRIVACY_POLICY.md exists',
        'Check TERMS_OF_SERVICE.md exists',
        'Run compliance agent with --verbose flag'
      ],
      autoFix: true,
      knowledge: {
        gdprChecks: [
          'Data processing agreement exists',
          'Privacy rights documented',
          'Data retention policy clear'
        ],
        ccpaChecks: [
          'California rights documented',
          'Opt-out mechanism exists',
          'Disclosure complete'
        ]
      }
    },

    'phase-1-sdet-agent': {
      name: 'SDET UI Change Detection',
      triggers: [
        'UI test generation failures',
        'Missing Cypress specs',
        'Playwright tests failing',
        'DOM changes detected but no tests'
      ],
      solutions: [
        'Ensure cypress/e2e directory exists',
        'Check that Playwright is installed',
        'Verify test files have proper structure',
        'Generate missing test specs automatically',
        'Run sdet-ui-change-detector.js'
      ],
      autoFix: true
    },

    'phase-2-fullstack-agent': {
      name: 'Fullstack Agent (Code & Compliance Fixes)',
      triggers: [
        'test-failures artifact not found',
        'Code generation failing',
        'Compliance auto-fix not working',
        'Cannot download test-failures artifact'
      ],
      solutions: [
        'Create test-failures/.gitkeep if missing',
        'Generate test-failures/summary.json placeholder',
        'Ensure test phases run before fullstack agent',
        'Check artifacts are properly uploaded',
        'Fallback to placeholder data if artifact missing'
      ],
      autoFix: true,
      knowledge: {
        fixableIssues: [
          'Missing alt text on images',
          'Unused variables and functions',
          'Color contrast problems',
          'Missing form labels',
          'npm audit vulnerabilities'
        ]
      }
    },

    'phase-2-5-observability': {
      name: 'Observability Setup (Prometheus & Jaeger)',
      triggers: [
        'Prometheus not starting',
        'Jaeger connection failed',
        'Metrics collection not working',
        'Tracing not initialized'
      ],
      solutions: [
        'Ensure prometheus.yml exists',
        'Check Prometheus service dependencies',
        'Verify Jaeger backend is running',
        'Create placeholder metrics if services unavailable',
        'Continue pipeline even if observability fails'
      ],
      autoFix: true
    },

    'phase-3-sre-agent': {
      name: 'SRE Agent (Pipeline & Production Fixes)',
      triggers: [
        'Linting errors not fixed',
        'Port conflicts',
        'Server not starting',
        'Missing cleanup scripts'
      ],
      solutions: [
        'Run eslint --fix automatically',
        'Kill processes on conflicting ports',
        'Ensure server graceful shutdown',
        'Check system resources',
        'Apply SRE dependency healer'
      ],
      autoFix: true,
      knowledge: {
        commonFixtures: [
          'eslint --fix',
          'npm audit fix --force',
          'lsof -ti:{port} | xargs kill -9',
          'killall node',
          'rm -rf node_modules && npm ci'
        ]
      }
    },

    'phase-4-safeguards': {
      name: 'Safeguards Validation',
      triggers: [
        'File protection violations',
        'Risk assessment high',
        'Unauthorized changes detected',
        'Rollback monitoring failed'
      ],
      solutions: [
        'Check package.json modifications',
        'Verify .env files not changed',
        'Validate .github/workflows/* protection',
        'Review auth/* and payment/* changes',
        'Score risk level and allow if acceptable'
      ],
      autoFix: false,
      knowledge: {
        protectedFiles: [
          'package.json',
          '.env*',
          '.github/workflows/**',
          'auth/**',
          'payment/**',
          '*.lock'
        ],
        riskFactors: {
          'security-code-change': 0.3,
          'multiple-directories': 0.2,
          'file-deletion': 0.15,
          'lock-file-change': 0.25
        }
      }
    }
  },

  commonErrors: {
    'ETARGET': {
      description: 'Package version not found on npm registry',
      cause: 'Requested version does not exist',
      solution: 'Downgrade to previous minor version',
      fix: 'Use SRE dependency healer agent'
    },
    'ENOENT': {
      description: 'File or directory not found',
      cause: 'Missing artifact or configuration file',
      solution: 'Create placeholder or default file',
      fix: 'Run emergency repair system'
    },
    'EADDRINUSE': {
      description: 'Port already in use',
      cause: 'Previous process still running',
      solution: 'Kill process or change port',
      fix: 'killall node or lsof -ti:{port} | xargs kill -9'
    },
    'ECONNREFUSED': {
      description: 'Connection refused',
      cause: 'Service not running or network issue',
      solution: 'Start service or check connectivity',
      fix: 'Ensure database/API running before agents'
    }
  },

  agentCapabilities: {
    'SRE Dependency Healer': {
      triggers: ['npm ci fails', 'version mismatch', 'ETARGET errors'],
      actions: [
        'Parse version error',
        'Downgrade to stable version',
        'Retry npm ci',
        'Report remediation'
      ]
    },
    'SRE Pipeline Emergency Repair': {
      triggers: ['Pipeline initialization', 'missing artifacts', 'workflow errors'],
      actions: [
        'Run diagnostics',
        'Create missing directories',
        'Create placeholder files',
        'Setup CI environment',
        'Report repairs applied'
      ]
    },
    'Compliance Agent': {
      triggers: ['Code changes', 'deployment', 'scheduled checks'],
      actions: [
        'Run 175+ compliance checks',
        'Generate compliance report',
        'Auto-fix policy documents',
        'Validate against 7 standards'
      ]
    },
    'SDET Agent': {
      triggers: ['UI changes detected', 'test coverage gaps'],
      actions: [
        'Generate test specs',
        'Validate test coverage',
        'Create accessibility tests',
        'Update test artifacts'
      ]
    },
    'Fullstack Agent': {
      triggers: ['Code violations', 'compliance failures'],
      actions: [
        'Fix code issues',
        'Apply compliance remediation',
        'Generate missing docs',
        'Validate fixes'
      ]
    }
  },

  bestPractices: {
    errorHandling: [
      'Always provide graceful degradation',
      'Log errors with context and remediation steps',
      'Never fail silently - report all issues',
      'Continue pipeline if non-critical failure',
      'Provide retry logic for transient errors'
    ],
    artifactManagement: [
      'Create placeholder artifacts if generation fails',
      'Upload artifacts after each phase',
      'Ensure .gitkeep files exist for empty dirs',
      'Archive artifacts for historical analysis'
    ],
    agentCoordination: [
      'Each agent reports its status',
      'Agents wait for dependencies before running',
      'Share context via artifact uploads',
      'Use Neo4j for workflow lineage',
      'Use Weaviate for semantic memory'
    ]
  },

  testFrameworkFixes: {
    cypress: {
      framework: 'Cypress E2E Testing',
      commonFailures: [
        {
          error: 'Element not found: Technologies Detected',
          cause: 'Test timeout or element not rendered',
          fix: 'Add cy.visit("/", { timeout: 10000 }) and cy.contains("h3", "Technologies Detected").should("be.visible")',
          autoFix: true,
          file: 'cypress/e2e/scan-ui.cy.js'
        },
        {
          error: 'Assertion failed on tab navigation',
          cause: 'Tab not active after click',
          fix: 'Add cy.wait(500) after tab click to ensure DOM update',
          autoFix: true,
          file: 'cypress/e2e/scan-ui.cy.js'
        },
        {
          error: 'CTA button not visible',
          cause: 'Hero section not loaded',
          fix: 'Add beforeEach with cy.visit("/", { timeout: 10000 })',
          autoFix: true,
          file: 'cypress/e2e/scan-ui.cy.js'
        }
      ]
    },

    playwright: {
      framework: 'Playwright Component Testing',
      commonFailures: [
        {
          error: 'Playwright test timeout',
          cause: 'Page not loading within default timeout',
          fix: 'Add test.setTimeout(30000), page.setDefaultTimeout(30000), and waitUntil: "domcontentloaded"',
          autoFix: true,
          file: 'playwright-tests/scan-ui.spec.js'
        },
        {
          error: 'Element not visible within timeout',
          cause: 'Async render not completed',
          fix: 'Add { timeout: 10000 } to each expect() call and await page.waitForLoadState("domcontentloaded")',
          autoFix: true,
          file: 'playwright-tests/scan-ui.spec.js'
        },
        {
          error: 'Scanner.html page not found',
          cause: 'Server not running or page not served',
          fix: 'Ensure server is started before tests run; add waitUntil: "domcontentloaded" to goto()',
          autoFix: true,
          file: 'playwright-tests/scan-ui.spec.js'
        }
      ]
    },

    jest: {
      framework: 'Jest Unit Testing',
      commonFailures: [
        {
          error: 'Module not found or mocking issue',
          cause: 'Missing package or incorrect mock setup',
          fix: 'Check package.json dependencies; update jest.config.js moduleNameMapper',
          autoFix: false
        }
      ]
    }
  }
};
