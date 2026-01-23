"""
Python SDK Example 3: CI/CD Pipeline Integration

This example shows how to integrate AgenticQA into your CI/CD pipeline.
Perfect for GitHub Actions, GitLab CI, Jenkins, etc.
"""

import sys
import json
from pathlib import Path
from agenticqa import AgentOrchestrator
from agenticqa.data_store import DataQualityValidatedPipeline

def run_qa_pipeline(test_directory: str):
    """
    Run complete QA pipeline for a project.
    
    Returns:
        - 0: All tests passed, ready to deploy
        - 1: Tests passed but warnings present
        - 2: Tests failed, do not deploy
    """
    
    test_directory = Path(test_directory)
    
    # Collect test data from files
    test_data = {
        "code": (test_directory / "src").read_text() if (test_directory / "src").exists() else "",
        "tests": (test_directory / "tests").read_text() if (test_directory / "tests").exists() else "",
        "config": json.loads((test_directory / "config.json").read_text()) if (test_directory / "config.json").exists() else {},
    }
    
    print("🚀 Starting AgenticQA Pipeline...")
    
    # Use validated pipeline for quality assurance
    pipeline = DataQualityValidatedPipeline()
    
    try:
        results = pipeline.execute_with_validation(test_data)
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        return 2
    
    # Analyze results
    qa_status = results.get("qa_agent", {}).get("status", "unknown")
    perf_status = results.get("performance_agent", {}).get("status", "unknown")
    compliance_status = results.get("compliance_agent", {}).get("status", "unknown")
    devops_status = results.get("devops_agent", {}).get("status", "unknown")
    
    print(f"\n📊 Pipeline Results:")
    print(f"  QA Agent: {qa_status}")
    print(f"  Performance Agent: {perf_status}")
    print(f"  Compliance Agent: {compliance_status}")
    print(f"  DevOps Agent: {devops_status}")
    
    # Determine deployment status
    failed_agents = [s for s in [qa_status, perf_status, compliance_status, devops_status] if s == "failed"]
    warning_agents = [s for s in [qa_status, perf_status, compliance_status, devops_status] if s == "warning"]
    
    if failed_agents:
        print(f"\n❌ Pipeline FAILED: {len(failed_agents)} agent(s) failed")
        return 2
    elif warning_agents:
        print(f"\n⚠️  Pipeline PASSED with WARNINGS: {len(warning_agents)} agent(s) have warnings")
        return 1
    else:
        print(f"\n✅ Pipeline PASSED: Ready to deploy!")
        return 0


if __name__ == "__main__":
    # Get test directory from command line or use current directory
    test_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    exit_code = run_qa_pipeline(test_dir)
    sys.exit(exit_code)
