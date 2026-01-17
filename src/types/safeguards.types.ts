/**
 * SafeGuards Type Definitions
 * Type-safe interfaces for code protection and audit trails
 */

export interface SafeguardConfig {
  enableFiltering: boolean;
  allowedFilePatterns: string[];
  blockedFilePatterns: string[];
  maxChangesPerPR: number;
  enableRollbackMonitoring: boolean;
  rollbackThresholds: RollbackThresholds;
  enableAuditLogging: boolean;
  auditLogStorage: 'memory' | 'file' | 'database' | 's3';
}

export interface RollbackThresholds {
  errorRateIncreasePercent: number;
  latencyIncreasePercent: number;
  memoryLeakMB: number;
  cpuSpikePercent: number;
  failedTestsThreshold: number;
}

export interface Change {
  filePath: string;
  type: 'CREATE' | 'UPDATE' | 'DELETE';
  oldContent?: string;
  newContent?: string;
  linesAdded?: number;
  linesRemoved?: number;
}

export interface Agent {
  id: string;
  name: string;
  type: 'SDET' | 'SRE' | 'FULLSTACK' | 'COMPLIANCE';
  successRate: number;
  confidenceScore: number;
  version: string;
}

export interface ValidationResult {
  passed: boolean;
  reason?: string;
  requiresApproval?: boolean;
  riskScore?: number;
  violations?: ValidationViolation[];
}

export interface ValidationViolation {
  type: 'FILE_PROTECTED' | 'TOO_MANY_CHANGES' | 'HIGH_RISK' | 'BLOCKED_PATTERN';
  severity: 'WARNING' | 'ERROR';
  filePath?: string;
  message: string;
}

export interface AuditEntry {
  id: string;
  timestamp: number;
  agent: Agent;
  action: string;
  changes: Change[];
  result: 'APPROVED' | 'REJECTED' | 'ROLLED_BACK' | 'VALIDATED';
  approver?: string;
  ipAddress?: string;
  riskScore: number;
  signature: string;
  metadata?: Record<string, any>;
}

export interface MetricsSnapshot {
  timestamp: number;
  errorRate: number;
  p95Latency: number;
  p99Latency: number;
  memoryUsagePercent: number;
  cpuUsagePercent: number;
  activeConnections: number;
  requestsPerSecond: number;
  databaseQueryTimeMs: number;
  failedTests: number;
  passedTests: number;
}

export interface MetricsDegradation {
  errorRateIncrease: number;
  latencyIncrease: number;
  memoryLeak: number;
  cpuSpike: number;
  failedTestIncrease: number;
  threshold: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
}

export interface Deployment {
  id: string;
  timestamp: number;
  agentId: string;
  changes: Change[];
  version: string;
  status: 'PENDING' | 'DEPLOYED' | 'ROLLED_BACK' | 'MONITORING';
  baselines?: MetricsSnapshot;
}

export interface ComplianceReport {
  period: { start: Date; end: Date };
  totalChanges: number;
  changesApproved: number;
  changesRolledBack: number;
  agentBreakdown: AgentStats[];
  highRiskChanges: AuditEntry[];
  exportUrl?: string;
}

export interface AgentStats {
  agentName: string;
  agentType: string;
  changesCount: number;
  approvalRate: number;
  successRate: number;
  rollbackCount: number;
  avgRiskScore: number;
}
