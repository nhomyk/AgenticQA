# Agent Orchestration Pipeline - Phase-Based Execution

## 🎯 Overview

The CI/CD pipeline has been restructured to follow a **3-phase orchestration model** where agents execute sequentially with clear dependencies and wait points. This ensures thorough testing before fixes are applied, and production stability before SRE interventions.

---

## 📋 Phase Architecture

### Phase 1️⃣: Testing & Analysis (Parallel Execution)

**SDET Agent** + **Compliance Agent** run in parallel after all standard tests complete.

#### 1.1 SDET Agent (Manual QA & Codebase Analysis)
- **Trigger:** Waits for all baseline tests to complete
  - ✅ unit-test
  - ✅ test-playwright
  - ✅ test-vitest
  - ✅ test-cypress
  - ✅ test-pa11y
  - ✅ test-security-audit

- **Execution:** Performs comprehensive testing analysis
  - Manual UI testing patterns
  - Codebase analysis for edge cases
  - Coverage gap identification
  - Test recommendations

- **Artifacts Generated:**
  - `sdet-coverage/` - Coverage analysis
  - `sdet-tests/` - Generated test cases

- **Duration:** ~5-10 minutes
- **Can Fail:** Yes, but continues to next phase

#### 1.2 Compliance Agent (Legal & Regulatory Testing)
- **Trigger:** Waits for all baseline tests to complete
  - ✅ unit-test
  - ✅ test-playwright
  - ✅ test-vitest
  - ✅ test-cypress
  - ✅ test-pa11y
  - ✅ test-security-audit

- **Execution:** Performs compliance auditing
  - License compliance checks
  - Regulatory requirement verification
  - Third-party library audit
  - Security compliance validation
  - Privacy & data handling review

- **Artifacts Generated:**
  - `compliance-audit-report.md` - Detailed audit report
  - Critical issues flagged for attention

- **Duration:** ~3-5 minutes
- **Can Fail:** No, reports issues but doesn't block

---

### Phase 2️⃣: Code & Compliance Fixes (Sequential After Phase 1)

**Fullstack Agent** runs ONLY after BOTH Phase 1 agents complete.

#### 2.1 Fullstack Agent (Code & Compliance Fixes)
- **Prerequisite:** 
  - ✅ SDET Agent MUST complete (or timeout/fail)
  - ✅ Compliance Agent MUST complete (or timeout/fail)

- **Trigger:** `needs: [sdet-agent, compliance-agent]`

- **Execution:** Applies fixes based on Phase 1 findings
  - Fixes test failures identified by SDET
  - Remedies compliance issues from Compliance Agent
  - Generates missing tests
  - Updates code for compliance
  - Auto-commits fixes via git

- **Data Available:**
  - Test failure artifacts from Phase 1
  - Compliance audit report
  - Coverage analysis
  - Code analysis results

- **Duration:** ~10-15 minutes
- **Can Fail:** Yes, but continues to Phase 3

---

### Phase 3️⃣: Production & Pipeline Fixes (Sequential After Phase 2)

**SRE Agent** runs ONLY after Fullstack Agent completes.

#### 3.1 SRE Agent (Infrastructure & Production Fixes)
- **Prerequisite:** 
  - ✅ Fullstack Agent MUST complete (or timeout/fail)

- **Trigger:** `needs: [fullstack-agent]`

- **Execution:** Applies production-level fixes
  - Pipeline performance optimizations
  - Infrastructure adjustments
  - Monitoring & observability updates
  - Production deployment fixes
  - Emergency interventions if needed

- **Scope:** SRE only fixes AFTER Fullstack completes
  - Does NOT re-run testing
  - Does NOT apply code logic fixes (Fullstack handles this)
  - Focuses on infrastructure & operations

- **Duration:** ~5-10 minutes
- **Can Fail:** Logs issues, continues monitoring

---

## 🔄 Workflow Dependency Tree

```
Baseline Tests (Parallel)
├─ lint
├─ unit-test
├─ test-playwright
├─ test-vitest
├─ test-cypress
├─ test-pa11y
└─ test-security-audit
    │
    ↓
Phase 1️⃣ (Parallel - BOTH must complete)
├─ SDET Agent        (Testing & Analysis)
│   ↓
│   Artifacts:
│   - sdet-coverage
│   - sdet-tests
│
└─ Compliance Agent   (Legal & Regulatory Testing)
    ↓
    Artifacts:
    - compliance-audit-report.md
    │
    ↓
Phase 2️⃣ (Sequential - After Phase 1 completes)
└─ Fullstack Agent    (Code & Compliance Fixes)
    ↓
    Artifacts:
    - Code fixes (auto-committed)
    - Test generation
    - Compliance remediation
    │
    ↓
Phase 3️⃣ (Sequential - After Phase 2 completes)
└─ SRE Agent          (Production & Pipeline Fixes)
    ↓
    Artifacts:
    - Infrastructure updates
    - Performance optimizations
    - Deployment adjustments
```

---

## 📊 Execution Timeline

```
Time │ Baseline Tests (5-15 min)           
  0  ├─────────────────────────────────────
     │
  5  │ ✅ lint completes
  7  ├─ unit-test, test-playwright,      ┐
  8  │  test-vitest, test-cypress, etc.  │ Parallel
 15  ├─ All baseline tests done          ┘
     │
 15  │ ↓ Phase 1️⃣ Begins (Parallel - 5-10 min)
 15  ├─ SDET Agent starts
 15  ├─ Compliance Agent starts          ┐ Parallel
     │                                    ├ BOTH must
 20  ├─ Compliance Agent done ✅         │ complete
 25  └─ SDET Agent done ✅              ┘
     │
 25  │ ↓ Phase 2️⃣ Begins (Sequential - 10-15 min)
 25  ├─ Fullstack Agent starts
 40  └─ Fullstack Agent done ✅
     │
 40  │ ↓ Phase 3️⃣ Begins (Sequential - 5-10 min)
 40  ├─ SRE Agent starts
 50  └─ SRE Agent done ✅
     │
 50  └─ ✅ WORKFLOW COMPLETE

Total Pipeline Duration: ~50-60 minutes
```

---

## ✅ Guarantees & Constraints

### Guarantee 1: SDET Before Fullstack
- SDET Agent ALWAYS completes before Fullstack Agent starts
- Fullstack Agent can trust SDET analysis is complete
- No race conditions between testing and fixing

### Guarantee 2: Compliance Before Fullstack
- Compliance Agent ALWAYS completes before Fullstack Agent starts
- Fullstack Agent can apply compliance fixes with full context
- No missing compliance requirements during fixes

### Guarantee 3: Fullstack Before SRE
- Fullstack Agent ALWAYS completes before SRE Agent starts
- SRE Agent operates on code that's already been fixed
- No conflicts between code-level and infrastructure fixes

### Guarantee 4: Test Completion Before Fixes
- All baseline tests complete before ANY agent runs
- Agents work with verified test results
- No testing happens after fixes are applied (in this pipeline)

---

## 🔧 Phase Environment Variables

Each phase receives environment variables to coordinate work:

### Phase 1️⃣ Agents
```bash
# SDET Agent
# (No special PHASE variable - standard execution)

# Compliance Agent
# (No special PHASE variable - standard execution)
```

### Phase 2️⃣ Fullstack Agent
```bash
PHASE=fixes
GITHUB_TOKEN=${{ secrets.GITHUB_TOKEN }}
GITHUB_RUN_ID=${{ github.run_id }}
COMPLIANCE_MODE=enabled
```

### Phase 3️⃣ SRE Agent
```bash
PHASE=production-fixes
GITHUB_TOKEN=${{ secrets.GITHUB_TOKEN }}
GH_PAT=${{ secrets.GH_PAT }}
```

---

## 📦 Artifact Flow

### Phase 1 → Phase 2 Handoff

**From SDET Agent:**
- `sdet-coverage/` → Fullstack can see coverage gaps
- `sdet-tests/` → Fullstack can generate corresponding fixes

**From Compliance Agent:**
- `compliance-audit-report.md` → Fullstack can read audit results
- Critical issues flagged → Fullstack prioritizes fixes

**From Baseline Tests:**
- `test-failures/` → Fullstack knows what needs fixing
- Coverage reports → Fullstack understands coverage gaps

### Phase 2 → Phase 3 Handoff

**From Fullstack Agent:**
- Committed code fixes → SRE can deploy
- Generated tests → SRE can run test validation
- Auto-commits → SRE knows what changed

**From Compliance Agent:**
- Remediated compliance report → SRE sees status
- No critical issues remaining → SRE can proceed safely

---

## 🚀 Job Names with Phase Indicators

```yaml
Phase 1️⃣ SDET Agent (Testing)
├─ Job name: "Phase 1️⃣ SDET Agent (Testing)"
└─ Clearly marks phase in GitHub UI

Phase 1️⃣ Compliance Agent (Testing)
├─ Job name: "Phase 1️⃣ Compliance Agent (Testing)"
└─ Clearly marks phase in GitHub UI

Phase 2️⃣ Fullstack Agent (Code & Compliance Fixes)
├─ Job name: "Phase 2️⃣ Fullstack Agent (Code & Compliance Fixes)"
└─ Clearly marks phase in GitHub UI

Phase 3️⃣ SRE Agent (Pipeline & Production Fixes)
├─ Job name: "Phase 3️⃣ SRE Agent (Pipeline & Production Fixes)"
└─ Clearly marks phase in GitHub UI
```

---

## 🔍 Monitoring & Observability

### GitHub Actions UI Shows:
1. **Phase 1 Block:**
   - SDET Agent and Compliance Agent in parallel
   - Both must succeed (or complete) before moving forward

2. **Phase 2 Block:**
   - Fullstack Agent waits for Phase 1
   - Clearly shows it's the "Fixing" phase

3. **Phase 3 Block:**
   - SRE Agent waits for Phase 2
   - Clearly shows it's the "Production" phase

### Logs Show Phase Progression:
```
[SDET Agent] 🧪 Run SDET Agent - Test Phase
[Compliance Agent] 🛡️  Run Compliance Agent - Test Phase
[Fullstack Agent] ⏳ Waiting for Phase 1 testing to complete
[Fullstack Agent] 🔧 Run Fullstack Agent - Fix Phase
[SRE Agent] ⏳ Waiting for Phase 2 fixes to complete
[SRE Agent] 🚀 Run SRE Agent - Production Fixes Phase
```

---

## 🎯 Use Cases

### Use Case 1: New Feature Branch
1. Push to main triggers workflow
2. Phase 1: SDET tests new feature, Compliance audits new code
3. Phase 2: Fullstack applies any fixes from test findings
4. Phase 3: SRE deploys stable version

### Use Case 2: Compliance Update
1. Compliance Agent discovers license issue
2. Report goes to Phase 2
3. Fullstack Agent remediates automatically
4. SRE Agent deploys fixed version

### Use Case 3: Test Coverage Gap
1. SDET Agent identifies coverage gap
2. Recommends test cases
3. Fullstack Agent generates & adds tests
4. SRE Agent validates & deploys

### Use Case 4: Production Emergency
1. Any phase detects critical issue
2. Fullstack Agent handles code fixes (Phase 2)
3. SRE Agent handles emergency deployment (Phase 3)
4. Coordinated fix without race conditions

---

## 🔐 Permissions & Credentials

### Phase 1️⃣ Agents
- `contents: read` - Can read code
- `actions: read` - Can read workflow status
- No write permissions - Analysis only

### Phase 2️⃣ Fullstack Agent
- `contents: write` - Can commit code fixes
- `actions: read` - Can read workflow artifacts
- Git credentials configured for auto-commit

### Phase 3️⃣ SRE Agent
- `contents: write` - Can commit updates
- `actions: write` - Can update deployments
- Git & GitHub credentials for operations

---

## ⚡ Performance Optimization

### Parallelization
- Phase 1 agents run in parallel (saves ~5 minutes)
- Not blocked by each other
- Both complete before Phase 2 starts

### Sequential Phases
- Each phase waits for previous phase to complete
- Eliminates race conditions
- Ensures proper ordering of operations

### Artifact Passing
- Phase 1 artifacts available to Phase 2
- Phase 2 artifacts available to Phase 3
- Each phase has complete context

---

## 📋 Workflow Status Summary

```
Baseline Tests: REQUIRED (5-15 min)
├─ lint
├─ unit-test
├─ test-playwright
├─ test-vitest
├─ test-cypress
├─ test-pa11y
└─ test-security-audit

Phase 1️⃣ - Testing: PARALLEL (10-15 min total)
├─ SDET Agent (Testing & Analysis) - REQUIRED
└─ Compliance Agent (Audit) - REQUIRED

Phase 2️⃣ - Fixes: SEQUENTIAL (10-15 min)
└─ Fullstack Agent (Code & Compliance Fixes) - REQUIRED

Phase 3️⃣ - Production: SEQUENTIAL (5-10 min)
└─ SRE Agent (Infrastructure & Deployment) - REQUIRED
```

---

## ✨ Summary

The new orchestration ensures:

✅ **No Race Conditions** - Clear sequential phases  
✅ **Complete Testing** - All tests run before any fixes  
✅ **Compliance First** - Audit before remediating  
✅ **Proper Ordering** - Code fixes before infrastructure changes  
✅ **Full Context** - Each phase has complete artifact history  
✅ **Observable** - Clear phase indicators in GitHub UI  
✅ **Reliable** - Deterministic execution order  

**Status:** ✅ IMPLEMENTED & READY FOR DEPLOYMENT
