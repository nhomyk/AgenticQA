# AgenticQA Data Flow Diagrams

## High-Level System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INPUT: Test Code & Artifacts                        │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   CODE CHANGE TRACKING      │
                    │  (Before/After Snapshots)   │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  PRE-EXECUTION VALIDATION   │
                    │  (Schema, PII, Encryption)  │
                    └──────────────┬──────────────┘
                                   │
                ┌──────────────────┼──────────────────┐
                │                  │                  │
        ┌───────▼─────┐    ┌───────▼─────┐    ┌──────▼──────┐
        │  QA Agent   │    │Performance  │    │ Compliance  │
        │   (Tests)   │    │   Agent     │    │    Agent    │
        └───────┬─────┘    └───────┬─────┘    └──────┬──────┘
                │                  │                  │
                │        ┌─────────▼──────────┐       │
                │        │  DevOps Agent      │       │
                │        │  (Risk Assessment) │       │
                │        └─────────┬──────────┘       │
                │                  │                  │
                └──────────────────┼──────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   STORE IN ARTIFACT STORE   │
                    │  .test-artifact-store/raw/  │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   SNAPSHOT TESTING          │
                    │  (Compare against baseline) │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  POST-EXECUTION VALIDATION  │
                    │   (10-Point Quality Test)   │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   PATTERN ANALYSIS          │
                    │  (Learn from history)       │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  DEPLOYMENT DECISION        │
                    │  ✅ Deploy / ❌ Block       │
                    └──────────────┬──────────────┘
                                   │
                 ┌─────────────────▼────────────────┐
                 │  OUTPUT & AUDIT TRAIL            │
                 │  (Complete execution record)     │
                 └──────────────────────────────────┘
```

---

## Artifact Store Central Hub

```
                        INPUT DATA
                           │
              ┌────────────▼────────────┐
              │  VALIDATION & SECURITY   │
              │  - PII Detection         │
              │  - Schema Validation     │
              │  - Encryption Check      │
              └────────────┬────────────┘
                           │
                ┌──────────▼──────────┐
                │  AGENT EXECUTION     │
                │  (4 parallel agents) │
                └──────────┬──────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
    ┌───▼───┐          ┌───▼───┐         ┌───▼───┐
    │ Raw   │          │Meta-  │         │Valid- │
    │  /    │          │  data │         │ation  │
    │       │          │  /    │         │  /    │
    └───┬───┘          └───┬───┘         └───┬───┘
        │                  │                  │
        │   ┌──────────────▼──────────────┐  │
        │   │                             │  │
        └──▶│  MASTER INDEX (index.json)  │◀─┘
            │                             │
            │ {                           │
            │   "uuid1": {                │
            │     "id": "uuid1",          │
            │     "timestamp": "...",     │
            │     "source": "qa_agent",   │
            │     "checksum": "a3f5c...", │
            │     "path": "raw/..."       │
            │   }                         │
            │ }                           │
            └──────────────┬──────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
    ┌───▼────┐         ┌───▼────┐       ┌────▼────┐
    │ Failure│         │ Perform│       │ Success │
    │Patterns│         │ Trends │       │Patterns │
    │        │         │        │       │         │
    └────────┘         └────────┘       └─────────┘

    .test-artifact-store/
    ├── raw/              (Agent outputs)
    ├── metadata/         (Timestamps, checksums)
    ├── validations/      (Quality test results)
    ├── patterns/         (Historical analysis)
    └── index.json        (Master searchable index)
```

---

## Parallel Agent Execution

```
Input Test Data
      │
      ├──────┬──────┬──────┐
      │      │      │      │
      ▼      ▼      ▼      ▼
  ┌────┐ ┌────┐ ┌────┐ ┌────┐
  │ QA │ │Perf│ │Comp│ │DevOps
  │Agnt│ │Agnt│ │Agnt│ │Agnt
  └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘
     │      │      │      │
     │      │      │      │
     ├──────┴──────┴──────┤
     │                   │
     ▼                   ▼
  Results          Results
   Dict             Dict
     │                │
     └────────┬───────┘
              │
         ┌────▼────┐
         │ Combine │
         │ Results │
         └────┬────┘
              │
         ┌────▼────────────────┐
         │ Store to Artifact   │
         │ Store (4 files)     │
         └────┬────────────────┘
              │
    .test-artifact-store/raw/
    ├── qa_agent_{uuid}.json
    ├── performance_agent_{uuid}.json
    ├── compliance_agent_{uuid}.json
    └── devops_agent_{uuid}.json
```

---

## Code Change Impact Analysis

```
BEFORE STATE CAPTURED
      │
      ├─ Quality Score: 85.0%
      ├─ Execution Time: 150ms
      ├─ Tests Passed: 95
      ├─ Tests Failed: 5
      └─ Compliance: 90.0%
      │
      ▼ Stored to: .code_changes/{id}_before.json
      │
      ⚙️ CODE CHANGE APPLIED
      │
      ├─ Agent optimization
      ├─ Algorithm refactoring
      └─ Configuration update
      │
      ▼
AFTER STATE CAPTURED
      │
      ├─ Quality Score: 92.0%
      ├─ Execution Time: 120ms
      ├─ Tests Passed: 98
      ├─ Tests Failed: 2
      └─ Compliance: 92.0%
      │
      ▼ Stored to: .code_changes/{id}_after.json
      │
      ANALYSIS COMPUTED
      │
      ├─ Quality Delta: +7.0%  ✅
      ├─ Performance Delta: +30ms ✅ (faster)
      ├─ Test Delta: +3 passed, -3 failed ✅
      └─ Compliance Delta: +2.0% ✅
      │
      ▼ Stored to: .code_changes/{id}_analysis.json
      │
      SAFETY DETERMINED
      │
      ├─ All metrics improved? YES ✅
      ├─ Tests failing? NO ✅
      ├─ Compliance maintained? YES ✅
      │
      ▼
    VERDICT: ✅ SAFE TO DEPLOY
```

---

## Snapshot Comparison

```
BASELINE ESTABLISHED (First Run)
      │
      ├─ QA Agent Output
      │  └─ Hash: a3f5c21e4d9b8f1c...
      │     Stored: .snapshots/qa_agent_output.json
      │
      ├─ Performance Output
      │  └─ Hash: b4g6d32f5e0c9h2d...
      │     Stored: .snapshots/performance_agent_output.json
      │
      ├─ Compliance Output
      │  └─ Hash: c5h7e43g6f1d0i3e...
      │     Stored: .snapshots/compliance_agent_output.json
      │
      └─ DevOps Output
         └─ Hash: d6i8f54h7g2e1j4f...
            Stored: .snapshots/devops_agent_output.json


SUBSEQUENT RUN: COMPARISON
      │
      ├─ QA Agent New Output
      │  └─ Hash: a3f5c21e4d9b8f1c... ✅ MATCHES
      │     Same behavior, baseline consistent
      │
      ├─ Performance New Output
      │  └─ Hash: X2Y9Z8A7B6C5D4E3... ❌ MISMATCH
      │     Unexpected change detected!
      │     → Review difference report
      │     → Determine if intentional
      │     → Update baseline if approved
      │
      ├─ Compliance New Output
      │  └─ Hash: c5h7e43g6f1d0i3e... ✅ MATCHES
      │
      └─ DevOps New Output
         └─ Hash: d6i8f54h7g2e1j4f... ✅ MATCHES


RESULT
      │
      ├─ 3 snapshots match baseline    ✅
      ├─ 1 snapshot changed            ⚠️
      │  └─ Requires review
      │
      └─ Action: Review mismatch, update if intentional
```

---

## Data Quality Testing Pipeline

```
RAW ARTIFACTS IN STORE
      │
      ▼
TEST 1: Artifact Integrity
      ├─ Verify checksums match
      ├─ Detect data corruption
      └─ Result: ✅ PASS

TEST 2: Format Validation
      ├─ Check JSON valid
      ├─ Verify encoding
      └─ Result: ✅ PASS

TEST 3: Schema Consistency
      ├─ All required fields present
      ├─ Data types correct
      └─ Result: ✅ PASS

TEST 4: Duplicate Detection
      ├─ No repeated artifacts
      ├─ IDs unique
      └─ Result: ✅ PASS

TEST 5: Metadata Completeness
      ├─ Timestamps present
      ├─ Source documented
      └─ Result: ✅ PASS

TEST 6: Index Accuracy
      ├─ All artifacts in index
      ├─ Index reflects reality
      └─ Result: ✅ PASS

TEST 7: Immutability
      ├─ Stored data unchanged
      ├─ Detect any modifications
      └─ Result: ✅ PASS

TEST 8: PII Protection
      ├─ No sensitive data
      ├─ No passwords/keys
      └─ Result: ✅ PASS

TEST 9: Temporal Consistency
      ├─ Timestamps logical
      ├─ No time reversals
      └─ Result: ✅ PASS

TEST 10: Cross-Deployment
      ├─ Data consistent across envs
      ├─ No divergence
      └─ Result: ✅ PASS

FINAL RESULT
      │
      ├─ Tests Passed: 10/10 ✅
      ├─ Quality Score: 100%
      │
      └─ VERDICT: Data quality verified, safe to deploy
```

---

## Pattern Learning Cycle

```
EXECUTION 1
      ├─ QA Tests: 95 passed, 5 failed
      │  └─ Tests 15, 23, 42 failed
      ├─ Performance: 150ms baseline
      └─ Artifacts stored


EXECUTION 2
      ├─ QA Tests: 97 passed, 3 failed
      │  └─ Tests 15, 42 failed (same ones!)
      │  └─ Test 23 now passes
      ├─ Performance: 155ms (trending up)
      └─ Artifacts stored


EXECUTION 3
      ├─ QA Tests: 96 passed, 4 failed
      │  └─ Tests 15, 42 failed AGAIN
      │  └─ Tests 8, 23 passed now
      ├─ Performance: 162ms (still trending up)
      └─ Artifacts stored


PATTERN ANALYSIS
      │
      ├─ Failure Pattern Detected
      │  └─ Tests 15 & 42 always fail together
      │     → Likely same root cause
      │     → Recommend fixing both
      │
      ├─ Performance Trend Detected
      │  └─ Execution time up 12ms over 3 runs
      │     → Trending +4ms per run
      │     → Will exceed threshold in 5 runs
      │     → Alert: investigate performance degradation
      │
      └─ Flakiness Detected
         └─ Test 23 fails 1 out of 3 times
            → Flaky test identified
            → Needs investigation


AGENTS USE PATTERNS IN NEXT EXECUTION
      │
      ├─ QA Agent
      │  └─ "Tests 15 & 42 are related, fix together"
      │  └─ "Test 23 is flaky, monitor it"
      │
      ├─ Performance Agent
      │  └─ "Performance degrading +4ms per run"
      │  └─ "Alert if next run > 166ms"
      │
      └─ DevOps Agent
         └─ "High flakiness indicates instability"
         └─ "Recommend extended testing"
```

---

## Complete Flow: Input to Decision

```
INPUT
  │
  ├─ Code changes to test
  ├─ Test suite
  └─ Environment


PHASE 1: VALIDATE CHANGES
  │
  ├─ Capture before state
  │  └─ → .code_changes/{id}_before.json
  │
  ├─ Apply code change
  │
  └─ Ready to test


PHASE 2: PRE-EXECUTION
  │
  ├─ Validate input
  │  ├─ Schema check
  │  ├─ PII scan
  │  └─ → .test-artifact-store/validations/
  │
  └─ Proceed to execution


PHASE 3: AGENT EXECUTION
  │
  ├─ QA Agent
  │  └─ → .test-artifact-store/raw/qa_agent_{uuid}.json
  │
  ├─ Performance Agent
  │  └─ → .test-artifact-store/raw/performance_agent_{uuid}.json
  │
  ├─ Compliance Agent
  │  └─ → .test-artifact-store/raw/compliance_agent_{uuid}.json
  │
  └─ DevOps Agent
     └─ → .test-artifact-store/raw/devops_agent_{uuid}.json


PHASE 4: VALIDATION
  │
  ├─ Update index
  │  └─ → .test-artifact-store/index.json
  │
  ├─ Create snapshots
  │  ├─ QA snapshot → .snapshots/qa_agent_output.json
  │  ├─ Perf snapshot → .snapshots/performance_agent_output.json
  │  ├─ Compliance → .snapshots/compliance_agent_output.json
  │  └─ DevOps → .snapshots/devops_agent_output.json
  │
  └─ Compare to baselines


PHASE 5: QUALITY TESTS
  │
  ├─ 10-point quality verification
  │  └─ → .test-artifact-store/validations/
  │
  └─ All tests passing?


PHASE 6: ANALYSIS
  │
  ├─ Detect patterns
  │  └─ → .test-artifact-store/patterns/
  │
  ├─ Analyze changes
  │  └─ → .code_changes/{id}_analysis.json
  │
  └─ Compare metrics


PHASE 7: DECISION
  │
  ├─ Review all data:
  │  ├─ Code change safe? (before/after improved)
  │  ├─ Snapshots match? (behavior consistent)
  │  ├─ Quality tests pass? (10/10)
  │  ├─ Patterns favorable? (safe indicators)
  │  └─ Compliance maintained? (security OK)
  │
  └─ Verdict:
     ├─ ✅ DEPLOY: All green
     ├─ ⚠️ REVIEW: Manual approval needed
     ├─ ❌ BLOCK: Do not deploy
     └─ 🔄 ROLLBACK: Restore previous state


OUTPUT
  │
  ├─ Deployment recommendation
  ├─ Complete audit trail
  ├─ Performance metrics
  ├─ Quality scores
  └─ Rollback available if needed
```

---

## Storage Locations Quick Reference

| Component | Stores To | Contains |
|-----------|-----------|----------|
| Agents | `.test-artifact-store/raw/` | Execution results |
| Validation | `.test-artifact-store/validations/` | Pre/post checks |
| Metadata | `.test-artifact-store/metadata/` | Timestamps, checksums |
| Patterns | `.test-artifact-store/patterns/` | Historical analysis |
| Index | `.test-artifact-store/index.json` | Master searchable index |
| Snapshots | `.snapshots/` | Agent output baselines |
| Code Changes | `.code_changes/` | Before/after comparisons |

All roads lead through `.test-artifact-store/` — the central data hub! 🎯

