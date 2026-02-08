"""
Benchmark Suite with Golden Answers

Fixed set of known inputs with expected outputs. Run on every CI build
to detect agent behavior regressions. If an agent's decision changes
for a known scenario, the benchmark fails.
"""

import json
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime


@dataclass
class BenchmarkCase:
    """A single benchmark test case with golden answer."""
    id: str
    agent_type: str
    description: str
    input_data: Dict[str, Any]
    expected_status: str
    expected_fields: Dict[str, Any]  # key -> expected value (supports partial match)
    tolerance: float = 0.0  # for numeric comparisons


@dataclass
class BenchmarkResult:
    case_id: str
    passed: bool
    expected: Dict[str, Any]
    actual: Dict[str, Any]
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


class BenchmarkSuite:
    """
    Runs a fixed benchmark against agent functions and compares to golden answers.
    """

    def __init__(self):
        self.cases: List[BenchmarkCase] = []
        self.results: List[BenchmarkResult] = []

    def add_case(self, case: BenchmarkCase):
        self.cases.append(case)

    def load_from_file(self, path: str):
        """Load benchmark cases from a JSON file."""
        data = json.loads(Path(path).read_text())
        for item in data:
            self.cases.append(BenchmarkCase(**item))

    def save_to_file(self, path: str):
        """Save benchmark cases to a JSON file."""
        data = [asdict(c) for c in self.cases]
        Path(path).write_text(json.dumps(data, indent=2))

    def run(self, execute_fn: Callable[[str, Dict], Dict]) -> List[BenchmarkResult]:
        """
        Run all benchmark cases.

        Args:
            execute_fn: Function(agent_type, input_data) -> result_dict
        """
        self.results = []
        for case in self.cases:
            import time
            start = time.time()
            try:
                actual = execute_fn(case.agent_type, case.input_data)
            except Exception as e:
                actual = {"status": "error", "error": str(e)}
            elapsed = (time.time() - start) * 1000

            errors = []
            # Check status
            if actual.get("status") != case.expected_status:
                errors.append(
                    f"status: expected '{case.expected_status}', got '{actual.get('status')}'"
                )
            # Check expected fields
            for key, expected_val in case.expected_fields.items():
                actual_val = actual.get(key)
                if isinstance(expected_val, (int, float)) and isinstance(actual_val, (int, float)):
                    if abs(actual_val - expected_val) > case.tolerance:
                        errors.append(f"{key}: expected ~{expected_val}, got {actual_val}")
                elif actual_val != expected_val:
                    errors.append(f"{key}: expected {expected_val!r}, got {actual_val!r}")

            self.results.append(BenchmarkResult(
                case_id=case.id,
                passed=len(errors) == 0,
                expected={"status": case.expected_status, **case.expected_fields},
                actual=actual,
                errors=errors,
                duration_ms=elapsed,
            ))

        return self.results

    def summary(self) -> Dict[str, Any]:
        """Get summary of benchmark run."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = [r for r in self.results if not r.passed]
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "failures": [
                {"case_id": r.case_id, "errors": r.errors} for r in failed
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }


def get_default_benchmarks() -> BenchmarkSuite:
    """Return the built-in benchmark suite for AgenticQA agents."""
    suite = BenchmarkSuite()

    suite.add_case(BenchmarkCase(
        id="qa-pass-all",
        agent_type="qa",
        description="QA agent with all tests passing should report success",
        input_data={"test_results": {"total": 100, "passed": 100, "failed": 0}},
        expected_status="success",
        expected_fields={"agent": "QA"},
    ))

    suite.add_case(BenchmarkCase(
        id="qa-some-failures",
        agent_type="qa",
        description="QA agent with failures should detect them",
        input_data={"test_results": {"total": 100, "passed": 85, "failed": 15}},
        expected_status="success",
        expected_fields={"agent": "QA"},
    ))

    suite.add_case(BenchmarkCase(
        id="perf-normal",
        agent_type="performance",
        description="Performance agent with normal metrics",
        input_data={"execution_data": {"response_time_ms": 200, "cpu_percent": 45}},
        expected_status="success",
        expected_fields={"agent": "Performance"},
    ))

    suite.add_case(BenchmarkCase(
        id="compliance-clean",
        agent_type="compliance",
        description="Compliance agent with no violations",
        input_data={"compliance_data": {"violations": [], "scan_passed": True}},
        expected_status="success",
        expected_fields={"agent": "Compliance"},
    ))

    suite.add_case(BenchmarkCase(
        id="devops-ready",
        agent_type="devops",
        description="DevOps agent with healthy deployment config",
        input_data={"deployment_config": {"target": "staging", "health_check": True}},
        expected_status="success",
        expected_fields={"agent": "DevOps"},
    ))

    suite.add_case(BenchmarkCase(
        id="qa-empty-input",
        agent_type="qa",
        description="QA agent handles empty input gracefully",
        input_data={},
        expected_status="success",
        expected_fields={"agent": "QA"},
    ))

    return suite
