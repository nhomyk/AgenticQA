"""
DNS Prober — Test DNS resolution from within the cluster.

INTERVIEW CONCEPT: K8s DNS is critical infrastructure. Every service
discovery call uses it. Understanding DNS resolution order:

    1. Pod queries its local DNS (configured in /etc/resolv.conf)
    2. resolv.conf points to CoreDNS ClusterIP (usually 10.96.0.10)
    3. CoreDNS checks its Corefile configuration:
       - cluster.local zone → served from K8s API (watches Services)
       - external domains → forwarded upstream (e.g., 8.8.8.8)
    4. Default search domains in pods:
       <namespace>.svc.cluster.local, svc.cluster.local, cluster.local
    5. ndots:5 (default) — if query has <5 dots, search domains are tried first
       This means "google.com" tries google.com.default.svc.cluster.local first!
       (This is why ndots:2 is a common tuning recommendation)

Usage:
    prober = DNSProber(kubeconfig="/path/to/kubeconfig")
    results = prober.probe_all_services("default")
    results = prober.probe_custom(["postgres.db.svc", "redis.cache.svc"])
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DNSResult:
    """Result of a single DNS resolution attempt."""

    query: str
    resolved: bool
    ip_addresses: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    error: str = ""


class DNSProber:
    """
    Tests DNS resolution from within a K8s cluster.

    Uses a temporary busybox pod to run nslookup/dig commands,
    simulating real pod-to-service DNS resolution.
    """

    def __init__(
        self,
        kubeconfig: Optional[str] = None,
        context: Optional[str] = None,
        probe_namespace: str = "default",
    ) -> None:
        self._kubeconfig = kubeconfig
        self._context = context
        self._probe_ns = probe_namespace

    def probe_service(
        self, service_name: str, namespace: str = "default"
    ) -> DNSResult:
        """
        Test DNS resolution for a specific K8s service.

        INTERVIEW CONCEPT: Services get DNS records in the format:
            <service>.<namespace>.svc.cluster.local
        For headless services (clusterIP: None), DNS returns pod IPs
        instead of the ClusterIP. This is used by StatefulSets.
        """
        fqdn = f"{service_name}.{namespace}.svc.cluster.local"
        return self.probe_fqdn(fqdn)

    def probe_fqdn(self, fqdn: str) -> DNSResult:
        """Test DNS resolution for an arbitrary FQDN."""
        start = time.monotonic()

        output = self._kubectl(
            "run", "dns-probe", "--rm", "-i", "--restart=Never",
            "--image=busybox:1.36", "-n", self._probe_ns,
            "--", "nslookup", fqdn,
        )

        latency = (time.monotonic() - start) * 1000  # ms

        if output is None:
            return DNSResult(query=fqdn, resolved=False, error="kubectl failed")

        # Parse nslookup output
        # nslookup format:
        #   Server:    10.96.0.10       ← DNS server
        #   Address:   10.96.0.10:53    ← DNS server address (has port)
        #   Name:      ...
        #   Address:   10.96.0.1        ← resolved address (no port)
        ips = []
        seen_name = False
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("Name:"):
                seen_name = True
            if line.startswith("Address") and ":" in line:
                addr = line.split(":", 1)[1].strip()
                # Skip DNS server address (contains port like :53)
                if ":53" in addr:
                    continue
                # After the Name: line, addresses are resolved results
                if seen_name and addr:
                    ips.append(addr)

        resolved = len(ips) > 0
        return DNSResult(
            query=fqdn,
            resolved=resolved,
            ip_addresses=ips,
            latency_ms=latency,
            error="" if resolved else "no addresses resolved",
        )

    def probe_all_services(self, namespace: str) -> list[DNSResult]:
        """
        Test DNS resolution for every Service in a namespace.

        This is the "are all services reachable via DNS?" check.
        """
        output = self._kubectl(
            "get", "services", "-n", namespace,
            "-o", "jsonpath={.items[*].metadata.name}",
        )
        if not output:
            return []

        services = output.strip().split()
        results = []
        for svc in services:
            results.append(self.probe_service(svc, namespace))
        return results

    def probe_external(self, domains: Optional[list[str]] = None) -> list[DNSResult]:
        """
        Test external DNS resolution from within the cluster.

        INTERVIEW CONCEPT: External DNS resolution goes through CoreDNS's
        forward plugin, which forwards to upstream resolvers (typically
        the node's /etc/resolv.conf or a configured upstream like 8.8.8.8).
        If external DNS fails but internal works, the forward plugin is
        misconfigured.
        """
        if domains is None:
            domains = ["google.com", "github.com", "registry-1.docker.io"]

        return [self.probe_fqdn(d) for d in domains]

    def check_coredns_health(self) -> dict:
        """
        Check CoreDNS deployment health.

        Returns deployment status, replica count, and pod health.
        """
        output = self._kubectl(
            "get", "deployment", "coredns", "-n", "kube-system", "-o", "json",
        )
        if not output:
            return {"healthy": False, "error": "CoreDNS deployment not found"}

        data = json.loads(output)
        spec_replicas = data.get("spec", {}).get("replicas", 0)
        status = data.get("status", {})
        ready = status.get("readyReplicas", 0)
        available = status.get("availableReplicas", 0)

        return {
            "healthy": ready >= 1 and ready == spec_replicas,
            "desired_replicas": spec_replicas,
            "ready_replicas": ready,
            "available_replicas": available,
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
                cmd, capture_output=True, text=True, check=True, timeout=30,
            )
            return result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning("kubectl failed: %s", e)
            return None
