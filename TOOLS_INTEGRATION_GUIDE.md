# Integration Guide: New Testing & Observability Tools

## Overview

Your pipeline now includes 5 enterprise-grade open source tools for comprehensive agent testing and observability:

### Tools Added

| Tool | Purpose | Status | Integration |
|------|---------|--------|-------------|
| **Promptfoo** | LLM prompt validation | Phase 1.5 | npm run test:promptfoo |
| **Semgrep** | OWASP/CWE security scanning | Phase 1.6 | npm run scan:semgrep |
| **Trivy** | Container image vulnerability scanning | Phase 1.6 | npm run scan:trivy |
| **Prometheus** | Metrics collection & monitoring | Phase 2.5 | docker-compose up |
| **Jaeger** | Distributed tracing for agents | Phase 2.5 | docker-compose up |

---

## 1. Promptfoo - LLM Agent Validation

**What it does:** Tests your agent prompts and validates output consistency.

### Usage

```bash
npm run test:promptfoo
```

### Configuration
Edit [promptfoo-config.yml](promptfoo-config.yml) to:
- Add more test cases for agent prompts
- Validate agent outputs match expected patterns
- Test edge cases and error scenarios

### Example Tests
- ✅ Agent generates valid Jest tests
- ✅ Agent identifies accessibility issues  
- ✅ Agent produces valid JSON output
- ✅ Agent correctly validates security patterns

### Results
Output saved to `promptfoo-results.json` and uploaded as artifact in CI/CD.

---

## 2. Semgrep - OWASP Top 10 & CWE Scanning

**What it does:** Scans code for OWASP Top 10 and CWE vulnerabilities.

### Usage

```bash
npm run scan:semgrep
# Or standalone:
semgrep --config=p/owasp-top-ten --json --output semgrep-report.json .
```

### Integration

Runs automatically in CI/CD Phase 1.6 after all Phase 1 tests complete.

### Output
- **File:** `semgrep-report.json`
- **Severity Levels:** Critical, High, Medium, Low
- **Artifact Retention:** 30 days

### Custom Rules

Add custom Semgrep rules to `.semgrep.yml`:

```yaml
rules:
  - id: hardcoded-credentials
    pattern: |
      password = "..."
    message: "Hardcoded credentials detected"
    severity: CRITICAL
```

---

## 3. Trivy - Container Image Vulnerability Scanning

**What it does:** Scans Docker images for known vulnerabilities.

### Usage

```bash
npm run docker:build
npm run scan:trivy
# Or standalone:
trivy image agentic-qa:latest --severity HIGH,CRITICAL
```

### Integration

Runs in CI/CD Phase 1.6:
1. Builds Docker image (`npm run docker:build`)
2. Scans with Trivy
3. Reports HIGH and CRITICAL vulnerabilities
4. Saves results to `trivy-report.json`

### Output Fields
- **Vulnerability ID** - CVE number
- **Severity** - CRITICAL, HIGH, MEDIUM, LOW
- **Package** - Affected dependency
- **Fixed Version** - Update recommendation

---

## 4. Prometheus - Metrics Collection

**What it does:** Collects and stores metrics from your agent pipeline.

### Setup

```bash
# Start with docker-compose
npm run docker:run

# View Prometheus UI
open http://localhost:9090
```

### Configuration
Edit [prometheus.yml](prometheus.yml) to add more scrape targets:

```yaml
scrape_configs:
  - job_name: 'agentic-qa'
    static_configs:
      - targets: ['localhost:3000']
```

### Metrics to Track

Add these metrics to your agent code for collection:

```javascript
// Example: Track agent test generation
const testGenerationTime = new prometheus.Histogram({
  name: 'agent_test_generation_seconds',
  help: 'Time taken to generate tests',
  buckets: [0.1, 0.5, 1, 2, 5]
});

// Track agent success rate
const agentSuccessRate = new prometheus.Counter({
  name: 'agent_success_total',
  help: 'Total successful agent runs'
});
```

### Useful Queries

```promql
# Agent test generation rate
rate(agent_tests_generated_total[5m])

# Agent success percentage  
(agent_success_total / agent_runs_total) * 100

# Average response time
histogram_quantile(0.95, agent_response_time_seconds)
```

---

## 5. Jaeger - Distributed Tracing

**What it does:** Traces agent requests through the entire pipeline for debugging.

### Setup

```bash
# Start with docker-compose
npm run docker:run

# View Jaeger UI
open http://localhost:16686
```

### Instrumentation

Add tracing to your agent code:

```javascript
const tracer = require('./tracing').tracer;

function generateTests() {
  const span = tracer.startSpan('generate-tests');
  
  try {
    // Your agent logic
    span.setTag('tests.count', 42);
    span.setTag('duration.ms', 500);
  } finally {
    span.finish();
  }
}
```

### Trace Visualization

Jaeger UI shows:
- **Service map** - Agent to database to external APIs
- **Request latency** - Time spent in each component
- **Error tracking** - Failed spans with error details
- **Dependency analysis** - Which agents call which services

---

## 6. Pydantic - Input/Output Validation

**What it does:** Validates agent-generated code and test cases.

### Setup

```bash
# Python validation (optional, for advanced validation)
pip install pydantic>=2.0

# Or use Node version via Zod (already in dependencies)
```

### Schemas

Review [pydantic-validation.py](pydantic-validation.py) for schemas:

- `TestCase` - Validates individual test cases
- `AgentOutput` - Validates agent output structure
- `ComplianceIssue` - Validates security findings
- `SecurityScanResult` - Validates scan results

### Usage Example

```python
from pydantic_validation import TestCase, AgentOutput

# Validate agent output
try:
    output = AgentOutput(
        status="success",
        tests_generated=5,
        issues_found=0,
        test_cases=[...]
    )
    print("✓ Output is valid")
except ValidationError as e:
    print("✗ Validation failed:", e)
```

---

## Pipeline Phases Overview

### Phase 1: Testing & Scanning
- ✅ Jest, Vitest, Playwright, Cypress tests
- ✅ Pa11y accessibility scanning  
- ✅ npm audit security scanning
- ✅ **1.5: Promptfoo LLM validation** (NEW)
- ✅ **1.6: Semgrep + Trivy scanning** (NEW)

### Phase 1.5: LLM Validation
- Validates agent prompts work correctly
- Tests agent output consistency
- Ensures JSON/code generation is valid

### Phase 1.6: Advanced Security
- OWASP Top 10 scanning with Semgrep
- Container image vulnerability scanning with Trivy
- CWE vulnerability detection

### Phase 2: Fixing & Remediation
- SDET Agent generates tests
- Compliance Agent audits compliance
- Fullstack Agent fixes issues

### Phase 2.5: Observability
- Prometheus metrics collection
- Jaeger distributed tracing setup

### Phase 3: SRE & Production
- SRE Agent handles production issues
- Pipeline monitoring and healing

### Phase 4: Safeguards
- Final validation of all agent changes
- Enterprise safety checks

---

## Local Development

### Run All Tests Locally

```bash
# Install dependencies
npm ci

# Run all tests
npm test

# Run specific tool
npm run test:promptfoo
npm run scan:semgrep
npm run scan:trivy

# Start observability stack
npm run docker:run
```

### View Results

```bash
# Test results
cat promptfoo-results.json
cat semgrep-report.json
cat trivy-report.json

# Metrics (requires running stack)
open http://localhost:9090

# Tracing (requires running stack)
open http://localhost:16686
```

---

## Troubleshooting

### Promptfoo fails
```bash
# Ensure OpenAI key is set
export OPENAI_API_KEY=your_key

# Run with verbose logging
npx promptfoo eval -c promptfoo-config.yml --verbose
```

### Semgrep not found
```bash
# Install semgrep
pip install semgrep
# or
brew install semgrep
```

### Trivy fails on image
```bash
# Ensure Docker is running and image exists
npm run docker:build
docker images | grep agentic-qa
```

### Prometheus not collecting metrics
```bash
# Check config file
cat prometheus.yml

# Check target is reachable
curl http://localhost:3000/metrics
```

### Jaeger shows no traces
```bash
# Ensure instrumentation is in place
# Check Jaeger agent is running
docker logs agentic-qa-jaeger

# Verify tracing exports are configured
```

---

## Next Steps

1. **Run pipeline:** `npm run docker:run` then monitor at localhost:9090 and localhost:16686
2. **Configure alerts:** Add alert rules to `prometheus.yml` 
3. **Add custom metrics:** Instrument agents to export Prometheus metrics
4. **Set up dashboards:** Create Grafana dashboards from Prometheus data
5. **Fine-tune rules:** Adjust Semgrep and Trivy rules for your codebase

---

## References

- [Promptfoo Docs](https://www.promptfoo.dev/)
- [Semgrep Docs](https://semgrep.dev/docs/)
- [Trivy Docs](https://aquasecurity.github.io/trivy/)
- [Prometheus Docs](https://prometheus.io/docs/)
- [Jaeger Docs](https://www.jaegertracing.io/docs/)
- [Pydantic Docs](https://docs.pydantic.dev/)
