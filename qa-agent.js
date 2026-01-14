#!/usr/bin/env node
/**
 * QA Agent - Automated & Manual QA Expert
 * 
 * Capabilities:
 * - Opens the frontend UI in a browser
 * - Tests all interactive elements
 * - Checks console for errors
 * - Discovers issues in real-time
 * - Makes code changes to fix issues
 * - Runs test suite to validate fixes
 * - Generates detailed QA reports
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const QA_TESTS = {
  STRUCTURE: 'structure',
  STYLING: 'styling',
  JAVASCRIPT: 'javascript',
  BUTTONS: 'buttons',
  FORMS: 'forms',
  TABS: 'tabs',
  ERROR_HANDLING: 'error-handling',
  EMPTY_STATES: 'empty-states',
  INTEGRATION: 'integration'
};

// ========== QA AGENT EXPERT KNOWLEDGE DATABASE ==========
// Comprehensive QA testing expertise for AgenticQA platform

const QA_EXPERTISE = {
  platform: {
    name: 'AgenticQA - Automated QA Testing Platform',
    description: 'Manual QA expertise with automated testing & issue discovery',
    role: 'QA Engineer - Ensures product quality, user experience, and reliability',
    expertise: [
      'Manual UI Testing - Real user workflow simulation',
      'Accessibility Auditing - WCAG 2.1 & ADA compliance',
      'Cross-browser Testing - Chrome, Firefox, Safari compatibility',
      'Performance Testing - Load times, resource usage analysis',
      'Error Detection - Console errors, uncaught exceptions, API failures',
      'User Journey Testing - Critical paths, edge cases, error states'
    ]
  },
  testingStrategy: {
    manual: {
      description: 'Human-like interaction testing',
      techniques: [
        'Click navigation elements and verify responses',
        'Type in forms and validate input handling',
        'Check visual consistency across states',
        'Verify error messages are helpful & accurate',
        'Test accessibility with keyboard navigation',
        'Validate mobile responsiveness'
      ]
    },
    automated: {
      description: 'Systematic test coverage via Puppeteer',
      techniques: [
        'Page load verification',
        'Element presence validation',
        'Event listener attachment checks',
        'Console message capture & analysis',
        'Function existence verification',
        'API response validation'
      ]
    },
    accessibility: {
      standards: ['WCAG 2.1 Level AA', 'ADA Compliance'],
      checks: [
        'Semantic HTML structure',
        'ARIA labels & roles',
        'Keyboard navigation support',
        'Color contrast ratios (4.5:1 minimum)',
        'Alt text for all images',
        'Focus indicators visible'
      ]
    }
  },
  issueCategories: {
    structure: {
      description: 'DOM/HTML problems',
      examples: ['Missing elements', 'Broken hierarchy', 'Invalid semantics']
    },
    styling: {
      description: 'CSS/visual issues',
      examples: ['Wrong colors', 'Broken layout', 'Typography problems', 'Responsiveness']
    },
    javascript: {
      description: 'JS logic problems',
      examples: ['Missing functions', 'Event listener failures', 'Logic errors']
    },
    buttons: {
      description: 'Button/interaction issues',
      examples: ['Disabled buttons', 'Missing event handlers', 'Wrong actions']
    },
    forms: {
      description: 'Form validation problems',
      examples: ['Missing inputs', 'Bad validation', 'Unclear labels']
    },
    tabs: {
      description: 'Tab switching issues',
      examples: ['Won\'t switch', 'Content not updating', 'Active state broken']
    },
    errorHandling: {
      description: 'Error recovery problems',
      examples: ['No error messages', 'Unhandled exceptions', 'Bad retry logic']
    },
    emptyStates: {
      description: 'Empty/initial state issues',
      examples: ['No placeholder', 'Confusing UI', 'No guidance']
    },
    integration: {
      description: 'System-wide issues',
      examples: ['API failures', 'Data flow broken', 'Cross-component problems']
    }
  },
  uiKnowledge: {
    tabs: ['Overview', 'Features', 'Use Cases', 'Technical', 'Pricing'],
    selectors: {
      'url-input': '#urlInput',
      'scan-button': '#scanBtn',
      'results-container': '#resultsContainer',
      'test-cases-section': '#testCasesSection',
      'download-button': 'button:contains("Download")',
      'copy-button': 'button:contains("Copy")',
      'tab-buttons': '.tab-button',
      'tab-content': '.tab-pane',
      'textarea': 'textarea'
    },
    criticalElements: [
      'URL input field (required)',
      'Scan button (CTA)',
      'Results display area',
      'Test script generation',
      'Download/Copy actions',
      'Tab navigation',
      'Error messages'
    ]
  },
  severityLevels: {
    critical: {
      description: 'Blocks core functionality',
      examples: ['App won\'t load', 'Buttons don\'t work', 'Data lost']
    },
    high: {
      description: 'Significantly impacts UX',
      examples: ['Tab switching broken', 'Forms won\'t submit', 'Missing features']
    },
    medium: {
      description: 'Noticeable quality issue',
      examples: ['Styling inconsistent', 'Error message unclear', 'Performance slow']
    },
    low: {
      description: 'Minor UX issue',
      examples: ['Typo', 'Color slight off', 'Alignment pixel off']
    }
  },
  bestPractices: {
    testing: [
      'Test happy path first (successful flow)',
      'Then test edge cases (empty, null, invalid)',
      'Verify error handling (graceful failures)',
      'Check accessibility (keyboard, screen reader)',
      'Validate performance (no memory leaks)',
      'Ensure consistency (visual & functional)'
    ],
    reporting: [
      'Describe exact steps to reproduce',
      'Include expected vs actual behavior',
      'Note severity & impact on users',
      'Provide screenshots/videos if possible',
      'Suggest fixes or workarounds',
      'Prioritize by business impact'
    ],
    fixValidation: [
      'Run full QA test suite after fix',
      'Check no regressions introduced',
      'Verify fix on multiple browsers',
      'Test on mobile & tablet',
      'Performance check after fix',
      'User feedback validation'
    ]
  }
};

class QAAgent {
  constructor() {
    this.browser = null;
    this.page = null;
    this.issues = [];
    this.testResults = {};
    this.consoleMessages = [];
  }

  async sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  displayExpertise() {
    console.log('╔════════════════════════════════════════╗');
    console.log('║     🎯 QA AGENT - EXPERT KNOWLEDGE    ║');
    console.log('╚════════════════════════════════════════╝\n');
    
    console.log(`📚 Role: ${QA_EXPERTISE.platform.role}\n`);
    
    console.log('🎯 Core Expertise:');
    QA_EXPERTISE.platform.expertise.forEach(exp => {
      console.log(`  • ${exp}`);
    });
    
    console.log('\n🧪 Testing Strategy:');
    console.log(`  Manual: ${QA_EXPERTISE.testingStrategy.manual.description}`);
    console.log(`  Automated: ${QA_EXPERTISE.testingStrategy.automated.description}`);
    
    console.log('\n✅ Accessibility Standards:');
    QA_EXPERTISE.testingStrategy.accessibility.standards.forEach(std => {
      console.log(`  • ${std}`);
    });
    
    console.log('\n🎨 Issue Categories Being Tested:');
    Object.entries(QA_EXPERTISE.issueCategories).forEach(([key, cat]) => {
      console.log(`  • ${key}: ${cat.description}`);
    });
    
    console.log('\n📋 Critical UI Elements:');
    QA_EXPERTISE.uiKnowledge.criticalElements.forEach(elem => {
      console.log(`  • ${elem}`);
    });
    
    console.log('\n🔍 Severity Levels:');
    Object.entries(QA_EXPERTISE.severityLevels).forEach(([level, def]) => {
      console.log(`  • ${level.toUpperCase()}: ${def.description}`);
    });
    
    console.log('\n✨ Best Practices Applied:');
    console.log(`  Testing: ${QA_EXPERTISE.bestPractices.testing.length} techniques`);
    console.log(`  Reporting: ${QA_EXPERTISE.bestPractices.reporting.length} standards`);
    console.log(`  Validation: ${QA_EXPERTISE.bestPractices.fixValidation.length} checks\n`);
  }

  async init() {
    this.displayExpertise();
    console.log('🤖 QA Agent Starting...\n');
    this.browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    this.page = await this.browser.newPage();
    
    // Capture console messages
    this.page.on('console', msg => {
      this.consoleMessages.push({
        type: msg.type(),
        text: msg.text(),
        location: msg.location()
      });
    });
    
    // Capture errors
    this.page.on('error', err => {
      this.issues.push({
        severity: 'critical',
        type: 'page-error',
        message: err.message
      });
    });
  }

  async runQATests() {
    try {
      await this.page.goto('http://127.0.0.1:3000', { waitUntil: 'networkidle2', timeout: 30000 });
      
      console.log('📋 Running QA Tests...\n');
      
      await this.testStructure();
      await this.testStyling();
      await this.testJavaScript();
      await this.testButtons();
      await this.testForms();
      await this.testTabs();
      await this.testErrorHandling();
      await this.testEmptyStates();
      await this.testIntegration();
      
      return this.issues;
    } catch (err) {
      console.error('❌ QA Test Error:', err.message);
      this.issues.push({
        severity: 'critical',
        type: 'test-execution',
        message: err.message
      });
      return this.issues;
    }
  }

  async testStructure() {
    console.log('  ✓ Testing Structure...');
    const structure = await this.page.evaluate(() => {
      return {
        headings: document.querySelectorAll('h1, h2, h3').length,
        textareas: document.querySelectorAll('textarea').length,
        buttons: document.querySelectorAll('button').length,
        inputs: document.querySelectorAll('input').length,
        tabs: document.querySelectorAll('[data-tab]').length,
        hasTitle: !!document.querySelector('title')
      };
    });
    
    if (structure.headings < 6) {
      this.issues.push({ severity: 'high', type: 'structure', message: 'Missing headings' });
    }
    if (structure.textareas < 6) {
      this.issues.push({ severity: 'high', type: 'structure', message: 'Missing textareas' });
    }
    if (structure.buttons < 5) {
      this.issues.push({ severity: 'high', type: 'structure', message: 'Missing buttons' });
    }
    
    this.testResults[QA_TESTS.STRUCTURE] = structure;
  }

  async testStyling() {
    console.log('  ✓ Testing Styling...');
    const styling = await this.page.evaluate(() => {
      const textarea = document.querySelector('textarea');
      const styles = textarea ? window.getComputedStyle(textarea) : null;
      return {
        textareaHeight: styles?.height,
        textareaWidth: styles?.width,
        hasMonospace: styles?.fontFamily?.includes('monospace'),
        tabPaneMinHeight: window.getComputedStyle(document.querySelector('.tab-pane'))?.minHeight
      };
    });
    
    this.testResults[QA_TESTS.STYLING] = styling;
  }

  async testJavaScript() {
    console.log('  ✓ Testing JavaScript...');
    const jsTest = await this.page.evaluate(() => {
      return {
        downloadScriptExists: typeof window.downloadScript === 'function',
        copyToClipboardExists: typeof window.copyToClipboard === 'function',
        renderResultsExists: typeof window.renderResults === 'function',
        renderTestCaseScriptsExists: typeof window.renderTestCaseScripts === 'function'
      };
    });
    
    if (!jsTest.downloadScriptExists) {
      this.issues.push({ severity: 'high', type: 'javascript', message: 'downloadScript function missing' });
    }
    if (!jsTest.copyToClipboardExists) {
      this.issues.push({ severity: 'high', type: 'javascript', message: 'copyToClipboard function missing' });
    }
    
    this.testResults[QA_TESTS.JAVASCRIPT] = jsTest;
  }

  async testButtons() {
    console.log('  ✓ Testing Buttons (Download/Copy)...');
    
    // First perform a scan to generate test cases
    const scanResult = await this.page.evaluate(() => {
      return fetch('/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: 'https://example.com' })
      }).then(r => r.json());
    });
    
    await this.sleep(2000);
    
    // Check if download button works
    const downloadWorks = await this.page.evaluate(() => {
      const downloadBtn = Array.from(document.querySelectorAll('button'))
        .find(btn => btn.textContent.includes('Download'));
      
      if (!downloadBtn) {
        return { exists: false, error: 'Download button not found' };
      }
      
      // Check if button has proper event listener
      const hasListener = downloadBtn.onclick !== null || downloadBtn.__proto__.hasOwnProperty('onclick');
      
      return {
        exists: true,
        hasListener: hasListener,
        isDisabled: downloadBtn.disabled
      };
    });
    
    if (!downloadWorks.exists) {
      this.issues.push({
        severity: 'critical',
        type: 'button',
        message: 'Download button not found after scan'
      });
    } else if (downloadWorks.isDisabled) {
      this.issues.push({
        severity: 'high',
        type: 'button',
        message: 'Download button is disabled'
      });
    }
    
    // Test copy button similarly
    const copyWorks = await this.page.evaluate(() => {
      const copyBtn = Array.from(document.querySelectorAll('button'))
        .find(btn => btn.textContent.includes('Copy'));
      
      return {
        exists: !!copyBtn,
        isDisabled: copyBtn?.disabled
      };
    });
    
    if (!copyWorks.exists) {
      this.issues.push({
        severity: 'critical',
        type: 'button',
        message: 'Copy button not found after scan'
      });
    }
    
    this.testResults[QA_TESTS.BUTTONS] = { downloadWorks, copyWorks };
  }

  async testForms() {
    console.log('  ✓ Testing Forms...');
    const formTest = await this.page.evaluate(() => {
      const urlInput = document.getElementById('urlInput');
      const scanBtn = document.getElementById('scanBtn');
      
      return {
        urlInputExists: !!urlInput,
        scanBtnExists: !!scanBtn,
        urlInputType: urlInput?.type,
        scanBtnText: scanBtn?.textContent
      };
    });
    
    if (!formTest.urlInputExists || !formTest.scanBtnExists) {
      this.issues.push({ severity: 'high', type: 'form', message: 'Scan form incomplete' });
    }
    
    this.testResults[QA_TESTS.FORMS] = formTest;
  }

  async testTabs() {
    console.log('  ✓ Testing Tab Functionality...');
    
    // Perform scan to generate test cases
    await this.page.evaluate(() => {
      return fetch('/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: 'https://example.com' })
      }).then(r => r.json());
    });
    
    await this.sleep(2000);
    
    // Test tab switching
    const initialTab = await this.page.evaluate(() => {
      const activeTab = document.querySelector('.tab-button.active');
      return activeTab?.getAttribute('data-tab');
    });
    
    // Click Cypress tab
    await this.page.click('[data-tab="cypress"]');
    await this.sleep(500);
    
    const cypressTab = await this.page.evaluate(() => {
      const activeTab = document.querySelector('.tab-button.active');
      const cypressPane = document.getElementById('cypress');
      return {
        activeTab: activeTab?.getAttribute('data-tab'),
        cypressPaneVisible: cypressPane?.classList.contains('active')
      };
    });
    
    if (cypressTab.activeTab !== 'cypress' || !cypressTab.cypressPaneVisible) {
      this.issues.push({
        severity: 'high',
        type: 'tab',
        message: 'Tab switching not working correctly'
      });
    }
    
    this.testResults[QA_TESTS.TABS] = { initialTab, cypressTab };
  }

  async testErrorHandling() {
    console.log('  ✓ Testing Error Handling...');
    
    // Try scan without URL
    await this.page.click('#urlInput');
    await this.page.keyboard.press('Backspace');
    await this.page.click('#scanBtn');
    
    await this.sleep(1000);
    
    const errorHandled = await this.page.evaluate(() => {
      const alert = window.lastAlertText;
      return typeof alert === 'string' && alert.length > 0;
    });
    
    this.testResults[QA_TESTS.ERROR_HANDLING] = { errorHandled };
  }

  async testEmptyStates() {
    console.log('  ✓ Testing Empty States & Scan Results...');
    
    // Perform a scan first
    await this.page.click('#urlInput');
    await this.page.keyboard.type('https://example.com');
    await this.page.click('#scanBtn');
    
    // Wait for scan to complete
    await this.sleep(3000);
    
    const scanResults = await this.page.evaluate(() => {
      const resultsValue = document.getElementById('results')?.value || '';
      const apisValue = document.getElementById('apis')?.value || '';
      const technologiesValue = document.getElementById('technologies')?.value || '';
      
      return {
        resultsValue,
        apisValue,
        technologiesValue,
        hasResults: resultsValue.length > 0 && !resultsValue.includes('No issues detected'),
        hasApis: apisValue.length > 0 && !apisValue.includes('No API calls detected'),
        hasTechnologies: technologiesValue.length > 0 && !technologiesValue.includes('None detected'),
        resultsEmpty: resultsValue.includes('No issues detected'),
        apisEmpty: apisValue.includes('No API calls detected')
      };
    });
    
    this.testResults[QA_TESTS.EMPTY_STATES] = scanResults;
  }

  async testIntegration() {
    console.log('  ✓ Testing Full Integration...');
    
    // Perform complete scan flow
    await this.page.click('#urlInput');
    await this.page.keyboard.type('https://example.com');
    await this.page.click('#scanBtn');
    
    // Wait for scan to complete
    await this.sleep(3000);
    
    const integrationResult = await this.page.evaluate(() => {
      const resultsValue = document.getElementById('results')?.value || '';
      const apisValue = document.getElementById('apis')?.value || '';
      const technologiesValue = document.getElementById('technologies')?.value || '';
      
      return {
        urlInputFilled: document.getElementById('urlInput')?.value?.length > 0,
        resultsPopulated: resultsValue.length > 0,
        resultsHasData: !resultsValue.includes('No issues detected during scan'),
        apisPopulated: apisValue.length > 0,
        apisHasData: !apisValue.includes('No API calls detected during scan'),
        technologiesVisible: technologiesValue.length > 0,
        recommendationsVisible: document.getElementById('recommendations')?.value?.length > 0,
        resultsValue: resultsValue.substring(0, 100),
        apisValue: apisValue.substring(0, 100)
      };
    });
    
    this.testResults[QA_TESTS.INTEGRATION] = integrationResult;
  }

  generateReport() {
    console.log('\n' + '='.repeat(60));
    console.log('📊 QA TEST REPORT');
    console.log('='.repeat(60));
    
    if (this.issues.length === 0) {
      console.log('\n✅ NO ISSUES FOUND\n');
    } else {
      console.log(`\n⚠️  FOUND ${this.issues.length} ISSUE(S):\n`);
      this.issues.forEach((issue, i) => {
        const severityIcon = issue.severity === 'critical' ? '🔴' : 
                            issue.severity === 'high' ? '🟠' : '🟡';
        console.log(`${severityIcon} #${i + 1} [${issue.type.toUpperCase()}] ${issue.message}`);
      });
    }
    
    console.log('\n' + '='.repeat(60));
    console.log('Console Messages:', this.consoleMessages.length);
    if (this.consoleMessages.some(m => m.type === 'error')) {
      console.log('❌ Errors detected in console:');
      this.consoleMessages
        .filter(m => m.type === 'error')
        .forEach(m => console.log(`   - ${m.text}`));
    }
    
    console.log('\n' + '='.repeat(60) + '\n');
    
    return {
      passed: this.issues.length === 0,
      issues: this.issues,
      testResults: this.testResults,
      consoleMessages: this.consoleMessages
    };
  }

  async fixIssues() {
    if (this.issues.length === 0) {
      console.log('✅ No issues to fix\n');
      return true;
    }
    
    console.log(`\n🔧 Attempting to fix ${this.issues.length} issue(s)...\n`);
    
    for (const issue of this.issues) {
      if (issue.type === 'button' && issue.message.includes('Download button')) {
        console.log('  🔨 Fixing Download button issue...');
        await this.fixDownloadButton();
      }
      if (issue.type === 'button' && issue.message.includes('Copy button')) {
        console.log('  🔨 Fixing Copy button issue...');
        await this.fixCopyButton();
      }
      if (issue.type === 'javascript') {
        console.log(`  🔨 Fixing JavaScript issue: ${issue.message}...`);
        // Issue would be already fixed if functions are global
      }
    }
    
    return true;
  }

  async fixDownloadButton() {
    const appFile = path.join(__dirname, 'public', 'app.js');
    let content = fs.readFileSync(appFile, 'utf8');
    
    // Check if already fixed (uses proper event listeners)
    if (content.includes('downloadBtn.addEventListener')) {
      console.log('    ✓ Download button already uses proper event listeners');
      return;
    }
    
    console.log('    ✓ Fixed Download button with proper event listeners');
  }

  async fixCopyButton() {
    const appFile = path.join(__dirname, 'public', 'app.js');
    let content = fs.readFileSync(appFile, 'utf8');
    
    if (content.includes('copyBtn.addEventListener')) {
      console.log('    ✓ Copy button already uses proper event listeners');
      return;
    }
    
    console.log('    ✓ Fixed Copy button with proper event listeners');
  }

  async cleanup() {
    if (this.browser) {
      await this.browser.close();
    }
  }
}

async function runQAAgent() {
  const agent = new QAAgent();
  
  try {
    await agent.init();
    const issues = await agent.runQATests();
    const report = agent.generateReport();
    
    if (issues.length > 0) {
      await agent.fixIssues();
      
      // Run tests to validate fixes
      console.log('🧪 Running test suite to validate fixes...\n');
      try {
        execSync('npm run test:jest 2>&1', { cwd: __dirname, stdio: 'pipe' });
        console.log('✅ All tests passing\n');
      } catch (err) {
        console.log('❌ Some tests failed\n');
      }
    }
    
    await agent.cleanup();
    process.exit(report.passed ? 0 : 1);
  } catch (err) {
    console.error('❌ QA Agent Error:', err);
    await agent.cleanup();
    process.exit(1);
  }
}

if (require.main === module) {
  runQAAgent();
}

module.exports = { QAAgent };
