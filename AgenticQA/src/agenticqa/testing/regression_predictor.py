"""
Regression Prediction / Smart Test Selection.

Given changed files, predicts which tests are most likely to fail and
recommends running them first. Uses file name matching heuristics to
score test relevance without requiring coverage data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------
_EXACT_MATCH_SCORE = 1.0
_PARTIAL_MATCH_SCORE = 0.75
_CATEGORY_MATCH_SCORE = 0.5
_INTEGRATION_SCORE = 0.3
_NO_MATCH_SCORE = 0.1

_LIKELY_FAIL_THRESHOLD = 0.7
_POSSIBLY_FAIL_THRESHOLD = 0.4
_SKIP_THRESHOLD = 0.1

_TEST_EXTS = {".py"}
_SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".git", "dist", "build"}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TestPrediction:
    test_file: str
    relevance_score: float    # 0.0-1.0
    reason: str
    predicted_outcome: str    # LIKELY_FAIL | POSSIBLY_FAIL | PROBABLY_PASS

    def to_dict(self) -> dict:
        return {
            "test_file": self.test_file,
            "relevance_score": self.relevance_score,
            "reason": self.reason,
            "predicted_outcome": self.predicted_outcome,
        }


@dataclass
class RegressionPredictionResult:
    changed_files: List[str]
    test_predictions: List[TestPrediction]   # sorted by relevance_score desc
    priority_tests: List[str]               # relevance >= 0.5
    skip_candidates: List[str]              # relevance < 0.1
    coverage_estimate: float               # fraction of changed code likely covered

    def to_dict(self) -> dict:
        return {
            "changed_files": self.changed_files,
            "test_predictions": [p.to_dict() for p in self.test_predictions],
            "priority_tests": self.priority_tests,
            "skip_candidates": self.skip_candidates,
            "coverage_estimate": self.coverage_estimate,
        }


# ---------------------------------------------------------------------------
# Predictor
# ---------------------------------------------------------------------------

class RegressionPredictor:
    """Predict which tests are likely to fail given a set of changed files."""

    def predict(
        self, repo_path: str, changed_files: List[str]
    ) -> RegressionPredictionResult:
        root = Path(repo_path).resolve()

        if not changed_files:
            return RegressionPredictionResult(
                changed_files=[],
                test_predictions=[],
                priority_tests=[],
                skip_candidates=[],
                coverage_estimate=0.0,
            )

        # Extract stems from changed files for matching
        changed_stems = [Path(f).stem for f in changed_files]

        # Find all test files
        test_paths = self._find_test_files(root)

        if not test_paths:
            return RegressionPredictionResult(
                changed_files=list(changed_files),
                test_predictions=[],
                priority_tests=[],
                skip_candidates=[],
                coverage_estimate=0.0,
            )

        # Score each test
        predictions: List[TestPrediction] = []
        for test_path in test_paths:
            prediction = self._score_test(test_path, changed_files, root)
            predictions.append(prediction)

        # Sort by relevance_score descending
        predictions.sort(key=lambda p: p.relevance_score, reverse=True)

        priority = [p.test_file for p in predictions if p.relevance_score >= _SKIP_THRESHOLD * 2]
        # Actually per spec: priority_tests = relevance >= 0.5 (CATEGORY_MATCH_SCORE threshold)
        priority = [p.test_file for p in predictions if p.relevance_score >= _CATEGORY_MATCH_SCORE]
        skip_candidates = [p.test_file for p in predictions if p.relevance_score < _SKIP_THRESHOLD]

        total_tests = len(predictions)
        coverage_estimate = len(priority) / max(total_tests, 1)

        return RegressionPredictionResult(
            changed_files=list(changed_files),
            test_predictions=predictions,
            priority_tests=priority,
            skip_candidates=skip_candidates,
            coverage_estimate=round(coverage_estimate, 4),
        )

    def _find_test_files(self, root: Path) -> List[Path]:
        """Find all test files in the repo."""
        found: List[Path] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            if path.suffix not in _TEST_EXTS:
                continue
            name = path.name
            if name.startswith("test_") or name.endswith("_test.py") or "test" in path.parts:
                found.append(path)
        return found

    def _score_test(
        self, test_path: Path, changed_files: List[str], root: Path
    ) -> TestPrediction:
        """Score a test file against changed files and return a prediction."""
        changed_stems = [Path(f).stem for f in changed_files]
        try:
            rel = str(test_path.relative_to(root))
        except ValueError:
            rel = str(test_path)

        score, reason = self._compute_relevance(rel, changed_stems)

        if score >= _LIKELY_FAIL_THRESHOLD:
            outcome = "LIKELY_FAIL"
        elif score >= _POSSIBLY_FAIL_THRESHOLD:
            outcome = "POSSIBLY_FAIL"
        else:
            outcome = "PROBABLY_PASS"

        return TestPrediction(
            test_file=rel,
            relevance_score=round(score, 4),
            reason=reason,
            predicted_outcome=outcome,
        )

    def _compute_relevance(
        self, test_file: str, changed_stems: List[str]
    ) -> Tuple[float, str]:
        """Compute relevance score and reason for a test file vs changed stems."""
        test_stem = Path(test_file).stem
        # Strip test_ prefix and _test suffix
        clean_stem = test_stem
        if clean_stem.startswith("test_"):
            clean_stem = clean_stem[5:]
        if clean_stem.endswith("_test"):
            clean_stem = clean_stem[:-5]

        test_file_lower = test_file.lower()

        best_score = _NO_MATCH_SCORE
        best_reason = "No direct relationship to changed files"

        for changed_stem in changed_stems:
            # 1. Exact name match
            if clean_stem == changed_stem or test_stem == changed_stem:
                return _EXACT_MATCH_SCORE, f"Exact name match: test covers changed module"

            # 2. Partial name match — changed stem appears in test stem
            if changed_stem in clean_stem or changed_stem in test_stem:
                if _PARTIAL_MATCH_SCORE > best_score:
                    best_score = _PARTIAL_MATCH_SCORE
                    best_reason = f"Partial match: test name contains changed module name"

            # 3. Shared category — changed file dir keyword appears in test path
            changed_parts = changed_stem.split("_")
            for part in changed_parts:
                if len(part) >= 4 and part in test_file_lower:
                    if _CATEGORY_MATCH_SCORE > best_score:
                        best_score = _CATEGORY_MATCH_SCORE
                        best_reason = f"Shared category: test path contains '{part}' from changed file"
                        break

        # 4. Integration test — always include with score 0.3
        test_path_obj = Path(test_file)
        is_integration = (
            test_path_obj.stem.startswith("test_integration")
            or "integration" in test_path_obj.parts
        )
        if is_integration and best_score < _INTEGRATION_SCORE:
            best_score = _INTEGRATION_SCORE
            best_reason = "Integration test: always run against any changes"

        return best_score, best_reason
