# 🤖 Agent Testing & Auto-Recovery System

Complete automated testing and self-healing framework for all agents in the AgenticQA platform.

## 🎯 Overview

This system ensures all agents (Fullstack, SRE, Compliance, SDET, QA) are functioning correctly by:

1. **Running comprehensive tests** on each agent
2. **Detecting failures** automatically
3. **Recovering failed agents** with intelligent repair strategies
4. **Re-testing recovered agents** to verify fixes
5. **Generating reports** with trends and recommendations

## 🚀 Quick Start

### Run Full Orchestration

```bash
npm run test:agents
```

This runs the complete 5-phase process:
- Phase 1: Test all agents
- Phase 2: Analyze results
- Phase 3: Recover failures
- Phase 4: Re-test recovered agents
- Phase 5: Generate report

### Run Individual Components

```bash
# Run only the test framework
npm run test:agents:framework

# Run agent-specific repair tests
npm run test:agents:repair

# Run recovery system directly
npm run test:agents:recover

# Watch mode (runs every 5 seconds)
npm run test:agents:watch
```

## 📁 System Components

### 1. Agent Test Framework (`agent-test-framework.js`)

Comprehensive testing suite with 8 tests per agent:

```
✅ File Exists - Verifies agent file is present
✅ Syntax Valid - Checks for JavaScript syntax errors
✅ Can Require - Tests module can be imported
✅ Has Exports - Verifies proper module exports
✅ Dependencies Available - Checks all imports are resolvable
✅ Configuration Valid - Validates agent configuration
✅ Error Handling - Ensures proper error handling
✅ Functionality Test - Runs agent-specific functionality checks
```

**Results**: Saved to `.agent-test-results/` with JSON format

### 2. Agent Repair Tests (`agent-tests.js`)

Agent-specific test suites:

- **Fullstack Agent**: Code analysis, test generation, git operations
- **SRE Agent**: Workflow monitoring, version management, failure detection
- **Compliance Agent**: Compliance checking, report generation
- **SDET Agent**: Test analysis, QA logic
- **QA Agent**: Quality assurance testing, feedback system

**Results**: Pass/fail counts, percentage scores, detailed reporting

### 3. Agent Recovery System (`agent-recovery-system.js`)

Automatic failure detection and repair with 4 strategies:

```
Strategy 1: Fix Imports
  └─ Adds missing fs, path, and other required imports

Strategy 2: Add Error Handling
  └─ Wraps functions in try-catch blocks
  └─ Ensures graceful error handling

Strategy 3: Validate Exports
  └─ Ensures proper module.exports
  └─ Adds missing main entry points

Strategy 4: Test Functionality
  └─ Validates syntax
  └─ Checks for fatal errors
```

### 4. Agent Orchestrator (`agent-orchestrator.js`)

Coordinates the complete testing and recovery workflow:

```
Phase 1: Run Agent Tests
  ├─ Test all 6 agents
  ├─ Capture results
  └─ Save initial results

Phase 2: Analyze Results
  ├─ Identify failures
  ├─ Categorize by severity
  └─ Generate failure list

Phase 3: Recover Failed Agents
  ├─ Run recovery strategies
  ├─ Attempt repairs
  └─ Log recovery attempts

Phase 4: Re-Test Recovered Agents
  ├─ Test fixed agents
  ├─ Verify recovery
  └─ Update results

Phase 5: Generate Report
  ├─ Compile final metrics
  ├─ Generate recommendations
  └─ Save historical data
```

## 📊 Output & Results

### Test Results Directory

```
.agent-test-results/
├── test-results-[timestamp].json     # Individual test results
├── test-latest.json                  # Latest test snapshot
└── test-summary.txt                  # Human-readable summary

.agent-recovery/
├── recovery-log.json                 # All recovery attempts
└── recovery-latest.json              # Latest recovery state

.agent-orchestration-results/
├── orchestration-[timestamp].json    # Full orchestration results
└── orchestration-latest.json         # Current orchestration snapshot
```

### Example Results JSON

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
  },
  "agents": {
    "fullstack-agent.js": {
      "status": "passing",
      "tests": { "passed": 8, "failed": 0, "total": 8 },
      "passRate": 100
    },
    "agentic_sre_engineer.js": {
      "status": "failing",
      "tests": { "passed": 6, "failed": 2, "total": 8 },
      "passRate": 75
    }
  }
}
```

## 🔧 Recovery Strategies in Detail

### Strategy 1: Fix Imports

Automatically detects and adds missing imports:

```javascript
// Before
const filePath = './config.json';
const data = fs.readFileSync(filePath);

// After
const fs = require('fs');
const path = require('path');
const filePath = './config.json';
const data = fs.readFileSync(filePath);
```

### Strategy 2: Add Error Handling

Wraps main functions in try-catch:

```javascript
// Before
async function agenticSRELoop() {
  const workflow = await getLatestWorkflow();
  await analyzeWorkflow(workflow);
}

// After
async function agenticSRELoop() {
  try {
    const workflow = await getLatestWorkflow();
    await analyzeWorkflow(workflow);
  } catch (error) {
    console.error('Agent error:', error.message);
    process.exit(1);
  }
}
```

### Strategy 3: Validate Exports

Ensures proper module exports and main entry:

```javascript
// Before
async function agenticSRELoop() {
  // function body
}

// After
async function agenticSRELoop() {
  // function body
}

if (require.main === module) {
  agenticSRELoop().catch(console.error);
}
```

### Strategy 4: Test Functionality

Validates syntax and basic functionality:

```javascript
try {
  new Function(agentContent);  // Syntax check
  require(agentPath);          // Import check
  // Agent is functional
} catch (err) {
  // Agent needs repair
}
```

## 📈 Monitoring & Trends

### View Historical Trends

```bash
node -e "
  const Orchestrator = require('./agent-orchestrator');
  const o = new Orchestrator();
  const trends = o.generateTrends();
  console.log(JSON.stringify(trends, null, 2));
"
```

### Example Trends Output

```json
{
  "averagePassRate": 94.2,
  "agentStability": {
    "fullstack-agent.js": { "stability": 100, "runs": 15 },
    "agentic_sre_engineer.js": { "stability": 88.5, "runs": 15 },
    "compliance-agent.js": { "stability": 92, "runs": 15 }
  },
  "trend": "improving"
}
```

## 🔍 Troubleshooting

### Agent Tests Failing

1. **Check agent syntax**
   ```bash
   node -c agent-name.js
   ```

2. **Check recovery logs**
   ```bash
   cat .agent-recovery/recovery-log.json | jq 'last'
   ```

3. **Run recovery directly**
   ```bash
   node agent-recovery-system.js
   ```

### Orchestrator Hangs

1. **Check for infinite loops**
   ```bash
   timeout 60 npm run test:agents
   ```

2. **Check system resources**
   ```bash
   ps aux | grep node
   ```

### Results Not Saving

1. **Check directory permissions**
   ```bash
   ls -la .agent-test-results/
   ```

2. **Manually create directories**
   ```bash
   mkdir -p .agent-test-results
   mkdir -p .agent-recovery
   mkdir -p .agent-orchestration-results
   ```

## 🐳 CI/CD Integration

### Add to GitHub Actions

```yaml
agent-validation:
  name: Agent Testing & Recovery
  runs-on: ubuntu-latest
  
  steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-node@v3
      with:
        node-version: '20'
        cache: 'npm'
    
    - run: npm ci
    - run: npm run test:agents
    
    - uses: actions/upload-artifact@v3
      if: always()
      with:
        name: agent-results
        path: |
          .agent-test-results/
          .agent-recovery/
          .agent-orchestration-results/
```

## 📝 Success Criteria

### Agent Test Pass
- ✅ File exists and is readable
- ✅ Syntax is valid
- ✅ Can be imported/required
- ✅ Has proper exports
- ✅ All dependencies available
- ✅ Configuration is valid
- ✅ Has error handling
- ✅ Passes functionality tests

### Recovery Success
- ✅ At least 3 out of 4 strategies succeed
- ✅ Agent re-tests pass
- ✅ No new errors introduced

### Orchestration Success
- ✅ All agents pass or recover
- ✅ Pass rate ≥ 75%
- ✅ No unrecoverable errors

## 📚 Agent Details

### Fullstack Agent
- **File**: `fullstack-agent.js`
- **Tests**: Code analysis, test generation, git operations
- **Recovery**: Import fixes, error handling, export validation

### SRE Agent
- **File**: `agentic_sre_engineer.js`
- **Tests**: Workflow monitoring, version management, failure detection
- **Recovery**: Config validation, dependency checks

### Compliance Agent
- **File**: `compliance-agent.js`
- **Tests**: Compliance checking, GDPR/CCPA validation
- **Recovery**: Rule validation, report generation

### SDET Agent
- **File**: `sdet-agent.js`
- **Tests**: Test analysis, QA logic
- **Recovery**: Test framework validation

### QA Agent
- **File**: `qa-agent.js`
- **Tests**: Quality assurance, feedback system
- **Recovery**: Test suite validation

## 🎯 Best Practices

1. **Run tests regularly**
   - Before each commit
   - In CI/CD pipeline
   - On schedule (daily/weekly)

2. **Monitor recovery logs**
   - Check for patterns
   - Improve recovery strategies
   - Document recurring issues

3. **Track trends**
   - Monitor pass rates
   - Identify declining agents
   - Plan improvements

4. **Keep agents clean**
   - Remove dead code
   - Update dependencies
   - Document changes

5. **Alert on failures**
   - Email notifications
   - Slack alerts
   - Dashboard metrics

## 🚨 Failure Response

When an agent fails:

1. **Automatic Detection** (< 1 second)
   - Failure identified
   - Type categorized
   - Recovery initiated

2. **Automatic Recovery** (< 5 seconds)
   - Recovery strategies executed
   - Up to 4 repair attempts
   - Results logged

3. **Re-Testing** (< 5 seconds)
   - Fixed agent re-tested
   - Verification completed
   - Results updated

4. **Reporting** (< 1 second)
   - Report generated
   - Recommendations provided
   - Notifications sent

## 📞 Support & Debugging

### Get Detailed Diagnostics

```bash
# Show test framework diagnostics
node -e "
  const Framework = require('./agent-test-framework');
  const f = new Framework();
  f.runAllTests().then(results => {
    console.log(JSON.stringify(results, null, 2));
  });
"
```

### Check Agent-Specific Issues

```bash
# Validate specific agent
node -e "
  const fs = require('fs');
  const content = fs.readFileSync('agent-name.js', 'utf8');
  try {
    new Function(content);
    console.log('✅ Syntax valid');
  } catch (e) {
    console.log('❌ Syntax error:', e.message);
  }
"
```

### Review Recovery Attempts

```bash
# Show last 5 recovery attempts
cat .agent-recovery/recovery-log.json | \
  jq 'last(5)' | \
  jq '.[] | {agent, timestamp, success, strategies: [.strategies[].name]}'
```

## 🔗 Related Documentation

- [Agent Testing Integration Guide](./AGENT_TESTING_INTEGRATION_GUIDE.md)
- [Self-Healing Pipeline Architecture](./SELF_HEALING_LINEAR_PIPELINE.md)
- [DevOps Transformation Summary](./DEVOPS_TRANSFORMATION_COMPLETE.md)

---

**Last Updated**: January 2024  
**System Version**: 1.0.0  
**Status**: ✅ Production Ready
