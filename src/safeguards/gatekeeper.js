/**
 * PipelineGatekeeper
 * Validates agent changes against safety rules before they're applied
 * Ensures codebase protection without blocking the build process
 */

const fs = require('fs');
const path = require('path');
const minimatch = require('minimatch');

class PipelineGatekeeper {
  constructor(config = {}) {
    this.config = {
      enableFiltering: config.enableFiltering ?? true,
      allowedFilePatterns: config.allowedFilePatterns || [
        '**/*.js',
        '**/*.ts',
        '**/*.jsx',
        '**/*.tsx',
        '**/*.json',
        '**/*.md',
        '**/*.yml',
        '**/*.yaml'
      ],
      blockedFilePatterns: config.blockedFilePatterns || [
        '**/package.json', // Don't let agents break dependencies
        '**/.env*', // Never touch secrets
        '**/auth/**', // Critical security code
        '**/payment/**', // PCI-DSS compliance
        '**/*.lock', // Lock files only for package managers
        '**/.git/**', // Git internals
        '**/node_modules/**' // Dependencies
      ],
      maxChangesPerPR: config.maxChangesPerPR ?? 50,
      enableLogging: config.enableLogging ?? true
    };

    this.violations = [];
    this.auditLog = [];
  }

  /**
   * Main validation entry point
   */
  async validateAgentChanges(changes, agent) {
    this.violations = [];

    if (!changes || changes.length === 0) {
      return {
        passed: true,
        reason: 'No changes to validate',
        riskScore: 0,
        violations: []
      };
    }

    // 1. Check file permissions
    const fileCheck = this.validateFileAccess(changes);
    if (!fileCheck.passed) {
      return fileCheck;
    }

    // 2. Change size limits
    const sizeCheck = this.validateChangeScope(changes);
    if (!sizeCheck.passed) {
      return sizeCheck;
    }

    // 3. Risk assessment
    const riskScore = this.assessRisk(changes, agent);

    // 4. Log validation
    this.logValidation({
      agent,
      changes,
      riskScore,
      violations: this.violations,
      status: 'VALIDATED'
    });

    return {
      passed: true,
      riskScore,
      violations: this.violations,
      summary: `Validated ${changes.length} changes from ${agent.name} (risk: ${(riskScore * 100).toFixed(1)}%)`
    };
  }

  /**
   * Ensures agents don't modify protected files
   */
  validateFileAccess(changes) {
    const blockedFiles = [];

    for (const change of changes) {
      if (!change.filePath) continue;

      // Check against blocked patterns
      for (const pattern of this.config.blockedFilePatterns) {
        if (this.matchPattern(change.filePath, pattern)) {
          blockedFiles.push(change.filePath);
          this.violations.push({
            type: 'FILE_PROTECTED',
            severity: 'ERROR',
            filePath: change.filePath,
            message: `File ${change.filePath} is protected from agent modification`
          });
        }
      }

      // Check against allowed patterns (if whitelist is strict)
      if (this.config.allowedFilePatterns.length > 0) {
        const isAllowed = this.config.allowedFilePatterns.some(pattern =>
          this.matchPattern(change.filePath, pattern)
        );

        if (!isAllowed && !change.filePath.startsWith('.')) {
          this.violations.push({
            type: 'BLOCKED_PATTERN',
            severity: 'WARNING',
            filePath: change.filePath,
            message: `File ${change.filePath} not in allowed patterns`
          });
        }
      }
    }

    if (blockedFiles.length > 0) {
      return {
        passed: false,
        reason: `${blockedFiles.length} protected files cannot be modified`,
        violations: this.violations
      };
    }

    return { passed: true, violations: this.violations };
  }

  /**
   * Prevents massive sweeping changes that are hard to review
   */
  validateChangeScope(changes) {
    if (changes.length > this.config.maxChangesPerPR) {
      this.violations.push({
        type: 'TOO_MANY_CHANGES',
        severity: 'ERROR',
        message: `Too many changes (${changes.length}). Max: ${this.config.maxChangesPerPR}. Split into multiple PRs.`
      });

      return {
        passed: false,
        reason: `Change scope exceeds limit (${changes.length} > ${this.config.maxChangesPerPR})`,
        violations: this.violations
      };
    }

    return { passed: true, violations: this.violations };
  }

  /**
   * Calculates risk score based on change patterns
   */
  assessRisk(changes, agent) {
    let riskScore = 0;

    // +0.3 if touching security-related code
    if (changes.some(c => c.filePath.includes('security') || c.filePath.includes('auth'))) {
      riskScore += 0.3;
    }

    // +0.2 if modifying multiple unrelated directories
    const uniqueDirectories = new Set(
      changes.map(c => c.filePath.split('/')[0]).filter(d => d && !d.startsWith('.'))
    );
    if (uniqueDirectories.size > 3) {
      riskScore += 0.2;
    }

    // +0.15 if deletions involved
    if (changes.some(c => c.type === 'DELETE')) {
      riskScore += 0.15;
    }

    // +0.1 if modifying test infrastructure
    if (changes.some(c => c.filePath.includes('.config') || c.filePath.includes('jest') || c.filePath.includes('playwright'))) {
      riskScore += 0.1;
    }

    // -0.1 if agent has high success rate
    if (agent && agent.successRate > 0.95) {
      riskScore -= 0.1;
    }

    // +0.2 if agent is new/unproven
    if (agent && agent.successRate < 0.85) {
      riskScore += 0.2;
    }

    return Math.max(0, Math.min(riskScore, 1.0));
  }

  /**
   * Glob pattern matching
   */
  matchPattern(filePath, pattern) {
    return minimatch(filePath, pattern, { matchBase: true });
  }

  /**
   * Log validation event
   */
  logValidation(event) {
    const entry = {
      id: this.generateId(),
      timestamp: Date.now(),
      agent: event.agent.name,
      changesCount: event.changes.length,
      riskScore: event.riskScore,
      violations: event.violations,
      status: event.status
    };

    this.auditLog.push(entry);

    if (this.config.enableLogging) {
      console.log(`[GATEKEEPER] ${entry.agent}: ${entry.changesCount} changes validated (risk: ${(entry.riskScore * 100).toFixed(1)}%)`);
      if (entry.violations.length > 0) {
        console.warn(`[GATEKEEPER] Violations: ${entry.violations.map(v => v.message).join('; ')}`);
      }
    }
  }

  /**
   * Get validation history
   */
  getAuditLog(limit = 100) {
    return this.auditLog.slice(-limit);
  }

  /**
   * Export audit log to file
   */
  exportAuditLog(filePath) {
    const logData = {
      exportDate: new Date().toISOString(),
      totalEntries: this.auditLog.length,
      entries: this.auditLog
    };

    fs.writeFileSync(filePath, JSON.stringify(logData, null, 2));
    return filePath;
  }

  /**
   * Reset gatekeeper state
   */
  reset() {
    this.violations = [];
    // Keep audit log for historical record
  }

  /**
   * Generate unique ID
   */
  generateId() {
    return `GK-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }
}

module.exports = PipelineGatekeeper;
