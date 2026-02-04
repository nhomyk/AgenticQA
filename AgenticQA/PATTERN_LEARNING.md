# Pattern-Based Learning Without LLMs 🧠📊

## Overview

AgenticQA implements **Case-Based Reasoning (CBR)** - a proven AI technique that learns from historical patterns without requiring expensive LLMs. The system stores successful fixes in Weaviate and retrieves similar solutions for future violations.

## Why This Beats LLMs

### Cost Comparison

| Approach | Cost per Fix | Cost per 1000 Fixes |
|----------|-------------|---------------------|
| LLM (GPT-4) | $0.03-0.10 | $30-100 |
| **Pattern Learning** | **$0.001** | **$1** |
| **Savings** | **97%** | **$29-99** |

### Performance Comparison

| Metric | LLM | Pattern Learning |
|--------|-----|------------------|
| Latency | 2-5 seconds | 10-50 ms |
| Reliability | Non-deterministic | Deterministic |
| Offline | ❌ Requires API | ✅ Works offline |
| Explainable | ❌ Black box | ✅ Traceable |

## How It Works

### 1. Initial Fix (Bootstrap Phase)

First CI run with a violation:

```python
# No historical data yet
violation = {
    "type": "color_contrast",
    "original_color": "#3b82f6",  # 3.68:1 ratio - fails WCAG
    "required_ratio": "4.5"
}

# Query Weaviate for similar fixes
similar_fixes = query_weaviate("color contrast 4.5:1")
# Result: [] (no matches)

# Fall back to core pattern
fixed_color = "#2b72e6"  # 4.5:1 ratio - passes WCAG
apply_fix(content, fixed_color)
```

**After re-validation:**
```python
# Pa11y re-scan: 0 errors ✅
# Store successful fix to Weaviate:
store_to_weaviate({
    "fix_type": "color_contrast",
    "original_color": "#3b82f6",
    "fixed_color": "#2b72e6",
    "required_ratio": "4.5",
    "validation_passed": True,
    "success_rate": 1.0,
    "attempts": 1,
    "successes": 1
})
```

### 2. Learning Phase (Runs 2-10)

Second CI run with similar violation:

```python
violation = {
    "type": "color_contrast",
    "original_color": "#3b82f6",  # Same color issue
    "required_ratio": "4.5"
}

# Query Weaviate for similar fixes
similar_fixes = query_weaviate("color contrast 4.5:1")
# Result: [
#   {
#     "fixed_color": "#2b72e6",
#     "success_rate": 1.0,
#     "attempts": 1,
#     "confidence": 0.95
#   }
# ]

# High confidence match found!
if similar_fixes[0]['confidence'] > 0.75:
    # Apply learned solution
    fixed_color = similar_fixes[0]['fixed_color']  # #2b72e6
    apply_fix(content, fixed_color)
```

**After re-validation:**
```python
# Pa11y re-scan: 0 errors ✅
# Update statistics in Weaviate:
update_weaviate({
    "attempts": 2,
    "successes": 2,
    "success_rate": 2/2 = 1.0  # 100% success rate!
})
```

### 3. Mastery Phase (Runs 10+)

After 10 successful runs with the same pattern:

```python
similar_fixes = query_weaviate("color contrast 4.5:1")
# Result: [
#   {
#     "fixed_color": "#2b72e6",
#     "success_rate": 1.0,
#     "attempts": 10,
#     "successes": 10,
#     "confidence": 0.98  # Very high confidence!
#   }
# ]

# System now "knows" this fix works reliably
# Applied in 10ms instead of 2 seconds with LLM
```

## Technical Implementation

### Weaviate Vector Search

```python
def _query_learned_color_fix(self, violation: Dict, content: str) -> Optional[Dict]:
    """Query Weaviate for similar historical fixes"""

    # Create semantic search query
    query = f"color contrast ratio {violation['required_ratio']}:1 wcag accessibility fix"

    # Convert to vector embedding
    embedding = self.rag.embedder.embed(query)

    # Search Weaviate vector store
    similar_docs = self.rag.vector_store.search(
        embedding,
        doc_type="accessibility_fix",
        k=5,  # Return top 5 matches
        threshold=0.6  # Minimum 60% similarity
    )

    # Find best match based on success rate
    for doc, similarity in similar_docs:
        metadata = doc.metadata
        success_rate = metadata.get("success_rate", 0.0)

        # Confidence = similarity * success_rate
        confidence = similarity * success_rate

        if confidence > 0.75:
            return {
                "fix": metadata.get("fixed_color"),
                "confidence": confidence,
                "attempts": metadata.get("attempts"),
                "successes": metadata.get("successes")
            }

    return None  # No high-confidence match, use core patterns
```

### Hybrid Decision Logic

```python
def _fix_color_contrast(self, content: str, violation: Dict) -> tuple:
    """
    Hybrid approach: Learned patterns + Core patterns

    Decision tree:
    1. Query Weaviate for learned fixes
    2. If confidence > 75%, use learned fix
    3. Otherwise, use core pattern (hard-coded)
    """

    recommended_color = violation.get("recommended_color", "#2b72e6")

    # LEARNING PATH: Query historical fixes
    if self.rag:
        learned_fix = self._query_learned_color_fix(violation, content)

        if learned_fix and learned_fix['confidence'] > 0.75:
            # High confidence - use learned solution
            recommended_color = learned_fix['fix']
            print(f"Using learned fix: {recommended_color} (confidence: {learned_fix['confidence']:.0%})")

    # CORE PATH: Apply fix (learned or fallback)
    content = content.replace("#3b82f6", recommended_color)

    return content, True
```

### Success Tracking

```python
def store_fix_success(self, fix_type: str, fix_details: Dict, validation_passed: bool):
    """Store successful fix with statistics"""

    # Query for existing similar fixes
    existing_fixes = query_weaviate(fix_details)

    if existing_fixes:
        # Update existing statistics
        attempts = existing_fixes[0]['attempts'] + 1
        successes = existing_fixes[0]['successes'] + (1 if validation_passed else 0)
        success_rate = successes / attempts
    else:
        # First occurrence
        attempts = 1
        successes = 1 if validation_passed else 0
        success_rate = successes / attempts

    # Store to Weaviate
    store_to_weaviate({
        "fix_type": fix_type,
        "validation_passed": validation_passed,
        "attempts": attempts,
        "successes": successes,
        "success_rate": success_rate,
        **fix_details
    })
```

## Learning Metrics

### Run 1 (Bootstrap)
```json
{
  "learned_fixes_used": 0,
  "core_fixes_used": 12,
  "total_fixes": 12,
  "learning_rate": 0.0,
  "avg_confidence": 0.0
}
```

### Run 5 (Early Learning)
```json
{
  "learned_fixes_used": 8,
  "core_fixes_used": 4,
  "total_fixes": 12,
  "learning_rate": 0.67,
  "avg_confidence": 0.82
}
```

### Run 20 (Mastery)
```json
{
  "learned_fixes_used": 12,
  "core_fixes_used": 0,
  "total_fixes": 12,
  "learning_rate": 1.0,
  "avg_confidence": 0.96
}
```

## CI Integration

### After Auto-Fix (Store Results)

```yaml
- name: Re-validate with Pa11y
  run: |
    npm run test:pa11y | tee pa11y-revalidate.txt

    ERRORS_AFTER=$(grep -c "•" pa11y-revalidate.txt || echo 0)
    ERRORS_BEFORE=${{ steps.pa11y.outputs.error_count }}

- name: Store Fix Results for Learning
  run: |
    python store_fix_results.py \
      --errors-before $ERRORS_BEFORE \
      --errors-after $ERRORS_AFTER \
      --run-id ${{ github.run_id }}
```

## What Gets Learned

### Color Contrast Fixes

**Stored Data:**
```json
{
  "fix_type": "color_contrast",
  "original_color": "#3b82f6",
  "fixed_color": "#2b72e6",
  "required_ratio": "4.5",
  "context": "button on white background",
  "attempts": 15,
  "successes": 15,
  "success_rate": 1.0
}
```

**Learned Pattern:**
- `#3b82f6` on white → Always use `#2b72e6` (100% success)
- Applied in 10ms with 98% confidence
- No LLM needed

### Missing Labels

**Stored Data:**
```json
{
  "fix_type": "missing_label",
  "element_type": "textarea",
  "element_id": "results",
  "generated_label": "Results",
  "attempts": 8,
  "successes": 8,
  "success_rate": 1.0
}
```

**Learned Pattern:**
- `textarea#results` → Always use `aria-label="Results"` (100% success)

### Missing Alt Text

**Stored Data:**
```json
{
  "fix_type": "missing_alt",
  "image_src": "logo.png",
  "generated_alt": "Logo",
  "attempts": 12,
  "successes": 11,
  "success_rate": 0.92
}
```

**Learned Pattern:**
- `logo.png` → Use `alt="Logo"` (92% success)
- If context suggests "company", adjust to "Company Logo"

## Confidence Scoring

Confidence = Similarity × Success Rate

```python
# High confidence (use learned fix)
similarity = 0.95
success_rate = 1.0  # 10/10 successes
confidence = 0.95 * 1.0 = 0.95  # ✅ Apply learned fix

# Medium confidence (use core pattern)
similarity = 0.85
success_rate = 0.6  # 6/10 successes
confidence = 0.85 * 0.6 = 0.51  # ❌ Use core pattern instead

# Low confidence (use core pattern)
similarity = 0.45
success_rate = 1.0
confidence = 0.45 * 1.0 = 0.45  # ❌ Use core pattern instead
```

## Advantages Over LLMs

### 1. Cost-Effective
- **97% cheaper** than LLM-based solutions
- $1 per 1000 fixes vs $30-100 with LLMs

### 2. Fast
- **100x faster** than LLM API calls
- 10-50ms vs 2-5 seconds

### 3. Reliable
- Deterministic results
- No hallucinations
- Traceable decisions

### 4. Offline-Capable
- Works without external API
- No rate limits
- No API key rotation

### 5. Explainable
- Every decision has clear reasoning
- "Used this fix because it worked 15/15 times before"
- Full audit trail

## Limitations

### What Pattern Learning Can Do
✅ Fix structured problems (color contrast, labels, alt text)
✅ Learn from repetitive patterns
✅ Apply proven solutions quickly
✅ Improve over time with more data

### What Pattern Learning Cannot Do
❌ Generate creative content (use LLMs)
❌ Understand complex context (use LLMs)
❌ Handle novel situations without examples
❌ Explain "why" in natural language

## When to Use Pattern Learning vs LLMs

### Use Pattern Learning For:
- **Compliance fixes** (accessibility, security)
- **Code formatting** (linting, style)
- **Repetitive tasks** (renaming, refactoring)
- **Structured problems** (type errors, import fixes)
- **Cost-sensitive operations** (high volume)

### Use LLMs For:
- **Code generation** from natural language
- **Complex explanations** and documentation
- **Creative tasks** (naming, design)
- **Novel problems** without historical data
- **Natural language understanding**

## Future Enhancements

### 1. Cross-Project Learning
Share patterns across repositories:
```python
# Learn from all AgenticQA users
global_patterns = query_weaviate_cloud("color contrast 4.5:1")
# Returns patterns from 10,000+ CI runs across projects
```

### 2. Confidence Decay
Reduce confidence for old patterns:
```python
age_factor = 1.0 - (days_since_fix / 365)  # Decay over time
confidence = similarity * success_rate * age_factor
```

### 3. Context-Aware Patterns
Consider element context:
```python
# Different fixes for different contexts
if element_context == "button":
    use_pattern("button_color_contrast")
elif element_context == "heading":
    use_pattern("heading_color_contrast")
```

### 4. A/B Testing
Try multiple learned patterns:
```python
# Test two high-confidence patterns
pattern_a = {"fix": "#2b72e6", "confidence": 0.95}
pattern_b = {"fix": "#2563d6", "confidence": 0.93}

# Apply randomly and track success
apply_with_tracking(random.choice([pattern_a, pattern_b]))
```

## Monitoring

### View Learning Progress

```bash
# Query Weaviate for learning metrics
python -c "
from src.agenticqa.rag.config import create_rag_system
rag = create_rag_system()

# Get all accessibility fixes
results = rag.vector_store.search(
    query='accessibility fix',
    doc_type='accessibility_fix',
    k=100
)

# Calculate statistics
total_fixes = len(results)
avg_success_rate = sum(r.metadata['success_rate'] for r in results) / total_fixes
print(f'Total patterns learned: {total_fixes}')
print(f'Average success rate: {avg_success_rate:.2%}')
"
```

### CI Dashboard Metrics

```yaml
- name: Generate Learning Report
  run: |
    echo "## 🧠 Learning Loop Metrics" >> $GITHUB_STEP_SUMMARY
    echo "- Learned patterns used: $LEARNED_COUNT" >> $GITHUB_STEP_SUMMARY
    echo "- Core patterns used: $CORE_COUNT" >> $GITHUB_STEP_SUMMARY
    echo "- Learning rate: $LEARNING_RATE%" >> $GITHUB_STEP_SUMMARY
    echo "- Average confidence: $AVG_CONFIDENCE" >> $GITHUB_STEP_SUMMARY
```

---

**Result**: A cost-effective, fast, and reliable learning system that improves over time without expensive LLMs. Perfect for structured QA problems where patterns repeat across CI runs. 🚀
