# AgenticQA Quick Reference

## For Developers

### Before Pushing Code
```bash
# Validate locally
./scripts/validate_pipeline.sh

# If all green, push
git push origin main
```

### Testing Locally
```bash
# Run all local tests
pytest tests/test_local_pipeline_validation.py -v

# Test specific agent
pytest tests/test_agent_error_handling.py::TestSREAgentLintingFixes -v

# Test with Weaviate (requires Docker)
docker run -d -p 8080:8080 semitechnologies/weaviate:latest
export WEAVIATE_HOST=localhost
pytest tests/test_agent_rag_integration.py -v
```

---

## For Platform Team

### Validate Pipeline Health
```bash
# Trigger validation workflow
./scripts/trigger_pipeline_validation.sh

# Watch progress
gh run watch

# View results
gh run list --workflow=pipeline-validation.yml
```

### Monitor Nightly Validations
1. Check GitHub Actions each morning
2. Look for "Pipeline Self-Validation" workflow
3. Review health report
4. Address any failures

### After Pipeline Changes
```bash
# Always validate after modifying pipeline
vim .github/workflows/ci.yml
git commit -am "feat: update pipeline"

# Validate BEFORE pushing
./scripts/trigger_pipeline_validation.sh

# If healthy, push
git push origin main
```

---

## For Clients

### Pipeline Status
- **Main Pipeline:** Tests code on every push
- **Validation Pipeline:** Tests pipeline itself nightly
- **Health Report:** Available in GitHub Actions

### Confidence Metrics
- ✅ Pipeline validates itself automatically
- ✅ Agents self-heal errors autonomously
- ✅ 95%+ uptime target
- ✅ Continuous learning and improvement

---

## Test Frameworks

### 1. Local Validation (Fast)
**File:** `tests/test_local_pipeline_validation.py`
**Duration:** 1-2 minutes
**Purpose:** Quick checks during development

```bash
pytest tests/test_local_pipeline_validation.py -v
```

### 2. Agent Error Handling
**File:** `tests/test_agent_error_handling.py`
**Duration:** 3-5 minutes
**Purpose:** Verify self-healing works

```bash
pytest tests/test_agent_error_handling.py -v
```

### 3. RAG Integration
**File:** `tests/test_agent_rag_integration.py`
**Duration:** 5-10 minutes
**Purpose:** Verify agents learn from Weaviate

```bash
# Requires Weaviate running
pytest tests/test_agent_rag_integration.py -v
```

### 4. Meta-Validation
**File:** `tests/test_pipeline_meta_validation.py`
**Duration:** 10-20 minutes
**Purpose:** Full end-to-end with real GitHub

```bash
# Requires GH_TOKEN
export GH_TOKEN=<token>
pytest tests/test_pipeline_meta_validation.py -v
```

---

## Workflows

### Main Pipeline (ci.yml)
**Trigger:** Push, Pull Request
**Purpose:** Test code changes
**Duration:** 10-15 minutes

Jobs:
- Validate workflows
- Pipeline health check
- Auto-fix linting
- Code linting
- Tests (unit, integration)
- RAG tests
- Weaviate integration
- Agent RAG integration
- Agent error handling
- Local pipeline validation
- Data validation
- Data quality integration
- Deployment validation
- UI tests
- Final deployment gate

### Validation Pipeline (pipeline-validation.yml)
**Trigger:** Nightly (2 AM UTC), Manual
**Purpose:** Test pipeline health
**Duration:** 15-30 minutes

Jobs:
- Pipeline health check
- Test SRE agent self-healing
- Test SDET agent coverage
- Test Fullstack agent generation
- Test agent integration workflows
- Test RAG learning system
- Test pipeline tools
- Generate health report

---

## Agents

### SRE Agent
**Purpose:** Fix linting errors
**Capabilities:**
- Detect quote violations
- Fix missing semicolons
- Correct indentation
- Remove unused variables

**Test:**
```bash
pytest tests/test_agent_error_handling.py::TestSREAgentLintingFixes -v
```

### SDET Agent
**Purpose:** Analyze test coverage
**Capabilities:**
- Identify untested files
- Prioritize high-risk code
- Generate test recommendations
- Track coverage trends

**Test:**
```bash
pytest tests/test_agent_error_handling.py::TestSDETAgentCoverageAnalysis -v
```

### Fullstack Agent
**Purpose:** Generate code from requests
**Capabilities:**
- Create API endpoints
- Build UI components
- Generate utility functions
- Follow project patterns

**Test:**
```bash
pytest tests/test_agent_error_handling.py::TestFullstackAgentCodeGeneration -v
```

### QA Agent
**Purpose:** Analyze test results
**Capabilities:**
- Process test failures
- Identify patterns
- Recommend fixes
- Learn from history

### Performance Agent
**Purpose:** Monitor performance
**Capabilities:**
- Detect degradation
- Suggest optimizations
- Track metrics
- Learn patterns

### Compliance Agent
**Purpose:** Ensure compliance
**Capabilities:**
- Check security rules
- Validate data protection
- Enforce policies
- Track violations

### DevOps Agent
**Purpose:** Manage deployments
**Capabilities:**
- Health checks
- Deployment validation
- Error detection
- Recovery coordination

---

## Key Files

### Workflows
- `.github/workflows/ci.yml` - Main pipeline
- `.github/workflows/pipeline-validation.yml` - Validation pipeline

### Tests
- `tests/test_local_pipeline_validation.py` - Local validation
- `tests/test_agent_error_handling.py` - Agent self-healing
- `tests/test_agent_rag_integration.py` - RAG learning
- `tests/test_pipeline_meta_validation.py` - End-to-end validation

### Scripts
- `scripts/validate_pipeline.sh` - Local validation script
- `scripts/trigger_pipeline_validation.sh` - Trigger validation workflow

### Documentation
- `AGENT_LEARNING_SYSTEM.md` - Agent learning architecture
- `PIPELINE_TESTING_FRAMEWORK.md` - Testing framework guide
- `PIPELINE_VALIDATION_WORKFLOW.md` - Validation workflow guide
- `QUICK_REFERENCE.md` - This file

### Agents
- `src/agents.py` - All agent implementations

---

## Common Commands

```bash
# Local validation
./scripts/validate_pipeline.sh

# Trigger pipeline validation
./scripts/trigger_pipeline_validation.sh

# Run specific tests
pytest tests/test_agent_error_handling.py -v

# Watch workflow
gh run watch

# View workflow logs
gh run view <run-id>

# List recent runs
gh run list --limit 10

# Start Weaviate locally
docker run -d -p 8080:8080 semitechnologies/weaviate:latest

# Check Weaviate health
curl http://localhost:8080/v1/.well-known/ready
```

---

## Getting Help

### Documentation
- `README.md` - Project overview
- `AGENT_LEARNING_SYSTEM.md` - Agent architecture
- `PIPELINE_TESTING_FRAMEWORK.md` - Testing guide
- `PIPELINE_VALIDATION_WORKFLOW.md` - Validation guide

### Troubleshooting
Check documentation sections:
- Pipeline validation workflow troubleshooting
- Testing framework troubleshooting
- Agent learning system FAQ

### Support
- GitHub Issues: Report problems
- GitHub Discussions: Ask questions
- Documentation: Comprehensive guides
