"""
AgenticQA - Intelligent Autonomous QA Platform

A comprehensive QA platform powered by specialized agents that learn from historical patterns,
analyze real-time data, and make intelligent deployment decisions.

Example:
    >>> from agenticqa import AgentOrchestrator, TestArtifactStore
    >>> 
    >>> orchestrator = AgentOrchestrator()
    >>> results = orchestrator.execute_all_agents(test_data)
    >>> 
    >>> store = TestArtifactStore()
    >>> patterns = store.get_patterns()
"""

from agenticqa.agents import (
    BaseAgent,
    QAAssistantAgent,
    PerformanceAgent,
    ComplianceAgent,
    DevOpsAgent,
    AgentOrchestrator,
)

from agenticqa.data_store import (
    TestArtifactStore,
    SecureDataPipeline,
    PatternAnalyzer,
    DataQualityTester,
    DataQualityValidatedPipeline,
)

from agenticqa.data_store.snapshot_manager import SnapshotManager
from agenticqa.data_store.snapshot_pipeline import SnapshotValidatingPipeline
from agenticqa.data_store.code_change_tracker import CodeChangeTracker, BeforeAfterMetrics, ChangeImpactReport
from agenticqa.data_store.change_executor import SafeCodeChangeExecutor, ChangeHistoryAnalyzer

__version__ = "1.0.0"
__author__ = "Nicholas Homyk"
__license__ = "MIT"

__all__ = [
    "BaseAgent",
    "QAAssistantAgent",
    "PerformanceAgent",
    "ComplianceAgent",
    "DevOpsAgent",
    "AgentOrchestrator",
    "TestArtifactStore",
    "SecureDataPipeline",
    "PatternAnalyzer",
    "DataQualityTester",
    "DataQualityValidatedPipeline",
    "SnapshotManager",
    "SnapshotValidatingPipeline",
    "CodeChangeTracker",
    "BeforeAfterMetrics",
    "ChangeImpactReport",
    "SafeCodeChangeExecutor",
    "ChangeHistoryAnalyzer",
]
