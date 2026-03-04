"""Locust-based load testing for AgenticQA API endpoints.

Optional dependency — install with ``pip install agenticqa[loadtest]``.

Usage (CLI):
    python scripts/run_load_test.py --host http://localhost:8000 --users 20 --duration 60

Usage (programmatic):
    from agenticqa.loadtest.results import LoadTestResult, LoadTestAnalyzer
"""
from agenticqa.loadtest.results import (
    EndpointStats,
    LoadTestResult,
    LoadTestAnalyzer,
)

__all__ = ["EndpointStats", "LoadTestResult", "LoadTestAnalyzer"]
