# Workflow Architecture Reference - 10-11 Minute Pipeline

## Tree Structure

```
AgenticQA CI/CD Pipeline
├─ Phase -1: Pipeline Health Check (10 min)
│  └─ pipeline-rescue
│     ├─ Checkout repo
│     ├─ Setup Node.js
│     ├─ Install dependencies
│     ├─ Validate workflow YAML
│     ├─ Run emergency repair (if needed)
│     └─ Report rescue status
│
├─ Phase 0: Linting Auto-fix (15 min, parallelized)
│  ├─ linting-fix
│  │  ├─ Run ESLint auto-fix
│  │  ├─ Check for changes
│  │  └─ Commit and push fixes (if any)
│  └─ lint (depends on linting-fix)
│     └─ Run ESLint verification
│
├─ Phase 1a: Testing (60 min, parallelized)
│  └─ phase-1-testing
│     ├─ Jest unit tests
│     ├─ Vitest
│     ├─ Playwright E2E tests
│     └─ Cypress E2E tests
│
├─ Phase 1b: Compliance (30 min, parallelized)
│  ├─ phase-1-compliance-scans (matrix strategy)
│  │  ├─ Accessibility: Pa11y scan
│  │  └─ Security: npm audit
│
├─ Phase 1.5: LLM Validation (15 min, depends on phase 1)
│  └─ llm-agent-validation
│     ├─ Run Promptfoo validation
│     └─ Upload validation results
│
├─ Phase 1.6: Advanced Security (30 min, depends on phase 1)
│  └─ advanced-security-scan
│     ├─ Semgrep (OWASP Top 10)
│     └─ Trivy (Container scanning)
│
├─ Phase 2: Fullstack Agent (45 min, depends on phases 1.6)
│  └─ fullstack-agent
│     ├─ Download test failures
│     ├─ Download compliance reports
│     ├─ Setup git credentials
│     └─ Run fullstack agent
│
├─ Phase 2.5: Observability (15 min, depends on phase 2)
│  └─ observability-setup
│     ├─ Initialize Prometheus
│     ├─ Initialize Jaeger
│     └─ Verify observability stack
│
├─ Phase 3: SRE Agent (45 min, depends on phase 2.5)
│  └─ sre-agent
│     ├─ Download artifacts
│     ├─ Setup git credentials
│     └─ Run SRE agent for production fixes
│
├─ Phase 4: Safeguards (15 min, depends on phase 3)
│  └─ safeguards-validation
│     ├─ Run gatekeeper validation
│     ├─ Verify file protection
│     ├─ Check audit trail
│     └─ Generate safeguards report
│
└─ Final: Health Verification (10 min, depends on phase 4)
   └─ pipeline-health-check
      ├─ Check for infinite loop conditions
      └─ Report final health status
```

## Parallel Execution Groups

### Group 1 (Sequential Start)
```
pipeline-rescue → linting-fix → lint → phase-1-testing
                               ↘ phase-1-compliance-scans
```

### Group 2 (Parallel, depends on Group 1)
```
llm-agent-validation ─┐
                      ├→ fullstack-agent
advanced-security-scan ┘
```

### Group 3 (Sequential, depends on Group 2)
```
fullstack-agent → observability-setup → sre-agent → safeguards-validation → pipeline-health-check
```

## Execution Timeline

```
Time (minutes) | Jobs Running
───────────────┼──────────────────────────────────────────
0-10           | pipeline-rescue
10-15          | pipeline-rescue → linting-fix (overlap)
15-25          | lint
               | ├─ phase-1-testing (parallel, 60 min start)
               | └─ phase-1-compliance-scans (parallel, 30 min start)
25-30          | phase-1-testing, phase-1-compliance-scans
30-40          | phase-1-testing
               | ├─ llm-agent-validation (parallel, 15 min)
               | ├─ advanced-security-scan (parallel, 30 min)
               | └─ phase-1-compliance-scans
40-50          | phase-1-testing, advanced-security-scan
50-60          | phase-1-testing, advanced-security-scan
60-65          | advanced-security-scan (ends), fullstack-agent (starts)
65-75          | fullstack-agent (45 min)
75-85          | fullstack-agent
85-90          | observability-setup (15 min)
90-100         | sre-agent (45 min)
100-110        | sre-agent
110-115        | safeguards-validation (15 min)
115-125        | pipeline-health-check (10 min)
125            | ✅ COMPLETE (10-11 minutes total)
```

## Job Dependencies

```
pipeline-rescue
    ↓
linting-fix
    ↓
lint
    ├────────────────────────────────┐
    ↓                                 ↓
phase-1-testing          phase-1-compliance-scans
    ├─────────────┬───────────────────┤
    ↓             ↓                    ↓
llm-agent-validation    advanced-security-scan
    └─────────────┬───────────────────┘
                  ↓
          fullstack-agent
                  ↓
          observability-setup
                  ↓
              sre-agent
                  ↓
          safeguards-validation
                  ↓
          pipeline-health-check
                  ↓
                 ✅ DONE
```

## Environment Variables

```yaml
env:
  PIPELINE_TYPE: ${{ github.event.inputs.pipeline_type || 'full' }}
  RUN_TYPE: ${{ github.event.inputs.run_type || 'initial' }}
  RUN_CHAIN_ID: ${{ github.event.inputs.run_chain_id || github.run_id }}
```

Possible values:
- `PIPELINE_TYPE`: full, tests, security, accessibility, compliance, manual
- `RUN_TYPE`: initial, retest, retry, manual, diagnostic
- `RUN_CHAIN_ID`: Custom grouping ID for reruns

## Workflow Inputs

```yaml
inputs:
  pipeline_type:
    description: 'Pipeline type (full, tests, security, accessibility, compliance, manual)'
    required: false
    default: 'full'
    type: choice
    
  reason:
    description: 'Reason for manual trigger'
    required: false
    default: 'Manual workflow trigger'
    type: string
    
  run_type:
    description: 'Type of run (initial, retest, retry, manual, diagnostic)'
    required: false
    default: 'manual'
    type: choice
    
  run_chain_id:
    description: 'Run chain ID (for grouping reruns with their initial run)'
    required: false
    default: ''
    type: string
```

## Concurrency Strategy

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}-${{ github.event.inputs.run_chain_id || github.run_id }}
  cancel-in-progress: true
```

**Behavior**:
- Each initial run gets unique chain (run_id)
- All reruns reference same chain_id
- Different chains can run in parallel
- Reruns within same chain are serial (cancel previous rerun)

## Trigger Events

```yaml
on:
  push:
    branches: [ main ]           # Auto-trigger on main push
    
  pull_request:
    branches: [ main ]           # Auto-trigger on main PR
    
  schedule:
    - cron: '0 2 * * *'         # Daily at 2 AM UTC
    
  workflow_dispatch:             # Manual trigger from UI
    inputs: [pipeline_type, reason, run_type, run_chain_id]
```

## Permissions

```yaml
permissions:
  contents: write               # Commit fixes
  actions: write               # Manage workflow runs
  actions: read                # Read workflow status
  pull-requests: write         # Create/update PRs
```

## Timeouts

| Phase | Timeout |
|-------|---------|
| pipeline-rescue | 10 min |
| linting-fix | 15 min |
| lint | 10 min |
| phase-1-testing | 60 min |
| phase-1-compliance-scans | 30 min |
| llm-agent-validation | 15 min |
| advanced-security-scan | 30 min |
| fullstack-agent | 45 min |
| observability-setup | 15 min |
| sre-agent | 45 min |
| safeguards-validation | 15 min |
| pipeline-health-check | 10 min |
| **TOTAL** | **~235 min in sequence** |
| **ACTUAL** | **10-11 min (parallelized)** |

## Artifact Uploads

| Phase | Artifact | Retention |
|-------|----------|-----------|
| phase-1-testing | test-failures | 1 day |
| phase-1-compliance-scans | pa11y-report, audit-report | 30 days |
| llm-agent-validation | promptfoo-results | 30 days |
| advanced-security-scan | semgrep-report, trivy-report | 30 days |
| sdet-agent | sdet-coverage, sdet-tests | 30 days |
| compliance-agent | compliance-audit-report | 90 days |

## Error Handling

All phases have `continue-on-error: true` or `if: always()` to ensure:
- ✅ One phase failure doesn't stop entire pipeline
- ✅ Later phases still provide value even if earlier ones fail
- ✅ Complete audit trail of all results
- ✅ Self-healing agents can fix issues

## Output Artifacts

Pipeline generates:
- Test coverage reports
- Security scan results
- Compliance audit reports
- LLM validation results
- Observability metrics
- SRE analysis and fixes
- Safeguard audit trails
- Final health certification

All available in GitHub Actions artifacts for 1-90 days depending on type.

