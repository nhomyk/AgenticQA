"""Generate observability trace quality report for CI/CD gating."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


try:
    from src.agenticqa.observability import ObservabilityStore
except Exception:
    from agenticqa.observability import ObservabilityStore


def seed_demo_trace(store: ObservabilityStore) -> None:
    trace_id = "tr_ci_seed"
    span_id = "sp_ci_seed_root"
    store.log_event(
        trace_id=trace_id,
        request_id="wr_ci_seed",
        span_id=span_id,
        agent="CI",
        action="observability_quality",
        status="STARTED",
        event_type="ci_gate",
        step_key="ci.observability.seed",
        metadata={"seeded": True},
    )
    store.log_event(
        trace_id=trace_id,
        request_id="wr_ci_seed",
        span_id=span_id,
        agent="CI",
        action="observability_quality",
        status="COMPLETED",
        event_type="ci_gate",
        step_key="ci.observability.seed",
        decision={"seed_gate": "pass"},
        metadata={"seeded": True},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate observability quality summary")
    parser.add_argument("--db-path", default=str(Path.home() / ".agenticqa" / "observability.db"))
    parser.add_argument("--output", default="docs/reports/OBSERVABILITY_QUALITY.json")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--min-completeness", type=float, default=0.95)
    parser.add_argument("--min-decision-quality", type=float, default=0.60)
    parser.add_argument("--enforce", action="store_true")
    parser.add_argument("--seed-demo-if-empty", action="store_true")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    store = ObservabilityStore(db_path=args.db_path)
    try:
        if args.seed_demo_if_empty:
            initial = store.get_quality_summary(
                limit=max(1, args.limit),
                min_completeness=args.min_completeness,
                min_decision_quality=args.min_decision_quality,
            )
            if int(initial.get("trace_count") or 0) == 0:
                seed_demo_trace(store)

        quality = store.get_quality_summary(
            limit=max(1, args.limit),
            min_completeness=args.min_completeness,
            min_decision_quality=args.min_decision_quality,
        )
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "db_path": args.db_path,
            "quality": quality,
            "threshold": args.min_completeness,
            "decision_threshold": args.min_decision_quality,
            "enforced": bool(args.enforce),
        }
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        below = int(quality.get("below_threshold_count") or 0)
        below_decision = int(quality.get("decision_quality_below_threshold_count") or 0)
        if args.enforce and (below > 0 or below_decision > 0):
            return 2
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
