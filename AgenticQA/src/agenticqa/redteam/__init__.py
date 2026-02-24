"""Red Team module — adversarial probing and self-patching for AgenticQA governance."""

from .adversarial_generator import AdversarialGenerator
from .pattern_patcher import PatternPatcher

__all__ = ["AdversarialGenerator", "PatternPatcher"]
