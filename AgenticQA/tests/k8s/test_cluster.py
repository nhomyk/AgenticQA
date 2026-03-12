"""
Tests for the kind cluster manager.

All kubectl/kind commands are mocked — no real cluster needed.
"""

import json
import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

from agenticqa.k8s.cluster import ClusterConfig, KindCluster, NodeConfig


@pytest.fixture
def config():
    return ClusterConfig(name="test-cluster", workers=2, k8s_version="v1.29.2")


@pytest.fixture
def cluster(config):
    return KindCluster(config)


class TestClusterConfig:
    """Test cluster configuration generation."""

    @pytest.mark.unit
    def test_default_config(self):
        config = ClusterConfig()
        assert config.name == "agenticqa-test"
        assert config.workers == 2

    @pytest.mark.unit
    def test_to_kind_config_structure(self, config):
        kind_cfg = config.to_kind_config()
        assert kind_cfg["kind"] == "Cluster"
        assert kind_cfg["apiVersion"] == "kind.x-k8s.io/v1alpha4"
        # 1 control-plane + 2 workers
        assert len(kind_cfg["nodes"]) == 3
        assert kind_cfg["nodes"][0]["role"] == "control-plane"
        assert kind_cfg["nodes"][1]["role"] == "worker"

    @pytest.mark.unit
    def test_networking_config(self, config):
        kind_cfg = config.to_kind_config()
        assert kind_cfg["networking"]["podSubnet"] == "10.244.0.0/16"
        assert kind_cfg["networking"]["serviceSubnet"] == "10.96.0.0/12"

    @pytest.mark.unit
    def test_extra_nodes_with_labels(self):
        config = ClusterConfig(
            extra_nodes=[
                NodeConfig(role="worker", labels={"gpu": "true"})
            ]
        )
        kind_cfg = config.to_kind_config()
        # 1 control-plane + 2 default workers + 1 extra
        assert len(kind_cfg["nodes"]) == 4


class TestKindCluster:
    """Test kind cluster lifecycle management."""

    @pytest.mark.unit
    @patch.object(KindCluster, "_run")
    def test_exists_returns_true(self, mock_run, cluster):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="test-cluster\nother-cluster\n"
        )
        assert cluster.exists() is True

    @pytest.mark.unit
    @patch.object(KindCluster, "_run")
    def test_exists_returns_false(self, mock_run, cluster):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="other-cluster\n"
        )
        assert cluster.exists() is False

    @pytest.mark.unit
    @patch.object(KindCluster, "_run")
    def test_exists_handles_failure(self, mock_run, cluster):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert cluster.exists() is False

    @pytest.mark.unit
    @patch.object(KindCluster, "_run")
    def test_delete(self, mock_run, cluster):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        cluster.delete()
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "delete" in args
        assert "cluster" in args

    @pytest.mark.unit
    @patch.object(KindCluster, "_run")
    def test_get_nodes_parses_json(self, mock_run, cluster):
        cluster._kubeconfig_path = "/tmp/test.kubeconfig"
        node_data = {
            "items": [
                {
                    "metadata": {
                        "name": "test-control-plane",
                        "labels": {
                            "node-role.kubernetes.io/control-plane": "",
                        },
                    },
                    "status": {
                        "conditions": [
                            {"type": "Ready", "status": "True"},
                        ]
                    },
                }
            ]
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(node_data)
        )
        nodes = cluster.get_nodes()
        assert len(nodes) == 1
        assert nodes[0]["name"] == "test-control-plane"
        assert nodes[0]["ready"] is True
        assert "control-plane" in nodes[0]["roles"]

    @pytest.mark.unit
    @patch.object(KindCluster, "_run")
    def test_get_nodes_empty_on_failure(self, mock_run, cluster):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert cluster.get_nodes() == []

    @pytest.mark.unit
    def test_name_property(self, cluster):
        assert cluster.name == "test-cluster"

    @pytest.mark.unit
    def test_kubeconfig_initially_none(self, cluster):
        assert cluster.kubeconfig is None
