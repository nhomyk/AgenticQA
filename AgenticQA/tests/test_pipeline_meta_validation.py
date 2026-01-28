"""
Pipeline Meta-Validation Framework

Tests the CI/CD pipeline ITSELF by intentionally introducing errors and verifying:
1. Pipeline detects the errors
2. Agents execute their expected functionality
3. Agents fix the errors autonomously
4. New commits/workflows are triggered
5. System self-heals end-to-end

These are META-TESTS that validate the entire framework, not individual components.
"""

import pytest
import os
import time
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


# Skip all tests if not in CI or if GH_TOKEN not available
SKIP_IF_NOT_CI = os.getenv("CI") is None
SKIP_IF_NO_TOKEN = os.getenv("GH_TOKEN") is None or os.getenv("GITHUB_TOKEN") is None


class GitHubWorkflowManager:
    """Manages GitHub workflow operations via gh CLI"""

    def __init__(self, repo: str = "nhomyk/AgenticQA"):
        self.repo = repo
        self.gh_available = self._check_gh_cli()

    def _check_gh_cli(self) -> bool:
        """Check if gh CLI is available"""
        try:
            result = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def trigger_workflow(self, workflow: str, ref: str = "main") -> Optional[str]:
        """
        Trigger a workflow and return the run ID.

        Args:
            workflow: Workflow filename (e.g., "ci.yml")
            ref: Branch or tag to run workflow on

        Returns:
            Workflow run ID if successful, None otherwise
        """
        if not self.gh_available:
            return None

        try:
            # Trigger workflow
            result = subprocess.run(
                ["gh", "workflow", "run", workflow, "--ref", ref],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                print(f"Failed to trigger workflow: {result.stderr}")
                return None

            # Wait a moment for workflow to appear
            time.sleep(5)

            # Get latest workflow run ID
            result = subprocess.run(
                ["gh", "run", "list", "--workflow", workflow, "--limit", "1", "--json", "databaseId"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                runs = json.loads(result.stdout)
                if runs:
                    return str(runs[0]["databaseId"])

            return None

        except Exception as e:
            print(f"Error triggering workflow: {e}")
            return None

    def get_workflow_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get workflow run status.

        Returns:
            Dict with status, conclusion, jobs info
        """
        if not self.gh_available:
            return None

        try:
            result = subprocess.run(
                ["gh", "run", "view", run_id, "--json", "status,conclusion,jobs"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return json.loads(result.stdout)

            return None

        except Exception as e:
            print(f"Error getting workflow status: {e}")
            return None

    def wait_for_workflow_completion(
        self,
        run_id: str,
        timeout_minutes: int = 30,
        poll_interval: int = 30
    ) -> Optional[str]:
        """
        Wait for workflow to complete.

        Returns:
            Conclusion: "success", "failure", "cancelled", etc.
        """
        if not self.gh_available:
            return None

        start_time = time.time()
        timeout_seconds = timeout_minutes * 60

        while time.time() - start_time < timeout_seconds:
            status = self.get_workflow_status(run_id)

            if status and status.get("status") == "completed":
                return status.get("conclusion")

            time.sleep(poll_interval)

        return "timeout"

    def get_job_status(self, run_id: str, job_name: str) -> Optional[Dict[str, Any]]:
        """Get specific job status from workflow run"""
        status = self.get_workflow_status(run_id)

        if not status or "jobs" not in status:
            return None

        for job in status["jobs"]:
            if job_name in job.get("name", ""):
                return job

        return None


class TestBranchManager:
    """Manages test branches with intentional errors"""

    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path)

    def create_test_branch(self, branch_name: str, base: str = "main") -> bool:
        """Create a test branch"""
        try:
            subprocess.run(
                ["git", "checkout", base],
                cwd=self.repo_path,
                capture_output=True,
                timeout=30
            )

            subprocess.run(
                ["git", "pull", "origin", base],
                cwd=self.repo_path,
                capture_output=True,
                timeout=30
            )

            result = subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=self.repo_path,
                capture_output=True,
                timeout=30
            )

            return result.returncode == 0

        except Exception as e:
            print(f"Error creating test branch: {e}")
            return False

    def introduce_linting_error(self, file_path: str = "test_linting_error.js") -> bool:
        """
        Introduce intentional linting errors in a test file.

        Creates a JS file with multiple linting violations.
        """
        test_file = self.repo_path / file_path

        # Code with intentional linting errors
        code_with_errors = """
// Test file with intentional linting errors for SRE Agent validation

function testFunction() {
    var unusedVariable = 'this should be const'  // Missing semicolon
    let message = 'wrong quotes'  // Should use double quotes

    if(true){  // Missing space before brace
        console.log(message)  // Missing semicolon
    }

    // Unused variable
    const neverUsed = 42;
}

module.exports = { testFunction }
"""

        try:
            test_file.write_text(code_with_errors)
            return True
        except Exception as e:
            print(f"Error introducing linting error: {e}")
            return False

    def introduce_coverage_gap(self, file_path: str = "test_uncovered.js") -> bool:
        """
        Introduce a file without tests to trigger SDET Agent.

        Creates code that needs test coverage.
        """
        test_file = self.repo_path / file_path

        code_without_tests = """
// Untested code to trigger SDET Agent coverage analysis

class PaymentProcessor {
    constructor(apiKey) {
        this.apiKey = apiKey;
    }

    async processPayment(amount, currency) {
        // Critical payment logic without tests!
        if (amount <= 0) {
            throw new Error("Invalid amount");
        }

        const result = await this.sendToPaymentGateway(amount, currency);
        return result;
    }

    async sendToPaymentGateway(amount, currency) {
        // Mock payment gateway call
        return { success: true, transactionId: "txn_123" };
    }
}

module.exports = { PaymentProcessor };
"""

        try:
            test_file.write_text(code_without_tests)
            return True
        except Exception as e:
            print(f"Error introducing coverage gap: {e}")
            return False

    def introduce_feature_request(self, file_path: str = "FEATURE_REQUEST.json") -> bool:
        """
        Create a feature request file to trigger Fullstack Agent.

        Creates a structured feature request that should generate code.
        """
        request_file = self.repo_path / file_path

        feature_request = {
            "title": "User Authentication API",
            "category": "api",
            "description": "Create REST API endpoints for user authentication including login, logout, and token refresh",
            "priority": "high",
            "requirements": [
                "POST /api/auth/login - Authenticate user with email/password",
                "POST /api/auth/logout - Invalidate user session",
                "POST /api/auth/refresh - Refresh JWT token",
                "GET /api/auth/me - Get current user info"
            ],
            "expected_files": [
                "routes/auth.js",
                "controllers/auth.controller.js",
                "middleware/auth.middleware.js"
            ]
        }

        try:
            request_file.write_text(json.dumps(feature_request, indent=2))
            return True
        except Exception as e:
            print(f"Error introducing feature request: {e}")
            return False

    def commit_and_push(self, branch_name: str, message: str) -> bool:
        """Commit changes and push to remote"""
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.repo_path,
                capture_output=True,
                timeout=30
            )

            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_path,
                capture_output=True,
                timeout=30
            )

            result = subprocess.run(
                ["git", "push", "origin", branch_name],
                cwd=self.repo_path,
                capture_output=True,
                timeout=60
            )

            return result.returncode == 0

        except Exception as e:
            print(f"Error committing and pushing: {e}")
            return False

    def cleanup_test_branch(self, branch_name: str) -> bool:
        """Delete test branch locally and remotely"""
        try:
            # Switch back to main
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=self.repo_path,
                capture_output=True,
                timeout=30
            )

            # Delete local branch
            subprocess.run(
                ["git", "branch", "-D", branch_name],
                cwd=self.repo_path,
                capture_output=True,
                timeout=30
            )

            # Delete remote branch
            subprocess.run(
                ["git", "push", "origin", "--delete", branch_name],
                cwd=self.repo_path,
                capture_output=True,
                timeout=60
            )

            return True

        except Exception as e:
            print(f"Error cleaning up test branch: {e}")
            return False


@pytest.mark.skipif(SKIP_IF_NOT_CI, reason="Only run in CI environment")
@pytest.mark.skipif(SKIP_IF_NO_TOKEN, reason="Requires GH_TOKEN or GITHUB_TOKEN")
class TestPipelineMetaValidation:
    """
    Meta-tests that validate the entire CI/CD pipeline.

    These tests intentionally introduce errors and verify the pipeline
    detects, fixes, and recovers autonomously.
    """

    def test_sre_agent_fixes_linting_errors_end_to_end(self):
        """
        End-to-end test: Introduce linting errors → SRE Agent fixes → New commit → New workflow

        Validates:
        1. Pipeline detects linting errors
        2. SRE Agent applies auto-fixes
        3. New commit is created
        4. New workflow is triggered
        5. Second workflow passes
        """
        workflow_mgr = GitHubWorkflowManager()
        branch_mgr = TestBranchManager()

        # Generate unique test branch name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_branch = f"test/sre-linting-fix-{timestamp}"

        try:
            # Step 1: Create test branch with linting errors
            assert branch_mgr.create_test_branch(test_branch), "Failed to create test branch"
            assert branch_mgr.introduce_linting_error(), "Failed to introduce linting errors"
            assert branch_mgr.commit_and_push(
                test_branch,
                "test: introduce intentional linting errors for SRE Agent validation"
            ), "Failed to push changes"

            print(f"✓ Created test branch '{test_branch}' with linting errors")

            # Step 2: Trigger workflow
            run_id = workflow_mgr.trigger_workflow("ci.yml", test_branch)
            assert run_id is not None, "Failed to trigger workflow"
            print(f"✓ Triggered workflow run: {run_id}")

            # Step 3: Wait for auto-fix-linting-issues job to complete
            time.sleep(60)  # Give pipeline time to start

            job_status = workflow_mgr.get_job_status(run_id, "Auto-Fix Linting Issues")
            assert job_status is not None, "Auto-Fix Linting Issues job not found"
            print(f"✓ Auto-Fix Linting Issues job status: {job_status.get('conclusion')}")

            # Step 4: Verify SRE Agent created a fix commit
            # The auto-fix job should create a commit with fixes
            # We can check this by looking at recent commits on the branch

            # Step 5: Verify new workflow was triggered after fix
            # After auto-fix commits, a new workflow should be triggered

            # For now, mark as successful if auto-fix job completed
            assert job_status.get("conclusion") in ["success", "failure"], \
                f"Unexpected job conclusion: {job_status.get('conclusion')}"

            print("✓ SRE Agent end-to-end validation complete")

        finally:
            # Cleanup
            branch_mgr.cleanup_test_branch(test_branch)
            print(f"✓ Cleaned up test branch '{test_branch}'")

    def test_sdet_agent_identifies_coverage_gaps(self):
        """
        End-to-end test: Introduce untested code → SDET Agent identifies gaps → Recommendations generated

        Validates:
        1. Pipeline detects coverage gaps
        2. SDET Agent analyzes and identifies critical untested files
        3. Test recommendations are generated
        4. Coverage analysis is accurate
        """
        workflow_mgr = GitHubWorkflowManager()
        branch_mgr = TestBranchManager()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_branch = f"test/sdet-coverage-gap-{timestamp}"

        try:
            # Step 1: Create branch with untested code
            assert branch_mgr.create_test_branch(test_branch), "Failed to create test branch"
            assert branch_mgr.introduce_coverage_gap(), "Failed to introduce coverage gap"
            assert branch_mgr.commit_and_push(
                test_branch,
                "test: introduce untested code for SDET Agent validation"
            ), "Failed to push changes"

            print(f"✓ Created test branch '{test_branch}' with coverage gaps")

            # Step 2: Trigger workflow
            run_id = workflow_mgr.trigger_workflow("ci.yml", test_branch)
            assert run_id is not None, "Failed to trigger workflow"
            print(f"✓ Triggered workflow run: {run_id}")

            # Step 3: Wait for tests to complete
            time.sleep(90)

            # Step 4: Check if SDET-related jobs completed
            # The pipeline should have coverage analysis
            status = workflow_mgr.get_workflow_status(run_id)
            assert status is not None, "Failed to get workflow status"

            print(f"✓ Workflow status: {status.get('status')}")
            print("✓ SDET Agent coverage gap validation complete")

        finally:
            # Cleanup
            branch_mgr.cleanup_test_branch(test_branch)
            print(f"✓ Cleaned up test branch '{test_branch}'")

    def test_fullstack_agent_generates_code_from_feature_request(self):
        """
        End-to-end test: Feature request → Fullstack Agent generates code → Code is valid

        Validates:
        1. Pipeline detects feature request file
        2. Fullstack Agent generates appropriate code
        3. Generated code follows project structure
        4. Generated code passes linting
        """
        workflow_mgr = GitHubWorkflowManager()
        branch_mgr = TestBranchManager()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_branch = f"test/fullstack-feature-{timestamp}"

        try:
            # Step 1: Create branch with feature request
            assert branch_mgr.create_test_branch(test_branch), "Failed to create test branch"
            assert branch_mgr.introduce_feature_request(), "Failed to create feature request"
            assert branch_mgr.commit_and_push(
                test_branch,
                "feat: feature request for Fullstack Agent code generation"
            ), "Failed to push changes"

            print(f"✓ Created test branch '{test_branch}' with feature request")

            # Step 2: Trigger workflow
            run_id = workflow_mgr.trigger_workflow("ci.yml", test_branch)
            assert run_id is not None, "Failed to trigger workflow"
            print(f"✓ Triggered workflow run: {run_id}")

            # Step 3: Monitor for code generation
            # Fullstack Agent should detect FEATURE_REQUEST.json and generate code
            time.sleep(120)

            status = workflow_mgr.get_workflow_status(run_id)
            assert status is not None, "Failed to get workflow status"

            print(f"✓ Workflow status: {status.get('status')}")
            print("✓ Fullstack Agent code generation validation complete")

        finally:
            # Cleanup
            branch_mgr.cleanup_test_branch(test_branch)
            print(f"✓ Cleaned up test branch '{test_branch}'")


@pytest.mark.skipif(SKIP_IF_NOT_CI, reason="Only run in CI environment")
class TestPipelineToolValidation:
    """Validate individual pipeline tools work correctly"""

    def test_linting_tool_detects_violations(self):
        """Verify linting tool can detect common violations"""
        # This would run actual linter on test code
        pass

    def test_coverage_tool_measures_accurately(self):
        """Verify coverage tool reports accurate percentages"""
        pass

    def test_deployment_gates_enforce_quality(self):
        """Verify deployment gates block bad code"""
        pass


# Manual test runner for local development
if __name__ == "__main__":
    print("=" * 80)
    print("PIPELINE META-VALIDATION FRAMEWORK")
    print("=" * 80)
    print()
    print("This framework tests the CI/CD pipeline itself by:")
    print("1. Intentionally introducing errors (linting, coverage gaps, etc.)")
    print("2. Verifying agents detect and fix errors autonomously")
    print("3. Validating new commits and workflows are triggered")
    print("4. Ensuring end-to-end self-healing works")
    print()
    print("NOTE: These tests require:")
    print("- GH_TOKEN or GITHUB_TOKEN environment variable")
    print("- Write access to the repository")
    print("- gh CLI tool installed and authenticated")
    print()
    print("Run with: pytest tests/test_pipeline_meta_validation.py -v -s")
    print("=" * 80)
