# Extending Pattern Learning to All Agents 🧠🤖

## Overview

The ComplianceAgent demonstrates the complete learning pattern using Weaviate as the "one smart core" for all agents. This guide shows how to extend the same pattern-based learning to every agent.

## Architecture: One Smart Core

```
┌─────────────────────────────────────────────────────────────┐
│                    Weaviate (Smart Core)                     │
│  Vector Database with Semantic Search & Success Tracking    │
└───┬─────────┬─────────┬──────────┬──────────┬──────────┬───┘
    │         │         │          │          │          │
    ▼         ▼         ▼          ▼          ▼          ▼
┌─────┐  ┌──────┐  ┌──────┐  ┌───────┐  ┌──────┐  ┌──────┐
│SDET │  │  QA  │  │ Comp │  │DevOps │  │ SRE  │  │Full  │
│Agent│  │Agent │  │Agent │  │Agent  │  │Agent │  │Stack │
└─────┘  └──────┘  └──────┘  └───────┘  └──────┘  └──────┘
   │         │         │          │          │          │
   └─────────┴─────────┴──────────┴──────────┴──────────┘
                       │
                       ▼
              All agents query and
              contribute to the same
              Weaviate knowledge base
```

## What Data Gets Stored to Weaviate

### 1. ComplianceAgent (Already Implemented)

**Accessibility Fixes:**
```json
{
  "doc_type": "accessibility_fix",
  "fix_type": "color_contrast",
  "original_color": "#3b82f6",
  "fixed_color": "#2b72e6",
  "required_ratio": "4.5",
  "context": "button on white background",
  "file": "public/index.html",
  "attempts": 5,
  "successes": 5,
  "success_rate": 1.0,
  "validation_passed": true,
  "timestamp": "2024-02-04T10:30:00Z",
  "run_id": "12345"
}
```

**Queryable by:**
- Semantic search: "color contrast 4.5:1 wcag fix"
- Filters: `doc_type="accessibility_fix"`, `fix_type="color_contrast"`
- Returns: High-confidence fixes with success rates

### 2. SDET Agent (Needs Implementation)

**Test Generation Patterns:**
```json
{
  "doc_type": "test_generation_pattern",
  "test_framework": "playwright",
  "test_type": "e2e",
  "component_type": "button",
  "generated_test": "await page.click('#submit-button'); expect(...)",
  "test_passed": true,
  "attempts": 12,
  "successes": 11,
  "success_rate": 0.92,
  "context": {
    "page_type": "form",
    "user_flow": "checkout"
  },
  "coverage_improvement": 15.5,
  "timestamp": "2024-02-04T10:30:00Z"
}
```

**Queryable by:**
- "playwright test button checkout flow"
- Returns: Proven test patterns with high success rates

**Coverage Gap Patterns:**
```json
{
  "doc_type": "coverage_gap_pattern",
  "file": "src/payment.js",
  "uncovered_lines": [45, 46, 47],
  "gap_type": "error_handling",
  "suggested_test": "Test edge case: payment fails",
  "implemented": true,
  "coverage_gained": 8.2,
  "attempts": 3,
  "successes": 3,
  "success_rate": 1.0
}
```

### 3. QA Agent (Needs Implementation)

**Manual Test Automation Patterns:**
```json
{
  "doc_type": "qa_automation_pattern",
  "manual_test_description": "Verify user can login with Google",
  "automated_solution": "await loginWithGoogle(); expect(user.isLoggedIn)",
  "test_framework": "playwright",
  "validation_passed": true,
  "attempts": 8,
  "successes": 7,
  "success_rate": 0.875,
  "context": {
    "auth_type": "oauth",
    "provider": "google"
  }
}
```

**Queryable by:**
- "automate manual test google oauth login"
- Returns: Proven automation patterns

### 4. DevOps Agent (Needs Implementation)

**Security Fix Patterns:**
```json
{
  "doc_type": "security_fix_pattern",
  "vulnerability_type": "npm_audit",
  "package": "lodash",
  "severity": "high",
  "vulnerable_version": "4.17.19",
  "fixed_version": "4.17.21",
  "breaking_changes": false,
  "fix_applied": "npm update lodash@4.17.21",
  "validation_passed": true,
  "attempts": 25,
  "successes": 24,
  "success_rate": 0.96
}
```

**Queryable by:**
- "security fix lodash npm audit high severity"
- Returns: Safe upgrade paths with success rates

### 5. SRE Agent (Needs Implementation)

**Pipeline Fix Patterns:**
```json
{
  "doc_type": "pipeline_fix_pattern",
  "error_type": "timeout",
  "pipeline_step": "npm install",
  "error_message": "ETIMEDOUT registry.npmjs.org",
  "fix_applied": "added retry logic with exponential backoff",
  "fix_code": "npm install --retry 3 --retry-delay 1000",
  "validation_passed": true,
  "attempts": 15,
  "successes": 14,
  "success_rate": 0.93
}
```

**Queryable by:**
- "pipeline timeout npm install registry"
- Returns: Proven solutions to CI failures

### 6. Fullstack Agent (Needs Implementation)

**Code Generation Patterns:**
```json
{
  "doc_type": "code_generation_pattern",
  "task_type": "api_endpoint",
  "language": "javascript",
  "framework": "express",
  "generated_code": "router.post('/api/users', async (req, res) => {...})",
  "validation_passed": true,
  "tests_passed": true,
  "attempts": 10,
  "successes": 9,
  "success_rate": 0.90,
  "context": {
    "auth_required": true,
    "validation": "joi"
  }
}
```

## Implementation Pattern for Each Agent

### Step 1: Query Weaviate for Historical Patterns

```python
def _query_learned_fix(self, problem_context: Dict) -> Optional[Dict]:
    """
    Query Weaviate for similar historical solutions.

    Pattern applies to ALL agents - just change:
    - Query text
    - doc_type filter
    - Confidence calculation
    """
    try:
        # Create semantic search query
        query = self._build_query(problem_context)

        # Search Weaviate
        embedding = self.rag.embedder.embed(query)
        similar_docs = self.rag.vector_store.search(
            embedding,
            doc_type=self._get_doc_type(),  # Agent-specific
            k=5,
            threshold=0.6
        )

        if not similar_docs:
            return None

        # Find best match with highest success rate
        best_solution = None
        best_score = 0.0

        for doc, similarity in similar_docs:
            metadata = doc.metadata
            success_rate = metadata.get("success_rate", 0.0)

            # Confidence = similarity × success_rate
            confidence = similarity * success_rate

            if confidence > best_score:
                best_score = confidence
                best_solution = {
                    "solution": metadata.get("fix_applied"),
                    "confidence": confidence,
                    "attempts": metadata.get("attempts"),
                    "successes": metadata.get("successes")
                }

        return best_solution

    except Exception as e:
        self.log(f"RAG query failed: {e}", "WARNING")
        return None
```

### Step 2: Apply with Confidence Threshold

```python
def fix_problem(self, problem: Dict) -> Dict:
    """
    Hybrid approach: Learned patterns + Core fallbacks

    Same pattern for ALL agents!
    """

    # LEARNING PATH: Query historical solutions
    if self.rag:
        learned_solution = self._query_learned_fix(problem)

        if learned_solution and learned_solution['confidence'] > 0.75:
            # High confidence - use learned solution!
            self.log(f"Using learned fix (confidence: {learned_solution['confidence']:.0%})")
            return self._apply_learned_solution(learned_solution)

    # CORE PATH: Use hard-coded patterns as fallback
    return self._apply_core_pattern(problem)
```

### Step 3: Store Results After Validation

```python
def store_fix_success(self, fix_type: str, fix_details: Dict, validation_passed: bool):
    """
    Store successful fix to Weaviate.

    Same pattern for ALL agents!
    """
    if not self.rag:
        return

    try:
        # Query for existing similar fixes
        query = self._build_storage_query(fix_details)
        embedding = self.rag.embedder.embed(query)
        existing = self.rag.vector_store.search(
            embedding,
            doc_type=self._get_doc_type(),
            k=1,
            threshold=0.9
        )

        # Update statistics
        if existing:
            existing_meta = existing[0][0].metadata
            attempts = existing_meta.get("attempts", 0) + 1
            successes = existing_meta.get("successes", 0) + (1 if validation_passed else 0)
        else:
            attempts = 1
            successes = 1 if validation_passed else 0

        success_rate = successes / attempts

        # Store to Weaviate
        document = {
            "fix_type": fix_type,
            "validation_passed": validation_passed,
            "attempts": attempts,
            "successes": successes,
            "success_rate": success_rate,
            "timestamp": datetime.utcnow().isoformat(),
            **fix_details
        }

        content = f"{fix_type} {self.agent_name} fix"
        embedding = self.rag.embedder.embed(content)

        self.rag.vector_store.add_document(
            content=content,
            embedding=embedding,
            metadata=document,
            doc_type=self._get_doc_type()
        )

        self.log(f"Stored fix to Weaviate (success_rate: {success_rate:.2%})")

    except Exception as e:
        self.log(f"Failed to store fix: {e}", "WARNING")
```

## Example: Implementing Learning for SDET Agent

```python
class SDETAgent(BaseAgent):
    """SDET Agent with pattern-based learning"""

    def __init__(self):
        super().__init__("SDET_Agent")

    def generate_test(self, component: Dict) -> str:
        """Generate test with learning"""

        # LEARNING PATH: Query for similar tests
        if self.rag:
            learned_test = self._query_learned_test(component)

            if learned_test and learned_test['confidence'] > 0.75:
                # Adapt learned test to current component
                return self._adapt_test(learned_test['solution'], component)

        # CORE PATH: Generate from template
        return self._generate_from_template(component)

    def _query_learned_test(self, component: Dict) -> Optional[Dict]:
        """Query Weaviate for similar test generation patterns"""

        query = f"test generation {component['type']} {component['framework']}"
        embedding = self.rag.embedder.embed(query)

        similar_docs = self.rag.vector_store.search(
            embedding,
            doc_type="test_generation_pattern",
            k=5,
            threshold=0.6
        )

        if not similar_docs:
            return None

        # Find best match
        best_test = None
        best_score = 0.0

        for doc, similarity in similar_docs:
            metadata = doc.metadata
            success_rate = metadata.get("success_rate", 0.0)
            confidence = similarity * success_rate

            if confidence > best_score:
                best_score = confidence
                best_test = {
                    "solution": metadata.get("generated_test"),
                    "confidence": confidence,
                    "framework": metadata.get("test_framework")
                }

        return best_test

    def store_test_generation_result(
        self,
        component: Dict,
        generated_test: str,
        test_passed: bool,
        coverage_improvement: float
    ):
        """Store test generation result for learning"""

        fix_details = {
            "component_type": component['type'],
            "test_framework": component['framework'],
            "generated_test": generated_test,
            "test_passed": test_passed,
            "coverage_improvement": coverage_improvement,
            "context": component.get("context", {})
        }

        self.store_fix_success(
            "test_generation",
            fix_details,
            test_passed
        )
```

## Shared Learning Across Agents

Agents can learn from each other's patterns:

```python
# DevOps Agent can query SDET test patterns when fixing pipelines
devops_agent = DevOpsAgent()

# Query: "playwright tests failing in CI"
similar_patterns = devops_agent.rag.vector_store.search(
    embedding,
    doc_type=None,  # Search ALL doc types
    k=10
)

# Results include:
# - SDET test_generation_patterns
# - SRE pipeline_fix_patterns
# - QA qa_automation_patterns
# All relevant to the problem!
```

## CI Integration for All Agents

Add to CI workflow for each agent:

```yaml
- name: Store {Agent} Results for Learning
  run: |
    python store_agent_results.py \
      --agent-type sdet \
      --results sdet-results.json \
      --run-id ${{ github.run_id }}
```

## Data Sufficiency Checklist

For each agent, store:

- ✅ **Problem Context**: What was the issue?
- ✅ **Solution Applied**: What fix was used?
- ✅ **Validation Result**: Did it work?
- ✅ **Success Metrics**: Attempts, successes, success_rate
- ✅ **Context Tags**: Framework, language, type, etc.
- ✅ **Timestamps**: When did this happen?

This gives Weaviate enough information to:
1. Semantically match similar problems
2. Calculate confidence scores
3. Return high-success solutions
4. Track improvement over time

## Expected Learning Progression

### Run 1-10: Bootstrap Phase
- All agents use core patterns
- Store all results to Weaviate
- Success rates: 70-80%

### Run 10-50: Learning Phase
- Agents query Weaviate first
- 30-50% of fixes use learned patterns
- Success rates: 85-90%

### Run 50+: Mastery Phase
- 80-95% of fixes use learned patterns
- Success rates: 95%+
- Agents handle edge cases automatically

## Benefits of One Smart Core

1. **Shared Knowledge**: All agents learn from each other
2. **Consistent Approach**: Same learning pattern everywhere
3. **Cross-Agent Insights**: DevOps learns from SDET, SRE learns from QA
4. **Centralized Metrics**: One place to track all agent improvements
5. **No LLM Costs**: Pure pattern matching and statistics

## Next Steps

1. ✅ ComplianceAgent learning: **Implemented**
2. ⏭️ SDET Agent learning: Implement test generation patterns
3. ⏭️ QA Agent learning: Implement automation patterns
4. ⏭️ DevOps Agent learning: Implement security fix patterns
5. ⏭️ SRE Agent learning: Implement pipeline fix patterns
6. ⏭️ Fullstack Agent learning: Implement code generation patterns

## Monitoring All Agents

```bash
# Query Weaviate for all learned patterns
python -c "
from src.agenticqa.rag.config import create_rag_system
rag = create_rag_system()

# Get patterns by agent
for agent in ['compliance', 'sdet', 'qa', 'devops', 'sre', 'fullstack']:
    results = rag.vector_store.search(
        query=f'{agent} patterns',
        k=100
    )
    print(f'{agent}: {len(results)} patterns learned')
"
```

---

**Result**: One smart Weaviate core that makes all agents collectively smarter over time, without requiring expensive LLMs for 95%+ of problems. 🧠🚀
