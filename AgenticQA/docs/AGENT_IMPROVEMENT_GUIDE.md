# Agent Delegation Improvement Guide

This guide shows how to use AgenticQA's analytics dashboard to identify and fix delegation issues.

## 🎯 Problem: Low Success Rate Between Agents

### Example: Performance_Agent → DevOps_Agent (33% success)

**Root Cause Analysis:**
1. **Task Mismatch**: Performance_Agent delegates "load_test" to DevOps_Agent
2. **Wrong Expertise**: Load testing should be handled by Performance_Agent or QA_Agent
3. **High Latency**: >4000ms indicates resource contention or timeouts

**Dashboard Evidence:**
- **Performance tab**: Shows DevOps_Agent as bottleneck
- **Network tab**: Red edge between Performance → DevOps (low success)
- **Ontology tab**: Shows this path violates expected workflow

---

## 🔧 Improvement Strategy 1: Fix Task Routing

### Before (Bad):
```python
# Performance_Agent incorrectly delegates load testing
delegation = await self.delegate(
    to_agent="DevOps_Agent",
    task_type="load_test",
    task_data={"target": "api.example.com"}
)
```

### After (Good):
```python
# Use GraphRAG to find the right agent
from agenticqa.graph import HybridGraphRAG

graphrag = HybridGraphRAG()
recommendation = graphrag.recommend_agent(
    from_agent="Performance_Agent",
    task_type="load_test",
    context={"target": "api.example.com"}
)

# Delegate to recommended agent (likely Performance_Agent itself or QA_Agent)
delegation = await self.delegate(
    to_agent=recommendation["agent"],
    task_type="load_test",
    task_data={"target": "api.example.com"}
)
```

---

## 🛡️ Improvement Strategy 2: Add Guardrails

Prevent bad delegations before they happen:

```python
class DelegationGuardrails:
    """Prevent common delegation mistakes"""

    # Define which agents should handle which tasks
    TASK_AGENT_MAP = {
        "load_test": ["Performance_Agent", "QA_Agent"],
        "deploy": ["DevOps_Agent", "SRE_Agent"],
        "generate_tests": ["SDET_Agent", "QA_Agent"],
        "security_scan": ["Compliance_Agent", "SDET_Agent"],
        "validate_code": ["QA_Agent", "Fullstack_Agent"],
        "monitor": ["SRE_Agent", "DevOps_Agent"],
    }

    @classmethod
    def validate_delegation(cls, from_agent: str, to_agent: str, task_type: str) -> dict:
        """
        Validate delegation before executing.

        Returns:
            {"valid": bool, "reason": str, "suggestion": str}
        """
        allowed_agents = cls.TASK_AGENT_MAP.get(task_type, [])

        if not allowed_agents:
            return {
                "valid": True,
                "reason": "Unknown task type, allowing delegation",
                "suggestion": None
            }

        if to_agent not in allowed_agents:
            return {
                "valid": False,
                "reason": f"{to_agent} not suitable for {task_type}",
                "suggestion": f"Consider delegating to: {', '.join(allowed_agents)}"
            }

        return {"valid": True, "reason": "Valid delegation", "suggestion": None}


# Usage in agent code
from agenticqa.delegation import DelegationGuardrails

validation = DelegationGuardrails.validate_delegation(
    from_agent="Performance_Agent",
    to_agent="DevOps_Agent",
    task_type="load_test"
)

if not validation["valid"]:
    logger.warning(f"Invalid delegation: {validation['reason']}")
    logger.info(f"Suggestion: {validation['suggestion']}")
    # Delegate to suggested agent instead
    to_agent = DelegationGuardrails.TASK_AGENT_MAP["load_test"][0]
```

---

## 🔄 Improvement Strategy 3: Implement Retry Logic

For transient failures:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class ResilientDelegation:
    """Add retry logic for failed delegations"""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def delegate_with_retry(
        self,
        to_agent: str,
        task_type: str,
        task_data: dict
    ):
        """
        Delegate with automatic retry on failure.

        Retries 3 times with exponential backoff:
        - Attempt 1: immediate
        - Attempt 2: wait 4s
        - Attempt 3: wait 8s
        """
        result = await self.delegate(
            to_agent=to_agent,
            task_type=task_type,
            task_data=task_data
        )

        if not result.success:
            raise DelegationError(f"Delegation failed: {result.error}")

        return result
```

---

## 🚦 Improvement Strategy 4: Circuit Breaker Pattern

Stop delegating to failing agents:

```python
from circuitbreaker import circuit

class CircuitBreakerDelegation:
    """Prevent cascading failures"""

    # Open circuit after 5 failures, try again after 60s
    @circuit(failure_threshold=5, recovery_timeout=60, expected_exception=DelegationError)
    async def delegate_with_circuit_breaker(
        self,
        to_agent: str,
        task_type: str,
        task_data: dict
    ):
        """
        Delegate with circuit breaker protection.

        If DevOps_Agent fails 5 times in a row, circuit opens
        and all future delegations are rejected for 60 seconds.
        """
        result = await self.delegate(
            to_agent=to_agent,
            task_type=task_type,
            task_data=task_data
        )

        if not result.success:
            raise DelegationError(f"Delegation to {to_agent} failed")

        return result
```

---

## 📊 Improvement Strategy 5: Use Dashboard Analytics

### Step 1: Identify Problem Paths

**Dashboard → Performance Tab:**
- Find agents with low success rates
- Identify slow delegations (>4000ms)

**Dashboard → Ontology Tab:**
- Check "Design Violations" section
- Look for unexpected delegation patterns

### Step 2: Query Neo4j for Details

```python
from agenticqa.graph import DelegationGraphStore

store = DelegationGraphStore()
store.connect()

# Find all failing delegations for a specific path
failing_delegations = store.get_failing_delegations(
    from_agent="Performance_Agent",
    to_agent="DevOps_Agent",
    task_type="load_test"
)

for delegation in failing_delegations:
    print(f"Failed at: {delegation['timestamp']}")
    print(f"Error: {delegation['error_message']}")
    print(f"Duration: {delegation['duration_ms']}ms")
    print("---")
```

### Step 3: Implement Fix

Based on analytics, choose appropriate strategy:
- **Task mismatch** → Use guardrails
- **Transient failures** → Add retry logic
- **Consistent failures** → Use circuit breaker
- **Wrong agent** → Use GraphRAG recommendations

---

## 🎯 Improvement Strategy 6: Self-Optimization

Make agents learn from failures:

```python
class SelfOptimizingAgent:
    """Agent that learns from delegation history"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.graph_store = DelegationGraphStore()
        self.graph_store.connect()

    async def smart_delegate(self, task_type: str, task_data: dict):
        """
        Automatically choose best delegation target based on history.
        """
        # Get historical success rates for this task type
        candidates = self.graph_store.get_best_agents_for_task(
            task_type=task_type,
            min_success_rate=0.7,  # Only consider agents with >70% success
            min_count=3  # Must have at least 3 historical delegations
        )

        if not candidates:
            # Fallback to GraphRAG recommendation
            from agenticqa.graph import HybridGraphRAG
            graphrag = HybridGraphRAG()
            recommendation = graphrag.recommend_agent(
                from_agent=self.agent_id,
                task_type=task_type,
                context=task_data
            )
            target_agent = recommendation["agent"]
        else:
            # Use most successful agent from history
            target_agent = candidates[0]["agent"]

        # Delegate with monitoring
        result = await self.delegate(
            to_agent=target_agent,
            task_type=task_type,
            task_data=task_data
        )

        return result
```

---

## 🏗️ Improvement Strategy 7: Add Capability Matching

Ensure agents have the required capabilities:

```python
class CapabilityMatcher:
    """Match tasks to agents based on capabilities"""

    AGENT_CAPABILITIES = {
        "SDET_Agent": ["generate_tests", "validate_tests", "security_scan"],
        "SRE_Agent": ["deploy", "monitor", "rollback", "incident_response"],
        "Fullstack_Agent": ["implement_feature", "code_review", "refactor"],
        "Compliance_Agent": ["security_scan", "audit", "compliance_check"],
        "DevOps_Agent": ["deploy", "ci_cd", "infrastructure"],
        "QA_Agent": ["validate_code", "manual_test", "regression_test"],
        "Performance_Agent": ["load_test", "benchmark", "optimize"],
    }

    @classmethod
    def find_capable_agents(cls, task_type: str) -> list[str]:
        """Find all agents capable of handling this task"""
        return [
            agent for agent, capabilities in cls.AGENT_CAPABILITIES.items()
            if task_type in capabilities
        ]

    @classmethod
    def choose_best_agent(cls, task_type: str, from_agent: str) -> str:
        """Choose best agent for task based on capabilities and history"""
        capable_agents = cls.find_capable_agents(task_type)

        if not capable_agents:
            raise ValueError(f"No agents capable of handling {task_type}")

        # Query Neo4j for historical success rates
        store = DelegationGraphStore()
        success_rates = {}

        for agent in capable_agents:
            rate = store.get_success_rate(from_agent=from_agent, to_agent=agent)
            success_rates[agent] = rate

        # Return agent with highest success rate
        return max(success_rates, key=success_rates.get)
```

---

## 📈 Monitoring Improvements

Add alerting for delegation issues:

```python
class DelegationMonitor:
    """Monitor delegation health and alert on issues"""

    def __init__(self):
        self.store = DelegationGraphStore()
        self.store.connect()

    def check_health(self) -> dict:
        """Run health checks on all delegation paths"""
        issues = []

        # Check for low success rates
        low_success = self.store.get_delegation_success_rate_by_pair(limit=100)
        for pair in low_success:
            if pair["success_rate"] < 0.5:  # Less than 50% success
                issues.append({
                    "severity": "high",
                    "type": "low_success_rate",
                    "from": pair["from_agent"],
                    "to": pair["to_agent"],
                    "rate": pair["success_rate"],
                    "recommendation": "Review task routing or add retry logic"
                })

        # Check for slow delegations
        slow = self.store.find_bottleneck_agents(slow_threshold_ms=3000.0)
        for agent in slow:
            issues.append({
                "severity": "medium",
                "type": "slow_delegation",
                "agent": agent["agent"],
                "avg_duration": agent["avg_duration"],
                "recommendation": "Optimize agent performance or increase timeout"
            })

        # Check for unusual patterns
        self_delegations = self.store.find_self_delegations()
        for agent in self_delegations:
            issues.append({
                "severity": "low",
                "type": "self_delegation",
                "agent": agent["agent"],
                "count": agent["count"],
                "recommendation": "Review agent logic to avoid self-delegation"
            })

        return {
            "healthy": len(issues) == 0,
            "issues": issues,
            "total_issues": len(issues)
        }

    def alert_if_unhealthy(self):
        """Send alerts if health check fails"""
        health = self.check_health()

        if not health["healthy"]:
            for issue in health["issues"]:
                logger.warning(
                    f"Delegation issue detected: {issue['type']} "
                    f"(severity: {issue['severity']})"
                )
                logger.info(f"Recommendation: {issue['recommendation']}")


# Run health check periodically
monitor = DelegationMonitor()
monitor.alert_if_unhealthy()
```

---

## 🚀 Quick Wins

### Fix Performance → DevOps Issue Now:

1. **Update populate_dashboard.py** to fix the data:
   ```python
   # Change this:
   ("Performance_Agent", "DevOps_Agent", "load_test", "failed", 5000),

   # To this (Performance does its own load testing):
   ("Performance_Agent", "Performance_Agent", "load_test", "success", 2000),
   ```

2. **Add guardrails** to prevent future mistakes

3. **Use GraphRAG** recommendations in your agent code

4. **Monitor** with the dashboard's Ontology tab to catch violations early

---

## 📚 Summary

**Immediate Actions:**
1. ✅ Use GraphRAG recommendations for delegations
2. ✅ Add guardrails to validate delegations
3. ✅ Implement retry logic for transient failures

**Medium-term:**
4. ✅ Add circuit breakers for failing paths
5. ✅ Implement capability matching
6. ✅ Add self-optimization based on history

**Long-term:**
7. ✅ Build automated monitoring and alerting
8. ✅ Implement A/B testing for delegation strategies
9. ✅ Use ML to predict optimal delegation paths

**Use the Dashboard:**
- **Performance tab**: Find bottlenecks
- **Ontology tab**: Identify design violations
- **GraphRAG tab**: Get AI recommendations
- **Live Activity**: Monitor in real-time

The key is to use your Neo4j analytics to continuously improve agent behavior!
