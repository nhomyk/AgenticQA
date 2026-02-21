"""Universal Constitutional Wrapper — governs any agent framework."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from agenticqa.constitutional_gate import (
    check_action,
    ConstitutionalViolationError,
)
from agenticqa.verification.feedback_loop import RelevanceFeedback
from agenticqa.verification.outcome_tracker import OutcomeTracker


class ConstitutionalWrapper:
    """
    Wraps any callable agent with AgenticQA's constitutional governance layer.

    On every invocation:
    1. Pre-checks the constitutional gate (ALLOW / REQUIRE_APPROVAL / DENY)
    2. Executes the wrapped agent if allowed
    3. Records outcome to the ML learning loop (feedback + outcome tracker)

    Compatible with AgentRegistry: exposes agent_name and agent_registry attributes.
    """

    def __init__(
        self,
        agent: Any,
        agent_name: str,
        framework: str,
        capabilities: Optional[List[str]] = None,
        scopes: Optional[Dict[str, Any]] = None,
    ):
        self.agent = agent
        self.agent_name = agent_name
        self.framework = framework
        self.capabilities = capabilities or []
        self._scopes = scopes or {}
        self.agent_registry = None  # injected by AgentRegistry.register_agent()

        # Auto-enroll in ML learning loop
        self.feedback = RelevanceFeedback()
        self.outcome_tracker = OutcomeTracker()

    # ------------------------------------------------------------------
    # Primary invocation interface
    # ------------------------------------------------------------------

    def invoke(self, input: Dict[str, Any], trace_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Invoke the wrapped agent with pre/post constitutional checks."""
        trace_id = trace_id or str(uuid.uuid4())
        context = {
            "agent": self.agent_name,
            "framework": self.framework,
            "trace_id": trace_id,
            "input_keys": list(input.keys()) if isinstance(input, dict) else [],
        }

        # --- Pre-check ---
        verdict = check_action("agent_invoke", context)
        if verdict["verdict"] == "DENY":
            raise ConstitutionalViolationError(
                f"[{self.agent_name}] Blocked by constitution: {verdict.get('reason')}"
            )
        if verdict["verdict"] == "REQUIRE_APPROVAL":
            return {
                "status": "awaiting_approval",
                "agent": self.agent_name,
                "framework": self.framework,
                "trace_id": trace_id,
                "reason": verdict.get("reason"),
                "law": verdict.get("law"),
            }

        # --- Execute ---
        started = datetime.now(timezone.utc)
        error = None
        result = None
        try:
            invoke_fn = getattr(self.agent, "invoke", None) or getattr(self.agent, "run", None)
            if callable(invoke_fn):
                result = invoke_fn(input, **kwargs)
            elif callable(self.agent):
                result = self.agent(input, **kwargs)
            else:
                raise TypeError(f"Wrapped agent {self.agent_name!r} has no invoke/run method and is not callable.")
        except ConstitutionalViolationError:
            raise
        except Exception as exc:
            error = str(exc)

        duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        success = error is None

        # --- Post: ML loop ---
        try:
            self.outcome_tracker.record_outcome(
                agent=self.agent_name,
                task_type="agent_invoke",
                success=success,
                duration_ms=duration_ms,
                metadata={"framework": self.framework, "trace_id": trace_id},
            )
        except Exception:
            pass  # never block execution due to telemetry failure

        if error:
            return {
                "status": "error",
                "agent": self.agent_name,
                "framework": self.framework,
                "trace_id": trace_id,
                "error": error,
                "duration_ms": duration_ms,
            }

        return {
            "status": "completed",
            "agent": self.agent_name,
            "framework": self.framework,
            "trace_id": trace_id,
            "result": result,
            "duration_ms": duration_ms,
        }

    def run(self, input: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Alias — some frameworks call .run() instead of .invoke()."""
        return self.invoke(input, **kwargs)

    def __call__(self, input: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        return self.invoke(input, **kwargs)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def describe(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "framework": self.framework,
            "capabilities": self.capabilities,
            "scopes": self._scopes,
            "governed": True,
        }
