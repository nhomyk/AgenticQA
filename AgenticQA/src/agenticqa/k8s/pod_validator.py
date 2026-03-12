"""
Pod Health Validator — Assert pod states across namespaces.

INTERVIEW CONCEPT: Pod lifecycle and health checking is the most
fundamental K8s operations question. This module exercises every
aspect of it:

    Pod Status Phases:
        Pending     → Waiting for scheduling or image pull
        Running     → At least one container is running
        Succeeded   → All containers exited with code 0 (Jobs)
        Failed      → At least one container exited with non-zero
        Unknown     → Node communication lost

    Container States (within a running pod):
        Waiting     → Not yet started (pulling image, init containers)
        Running     → Executing
        Terminated  → Exited (check exit code and reason)

    QoS Classes (determines eviction priority):
        Guaranteed  → requests == limits for all containers
        Burstable   → at least one request or limit set
        BestEffort  → no requests or limits set (evicted first)

Usage:
    validator = PodValidator(kubeconfig="/path/to/kubeconfig")
    report = validator.validate_namespace("default")
    report = validator.validate_all()
    issues = validator.find_issues()
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ContainerStatus:
    """Status of a single container within a pod."""

    name: str
    ready: bool
    state: str  # "running", "waiting", "terminated"
    reason: str = ""  # e.g., "OOMKilled", "CrashLoopBackOff", "ImagePullBackOff"
    exit_code: Optional[int] = None
    restart_count: int = 0
    image: str = ""


@dataclass
class PodHealth:
    """Health assessment of a single pod."""

    name: str
    namespace: str
    phase: str  # Pending, Running, Succeeded, Failed, Unknown
    qos_class: str  # Guaranteed, Burstable, BestEffort
    node: str = ""
    containers: list[ContainerStatus] = field(default_factory=list)
    conditions: dict[str, bool] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        """Pod is healthy if Running with all containers ready."""
        if self.phase == "Succeeded":
            return True  # Completed Job pods
        return self.phase == "Running" and all(c.ready for c in self.containers)

    @property
    def taxonomy_ids(self) -> list[str]:
        """Map current issues to failure taxonomy IDs for coverage tracking."""
        ids = []
        for c in self.containers:
            if c.reason == "OOMKilled":
                ids.append("POD-001")
            elif c.reason == "CrashLoopBackOff":
                ids.append("POD-002")
            elif c.reason in ("ImagePullBackOff", "ErrImagePull"):
                ids.append("POD-003")
            elif c.state == "waiting" and c.reason == "":
                ids.append("POD-008")  # Likely init container
        if self.phase == "Failed" and any(
            "Evicted" in i for i in self.issues
        ):
            ids.append("POD-004")
        return ids


@dataclass
class NamespaceReport:
    """Validation report for a single namespace."""

    namespace: str
    total_pods: int = 0
    healthy_pods: int = 0
    unhealthy_pods: int = 0
    pods: list[PodHealth] = field(default_factory=list)

    @property
    def health_percentage(self) -> float:
        if self.total_pods == 0:
            return 100.0
        return (self.healthy_pods / self.total_pods) * 100

    @property
    def issues(self) -> list[dict]:
        """All issues across all pods in this namespace."""
        result = []
        for pod in self.pods:
            if not pod.healthy:
                result.append(
                    {
                        "pod": pod.name,
                        "phase": pod.phase,
                        "issues": pod.issues,
                        "taxonomy_ids": pod.taxonomy_ids,
                    }
                )
        return result


class PodValidator:
    """
    Validates pod health across a K8s cluster.

    Connects via kubeconfig (file path or in-cluster auto-detection).
    Can validate individual namespaces or the entire cluster.
    Maps issues to the failure taxonomy for coverage tracking.
    """

    def __init__(
        self,
        kubeconfig: Optional[str] = None,
        context: Optional[str] = None,
    ) -> None:
        self._kubeconfig = kubeconfig
        self._context = context

    def validate_namespace(self, namespace: str) -> NamespaceReport:
        """
        Validate all pods in a namespace.

        INTERVIEW CONCEPT: In production, you'd use this after a deployment
        to verify all pods are healthy. This is the programmatic equivalent
        of "kubectl get pods -n <ns>" + "kubectl describe pod" for each.
        """
        pods_json = self._kubectl(
            "get", "pods", "-n", namespace, "-o", "json"
        )
        if pods_json is None:
            return NamespaceReport(namespace=namespace)

        data = json.loads(pods_json)
        pods: list[PodHealth] = []

        for item in data.get("items", []):
            pod = self._parse_pod(item, namespace)
            pods.append(pod)

        healthy = sum(1 for p in pods if p.healthy)
        return NamespaceReport(
            namespace=namespace,
            total_pods=len(pods),
            healthy_pods=healthy,
            unhealthy_pods=len(pods) - healthy,
            pods=pods,
        )

    def validate_all(self) -> list[NamespaceReport]:
        """Validate all pods across all namespaces."""
        ns_json = self._kubectl("get", "namespaces", "-o", "json")
        if ns_json is None:
            return []

        data = json.loads(ns_json)
        namespaces = [
            item["metadata"]["name"] for item in data.get("items", [])
        ]

        reports = []
        for ns in namespaces:
            reports.append(self.validate_namespace(ns))
        return reports

    def find_issues(
        self, namespace: Optional[str] = None
    ) -> list[dict]:
        """
        Find all unhealthy pods, optionally filtered by namespace.

        Returns a flat list of issue dicts with pod name, namespace,
        issues, and mapped taxonomy IDs.
        """
        if namespace:
            reports = [self.validate_namespace(namespace)]
        else:
            reports = self.validate_all()

        all_issues = []
        for report in reports:
            all_issues.extend(report.issues)
        return all_issues

    def check_probes(self, namespace: str) -> list[dict]:
        """
        Check probe configuration for all pods in a namespace.

        INTERVIEW CONCEPT: A common production issue is missing probes.
        Without a liveness probe, K8s can't self-heal. Without a readiness
        probe, traffic goes to pods that aren't ready. This method flags
        pods that are missing probes.
        """
        pods_json = self._kubectl(
            "get", "pods", "-n", namespace, "-o", "json"
        )
        if pods_json is None:
            return []

        data = json.loads(pods_json)
        findings = []

        for item in data.get("items", []):
            pod_name = item["metadata"]["name"]
            for container in item.get("spec", {}).get("containers", []):
                missing = []
                if "livenessProbe" not in container:
                    missing.append("liveness")
                if "readinessProbe" not in container:
                    missing.append("readiness")
                if "startupProbe" not in container:
                    missing.append("startup")
                if missing:
                    findings.append(
                        {
                            "pod": pod_name,
                            "container": container["name"],
                            "missing_probes": missing,
                            "severity": (
                                "critical" if "liveness" in missing else "medium"
                            ),
                        }
                    )
        return findings

    def check_resource_config(self, namespace: str) -> list[dict]:
        """
        Check resource requests/limits for all pods in a namespace.

        INTERVIEW CONCEPT: Without resource requests, the scheduler can't
        make informed decisions. Without limits, a single pod can consume
        all node resources. QoS class is determined by request/limit config:
            - Guaranteed: requests == limits (best eviction protection)
            - Burstable: partial requests/limits
            - BestEffort: none (evicted first under pressure)
        """
        pods_json = self._kubectl(
            "get", "pods", "-n", namespace, "-o", "json"
        )
        if pods_json is None:
            return []

        data = json.loads(pods_json)
        findings = []

        for item in data.get("items", []):
            pod_name = item["metadata"]["name"]
            qos = item.get("status", {}).get("qosClass", "BestEffort")
            for container in item.get("spec", {}).get("containers", []):
                resources = container.get("resources", {})
                issues = []
                if not resources.get("requests"):
                    issues.append("no resource requests")
                if not resources.get("limits"):
                    issues.append("no resource limits")
                if issues:
                    findings.append(
                        {
                            "pod": pod_name,
                            "container": container["name"],
                            "qos_class": qos,
                            "issues": issues,
                        }
                    )
        return findings

    # ── Private helpers ──────────────────────────────────────────────────

    def _parse_pod(self, item: dict, namespace: str) -> PodHealth:
        """Parse a pod JSON item into a PodHealth dataclass."""
        metadata = item.get("metadata", {})
        status = item.get("status", {})
        spec = item.get("spec", {})

        # Parse container statuses
        containers = []
        for cs in status.get("containerStatuses", []):
            state_info = cs.get("state", {})
            state, reason, exit_code = self._parse_container_state(state_info)
            containers.append(
                ContainerStatus(
                    name=cs.get("name", ""),
                    ready=cs.get("ready", False),
                    state=state,
                    reason=reason,
                    exit_code=exit_code,
                    restart_count=cs.get("restartCount", 0),
                    image=cs.get("image", ""),
                )
            )

        # Parse conditions
        conditions = {}
        for cond in status.get("conditions", []):
            conditions[cond["type"]] = cond["status"] == "True"

        # Identify issues
        issues = []
        phase = status.get("phase", "Unknown")
        if phase == "Pending":
            issues.append(f"Pod is Pending (not yet scheduled or pulling images)")
        elif phase == "Failed":
            issues.append(f"Pod failed: {status.get('reason', 'unknown reason')}")
        elif phase == "Unknown":
            issues.append("Pod status unknown (node may be unreachable)")

        for c in containers:
            if c.restart_count > 5:
                issues.append(
                    f"Container {c.name} has restarted {c.restart_count} times"
                )
            if c.reason:
                issues.append(f"Container {c.name}: {c.reason}")

        return PodHealth(
            name=metadata.get("name", ""),
            namespace=namespace,
            phase=phase,
            qos_class=status.get("qosClass", "BestEffort"),
            node=spec.get("nodeName", ""),
            containers=containers,
            conditions=conditions,
            issues=issues,
        )

    @staticmethod
    def _parse_container_state(
        state_info: dict,
    ) -> tuple[str, str, Optional[int]]:
        """Extract state, reason, and exit code from container state."""
        if "running" in state_info:
            return "running", "", None
        if "waiting" in state_info:
            waiting = state_info["waiting"]
            return "waiting", waiting.get("reason", ""), None
        if "terminated" in state_info:
            terminated = state_info["terminated"]
            return (
                "terminated",
                terminated.get("reason", ""),
                terminated.get("exitCode"),
            )
        return "unknown", "", None

    def _kubectl(self, *args: str) -> Optional[str]:
        """Run kubectl and return stdout, or None on failure."""
        cmd = ["kubectl"]
        if self._kubeconfig:
            cmd.extend(["--kubeconfig", self._kubeconfig])
        if self._context:
            cmd.extend(["--context", self._context])
        cmd.extend(args)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=30
            )
            return result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning("kubectl command failed: %s — %s", " ".join(cmd), e)
            return None
