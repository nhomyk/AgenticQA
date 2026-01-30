"""Delegation tracking for debugging and observability"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class DelegationEvent:
    """Represents a single delegation event"""
    from_agent: str
    to_agent: str
    task: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    duration_ms: Optional[float] = None
    depth: int = 0


class DelegationTracker:
    """
    Tracks delegation chains for debugging, observability, and Ragas evaluation.
    Provides complete visibility into agent collaboration patterns.
    """

    def __init__(self):
        self.events: List[DelegationEvent] = []
        self.current_chain: List[str] = []
        self.root_agent: Optional[str] = None

    def start_request(self, agent_name: str):
        """Start tracking a new root request"""
        self.root_agent = agent_name
        self.current_chain = [agent_name]
        self.events = []

    def record_delegation(
        self,
        from_agent: str,
        to_agent: str,
        task: Dict[str, Any],
        depth: int
    ) -> DelegationEvent:
        """Record the start of a delegation"""
        event = DelegationEvent(
            from_agent=from_agent,
            to_agent=to_agent,
            task=task,
            depth=depth
        )
        self.events.append(event)
        self.current_chain.append(to_agent)
        return event

    def record_result(
        self,
        event: DelegationEvent,
        result: Dict[str, Any],
        duration_ms: float
    ):
        """Record the completion of a delegation"""
        event.result = result
        event.duration_ms = duration_ms
        if self.current_chain and self.current_chain[-1] == event.to_agent:
            self.current_chain.pop()

    def record_error(self, event: DelegationEvent, error: str):
        """Record a delegation failure"""
        event.error = error
        if self.current_chain and self.current_chain[-1] == event.to_agent:
            self.current_chain.pop()

    def get_delegation_chain(self) -> List[str]:
        """Get the current delegation chain"""
        return self.current_chain.copy()

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all delegations for this request"""
        successful = [e for e in self.events if e.result is not None]
        failed = [e for e in self.events if e.error is not None]

        return {
            "root_agent": self.root_agent,
            "total_delegations": len(self.events),
            "successful": len(successful),
            "failed": len(failed),
            "max_depth": max([e.depth for e in self.events]) if self.events else 0,
            "total_duration_ms": sum([e.duration_ms for e in self.events if e.duration_ms]) if self.events else 0,
            "delegation_path": self._build_delegation_tree(),
            "events": [self._event_to_dict(e) for e in self.events]
        }

    def _build_delegation_tree(self) -> str:
        """Build a visual representation of the delegation tree"""
        if not self.events:
            return f"{self.root_agent}"

        lines = [f"{self.root_agent}"]
        for event in self.events:
            indent = "  " * event.depth
            status = "✅" if event.result else ("❌" if event.error else "⏳")
            lines.append(f"{indent}└─ {status} {event.to_agent}")

        return "\n".join(lines)

    def _event_to_dict(self, event: DelegationEvent) -> Dict:
        """Convert delegation event to dict for serialization"""
        return {
            "from_agent": event.from_agent,
            "to_agent": event.to_agent,
            "timestamp": event.timestamp,
            "duration_ms": event.duration_ms,
            "depth": event.depth,
            "success": event.result is not None,
            "error": event.error
        }
