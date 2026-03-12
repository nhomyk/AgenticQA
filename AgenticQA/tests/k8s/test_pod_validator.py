"""
Tests for the pod health validator.

All kubectl commands are mocked.
"""

import json
from unittest.mock import patch

import pytest

from agenticqa.k8s.pod_validator import (
    ContainerStatus,
    NamespaceReport,
    PodHealth,
    PodValidator,
)


def _mock_pods_json(pods_data):
    """Helper to create kubectl get pods JSON output."""
    return json.dumps({"items": pods_data})


def _healthy_pod(name="web-abc123", namespace="default"):
    return {
        "metadata": {"name": name},
        "spec": {
            "nodeName": "node-1",
            "containers": [
                {
                    "name": "web",
                    "livenessProbe": {"httpGet": {"path": "/healthz"}},
                    "readinessProbe": {"httpGet": {"path": "/ready"}},
                    "resources": {
                        "requests": {"cpu": "100m", "memory": "128Mi"},
                        "limits": {"cpu": "200m", "memory": "256Mi"},
                    },
                }
            ],
        },
        "status": {
            "phase": "Running",
            "qosClass": "Guaranteed",
            "conditions": [{"type": "Ready", "status": "True"}],
            "containerStatuses": [
                {
                    "name": "web",
                    "ready": True,
                    "state": {"running": {"startedAt": "2026-01-01T00:00:00Z"}},
                    "restartCount": 0,
                    "image": "nginx:1.25",
                }
            ],
        },
    }


def _oom_pod(name="worker-xyz789"):
    return {
        "metadata": {"name": name},
        "spec": {"nodeName": "node-2", "containers": [{"name": "worker"}]},
        "status": {
            "phase": "Running",
            "qosClass": "Burstable",
            "conditions": [{"type": "Ready", "status": "False"}],
            "containerStatuses": [
                {
                    "name": "worker",
                    "ready": False,
                    "state": {
                        "terminated": {
                            "reason": "OOMKilled",
                            "exitCode": 137,
                        }
                    },
                    "restartCount": 12,
                    "image": "worker:v1",
                }
            ],
        },
    }


def _pending_pod(name="pending-pod"):
    return {
        "metadata": {"name": name},
        "spec": {"containers": [{"name": "app"}]},
        "status": {
            "phase": "Pending",
            "qosClass": "BestEffort",
            "conditions": [],
            "containerStatuses": [],
        },
    }


class TestPodHealth:
    """Test PodHealth dataclass behavior."""

    @pytest.mark.unit
    def test_healthy_pod(self):
        pod = PodHealth(
            name="web",
            namespace="default",
            phase="Running",
            qos_class="Guaranteed",
            containers=[
                ContainerStatus(name="web", ready=True, state="running")
            ],
        )
        assert pod.healthy is True

    @pytest.mark.unit
    def test_unhealthy_pod_not_running(self):
        pod = PodHealth(
            name="broken",
            namespace="default",
            phase="Pending",
            qos_class="BestEffort",
        )
        assert pod.healthy is False

    @pytest.mark.unit
    def test_unhealthy_pod_container_not_ready(self):
        pod = PodHealth(
            name="broken",
            namespace="default",
            phase="Running",
            qos_class="Burstable",
            containers=[
                ContainerStatus(name="app", ready=False, state="waiting", reason="CrashLoopBackOff")
            ],
        )
        assert pod.healthy is False

    @pytest.mark.unit
    def test_succeeded_pod_is_healthy(self):
        pod = PodHealth(
            name="job-done",
            namespace="default",
            phase="Succeeded",
            qos_class="Guaranteed",
        )
        assert pod.healthy is True

    @pytest.mark.unit
    def test_taxonomy_ids_oom(self):
        pod = PodHealth(
            name="oom",
            namespace="default",
            phase="Running",
            qos_class="Burstable",
            containers=[
                ContainerStatus(name="app", ready=False, state="terminated", reason="OOMKilled")
            ],
        )
        assert "POD-001" in pod.taxonomy_ids

    @pytest.mark.unit
    def test_taxonomy_ids_crashloop(self):
        pod = PodHealth(
            name="crash",
            namespace="default",
            phase="Running",
            qos_class="BestEffort",
            containers=[
                ContainerStatus(name="app", ready=False, state="waiting", reason="CrashLoopBackOff")
            ],
        )
        assert "POD-002" in pod.taxonomy_ids

    @pytest.mark.unit
    def test_taxonomy_ids_image_pull(self):
        pod = PodHealth(
            name="bad-image",
            namespace="default",
            phase="Pending",
            qos_class="BestEffort",
            containers=[
                ContainerStatus(name="app", ready=False, state="waiting", reason="ImagePullBackOff")
            ],
        )
        assert "POD-003" in pod.taxonomy_ids


class TestNamespaceReport:
    """Test NamespaceReport aggregation."""

    @pytest.mark.unit
    def test_health_percentage_all_healthy(self):
        report = NamespaceReport(
            namespace="default", total_pods=3, healthy_pods=3, unhealthy_pods=0
        )
        assert report.health_percentage == 100.0

    @pytest.mark.unit
    def test_health_percentage_some_unhealthy(self):
        report = NamespaceReport(
            namespace="default", total_pods=4, healthy_pods=3, unhealthy_pods=1
        )
        assert report.health_percentage == 75.0

    @pytest.mark.unit
    def test_health_percentage_empty(self):
        report = NamespaceReport(namespace="default")
        assert report.health_percentage == 100.0


class TestPodValidator:
    """Test PodValidator with mocked kubectl."""

    @pytest.mark.unit
    @patch.object(PodValidator, "_kubectl")
    def test_validate_namespace_healthy(self, mock_kubectl):
        mock_kubectl.return_value = _mock_pods_json([_healthy_pod()])
        validator = PodValidator()
        report = validator.validate_namespace("default")
        assert report.total_pods == 1
        assert report.healthy_pods == 1
        assert report.health_percentage == 100.0

    @pytest.mark.unit
    @patch.object(PodValidator, "_kubectl")
    def test_validate_namespace_mixed(self, mock_kubectl):
        mock_kubectl.return_value = _mock_pods_json([
            _healthy_pod(), _oom_pod(), _pending_pod()
        ])
        validator = PodValidator()
        report = validator.validate_namespace("default")
        assert report.total_pods == 3
        assert report.healthy_pods == 1
        assert report.unhealthy_pods == 2

    @pytest.mark.unit
    @patch.object(PodValidator, "_kubectl")
    def test_validate_namespace_kubectl_failure(self, mock_kubectl):
        mock_kubectl.return_value = None
        validator = PodValidator()
        report = validator.validate_namespace("default")
        assert report.total_pods == 0

    @pytest.mark.unit
    @patch.object(PodValidator, "_kubectl")
    def test_find_issues(self, mock_kubectl):
        mock_kubectl.return_value = _mock_pods_json([_oom_pod()])
        validator = PodValidator()
        issues = validator.find_issues(namespace="default")
        assert len(issues) == 1
        assert "POD-001" in issues[0]["taxonomy_ids"]

    @pytest.mark.unit
    @patch.object(PodValidator, "_kubectl")
    def test_check_probes_missing(self, mock_kubectl):
        pod_no_probes = {
            "metadata": {"name": "no-probes"},
            "spec": {
                "containers": [
                    {"name": "app"}  # No probes defined
                ]
            },
            "status": {"phase": "Running"},
        }
        mock_kubectl.return_value = json.dumps({"items": [pod_no_probes]})
        validator = PodValidator()
        findings = validator.check_probes("default")
        assert len(findings) == 1
        assert "liveness" in findings[0]["missing_probes"]
        assert "readiness" in findings[0]["missing_probes"]
        assert findings[0]["severity"] == "critical"

    @pytest.mark.unit
    @patch.object(PodValidator, "_kubectl")
    def test_check_probes_all_present(self, mock_kubectl):
        mock_kubectl.return_value = _mock_pods_json([_healthy_pod()])
        validator = PodValidator()
        findings = validator.check_probes("default")
        # startup probe is missing, but that's expected for many pods
        assert all("liveness" not in f["missing_probes"] for f in findings)

    @pytest.mark.unit
    @patch.object(PodValidator, "_kubectl")
    def test_check_resource_config(self, mock_kubectl):
        pod_no_resources = {
            "metadata": {"name": "no-resources"},
            "spec": {
                "containers": [
                    {"name": "app", "resources": {}}
                ]
            },
            "status": {"phase": "Running", "qosClass": "BestEffort"},
        }
        mock_kubectl.return_value = json.dumps({"items": [pod_no_resources]})
        validator = PodValidator()
        findings = validator.check_resource_config("default")
        assert len(findings) == 1
        assert "no resource requests" in findings[0]["issues"]
        assert findings[0]["qos_class"] == "BestEffort"
