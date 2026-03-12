"""
Connectivity Matrix — Map and validate all communication paths in a cluster.

INTERVIEW CONCEPT: In a microservices architecture, understanding which
services talk to which services is critical for:
    1. SecurityNetworkPolicy design (which paths to allow)
    2. Failure blast radius (if service A goes down, what's affected?)
    3. Performance testing (which paths are latency-sensitive?)

The connectivity matrix is a map of all expected and actual communication
paths. Discrepancies indicate either missing NetworkPolicies or
misconfigured services.

Usage:
    matrix = ConnectivityMatrix(kubeconfig="/path/to/kubeconfig")
    matrix.define_expected("frontend", "backend", port=8080)
    matrix.define_expected("backend", "postgres", port=5432)
    matrix.define_blocked("frontend", "postgres")  # should NOT be reachable
    report = matrix.validate("my-namespace")
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ExpectedPath:
    """An expected (or blocked) communication path."""

    source_label: str  # Label selector value (e.g., "app=frontend")
    dest_label: str  # Label selector value
    port: int = 80
    should_reach: bool = True  # True = allowed, False = blocked
    protocol: str = "TCP"


@dataclass
class PathValidation:
    """Result of validating a single expected path."""

    path: ExpectedPath
    actual_reachable: bool
    correct: bool
    source_pod: str = ""
    dest_pod: str = ""
    dest_ip: str = ""
    error: str = ""


@dataclass
class MatrixReport:
    """Full connectivity matrix validation report."""

    namespace: str
    total_paths: int
    correct_paths: int
    incorrect_paths: int
    validations: list[PathValidation] = field(default_factory=list)

    @property
    def compliance_rate(self) -> float:
        if self.total_paths == 0:
            return 100.0
        return (self.correct_paths / self.total_paths) * 100

    @property
    def violations(self) -> list[PathValidation]:
        return [v for v in self.validations if not v.correct]


class ConnectivityMatrix:
    """
    Defines and validates expected communication paths in a cluster.

    You define which services should communicate (and which should NOT),
    then validate against the real cluster state.
    """

    def __init__(
        self,
        kubeconfig: Optional[str] = None,
        context: Optional[str] = None,
    ) -> None:
        self._kubeconfig = kubeconfig
        self._context = context
        self._expected_paths: list[ExpectedPath] = []

    def define_expected(
        self,
        source_label: str,
        dest_label: str,
        port: int = 80,
        protocol: str = "TCP",
    ) -> None:
        """Define a path that SHOULD be reachable."""
        self._expected_paths.append(
            ExpectedPath(
                source_label=source_label,
                dest_label=dest_label,
                port=port,
                should_reach=True,
                protocol=protocol,
            )
        )

    def define_blocked(
        self, source_label: str, dest_label: str, port: int = 80
    ) -> None:
        """Define a path that should be BLOCKED."""
        self._expected_paths.append(
            ExpectedPath(
                source_label=source_label,
                dest_label=dest_label,
                port=port,
                should_reach=False,
            )
        )

    def validate(self, namespace: str) -> MatrixReport:
        """
        Validate all defined paths against the real cluster.

        For each expected path:
            1. Find a pod matching the source selector
            2. Find a pod matching the dest selector (get its IP)
            3. Attempt TCP connection from source to dest:port
            4. Compare actual result with expected (should_reach)
        """
        validations = []

        for path in self._expected_paths:
            validation = self._validate_path(path, namespace)
            validations.append(validation)

        correct = sum(1 for v in validations if v.correct)
        return MatrixReport(
            namespace=namespace,
            total_paths=len(validations),
            correct_paths=correct,
            incorrect_paths=len(validations) - correct,
            validations=validations,
        )

    def from_service_map(self, service_map: dict[str, list[str]]) -> None:
        """
        Load expected paths from a service dependency map.

        Args:
            service_map: Dict of service → list of dependencies.
                Example: {"frontend": ["backend"], "backend": ["postgres", "redis"]}
        """
        for source, destinations in service_map.items():
            for dest in destinations:
                self.define_expected(f"app={source}", f"app={dest}")

    # ── Private helpers ──────────────────────────────────────────────────

    def _validate_path(
        self, path: ExpectedPath, namespace: str
    ) -> PathValidation:
        """Validate a single expected path."""
        # Find source pod
        source_pod = self._find_pod(namespace, path.source_label)
        if not source_pod:
            return PathValidation(
                path=path,
                actual_reachable=False,
                correct=not path.should_reach,
                error=f"No pod found matching {path.source_label}",
            )

        # Find dest pod and its IP
        dest_pod, dest_ip = self._find_pod_with_ip(namespace, path.dest_label)
        if not dest_pod or not dest_ip:
            return PathValidation(
                path=path,
                actual_reachable=False,
                correct=not path.should_reach,
                source_pod=source_pod,
                error=f"No pod found matching {path.dest_label}",
            )

        # Test connectivity
        reachable = self._test_connection(
            namespace, source_pod, dest_ip, path.port
        )

        return PathValidation(
            path=path,
            actual_reachable=reachable,
            correct=reachable == path.should_reach,
            source_pod=source_pod,
            dest_pod=dest_pod,
            dest_ip=dest_ip,
        )

    def _find_pod(self, namespace: str, label_selector: str) -> Optional[str]:
        """Find the first Running pod matching a label selector."""
        output = self._kubectl(
            "get", "pods", "-n", namespace,
            "-l", label_selector,
            "--field-selector=status.phase=Running",
            "-o", "jsonpath={.items[0].metadata.name}",
        )
        return output.strip() if output else None

    def _find_pod_with_ip(
        self, namespace: str, label_selector: str
    ) -> tuple[Optional[str], Optional[str]]:
        """Find pod name and IP for a label selector."""
        output = self._kubectl(
            "get", "pods", "-n", namespace,
            "-l", label_selector,
            "--field-selector=status.phase=Running",
            "-o", "json",
        )
        if not output:
            return None, None

        data = json.loads(output)
        items = data.get("items", [])
        if not items:
            return None, None

        pod = items[0]
        return (
            pod["metadata"]["name"],
            pod.get("status", {}).get("podIP"),
        )

    def _test_connection(
        self, namespace: str, source_pod: str, dest_ip: str, port: int
    ) -> bool:
        """Test TCP connectivity from source pod to dest IP:port."""
        output = self._kubectl(
            "exec", source_pod, "-n", namespace, "--",
            "sh", "-c",
            f"timeout 3 sh -c 'echo | nc -w 3 {dest_ip} {port}' 2>&1; echo $?",
        )
        return output is not None and output.strip().endswith("0")

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
