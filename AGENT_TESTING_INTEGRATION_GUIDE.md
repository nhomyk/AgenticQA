# Agent Testing & Recovery Integration Guide

## Overview

This guide explains how to integrate the agent testing and recovery system into your CI/CD pipeline for automated quality assurance and self-healing capabilities.

## Components

### 1. **Agent Test Framework** (`agent-test-framework.js`)
- Runs 8 standardized tests per agent
- Tests: File existence, syntax validity, require-ability, exports, dependencies, configuration, error handling, functionality
- Automatic recovery with up to 2 retry attempts
- Results saved to `.agent-test-results/` with JSON format

### 2. **Agent Repair Tests** (`agent-tests.js`)
- Agent-specific functionality tests
- Per-agent test suites for: Fullstack, SRE, Compliance, SDET, QA agents
- Detailed pass/fail reporting

### 3. **Agent Recovery System** (`agent-recovery-system.js`)
- Detects agent failures automatically
- Implements 4 recovery strategies:
  1. **Fix Imports** - Adds missing require statements
  2. **Add Error Handling** - Wraps functions in try-catch blocks
  3. **Validate Exports** - Ensures proper module exports
  4. **Test Functionality** - Validates agent syntax and structure

### 4. **Agent Orchestrator** (`agent-orchestrator.js`)
- Coordinates testing, failure detection, and recovery
- 5-phase process:
  1. Run agent tests
  2. Analyze results
  3. Recover failed agents
  4. Re-test recovered agents
  5. Generate final report
- Tracks historical trends and agent stability

## Integration Steps

### Step 1: Add Agent Testing Job to CI/CD

Add this to `.github/workflows/ci.yml` after Phase 1 tests:

```yaml
  agent-validation:
    name: Agent Validation & Recovery
    runs-on: ubuntu-latest
    needs: [test]
    if: always()
    
    steps:
      - name: Checkout
        uses: actions/checkout@v3
      
      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: '20'
          cache: 'npm'
      
      - name: Install Dependencies
        run: npm ci
      
      - name: Run Agent Orchestration
        run: node agent-orchestrator.js
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Upload Test Results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: agent-test-results
          path: |
            .agent-test-results/
            .agent-recovery/
            .agent-orchestration-results/
          retention-days: 30
```

### Step 2: Add Automatic Recovery Hook

Add to `.github/workflows/ci.yml` in case of critical failures:

```yaml
  agent-recovery:
    name: Agent Auto-Recovery
    runs-on: ubuntu-latest
    needs: [agent-validation]
    if: failure()
    
    steps:
      - name: Checkout
        uses: actions/checkout@v3
      
      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: '20'
          cache: 'npm'
      
      - name: Attempt Agent Recovery
        run: node agent-recovery-system.js
      
      - name: Commit Recovery Changes
        if: success()
        run: |
          git config --local user.email "agent@agenticqa.dev"
          git config --local user.name "AgenticQA Auto-Recovery"
          git add -A
          git commit -m "fix: Auto-recover failed agents" || true
          git push
```

### Step 3: Setup Local Testing

Run tests locally before pushing:

```bash
# Test all agents
node agent-orchestrator.js

# Run specific agent tests
node agent-test-framework.js

# Run individual agent repair tests
node agent-tests.js

# Run recovery system directly
node agent-recovery-system.js
```

### Step 4: Monitor Agent Health

Check historical trends:

```bash
# View latest test results
cat .agent-orchestration-results/orchestration-latest.json

# View recovery logs
cat .agent-recovery/recovery-log.json

# View test details
ls -la .agent-test-results/
```

## Usage Patterns

### Pattern 1: Local Pre-Commit Validation

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "🧪 Running agent tests..."
if ! node agent-orchestrator.js; then
  echo "❌ Agent tests failed - attempting recovery"
  node agent-recovery-system.js
  exit 1
fi
exit 0
```

### Pattern 2: Daily Automated Testing

Add to your local scheduler or use GitHub Actions schedule:

```yaml
schedule:
  - cron: '0 2 * * *'  # Daily at 2 AM UTC
```

### Pattern 3: On-Demand Testing

```bash
# Manual trigger
npm run test:agents

# With recovery
npm run test:agents:recover
```

### Pattern 4: Pull Request Validation

```yaml
on:
  pull_request:
    branches: [main, develop]

jobs:
  agent-validation:
    # (same as above)
```

## Recovery Strategies

### Strategy 1: Fix Imports
- Detects missing `fs`, `path` imports
- Detects missing config references
- Automatically adds required imports

### Strategy 2: Add Error Handling
- Wraps async functions in try-catch blocks
- Adds proper error logging
- Ensures graceful shutdown on errors

### Strategy 3: Validate Exports
- Ensures module.exports exists
- Adds main entry points if missing
- Validates export syntax

### Strategy 4: Test Functionality
- Runs syntax validation
- Checks for fatal errors
- Validates module loading

## Success Criteria

### For Passing an Agent Test:
- ✅ File exists and is readable
- ✅ Syntax is valid (no parsing errors)
- ✅ Can be required/imported
- ✅ Has proper exports
- ✅ All dependencies are available
- ✅ Configuration is valid
- ✅ Has error handling
- ✅ Passes functionality tests

### For Successful Recovery:
- ✅ At least 3 out of 4 recovery strategies succeed
- ✅ Agent re-tests pass after recovery
- ✅ No new errors introduced

### For Orchestration Success:
- ✅ All agents pass testing or successfully recover
- ✅ Overall pass rate ≥ 75%
- ✅ No unrecoverable critical errors

## Troubleshooting

### Agent Tests Failing

1. **Check agent syntax**
   ```bash
   node -c path/to/agent.js
   ```

2. **Check agent dependencies**
   ```bash
   npm ls --depth=0
   ```

3. **Check agent exports**
   ```bash
   grep -E "module\.exports|export default" path/to/agent.js
   ```

### Recovery System Not Working

1. **Check recovery logs**
   ```bash
   cat .agent-recovery/recovery-log.json | jq '.[0]'
   ```

2. **Run recovery directly**
   ```bash
   node agent-recovery-system.js
   ```

3. **Check for permission issues**
   ```bash
   ls -la agent*.js
   ```

### Orchestrator Hangs

1. **Check for infinite loops in agents**
   ```bash
   timeout 30 node agent-orchestrator.js
   ```

2. **Check system resources**
   ```bash
   ps aux | grep node
   ```

## Configuration

### Environment Variables

```bash
# Enable debug logging
export DEBUG=agentic:*

# Set recovery timeout (ms)
export RECOVERY_TIMEOUT=30000

# Set test timeout (ms)
export TEST_TIMEOUT=10000

# GitHub token for SRE agent features
export GITHUB_TOKEN=your-token-here

# Slack notification on failures (optional)
export SLACK_WEBHOOK_URL=your-webhook-url
```

### Agent-Specific Configuration

See individual agent files for their configuration options.

## Monitoring & Reporting

### Real-Time Monitoring

```bash
# Watch test results in real-time
watch -n 5 'cat .agent-orchestration-results/orchestration-latest.json | jq .summary'
```

### Historical Analysis

```bash
# Generate trends report
node -e "
  const Orchestrator = require('./agent-orchestrator');
  const o = new Orchestrator();
  console.log(JSON.stringify(o.generateTrends(), null, 2));
"
```

### Integration with Monitoring Systems

Results can be parsed by monitoring tools:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "summary": {
    "totalAgents": 6,
    "totalTests": 48,
    "totalPassed": 45,
    "totalFailed": 3,
    "passRate": 93.75,
    "agentsRecovered": 1
  }
}
```

## Best Practices

1. **Run orchestrator before each commit**
   - Catch agent issues early
   - Prevent broken pushes

2. **Review recovery logs regularly**
   - Identify patterns
   - Improve recovery strategies

3. **Monitor trends over time**
   - Track agent stability
   - Plan improvements

4. **Keep agent files clean**
   - Remove dead code
   - Update dependencies

5. **Document agent-specific setup**
   - Configuration requirements
   - Environment variables needed

## Next Steps

1. Add agent validation job to CI/CD pipeline
2. Test locally with `node agent-orchestrator.js`
3. Monitor results in `.agent-orchestration-results/`
4. Adjust recovery strategies based on findings
5. Integrate historical trend analysis
6. Setup notifications on failures

## Support

For issues or questions:
- Check `.agent-recovery/recovery-log.json` for error details
- Review `.agent-test-results/` for individual test results
- Run `node agent-recovery-system.js` for diagnostics
- Check individual agent files for specific configuration
