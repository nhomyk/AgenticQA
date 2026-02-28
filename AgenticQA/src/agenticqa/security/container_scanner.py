"""
Container & Infrastructure Security Scanner.

Scans Dockerfiles, docker-compose files, and Kubernetes YAML for security
issues. Pure static analysis — no external tools, no subprocess.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml  # type: ignore
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


# ---------------------------------------------------------------------------
# Severity weights
# ---------------------------------------------------------------------------
_SEVERITY_WEIGHTS: Dict[str, float] = {
    "critical": 1.0,
    "high": 0.6,
    "medium": 0.3,
    "low": 0.1,
}

_SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".git", "dist", "build"}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ContainerFinding:
    check_id: str
    severity: str
    source_file: str
    line_number: int
    evidence: str
    description: str
    remediation: str

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "severity": self.severity,
            "source_file": self.source_file,
            "line_number": self.line_number,
            "evidence": self.evidence,
            "description": self.description,
            "remediation": self.remediation,
        }


@dataclass
class ContainerScanResult:
    repo_path: str
    findings: List[ContainerFinding]
    files_scanned: int
    dockerfiles_found: int
    compose_files_found: int
    k8s_files_found: int
    risk_score: float

    @property
    def critical_findings(self) -> List[ContainerFinding]:
        return [f for f in self.findings if f.severity == "critical"]

    def to_dict(self) -> dict:
        return {
            "repo_path": self.repo_path,
            "findings": [f.to_dict() for f in self.findings],
            "files_scanned": self.files_scanned,
            "dockerfiles_found": self.dockerfiles_found,
            "compose_files_found": self.compose_files_found,
            "k8s_files_found": self.k8s_files_found,
            "risk_score": self.risk_score,
            "critical_findings": [f.to_dict() for f in self.critical_findings],
        }


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class ContainerScanner:
    """Scan Dockerfiles, compose files, and k8s YAML for security issues."""

    def scan(self, repo_path: str = ".") -> ContainerScanResult:
        root = Path(repo_path).resolve()
        all_findings: List[ContainerFinding] = []
        files_scanned = 0
        dockerfiles_found = 0
        compose_files_found = 0
        k8s_files_found = 0

        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in _SKIP_DIRS for part in path.parts):
                continue

            name = path.name
            suffix = path.suffix.lower()

            # Dockerfile detection
            if self._is_dockerfile(name):
                findings = self._scan_dockerfile(path, root)
                all_findings.extend(findings)
                files_scanned += 1
                dockerfiles_found += 1

            # Docker Compose detection
            elif self._is_compose_file(name, path):
                findings = self._scan_compose(path, root)
                all_findings.extend(findings)
                files_scanned += 1
                compose_files_found += 1

            # K8s YAML detection
            elif self._is_k8s_file(name, path, suffix):
                findings = self._scan_k8s(path, root)
                all_findings.extend(findings)
                files_scanned += 1
                k8s_files_found += 1

        risk_score = min(
            100.0,
            sum(_SEVERITY_WEIGHTS.get(f.severity, 0) * 10 for f in all_findings),
        )

        return ContainerScanResult(
            repo_path=str(root),
            findings=all_findings,
            files_scanned=files_scanned,
            dockerfiles_found=dockerfiles_found,
            compose_files_found=compose_files_found,
            k8s_files_found=k8s_files_found,
            risk_score=round(risk_score, 2),
        )

    # ------------------------------------------------------------------
    # File type detection
    # ------------------------------------------------------------------

    def _is_dockerfile(self, name: str) -> bool:
        return name == "Dockerfile" or name.lower().startswith("dockerfile")

    def _is_compose_file(self, name: str, path: Path) -> bool:
        lower = name.lower()
        if lower.startswith("docker-compose") and lower.endswith((".yml", ".yaml")):
            return True
        if lower.endswith((".yml", ".yaml")):
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                return "services:" in content
            except OSError:
                pass
        return False

    def _is_k8s_file(self, name: str, path: Path, suffix: str) -> bool:
        if suffix not in (".yml", ".yaml"):
            return False
        # Already covered as compose
        if self._is_compose_file(name, path):
            return False
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            return "apiVersion:" in content and "kind:" in content
        except OSError:
            return False

    # ------------------------------------------------------------------
    # Dockerfile scanning
    # ------------------------------------------------------------------

    def _scan_dockerfile(self, path: Path, root: Path) -> List[ContainerFinding]:
        findings: List[ContainerFinding] = []
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return findings

        rel = str(path.relative_to(root))
        lines = content.splitlines()

        has_user = False
        has_healthcheck = False

        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()
            upper = stripped.upper()

            # DOCK-001: USER root
            if re.match(r"USER\s+root\b", stripped, re.IGNORECASE):
                findings.append(ContainerFinding(
                    check_id="DOCK-001",
                    severity="critical",
                    source_file=rel,
                    line_number=line_num,
                    evidence=stripped,
                    description="Container runs as root",
                    remediation="Add 'USER nonroot' or create a dedicated non-root user",
                ))

            # Track if USER instruction exists (non-root)
            if re.match(r"^USER\b", stripped, re.IGNORECASE):
                has_user = True

            # DOCK-002: ADD with URL
            if re.match(r"ADD\s+https?://", stripped, re.IGNORECASE):
                findings.append(ContainerFinding(
                    check_id="DOCK-002",
                    severity="high",
                    source_file=rel,
                    line_number=line_num,
                    evidence=stripped,
                    description="ADD with URL fetches remote content at build time",
                    remediation="Use RUN curl/wget + verification instead of ADD with URL",
                ))

            # DOCK-003: privileged in RUN
            if re.match(r"RUN\b", stripped, re.IGNORECASE) and "--privileged" in stripped:
                findings.append(ContainerFinding(
                    check_id="DOCK-003",
                    severity="high",
                    source_file=rel,
                    line_number=line_num,
                    evidence=stripped,
                    description="Privileged mode during build",
                    remediation="Remove --privileged flag from RUN instruction",
                ))

            # DOCK-004: ENV with secret
            if re.match(r"ENV\b", stripped, re.IGNORECASE):
                if re.search(r"(PASSWORD|SECRET|KEY)\s*=", stripped, re.IGNORECASE):
                    findings.append(ContainerFinding(
                        check_id="DOCK-004",
                        severity="medium",
                        source_file=rel,
                        line_number=line_num,
                        evidence=stripped,
                        description="Secret in ENV instruction",
                        remediation="Use Docker secrets or build args with --secret instead of ENV",
                    ))

            # DOCK-005: HEALTHCHECK
            if upper.startswith("HEALTHCHECK"):
                has_healthcheck = True

            # DOCK-006: latest tag in FROM
            if re.match(r"FROM\b", stripped, re.IGNORECASE):
                if re.search(r":latest\b", stripped, re.IGNORECASE) or (
                    ":" not in stripped.split()[-1] and "@" not in stripped.split()[-1]
                    and "AS" not in stripped.upper()
                ):
                    if ":latest" in stripped.lower() or (
                        ":" not in stripped and "@" not in stripped and len(stripped.split()) == 2
                    ):
                        findings.append(ContainerFinding(
                            check_id="DOCK-006",
                            severity="low",
                            source_file=rel,
                            line_number=line_num,
                            evidence=stripped,
                            description="Unpinned base image tag",
                            remediation="Pin base image to a specific digest or version tag",
                        ))

            # DOCK-007: COPY . .
            if re.match(r"COPY\s+\.\s+\.", stripped, re.IGNORECASE):
                findings.append(ContainerFinding(
                    check_id="DOCK-007",
                    severity="medium",
                    source_file=rel,
                    line_number=line_num,
                    evidence=stripped,
                    description="Entire context copied — may include .env and secrets",
                    remediation="Use .dockerignore to exclude sensitive files",
                ))

        # DOCK-001 no USER at all
        if not has_user:
            findings.append(ContainerFinding(
                check_id="DOCK-001",
                severity="critical",
                source_file=rel,
                line_number=0,
                evidence="(no USER instruction found)",
                description="Container runs as root",
                remediation="Add 'USER nonroot' instruction to run as non-root",
            ))

        # DOCK-005 no HEALTHCHECK
        if not has_healthcheck:
            findings.append(ContainerFinding(
                check_id="DOCK-005",
                severity="medium",
                source_file=rel,
                line_number=0,
                evidence="(no HEALTHCHECK found)",
                description="No HEALTHCHECK defined",
                remediation="Add HEALTHCHECK instruction for container orchestration",
            ))

        return findings

    # ------------------------------------------------------------------
    # Docker Compose scanning
    # ------------------------------------------------------------------

    def _scan_compose(self, path: Path, root: Path) -> List[ContainerFinding]:
        findings: List[ContainerFinding] = []
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return findings

        rel = str(path.relative_to(root))
        lines = content.splitlines()

        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()

            # COMP-001: privileged: true
            if re.match(r"privileged\s*:\s*true", stripped, re.IGNORECASE):
                findings.append(ContainerFinding(
                    check_id="COMP-001",
                    severity="critical",
                    source_file=rel,
                    line_number=line_num,
                    evidence=stripped,
                    description="Container runs in privileged mode",
                    remediation="Remove 'privileged: true' and use specific capabilities instead",
                ))

            # COMP-002: network_mode: host
            if re.match(r"network_mode\s*:\s*['\"]?host['\"]?", stripped, re.IGNORECASE):
                findings.append(ContainerFinding(
                    check_id="COMP-002",
                    severity="high",
                    source_file=rel,
                    line_number=line_num,
                    evidence=stripped,
                    description="Host network mode — container shares host networking",
                    remediation="Use bridge networking and expose only required ports",
                ))

            # COMP-003: docker.sock mount
            if "/var/run/docker.sock" in stripped:
                findings.append(ContainerFinding(
                    check_id="COMP-003",
                    severity="high",
                    source_file=rel,
                    line_number=line_num,
                    evidence=stripped,
                    description="Docker socket mounted — container can control host Docker",
                    remediation="Avoid mounting Docker socket; use rootless Docker or Podman",
                ))

            # COMP-004: environment with secrets
            if re.search(r"(PASSWORD|SECRET|KEY)\s*[:=]", stripped, re.IGNORECASE):
                # Avoid flagging 'environment:' section header itself
                if "environment" not in stripped.lower() or ":" in stripped[10:]:
                    findings.append(ContainerFinding(
                        check_id="COMP-004",
                        severity="medium",
                        source_file=rel,
                        line_number=line_num,
                        evidence=stripped,
                        description="Secret in compose environment",
                        remediation="Use Docker secrets or .env file with docker-compose --env-file",
                    ))

            # COMP-005: ports with 0.0.0.0
            if re.search(r"['\"]?0\.0\.0\.0:", stripped):
                findings.append(ContainerFinding(
                    check_id="COMP-005",
                    severity="medium",
                    source_file=rel,
                    line_number=line_num,
                    evidence=stripped,
                    description="Service bound to all interfaces",
                    remediation="Bind to 127.0.0.1 unless external access is required",
                ))

        return findings

    # ------------------------------------------------------------------
    # K8s YAML scanning
    # ------------------------------------------------------------------

    def _scan_k8s(self, path: Path, root: Path) -> List[ContainerFinding]:
        findings: List[ContainerFinding] = []
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return findings

        rel = str(path.relative_to(root))
        lines = content.splitlines()

        has_resource_limits = False

        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()

            # K8S-001: privileged: true
            if re.match(r"privileged\s*:\s*true", stripped, re.IGNORECASE):
                findings.append(ContainerFinding(
                    check_id="K8S-001",
                    severity="critical",
                    source_file=rel,
                    line_number=line_num,
                    evidence=stripped,
                    description="Pod running in privileged mode",
                    remediation="Set privileged: false in securityContext",
                ))

            # K8S-002: hostNetwork: true
            if re.match(r"hostNetwork\s*:\s*true", stripped, re.IGNORECASE):
                findings.append(ContainerFinding(
                    check_id="K8S-002",
                    severity="high",
                    source_file=rel,
                    line_number=line_num,
                    evidence=stripped,
                    description="Pod shares host network namespace",
                    remediation="Set hostNetwork: false unless absolutely required",
                ))

            # K8S-003: allowPrivilegeEscalation: true
            if re.match(r"allowPrivilegeEscalation\s*:\s*true", stripped, re.IGNORECASE):
                findings.append(ContainerFinding(
                    check_id="K8S-003",
                    severity="high",
                    source_file=rel,
                    line_number=line_num,
                    evidence=stripped,
                    description="Privilege escalation allowed",
                    remediation="Set allowPrivilegeEscalation: false in securityContext",
                ))

            # K8S-004: runAsRoot: true (or missing runAsNonRoot)
            if re.match(r"runAsRoot\s*:\s*true", stripped, re.IGNORECASE):
                findings.append(ContainerFinding(
                    check_id="K8S-004",
                    severity="medium",
                    source_file=rel,
                    line_number=line_num,
                    evidence=stripped,
                    description="Container may run as root",
                    remediation="Set runAsNonRoot: true and specify runAsUser",
                ))

            # K8S-005: resource limits
            if re.match(r"limits\s*:", stripped, re.IGNORECASE):
                has_resource_limits = True

            # K8S-006: hostPath volume
            if re.match(r"hostPath\s*:", stripped, re.IGNORECASE):
                findings.append(ContainerFinding(
                    check_id="K8S-006",
                    severity="high",
                    source_file=rel,
                    line_number=line_num,
                    evidence=stripped,
                    description="Host filesystem mounted into pod",
                    remediation="Use PersistentVolumeClaims instead of hostPath mounts",
                ))

        # K8S-005: no resource limits found in the entire file
        if not has_resource_limits and ("kind: Pod" in content or "kind: Deployment" in content or "containers:" in content):
            findings.append(ContainerFinding(
                check_id="K8S-005",
                severity="medium",
                source_file=rel,
                line_number=0,
                evidence="(no resource limits found)",
                description="No CPU/memory limits — DoS risk",
                remediation="Add resources.limits.cpu and resources.limits.memory",
            ))

        return findings
