"""Normalized event schema for cross-platform agent ingestion.

Any agent platform (LangGraph, LangChain, CrewAI, AutoGen, OpenAI Agents SDK,
custom) can emit events in this format via REST or the callback adapter.
The schema maps directly onto ObservabilityStore.log_event().
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# Valid status values — superset covers both LangChain and internal conventions
VALID_STATUSES = {"STARTED", "COMPLETED", "FAILED", "RETRY", "SKIPPED", "CANCELLED"}

# Maps common external status strings to AgenticQA canonical values
_STATUS_MAP = {
    "start": "STARTED",
    "starting": "STARTED",
    "running": "STARTED",
    "end": "COMPLETED",
    "success": "COMPLETED",
    "done": "COMPLETED",
    "error": "FAILED",
    "exception": "FAILED",
    "retry": "RETRY",
    "skip": "SKIPPED",
    "cancel": "CANCELLED",
}


class IngestEvent:
    """Normalized event consumed by ObservabilityStore.log_event().

    Constructed directly or via normalize_event() from platform-specific dicts.
    Deliberately not a Pydantic model so LangChain callbacks can construct it
    without requiring pydantic as a hard dependency in the adapter.
    """

    __slots__ = (
        "trace_id", "request_id", "agent", "action", "status",
        "span_id", "parent_span_id", "event_type", "step_key",
        "latency_ms", "decision", "error", "metadata",
        "llm_prompt_tokens", "llm_completion_tokens",
    )

    def __init__(
        self,
        trace_id: str,
        agent: str,
        action: str,
        status: str,
        *,
        request_id: Optional[str] = None,
        span_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        event_type: Optional[str] = None,
        step_key: Optional[str] = None,
        latency_ms: Optional[float] = None,
        decision: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        llm_prompt_tokens: Optional[int] = None,
        llm_completion_tokens: Optional[int] = None,
    ) -> None:
        self.trace_id = trace_id
        self.request_id = request_id
        self.agent = agent
        self.action = action
        self.status = _normalize_status(status)
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.event_type = event_type
        self.step_key = step_key
        self.latency_ms = latency_ms
        self.decision = decision or {}
        self.error = error
        self.metadata = metadata or {}
        self.llm_prompt_tokens = llm_prompt_tokens
        self.llm_completion_tokens = llm_completion_tokens

    def to_dict(self) -> Dict[str, Any]:
        return {s: getattr(self, s) for s in self.__slots__}


def _normalize_status(raw: str) -> str:
    s = str(raw).strip().upper()
    if s in VALID_STATUSES:
        return s
    return _STATUS_MAP.get(raw.strip().lower(), "COMPLETED")


def normalize_event(payload: Dict[str, Any]) -> IngestEvent:
    """Construct an IngestEvent from any loosely-typed dict.

    Handles field aliases used by common platforms:
    - LangChain/LangGraph: run_id → span_id, parent_run_id → parent_span_id,
      name → agent, serialized["name"] → action
    - CrewAI: task_id → span_id, crew_id → trace_id
    - AutoGen: sender → agent, message_type → action
    - Generic: passes through if fields match IngestEvent schema
    """
    p = payload or {}

    trace_id = str(
        p.get("trace_id")
        or p.get("crew_id")
        or p.get("session_id")
        or p.get("run_id")  # LangChain top-level run
        or "unknown"
    )
    span_id = str(p.get("span_id") or p.get("run_id") or "") or None
    parent_span_id = str(p.get("parent_span_id") or p.get("parent_run_id") or "") or None

    agent = str(
        p.get("agent")
        or p.get("name")
        or p.get("sender")
        or p.get("node")
        or "unknown_agent"
    )
    action = str(
        p.get("action")
        or p.get("tool")
        or p.get("message_type")
        or p.get("event_type")
        or "run"
    )
    status = str(p.get("status") or p.get("state") or "COMPLETED")

    # LLM token usage — LangChain LLMResult / OpenAI response
    token_usage = p.get("token_usage") or (p.get("llm_output") or {}).get("token_usage") or {}
    prompt_tokens = _safe_int(p.get("llm_prompt_tokens") or token_usage.get("prompt_tokens"))
    completion_tokens = _safe_int(
        p.get("llm_completion_tokens") or token_usage.get("completion_tokens")
    )

    return IngestEvent(
        trace_id=trace_id,
        agent=agent,
        action=action,
        status=status,
        request_id=p.get("request_id"),
        span_id=span_id,
        parent_span_id=parent_span_id,
        event_type=p.get("event_type"),
        step_key=p.get("step_key"),
        latency_ms=_safe_float(p.get("latency_ms") or p.get("duration_ms")),
        decision=p.get("decision") or p.get("provenance") or {},
        error=p.get("error"),
        metadata=p.get("metadata") or {},
        llm_prompt_tokens=prompt_tokens,
        llm_completion_tokens=completion_tokens,
    )


def normalize_events(payloads: List[Dict[str, Any]]) -> List[IngestEvent]:
    return [normalize_event(p) for p in payloads]


def _safe_int(v: Any) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _safe_float(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None
