"""AI Decision Audit Report — aggregates trace analysis, counterfactuals, and quality into a shareable artifact."""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Dict, List

_QUALITY_THRESHOLD = 0.60
_COMPLETENESS_THRESHOLD = 0.80


def build_audit_report(
    trace_id: str,
    obs_store: Any,
    *,
    limit: int = 500,
) -> Dict[str, Any]:
    """Build a structured, shareable audit report for a single trace.

    Raises ValueError (with prefix 'trace_not_found:') if trace has no events.
    """
    events = obs_store.list_events(limit=limit, trace_id=trace_id, newest_first=False)
    if not events:
        raise ValueError(f"trace_not_found:{trace_id}")

    analysis = obs_store.analyze_trace(trace_id, events=events)
    counterfactuals = obs_store.get_counterfactual_recommendations(trace_id, limit=limit)

    quality_score = _compute_quality(events)
    quality_verdict = "PASS" if quality_score >= _QUALITY_THRESHOLD else "FAIL"

    # Aggregate root causes ranked by frequency
    root_cause_counts: Counter = Counter()
    all_recs: List[str] = []
    for rec in counterfactuals.get("recommendations") or []:
        rc = rec.get("root_cause") or "UNKNOWN"
        root_cause_counts[rc] += 1
        for alt in rec.get("counterfactuals") or []:
            all_recs.append(alt)

    root_causes = [
        {"root_cause": rc, "count": cnt}
        for rc, cnt in root_cause_counts.most_common()
    ]

    # Deduplicate, keep top 3
    seen: set = set()
    unique_recs: List[str] = []
    for r in all_recs:
        if r not in seen:
            seen.add(r)
            unique_recs.append(r)
        if len(unique_recs) == 3:
            break

    by_agent_action = analysis.get("by_agent_action") or []
    total_actions = sum(e.get("count", 0) for e in by_agent_action)
    total_failures = sum(e.get("failures", 0) for e in by_agent_action)
    agents_involved = sorted({e.get("agent") for e in by_agent_action if e.get("agent")})
    completeness = analysis.get("completeness_ratio", 0.0)

    overall_verdict = (
        "PASS"
        if quality_verdict == "PASS"
        and completeness >= _COMPLETENESS_THRESHOLD
        and total_failures == 0
        else "FAIL"
    )

    timestamp = datetime.now(UTC).isoformat()
    audit_id = hashlib.sha256(f"{trace_id}{timestamp}".encode()).hexdigest()[:12]

    report: Dict[str, Any] = {
        "audit_id": audit_id,
        "trace_id": trace_id,
        "generated_at": timestamp,
        "verdict": overall_verdict,
        "summary": {
            "agents_involved": agents_involved,
            "total_actions": total_actions,
            "total_failures": total_failures,
            "span_count": analysis.get("span_count", 0),
            "completeness_ratio": completeness,
            "critical_path_ms": analysis.get("critical_path_ms", 0.0),
        },
        "decision_quality": {
            "score": quality_score,
            "threshold": _QUALITY_THRESHOLD,
            "verdict": quality_verdict,
        },
        "root_causes": root_causes,
        "recommendations": unique_recs,
        "by_agent_action": by_agent_action,
    }

    report["markdown_body"] = _render_markdown(report)
    return report


def _compute_quality(events: List[Dict[str, Any]]) -> float:
    terminal = [
        e
        for e in events
        if str(e.get("status") or "").upper() in {"COMPLETED", "FAILED", "CANCELLED", "SKIPPED"}
    ]
    if not terminal:
        return 1.0
    with_decision = [e for e in terminal if bool(e.get("decision"))]
    coverage = len(with_decision) / len(terminal)
    success = (
        len([e for e in with_decision if str(e.get("status") or "").upper() == "COMPLETED"])
        / len(with_decision)
        if with_decision
        else 1.0
    )
    return round(0.7 * coverage + 0.3 * success, 3)


def _render_markdown(report: Dict[str, Any]) -> str:
    verdict = report["verdict"]
    dq = report["decision_quality"]
    summary = report["summary"]

    lines = [
        f"## AgenticQA Decision Audit — `{report['trace_id']}`",
        "",
        f"**Overall Verdict:** {verdict}  |  **Audit ID:** `{report['audit_id']}`  |  **Generated:** {report['generated_at']}",
        "",
        "### Decision Quality",
        "| Metric | Value |",
        "|---|---|",
        f"| Score | `{dq['score']}` |",
        f"| Threshold | `{dq['threshold']}` |",
        f"| Verdict | {dq['verdict']} |",
        f"| Trace Completeness | `{summary['completeness_ratio']}` |",
        f"| Critical Path | `{summary['critical_path_ms']} ms` |",
        "",
    ]

    if report["root_causes"]:
        lines += [
            "### Root Causes",
            "| Root Cause | Count |",
            "|---|---|",
        ]
        for rc in report["root_causes"]:
            lines.append(f"| `{rc['root_cause']}` | {rc['count']} |")
        lines.append("")

    if report["recommendations"]:
        lines += ["### Recommendations", ""]
        for i, rec in enumerate(report["recommendations"], 1):
            lines.append(f"{i}. {rec}")
        lines.append("")

    agents = ", ".join(f"`{a}`" for a in summary["agents_involved"]) or "_none_"
    lines += [
        "### Execution Summary",
        f"- **Agents:** {agents}",
        f"- **Total Actions:** {summary['total_actions']}",
        f"- **Failures:** {summary['total_failures']}",
        f"- **Spans:** {summary['span_count']}",
    ]

    return "\n".join(lines)
