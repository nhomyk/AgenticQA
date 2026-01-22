#!/usr/bin/env node

/**
 * Agent Report Processor
 * 
 * Enables agents to:
 * 1. Scan and parse reports from pipeline tools (compliance, security, linting, testing)
 * 2. Extract actionable findings (issues, bugs, vulnerabilities)
 * 3. Organize findings by priority and category
 * 4. Generate fix recommendations based on findings
 * 5. Track which issues have been fixed
 * 
 * Usage:
 *   const reportProcessor = new AgentReportProcessor();
 *   const findings = reportProcessor.scanAllReports();
 *   findings.forEach(finding => {
 *     const fix = reportProcessor.generateFix(finding);
 *     // Apply fix to codebase
 *   });
 */

const fs = require('fs');
const path = require('path');

class AgentReportProcessor {
  constructor() {
    this.findings = [];
    this.processedReports = new Set();
    this.reportLocations = {
      compliance: 'compliance-audit-report.md',
      pa11y: 'pa11y-report.json',
      audit: 'audit-report.json',
      semgrep: 'semgrep-report.json',
      trivy: 'trivy-report.json',
      testFailures: 'test-failures/',
      coverage: 'coverage/',
      eslint: '.eslintrc.json'
    };
  }

  /**
   * Scan all available reports and extract findings
   * @returns {Array} Array of findings with priority, category, and fix recommendations
   */
  scanAllReports() {
    console.log('\n📋 === SCANNING PIPELINE REPORTS ===\n');
    
    this.findings = [];

    // Scan each report type
    this.scanComplianceReport();
    this.scanAccessibilityReport();
    this.scanSecurityReport();
    this.scanTestFailures();
    this.scanCodeCoverage();
    this.scanSemgrepReport();
    this.scanTrivyReport();

    // Sort by priority
    this.findings.sort((a, b) => {
      const priorityMap = { critical: 0, high: 1, medium: 2, low: 3 };
      return (priorityMap[a.priority] || 4) - (priorityMap[b.priority] || 4);
    });

    console.log(`\n✅ Scan complete. Found ${this.findings.length} actionable findings.\n`);
    this.printFindingsSummary();

    return this.findings;
  }

  /**
   * Scan compliance audit report
   */
  scanComplianceReport() {
    const reportPath = this.reportLocations.compliance;
    
    if (!fs.existsSync(reportPath)) {
      return;
    }

    console.log('🛡️  Scanning compliance report...');
    const content = fs.readFileSync(reportPath, 'utf8');

    // Extract critical issues
    const criticalSection = this.extractSection(content, '## 🔴 Critical Issues');
    if (criticalSection) {
      const issues = this.parseIssueSection(criticalSection, 'critical');
      this.findings.push(...issues);
    }

    // Extract high priority issues
    const highSection = this.extractSection(content, '## 🟠 High Priority');
    if (highSection) {
      const issues = this.parseIssueSection(highSection, 'high');
      this.findings.push(...issues);
    }

    // Extract medium priority issues
    const mediumSection = this.extractSection(content, '## 🟡 Medium Priority');
    if (mediumSection) {
      const issues = this.parseIssueSection(mediumSection, 'medium');
      this.findings.push(...issues);
    }

    // Extract low priority issues
    const lowSection = this.extractSection(content, '## 🔵 Low Priority');
    if (lowSection) {
      const issues = this.parseIssueSection(lowSection, 'low');
      this.findings.push(...issues);
    }

    console.log(`  ✓ Found ${this.findings.filter(f => f.source === 'compliance').length} compliance findings`);
  }

  /**
   * Scan accessibility report (Pa11y)
   */
  scanAccessibilityReport() {
    const reportPath = this.reportLocations.pa11y;
    
    if (!fs.existsSync(reportPath)) {
      return;
    }

    try {
      console.log('♿ Scanning accessibility report...');
      const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
      
      const errors = report.issues?.filter(i => i.type === 'error') || [];
      const warnings = report.issues?.filter(i => i.type === 'warning') || [];

      errors.forEach(issue => {
        this.findings.push({
          id: `a11y-${issue.code}`,
          priority: 'high',
          category: 'accessibility',
          source: 'pa11y',
          type: 'accessibility-violation',
          code: issue.code,
          message: issue.message,
          element: issue.selector,
          recommendation: this.getA11yFix(issue.code),
          file: null
        });
      });

      warnings.forEach(issue => {
        this.findings.push({
          id: `a11y-${issue.code}`,
          priority: 'medium',
          category: 'accessibility',
          source: 'pa11y',
          type: 'accessibility-warning',
          code: issue.code,
          message: issue.message,
          element: issue.selector,
          recommendation: this.getA11yFix(issue.code),
          file: null
        });
      });

      console.log(`  ✓ Found ${errors.length} critical a11y issues, ${warnings.length} warnings`);
    } catch (err) {
      console.log(`  ⚠️  Could not parse Pa11y report: ${err.message}`);
    }
  }

  /**
   * Scan security audit report
   */
  scanSecurityReport() {
    const reportPath = this.reportLocations.audit;
    
    if (!fs.existsSync(reportPath)) {
      return;
    }

    try {
      console.log('🔒 Scanning security report...');
      const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
      
      const vulnerabilities = report.vulnerabilities || {};
      let criticalCount = 0;
      let highCount = 0;

      Object.entries(vulnerabilities).forEach(([pkg, vuln]) => {
        const severity = vuln.severity || 'medium';
        const priority = severity === 'critical' ? 'critical' : severity === 'high' ? 'high' : 'medium';
        
        if (priority === 'critical') criticalCount++;
        if (priority === 'high') highCount++;

        this.findings.push({
          id: `sec-${pkg}-${vuln.via[0]?.source || 'unknown'}`,
          priority: priority,
          category: 'security',
          source: 'npm-audit',
          type: 'vulnerability',
          package: pkg,
          vulnerability: vuln.via[0]?.title || 'Unknown vulnerability',
          severity: severity,
          recommendation: `Run 'npm update ${pkg}' to patch ${pkg} to version ${vuln.fixed_in || 'latest'}`,
          file: null
        });
      });

      console.log(`  ✓ Found ${criticalCount} critical, ${highCount} high severity vulnerabilities`);
    } catch (err) {
      console.log(`  ⚠️  Could not parse security report: ${err.message}`);
    }
  }

  /**
   * Scan test failures
   */
  scanTestFailures() {
    const failureDir = this.reportLocations.testFailures;
    
    if (!fs.existsSync(failureDir)) {
      return;
    }

    try {
      console.log('🧪 Scanning test failures...');
      
      const files = fs.readdirSync(failureDir);
      let totalFailures = 0;

      files.forEach(file => {
        if (file === 'summary.txt') {
          const summary = fs.readFileSync(path.join(failureDir, file), 'utf8');
          const failedFrameworks = summary.split('\n').filter(l => l.includes('_FAILED'));
          
          failedFrameworks.forEach(line => {
            const framework = line.split('=')[0].replace('_FAILED', '');
            this.findings.push({
              id: `test-${framework.toLowerCase()}`,
              priority: 'high',
              category: 'testing',
              source: 'test-failures',
              type: 'test-failure',
              framework: framework,
              message: `${framework} tests failed`,
              recommendation: `Review and fix ${framework} test failures. See test-failures/${framework.toLowerCase()}-errors.txt`,
              file: `test-failures/${framework.toLowerCase()}-errors.txt`
            });
            totalFailures++;
          });
        }
      });

      console.log(`  ✓ Found ${totalFailures} test framework failures`);
    } catch (err) {
      console.log(`  ⚠️  Could not scan test failures: ${err.message}`);
    }
  }

  /**
   * Scan code coverage reports
   */
  scanCodeCoverage() {
    const coverageDir = this.reportLocations.coverage;
    
    if (!fs.existsSync(coverageDir)) {
      return;
    }

    try {
      console.log('📊 Scanning code coverage...');
      
      const coverageSummaryPath = path.join(coverageDir, 'coverage-summary.json');
      if (fs.existsSync(coverageSummaryPath)) {
        const summary = JSON.parse(fs.readFileSync(coverageSummaryPath, 'utf8'));
        
        // Find files with low coverage
        Object.entries(summary).forEach(([file, coverage]) => {
          if (file === 'total') return;
          
          const linesCovered = coverage.lines.pct;
          if (linesCovered < 80) {
            this.findings.push({
              id: `coverage-${file}`,
              priority: linesCovered < 50 ? 'high' : 'medium',
              category: 'testing',
              source: 'coverage',
              type: 'low-coverage',
              file: file,
              coverage: linesCovered,
              message: `${file} has ${linesCovered}% line coverage`,
              recommendation: `Add tests to increase coverage of ${file} above 80%`,
              uncoveredLines: this.findUncoveredLines(file)
            });
          }
        });

        console.log(`  ✓ Scanned code coverage metrics`);
      }
    } catch (err) {
      console.log(`  ⚠️  Could not scan coverage: ${err.message}`);
    }
  }

  /**
   * Scan Semgrep report for code quality issues
   */
  scanSemgrepReport() {
    const reportPath = this.reportLocations.semgrep;
    
    if (!fs.existsSync(reportPath)) {
      return;
    }

    try {
      console.log('🔍 Scanning Semgrep code quality report...');
      const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
      
      const results = report.results || [];
      const errors = results.filter(r => r.severity === 'ERROR');
      const warnings = results.filter(r => r.severity === 'WARNING');

      errors.forEach(issue => {
        this.findings.push({
          id: `semgrep-${issue.check_id}`,
          priority: 'high',
          category: 'code-quality',
          source: 'semgrep',
          type: 'code-quality-error',
          checkId: issue.check_id,
          message: issue.extra?.message || issue.message,
          file: issue.path,
          line: issue.start?.line,
          recommendation: this.getSemgrepFix(issue.check_id),
          severity: 'error'
        });
      });

      warnings.forEach(issue => {
        this.findings.push({
          id: `semgrep-${issue.check_id}`,
          priority: 'medium',
          category: 'code-quality',
          source: 'semgrep',
          type: 'code-quality-warning',
          checkId: issue.check_id,
          message: issue.extra?.message || issue.message,
          file: issue.path,
          line: issue.start?.line,
          recommendation: this.getSemgrepFix(issue.check_id),
          severity: 'warning'
        });
      });

      console.log(`  ✓ Found ${errors.length} errors, ${warnings.length} warnings in code quality checks`);
    } catch (err) {
      console.log(`  ⚠️  Could not parse Semgrep report: ${err.message}`);
    }
  }

  /**
   * Scan Trivy report for container vulnerabilities
   */
  scanTrivyReport() {
    const reportPath = this.reportLocations.trivy;
    
    if (!fs.existsSync(reportPath)) {
      return;
    }

    try {
      console.log('🐳 Scanning Trivy container report...');
      const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
      
      const results = report.Results || [];
      let vulnCount = 0;

      results.forEach(result => {
        const vulnerabilities = result.Vulnerabilities || [];
        vulnerabilities.forEach(vuln => {
          const priority = vuln.Severity === 'CRITICAL' ? 'critical' : 
                          vuln.Severity === 'HIGH' ? 'high' : 'medium';
          
          this.findings.push({
            id: `trivy-${vuln.VulnerabilityID}`,
            priority: priority,
            category: 'container-security',
            source: 'trivy',
            type: 'container-vulnerability',
            vulnerabilityId: vuln.VulnerabilityID,
            message: vuln.Title,
            severity: vuln.Severity,
            description: vuln.Description,
            fixedVersion: vuln.FixedVersion,
            recommendation: `Update ${result.Target} to use a patched version`,
            file: result.Target
          });
          vulnCount++;
        });
      });

      console.log(`  ✓ Found ${vulnCount} container vulnerabilities`);
    } catch (err) {
      console.log(`  ⚠️  Could not parse Trivy report: ${err.message}`);
    }
  }

  /**
   * Extract section from markdown report
   */
  extractSection(content, sectionHeader) {
    const regex = new RegExp(`${sectionHeader}[\\s\\S]*?(?=##|$)`, 'i');
    const match = content.match(regex);
    return match ? match[0] : null;
  }

  /**
   * Parse issue section from compliance report
   */
  parseIssueSection(section, priority) {
    const issues = [];
    const issuePattern = /### \d+\.\s+(.+?)\n.*?- \*\*Message:\*\*\s+(.+?)\n.*?- \*\*Recommendation:\*\*\s+(.+?)(?=\n###|\n$)/gs;
    
    let match;
    while ((match = issuePattern.exec(section)) !== null) {
      issues.push({
        id: `compliance-${issues.length}`,
        priority: priority,
        category: 'compliance',
        source: 'compliance',
        type: 'compliance-issue',
        check: match[1].trim(),
        message: match[2].trim(),
        recommendation: match[3].trim(),
        file: null
      });
    }

    return issues;
  }

  /**
   * Get accessibility fix recommendation
   */
  getA11yFix(code) {
    const fixes = {
      'WCAG2AA.Principle1.Guideline1_1.1_1_1_H30.app.AriaImg': 'Add aria-label to image elements',
      'WCAG2AA.Principle1.Guideline1_3.1_3_1.H65': 'Add label elements for form inputs',
      'WCAG2AA.Principle2.Guideline2_4.2_4_3.H25.1.NoHeadTag': 'Add H1 heading to page',
      'WCAG2AA.Principle1.Guideline1_1.1_1_1_H36': 'Add alt text to image elements',
      'WCAG2AA.Principle4.Guideline4_1.4_1_2.H91.A.Empty': 'Add meaningful link text',
      'WCAG2AA.Principle1.Guideline1_3.1_3_1.H44': 'Associate form inputs with labels'
    };
    return fixes[code] || `Fix accessibility issue ${code}`;
  }

  /**
   * Get Semgrep fix recommendation
   */
  getSemgrepFix(checkId) {
    const fixes = {
      'owasp-a01:hardcoded-sql-string': 'Use parameterized queries instead of string concatenation',
      'owasp-a02:sql-injection': 'Use prepared statements to prevent SQL injection',
      'owasp-a03:xss': 'Sanitize user input before rendering in HTML',
      'owasp-a06:path-traversal': 'Validate file paths to prevent directory traversal',
      'owasp-a07:sensitive-data-exposure': 'Use HTTPS/TLS and encrypt sensitive data'
    };
    return fixes[checkId] || `Fix code quality issue ${checkId}`;
  }

  /**
   * Generate a complete fix for a finding
   * @param {Object} finding - The finding to fix
   * @returns {Object} Fix instructions
   */
  generateFix(finding) {
    const fixGenerator = {
      'compliance-issue': () => this.fixComplianceIssue(finding),
      'accessibility-violation': () => this.fixAccessibilityIssue(finding),
      'accessibility-warning': () => this.fixAccessibilityIssue(finding),
      'vulnerability': () => this.fixVulnerability(finding),
      'test-failure': () => this.fixTestFailure(finding),
      'low-coverage': () => this.fixCodeCoverage(finding),
      'code-quality-error': () => this.fixCodeQuality(finding),
      'code-quality-warning': () => this.fixCodeQuality(finding),
      'container-vulnerability': () => this.fixContainerVulnerability(finding)
    };

    const generator = fixGenerator[finding.type];
    if (generator) {
      return generator();
    }

    return {
      finding: finding,
      action: 'manual-review',
      steps: [
        'Manually review the finding',
        finding.recommendation
      ]
    };
  }

  /**
   * Fix compliance issue
   */
  fixComplianceIssue(finding) {
    return {
      finding: finding,
      action: 'compliance-fix',
      category: 'compliance',
      type: finding.check,
      steps: [
        finding.recommendation,
        'Verify the fix meets compliance requirements',
        'Run compliance-agent again to confirm resolution'
      ],
      affectedFiles: this.findAffectedFiles(finding.check)
    };
  }

  /**
   * Fix accessibility issue
   */
  fixAccessibilityIssue(finding) {
    return {
      finding: finding,
      action: 'accessibility-fix',
      category: 'accessibility',
      element: finding.element,
      steps: [
        finding.recommendation,
        `Update element: ${finding.element}`,
        'Run Pa11y scan again to confirm fix'
      ],
      file: this.inferFileFromElement(finding.element)
    };
  }

  /**
   * Fix security vulnerability
   */
  fixVulnerability(finding) {
    return {
      finding: finding,
      action: 'security-patch',
      category: 'security',
      package: finding.package,
      steps: [
        `Update package: npm update ${finding.package}`,
        'Run npm audit again to verify fix',
        'Commit dependency updates'
      ],
      command: `npm update ${finding.package}`
    };
  }

  /**
   * Fix test failure
   */
  fixTestFailure(finding) {
    return {
      finding: finding,
      action: 'test-fix',
      category: 'testing',
      framework: finding.framework,
      steps: [
        `Read error details: ${finding.file}`,
        `Fix ${finding.framework} tests based on error messages`,
        `Run: npm run test:${finding.framework.toLowerCase()}`,
        'Verify all tests pass'
      ],
      errorFile: finding.file
    };
  }

  /**
   * Fix low code coverage
   */
  fixCodeCoverage(finding) {
    return {
      finding: finding,
      action: 'add-tests',
      category: 'testing',
      file: finding.file,
      coverage: finding.coverage,
      steps: [
        `Identify untested code in ${finding.file}`,
        'Write new unit or integration tests',
        'Aim for >80% line coverage',
        'Run coverage report to verify improvement'
      ],
      uncoveredLines: finding.uncoveredLines
    };
  }

  /**
   * Fix code quality issues
   */
  fixCodeQuality(finding) {
    return {
      finding: finding,
      action: 'code-quality-fix',
      category: 'code-quality',
      file: finding.file,
      line: finding.line,
      steps: [
        `Review issue at ${finding.file}:${finding.line}`,
        finding.recommendation,
        'Apply fix to source code',
        'Run linting to verify fix'
      ],
      checkId: finding.checkId
    };
  }

  /**
   * Fix container vulnerability
   */
  fixContainerVulnerability(finding) {
    return {
      finding: finding,
      action: 'container-patch',
      category: 'container-security',
      vulnerabilityId: finding.vulnerabilityId,
      steps: [
        finding.recommendation,
        'Update Dockerfile or base image',
        'Run: docker build -t agentic-qa:latest .',
        'Run trivy scan again to verify'
      ],
      fixedVersion: finding.fixedVersion
    };
  }

  /**
   * Find affected files for a compliance check
   */
  findAffectedFiles(check) {
    const checkFileMap = {
      'GDPR': ['PRIVACY_POLICY.md'],
      'CCPA': ['PRIVACY_POLICY.md'],
      'Privacy': ['PRIVACY_POLICY.md'],
      'No privacy policy': ['PRIVACY_POLICY.md'],
      'No LICENSE': ['LICENSE'],
      'No security policy': ['SECURITY.md'],
      'No terms of service': ['TERMS_OF_SERVICE.md'],
      'HTTPS not configured': ['server.js'],
      'No rate limiting': ['server.js'],
      'Missing security headers': ['server.js']
    };

    for (const [pattern, files] of Object.entries(checkFileMap)) {
      if (check.includes(pattern)) {
        return files;
      }
    }

    return [];
  }

  /**
   * Infer which file contains the element
   */
  inferFileFromElement(selector) {
    // Try to find the selector in HTML files
    const htmlFiles = ['public/index.html', 'public/dashboard.html'];
    for (const file of htmlFiles) {
      if (fs.existsSync(file)) {
        const content = fs.readFileSync(file, 'utf8');
        if (content.includes(selector)) {
          return file;
        }
      }
    }
    return null;
  }

  /**
   * Find uncovered lines in a file
   */
  findUncoveredLines(file) {
    try {
      const coveragePath = path.join(this.reportLocations.coverage, `${file.replace(/\//g, '__')}.json`);
      if (fs.existsSync(coveragePath)) {
        const coverage = JSON.parse(fs.readFileSync(coveragePath, 'utf8'));
        const uncovered = [];
        
        if (coverage.l) {
          Object.entries(coverage.l).forEach(([line, count]) => {
            if (count === 0) {
              uncovered.push(parseInt(line));
            }
          });
        }
        
        return uncovered;
      }
    } catch (err) {
      // Silently fail if coverage details not found
    }
    return [];
  }

  /**
   * Print summary of findings
   */
  printFindingsSummary() {
    if (this.findings.length === 0) {
      console.log('✅ No findings - codebase is clean!\n');
      return;
    }

    console.log('📊 FINDINGS BY PRIORITY:\n');
    
    const byPriority = {
      critical: [],
      high: [],
      medium: [],
      low: []
    };

    this.findings.forEach(f => {
      if (byPriority[f.priority]) {
        byPriority[f.priority].push(f);
      }
    });

    if (byPriority.critical.length > 0) {
      console.log(`  🔴 CRITICAL (${byPriority.critical.length}):`);
      byPriority.critical.forEach(f => {
        console.log(`     • ${f.category}: ${(f.check || f.message || f.type).substring(0, 60)}`);
      });
      console.log('');
    }

    if (byPriority.high.length > 0) {
      console.log(`  🟠 HIGH (${byPriority.high.length}):`);
      byPriority.high.slice(0, 5).forEach(f => {
        console.log(`     • ${f.category}: ${(f.check || f.message || f.type).substring(0, 60)}`);
      });
      if (byPriority.high.length > 5) {
        console.log(`     ... and ${byPriority.high.length - 5} more`);
      }
      console.log('');
    }

    if (byPriority.medium.length > 0) {
      console.log(`  🟡 MEDIUM (${byPriority.medium.length}):`);
      byPriority.medium.slice(0, 3).forEach(f => {
        console.log(`     • ${f.category}: ${(f.check || f.message || f.type).substring(0, 60)}`);
      });
      if (byPriority.medium.length > 3) {
        console.log(`     ... and ${byPriority.medium.length - 3} more`);
      }
      console.log('');
    }
  }

  /**
   * Export findings for agent processing
   */
  exportFindings(format = 'json') {
    if (format === 'json') {
      return JSON.stringify(this.findings, null, 2);
    } else if (format === 'markdown') {
      return this.renderMarkdown();
    }
    return this.findings;
  }

  /**
   * Render findings as Markdown
   */
  renderMarkdown() {
    let md = '# Agent Findings Report\n\n';
    md += `Generated: ${new Date().toISOString()}\n`;
    md += `Total Findings: ${this.findings.length}\n\n`;

    const byCategory = {};
    this.findings.forEach(f => {
      if (!byCategory[f.category]) {
        byCategory[f.category] = [];
      }
      byCategory[f.category].push(f);
    });

    Object.entries(byCategory).forEach(([category, findings]) => {
      md += `## ${category.charAt(0).toUpperCase() + category.slice(1)}\n\n`;
      md += `**Total:** ${findings.length}\n\n`;

      findings.forEach((f, idx) => {
        md += `### ${idx + 1}. ${f.check || f.message || f.type}\n`;
        md += `- **Priority:** ${f.priority}\n`;
        md += `- **Message:** ${f.message || 'N/A'}\n`;
        md += `- **Recommendation:** ${f.recommendation}\n`;
        if (f.file) {
          md += `- **File:** ${f.file}\n`;
        }
        md += '\n';
      });
    });

    return md;
  }
}

// Export for use in agents
module.exports = AgentReportProcessor;

// CLI Usage
if (require.main === module) {
  const processor = new AgentReportProcessor();
  const findings = processor.scanAllReports();
  
  console.log('\n📝 ACTIONABLE FIXES:\n');
  findings.slice(0, 5).forEach((finding, idx) => {
    const fix = processor.generateFix(finding);
    console.log(`${idx + 1}. ${finding.check || finding.message}`);
    console.log(`   Action: ${fix.action}`);
    if (fix.steps) {
      fix.steps.forEach(step => {
        console.log(`     • ${step}`);
      });
    }
    console.log('');
  });

  if (findings.length > 5) {
    console.log(`... and ${findings.length - 5} more findings to address\n`);
  }

  // Export findings as JSON for agent processing
  fs.writeFileSync('agent-findings.json', processor.exportFindings('json'));
  console.log('✅ Findings exported to agent-findings.json\n');
}
