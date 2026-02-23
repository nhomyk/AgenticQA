"""AgenticQA Agent Factory — scaffold any agent framework with constitutional governance."""

from .constitutional_wrapper import ConstitutionalWrapper
from .agent_factory import AgentFactory, SUPPORTED_FRAMEWORKS
from .adapters.sandboxed_adapter import SandboxedAgentAdapter, SandboxOutputFlaggedError
from .spec_extractor import AgentSpec, NaturalLanguageSpecExtractor

__all__ = [
    "ConstitutionalWrapper",
    "AgentFactory",
    "SUPPORTED_FRAMEWORKS",
    "SandboxedAgentAdapter",
    "SandboxOutputFlaggedError",
    "AgentSpec",
    "NaturalLanguageSpecExtractor",
]
