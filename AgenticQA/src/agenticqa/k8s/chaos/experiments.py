"""
Built-in Chaos Experiments — Ready-to-use fault injection scenarios.

Each experiment maps to one or more failure taxonomy IDs and includes
the K8s concept being tested. These are the experiments you'd run in
a Domino staging environment.

INTERVIEW CONCEPT: When asked "how would you test K8s resilience?",
you can describe these exact experiments with their taxonomy IDs,
steady state hypotheses, and recovery expectations.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

import yaml

from agenticqa.k8s.chaos.engine import (
    ChaosExperiment,
    SteadyStateHypothesis,
)

logger = logging.getLogger(__name__)


# =============================================================================
# POD-LEVEL EXPERIMENTS
# =============================================================================


@dataclass
class PodKillExperiment(ChaosExperiment):
    """
    Kill a pod and verify the controller recreates it.

    INTERVIEW CONCEPT: Deployments create ReplicaSets which maintain
    desired replica count. Killing a pod should trigger the ReplicaSet
    controller to create a replacement. If it doesn't, the controller
    manager or the ReplicaSet itself may be broken.

    Tests: POD-002 (CrashLoopBackOff recovery), POD-005 (liveness recovery)
    """

    name: str = "pod-kill"
    taxonomy_id: str = "POD-002"
    namespace: str = "default"
    label_selector: str = ""
    pod_name: str = ""

    def inject(self, kubectl_fn) -> dict:
        if self.pod_name:
            target = self.pod_name
        else:
            # Find a pod matching the selector
            output = kubectl_fn(
                "get", "pods", "-n", self.namespace,
                "-l", self.label_selector,
                "-o", "jsonpath={.items[0].metadata.name}",
            )
            if not output:
                raise RuntimeError(
                    f"No pods found matching selector: {self.label_selector}"
                )
            target = output.strip()

        kubectl_fn("delete", "pod", target, "-n", self.namespace, "--grace-period=0")
        return {"killed_pod": target, "namespace": self.namespace}

    def cleanup(self, kubectl_fn) -> None:
        pass  # Controller should recreate the pod

    def steady_state(self) -> SteadyStateHypothesis:
        check_cmd = [
            "get", "pods", "-n", self.namespace,
            "-l", self.label_selector,
            "-o", "jsonpath={.items[*].status.phase}",
        ]
        return SteadyStateHypothesis(
            description="All pods matching selector are Running",
            check_command=check_cmd,
            expected_output="Running",
        )


@dataclass
class OOMExperiment(ChaosExperiment):
    """
    Deploy a pod that exceeds its memory limit to trigger OOMKilled.

    INTERVIEW CONCEPT: When a container exceeds its memory limit, the
    kernel's OOM killer terminates the process (SIGKILL). The container
    status shows OOMKilled. This is different from node-level OOM where
    the kubelet evicts pods based on QoS class.

    Tests: POD-001 (OOMKilled)
    """

    name: str = "oom-kill"
    taxonomy_id: str = "POD-001"
    namespace: str = "default"
    memory_limit: str = "64Mi"

    def _pod_manifest(self) -> dict:
        return {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "chaos-oom-test",
                "namespace": self.namespace,
                "labels": {"chaos-experiment": "oom-kill"},
            },
            "spec": {
                "restartPolicy": "Never",
                "containers": [
                    {
                        "name": "oom-trigger",
                        "image": "busybox:1.36",
                        "command": [
                            "sh", "-c",
                            # Allocate memory until OOMKilled
                            "dd if=/dev/zero of=/dev/null bs=1M count=1024",
                        ],
                        "resources": {
                            "limits": {"memory": self.memory_limit},
                            "requests": {"memory": self.memory_limit},
                        },
                    }
                ],
            },
        }

    def inject(self, kubectl_fn) -> dict:
        manifest = yaml.dump(self._pod_manifest())
        import subprocess
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(manifest)
            path = f.name
        try:
            kubectl_fn("apply", "-f", path)
        finally:
            Path(path).unlink(missing_ok=True)
        return {"pod": "chaos-oom-test", "memory_limit": self.memory_limit}

    def cleanup(self, kubectl_fn) -> None:
        kubectl_fn(
            "delete", "pod", "chaos-oom-test",
            "-n", self.namespace, "--ignore-not-found",
        )

    def steady_state(self) -> SteadyStateHypothesis:
        return SteadyStateHypothesis(
            description="OOM test pod should show OOMKilled status",
            check_command=[
                "get", "pod", "chaos-oom-test",
                "-n", self.namespace,
                "-o", "jsonpath={.status.containerStatuses[0].state.terminated.reason}",
            ],
            expected_output="OOMKilled",
            timeout_seconds=30,
        )


@dataclass
class ProbeFailureExperiment(ChaosExperiment):
    """
    Deploy a pod with a liveness probe that fails after N checks.

    INTERVIEW CONCEPT: Liveness probes tell kubelet whether the container
    is alive. If the probe fails `failureThreshold` consecutive times,
    kubelet kills the container and restarts it (per restartPolicy).

    Key parameters:
        initialDelaySeconds — wait before first probe (give app time to start)
        periodSeconds       — how often to probe
        failureThreshold    — consecutive failures before kill
        timeoutSeconds      — how long to wait for probe response

    Tests: POD-005 (Liveness probe failure)
    """

    name: str = "probe-failure"
    taxonomy_id: str = "POD-005"
    namespace: str = "default"
    probe_type: str = "liveness"  # "liveness" or "readiness"
    fail_after_seconds: int = 30

    def _pod_manifest(self) -> dict:
        probe_name = f"{self.probe_type}Probe"
        return {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": f"chaos-{self.probe_type}-test",
                "namespace": self.namespace,
                "labels": {"chaos-experiment": "probe-failure"},
            },
            "spec": {
                "restartPolicy": "Always",
                "containers": [
                    {
                        "name": "probe-target",
                        "image": "busybox:1.36",
                        "command": [
                            "sh", "-c",
                            # Create healthz file, remove it after N seconds
                            f"touch /tmp/healthz && sleep {self.fail_after_seconds} && rm /tmp/healthz && sleep 3600",
                        ],
                        probe_name: {
                            "exec": {"command": ["cat", "/tmp/healthz"]},
                            "initialDelaySeconds": 5,
                            "periodSeconds": 5,
                            "failureThreshold": 3,
                        },
                    }
                ],
            },
        }

    def inject(self, kubectl_fn) -> dict:
        manifest = yaml.dump(self._pod_manifest())
        import subprocess
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(manifest)
            path = f.name
        try:
            kubectl_fn("apply", "-f", path)
        finally:
            Path(path).unlink(missing_ok=True)
        return {
            "pod": f"chaos-{self.probe_type}-test",
            "probe_type": self.probe_type,
            "fail_after": self.fail_after_seconds,
        }

    def cleanup(self, kubectl_fn) -> None:
        kubectl_fn(
            "delete", "pod", f"chaos-{self.probe_type}-test",
            "-n", self.namespace, "--ignore-not-found",
        )


@dataclass
class ImagePullExperiment(ChaosExperiment):
    """
    Deploy a pod with a nonexistent image to trigger ImagePullBackOff.

    INTERVIEW CONCEPT: ImagePullBackOff happens when kubelet can't pull
    the container image. Causes: wrong tag, private registry without
    imagePullSecrets, registry unreachable, rate limiting (Docker Hub
    does 100 pulls/6h for anonymous). The backoff is exponential.

    Tests: POD-003 (ImagePullBackOff)
    """

    name: str = "image-pull-backoff"
    taxonomy_id: str = "POD-003"
    namespace: str = "default"

    def inject(self, kubectl_fn) -> dict:
        manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "chaos-image-pull-test",
                "namespace": self.namespace,
                "labels": {"chaos-experiment": "image-pull"},
            },
            "spec": {
                "restartPolicy": "Never",
                "containers": [
                    {
                        "name": "bad-image",
                        "image": "nonexistent-registry.invalid/no-such-image:v999",
                    }
                ],
            },
        }
        manifest_yaml = yaml.dump(manifest)
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(manifest_yaml)
            path = f.name
        try:
            kubectl_fn("apply", "-f", path)
        finally:
            Path(path).unlink(missing_ok=True)
        return {"pod": "chaos-image-pull-test"}

    def cleanup(self, kubectl_fn) -> None:
        kubectl_fn(
            "delete", "pod", "chaos-image-pull-test",
            "-n", self.namespace, "--ignore-not-found",
        )


# =============================================================================
# SCHEDULING EXPERIMENTS
# =============================================================================


@dataclass
class ResourceExhaustionExperiment(ChaosExperiment):
    """
    Request more resources than available to trigger FailedScheduling.

    INTERVIEW CONCEPT: The kube-scheduler scores each node based on
    available resources (allocatable - sum of existing requests). If
    no node can satisfy the pod's requests, it stays Pending with a
    FailedScheduling event. The cluster autoscaler (if enabled) watches
    for these events and provisions new nodes.

    Tests: SCHED-001 (Insufficient resources)
    """

    name: str = "resource-exhaustion"
    taxonomy_id: str = "SCHED-001"
    namespace: str = "default"
    cpu_request: str = "100"  # 100 CPUs — no node has this

    def inject(self, kubectl_fn) -> dict:
        manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "chaos-resource-exhaust",
                "namespace": self.namespace,
                "labels": {"chaos-experiment": "resource-exhaust"},
            },
            "spec": {
                "restartPolicy": "Never",
                "containers": [
                    {
                        "name": "greedy",
                        "image": "busybox:1.36",
                        "command": ["sleep", "3600"],
                        "resources": {
                            "requests": {"cpu": self.cpu_request},
                        },
                    }
                ],
            },
        }
        manifest_yaml = yaml.dump(manifest)
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(manifest_yaml)
            path = f.name
        try:
            kubectl_fn("apply", "-f", path)
        finally:
            Path(path).unlink(missing_ok=True)
        return {"pod": "chaos-resource-exhaust", "cpu_request": self.cpu_request}

    def cleanup(self, kubectl_fn) -> None:
        kubectl_fn(
            "delete", "pod", "chaos-resource-exhaust",
            "-n", self.namespace, "--ignore-not-found",
        )


@dataclass
class TaintExperiment(ChaosExperiment):
    """
    Taint a node and verify pods without tolerations are evicted.

    INTERVIEW CONCEPT: Taints and tolerations control which pods can
    schedule on which nodes.
        Taint effects:
            NoSchedule    — new pods rejected, existing pods stay
            PreferNoSchedule — soft version, scheduler tries to avoid
            NoExecute     — new pods rejected AND existing pods evicted

    Tests: SCHED-003 (Taint/toleration mismatch)
    """

    name: str = "node-taint"
    taxonomy_id: str = "SCHED-003"
    node_name: str = ""
    taint_key: str = "chaos-test"
    taint_value: str = "true"
    taint_effect: str = "NoSchedule"  # NoSchedule, PreferNoSchedule, NoExecute

    def inject(self, kubectl_fn) -> dict:
        if not self.node_name:
            output = kubectl_fn(
                "get", "nodes", "-o",
                "jsonpath={.items[0].metadata.name}",
            )
            if not output:
                raise RuntimeError("No nodes found")
            self.node_name = output.strip()

        kubectl_fn(
            "taint", "nodes", self.node_name,
            f"{self.taint_key}={self.taint_value}:{self.taint_effect}",
        )
        return {
            "node": self.node_name,
            "taint": f"{self.taint_key}={self.taint_value}:{self.taint_effect}",
        }

    def cleanup(self, kubectl_fn) -> None:
        if self.node_name:
            kubectl_fn(
                "taint", "nodes", self.node_name,
                f"{self.taint_key}:{self.taint_effect}-",
            )


# =============================================================================
# NETWORK EXPERIMENTS
# =============================================================================


@dataclass
class NetworkPolicyDenyExperiment(ChaosExperiment):
    """
    Apply a default-deny NetworkPolicy and verify traffic is blocked.

    INTERVIEW CONCEPT: NetworkPolicies are namespace-scoped firewall rules.
    By default, K8s allows ALL pod-to-pod traffic. Once you apply ANY
    NetworkPolicy that selects a pod, that pod is isolated — only traffic
    explicitly allowed by a policy gets through.

    Default deny = apply a policy that selects all pods ({}) but has
    no ingress/egress rules → all traffic blocked.

    Tests: NET-003 (NetworkPolicy blocking traffic)
    """

    name: str = "network-policy-deny"
    taxonomy_id: str = "NET-003"
    namespace: str = "default"

    def _policy_manifest(self) -> dict:
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": "chaos-deny-all",
                "namespace": self.namespace,
            },
            "spec": {
                "podSelector": {},  # Selects ALL pods in namespace
                "policyTypes": ["Ingress", "Egress"],
                # No ingress or egress rules = deny all
            },
        }

    def inject(self, kubectl_fn) -> dict:
        manifest = yaml.dump(self._policy_manifest())
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(manifest)
            path = f.name
        try:
            kubectl_fn("apply", "-f", path)
        finally:
            Path(path).unlink(missing_ok=True)
        return {"policy": "chaos-deny-all", "namespace": self.namespace}

    def cleanup(self, kubectl_fn) -> None:
        kubectl_fn(
            "delete", "networkpolicy", "chaos-deny-all",
            "-n", self.namespace, "--ignore-not-found",
        )


@dataclass
class DNSDisruptionExperiment(ChaosExperiment):
    """
    Scale CoreDNS to 0 replicas to simulate DNS failure.

    INTERVIEW CONCEPT: CoreDNS is the cluster DNS server. Every pod's
    /etc/resolv.conf points to the CoreDNS service IP. If CoreDNS is
    down, pods can't resolve service names (e.g., postgres.default.svc).
    External DNS may still work if the pod's ndots config allows it to
    bypass the search domains.

    Tests: NET-001 (DNS resolution failure)
    """

    name: str = "dns-disruption"
    taxonomy_id: str = "NET-001"
    _original_replicas: int = 2

    def inject(self, kubectl_fn) -> dict:
        # Save current replica count
        output = kubectl_fn(
            "get", "deployment", "coredns", "-n", "kube-system",
            "-o", "jsonpath={.spec.replicas}",
        )
        if output:
            self._original_replicas = int(output.strip())

        kubectl_fn(
            "scale", "deployment", "coredns",
            "-n", "kube-system", "--replicas=0",
        )
        return {"service": "coredns", "original_replicas": self._original_replicas}

    def cleanup(self, kubectl_fn) -> None:
        kubectl_fn(
            "scale", "deployment", "coredns",
            "-n", "kube-system",
            f"--replicas={self._original_replicas}",
        )


# =============================================================================
# CONTROL PLANE EXPERIMENTS
# =============================================================================


@dataclass
class NodeDrainExperiment(ChaosExperiment):
    """
    Drain a worker node and verify workloads reschedule.

    INTERVIEW CONCEPT: kubectl drain cordons the node (marks it
    unschedulable) then evicts all pods. Eviction respects PDBs
    (PodDisruptionBudgets). If a PDB blocks eviction, drain hangs.
    This simulates node maintenance or AZ failure.

    Tests: SCALE-003 (PDB blocking drain), POD-004 (Eviction)
    """

    name: str = "node-drain"
    taxonomy_id: str = "SCALE-003"
    node_name: str = ""
    ignore_daemonsets: bool = True
    timeout_seconds: int = 60

    def inject(self, kubectl_fn) -> dict:
        if not self.node_name:
            output = kubectl_fn(
                "get", "nodes",
                "-l", "!node-role.kubernetes.io/control-plane",
                "-o", "jsonpath={.items[0].metadata.name}",
            )
            if not output:
                raise RuntimeError("No worker nodes found")
            self.node_name = output.strip()

        cmd = [
            "drain", self.node_name,
            "--delete-emptydir-data",
            f"--timeout={self.timeout_seconds}s",
        ]
        if self.ignore_daemonsets:
            cmd.append("--ignore-daemonsets")

        kubectl_fn(*cmd)
        return {"node": self.node_name, "action": "drain"}

    def cleanup(self, kubectl_fn) -> None:
        if self.node_name:
            kubectl_fn("uncordon", self.node_name)


# =============================================================================
# EXPERIMENT REGISTRY
# =============================================================================

BUILTIN_EXPERIMENTS = {
    # Pod failures
    "pod-kill": PodKillExperiment,
    "oom-kill": OOMExperiment,
    "probe-failure": ProbeFailureExperiment,
    "image-pull-backoff": ImagePullExperiment,
    # Scheduling
    "resource-exhaustion": ResourceExhaustionExperiment,
    "node-taint": TaintExperiment,
    # Network
    "network-deny": NetworkPolicyDenyExperiment,
    "dns-disruption": DNSDisruptionExperiment,
    # Control plane / scaling
    "node-drain": NodeDrainExperiment,
}
