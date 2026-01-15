# Agent Orchestration - Visual Diagrams

## Workflow Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                      BASELINE TESTS (Required)                  │
├────────────┬──────────────┬────────────┬──────────────────┬─────┤
│    lint    │ unit-test    │ test-      │  test-vitest     │     │
│            │              │ playwright │                  │     │
│            │              │            │  test-cypress    │     │
│            │              │            │  test-pa11y      │     │
│            │              │            │  test-security   │     │
└────────────┴──────────────┴────────────┴──────────────────┴─────┘
                              All Complete ✅
                                   ↓
┌──────────────────────────────────┬──────────────────────────────┐
│      PHASE 1️⃣ - Testing (Parallel)                             │
│                                                                 │
│  ┌──────────────────────┐    ┌──────────────────────────────┐  │
│  │   SDET Agent         │    │  Compliance Agent            │  │
│  │  🧪 QA Testing       │    │  🛡️  Legal & Regulatory     │  │
│  │                      │    │                              │  │
│  │ Generates:           │    │  Generates:                  │  │
│  │ - sdet-coverage/     │    │  - compliance-audit-report   │  │
│  │ - sdet-tests/        │    │    .md                       │  │
│  │                      │    │                              │  │
│  │ ⏱️  ~5-10 minutes    │    │  ⏱️  ~3-5 minutes           │  │
│  └──────────────────────┘    └──────────────────────────────┘  │
│                                                                 │
│  Both agents run simultaneously                                │
│  Both MUST complete before Phase 2                             │
└──────────────────────────────────┬──────────────────────────────┘
                              BOTH Complete ✅
                                   ↓
┌────────────────────────────────────────────────────────────────┐
│      PHASE 2️⃣ - Fixes (Sequential)                            │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │         Fullstack Agent 🔧 Fixes                         │  │
│  │                                                           │  │
│  │  Input Artifacts (from Phase 1):                          │  │
│  │  ├─ test-failures/                                       │  │
│  │  ├─ sdet-coverage/                                       │  │
│  │  ├─ sdet-tests/                                          │  │
│  │  └─ compliance-audit-report.md                           │  │
│  │                                                           │  │
│  │  Processing:                                              │  │
│  │  ├─ Fix code issues from test failures                  │  │
│  │  ├─ Improve test coverage                               │  │
│  │  ├─ Generate missing tests                              │  │
│  │  └─ Remediate compliance issues                         │  │
│  │                                                           │  │
│  │  Output: Auto-committed code fixes                       │  │
│  │                                                           │  │
│  │  ⏱️  ~10-15 minutes                                      │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  MUST complete before Phase 3                                 │
└────────────────────────────────────┬─────────────────────────┘
                              Complete ✅
                                   ↓
┌────────────────────────────────────────────────────────────────┐
│      PHASE 3️⃣ - Production (Sequential)                       │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │         SRE Agent 🚀 Operations                          │  │
│  │                                                           │  │
│  │  Input: All previous artifacts + fixed code              │  │
│  │                                                           │  │
│  │  Processing:                                              │  │
│  │  ├─ Validate fixed code                                  │  │
│  │  ├─ Optimize performance                                 │  │
│  │  ├─ Update infrastructure                                │  │
│  │  ├─ Handle emergency fixes if needed                    │  │
│  │  └─ Manage deployments                                   │  │
│  │                                                           │  │
│  │  Output: Production deployments, infrastructure updates   │  │
│  │                                                           │  │
│  │  ⏱️  ~5-10 minutes                                       │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
                              Complete ✅
                                   ↓
                    ✨ WORKFLOW COMPLETE ✨
```

---

## Phase Coordination Sequence

```
Time    Event                               Phase     Job Status
────────────────────────────────────────────────────────────────
T+0     Workflow starts                     -         🔵 Pending
        Baseline tests run in parallel      Base      🟡 Running

T+5     Lint completes                      Base      ✅ Done
        Other tests continue                Base      🟡 Running

T+15    All baseline tests complete         Base      ✅ Done
        ↓                                              ↓

T+15    Phase 1 agents triggered            1️⃣       🔵 Pending
        SDET Agent starts                   1️⃣       🟡 Running
        Compliance Agent starts             1️⃣       🟡 Running

T+20    Compliance Agent completes          1️⃣       ✅ Done
        SDET Agent still running            1️⃣       🟡 Running

T+25    SDET Agent completes                1️⃣       ✅ Done
        Both Phase 1 agents done            1️⃣       ✅ All Done
        ↓                                              ↓

T+25    Phase 2 agent triggered             2️⃣       🔵 Pending
        Fullstack Agent starts              2️⃣       🟡 Running
        (Has access to all Phase 1 artifacts)

T+40    Fullstack Agent completes           2️⃣       ✅ Done
        ↓                                              ↓

T+40    Phase 3 agent triggered             3️⃣       🔵 Pending
        SRE Agent starts                    3️⃣       🟡 Running
        (Has access to all previous artifacts)

T+50    SRE Agent completes                 3️⃣       ✅ Done
        ↓                                              ↓

T+50    ✨ WORKFLOW COMPLETE ✨            All      ✅ Success
```

---

## Agent Responsibility Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                    WORKFLOW PIPELINE                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Phase 1️⃣ Agents          Phase 2️⃣ Agent    Phase 3️⃣ Agent │
│  ┌──────────┐┌─────────┐  ┌────────────┐  ┌────────────┐  │
│  │  SDET    ││Compliance  Fullstack    │  │    SRE     │  │
│  │  Agent   ││Agent    │  │   Agent    │  │   Agent    │  │
│  └──────────┘└─────────┘  └────────────┘  └────────────┘  │
│       ↓           ↓             ↓              ↓           │
│  ┌──────────┐┌─────────┐  ┌────────────┐  ┌────────────┐  │
│  │ TESTING  ││AUDIT    │→→│   FIXES    │→→│PRODUCTION  │  │
│  │ & QA     ││LEGAL &  │  │ & COMPILE  │  │& DEPLOY    │  │
│  │ANALYSIS  ││COMPLIANCE  │            │  │            │  │
│  └──────────┘└─────────┘  └────────────┘  └────────────┘  │
│                                                             │
│  ❌ SDET does NOT:        ❌ Fullstack does NOT:          │
│  - Commit code            - Re-run tests                  │
│  - Deploy                 - Audit compliance              │
│  - Fix issues             - Deploy to prod                │
│                                                             │
│  ❌ Compliance does NOT:   ❌ SRE does NOT:               │
│  - Fix code               - Write app code                │
│  - Deploy                 - Audit compliance              │
│  - Run tests              - Fix code logic                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow Between Phases

```
PHASE 1️⃣ AGENTS
├─ SDET Agent
│  ├─ Outputs: sdet-coverage/
│  ├─ Outputs: sdet-tests/
│  └─ → Available to Phase 2
│
├─ Compliance Agent
│  ├─ Outputs: compliance-audit-report.md
│  └─ → Available to Phase 2
│
└─ Baseline Tests (artifacts)
   ├─ Outputs: test-failures/
   └─ → Available to Phase 2
        │
        ↓
        
PHASE 2️⃣ FULLSTACK AGENT
├─ Reads from Phase 1:
│  ├─ test-failures/ (what to fix)
│  ├─ sdet-coverage/ (coverage gaps)
│  ├─ sdet-tests/ (suggested tests)
│  └─ compliance-audit-report.md (what to remediate)
│
├─ Processes:
│  ├─ Fixes code issues
│  ├─ Generates tests
│  ├─ Remediates compliance
│  └─ Auto-commits fixes
│
└─ → Outputs to GitHub (code commits)
     → Available to Phase 3 (fixed code)
        │
        ↓
        
PHASE 3️⃣ SRE AGENT
├─ Reads from Phase 2:
│  ├─ Fixed/validated code
│  ├─ All previous test results
│  ├─ Compliance status
│  └─ Coverage improvements
│
├─ Processes:
│  ├─ Validates fixed code
│  ├─ Optimizes performance
│  ├─ Updates infrastructure
│  └─ Manages deployments
│
└─ → Deploys to production ✅
```

---

## Wait Points & Synchronization

```
                     SYNCHRONIZATION POINTS
                     
Baseline Tests Complete ↓
┌──────────────────────────────────────┐
│  WAIT: All 6 tests must finish       │
│  - lint ✅                            │
│  - unit-test ✅                       │
│  - test-playwright ✅                 │
│  - test-vitest ✅                     │
│  - test-cypress ✅                    │
│  - test-security-audit ✅             │
│  Then trigger Phase 1️⃣               │
└──────────────────────────────────────┘
             SYNC POINT 1
                 ↓
            PHASE 1️⃣ START

Phase 1 Agents Running ↓
┌──────────────────────────────────────┐
│  WAIT: Both agents must finish       │
│  - SDET Agent running... 🟡          │
│  - Compliance Agent done ✅           │
│  Wait for SDET to complete           │
│  Then trigger Phase 2️⃣              │
└──────────────────────────────────────┘
             SYNC POINT 2
                 ↓
            PHASE 2️⃣ START

Phase 2 Agent Running ↓
┌──────────────────────────────────────┐
│  WAIT: Fullstack must finish         │
│  - Fullstack Agent running... 🟡     │
│  Wait for fixes to complete          │
│  Then trigger Phase 3️⃣              │
└──────────────────────────────────────┘
             SYNC POINT 3
                 ↓
            PHASE 3️⃣ START

All Phases Complete ↓
┌──────────────────────────────────────┐
│  WORKFLOW COMPLETE ✅                │
│  All phases executed successfully    │
│  Production ready ✅                 │
└──────────────────────────────────────┘
```

---

## GitHub Actions UI View

```
When viewing your GitHub Actions workflow, you'll see:

Run #307 - feat: Implement 3-phase agent orchestration

All checks have passed ✅

Jobs:
✅ Code Linting (lint)                           1m 30s
✅ Unit Tests (unit-test)                        2m 15s
✅ Playwright Tests (test-playwright)            3m 45s
✅ Vitest Tests (test-vitest)                    1m 50s
✅ Cypress Tests (test-cypress)                  2m 30s
✅ Pa11y Accessibility Tests (test-pa11y)        1m 20s
✅ Security & Dependency Audit (test-security)  1m 10s
───────────────────────────────────────────────────────────
✅ Phase 1️⃣ SDET Agent (Testing)                 8m 30s
✅ Phase 1️⃣ Compliance Agent (Testing)           4m 15s
───────────────────────────────────────────────────────────
✅ Phase 2️⃣ Fullstack Agent (Code & Fixes)     12m 45s
───────────────────────────────────────────────────────────
✅ Phase 3️⃣ SRE Agent (Production)               7m 30s


Each phase clearly marked with emoji:
- 1️⃣ = Phase 1 (Testing)
- 2️⃣ = Phase 2 (Fixes)
- 3️⃣ = Phase 3 (Production)
```

---

## Dependency Chain in YAML

```yaml
# How Phase 1 starts
sdet-agent:
  needs:
    - unit-test
    - test-playwright
    - test-vitest
    - test-cypress
    - test-pa11y
    - test-security-audit
  # Starts when ALL above complete

compliance-agent:
  needs:
    - unit-test
    - test-playwright
    - test-vitest
    - test-cypress
    - test-pa11y
    - test-security-audit
  # Starts when ALL above complete (parallel to sdet-agent)

# How Phase 2 starts
fullstack-agent:
  needs: [sdet-agent, compliance-agent]
  # Starts when BOTH Phase 1 agents complete

# How Phase 3 starts
sre-agent:
  needs: [fullstack-agent]
  # Starts when Phase 2 completes
```

---

## Summary

The three-phase orchestration ensures:

1. ✅ **Phase 1️⃣:** Complete all testing
2. ✅ **Phase 2️⃣:** Fix all issues found
3. ✅ **Phase 3️⃣:** Deploy stable code

No race conditions, proper ordering, full context at each step.

**Status:** ✅ Live and operational
