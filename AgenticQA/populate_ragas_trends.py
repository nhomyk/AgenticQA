#!/usr/bin/env python3
"""Populate RagasTracker and OutcomeTracker with sample data for dashboard visualization."""

import sys
import os
import random
import uuid
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

from agenticqa.verification import RagasTracker, OutcomeTracker

# ── RAGAS Scores ────────────────────────────────────────────────────

print("📊 Populating RAGAS score history...")
tracker = RagasTracker()

# Simulate 30 CI runs over time showing gradual improvement
base_scores = {
    "faithfulness": 0.72,
    "answer_relevancy": 0.68,
    "context_precision": 0.65,
    "context_recall": 0.60,
}

for i in range(30):
    run_id = f"ci-{1000 + i}"
    commit_sha = uuid.uuid4().hex[:7]

    # Gradual improvement with noise
    improvement = i * 0.005  # ~0.5% per run
    noise = random.uniform(-0.03, 0.03)

    scores = {}
    for metric, base in base_scores.items():
        score = min(1.0, max(0.0, base + improvement + noise + random.uniform(-0.01, 0.01)))
        scores[metric] = round(score, 4)

    tracker.record_scores(
        run_id=run_id,
        commit_sha=commit_sha,
        scores=scores,
        branch="main",
    )
    print(f"  ✓ {run_id}: faith={scores['faithfulness']:.3f} rel={scores['answer_relevancy']:.3f} "
          f"prec={scores['context_precision']:.3f} rec={scores['context_recall']:.3f}")

tracker.close()

# ── Delegation Outcomes ─────────────────────────────────────────────

print("\n🎯 Populating delegation outcome predictions...")
ot = OutcomeTracker()

agents = ["SDET_Agent", "SRE_Agent", "QA_Agent", "DevOps_Agent", "Fullstack_Agent"]
tasks = ["deploy_tests", "generate_tests", "security_scan", "load_test", "code_review"]

for i in range(50):
    delegation_id = f"del-{uuid.uuid4().hex[:8]}"
    from_agent = random.choice(agents)
    to_agent = random.choice([a for a in agents if a != from_agent])
    task = random.choice(tasks)

    # Higher confidence predictions tend to succeed more
    confidence = random.uniform(0.3, 0.95)
    success_prob = confidence * 0.85 + 0.1  # correlated but not perfect
    actual_success = random.random() < success_prob

    ot.record_prediction(
        delegation_id=delegation_id,
        from_agent=from_agent,
        to_agent=to_agent,
        task_type=task,
        predicted_confidence=round(confidence, 3),
    )
    ot.record_outcome(
        delegation_id=delegation_id,
        actual_success=actual_success,
        duration_ms=round(random.uniform(100, 5000), 0),
    )

ot.close()

print(f"\n✅ Done! 30 RAGAS runs + 50 delegation outcomes seeded.")
print("🚀 Go to GraphRAG → RAG Quality Trends tab in the dashboard.")
