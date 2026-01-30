# Agent Collaboration (Tier 3)

## Overview

AgenticQA agents can now **autonomously collaborate** by delegating tasks to specialized agents. This mimics how real engineering teams work: specialists consult each other's expertise to solve complex problems.

## Architecture

```
┌─────────────────┐
│  SDET Agent     │  "I found coverage gaps"
│  (Coverage)     │
└────────┬────────┘
         │ delegates
         ▼
┌─────────────────┐
│  SRE Agent      │  "I'll generate tests for those gaps"
│  (Code Quality) │
└─────────────────┘
```

## Safety Guardrails

All delegations are protected by built-in safety mechanisms:

### 1. Max Depth Limit
- **Limit**: 3 levels deep
- **Prevents**: Infinite delegation chains
- **Example**: SDET → SRE → (stops here)

### 2. Circular Detection
- **Prevents**: Agent A → Agent B → Agent A loops
- **Action**: Immediately rejects circular delegations

### 3. Delegation Budget
- **Limit**: 5 total delegations per request
- **Prevents**: Cost explosions from runaway delegations

### 4. Authorization Whitelist
- **Only whitelisted delegations allowed**
- **Conservative by design**

## Allowed Delegations

Current whitelist (conservative start):

| Source Agent | Can Delegate To | Use Case |
|-------------|-----------------|----------|
| **SDET** | SRE | Test generation for coverage gaps |
| **Fullstack** | Compliance | Code validation for regulatory compliance |
| **Compliance** | DevOps | Deployment security consultation |

Agents not listed **cannot delegate** (prevents loops).

## Usage Examples

### Example 1: SDET Delegates Test Generation

```python
from src.agents import SDETAgent, SREAgent
from src.agenticqa.collaboration import AgentRegistry

# Setup collaboration
registry = AgentRegistry()
sdet = SDETAgent()
sre = SREAgent()

registry.register_agent(sdet)
registry.register_agent(sre)
registry.reset_for_new_request("SDET_Agent")

# SDET identifies coverage gap
coverage_data = {
    "file": "src/api.py",
    "coverage_percentage": 45,
    "uncovered_lines": [10, 15, 20],
    "high_risk": True
}

# SDET delegates test generation to SRE specialist
tests = sdet.delegate_to_agent("SRE_Agent", {
    "task": "generate_tests",
    "file": coverage_data["file"],
    "lines": coverage_data["uncovered_lines"]
})

# Get delegation summary
summary = registry.get_delegation_summary()
print(f"Delegation path:\n{summary['delegation_path']}")
```

### Example 2: Fullstack Validates with Compliance

```python
# Fullstack generates code, validates with Compliance
fullstack = FullstackAgent()
compliance = ComplianceAgent()

registry.register_agent(fullstack)
registry.register_agent(compliance)

# Generate authentication code
code = fullstack.execute({
    "feature": "user_authentication",
    "requirements": ["JWT", "password hashing"]
})

# Validate for GDPR compliance
validation = fullstack.delegate_to_agent("Compliance_Agent", {
    "context": "code_validation",
    "regulations": ["GDPR", "PCI_DSS"],
    "encrypted": True,
    "pii_masked": True,
    "audit_enabled": True
})

if "violations" in validation and len(validation["violations"]) == 0:
    print("✅ Code is compliant!")
```

### Example 3: Query Agent Expertise

```python
# Lightweight consultation (no full delegation)
advice = compliance.query_agent_expertise("DevOps_Agent", {
    "question": "Is this deployment config secure?",
    "config": deployment_config
})
```

## Delegation Tracking

Every delegation is tracked for observability:

```python
summary = registry.get_delegation_summary()

# Available data:
{
    "root_agent": "SDET_Agent",
    "total_delegations": 1,
    "successful": 1,
    "failed": 0,
    "max_depth": 1,
    "total_duration_ms": 1234,
    "delegation_path": """
    SDET_Agent
      └─ ✅ SRE_Agent
    """,
    "events": [
        {
            "from_agent": "SDET_Agent",
            "to_agent": "SRE_Agent",
            "duration_ms": 1234,
            "success": True
        }
    ]
}
```

## Error Handling

Delegations can fail for several reasons:

```python
from src.agenticqa.collaboration import (
    CircularDelegationError,
    MaxDelegationDepthError,
    UnauthorizedDelegationError,
    DelegationError
)

try:
    result = agent.delegate_to_agent("OtherAgent", task)
except CircularDelegationError:
    # Agent tried to create a loop
    pass
except MaxDelegationDepthError:
    # Delegation chain too deep (>3 levels)
    pass
except UnauthorizedDelegationError:
    # Agent not whitelisted to delegate to target
    pass
except DelegationError as e:
    # Other delegation failure
    pass
```

## Quality Evaluation

Delegation quality is evaluated using Ragas metrics:

- **Delegation Quality**: Faithfulness of delegated results
- **Collaboration Coherence**: Context preservation across hops
- **Multi-hop Chains**: Quality of complex delegation paths

See [test_ragas_evaluation.py](../tests/test_ragas_evaluation.py) for details.

## Pipeline Validation

Agent collaboration is validated nightly at 2 AM UTC:

✅ **Delegation Safety Guardrails**
- Max depth enforcement
- Circular detection
- Budget limits
- Authorization

✅ **Collaboration Workflows**
- SDET → SRE
- Fullstack → Compliance
- Compliance → DevOps

✅ **Observability**
- Delegation tracking
- Chain visualization
- Quality metrics

## Expanding Collaboration

To add new delegation paths:

1. **Update whitelist** in `src/agenticqa/collaboration/delegation.py`:
   ```python
   ALLOWED_DELEGATIONS = {
       "MyAgent": ["SpecialistAgent"],  # Add new path
   }
   ```

2. **Add tests** in `tests/test_agent_delegation.py`

3. **Run pipeline validation** to ensure safety

## Best Practices

1. **Use delegation for specialization**: Don't delegate what you can do yourself
2. **Keep chains short**: 1-2 hops is ideal
3. **Monitor costs**: Each delegation = potential LLM API call
4. **Check before delegating**: Use `can_delegate_to()` to validate
5. **Handle failures gracefully**: Always catch `DelegationError`

## Future Enhancements

Potential future capabilities:
- Dynamic delegation routing (agent learns optimal delegation)
- Delegation cost prediction
- Parallel delegations (fan-out/fan-in)
- Delegation replay for debugging
- Cross-team agent collaboration

## Architecture Benefits

**Why Tier 3 Matters:**

1. **True Specialization**: Each agent focuses on their expertise
2. **Emergent Intelligence**: Agents discover optimal workflows
3. **Real Engineering Teams**: Mimics how humans collaborate
4. **Quality Improvement**: Specialists provide better results than generalists

**AgenticQA's Differentiator:**
> "Agents that autonomously collaborate—just like a real engineering team."
