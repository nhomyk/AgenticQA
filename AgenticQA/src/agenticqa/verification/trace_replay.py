"""Deterministic replay utilities for recorded traces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .tracing import Tracer


@dataclass
class ReplayResult:
    trace_id: str
    replayable: bool
    steps: int
    operation_sequence: List[str]
    status_sequence: List[str]


class TraceReplay:
    """Exports and replays traces with deterministic sequence checks."""

    def __init__(self, tracer: Tracer):
        self.tracer = tracer

    def export_bundle(self, trace_id: str) -> Dict[str, Any]:
        spans = self.tracer.get_trace(trace_id)
        normalized = [
            {
                "operation": s.get("operation"),
                "agent": s.get("agent"),
                "status": s.get("status"),
                "metadata": s.get("metadata") or "{}",
            }
            for s in spans
        ]
        return {
            "trace_id": trace_id,
            "steps": normalized,
            "total_steps": len(normalized),
        }

    def replay_bundle(self, bundle: Dict[str, Any]) -> ReplayResult:
        steps = bundle.get("steps", [])
        op_sequence = [step.get("operation", "unknown") for step in steps]
        status_sequence = [step.get("status", "unknown") for step in steps]

        # Deterministic replay requirement: operation sequence must be stable and non-empty
        replayable = len(op_sequence) > 0 and all(op_sequence)

        return ReplayResult(
            trace_id=str(bundle.get("trace_id", "unknown")),
            replayable=replayable,
            steps=len(steps),
            operation_sequence=op_sequence,
            status_sequence=status_sequence,
        )

    def compare(self, left_bundle: Dict[str, Any], right_bundle: Dict[str, Any]) -> Dict[str, Any]:
        left = self.replay_bundle(left_bundle)
        right = self.replay_bundle(right_bundle)

        return {
            "deterministic_match": (
                left.operation_sequence == right.operation_sequence
                and left.status_sequence == right.status_sequence
            ),
            "left_trace": left.trace_id,
            "right_trace": right.trace_id,
            "left_steps": left.steps,
            "right_steps": right.steps,
        }
