# 🚀 Agent Testing Quick Reference

One-page reference for running and managing agent tests.

## ⚡ Quick Commands

```bash
# Full orchestration (5 phases)
npm run test:agents

# Just tests
npm run test:agents:framework

# Just recovery
npm run test:agents:recover

# Just repair tests
npm run test:agents:repair

# Watch mode
npm run test:agents:watch
```

## 📊 Check Results

```bash
# Latest results
cat .agent-orchestration-results/orchestration-latest.json | jq '.summary'

# All results
ls -la .agent-orchestration-results/

# Recovery history
cat .agent-recovery/recovery-log.json | jq 'last'

# Test details
cat .agent-test-results/test-latest.json | jq
```

## 🔍 Troubleshoot Agent

```bash
# Check syntax
node -c agent-name.js

# Test import
node -e "require('./agent-name.js')" && echo "✅ OK"

# Run directly
node agent-name.js

# View error logs
cat .agent-recovery/recovery-log.json | jq '.[].error'
```

## 📈 Monitor Trends

```bash
# Historical pass rate
cat .agent-orchestration-results/orchestration-latest.json | jq '.summary.passRate'

# Agent stability
npm run test:agents 2>&1 | grep "HISTORICAL TRENDS" -A 5

# Failed agents
cat .agent-orchestration-results/orchestration-latest.json | jq '.agents[] | select(.status=="failing")'
```

## 🔧 Recovery Strategies

1. **Fix Imports** - Adds missing require statements
2. **Add Error Handling** - Wraps functions in try-catch
3. **Validate Exports** - Ensures module.exports
4. **Test Functionality** - Validates syntax

## ✅ Success Criteria

- **Agent Test**: ✅ All 8 tests pass
- **Recovery**: ✅ Re-tests pass after fix
- **Orchestration**: ✅ 75%+ pass rate overall

## 📁 File Locations

```
Core Files:
  agent-orchestrator.js      - Main orchestrator
  agent-test-framework.js    - Test framework
  agent-recovery-system.js   - Recovery system
  agent-tests.js            - Repair tests

Results:
  .agent-orchestration-results/   - Full results
  .agent-recovery/               - Recovery logs
  .agent-test-results/           - Test details

Docs:
  AGENT_TESTING_SYSTEM.md        - User guide
  AGENT_TESTING_INTEGRATION_GUIDE.md - CI/CD setup
```

## 🎯 Common Tasks

**Run before committing:**
```bash
npm run test:agents
```

**Check if agents are healthy:**
```bash
npm run test:agents 2>&1 | grep "Pass Rate"
```

**Recover failed agents:**
```bash
npm run test:agents:recover
```

**Monitor continuously:**
```bash
npm run test:agents:watch
```

**Get detailed diagnostics:**
```bash
npm run test:agents:framework
```

## 🔌 CI/CD Command

Add to `.github/workflows/ci.yml`:
```yaml
- name: Run Agent Tests
  run: npm run test:agents
```

## 📞 Help

- Full guide: `AGENT_TESTING_SYSTEM.md`
- Integration: `AGENT_TESTING_INTEGRATION_GUIDE.md`
- Status: `AGENT_TESTING_DEPLOYMENT.md`

---

**Last Run**: Check `.agent-orchestration-results/orchestration-latest.json`  
**Version**: 1.0.0  
**Status**: ✅ Production Ready
