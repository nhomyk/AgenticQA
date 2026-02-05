"""Delegation tracking for debugging and observability"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
import uuid
import logging
import os

logger = logging.getLogger(__name__)


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
    delegation_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class DelegationTracker:
    """
    Tracks delegation chains for debugging, observability, and Ragas evaluation.
    Provides complete visibility into agent collaboration patterns.

    Dual-Write Pattern:
    - In-memory tracking for real-time access
    - Neo4j persistence for analytics and GraphRAG
    """

    def __init__(self, enable_neo4j: bool = True, deployment_id: Optional[str] = None):
        self.events: List[DelegationEvent] = []
        self.current_chain: List[str] = []
        self.root_agent: Optional[str] = None
        self.deployment_id = deployment_id or os.getenv("GITHUB_RUN_ID", f"local-{uuid.uuid4()}")

        # Neo4j integration (optional)
        self.enable_neo4j = enable_neo4j
        self.graph_store = None

        if self.enable_neo4j:
            try:
                from agenticqa.graph import DelegationGraphStore
                self.graph_store = DelegationGraphStore()
                self.graph_store.connect()
                logger.info("Neo4j delegation tracking enabled")
            except ImportError:
                logger.warning("Neo4j package not installed. Install with: pip install neo4j")
                self.enable_neo4j = False
            except Exception as e:
                logger.warning(f"Failed to connect to Neo4j: {e}. Continuing with in-memory tracking only.")
                self.enable_neo4j = False

    def start_request(self, agent_name: str):
        """Start tracking a new root request"""
        self.root_agent = agent_name
        self.current_chain = [agent_name]
        self.events = []

    def record_delegation(
        self, from_agent: str, to_agent: str, task: Dict[str, Any], depth: int
    ) -> DelegationEvent:
        """Record the start of a delegation"""
        event = DelegationEvent(from_agent=from_agent, to_agent=to_agent, task=task, depth=depth)
        self.events.append(event)
        self.current_chain.append(to_agent)

        # Dual-write: Also record to Neo4j
        if self.enable_neo4j and self.graph_store:
            try:
                self.graph_store.record_delegation(
                    from_agent=from_agent,
                    to_agent=to_agent,
                    task=task,
                    delegation_id=event.delegation_id,
                    depth=depth,
                    deployment_id=self.deployment_id
                )
            except Exception as e:
                logger.error(f"Failed to record delegation to Neo4j: {e}")

        return event

    def record_result(self, event: DelegationEvent, result: Dict[str, Any], duration_ms: float):
        """Record the completion of a delegation"""
        event.result = result
        event.duration_ms = duration_ms
        if self.current_chain and self.current_chain[-1] == event.to_agent:
            self.current_chain.pop()

        # Dual-write: Update Neo4j
        if self.enable_neo4j and self.graph_store:
            try:
                self.graph_store.update_delegation_result(
                    delegation_id=event.delegation_id,
                    status="success",
                    duration_ms=duration_ms,
                    result=result
                )
            except Exception as e:
                logger.error(f"Failed to update delegation result in Neo4j: {e}")

    def record_error(self, event: DelegationEvent, error: str):
        """Record a delegation failure"""
        event.error = error
        if self.current_chain and self.current_chain[-1] == event.to_agent:
            self.current_chain.pop()

        # Dual-write: Update Neo4j
        if self.enable_neo4j and self.graph_store:
            try:
                self.graph_store.update_delegation_result(
                    delegation_id=event.delegation_id,
                    status="failed",
                    duration_ms=0,
                    error_message=error
                )
            except Exception as e:
                logger.error(f"Failed to update delegation error in Neo4j: {e}")

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
            "total_duration_ms": sum([e.duration_ms for e in self.events if e.duration_ms])
            if self.events
            else 0,
            "delegation_path": self._build_delegation_tree(),
            "events": [self._event_to_dict(e) for e in self.events],
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
            "error": event.error,
            "delegation_id": event.delegation_id,
        }

    def close(self):
        """Close Neo4j connection"""
        if self.graph_store:
            self.graph_store.close()

    def get_neo4j_stats(self) -> Optional[Dict]:
        """Get statistics from Neo4j (if enabled)"""
        if not self.enable_neo4j or not self.graph_store:
            return None

        try:
            return self.graph_store.get_database_stats()
        except Exception as e:
            logger.error(f"Failed to get Neo4j stats: {e}")
            return None
