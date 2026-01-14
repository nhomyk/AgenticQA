#!/usr/bin/env node

/**
 * Pa11y & Security Compliance Scanner
 * Automated accessibility and security scanning with remediation suggestions
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

class ComplianceScanner {
  constructor() {
    this.violations = [];
    this.vulnerabilities = [];
    this.reports = {
      pa11y: null,
      audit: null
    };
  }

  /**
   * Run Pa11y accessibility scan
   */
  runPa11yScan() {
    console.log('♿ Running Pa11y accessibility scan...\n');
    
    try {
      // Start server if not running
      this.ensureServerRunning();
      
      execSync('npm run test:pa11y', { stdio: 'inherit' });
      console.log('\n✅ Accessibility scan passed!\n');
      return { status: 'passed', violations: 0 };
    } catch (error) {
      console.log('\n⚠️  Accessibility issues detected\n');
      return { status: 'failed', violations: this.countViolations() };
    }
  }

  /**
   * Run npm audit security scan
   */
  runSecurityScan() {
    console.log('🔐 Running npm audit security scan...\n');
    
    try {
      execSync('npm audit --audit-level=moderate', { stdio: 'inherit' });
      console.log('\n✅ Security scan passed!\n');
      return { status: 'passed', vulnerabilities: 0 };
    } catch (error) {
      // Generate JSON report for parsing
      try {
        execSync('npm audit --json > .audit-report.json 2>/dev/null', { stdio: 'pipe' });
        const report = JSON.parse(fs.readFileSync('.audit-report.json', 'utf-8'));
        const vulnCount = Object.keys(report.vulnerabilities || {}).length;
        
        console.log(`\n⚠️  Found ${vulnCount} vulnerability/vulnerabilities\n`);
        
        // Clean up
        fs.unlinkSync('.audit-report.json');
        
        return { status: 'failed', vulnerabilities: vulnCount };
      } catch (parseError) {
        return { status: 'failed', vulnerabilities: 1 };
      }
    }
  }

  /**
   * Ensure development server is running
   */
  ensureServerRunning() {
    try {
      execSync('curl -s http://localhost:3000 > /dev/null', { stdio: 'pipe' });
    } catch (error) {
      console.log('Starting development server...');
      require('child_process').spawn('npm', ['start'], {
        detached: true,
        stdio: 'ignore'
      });
      
      // Wait for server to start
      let retries = 0;
      while (retries < 10) {
        try {
          execSync('curl -s http://localhost:3000 > /dev/null', { stdio: 'pipe' });
          break;
        } catch (e) {
          retries++;
          if (retries === 10) throw new Error('Server failed to start');
        }
      }
    }
  }

  /**
   * Count violations from Pa11y report
   */
  countViolations() {
    try {
      if (fs.existsSync('pa11y-report.json')) {
        const report = JSON.parse(fs.readFileSync('pa11y-report.json', 'utf-8'));
        return report.issues?.length || 0;
      }
    } catch (error) {
      console.error('Could not parse Pa11y report:', error.message);
    }
    return 1;
  }

  /**
   * Display accessibility remediation guide
   */
  displayA11yRemediations() {
    console.log('\n🛠️  Common Accessibility Issues & Fixes:\n');
    console.log('=========================================\n');
    
    const remediations = [
      {
        issue: 'Missing alt text on images',
        fix: 'Add alt attribute: <img alt="description" src="..." />'
      },
      {
        issue: 'Poor color contrast',
        fix: 'Ensure contrast ratio ≥ 4.5:1. Use WebAIM Contrast Checker'
      },
      {
        issue: 'Form labels not associated',
        fix: 'Use <label for="inputId">Label</label> or wrap input'
      },
      {
        issue: 'Missing heading hierarchy',
        fix: 'Use h1 → h2 → h3 in order. One h1 per page'
      },
      {
        issue: 'Keyboard not usable',
        fix: 'Test Tab key navigation. Ensure focus indicators visible'
      },
      {
        issue: 'Missing ARIA labels',
        fix: 'Add aria-label or aria-describedby for screen readers'
      },
      {
        issue: 'No focus visible indicator',
        fix: 'CSS: outline: 2px solid #blue; outline-offset: 2px;'
      }
    ];
    
    remediations.forEach((r, i) => {
      console.log(`${i + 1}. ${r.issue}`);
      console.log(`   Fix: ${r.fix}\n`);
    });
  }

  /**
   * Display security remediation guide
   */
  displaySecurityRemediations() {
    console.log('\n🔒 Security Remediation Steps:\n');
    console.log('============================\n');
    
    console.log('1. Review npm audit report:');
    console.log('   npm audit --json\n');
    
    console.log('2. Attempt automatic fixes:');
    console.log('   npm audit fix\n');
    
    console.log('3. Update specific package:');
    console.log('   npm install package@latest\n');
    
    console.log('4. Review package changelog:');
    console.log('   npm view package changelog\n');
    
    console.log('5. Test after updates:');
    console.log('   npm test\n');
  }

  /**
   * Generate compliance report
   */
  generateReport(pa11yResult, securityResult) {
    const timestamp = new Date().toISOString();
    const allPassed = pa11yResult.status === 'passed' && securityResult.status === 'passed';
    
    const report = {
      timestamp,
      accessibility: {
        status: pa11yResult.status,
        violations: pa11yResult.violations,
        url: 'http://localhost:3000'
      },
      security: {
        status: securityResult.status,
        vulnerabilities: securityResult.vulnerabilities
      },
      overall: {
        passed: allPassed,
        timestamp
      }
    };
    
    // Save report
    const reportPath = './compliance-scan-report.json';
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
    
    console.log(`\n📋 Report saved to: ${reportPath}\n`);
    
    return report;
  }

  /**
   * Run full compliance scan
   */
  run() {
    console.log('\n🔍 Starting Compliance & Security Scan\n');
    console.log('='.repeat(50) + '\n');
    
    const pa11yResult = this.runPa11yScan();
    const securityResult = this.runSecurityScan();
    
    // Display results summary
    console.log('📊 Scan Results:\n');
    console.log('='.repeat(50) + '\n');
    
    if (pa11yResult.status === 'passed') {
      console.log('✅ Accessibility: PASSED\n');
    } else {
      console.log(`❌ Accessibility: ${pa11yResult.violations} violation(s)\n`);
      this.displayA11yRemediations();
    }
    
    if (securityResult.status === 'passed') {
      console.log('✅ Security: PASSED\n');
    } else {
      console.log(`❌ Security: ${securityResult.vulnerabilities} vulnerability/vulnerabilities\n`);
      this.displaySecurityRemediations();
    }
    
    // Generate report
    this.generateReport(pa11yResult, securityResult);
    
    // Exit with appropriate code
    const allPassed = pa11yResult.status === 'passed' && securityResult.status === 'passed';
    process.exitCode = allPassed ? 0 : 1;
  }
}

// Run scanner
if (require.main === module) {
  const scanner = new ComplianceScanner();
  scanner.run().catch(error => {
    console.error('Compliance scan error:', error.message);
    process.exitCode = 1;
  });
}

module.exports = ComplianceScanner;
