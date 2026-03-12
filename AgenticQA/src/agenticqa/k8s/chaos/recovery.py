"""
Recovery Assertion Helpers — Verify system recovery after fault injection.

INTERVIEW CONCEPT: The most important part of chaos engineering isn't
breaking things — it's verifying recovery. These helpers codify what
"recovered" means for different K8s resource types.

Recovery patterns:
    Pod recovery     → Controller recreates pod, new pod reaches Running
    Service recovery → Endpoints repopulated after pod replacement
    Node recovery    → Uncordon + pods rescheduled back
    DNS recovery     → CoreDNS pods back, resolution works
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RecoveryAssertion:
    """Result of a recovery check."""

    name: str
    passed: bool
    elapsed_seconds: float
    details: str = ""


def assert_pod_recovery(
    kubectl_fn,
    namespace: str,
    label_selector: str,
    expected_count: int = 1,
    timeout: int = 120,
    poll_interval: int = 5,
) -> RecoveryAssertion:
    """
    Assert that pods matching a selector return to Running state.

    INTERVIEW CONCEPT: After killing a pod managed by a Deployment,
    the ReplicaSet controller notices the actual count < desired count
    and creates a replacement. Time to recovery depends on:
        - Image pull time (if not cached on the node)
        - Init containers (if any)
        - Startup probe (if defined)
        - Resource availability (scheduling)
    """
    start = time.monotonic()
    deadline = start + timeout

    while time.monotonic() < deadline:
        output = kubectl_fn(
            "get", "pods", "-n", namespace,
            "-l", label_selector,
            "-o", "json",
        )
        if output:
            data = json.loads(output)
            running = [
                p for p in data.get("items", [])
                if p.get("status", {}).get("phase") == "Running"
                and all(
                    c.get("ready", False)
                    for c in p.get("status", {}).get("containerStatuses", [])
                )
            ]
            if len(running) >= expected_count:
                elapsed = time.monotonic() - start
                return RecoveryAssertion(
                    name="pod_recovery",
                    passed=True,
                    elapsed_seconds=elapsed,
                    details=f"{len(running)}/{expected_count} pods recovered in {elapsed:.1f}s",
                )
        time.sleep(poll_interval)

    elapsed = time.monotonic() - start
    return RecoveryAssertion(
        name="pod_recovery",
        passed=False,
        elapsed_seconds=elapsed,
        details=f"Timed out waiting for {expected_count} Running pods after {timeout}s",
    )


def assert_endpoint_recovery(
    kubectl_fn,
    namespace: str,
    service_name: str,
    min_endpoints: int = 1,
    timeout: int = 60,
    poll_interval: int = 5,
) -> RecoveryAssertion:
    """
    Assert that a Service has healthy endpoints.

    INTERVIEW CONCEPT: Services discover pods via label selectors.
    The endpoints controller watches pods and populates the Endpoints
    object. When a pod passes its readiness probe, its IP appears in
    the Endpoints list. This is how traffic gets routed.
    """
    start = time.monotonic()
    deadline = start + timeout

    while time.monotonic() < deadline:
        output = kubectl_fn(
            "get", "endpoints", service_name, "-n", namespace,
            "-o", "jsonpath={.subsets[*].addresses[*].ip}",
        )
        if output:
            ips = output.strip().split()
            if len(ips) >= min_endpoints:
                elapsed = time.monotonic() - start
                return RecoveryAssertion(
                    name="endpoint_recovery",
                    passed=True,
                    elapsed_seconds=elapsed,
                    details=f"{len(ips)} endpoints recovered in {elapsed:.1f}s",
                )
        time.sleep(poll_interval)

    return RecoveryAssertion(
        name="endpoint_recovery",
        passed=False,
        elapsed_seconds=time.monotonic() - start,
        details=f"Timed out waiting for {min_endpoints} endpoints on {service_name}",
    )


def assert_dns_resolution(
    kubectl_fn,
    namespace: str = "default",
    service_name: str = "kubernetes",
    target_namespace: str = "default",
    timeout: int = 60,
    poll_interval: int = 5,
) -> RecoveryAssertion:
    """
    Assert DNS resolution works from within the cluster.

    INTERVIEW CONCEPT: K8s DNS resolution follows this pattern:
        <service>.<namespace>.svc.cluster.local
    The pod's /etc/resolv.conf has:
        search <ns>.svc.cluster.local svc.cluster.local cluster.local
    So "kubernetes" resolves to "kubernetes.default.svc.cluster.local"
    when queried from the default namespace.
    """
    start = time.monotonic()
    fqdn = f"{service_name}.{target_namespace}.svc.cluster.local"

    # Use a temporary pod to run nslookup
    while time.monotonic() < start + timeout:
        output = kubectl_fn(
            "run", "dns-test", "--rm", "-i", "--restart=Never",
            "--image=busybox:1.36", "-n", namespace,
            "--", "nslookup", fqdn,
        )
        if output and "Address" in output:
            elapsed = time.monotonic() - start
            return RecoveryAssertion(
                name="dns_resolution",
                passed=True,
                elapsed_seconds=elapsed,
                details=f"DNS resolved {fqdn} in {elapsed:.1f}s",
            )
        time.sleep(poll_interval)

    return RecoveryAssertion(
        name="dns_resolution",
        passed=False,
        elapsed_seconds=time.monotonic() - start,
        details=f"DNS resolution failed for {fqdn} after {timeout}s",
    )


def assert_node_ready(
    kubectl_fn,
    node_name: str,
    timeout: int = 120,
    poll_interval: int = 10,
) -> RecoveryAssertion:
    """
    Assert that a node returns to Ready condition.

    INTERVIEW CONCEPT: Node conditions are reported by the kubelet.
    The key conditions:
        Ready           → kubelet is healthy and can accept pods
        MemoryPressure  → node is running low on memory
        DiskPressure    → node is running low on disk
        PIDPressure     → too many processes on the node
        NetworkUnavailable → node network is misconfigured
    """
    start = time.monotonic()
    deadline = start + timeout

    while time.monotonic() < deadline:
        output = kubectl_fn(
            "get", "node", node_name,
            "-o", "jsonpath={.status.conditions[?(@.type=='Ready')].status}",
        )
        if output and output.strip() == "True":
            elapsed = time.monotonic() - start
            return RecoveryAssertion(
                name="node_ready",
                passed=True,
                elapsed_seconds=elapsed,
                details=f"Node {node_name} Ready in {elapsed:.1f}s",
            )
        time.sleep(poll_interval)

    return RecoveryAssertion(
        name="node_ready",
        passed=False,
        elapsed_seconds=time.monotonic() - start,
        details=f"Node {node_name} not Ready after {timeout}s",
    )
