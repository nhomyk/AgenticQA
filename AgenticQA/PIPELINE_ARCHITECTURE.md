# AgenticQA Pipeline Architecture & Data Flow

## Complete System Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        AGENTICQA PIPELINE ARCHITECTURE                    │
└──────────────────────────────────────────────────────────────────────────┘

INPUT: Test Data
  ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: CODE CHANGE MANAGEMENT                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Before State Captured → .code_changes/{id}_before.json                │
│  CodeChangeTracker stores:                                              │
│    • Quality metrics                                                     │
│    • Performance baseline                                                │
│    • Test results                                                        │
│    • Compliance score                                                    │
│                                                                          │
│  ⚙️ CODE CHANGE APPLIED                                                │
│                                                                          │
│  After State Captured → .code_changes/{id}_after.json                  │
│                                                                          │
│  Analysis Generated → .code_changes/{id}_analysis.json                 │
│    • Before/After comparison                                            │
│    • Metric deltas                                                      │
│    • Safety determination                                               │
│                                                                          │
│  Decision: Deploy ✅ or Rollback ❌                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: PRE-EXECUTION VALIDATION                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  SecureDataPipeline.validate_input_data():                             │
│    ✓ Schema validation                                                  │
│    ✓ PII detection                                                      │
│    ✓ Encryption readiness                                               │
│    ✓ Format validation                                                  │
│                                                                          │
│  Results → .test-artifact-store/validations/pre_exec_{timestamp}.json │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: AGENT EXECUTION (PARALLEL)                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────┐  ┌──────────────────────┐  ┌────────────────┐ │
│  │  QA Agent           │  │ Performance Agent    │  │ Compliance     │ │
│  │  • Run tests        │  │ • Measure timing     │  │ • Check GDPR   │ │
│  │  • Code review      │  │ • Profile execution  │  │ • Check HIPAA  │ │
│  │  • Find bugs        │  │ • Memory analysis    │  │ • Audit GDPR   │ │
│  └──────────┬──────────┘  └──────────┬───────────┘  └────────┬───────┘ │
│             │                       │                        │          │
│  ┌──────────┴────────────────────────┴────────────────────────┴────────┐ │
│  │              DevOps Agent                                   │ │
│  │              • Assess risk                                  │ │
│  │              • Evaluate deployment                          │ │
│  │              • Security check                               │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  All agents record execution:                                           │
│    → .test-artifact-store/raw/{agent}_{uuid}.json                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: SNAPSHOT TESTING                                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  SnapshotManager captures agent outputs:                                │
│    → .snapshots/qa_agent_output.json                                    │
│    → .snapshots/performance_agent_output.json                           │
│    → .snapshots/compliance_agent_output.json                            │
│    → .snapshots/devops_agent_output.json                                │
│                                                                          │
│  Compares against previous baselines using SHA256:                      │
│    Before Hash: a3f5c21e4d9b8f1c2e3a4b5c6d7e8f9a...                   │
│    After Hash:  b4g6d32f5e0c9h2d3f4e5g6h7i8j9k0l...                   │
│                                                                          │
│  Results: ✅ Match or ❌ Mismatch                                       │
│                                                                          │
│  Snapshot metadata → .test-artifact-store/metadata/{snapshot_id}.json  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 5: POST-EXECUTION VALIDATION                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  DataQualityTester runs 10 comprehensive tests:                         │
│    1. Artifact integrity (checksums)                                    │
│    2. Format validation (JSON, encoding)                                │
│    3. Schema consistency (all fields present)                           │
│    4. Duplicate detection (no repeats)                                  │
│    5. Metadata completeness (timestamps, IDs)                           │
│    6. Index accuracy (master index correct)                             │
│    7. Immutability (stored data unchanged)                              │
│    8. PII protection (no sensitive data)                                │
│    9. Temporal consistency (logical timestamps)                         │
│    10. Cross-deployment consistency                                     │
│                                                                          │
│  Results → .test-artifact-store/validations/post_exec_{timestamp}.json │
│                                                                          │
│  All artifacts indexed in master index                                  │
│    → .test-artifact-store/index.json                                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 6: PATTERN ANALYSIS & LEARNING                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  PatternAnalyzer examines historical data:                              │
│    • Failure patterns (which tests fail together?)                      │
│    • Performance trends (is it getting slower?)                         │
│    • Flakiness detection (which tests are unreliable?)                 │
│    • Success patterns (what makes deployments safe?)                    │
│                                                                          │
│  Results → .test-artifact-store/patterns/{pattern_type}.json           │
│                                                                          │
│  Agents use patterns to improve decisions:                              │
│    QA Agent:         "This test usually fails when X"                  │
│    Performance:      "Execution time trending up 2% per week"          │
│    Compliance:       "These endpoints need audit logs"                  │
│    DevOps:           "High risk when >3 tests fail"                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 7: DEPLOYMENT DECISION                                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  All data evaluated:                                                    │
│    ✓ Code change metrics (before/after improved?)                      │
│    ✓ Snapshot consistency (outputs match baseline?)                    │
│    ✓ Quality tests (all 10 tests passing?)                             │
│    ✓ Pattern analysis (matches safe deployment pattern?)               │
│    ✓ Compliance (security requirements met?)                           │
│                                                                          │
│  DEPLOYMENT DECISION:                                                   │
│    ✅ DEPLOY: All checks passing, metrics improved                    │
│    ⚠️  REVIEW: Mixed results, manual approval needed                  │
│    ❌ BLOCK: Tests failing, security risk, or major regression        │
│    🔄 ROLLBACK: If change applied, restore previous state             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
  ↓
OUTPUT: Deployment recommendation + Audit trail
```

---

## Data Store Directory Structure

```
.test-artifact-store/                          ← Central data repository
│
├── raw/                                        ← Raw execution results
│   ├── qa_agent_{uuid}.json                   (QA agent execution)
│   ├── performance_agent_{uuid}.json          (Performance results)
│   ├── compliance_agent_{uuid}.json           (Compliance check)
│   └── devops_agent_{uuid}.json               (DevOps assessment)
│
├── metadata/                                   ← Execution metadata
│   ├── artifact_{uuid}_metadata.json          (Timestamps, checksums)
│   ├── execution_{timestamp}.json             (Execution info)
│   └── snapshots/                             (Snapshot metadata)
│       ├── snapshot_{id}.json
│       └── snapshot_comparison_{id}.json
│
├── validations/                                ← Quality assurance results
│   ├── pre_exec_{timestamp}.json              (Pre-execution checks)
│   ├── post_exec_{timestamp}.json             (Post-execution checks)
│   └── quality_tests_{timestamp}.json         (10-point test results)
│
├── patterns/                                   ← Historical analysis
│   ├── failure_patterns.json                  (Which tests fail together)
│   ├── performance_trends.json                (Speed analysis)
│   ├── flakiness_detection.json               (Unreliable tests)
│   └── success_patterns.json                  (Safe deployments)
│
└── index.json                                  ← Master searchable index
    {
      "uuid1": {
        "id": "uuid1",
        "timestamp": "2026-01-26T10:30:00",
        "source": "qa_agent",
        "type": "execution",
        "tags": ["critical", "ui-tests"],
        "checksum": "a3f5c21e...",
        "path": "raw/qa_agent_uuid1.json"
      },
      ...
    }

.code_changes/                                 ← Code change tracking
├── change1_before.json                        (Before snapshot)
├── change1_after.json                         (After snapshot)
└── change1_analysis.json                      (Impact analysis)

.snapshots/                                    ← Snapshot baselines
├── qa_agent_output.json                       (QA baseline)
├── performance_agent_output.json              (Performance baseline)
├── compliance_agent_output.json               (Compliance baseline)
└── devops_agent_output.json                   (DevOps baseline)
```

---

## Data Flow Through Components

### 1. Agent Execution Flow

```
Input Test Data
       ↓
   ┌───────────────────┐
   │ Agent Execution   │
   └─────────┬─────────┘
             ↓
   Execution Results (Dict)
             ↓
   ┌─────────────────────────────────────────┐
   │ _record_execution() in BaseAgent         │
   │ Stores to: TestArtifactStore             │
   └─────────┬───────────────────────────────┘
             ↓
   .test-artifact-store/raw/{agent}_{uuid}.json
             ↓
   ┌─────────────────────────────────────────┐
   │ Master Index Updated                    │
   │ .test-artifact-store/index.json          │
   └─────────────────────────────────────────┘
```

### 2. Validation Flow

```
Raw Artifacts
       ↓
   ┌──────────────────────┐
   │ Pre-Execution Val.   │ ← Before agents run
   └──────────┬───────────┘
             ↓
   Stored in: validations/pre_exec_{ts}.json
             ↓
   [Agent Execution]
             ↓
   ┌──────────────────────┐
   │ Post-Execution Val.  │ ← After agents run
   └──────────┬───────────┘
             ↓
   Stored in: validations/post_exec_{ts}.json
             ↓
   ┌──────────────────────┐
   │ Quality Tests (10)   │ ← Run all quality checks
   └──────────┬───────────┘
             ↓
   Stored in: validations/quality_tests_{ts}.json
             ↓
   Decision: ✅ Pass or ❌ Fail
```

### 3. Snapshot & Comparison Flow

```
Agent Output
       ↓
   ┌─────────────────────────┐
   │ SnapshotManager         │
   │ Creates snapshot        │
   │ Computes SHA256 hash    │
   └──────────┬──────────────┘
             ↓
   .snapshots/{agent}_output.json (stored)
             ↓
   Metadata → .test-artifact-store/metadata/
             ↓
   ┌─────────────────────────┐
   │ Compare with Baseline   │
   │ Hash match?             │
   └──────────┬──────────────┘
             ↓
   ✅ Match (consistency OK)
   or
   ❌ Mismatch (unexpected change)
```

### 4. Code Change Flow

```
Baseline Metrics Captured
       ↓
   ┌──────────────────────────┐
   │ CodeChangeTracker        │
   │ start_change()           │
   │ Before state stored      │
   └──────────┬───────────────┘
             ↓
   .code_changes/{id}_before.json
             ↓
   ⚙️ CODE CHANGE APPLIED
             ↓
   New Metrics Captured
             ↓
   ┌──────────────────────────┐
   │ CodeChangeTracker        │
   │ end_change()             │
   │ After state stored       │
   └──────────┬───────────────┘
             ↓
   .code_changes/{id}_after.json
             ↓
   ┌──────────────────────────┐
   │ Analyze Impact           │
   │ Compare metrics          │
   │ Determine safety         │
   └──────────┬───────────────┘
             ↓
   .code_changes/{id}_analysis.json
             ↓
   Decision: ✅ Deploy or ❌ Rollback
```

### 5. Pattern Analysis Flow

```
Historical Artifacts in Store
       ↓
   ┌─────────────────────────┐
   │ PatternAnalyzer         │
   │ Examines all data       │
   └──────────┬──────────────┘
             ↓
   Identifies patterns:
   - Failure clusters
   - Performance trends
   - Flaky tests
   - Success indicators
             ↓
   ┌─────────────────────────┐
   │ Store patterns          │
   └──────────┬──────────────┘
             ↓
   .test-artifact-store/patterns/
   ├── failure_patterns.json
   ├── performance_trends.json
   ├── flakiness_detection.json
   └── success_patterns.json
             ↓
   Agents use patterns in next execution
```

---

## Component Integration Summary

| Component | Reads From | Writes To | Purpose |
|-----------|-----------|-----------|---------|
| **TestArtifactStore** | `.test-artifact-store/` | `.test-artifact-store/` | Central data repository |
| **SecureDataPipeline** | Input data | `.test-artifact-store/validations/` | Validation orchestration |
| **Agents** | Input data | `.test-artifact-store/raw/` | Execution & learning |
| **SnapshotManager** | Agent output | `.snapshots/`, `.test-artifact-store/metadata/` | Consistency verification |
| **CodeChangeTracker** | Agent metrics | `.code_changes/` | Before/after comparison |
| **PatternAnalyzer** | `.test-artifact-store/raw/` | `.test-artifact-store/patterns/` | Learning from history |
| **DataQualityTester** | `.test-artifact-store/raw/` | `.test-artifact-store/validations/` | Quality assurance |
| **ChangeHistoryAnalyzer** | `.code_changes/` | Reporting | Analytics over time |

---

## Complete Execution Sequence

```
1. INPUT: Test code + test suite
   ↓
2. CODE CHANGE CHECK
   → Capture before metrics
   → Apply code change
   → Capture after metrics
   → Analyze impact
   → ✅ Safe to proceed?
   ↓
3. PRE-EXECUTION VALIDATION
   → Schema check
   → PII scan
   → Format validation
   → Store results
   ↓
4. AGENT EXECUTION (parallel)
   → QA Agent (tests, code review)
   → Performance Agent (timing, profiling)
   → Compliance Agent (security, audit)
   → DevOps Agent (risk, deployment readiness)
   → Store all results in artifact store
   → Update master index
   ↓
5. SNAPSHOT TESTING
   → Capture agent outputs
   → Compare against baselines
   → Check for unexpected changes
   → Store metadata
   ↓
6. POST-EXECUTION VALIDATION
   → Run 10-point quality test suite
   → Validate artifact integrity
   → Check data consistency
   → Store validation results
   ↓
7. PATTERN ANALYSIS
   → Analyze historical data
   → Detect trends
   → Identify flaky tests
   → Update patterns database
   ↓
8. DEPLOYMENT DECISION
   → Review all metrics
   → Evaluate code change impact
   → Check snapshot consistency
   → Verify quality tests passing
   → Confirm pattern match
   → Make decision: ✅ Deploy, ⚠️ Review, or ❌ Block
   ↓
9. OUTPUT: Deployment recommendation + complete audit trail
```

---

## Key Guarantees

This architecture ensures:

✅ **Data Integrity** - Every artifact is checksummed, indexed, and validated
✅ **Consistency** - Snapshots ensure agent behavior doesn't regress
✅ **Quality** - 10-point testing validates every aspect of data
✅ **Safety** - Code changes are validated before deployment
✅ **Learning** - Patterns improve decision-making over time
✅ **Auditability** - Complete trail of all operations
✅ **Compliance** - Security checks at every stage
✅ **Rollback** - Automatic recovery from bad changes

