#!/usr/bin/env node

/**
 * Error Recovery Handler for AgenticQA Pipeline
 * 
 * Analyzes workflow failures and creates recovery reports that agents can use
 * to improve future runs. This system learns from failures to provide better
 * error handling and recovery strategies.
 */

const fs = require('fs');
const path = require('path');

class ErrorRecoveryHandler {
  constructor() {
    this.recoveryDir = path.join(process.cwd(), '.error-recovery');
    this.logsDir = path.join(this.recoveryDir, 'logs');
    this.patternsDir = path.join(this.recoveryDir, 'patterns');
    this.ensureDirectories();
  }

  ensureDirectories() {
    [this.recoveryDir, this.logsDir, this.patternsDir].forEach(dir => {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
    });
  }

  /**
   * Log a phase failure with recovery suggestions
   */
  logPhaseFailure(phase, error, context = {}) {
    const timestamp = new Date().toISOString();
    const errorLog = {
      timestamp,
      phase,
      error: error.message || error,
      stack: error.stack,
      context,
      suggestions: this.generateSuggestions(phase, error),
    };

    const logFile = path.join(this.logsDir, `${phase}-${timestamp.split('T')[0]}.json`);
    
    // Append to existing log or create new
    let logs = [];
    if (fs.existsSync(logFile)) {
      logs = JSON.parse(fs.readFileSync(logFile, 'utf8'));
    }
    logs.push(errorLog);
    
    fs.writeFileSync(logFile, JSON.stringify(logs, null, 2));
    return errorLog;
  }

  /**
   * Generate AI-friendly recovery suggestions based on error patterns
   */
  generateSuggestions(phase, error) {
    const errorMsg = (error.message || error).toLowerCase();
    const suggestions = [];

    // Phase 1.5 (Promptfoo) suggestions
    if (phase === 'llm-agent-validation') {
      if (errorMsg.includes('openai') || errorMsg.includes('api') || errorMsg.includes('key')) {
        suggestions.push({
          issue: 'OpenAI API key missing or invalid',
          action: 'Set OPENAI_API_KEY environment variable in GitHub Secrets',
          recovery: 'Skip LLM validation if key not available',
        });
      }
      if (errorMsg.includes('config') || errorMsg.includes('enoent')) {
        suggestions.push({
          issue: 'Configuration file not found',
          action: 'Ensure promptfoo-config.yml exists at project root',
          recovery: 'Create minimal config if missing',
        });
      }
    }

    // Phase 1.6 (Semgrep) suggestions
    if (phase === 'advanced-security-scan' && errorMsg.includes('semgrep')) {
      suggestions.push({
        issue: 'Semgrep installation failed',
        action: 'Install via apt-get (apt-get update && apt-get install semgrep)',
        recovery: 'Fall back to curl download from GitHub releases',
      });
    }

    // Phase 1.6 (Trivy) suggestions
    if (phase === 'advanced-security-scan' && errorMsg.includes('trivy')) {
      suggestions.push({
        issue: 'Trivy installation or Docker build failed',
        action: 'Ensure Docker is available or install trivy via package manager',
        recovery: 'Skip trivy if Docker unavailable, use apt-get install trivy',
      });
    }

    // General Docker suggestions
    if (errorMsg.includes('docker') || errorMsg.includes('permission denied')) {
      suggestions.push({
        issue: 'Docker daemon not available or permission denied',
        action: 'Check if Docker is installed and accessible',
        recovery: 'Skip Docker-dependent phases gracefully',
      });
    }

    // General file path suggestions
    if (errorMsg.includes('enoent') || errorMsg.includes('not found')) {
      suggestions.push({
        issue: 'File or path not found',
        action: 'Use full paths with ${{ github.workspace }}',
        recovery: 'Create files dynamically if missing',
      });
    }

    return suggestions.length > 0 ? suggestions : [{ action: 'Review logs for more details' }];
  }

  /**
   * Create a pattern analysis report for agents
   */
  createPatternAnalysis() {
    const analysis = {
      timestamp: new Date().toISOString(),
      patterns: {},
      recommendations: [],
    };

    // Read all error logs
    if (fs.existsSync(this.logsDir)) {
      const logFiles = fs.readdirSync(this.logsDir);
      
      logFiles.forEach(file => {
        const logs = JSON.parse(fs.readFileSync(path.join(this.logsDir, file), 'utf8'));
        logs.forEach(log => {
          if (!analysis.patterns[log.phase]) {
            analysis.patterns[log.phase] = {
              totalFailures: 0,
              commonErrors: {},
              suggestions: [],
            };
          }
          analysis.patterns[log.phase].totalFailures++;
          
          // Track common error patterns
          const errorKey = log.error.split('\n')[0];
          analysis.patterns[log.phase].commonErrors[errorKey] =
            (analysis.patterns[log.phase].commonErrors[errorKey] || 0) + 1;
          
          // Collect suggestions
          if (log.suggestions && log.suggestions.length > 0) {
            analysis.patterns[log.phase].suggestions.push(...log.suggestions);
          }
        });
      });
    }

    // Generate recommendations for agents
    Object.entries(analysis.patterns).forEach(([phase, data]) => {
      const topError = Object.entries(data.commonErrors)
        .sort((a, b) => b[1] - a[1])[0];
      
      if (topError) {
        analysis.recommendations.push({
          phase,
          priority: data.totalFailures > 3 ? 'HIGH' : 'MEDIUM',
          topError: topError[0],
          occurrences: topError[1],
          action: `Focus on improving ${phase} robustness`,
        });
      }
    });

    const reportFile = path.join(this.patternsDir, 'analysis.json');
    fs.writeFileSync(reportFile, JSON.stringify(analysis, null, 2));
    return analysis;
  }

  /**
   * Create an agent-readable recovery guide
   */
  createAgentRecoveryGuide() {
    const guide = {
      version: '1.0.0',
      lastUpdated: new Date().toISOString(),
      phases: {},
    };

    // Phase 1.5 Recovery Guide
    guide.phases['llm-agent-validation'] = {
      name: 'LLM Agent Validation (Promptfoo)',
      description: 'Tests agent prompts for consistency and LLM output validity',
      commonIssues: [
        {
          symptom: 'OPENAI_API_KEY not configured',
          fix: 'Add OPENAI_API_KEY to GitHub Secrets',
          fallback: 'Skip validation with status=skipped-no-key',
        },
        {
          symptom: 'Config file not found',
          fix: 'Ensure promptfoo-config.yml exists',
          fallback: 'Create minimal config dynamically',
        },
      ],
      improvements: [
        'Check key existence before running',
        'Create config if missing',
        'Use full paths ${{ github.workspace }}/promptfoo-config.yml',
      ],
    };

    // Phase 1.6 Semgrep Recovery Guide
    guide.phases['semgrep-security-scan'] = {
      name: 'Semgrep OWASP Scanning',
      description: 'Scans code for OWASP Top 10 and CWE vulnerabilities',
      commonIssues: [
        {
          symptom: 'pip or brew not available',
          fix: 'Use apt-get or curl download from GitHub releases',
          fallback: 'Download binary from releases',
        },
        {
          symptom: 'Semgrep binary not in PATH',
          fix: 'Export PATH before running semgrep',
          fallback: 'Use full path to binary',
        },
      ],
      improvements: [
        'Try apt-get first, then curl as fallback',
        'Verify command exists before running',
        'Export PATH for downloaded binaries',
        'Handle missing output file gracefully',
      ],
    };

    // Phase 1.6 Trivy Recovery Guide
    guide.phases['trivy-container-scan'] = {
      name: 'Trivy Container Scanning',
      description: 'Scans Docker images for CVE vulnerabilities',
      commonIssues: [
        {
          symptom: 'Docker not available',
          fix: 'Check Docker daemon or install trivy via apt-get',
          fallback: 'Skip if Docker unavailable',
        },
        {
          symptom: 'Image build fails',
          fix: 'Ensure Dockerfile is valid',
          fallback: 'Continue with scan anyway',
        },
      ],
      improvements: [
        'Check Docker availability first',
        'Try apt-get install trivy',
        'Curl download as fallback',
        'Handle missing Docker gracefully',
      ],
    };

    // Phase 2.5 Observability Guide
    guide.phases['observability-setup'] = {
      name: 'Observability Setup (Prometheus + Jaeger)',
      description: 'Initializes metrics and tracing infrastructure',
      commonIssues: [
        {
          symptom: 'Docker not available',
          fix: 'Check Docker daemon availability',
          fallback: 'Skip observability setup',
        },
        {
          symptom: 'Port already in use',
          fix: 'Stop existing containers or use different ports',
          fallback: 'Skip with warning',
        },
      ],
      improvements: [
        'Check Docker availability before starting',
        'Handle missing config files',
        'Use dynamic ports if needed',
        'Provide clear status in summary',
      ],
    };

    const guideFile = path.join(this.patternsDir, 'agent-recovery-guide.json');
    fs.writeFileSync(guideFile, JSON.stringify(guide, null, 2));
    return guide;
  }
}

// CLI Usage
if (require.main === module) {
  const handler = new ErrorRecoveryHandler();
  
  const command = process.argv[2];
  
  if (command === 'log') {
    const phase = process.argv[3];
    const error = process.argv[4] || 'Unknown error';
    const result = handler.logPhaseFailure(phase, new Error(error));
    console.log('✅ Error logged:', result);
  } else if (command === 'analyze') {
    const analysis = handler.createPatternAnalysis();
    console.log('✅ Pattern analysis created');
    console.log(JSON.stringify(analysis, null, 2));
  } else if (command === 'guide') {
    const guide = handler.createAgentRecoveryGuide();
    console.log('✅ Agent recovery guide created');
  } else {
    console.log(`
Error Recovery Handler for AgenticQA

Usage:
  node error-recovery-handler.js log <phase> <error>    - Log a phase failure
  node error-recovery-handler.js analyze                 - Create pattern analysis
  node error-recovery-handler.js guide                   - Create agent recovery guide
    `);
  }
}

module.exports = ErrorRecoveryHandler;
