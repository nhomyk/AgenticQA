"""
AgenticQA Kubernetes Testing Framework
=======================================

A comprehensive K8s failure testing toolkit that exercises the full range
of infrastructure failure modes (~450 scenarios across 7 categories).

Architecture:
    taxonomy    → Failure scenario registry (YAML-driven, tagged, filterable)
    cluster     → kind/k3d cluster lifecycle management
    pod_validator → Pod health assertion across namespaces
    chaos/      → Fault injection engine (Chaos Mesh / Litmus / native)
    network/    → DNS, NetworkPolicy, and connectivity testing
    observability/ → Prometheus rule validation, synthetic probes
    coverage    → Maps test results back to taxonomy for gap analysis

Interview-ready concepts in each module:
    - Pod lifecycle states and probe mechanics (pod_validator)
    - Scheduling constraints: affinity, taints, tolerations, PDB (chaos/)
    - CNI, Services, DNS resolution, NetworkPolicy (network/)
    - Prometheus PromQL, alerting rules, recording rules (observability/)
    - Control plane components and failure domains (taxonomy)
"""

from agenticqa.k8s.taxonomy import FailureTaxonomy, Scenario
from agenticqa.k8s.cluster import KindCluster
from agenticqa.k8s.pod_validator import PodValidator
from agenticqa.k8s.coverage import CoverageTracker

__all__ = [
    "FailureTaxonomy",
    "Scenario",
    "KindCluster",
    "PodValidator",
    "CoverageTracker",
]
