"""
Tests for the chaos experiment engine and built-in experiments.

All kubectl calls are mocked — no real cluster needed.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from agenticqa.k8s.chaos.engine import (
    ChaosEngine,
    ChaosExperiment,
    ExperimentResult,
    ExperimentStatus,
    SteadyStateHypothesis,
)
from agenticqa.k8s.chaos.experiments import (
    BUILTIN_EXPERIMENTS,
    DNSDisruptionExperiment,
    ImagePullExperiment,
    NetworkPolicyDenyExperiment,
    NodeDrainExperiment,
    OOMExperiment,
    PodKillExperiment,
    ProbeFailureExperiment,
    ResourceExhaustionExperiment,
    TaintExperiment,
)


class MockExperiment(ChaosExperiment):
    """Test experiment that always succeeds."""

    name = "mock-test"
    taxonomy_id = "TEST-001"

    def __init__(self, should_fail=False):
        self._should_fail = should_fail

    def inject(self, kubectl_fn):
        return {"injected": True}

    def cleanup(self, kubectl_fn):
        pass

    def steady_state(self):
        return SteadyStateHypothesis(
            description="Test is healthy",
            check_command=["get", "pods"],
            expected_output="Running",
        )


class FailingExperiment(ChaosExperiment):
    """Test experiment whose injection raises an error."""

    name = "failing-test"
    taxonomy_id = "TEST-002"

    def inject(self, kubectl_fn):
        raise RuntimeError("Injection failed")

    def cleanup(self, kubectl_fn):
        pass


class NoHypothesisExperiment(ChaosExperiment):
    """Test experiment with no steady state hypothesis."""

    name = "no-hypothesis"
    taxonomy_id = "TEST-003"

    def inject(self, kubectl_fn):
        return {"injected": True}

    def cleanup(self, kubectl_fn):
        pass


class TestChaosEngine:
    """Test the chaos engine orchestration."""

    @pytest.mark.unit
    def test_dry_run(self):
        engine = ChaosEngine(dry_run=True)
        exp = MockExperiment()
        result = engine.run_experiment(exp)
        assert result.status == ExperimentStatus.SKIPPED
        assert result.details["reason"] == "dry_run"

    @pytest.mark.unit
    @patch.object(ChaosEngine, "_kubectl")
    @patch.object(ChaosEngine, "_check_steady_state")
    @patch("agenticqa.k8s.chaos.engine.time")
    def test_successful_experiment(self, mock_time, mock_steady, mock_kubectl):
        mock_time.monotonic.side_effect = [0.0, 0.1, 30.1, 30.2]
        mock_time.sleep = MagicMock()
        mock_steady.return_value = True

        engine = ChaosEngine(recovery_wait_seconds=1)
        exp = MockExperiment()
        result = engine.run_experiment(exp)

        assert result.status == ExperimentStatus.PASSED
        assert result.steady_state_before is True
        assert result.steady_state_after is True
        assert result.taxonomy_id == "TEST-001"

    @pytest.mark.unit
    @patch.object(ChaosEngine, "_kubectl")
    @patch.object(ChaosEngine, "_check_steady_state")
    @patch("agenticqa.k8s.chaos.engine.time")
    def test_failed_recovery(self, mock_time, mock_steady, mock_kubectl):
        mock_time.monotonic.side_effect = [0.0, 0.1, 30.1, 30.2]
        mock_time.sleep = MagicMock()
        # Steady state passes before but fails after
        mock_steady.side_effect = [True, False]

        engine = ChaosEngine(recovery_wait_seconds=1)
        result = engine.run_experiment(MockExperiment())

        assert result.status == ExperimentStatus.FAILED
        assert result.steady_state_before is True
        assert result.steady_state_after is False

    @pytest.mark.unit
    @patch.object(ChaosEngine, "_kubectl")
    @patch.object(ChaosEngine, "_check_steady_state")
    def test_skip_when_already_unhealthy(self, mock_steady, mock_kubectl):
        mock_steady.return_value = False

        engine = ChaosEngine()
        result = engine.run_experiment(MockExperiment())

        assert result.status == ExperimentStatus.SKIPPED
        assert "steady state failed" in result.details.get("reason", "")

    @pytest.mark.unit
    @patch.object(ChaosEngine, "_kubectl")
    def test_injection_error(self, mock_kubectl):
        engine = ChaosEngine()
        result = engine.run_experiment(FailingExperiment())

        assert result.status == ExperimentStatus.ERROR
        assert "Injection failed" in result.error

    @pytest.mark.unit
    @patch.object(ChaosEngine, "_kubectl")
    @patch("agenticqa.k8s.chaos.engine.time")
    def test_no_hypothesis(self, mock_time, mock_kubectl):
        mock_time.monotonic.side_effect = [0.0, 0.1, 0.2]
        mock_time.sleep = MagicMock()

        engine = ChaosEngine(recovery_wait_seconds=0)
        result = engine.run_experiment(NoHypothesisExperiment())

        assert result.status == ExperimentStatus.PASSED

    @pytest.mark.unit
    @patch.object(ChaosEngine, "_kubectl")
    @patch.object(ChaosEngine, "_check_steady_state", return_value=True)
    @patch("agenticqa.k8s.chaos.engine.time")
    def test_run_suite(self, mock_time, mock_steady, mock_kubectl):
        mock_time.monotonic.side_effect = [i * 0.1 for i in range(20)]
        mock_time.sleep = MagicMock()

        engine = ChaosEngine(recovery_wait_seconds=0)
        results = engine.run_suite([MockExperiment(), MockExperiment()])
        assert len(results) == 2

    @pytest.mark.unit
    @patch.object(ChaosEngine, "_kubectl")
    @patch.object(ChaosEngine, "_check_steady_state", return_value=True)
    @patch("agenticqa.k8s.chaos.engine.time")
    def test_summary(self, mock_time, mock_steady, mock_kubectl):
        mock_time.monotonic.side_effect = [i * 0.1 for i in range(20)]
        mock_time.sleep = MagicMock()

        engine = ChaosEngine(recovery_wait_seconds=0)
        engine.run_suite([MockExperiment(), MockExperiment()])
        summary = engine.summary()

        assert summary["total_experiments"] == 2
        assert summary["pass_rate"] == 100.0
        assert "TEST-001" in summary["taxonomy_ids_tested"]


class TestBuiltinExperiments:
    """Test built-in experiment definitions."""

    @pytest.mark.unit
    def test_registry_completeness(self):
        assert len(BUILTIN_EXPERIMENTS) >= 9
        assert "pod-kill" in BUILTIN_EXPERIMENTS
        assert "oom-kill" in BUILTIN_EXPERIMENTS
        assert "dns-disruption" in BUILTIN_EXPERIMENTS

    @pytest.mark.unit
    def test_pod_kill_inject(self):
        exp = PodKillExperiment(namespace="test", pod_name="web-123")
        mock_kubectl = MagicMock()
        result = exp.inject(mock_kubectl)
        assert result["killed_pod"] == "web-123"
        mock_kubectl.assert_called_once()

    @pytest.mark.unit
    def test_pod_kill_finds_pod_by_selector(self):
        exp = PodKillExperiment(namespace="test", label_selector="app=web")
        mock_kubectl = MagicMock(return_value="web-abc123")
        result = exp.inject(mock_kubectl)
        assert result["killed_pod"] == "web-abc123"

    @pytest.mark.unit
    def test_pod_kill_no_pod_found(self):
        exp = PodKillExperiment(namespace="test", label_selector="app=web")
        mock_kubectl = MagicMock(return_value=None)
        with pytest.raises(RuntimeError, match="No pods found"):
            exp.inject(mock_kubectl)

    @pytest.mark.unit
    def test_oom_experiment_manifest(self):
        exp = OOMExperiment(namespace="test", memory_limit="32Mi")
        manifest = exp._pod_manifest()
        assert manifest["metadata"]["name"] == "chaos-oom-test"
        container = manifest["spec"]["containers"][0]
        assert container["resources"]["limits"]["memory"] == "32Mi"

    @pytest.mark.unit
    def test_probe_failure_manifest(self):
        exp = ProbeFailureExperiment(
            namespace="test", probe_type="liveness", fail_after_seconds=10
        )
        manifest = exp._pod_manifest()
        assert "livenessProbe" in manifest["spec"]["containers"][0]

    @pytest.mark.unit
    def test_readiness_probe_failure(self):
        exp = ProbeFailureExperiment(
            namespace="test", probe_type="readiness"
        )
        manifest = exp._pod_manifest()
        assert "readinessProbe" in manifest["spec"]["containers"][0]
        assert manifest["metadata"]["name"] == "chaos-readiness-test"

    @pytest.mark.unit
    def test_image_pull_experiment(self):
        exp = ImagePullExperiment(namespace="test")
        mock_kubectl = MagicMock()
        result = exp.inject(mock_kubectl)
        assert result["pod"] == "chaos-image-pull-test"

    @pytest.mark.unit
    def test_resource_exhaustion(self):
        exp = ResourceExhaustionExperiment(namespace="test", cpu_request="200")
        mock_kubectl = MagicMock()
        result = exp.inject(mock_kubectl)
        assert result["cpu_request"] == "200"

    @pytest.mark.unit
    def test_taint_experiment(self):
        exp = TaintExperiment(node_name="node-1")
        mock_kubectl = MagicMock()
        result = exp.inject(mock_kubectl)
        assert result["node"] == "node-1"
        assert "NoSchedule" in result["taint"]

    @pytest.mark.unit
    def test_taint_cleanup(self):
        exp = TaintExperiment(node_name="node-1")
        mock_kubectl = MagicMock()
        exp.cleanup(mock_kubectl)
        mock_kubectl.assert_called_once()
        args = mock_kubectl.call_args[0]
        assert "taint" in args
        # Cleanup removes taint (trailing -)
        assert any("-" in str(a) for a in args)

    @pytest.mark.unit
    def test_network_policy_deny(self):
        exp = NetworkPolicyDenyExperiment(namespace="test")
        policy = exp._policy_manifest()
        assert policy["spec"]["podSelector"] == {}
        assert "Ingress" in policy["spec"]["policyTypes"]
        assert "Egress" in policy["spec"]["policyTypes"]

    @pytest.mark.unit
    def test_dns_disruption_inject(self):
        exp = DNSDisruptionExperiment()
        mock_kubectl = MagicMock(return_value="2")
        result = exp.inject(mock_kubectl)
        assert result["service"] == "coredns"
        assert result["original_replicas"] == 2

    @pytest.mark.unit
    def test_dns_disruption_cleanup_restores_replicas(self):
        exp = DNSDisruptionExperiment()
        exp._original_replicas = 3
        mock_kubectl = MagicMock()
        exp.cleanup(mock_kubectl)
        call_args = mock_kubectl.call_args[0]
        assert "--replicas=3" in call_args

    @pytest.mark.unit
    def test_node_drain_finds_worker(self):
        exp = NodeDrainExperiment()
        mock_kubectl = MagicMock(return_value="worker-1")
        result = exp.inject(mock_kubectl)
        assert result["node"] == "worker-1"

    @pytest.mark.unit
    def test_node_drain_no_workers(self):
        exp = NodeDrainExperiment()
        mock_kubectl = MagicMock(return_value=None)
        with pytest.raises(RuntimeError, match="No worker nodes"):
            exp.inject(mock_kubectl)
