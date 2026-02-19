"""Agent platform adapters for AgenticQA observability.

Usage (LangGraph / LangChain):
    from agenticqa.ingestion import LangChainCallbackAdapter
    from agenticqa.observability import ObservabilityStore

    store = ObservabilityStore()
    adapter = LangChainCallbackAdapter(store=store, trace_id="my-trace-123")

    # Pass to any LangChain/LangGraph runnable:
    chain.invoke(inputs, config={"callbacks": [adapter]})

Usage (generic dict / REST):
    from agenticqa.ingestion import GenericDictAdapter
    adapter = GenericDictAdapter(store=store)
    adapter.ingest({"agent": "my-agent", "action": "classify", "status": "COMPLETED", ...})
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Union

from .event_schema import IngestEvent, normalize_event

try:
    from langchain_core.callbacks import BaseCallbackHandler as _LCBase  # type: ignore
except ImportError:
    _LCBase = object  # type: ignore


def _write(store: Any, event: IngestEvent) -> None:
    """Write an IngestEvent to an ObservabilityStore (direct mode)."""
    store.log_event(
        trace_id=event.trace_id,
        request_id=event.request_id,
        agent=event.agent,
        action=event.action,
        status=event.status,
        span_id=event.span_id,
        parent_span_id=event.parent_span_id,
        event_type=event.event_type,
        step_key=event.step_key,
        latency_ms=event.latency_ms,
        decision=event.decision,
        error=event.error,
        metadata=event.metadata,
    )
    if event.llm_prompt_tokens is not None or event.llm_completion_tokens is not None:
        try:
            store.log_complexity_metric(
                agent=event.agent,
                action=event.action,
                trace_id=event.trace_id,
                llm_prompt_tokens=event.llm_prompt_tokens or 0,
                llm_completion_tokens=event.llm_completion_tokens or 0,
            )
        except Exception:
            pass


class GenericDictAdapter:
    """Ingest any dict payload into AgenticQA observability.

    Works for CrewAI, AutoGen, OpenAI Agents SDK, or any custom agent
    that can emit a dict of execution metadata.
    """

    def __init__(self, store: Any) -> None:
        self._store = store

    def ingest(self, payload: Dict[str, Any]) -> IngestEvent:
        event = normalize_event(payload)
        _write(self._store, event)
        return event

    def ingest_batch(self, payloads: List[Dict[str, Any]]) -> List[IngestEvent]:
        return [self.ingest(p) for p in payloads]


class LangChainCallbackAdapter(_LCBase):
    """LangChain BaseCallbackHandler-compatible adapter for AgenticQA.

    Translates LangChain/LangGraph callback events into ObservabilityStore events.
    Supports: chains, tools, LLM calls (with token tracking), agents.

    LangGraph runs on top of LangChain's callback system — this adapter
    covers both automatically. Each LangGraph node becomes a span.

    LangChain is an optional dependency. If not installed, import will
    still succeed; just don't register this as a LangChain callback.
    """

    def __init__(
        self,
        store: Any,
        trace_id: Optional[str] = None,
        agent_name: str = "langchain_agent",
    ) -> None:
        self._store = store
        self._trace_id = trace_id or str(uuid.uuid4())
        self._agent_name = agent_name
        self._start_times: Dict[str, float] = {}

    # ------------------------------------------------------------------ #
    # LangChain callback hooks                                             #
    # ------------------------------------------------------------------ #

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], *, run_id: Any = None, parent_run_id: Any = None, **kwargs: Any
    ) -> None:
        run_id_str = str(run_id) if run_id else str(uuid.uuid4())
        self._start_times[run_id_str] = time.time()
        name = (serialized or {}).get("name") or self._agent_name
        _write(self._store, IngestEvent(
            trace_id=self._trace_id,
            agent=name,
            action="chain",
            status="STARTED",
            span_id=run_id_str,
            parent_span_id=str(parent_run_id) if parent_run_id else None,
            event_type="chain_start",
            metadata={"inputs_keys": list(inputs.keys()) if inputs else []},
        ))

    def on_chain_end(self, outputs: Dict[str, Any], *, run_id: Any = None, **kwargs: Any) -> None:
        run_id_str = str(run_id) if run_id else ""
        latency = self._elapsed(run_id_str)
        _write(self._store, IngestEvent(
            trace_id=self._trace_id,
            agent=self._agent_name,
            action="chain",
            status="COMPLETED",
            span_id=run_id_str,
            event_type="chain_end",
            latency_ms=latency,
            decision={"output_keys": list(outputs.keys()) if outputs else []},
        ))

    def on_chain_error(self, error: BaseException, *, run_id: Any = None, **kwargs: Any) -> None:
        run_id_str = str(run_id) if run_id else ""
        latency = self._elapsed(run_id_str)
        _write(self._store, IngestEvent(
            trace_id=self._trace_id,
            agent=self._agent_name,
            action="chain",
            status="FAILED",
            span_id=run_id_str,
            event_type="chain_error",
            latency_ms=latency,
            error=str(error),
        ))

    def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, *, run_id: Any = None, parent_run_id: Any = None, **kwargs: Any
    ) -> None:
        run_id_str = str(run_id) if run_id else str(uuid.uuid4())
        self._start_times[run_id_str] = time.time()
        tool_name = (serialized or {}).get("name") or "tool"
        _write(self._store, IngestEvent(
            trace_id=self._trace_id,
            agent=self._agent_name,
            action=f"tool:{tool_name}",
            status="STARTED",
            span_id=run_id_str,
            parent_span_id=str(parent_run_id) if parent_run_id else None,
            event_type="tool_start",
        ))

    def on_tool_end(self, output: str, *, run_id: Any = None, **kwargs: Any) -> None:
        run_id_str = str(run_id) if run_id else ""
        latency = self._elapsed(run_id_str)
        _write(self._store, IngestEvent(
            trace_id=self._trace_id,
            agent=self._agent_name,
            action="tool",
            status="COMPLETED",
            span_id=run_id_str,
            event_type="tool_end",
            latency_ms=latency,
        ))

    def on_tool_error(self, error: BaseException, *, run_id: Any = None, **kwargs: Any) -> None:
        run_id_str = str(run_id) if run_id else ""
        latency = self._elapsed(run_id_str)
        _write(self._store, IngestEvent(
            trace_id=self._trace_id,
            agent=self._agent_name,
            action="tool",
            status="FAILED",
            span_id=run_id_str,
            event_type="tool_error",
            latency_ms=latency,
            error=str(error),
        ))

    def on_llm_end(self, response: Any, *, run_id: Any = None, **kwargs: Any) -> None:
        """Capture LLM token usage — the key metric for LLM-based agent complexity."""
        run_id_str = str(run_id) if run_id else ""
        latency = self._elapsed(run_id_str)

        token_usage: Dict[str, Any] = {}
        try:
            llm_output = getattr(response, "llm_output", None) or {}
            token_usage = llm_output.get("token_usage") or {}
        except Exception:
            pass

        prompt_tokens = int(token_usage.get("prompt_tokens") or 0)
        completion_tokens = int(token_usage.get("completion_tokens") or 0)

        _write(self._store, IngestEvent(
            trace_id=self._trace_id,
            agent=self._agent_name,
            action="llm_call",
            status="COMPLETED",
            span_id=run_id_str,
            event_type="llm_end",
            latency_ms=latency,
            decision={"token_usage": token_usage},
            llm_prompt_tokens=prompt_tokens or None,
            llm_completion_tokens=completion_tokens or None,
        ))

    def on_llm_error(self, error: BaseException, *, run_id: Any = None, **kwargs: Any) -> None:
        run_id_str = str(run_id) if run_id else ""
        _write(self._store, IngestEvent(
            trace_id=self._trace_id,
            agent=self._agent_name,
            action="llm_call",
            status="FAILED",
            span_id=run_id_str,
            event_type="llm_error",
            error=str(error),
        ))

    def on_agent_action(self, action: Any, *, run_id: Any = None, **kwargs: Any) -> None:
        tool = getattr(action, "tool", None) or str(action)
        _write(self._store, IngestEvent(
            trace_id=self._trace_id,
            agent=self._agent_name,
            action=f"agent_action:{tool}",
            status="STARTED",
            span_id=str(run_id) if run_id else None,
            event_type="agent_action",
        ))

    # ------------------------------------------------------------------ #
    # Generic event hook (non-LangChain usage)                            #
    # ------------------------------------------------------------------ #

    def on_event(self, payload: Dict[str, Any]) -> IngestEvent:
        """Ingest a raw dict — usable without LangChain installed."""
        payload.setdefault("trace_id", self._trace_id)
        payload.setdefault("agent", self._agent_name)
        event = normalize_event(payload)
        _write(self._store, event)
        return event

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _elapsed(self, run_id: str) -> Optional[float]:
        start = self._start_times.pop(run_id, None)
        if start is None:
            return None
        return round((time.time() - start) * 1000, 2)
