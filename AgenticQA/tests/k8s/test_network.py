"""
Tests for network testing modules (DNS, NetworkPolicy, connectivity).
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from agenticqa.k8s.network.connectivity import ConnectivityMatrix, ExpectedPath
from agenticqa.k8s.network.dns_prober import DNSProber, DNSResult
from agenticqa.k8s.network.policy_tester import (
    NetworkPolicyTester,
    PolicyGap,
)


class TestDNSProber:
    """Test DNS resolution probing."""

    @pytest.mark.unit
    @patch.object(DNSProber, "_kubectl")
    def test_probe_fqdn_success(self, mock_kubectl):
        mock_kubectl.return_value = (
            "Server:    10.96.0.10\n"
            "Address:   10.96.0.10:53\n\n"
            "Name:      kubernetes.default.svc.cluster.local\n"
            "Address:   10.96.0.1\n"
        )
        prober = DNSProber()
        result = prober.probe_fqdn("kubernetes.default.svc.cluster.local")
        assert result.resolved is True
        assert "10.96.0.1" in result.ip_addresses

    @pytest.mark.unit
    @patch.object(DNSProber, "_kubectl")
    def test_probe_fqdn_failure(self, mock_kubectl):
        mock_kubectl.return_value = None
        prober = DNSProber()
        result = prober.probe_fqdn("nonexistent.svc")
        assert result.resolved is False
        assert "kubectl failed" in result.error

    @pytest.mark.unit
    @patch.object(DNSProber, "_kubectl")
    def test_probe_service(self, mock_kubectl):
        mock_kubectl.return_value = (
            "Name:      myservice.default.svc.cluster.local\n"
            "Address:   10.100.50.1\n"
        )
        prober = DNSProber()
        result = prober.probe_service("myservice", "default")
        assert result.resolved is True
        assert result.query == "myservice.default.svc.cluster.local"

    @pytest.mark.unit
    @patch.object(DNSProber, "_kubectl")
    def test_probe_all_services(self, mock_kubectl):
        # First call: get service names
        mock_kubectl.side_effect = [
            "kubernetes myservice",
            "Name: kubernetes\nAddress: 10.96.0.1\n",
            "Name: myservice\nAddress: 10.100.1.1\n",
        ]
        prober = DNSProber()
        results = prober.probe_all_services("default")
        assert len(results) == 2

    @pytest.mark.unit
    @patch.object(DNSProber, "_kubectl")
    def test_check_coredns_health(self, mock_kubectl):
        deploy = {
            "spec": {"replicas": 2},
            "status": {
                "readyReplicas": 2,
                "availableReplicas": 2,
            },
        }
        mock_kubectl.return_value = json.dumps(deploy)
        prober = DNSProber()
        health = prober.check_coredns_health()
        assert health["healthy"] is True
        assert health["ready_replicas"] == 2

    @pytest.mark.unit
    @patch.object(DNSProber, "_kubectl")
    def test_check_coredns_unhealthy(self, mock_kubectl):
        mock_kubectl.return_value = None
        prober = DNSProber()
        health = prober.check_coredns_health()
        assert health["healthy"] is False


class TestNetworkPolicyTester:
    """Test NetworkPolicy validation."""

    @pytest.mark.unit
    @patch.object(NetworkPolicyTester, "_kubectl")
    def test_list_policies(self, mock_kubectl):
        policies = {
            "items": [
                {
                    "metadata": {"name": "allow-web"},
                    "spec": {
                        "podSelector": {"matchLabels": {"app": "web"}},
                        "policyTypes": ["Ingress"],
                        "ingress": [{"from": [{"podSelector": {}}]}],
                    },
                }
            ]
        }
        mock_kubectl.return_value = json.dumps(policies)
        tester = NetworkPolicyTester()
        result = tester.list_policies("default")
        assert len(result) == 1
        assert result[0]["name"] == "allow-web"
        assert result[0]["ingress_rules"] == 1

    @pytest.mark.unit
    @patch.object(NetworkPolicyTester, "_kubectl")
    def test_find_policy_gaps_uncovered_pod(self, mock_kubectl):
        policies = {
            "items": [
                {
                    "metadata": {"name": "allow-web"},
                    "spec": {
                        "podSelector": {"matchLabels": {"app": "web"}},
                        "policyTypes": ["Ingress"],
                    },
                }
            ]
        }
        pods = {
            "items": [
                {"metadata": {"name": "web-1", "labels": {"app": "web"}}},
                {"metadata": {"name": "db-1", "labels": {"app": "db"}}},
            ]
        }
        mock_kubectl.side_effect = [
            json.dumps(policies),
            json.dumps(pods),
        ]
        tester = NetworkPolicyTester()
        gaps = tester.find_policy_gaps("default")
        # db-1 is not covered by the web policy
        pod_gaps = [g for g in gaps if g.pod != "(all pods)"]
        assert len(pod_gaps) == 1
        assert pod_gaps[0].pod == "db-1"

    @pytest.mark.unit
    @patch.object(NetworkPolicyTester, "_kubectl")
    def test_find_policy_gaps_empty_selector_covers_all(self, mock_kubectl):
        policies = {
            "items": [
                {
                    "metadata": {"name": "deny-all"},
                    "spec": {
                        "podSelector": {},
                        "policyTypes": ["Ingress", "Egress"],
                    },
                }
            ]
        }
        pods = {
            "items": [
                {"metadata": {"name": "web-1", "labels": {"app": "web"}}},
                {"metadata": {"name": "db-1", "labels": {"app": "db"}}},
            ]
        }
        mock_kubectl.side_effect = [
            json.dumps(policies),
            json.dumps(pods),
        ]
        tester = NetworkPolicyTester()
        gaps = tester.find_policy_gaps("default")
        # No pod gaps — empty selector covers all
        pod_gaps = [g for g in gaps if g.pod != "(all pods)"]
        assert len(pod_gaps) == 0

    @pytest.mark.unit
    @patch.object(NetworkPolicyTester, "_kubectl")
    def test_missing_egress_policy_warning(self, mock_kubectl):
        policies = {
            "items": [
                {
                    "metadata": {"name": "ingress-only"},
                    "spec": {
                        "podSelector": {},
                        "policyTypes": ["Ingress"],
                    },
                }
            ]
        }
        pods = {"items": []}
        mock_kubectl.side_effect = [
            json.dumps(policies),
            json.dumps(pods),
        ]
        tester = NetworkPolicyTester()
        gaps = tester.find_policy_gaps("default")
        egress_gaps = [g for g in gaps if "egress" in g.issue.lower()]
        assert len(egress_gaps) == 1


class TestConnectivityMatrix:
    """Test connectivity matrix validation."""

    @pytest.mark.unit
    def test_define_expected_path(self):
        matrix = ConnectivityMatrix()
        matrix.define_expected("app=frontend", "app=backend", port=8080)
        assert len(matrix._expected_paths) == 1
        assert matrix._expected_paths[0].should_reach is True

    @pytest.mark.unit
    def test_define_blocked_path(self):
        matrix = ConnectivityMatrix()
        matrix.define_blocked("app=frontend", "app=database")
        assert len(matrix._expected_paths) == 1
        assert matrix._expected_paths[0].should_reach is False

    @pytest.mark.unit
    def test_from_service_map(self):
        matrix = ConnectivityMatrix()
        matrix.from_service_map({
            "frontend": ["backend", "cache"],
            "backend": ["database"],
        })
        assert len(matrix._expected_paths) == 3

    @pytest.mark.unit
    @patch.object(ConnectivityMatrix, "_find_pod", return_value="frontend-abc")
    @patch.object(ConnectivityMatrix, "_find_pod_with_ip", return_value=("backend-xyz", "10.0.0.5"))
    @patch.object(ConnectivityMatrix, "_test_connection", return_value=True)
    def test_validate_passing(self, mock_conn, mock_dest, mock_source):
        matrix = ConnectivityMatrix()
        matrix.define_expected("app=frontend", "app=backend")
        report = matrix.validate("default")
        assert report.total_paths == 1
        assert report.correct_paths == 1
        assert report.compliance_rate == 100.0

    @pytest.mark.unit
    @patch.object(ConnectivityMatrix, "_find_pod", return_value="frontend-abc")
    @patch.object(ConnectivityMatrix, "_find_pod_with_ip", return_value=("db-xyz", "10.0.0.10"))
    @patch.object(ConnectivityMatrix, "_test_connection", return_value=True)
    def test_validate_violation(self, mock_conn, mock_dest, mock_source):
        matrix = ConnectivityMatrix()
        # This path should be BLOCKED but it's reachable
        matrix.define_blocked("app=frontend", "app=database")
        report = matrix.validate("default")
        assert report.incorrect_paths == 1
        assert len(report.violations) == 1

    @pytest.mark.unit
    @patch.object(ConnectivityMatrix, "_find_pod", return_value=None)
    def test_validate_source_not_found(self, mock_source):
        matrix = ConnectivityMatrix()
        matrix.define_expected("app=ghost", "app=backend")
        report = matrix.validate("default")
        # No source pod → not reachable → correct only if should_reach=False
        assert report.incorrect_paths == 1
