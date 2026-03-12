"""
Kind Cluster Manager — Create/destroy ephemeral K8s clusters for testing.

INTERVIEW CONCEPT: kind (Kubernetes IN Docker) runs a full K8s cluster
inside Docker containers. Each "node" is a Docker container running
kubelet + containerd. This gives you a real K8s API without cloud costs.

Key facts for interviews:
    - kind uses kubeadm under the hood (same as real cluster bootstrapping)
    - Nodes are Docker containers, not VMs
    - Supports multi-node clusters (1 control-plane + N workers)
    - Supports custom K8s versions (--image=kindest/node:v1.29.0)
    - Port mappings via extraPortMappings in kind config
    - Can load local Docker images: kind load docker-image myapp:latest

Usage:
    cluster = KindCluster("test-chaos")
    cluster.create()               # spins up cluster
    cluster.kubeconfig              # path to kubeconfig
    cluster.load_image("app:v1")   # load local image into cluster
    cluster.delete()               # tear down
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class NodeConfig:
    """Configuration for a kind cluster node."""

    role: str = "worker"  # "control-plane" or "worker"
    labels: dict[str, str] = field(default_factory=dict)
    extra_port_mappings: list[dict] = field(default_factory=list)


@dataclass
class ClusterConfig:
    """
    Kind cluster configuration.

    INTERVIEW CONCEPT: In production K8s, you'd use kubeadm config,
    cloud provider settings, or a managed service (EKS/GKE/AKS).
    kind uses its own config format that maps to these concepts:

        nodes       → number and role of nodes (control-plane vs worker)
        networking  → pod/service CIDR, CNI
        extraMounts → mount host paths into nodes (like hostPath volumes)
    """

    name: str = "agenticqa-test"
    workers: int = 2
    k8s_version: str = "v1.29.2"
    pod_cidr: str = "10.244.0.0/16"
    service_cidr: str = "10.96.0.0/12"
    extra_nodes: list[NodeConfig] = field(default_factory=list)
    install_calico: bool = False
    install_metrics_server: bool = False

    def to_kind_config(self) -> dict:
        """Generate kind config YAML structure."""
        nodes = [{"role": "control-plane"}]
        for _ in range(self.workers):
            nodes.append({"role": "worker"})
        for n in self.extra_nodes:
            node = {"role": n.role}
            if n.labels:
                node["kubeadmConfigPatches"] = [
                    yaml.dump(
                        {
                            "kind": "JoinConfiguration",
                            "nodeRegistration": {
                                "kubeletExtraArgs": {
                                    "node-labels": ",".join(
                                        f"{k}={v}" for k, v in n.labels.items()
                                    )
                                }
                            },
                        }
                    )
                ]
            if n.extra_port_mappings:
                node["extraPortMappings"] = n.extra_port_mappings
            nodes.append(node)

        return {
            "kind": "Cluster",
            "apiVersion": "kind.x-k8s.io/v1alpha4",
            "nodes": nodes,
            "networking": {
                "podSubnet": self.pod_cidr,
                "serviceSubnet": self.service_cidr,
            },
        }


class KindCluster:
    """
    Manages a kind cluster lifecycle.

    Wraps the `kind` CLI to create, configure, and destroy ephemeral
    K8s clusters for testing.
    """

    def __init__(self, config: Optional[ClusterConfig] = None) -> None:
        self.config = config or ClusterConfig()
        self._kubeconfig_path: Optional[Path] = None

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def kubeconfig(self) -> Optional[Path]:
        """Path to the cluster's kubeconfig file."""
        return self._kubeconfig_path

    def exists(self) -> bool:
        """Check if the cluster already exists."""
        result = self._run(["kind", "get", "clusters"], check=False)
        if result.returncode != 0:
            return False
        return self.name in result.stdout.strip().split("\n")

    def create(self, wait: str = "120s") -> None:
        """
        Create the kind cluster.

        INTERVIEW CONCEPT: This is equivalent to running kubeadm init +
        kubeadm join for each worker node, but containerized. The --wait
        flag tells kind to wait for control plane components (API server,
        scheduler, controller manager, etcd) to be ready.

        Args:
            wait: Timeout for control plane readiness (e.g., "120s", "5m").
        """
        if self.exists():
            logger.info("Cluster %s already exists, reusing", self.name)
            self._export_kubeconfig()
            return

        # Write kind config to temp file
        config_dict = self.config.to_kind_config()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_dict, f)
            config_path = f.name

        try:
            cmd = [
                "kind",
                "create",
                "cluster",
                "--name",
                self.name,
                "--config",
                config_path,
                "--wait",
                wait,
            ]
            if self.config.k8s_version:
                cmd.extend(
                    ["--image", f"kindest/node:{self.config.k8s_version}"]
                )
            self._run(cmd)
        finally:
            Path(config_path).unlink(missing_ok=True)

        self._export_kubeconfig()

        # Post-create setup
        if self.config.install_metrics_server:
            self._install_metrics_server()
        if self.config.install_calico:
            self._install_calico()

        logger.info("Cluster %s created successfully", self.name)

    def delete(self) -> None:
        """Tear down the kind cluster."""
        self._run(["kind", "delete", "cluster", "--name", self.name])
        if self._kubeconfig_path and self._kubeconfig_path.exists():
            self._kubeconfig_path.unlink(missing_ok=True)
        logger.info("Cluster %s deleted", self.name)

    def load_image(self, image: str) -> None:
        """
        Load a local Docker image into the kind cluster nodes.

        INTERVIEW CONCEPT: kind nodes are Docker containers with their own
        containerd. They can't see your host's Docker images by default.
        `kind load` copies the image tarball into each node's containerd.
        This is analogous to pushing to a private registry in production.
        """
        self._run(
            ["kind", "load", "docker-image", image, "--name", self.name]
        )
        logger.info("Loaded image %s into cluster %s", image, self.name)

    def kubectl(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """
        Run kubectl against this cluster.

        Uses the cluster-specific kubeconfig to avoid affecting the user's
        default context.
        """
        cmd = ["kubectl"]
        if self._kubeconfig_path:
            cmd.extend(["--kubeconfig", str(self._kubeconfig_path)])
        cmd.extend(args)
        return self._run(cmd, check=check)

    def get_nodes(self) -> list[dict]:
        """Get all nodes in the cluster with their status."""
        result = self.kubectl("get", "nodes", "-o", "json", check=False)
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        nodes = []
        for item in data.get("items", []):
            conditions = {
                c["type"]: c["status"]
                for c in item.get("status", {}).get("conditions", [])
            }
            nodes.append(
                {
                    "name": item["metadata"]["name"],
                    "roles": [
                        l.split("/")[-1]
                        for l in item["metadata"].get("labels", {})
                        if l.startswith("node-role.kubernetes.io/")
                    ],
                    "ready": conditions.get("Ready") == "True",
                    "conditions": conditions,
                }
            )
        return nodes

    def wait_for_ready(self, timeout: str = "120s") -> bool:
        """Wait for all nodes to be Ready."""
        result = self.kubectl(
            "wait",
            "--for=condition=Ready",
            "nodes",
            "--all",
            f"--timeout={timeout}",
            check=False,
        )
        return result.returncode == 0

    def apply_manifest(self, manifest: str | dict) -> subprocess.CompletedProcess:
        """Apply a K8s manifest (YAML string or dict)."""
        if isinstance(manifest, dict):
            manifest = yaml.dump(manifest)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(manifest)
            path = f.name
        try:
            return self.kubectl("apply", "-f", path)
        finally:
            Path(path).unlink(missing_ok=True)

    # ── Private helpers ──────────────────────────────────────────────────

    def _export_kubeconfig(self) -> None:
        """Export kubeconfig to a temp file."""
        self._kubeconfig_path = Path(tempfile.mkdtemp()) / f"{self.name}.kubeconfig"
        self._run(
            [
                "kind",
                "export",
                "kubeconfig",
                "--name",
                self.name,
                "--kubeconfig",
                str(self._kubeconfig_path),
            ]
        )

    def _install_metrics_server(self) -> None:
        """
        Install metrics-server for HPA testing.

        INTERVIEW CONCEPT: metrics-server provides the Metrics API
        (metrics.k8s.io). HPA reads CPU/memory from it. Without
        metrics-server, HPA can't function. In kind, we need to add
        --kubelet-insecure-tls because kind uses self-signed certs.
        """
        self.kubectl(
            "apply",
            "-f",
            "https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml",
            check=False,
        )
        # Patch for kind's self-signed certs
        self.kubectl(
            "patch",
            "deployment",
            "metrics-server",
            "-n",
            "kube-system",
            "--type=json",
            "-p",
            json.dumps(
                [
                    {
                        "op": "add",
                        "path": "/spec/template/spec/containers/0/args/-",
                        "value": "--kubelet-insecure-tls",
                    }
                ]
            ),
            check=False,
        )

    def _install_calico(self) -> None:
        """
        Install Calico CNI for NetworkPolicy support.

        INTERVIEW CONCEPT: kind's default CNI (kindnet) doesn't enforce
        NetworkPolicies. Calico or Cilium is needed for NetworkPolicy
        testing. In production, you'd choose based on performance and
        feature requirements (Cilium has eBPF, Calico has BGP).
        """
        self.kubectl(
            "apply",
            "-f",
            "https://raw.githubusercontent.com/projectcalico/calico/v3.27.0/manifests/calico.yaml",
            check=False,
        )

    @staticmethod
    def _run(
        cmd: list[str], check: bool = True
    ) -> subprocess.CompletedProcess:
        """Run a shell command with logging."""
        logger.debug("Running: %s", " ".join(cmd))
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
            timeout=300,
        )
