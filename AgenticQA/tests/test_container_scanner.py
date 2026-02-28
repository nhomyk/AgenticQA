"""Unit tests for ContainerScanner — @pytest.mark.unit"""
import pytest
from pathlib import Path

from agenticqa.security.container_scanner import (
    ContainerFinding,
    ContainerScanResult,
    ContainerScanner,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_scanner() -> ContainerScanner:
    return ContainerScanner()


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Dockerfile tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDockerfileScanning:

    def test_user_root_detected(self, tmp_path):
        write(tmp_path / "Dockerfile", "FROM ubuntu:20.04\nUSER root\nRUN apt-get update\n")
        result = make_scanner().scan(str(tmp_path))
        ids = [f.check_id for f in result.findings]
        assert "DOCK-001" in ids
        root_findings = [f for f in result.findings if f.check_id == "DOCK-001" and "root" in f.evidence.lower()]
        assert len(root_findings) > 0

    def test_no_user_instruction_triggers_dock001(self, tmp_path):
        write(tmp_path / "Dockerfile", "FROM ubuntu:20.04\nRUN apt-get update\n")
        result = make_scanner().scan(str(tmp_path))
        ids = [f.check_id for f in result.findings]
        assert "DOCK-001" in ids

    def test_add_http_url_detected(self, tmp_path):
        write(tmp_path / "Dockerfile", "FROM ubuntu:20.04\nUSER nonroot\nADD http://example.com/file.tar.gz /app/\n")
        result = make_scanner().scan(str(tmp_path))
        ids = [f.check_id for f in result.findings]
        assert "DOCK-002" in ids

    def test_env_secret_detected(self, tmp_path):
        write(tmp_path / "Dockerfile", "FROM ubuntu:20.04\nUSER nonroot\nENV DB_PASSWORD=secret123\n")
        result = make_scanner().scan(str(tmp_path))
        ids = [f.check_id for f in result.findings]
        assert "DOCK-004" in ids

    def test_latest_tag_detected(self, tmp_path):
        write(tmp_path / "Dockerfile", "FROM ubuntu:latest\nUSER nonroot\n")
        result = make_scanner().scan(str(tmp_path))
        ids = [f.check_id for f in result.findings]
        assert "DOCK-006" in ids

    def test_copy_dot_dot_detected(self, tmp_path):
        write(tmp_path / "Dockerfile", "FROM ubuntu:20.04\nUSER nonroot\nCOPY . .\n")
        result = make_scanner().scan(str(tmp_path))
        ids = [f.check_id for f in result.findings]
        assert "DOCK-007" in ids

    def test_clean_dockerfile_no_critical_findings(self, tmp_path):
        content = (
            "FROM ubuntu:20.04\n"
            "USER nonroot\n"
            "HEALTHCHECK CMD curl -f http://localhost/ || exit 1\n"
            "COPY requirements.txt /app/\n"
            "RUN pip install -r /app/requirements.txt\n"
        )
        write(tmp_path / "Dockerfile", content)
        result = make_scanner().scan(str(tmp_path))
        critical = [f for f in result.findings if f.severity == "critical"]
        assert len(critical) == 0


# ---------------------------------------------------------------------------
# Docker Compose tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestComposeScanning:

    def test_compose_privileged_detected(self, tmp_path):
        content = "services:\n  app:\n    image: nginx\n    privileged: true\n"
        write(tmp_path / "docker-compose.yml", content)
        result = make_scanner().scan(str(tmp_path))
        ids = [f.check_id for f in result.findings]
        assert "COMP-001" in ids

    def test_compose_host_network_detected(self, tmp_path):
        content = "services:\n  app:\n    image: nginx\n    network_mode: host\n"
        write(tmp_path / "docker-compose.yml", content)
        result = make_scanner().scan(str(tmp_path))
        ids = [f.check_id for f in result.findings]
        assert "COMP-002" in ids

    def test_docker_sock_mount_detected(self, tmp_path):
        content = "services:\n  app:\n    image: nginx\n    volumes:\n      - /var/run/docker.sock:/var/run/docker.sock\n"
        write(tmp_path / "docker-compose.yml", content)
        result = make_scanner().scan(str(tmp_path))
        ids = [f.check_id for f in result.findings]
        assert "COMP-003" in ids

    def test_compose_env_secret_detected(self, tmp_path):
        content = "services:\n  app:\n    image: nginx\n    environment:\n      - DB_PASSWORD=secret\n"
        write(tmp_path / "docker-compose.yml", content)
        result = make_scanner().scan(str(tmp_path))
        ids = [f.check_id for f in result.findings]
        assert "COMP-004" in ids

    def test_compose_all_interfaces_detected(self, tmp_path):
        content = 'services:\n  app:\n    image: nginx\n    ports:\n      - "0.0.0.0:80:80"\n'
        write(tmp_path / "docker-compose.yml", content)
        result = make_scanner().scan(str(tmp_path))
        ids = [f.check_id for f in result.findings]
        assert "COMP-005" in ids


# ---------------------------------------------------------------------------
# K8s YAML tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestK8sScanning:

    def test_k8s_privileged_detected(self, tmp_path):
        content = (
            "apiVersion: v1\nkind: Pod\nspec:\n  containers:\n  - name: app\n"
            "    securityContext:\n      privileged: true\n"
        )
        write(tmp_path / "pod.yaml", content)
        result = make_scanner().scan(str(tmp_path))
        ids = [f.check_id for f in result.findings]
        assert "K8S-001" in ids

    def test_k8s_host_network_detected(self, tmp_path):
        content = "apiVersion: v1\nkind: Pod\nspec:\n  hostNetwork: true\n  containers:\n  - name: app\n"
        write(tmp_path / "pod.yaml", content)
        result = make_scanner().scan(str(tmp_path))
        ids = [f.check_id for f in result.findings]
        assert "K8S-002" in ids

    def test_k8s_allow_privilege_escalation_detected(self, tmp_path):
        content = (
            "apiVersion: v1\nkind: Pod\nspec:\n  containers:\n  - name: app\n"
            "    securityContext:\n      allowPrivilegeEscalation: true\n"
        )
        write(tmp_path / "pod.yaml", content)
        result = make_scanner().scan(str(tmp_path))
        ids = [f.check_id for f in result.findings]
        assert "K8S-003" in ids

    def test_k8s_host_path_detected(self, tmp_path):
        content = (
            "apiVersion: v1\nkind: Pod\nspec:\n  volumes:\n  - name: data\n"
            "    hostPath:\n      path: /data\n  containers:\n  - name: app\n"
        )
        write(tmp_path / "pod.yaml", content)
        result = make_scanner().scan(str(tmp_path))
        ids = [f.check_id for f in result.findings]
        assert "K8S-006" in ids


# ---------------------------------------------------------------------------
# General result tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestContainerScanResult:

    def test_to_dict_fields(self, tmp_path):
        write(tmp_path / "Dockerfile", "FROM ubuntu:20.04\nUSER nonroot\nHEALTHCHECK CMD true\n")
        result = make_scanner().scan(str(tmp_path))
        d = result.to_dict()
        assert "repo_path" in d
        assert "findings" in d
        assert "files_scanned" in d
        assert "dockerfiles_found" in d
        assert "compose_files_found" in d
        assert "k8s_files_found" in d
        assert "risk_score" in d
        assert "critical_findings" in d

    def test_finding_to_dict_fields(self):
        f = ContainerFinding(
            check_id="DOCK-001",
            severity="critical",
            source_file="Dockerfile",
            line_number=3,
            evidence="USER root",
            description="Runs as root",
            remediation="Use USER nonroot",
        )
        d = f.to_dict()
        assert "check_id" in d
        assert "severity" in d
        assert "source_file" in d
        assert "line_number" in d
        assert "evidence" in d
        assert "description" in d
        assert "remediation" in d

    def test_files_scanned_count(self, tmp_path):
        write(tmp_path / "Dockerfile", "FROM ubuntu:20.04\nUSER nonroot\nHEALTHCHECK CMD true\n")
        result = make_scanner().scan(str(tmp_path))
        assert result.files_scanned >= 1
        assert result.dockerfiles_found >= 1

    def test_risk_score_zero_on_clean(self, tmp_path):
        # A truly clean Dockerfile: non-root user + healthcheck + pinned tag
        content = (
            "FROM ubuntu:20.04\n"
            "USER nonroot\n"
            "HEALTHCHECK CMD curl -f http://localhost/ || exit 1\n"
        )
        write(tmp_path / "Dockerfile", content)
        result = make_scanner().scan(str(tmp_path))
        assert result.risk_score == 0.0

    def test_critical_findings_property(self, tmp_path):
        write(tmp_path / "Dockerfile", "FROM ubuntu:20.04\nUSER root\n")
        result = make_scanner().scan(str(tmp_path))
        assert len(result.critical_findings) > 0
        assert all(f.severity == "critical" for f in result.critical_findings)
