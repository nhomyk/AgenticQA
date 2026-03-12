"""
NetworkPolicy Tester — Validate that NetworkPolicies enforce correctly.

INTERVIEW CONCEPT: NetworkPolicies are the most misunderstood K8s resource.
Key rules to know:

    1. By default, all pods can talk to all pods (no isolation)
    2. Once ANY NetworkPolicy selects a pod, that pod is isolated
    3. Policies are additive — they only ALLOW traffic, never DENY
    4. You need a CNI that supports NetworkPolicies (Calico, Cilium)
       kind's default CNI (kindnet) does NOT enforce them!
    5. Policies are namespace-scoped
    6. Egress policies control outbound traffic (often forgotten)

Common interview question: "How would you implement a zero-trust
network in K8s?" Answer: Default-deny in every namespace, then
explicit allow policies for each required communication path.

Usage:
    tester = NetworkPolicyTester(kubeconfig="/path/to/kubeconfig")
    matrix = tester.test_connectivity("default")
    gaps = tester.find_policy_gaps("default")
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ConnectivityResult:
    """Result of a connectivity test between two pods/services."""

    source: str
    destination: str
    port: int
    reachable: bool
    expected_reachable: bool = True
    latency_ms: float = 0.0
    error: str = ""

    @property
    def correct(self) -> bool:
        """Policy is enforced correctly if actual matches expected."""
        return self.reachable == self.expected_reachable


@dataclass
class PolicyGap:
    """A gap in NetworkPolicy coverage."""

    namespace: str
    pod: str
    issue: str
    severity: str  # "critical", "high", "medium"
    recommendation: str


class NetworkPolicyTester:
    """
    Tests NetworkPolicy enforcement and identifies gaps.

    Deploys temporary test pods, attempts connections between them,
    and verifies that NetworkPolicies are enforced correctly.
    """

    def __init__(
        self,
        kubeconfig: Optional[str] = None,
        context: Optional[str] = None,
    ) -> None:
        self._kubeconfig = kubeconfig
        self._context = context

    def list_policies(self, namespace: str) -> list[dict]:
        """List all NetworkPolicies in a namespace with parsed rules."""
        output = self._kubectl(
            "get", "networkpolicy", "-n", namespace, "-o", "json",
        )
        if not output:
            return []

        data = json.loads(output)
        policies = []
        for item in data.get("items", []):
            spec = item.get("spec", {})
            policies.append(
                {
                    "name": item["metadata"]["name"],
                    "pod_selector": spec.get("podSelector", {}),
                    "policy_types": spec.get("policyTypes", []),
                    "ingress_rules": len(spec.get("ingress", [])),
                    "egress_rules": len(spec.get("egress", [])),
                }
            )
        return policies

    def test_pod_to_pod(
        self,
        source_ns: str,
        source_pod: str,
        dest_ns: str,
        dest_ip: str,
        port: int = 80,
        timeout: int = 5,
    ) -> ConnectivityResult:
        """
        Test TCP connectivity from one pod to another.

        INTERVIEW CONCEPT: This is the fundamental connectivity test.
        In a zero-trust network, most of these should FAIL unless
        there's an explicit allow policy.
        """
        output = self._kubectl(
            "exec", source_pod, "-n", source_ns, "--",
            "sh", "-c",
            f"timeout {timeout} sh -c 'echo | nc -w {timeout} {dest_ip} {port}' 2>&1; echo $?",
        )

        reachable = output is not None and output.strip().endswith("0")

        return ConnectivityResult(
            source=f"{source_ns}/{source_pod}",
            destination=f"{dest_ns}/{dest_ip}:{port}",
            port=port,
            reachable=reachable,
        )

    def test_connectivity_matrix(
        self, namespace: str, port: int = 80
    ) -> list[ConnectivityResult]:
        """
        Test connectivity between all pods in a namespace.

        Builds an NxN matrix of connectivity results. This is how you
        verify that NetworkPolicies are isolating services correctly.
        """
        output = self._kubectl(
            "get", "pods", "-n", namespace,
            "-o", "json",
        )
        if not output:
            return []

        data = json.loads(output)
        pods = []
        for item in data.get("items", []):
            status = item.get("status", {})
            if status.get("phase") == "Running":
                pods.append(
                    {
                        "name": item["metadata"]["name"],
                        "ip": status.get("podIP", ""),
                    }
                )

        results = []
        for source in pods:
            for dest in pods:
                if source["name"] == dest["name"]:
                    continue
                if not dest["ip"]:
                    continue
                result = self.test_pod_to_pod(
                    namespace, source["name"],
                    namespace, dest["ip"],
                    port=port,
                )
                results.append(result)
        return results

    def find_policy_gaps(self, namespace: str) -> list[PolicyGap]:
        """
        Identify pods without NetworkPolicy coverage.

        INTERVIEW CONCEPT: Pods without any matching NetworkPolicy are
        "unprotected" — they accept ALL ingress and egress traffic.
        In a production environment, every pod should be covered by
        at least one NetworkPolicy (defense in depth).
        """
        policies = self.list_policies(namespace)
        pods_output = self._kubectl(
            "get", "pods", "-n", namespace, "-o", "json",
        )
        if not pods_output:
            return []

        pod_data = json.loads(pods_output)
        gaps = []

        for item in pod_data.get("items", []):
            pod_name = item["metadata"]["name"]
            pod_labels = item["metadata"].get("labels", {})

            # Check if any policy's podSelector matches this pod
            covered = False
            for policy in policies:
                selector = policy.get("pod_selector", {})
                match_labels = selector.get("matchLabels", {})
                if not match_labels:
                    # Empty selector matches all pods
                    covered = True
                    break
                if all(
                    pod_labels.get(k) == v for k, v in match_labels.items()
                ):
                    covered = True
                    break

            if not covered:
                gaps.append(
                    PolicyGap(
                        namespace=namespace,
                        pod=pod_name,
                        issue="No NetworkPolicy covers this pod",
                        severity="high",
                        recommendation=(
                            f"Add a NetworkPolicy with podSelector matching "
                            f"pod labels: {pod_labels}"
                        ),
                    )
                )

        # Check for missing egress policies
        has_egress_policy = any("Egress" in p.get("policy_types", []) for p in policies)
        if not has_egress_policy and policies:
            gaps.append(
                PolicyGap(
                    namespace=namespace,
                    pod="(all pods)",
                    issue="No egress NetworkPolicy in namespace",
                    severity="medium",
                    recommendation=(
                        "Add an egress NetworkPolicy to control outbound traffic. "
                        "Without egress policies, pods can reach any external service."
                    ),
                )
            )

        return gaps

    def apply_default_deny(self, namespace: str) -> dict:
        """
        Apply a default-deny-all NetworkPolicy to a namespace.

        INTERVIEW CONCEPT: This is step 1 of zero-trust networking.
        After applying this, ALL traffic to/from pods in the namespace
        is blocked. Then you add explicit allow policies for each
        required communication path.
        """
        policy = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": "default-deny-all",
                "namespace": namespace,
            },
            "spec": {
                "podSelector": {},
                "policyTypes": ["Ingress", "Egress"],
            },
        }

        import tempfile
        from pathlib import Path

        manifest = yaml.dump(policy)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(manifest)
            path = f.name
        try:
            self._kubectl("apply", "-f", path)
        finally:
            Path(path).unlink(missing_ok=True)

        return {"policy": "default-deny-all", "namespace": namespace}

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
                cmd, capture_output=True, text=True, check=True, timeout=30,
            )
            return result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning("kubectl failed: %s", e)
            return None
