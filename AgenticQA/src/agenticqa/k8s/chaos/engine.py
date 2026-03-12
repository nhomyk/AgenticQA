"""
Chaos Experiment Engine — Fault injection framework for K8s.

INTERVIEW CONCEPT: Chaos engineering is the discipline of experimenting
on a distributed system to build confidence in its ability to withstand
turbulent conditions in production. The key principle: "steady state
hypothesis" — define what healthy looks like, inject a fault, verify
the system returns to steady state.

Supported backends:
    - Native: kubectl-based (pod delete, node drain, exec kill)
    - Chaos Mesh: CRD-based (fine-grained network, IO, time faults)
    - Litmus: CRD-based (pre-built experiments from ChaosHub)

Usage:
    engine = ChaosEngine(kubeconfig="/path/to/kubeconfig")

    # Run a single experiment
    result = engine.run_experiment(
        PodKillExperiment(namespace="default", label_selector="app=web")
    )

    # Run a suite against the taxonomy
    results = engine.run_suite([
        PodKillExperiment(...),
        NetworkLatencyExperiment(...),
        DiskFillExperiment(...),
    ])
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    """Outcome of a chaos experiment."""

    PASSED = "passed"  # System recovered within SLO
    FAILED = "failed"  # System did not recover or SLO violated
    ERROR = "error"  # Experiment itself failed to run
    SKIPPED = "skipped"  # Pre-conditions not met


@dataclass
class SteadyStateHypothesis:
    """
    Define what "healthy" looks like before and after the experiment.

    INTERVIEW CONCEPT: This is the most important part of chaos engineering.
    Without a steady state hypothesis, you're just breaking things randomly.
    The hypothesis should be measurable and automated.
    """

    description: str
    check_command: list[str]  # kubectl command to verify
    expected_output: Optional[str] = None  # substring to find in output
    timeout_seconds: int = 60
    check_interval_seconds: int = 5


@dataclass
class ExperimentResult:
    """Result of running a chaos experiment."""

    experiment_name: str
    taxonomy_id: str  # Maps back to failure taxonomy (e.g., "POD-001")
    status: ExperimentStatus
    duration_seconds: float = 0.0
    steady_state_before: bool = False
    steady_state_after: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    error: str = ""


class ChaosExperiment(ABC):
    """
    Base class for all chaos experiments.

    Subclasses implement inject() and cleanup(). The engine handles
    steady state verification and recovery waiting.
    """

    name: str = "base"
    taxonomy_id: str = ""  # Link to failure taxonomy
    description: str = ""

    @abstractmethod
    def inject(self, kubectl_fn) -> dict:
        """
        Inject the fault.

        Args:
            kubectl_fn: Callable that runs kubectl commands.

        Returns:
            Dict with injection details (what was affected).
        """

    @abstractmethod
    def cleanup(self, kubectl_fn) -> None:
        """Reverse the fault injection (if needed)."""

    def steady_state(self) -> Optional[SteadyStateHypothesis]:
        """
        Define steady state hypothesis. Override in subclasses.

        Returns None if no automated steady state check is defined.
        """
        return None


class ChaosEngine:
    """
    Orchestrates chaos experiments against a K8s cluster.

    The engine follows the chaos engineering loop:
    1. Define steady state hypothesis
    2. Verify steady state (before)
    3. Inject fault
    4. Wait for recovery period
    5. Verify steady state (after)
    6. Cleanup
    """

    def __init__(
        self,
        kubeconfig: Optional[str] = None,
        context: Optional[str] = None,
        recovery_wait_seconds: int = 30,
        dry_run: bool = False,
    ) -> None:
        self._kubeconfig = kubeconfig
        self._context = context
        self._recovery_wait = recovery_wait_seconds
        self._dry_run = dry_run
        self._results: list[ExperimentResult] = []

    @property
    def results(self) -> list[ExperimentResult]:
        return list(self._results)

    def run_experiment(self, experiment: ChaosExperiment) -> ExperimentResult:
        """
        Run a single chaos experiment through the full lifecycle.

        INTERVIEW CONCEPT: The lifecycle is:
            steady_state_check → inject → wait → steady_state_check → cleanup
        If steady state fails BEFORE injection, the experiment is skipped
        (system is already unhealthy, can't attribute fault to injection).
        """
        start_time = time.monotonic()
        logger.info(
            "Starting experiment: %s (%s)", experiment.name, experiment.taxonomy_id
        )

        # Dry run mode — validate experiment without injecting
        if self._dry_run:
            result = ExperimentResult(
                experiment_name=experiment.name,
                taxonomy_id=experiment.taxonomy_id,
                status=ExperimentStatus.SKIPPED,
                details={"reason": "dry_run"},
            )
            self._results.append(result)
            return result

        hypothesis = experiment.steady_state()

        # Step 1: Verify steady state before injection
        steady_before = True
        if hypothesis:
            steady_before = self._check_steady_state(hypothesis)
            if not steady_before:
                result = ExperimentResult(
                    experiment_name=experiment.name,
                    taxonomy_id=experiment.taxonomy_id,
                    status=ExperimentStatus.SKIPPED,
                    steady_state_before=False,
                    details={"reason": "steady state failed before injection"},
                )
                self._results.append(result)
                logger.warning(
                    "Skipping %s: steady state not met before injection",
                    experiment.name,
                )
                return result

        # Step 2: Inject fault
        try:
            injection_details = experiment.inject(self._kubectl)
        except Exception as e:
            result = ExperimentResult(
                experiment_name=experiment.name,
                taxonomy_id=experiment.taxonomy_id,
                status=ExperimentStatus.ERROR,
                steady_state_before=steady_before,
                error=str(e),
                duration_seconds=time.monotonic() - start_time,
            )
            self._results.append(result)
            return result

        # Step 3: Wait for recovery
        logger.info("Waiting %ds for recovery...", self._recovery_wait)
        time.sleep(self._recovery_wait)

        # Step 4: Verify steady state after injection
        steady_after = True
        if hypothesis:
            steady_after = self._check_steady_state(hypothesis)

        # Step 5: Cleanup
        try:
            experiment.cleanup(self._kubectl)
        except Exception as e:
            logger.warning("Cleanup failed for %s: %s", experiment.name, e)

        duration = time.monotonic() - start_time
        status = (
            ExperimentStatus.PASSED if steady_after else ExperimentStatus.FAILED
        )

        result = ExperimentResult(
            experiment_name=experiment.name,
            taxonomy_id=experiment.taxonomy_id,
            status=status,
            duration_seconds=duration,
            steady_state_before=steady_before,
            steady_state_after=steady_after,
            details=injection_details or {},
        )
        self._results.append(result)

        logger.info(
            "Experiment %s: %s (%.1fs)",
            experiment.name,
            status.value,
            duration,
        )
        return result

    def run_suite(
        self, experiments: list[ChaosExperiment]
    ) -> list[ExperimentResult]:
        """Run a list of experiments sequentially."""
        results = []
        for exp in experiments:
            results.append(self.run_experiment(exp))
        return results

    def summary(self) -> dict:
        """Summary of all experiment results."""
        by_status = {}
        for r in self._results:
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1

        taxonomy_coverage = {
            r.taxonomy_id
            for r in self._results
            if r.status in (ExperimentStatus.PASSED, ExperimentStatus.FAILED)
        }

        return {
            "total_experiments": len(self._results),
            "by_status": by_status,
            "taxonomy_ids_tested": sorted(taxonomy_coverage),
            "pass_rate": (
                sum(
                    1
                    for r in self._results
                    if r.status == ExperimentStatus.PASSED
                )
                / max(len(self._results), 1)
                * 100
            ),
        }

    # ── Private helpers ──────────────────────────────────────────────────

    def _check_steady_state(self, hypothesis: SteadyStateHypothesis) -> bool:
        """Poll until steady state is met or timeout expires."""
        deadline = time.monotonic() + hypothesis.timeout_seconds
        while time.monotonic() < deadline:
            output = self._kubectl(*hypothesis.check_command)
            if output is not None:
                if hypothesis.expected_output is None:
                    return True  # Command succeeded, no output check needed
                if hypothesis.expected_output in output:
                    return True
            time.sleep(hypothesis.check_interval_seconds)
        return False

    def _kubectl(self, *args: str) -> Optional[str]:
        """Run kubectl and return stdout."""
        import subprocess

        cmd = ["kubectl"]
        if self._kubeconfig:
            cmd.extend(["--kubeconfig", self._kubeconfig])
        if self._context:
            cmd.extend(["--context", self._context])
        cmd.extend(args)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=30
            )
            return result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning("kubectl failed: %s", e)
            return None
