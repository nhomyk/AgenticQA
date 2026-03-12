"""
Synthetic Probe Runner — Continuous health checks as K8s CronJobs.

INTERVIEW CONCEPT: Synthetic monitoring runs known-good operations
against your system continuously. Unlike real-user monitoring, synthetic
probes:
    - Run 24/7 even with zero traffic
    - Have known expected outcomes (deterministic)
    - Detect issues before customers do
    - Can be deployed as K8s CronJobs or DaemonSets

In K8s, Kuberhealthy is the popular open-source tool for this. This
module provides a simpler, purpose-built alternative that generates
CronJob manifests and checks their results.

Common synthetic probes for a platform like Domino:
    1. DNS resolution (CoreDNS alive?)
    2. Storage mount (can write to PVC?)
    3. API server reachable (kubectl works?)
    4. Ingress responds (HTTP 200?)
    5. GPU allocatable (nvidia-smi works on GPU nodes?)
    6. Service mesh (mTLS handshake succeeds?)

Usage:
    runner = SyntheticProbeRunner(kubeconfig="/path/to/kubeconfig")
    runner.register("dns-check", DNSProbeSpec(...))
    runner.register("storage-check", StorageProbeSpec(...))
    manifests = runner.generate_manifests()  # K8s CronJob YAMLs
    results = runner.run_all()               # Execute probes now
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


class ProbeStatus(Enum):
    """Outcome of a synthetic probe."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    ERROR = "error"


@dataclass
class ProbeSpec:
    """Specification for a synthetic probe."""

    name: str
    description: str
    namespace: str = "default"
    schedule: str = "*/5 * * * *"  # Every 5 minutes
    image: str = "busybox:1.36"
    command: list[str] = field(default_factory=list)
    timeout_seconds: int = 30
    success_threshold: int = 1
    taxonomy_ids: list[str] = field(default_factory=list)  # Related failure scenarios


@dataclass
class ProbeResult:
    """Result of running a synthetic probe."""

    name: str
    status: ProbeStatus
    latency_ms: float = 0.0
    output: str = ""
    error: str = ""
    timestamp: float = 0.0
    taxonomy_ids: list[str] = field(default_factory=list)


# =============================================================================
# BUILT-IN PROBE SPECS
# =============================================================================


def dns_probe(namespace: str = "default") -> ProbeSpec:
    """
    Probe that verifies DNS resolution works.

    INTERVIEW CONCEPT: If this probe fails, CoreDNS is down or
    misconfigured. This is the single most impactful failure mode
    because ALL service discovery depends on DNS.
    """
    return ProbeSpec(
        name="dns-resolution",
        description="Verify CoreDNS resolves kubernetes.default.svc",
        namespace=namespace,
        command=["nslookup", "kubernetes.default.svc.cluster.local"],
        taxonomy_ids=["NET-001"],
    )


def api_server_probe(namespace: str = "default") -> ProbeSpec:
    """
    Probe that verifies the API server is reachable.

    INTERVIEW CONCEPT: The API server is the gateway to the entire
    cluster. If it's down, no operations can proceed. This probe
    uses the anonymous health endpoint (no auth needed).
    """
    return ProbeSpec(
        name="api-server-health",
        description="Verify K8s API server responds to health check",
        namespace=namespace,
        image="curlimages/curl:8.5.0",
        command=["curl", "-sf", "https://kubernetes.default.svc/healthz", "-k"],
        taxonomy_ids=["CP-002"],
    )


def storage_probe(namespace: str = "default") -> ProbeSpec:
    """
    Probe that verifies storage write/read works.

    INTERVIEW CONCEPT: Storage failures are silent — the PVC looks
    healthy but writes fail. This probe creates a temp file on a
    volume to verify the full write path works.
    """
    return ProbeSpec(
        name="storage-write-read",
        description="Verify file write/read on emptyDir volume",
        namespace=namespace,
        command=[
            "sh", "-c",
            "echo 'probe-test' > /tmp/probe.txt && cat /tmp/probe.txt | grep probe-test",
        ],
        taxonomy_ids=["STOR-001", "STOR-002"],
    )


def network_egress_probe(namespace: str = "default") -> ProbeSpec:
    """
    Probe that verifies outbound network connectivity.

    INTERVIEW CONCEPT: Egress can be blocked by NetworkPolicies,
    NAT gateway failures, or corporate proxy issues. This probe
    verifies that pods can reach external services.
    """
    return ProbeSpec(
        name="network-egress",
        description="Verify outbound connectivity to external DNS",
        namespace=namespace,
        command=["nslookup", "google.com"],
        taxonomy_ids=["NET-003"],
    )


BUILTIN_PROBES = {
    "dns": dns_probe,
    "api-server": api_server_probe,
    "storage": storage_probe,
    "network-egress": network_egress_probe,
}


class SyntheticProbeRunner:
    """
    Manages and executes synthetic health probes.

    Can run probes immediately (for testing) or generate CronJob
    manifests for continuous monitoring.
    """

    def __init__(
        self,
        kubeconfig: Optional[str] = None,
        context: Optional[str] = None,
    ) -> None:
        self._kubeconfig = kubeconfig
        self._context = context
        self._probes: dict[str, ProbeSpec] = {}

    def register(self, name: str, spec: ProbeSpec) -> None:
        """Register a probe spec."""
        self._probes[name] = spec

    def register_builtin(self, namespace: str = "default") -> None:
        """Register all built-in probes."""
        for name, factory in BUILTIN_PROBES.items():
            self._probes[name] = factory(namespace)

    def run_probe(self, name: str) -> ProbeResult:
        """
        Execute a single probe immediately using kubectl run.

        This creates a temporary pod, runs the command, captures
        the output, and deletes the pod.
        """
        spec = self._probes.get(name)
        if not spec:
            return ProbeResult(
                name=name,
                status=ProbeStatus.ERROR,
                error=f"Unknown probe: {name}",
            )

        start = time.monotonic()
        pod_name = f"probe-{name}-{int(time.time())}"

        output = self._kubectl(
            "run", pod_name, "--rm", "-i", "--restart=Never",
            "--image", spec.image,
            "-n", spec.namespace,
            f"--timeout={spec.timeout_seconds}s",
            "--", *spec.command,
        )

        latency = (time.monotonic() - start) * 1000

        if output is None:
            return ProbeResult(
                name=name,
                status=ProbeStatus.UNHEALTHY,
                latency_ms=latency,
                error="Probe command failed",
                timestamp=time.time(),
                taxonomy_ids=spec.taxonomy_ids,
            )

        return ProbeResult(
            name=name,
            status=ProbeStatus.HEALTHY,
            latency_ms=latency,
            output=output.strip(),
            timestamp=time.time(),
            taxonomy_ids=spec.taxonomy_ids,
        )

    def run_all(self) -> list[ProbeResult]:
        """Execute all registered probes."""
        return [self.run_probe(name) for name in self._probes]

    def generate_cronjob(self, name: str) -> Optional[dict]:
        """
        Generate a K8s CronJob manifest for a probe.

        INTERVIEW CONCEPT: CronJobs create Jobs on a schedule. Each Job
        creates a Pod. The CronJob controller manages:
            - concurrencyPolicy: Forbid (skip if previous still running)
            - successfulJobsHistoryLimit: How many completed Jobs to keep
            - failedJobsHistoryLimit: How many failed Jobs to keep
            - startingDeadlineSeconds: Grace period for missed schedules
        """
        spec = self._probes.get(name)
        if not spec:
            return None

        return {
            "apiVersion": "batch/v1",
            "kind": "CronJob",
            "metadata": {
                "name": f"synthetic-probe-{name}",
                "namespace": spec.namespace,
                "labels": {
                    "app": "agenticqa-probes",
                    "probe": name,
                },
            },
            "spec": {
                "schedule": spec.schedule,
                "concurrencyPolicy": "Forbid",
                "successfulJobsHistoryLimit": 3,
                "failedJobsHistoryLimit": 3,
                "startingDeadlineSeconds": 60,
                "jobTemplate": {
                    "spec": {
                        "backoffLimit": 1,
                        "activeDeadlineSeconds": spec.timeout_seconds,
                        "template": {
                            "metadata": {
                                "labels": {"probe": name},
                            },
                            "spec": {
                                "restartPolicy": "Never",
                                "containers": [
                                    {
                                        "name": "probe",
                                        "image": spec.image,
                                        "command": spec.command,
                                        "resources": {
                                            "requests": {
                                                "cpu": "10m",
                                                "memory": "16Mi",
                                            },
                                            "limits": {
                                                "cpu": "100m",
                                                "memory": "64Mi",
                                            },
                                        },
                                    }
                                ],
                            },
                        },
                    }
                },
            },
        }

    def generate_all_manifests(self) -> str:
        """Generate YAML manifests for all registered probes."""
        manifests = []
        for name in self._probes:
            cj = self.generate_cronjob(name)
            if cj:
                manifests.append(yaml.dump(cj, default_flow_style=False))
        return "---\n".join(manifests)

    def summary(self, results: list[ProbeResult]) -> dict:
        """Summarize probe results."""
        by_status = {}
        for r in results:
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1

        taxonomy_covered = set()
        for r in results:
            if r.status == ProbeStatus.HEALTHY:
                taxonomy_covered.update(r.taxonomy_ids)

        return {
            "total_probes": len(results),
            "by_status": by_status,
            "taxonomy_ids_covered": sorted(taxonomy_covered),
            "healthy_rate": (
                sum(1 for r in results if r.status == ProbeStatus.HEALTHY)
                / max(len(results), 1)
                * 100
            ),
        }

    # ── Private helpers ──────────────────────────────────────────────────

    def _kubectl(self, *args: str) -> Optional[str]:
        cmd = ["kubectl"]
        if self._kubeconfig:
            cmd.extend(["--kubeconfig", self._kubeconfig])
        if self._context:
            cmd.extend(["--context", self._context])
        cmd.extend(args)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=60,
            )
            return result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning("kubectl failed: %s", e)
            return None
