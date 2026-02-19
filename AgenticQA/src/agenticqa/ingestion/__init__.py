"""AgenticQA ingestion layer — accepts events from any agent platform."""

from .event_schema import IngestEvent, normalize_event
from .adapters import LangChainCallbackAdapter, GenericDictAdapter

__all__ = ["IngestEvent", "normalize_event", "LangChainCallbackAdapter", "GenericDictAdapter"]
