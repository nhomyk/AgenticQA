"""Network testing: DNS resolution, NetworkPolicy enforcement, pod-to-pod connectivity."""

from agenticqa.k8s.network.dns_prober import DNSProber
from agenticqa.k8s.network.policy_tester import NetworkPolicyTester
from agenticqa.k8s.network.connectivity import ConnectivityMatrix

__all__ = ["DNSProber", "NetworkPolicyTester", "ConnectivityMatrix"]
