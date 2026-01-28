# Pipeline Testing Framework

## Overview

AgenticQA includes a **comprehensive pipeline testing framework** that validates the CI/CD pipeline itself by intentionally introducing errors and verifying agents fix them autonomously.

This is **meta-testing** - testing that the framework works correctly end-to-end.

---

## Three Levels of Testing

### 1. Local Validation Tests ([test_local_pipeline_validation.py](tests/test_local_pipeline_validation.py))

**Purpose:** Fast validation of tools and agents during development

**What it tests:**
- Linting tools detect violations correctly
- Coverage tools measure accurately
- Agents process tool output correctly
- Agent-tool integration works
- Deployment gates are enforceable

**When to use:** Before pushing code, during development

**How to run:**
```bash
# Run all local validation tests
pytest tests/test_local_pipeline_validation.py -v

# Or use the convenience script
./scripts/validate_pipeline.sh
```

**Example tests:**
- `test_eslint_detects_quote_violations` - Verifies linter works
- `test_sdet_agent_identifies_coverage_gaps` - Verifies SDET agent functions
- `test_linting_to_sre_agent_flow` - Verifies tool → agent integration

---

### 2. Agent Error Handling Tests ([test_agent_error_handling.py](tests/test_agent_error_handling.py))

**Purpose:** Verify agents handle errors and self-heal correctly

**What it tests:**
- SRE Agent detects and fixes linting errors
- SDET Agent identifies coverage gaps and recommends tests
- Fullstack Agent generates code from feature requests
- Agents recover from failures gracefully
- Agent workflows integrate correctly (SRE → SDET → Fullstack)

**When to use:** Before pushing, in CI

**How to run:**
```bash
pytest tests/test_agent_error_handling.py -v
```

**Example tests:**
- `test_sre_agent_applies_quote_fix` - Throws linting error, verifies fix
- `test_fullstack_agent_generates_api_code` - Feature request → Code generation
- `test_sdet_agent_identifies_high_priority_gaps` - Coverage gap detection

---

### 3. Pipeline Meta-Validation Tests ([test_pipeline_meta_validation.py](tests/test_pipeline_meta_validation.py))

**Purpose:** Full end-to-end validation of the entire CI/CD pipeline

**What it tests:**
- Real GitHub workflow triggers
- Real commits with intentional errors
- Agents fix errors and create new commits
- New workflows are triggered after fixes
- Complete self-healing cycle works

**When to use:** In CI, for comprehensive validation

**How to run:**
```bash
# Requires: GH_TOKEN, write access to repo, gh CLI
pytest tests/test_pipeline_meta_validation.py -v -s
```

**Example tests:**
- `test_sre_agent_fixes_linting_errors_end_to_end`:
  1. Creates test branch with linting errors
  2. Pushes to GitHub
  3. Triggers workflow
  4. Verifies SRE agent fixes errors
  5. Verifies new commit is created
  6. Verifies new workflow is triggered
  7. Cleans up test branch

- `test_fullstack_agent_generates_code_from_feature_request`:
  1. Creates branch with FEATURE_REQUEST.json
  2. Triggers workflow
  3. Verifies Fullstack agent generates code
  4. Verifies generated code is valid

---

## Test Framework Components

### GitHubWorkflowManager

Manages GitHub workflow operations via `gh` CLI:

```python
workflow_mgr = GitHubWorkflowManager()

# Trigger workflow
run_id = workflow_mgr.trigger_workflow("ci.yml", "test-branch")

# Monitor progress
status = workflow_mgr.get_workflow_status(run_id)

# Wait for completion
conclusion = workflow_mgr.wait_for_workflow_completion(run_id)
```

### TestBranchManager

Creates test branches with intentional errors:

```python
branch_mgr = TestBranchManager()

# Create test branch
branch_mgr.create_test_branch("test/linting-errors")

# Introduce errors
branch_mgr.introduce_linting_error()  # Creates file with linting errors
branch_mgr.introduce_coverage_gap()   # Creates untested code
branch_mgr.introduce_feature_request() # Creates feature request file

# Push to trigger pipeline
branch_mgr.commit_and_push("test/linting-errors", "test: intentional errors")

# Cleanup
branch_mgr.cleanup_test_branch("test/linting-errors")
```

---

## Quick Start Guide

### For Developers

**Before pushing code:**
```bash
# Run local validation
./scripts/validate_pipeline.sh

# If all tests pass, you're good to push!
git push origin main
```

### For CI/CD

The pipeline automatically runs:
1. **Local validation tests** - Fast checks (1-2 min)
2. **Agent error handling tests** - Medium checks (3-5 min)
3. **Agent RAG integration tests** - With real Weaviate (5-10 min)

### For Comprehensive Testing

**Run full meta-validation** (requires GitHub access):
```bash
export GH_TOKEN=<your-github-token>
pytest tests/test_pipeline_meta_validation.py -v -s
```

---

## Test Examples

### Example 1: Validate SRE Agent Fixes Linting

```python
def test_sre_agent_fixes_linting_local():
    """Test SRE Agent fixes linting errors"""
    from src.agents import SREAgent

    agent = SREAgent()

    # Intentional linting errors
    linting_data = {
        "file_path": "test.js",
        "errors": [
            {"rule": "quotes", "message": "Use double quotes", "line": 1},
            {"rule": "semi", "message": "Missing semicolon", "line": 2}
        ]
    }

    # Agent should fix them
    result = agent.execute(linting_data)

    assert result["total_errors"] == 2
    assert result["fixes_applied"] >= 1
    assert result["status"] in ["success", "partial"]

    # Fixes should be logged to Weaviate for learning
    assert result["rag_insights_used"] >= 0
```

### Example 2: Validate SDET Agent Identifies Coverage Gaps

```python
def test_sdet_agent_finds_untested_code():
    """Test SDET Agent identifies critical untested files"""
    from src.agents import SDETAgent

    agent = SDETAgent()

    # Simulate coverage report with gaps
    coverage_data = {
        "coverage_percent": 65,  # Below 80% threshold
        "uncovered_files": [
            "src/api/payment.js",    # Critical - payment logic!
            "src/services/billing.js" # Critical - billing logic!
        ],
        "test_type": "integration"
    }

    result = agent.execute(coverage_data)

    # Should identify as insufficient
    assert result["coverage_status"] == "insufficient"

    # Should identify high-priority gaps
    high_priority_gaps = [g for g in result["gaps"] if g.get("priority") == "high"]
    assert len(high_priority_gaps) >= 2

    # Should provide recommendations
    assert len(result["recommendations"]) > 0
```

### Example 3: Validate Full Pipeline (Meta-Test)

```python
def test_full_pipeline_with_real_github():
    """End-to-end test with real GitHub workflow"""
    workflow_mgr = GitHubWorkflowManager()
    branch_mgr = TestBranchManager()

    # Create test branch with errors
    test_branch = "test/pipeline-validation-20250127"
    branch_mgr.create_test_branch(test_branch)
    branch_mgr.introduce_linting_error()
    branch_mgr.commit_and_push(test_branch, "test: intentional errors")

    # Trigger workflow
    run_id = workflow_mgr.trigger_workflow("ci.yml", test_branch)

    # Wait for auto-fix job
    conclusion = workflow_mgr.wait_for_workflow_completion(run_id, timeout_minutes=15)

    # Verify job completed (may be success or failure, but should complete)
    assert conclusion in ["success", "failure", "cancelled"]

    # Cleanup
    branch_mgr.cleanup_test_branch(test_branch)
```

---

## Validation Script

Use `./scripts/validate_pipeline.sh` for quick validation:

```bash
#!/bin/bash
# Runs comprehensive local validation

# 1. Install dependencies
pip install pytest pytest-cov

# 2. Run local validation tests
pytest tests/test_local_pipeline_validation.py -v

# 3. Run agent error handling tests
pytest tests/test_agent_error_handling.py -v

# 4. Optional: Test RAG integration (if Weaviate running)
if curl -s http://localhost:8080/v1/.well-known/ready; then
    pytest tests/test_agent_rag_integration.py -v
fi

# 5. Report results
echo "✅ PIPELINE VALIDATION COMPLETE"
```

---

## CI Integration

The pipeline automatically runs these tests:

```yaml
# .github/workflows/ci.yml

jobs:
  agent-error-handling:
    name: Agent Error Handling & Self-Healing Tests
    steps:
      - name: Test SRE Agent Linting Fixes
        run: pytest tests/test_agent_error_handling.py::TestSREAgentLintingFixes -v

      - name: Test Fullstack Agent Code Generation
        run: pytest tests/test_agent_error_handling.py::TestFullstackAgentCodeGeneration -v

      - name: Test SDET Agent Coverage Analysis
        run: pytest tests/test_agent_error_handling.py::TestSDETAgentCoverageAnalysis -v

  agent-rag-integration:
    name: Agent RAG Integration Tests
    services:
      weaviate:
        image: semitechnologies/weaviate:latest
    steps:
      - name: Run Agent RAG Integration Tests
        run: pytest tests/test_agent_rag_integration.py -v
```

---

## Test Categories

### Unit Tests (Fast, No Dependencies)
- Individual tool validation
- Agent initialization
- Basic functionality

**Run:** `pytest -m unit -v`

### Integration Tests (Medium, Mocked Dependencies)
- Tool → Agent integration
- Agent workflows
- Data quality checks

**Run:** `pytest -m integration -v`

### Meta Tests (Slow, Real GitHub/Weaviate)
- Full pipeline validation
- Real workflow triggers
- End-to-end self-healing

**Run:** `pytest tests/test_pipeline_meta_validation.py -v`

---

## Troubleshooting

### Tests fail with "ESLint not available"
```bash
npm install -g eslint
# Or skip: pytest -k "not eslint"
```

### Tests fail with "Weaviate not configured"
```bash
# Start Weaviate locally
docker run -d -p 8080:8080 semitechnologies/weaviate:latest

# Set environment
export WEAVIATE_HOST=localhost
export WEAVIATE_PORT=8080
```

### Meta-tests fail with "gh CLI not available"
```bash
# Install gh CLI
brew install gh  # macOS
# Or: https://cli.github.com/

# Authenticate
gh auth login
```

### Tests are slow
```bash
# Run only fast tests
pytest -m fast -v

# Run only local validation (no Weaviate/GitHub)
pytest tests/test_local_pipeline_validation.py -v
```

---

## Best Practices

### 1. Run Local Validation Before Pushing
```bash
./scripts/validate_pipeline.sh
```

### 2. Add New Tools? Add Validation Tests
```python
def test_new_tool_works():
    """Test new tool detects issues correctly"""
    # Test tool functionality
    # Verify agent can process tool output
```

### 3. Add New Agents? Add Error Handling Tests
```python
def test_new_agent_handles_errors():
    """Test new agent handles errors gracefully"""
    # Introduce intentional error
    # Verify agent detects and fixes
    # Verify RAG insights used
```

### 4. Test Agent Workflows
```python
def test_agent_workflow_integration():
    """Test agents work together"""
    # Tool → Agent 1 → Agent 2 → Result
    # Verify end-to-end flow
```

---

## Summary

The pipeline testing framework provides **three layers of validation**:

1. **Local Validation** - Fast checks during development
2. **Agent Error Handling** - Self-healing verification
3. **Meta-Validation** - Full end-to-end with real GitHub

**Before pushing:**
```bash
./scripts/validate_pipeline.sh
```

**In CI:**
- Automatic validation on every push
- Real Weaviate integration tests
- Agent error handling tests

**For comprehensive testing:**
```bash
pytest tests/test_pipeline_meta_validation.py -v -s
```

This ensures the CI/CD pipeline works correctly before clients use it.
