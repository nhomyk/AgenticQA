"""Chaos engineering: fault injection via Chaos Mesh, Litmus, or native kubectl."""

from agenticqa.k8s.chaos.engine import ChaosEngine
from agenticqa.k8s.chaos.experiments import BUILTIN_EXPERIMENTS

__all__ = ["ChaosEngine", "BUILTIN_EXPERIMENTS"]
