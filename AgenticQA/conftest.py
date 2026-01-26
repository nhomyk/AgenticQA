"""
pytest configuration for AgenticQA tests
"""

import pytest
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


@pytest.fixture(scope="session")
def test_artifacts_dir(tmp_path_factory):
    """Create temporary directory for test artifacts."""
    return tmp_path_factory.mktemp("artifacts")


@pytest.fixture(scope="session")
def snapshot_dir(tmp_path_factory):
    """Create temporary directory for snapshots."""
    return tmp_path_factory.mktemp("snapshots")
