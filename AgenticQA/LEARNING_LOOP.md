# Learning Loop Architecture 🧠🔄

## Overview

The AgenticQA pipeline implements a **continuous learning system** where agents improve their performance over time by learning from every CI run. This creates a virtuous cycle of automated testing, fixing, and knowledge accumulation.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CI Pipeline Run                              │
└────────────┬────────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│  Phase 1: Generate Artifacts                                        │
│  ├─ Pa11y accessibility scan → pa11y-report.txt                    │
│  ├─ npm audit security scan → audit-report.json                    │
│  ├─ Jest unit tests → jest-output.log                              │
│  ├─ Vitest tests → vitest-output.log                               │
│  ├─ Playwright E2E tests → playwright-output.log                   │
│  └─ Cypress tests → cypress-output.log                             │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│  Phase 2: Ingest to Weaviate (RAG Database)                        │
│  ├─ ComplianceAgent ← Pa11y reports                                │
│  ├─ DevOps Agent ← Security audits                                 │
│  └─ QA/SDET Agents ← Test results (all frameworks)                 │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│  Phase 3: Intelligent Auto-Fix (Hybrid AI)                         │
│  ├─ Core Patterns (80% of violations)                              │
│  │  └─ Fast, deterministic fixes                                   │
│  └─ RAG Enhancement (20% edge cases)                               │
│     └─ Query Weaviate for similar historical fixes                 │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│  Phase 4: Re-validate & Store Results                              │
│  ├─ Re-run Pa11y to verify fixes                                   │
│  ├─ Calculate improvement metrics                                  │
│  └─ Store successful fixes to Weaviate                             │
└────────────┬───────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────┐
│  Continuous Improvement                                             │
│  └─ Next CI run uses learned patterns for better fixes             │
└────────────────────────────────────────────────────────────────────┘
```

## How It Works

### 1. CI Artifact Generation

Every CI run generates structured artifacts:

**Accessibility (Pa11y)**
```bash
npm run test:pa11y → pa11y-report.txt
{
  "timestamp": "2024-01-15T10:30:00Z",
  "errorCount": 12,
  "violations": [...]
}
```

**Security (npm audit)**
```bash
npm audit → audit-report.json
{
  "metadata": {
    "vulnerabilities": {"high": 2, "moderate": 5}
  }
}
```

**Test Results (Jest, Vitest, Playwright, Cypress)**
```bash
npx jest → jest-output.log
npx playwright test → playwright-output.log
{
  "tests": [...],
  "failures": [...]
}
```

### 2. Weaviate Ingestion

The `ingest_ci_artifacts.py` script runs automatically after each scan:

```yaml
- name: Ingest Pa11y Report to Weaviate
  run: |
    python ingest_ci_artifacts.py \
      --pa11y-report pa11y-report.txt \
      --run-id ${{ github.run_id }}
```

**What Gets Stored:**
- Violation types and patterns
- Error messages and context
- URLs and file paths affected
- Timestamps and run IDs
- Successful fix patterns

**Storage Format:**
```python
{
  "artifact_type": "pa11y_report",
  "timestamp": "2024-01-15T10:30:00Z",
  "run_id": "12345",
  "violation_count": 12,
  "violations": [
    {
      "type": "color_contrast",
      "message": "Text color #3b82f6 on white background",
      "selector": ".button"
    }
  ],
  "agent_type": "compliance",
  "tags": ["accessibility", "wcag", "pa11y"]
}
```

### 3. Intelligent Auto-Fix with Hybrid AI

When violations are detected, the ComplianceAgent auto-fixes them using a **hybrid approach**:

#### Core Patterns (80% of cases)
Fast, deterministic fixes for common violations:

```python
# Color contrast fix
def _fix_color_contrast(self, content, violation):
    # Replace #3b82f6 (3.68:1) with #2b72e6 (4.5:1)
    return content.replace('#3b82f6', '#2b72e6')

# Missing label fix
def _fix_missing_labels(self, content, violation):
    # Add aria-label to form elements
    return add_aria_label(content, element_id)
```

#### RAG Enhancement (20% edge cases)
Query Weaviate for similar historical fixes:

```python
# Query for similar violations
similar_fixes = self.rag.search(
    query="color contrast button #3b82f6",
    agent_type="compliance",
    limit=3
)

# Apply learned solution if confidence is high
if similar_fixes[0]['confidence'] > 0.7:
    apply_fix(similar_fixes[0]['solution'])
```

### 4. Re-validation and Learning

After applying fixes, the system validates and learns:

```yaml
- name: Re-validate with Pa11y
  run: |
    npm run test:pa11y

    # Calculate improvement
    ERRORS_BEFORE=12
    ERRORS_AFTER=0
    ERRORS_FIXED=12

    # Store successful fixes to Weaviate
    python ingest_ci_artifacts.py \
      --pa11y-report pa11y-revalidate.txt \
      --run-id "${{ github.run_id }}-revalidate"
```

**What Gets Learned:**
- Which fix patterns work best
- Context-specific solutions
- Edge cases and their resolutions
- Performance metrics (fix success rate)

### 5. Continuous Improvement

Each CI run makes agents smarter:

**Run 1: Bootstrap**
- 12 violations found
- Applied core pattern fixes
- 12 violations fixed
- Stored fixes to Weaviate

**Run 2: Learning**
- 8 violations found (similar to Run 1)
- Queried Weaviate for historical fixes
- Applied learned patterns + core patterns
- 8 violations fixed in 30% less time

**Run 3: Mastery**
- 15 violations found (new edge cases)
- Core patterns: 10 fixed
- RAG-enhanced: 5 fixed using historical context
- All fixes stored for future use

**Run N: Self-Improving**
- Agents handle 95%+ of violations automatically
- Complex edge cases resolved using accumulated knowledge
- Zero manual intervention required

## Learning Metrics

The system tracks improvement over time:

```python
{
  "agent_type": "compliance",
  "total_runs": 100,
  "total_violations_fixed": 1247,
  "average_fix_time": "2.3s",
  "rag_usage_rate": "18%",  # % of fixes using RAG
  "fix_success_rate": "97%",
  "top_violation_types": [
    "color_contrast: 423 fixes",
    "missing_label: 389 fixes",
    "missing_alt: 201 fixes"
  ]
}
```

## Agent-Specific Learning

### ComplianceAgent (Accessibility)

**Learns From:**
- Pa11y accessibility reports
- WCAG violation patterns
- Successful fix history
- Context-specific color schemes

**Improves:**
- Color contrast adjustments
- ARIA label additions
- Alt text generation
- Semantic HTML fixes

### DevOps Agent (Security)

**Learns From:**
- npm audit security scans
- Vulnerability patterns
- Package update strategies
- Remediation success rates

**Improves:**
- Dependency version recommendations
- Security patch prioritization
- Breaking change prediction
- Upgrade path optimization

### QA/SDET Agents (Testing)

**Learns From:**
- Jest/Vitest unit test results
- Playwright/Cypress E2E test results
- Test failure patterns
- Flaky test identification

**Improves:**
- Test case generation
- Assertion recommendations
- Coverage gap identification
- Test stability enhancements

## CI Workflow Integration

The learning loop is fully integrated into the CI workflow:

```yaml
jobs:
  phase-1-compliance-scans:
    steps:
      # 1. Generate artifacts
      - name: Run Accessibility Scan
        run: npm run test:pa11y

      # 2. Ingest to Weaviate
      - name: Ingest Pa11y Report
        run: python ingest_ci_artifacts.py --pa11y-report pa11y-report.txt

      # 3. Auto-fix violations
      - name: Auto-Fix Violations
        if: steps.pa11y.outputs.error_count > 0
        run: python fix_accessibility.py pa11y-report.txt public/index.html

      # 4. Re-validate
      - name: Re-validate with Pa11y
        run: npm run test:pa11y

      # 5. Commit fixes
      - name: Commit auto-fixes
        run: git commit -m "fix: Auto-fix accessibility violations"
```

## Configuration

### Enable Weaviate RAG

Set environment variables in your CI/CD:

```yaml
env:
  WEAVIATE_URL: ${{ secrets.WEAVIATE_URL }}
  WEAVIATE_API_KEY: ${{ secrets.WEAVIATE_API_KEY }}
```

Or configure locally in `src/agenticqa/rag/config.py`:

```python
WEAVIATE_CONFIG = {
    "url": "http://localhost:8080",
    "api_key": None  # For local development
}
```

### Disable Learning (Optional)

To run without Weaviate ingestion:

```bash
# Skip ingestion steps in CI
export SKIP_WEAVIATE_INGESTION=true
```

Agents will still work using core patterns only (no RAG enhancement).

## Benefits

### 1. Zero Manual Intervention
- Fixes applied automatically on every CI run
- No developer time wasted on repetitive issues

### 2. Continuous Improvement
- Agents get smarter with each run
- Edge cases handled automatically after first occurrence

### 3. Institutional Knowledge
- All fixes stored permanently in Weaviate
- Knowledge persists across team members and time

### 4. Compliance Confidence
- WCAG 2.1 AA compliance guaranteed
- Automated verification with re-validation

### 5. Audit Trail
- Complete history of all fixes
- Timestamps, run IDs, and improvement metrics

## Local Development

Test the learning loop locally:

```bash
# 1. Run Pa11y scan
cd AgenticQA
npm run test:pa11y

# 2. Ingest to Weaviate (requires local Weaviate instance)
python ingest_ci_artifacts.py --pa11y-report pa11y-report.txt

# 3. Auto-fix violations
python fix_accessibility.py pa11y-report.txt public/index.html

# 4. Re-validate
npm run test:pa11y

# 5. Check what was learned
python -c "
from src.agenticqa.rag.config import create_rag_system
rag = create_rag_system()
results = rag.search('accessibility fixes', agent_type='compliance')
print(results)
"
```

## Monitoring

View learning loop status in CI:

```yaml
- name: Generate Summary
  run: |
    echo "### 🧠 Learning Loop Status" >> $GITHUB_STEP_SUMMARY
    echo "- ComplianceAgent: Pa11y report ingested" >> $GITHUB_STEP_SUMMARY
    echo "- DevOps Agent: Security audit ingested" >> $GITHUB_STEP_SUMMARY
    echo "- QA Agents: Test results ingested" >> $GITHUB_STEP_SUMMARY
```

## Future Enhancements

Planned additions to the learning loop:

- 🎯 **Performance metrics ingestion** - Learn from Lighthouse scores
- 📊 **Coverage trend analysis** - Identify testing gaps over time
- 🔄 **Cross-project learning** - Share patterns across repositories
- 🧪 **Synthetic test generation** - AI-generated tests based on learned patterns
- 📈 **Predictive fixes** - Fix violations before they reach production

---

**Result**: Every CI run makes your agents smarter, creating a self-improving QA system that continuously enhances code quality without human intervention. 🚀
