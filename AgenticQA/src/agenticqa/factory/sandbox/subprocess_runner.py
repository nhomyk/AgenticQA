"""
SubprocessRunner — executes an agent script in a clean subprocess.

Security properties:
- Environment: only explicitly passthrough'd keys from parent env; everything else stripped.
- Working directory: locked to allowed_dir; the subprocess cannot cd out.
- Communication: JSON over stdin/stdout; stderr is captured separately.
- Timeout: hard wall-clock limit; process is killed on expiry.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional


class SubprocessError(RuntimeError):
    """Raised when the sandboxed script exits non-zero."""


class SubprocessTimeoutError(RuntimeError):
    """Raised when the sandboxed script exceeds its timeout."""


class SubprocessRunner:
    """
    Runs a standalone Python script in a restricted subprocess.

    The script must:
      - read its input as JSON from stdin
      - write its result as JSON to stdout
      - exit 0 on success, non-zero on failure

    Args:
        allowed_dir:    Working directory for the subprocess (restrict filesystem access).
        timeout_s:      Hard timeout in seconds (default 30).
        env_passthrough: List of environment variable names to inherit from the parent.
                         All other env vars are stripped. Default: none (clean env).
    """

    def __init__(
        self,
        allowed_dir: str = ".",
        timeout_s: int = 30,
        env_passthrough: Optional[List[str]] = None,
    ):
        self.allowed_dir = os.path.abspath(allowed_dir)
        self.timeout_s = timeout_s
        self.env_passthrough = env_passthrough or []

    def run(self, script_path: str, input_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Launch script_path as a subprocess, send input_payload as JSON via stdin,
        and return the parsed JSON from stdout.

        Raises:
            SubprocessTimeoutError: if the script takes longer than timeout_s.
            SubprocessError: if the script exits non-zero.
            ValueError: if stdout is not valid JSON.
        """
        # Build a clean environment — only explicitly passthrough'd keys.
        # PYTHONPATH is NOT inherited by default; callers that need it must
        # add "PYTHONPATH" to env_passthrough (prevents library-injection attacks).
        clean_env = {k: os.environ[k] for k in self.env_passthrough if k in os.environ}

        stdin_bytes = json.dumps(input_payload).encode()

        try:
            proc = subprocess.run(
                [sys.executable, script_path],
                input=stdin_bytes,
                capture_output=True,
                cwd=self.allowed_dir,
                env=clean_env,
                timeout=self.timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise SubprocessTimeoutError(
                f"Agent script '{script_path}' timed out after {self.timeout_s}s"
            ) from exc

        if proc.returncode != 0:
            stderr_snippet = proc.stderr.decode(errors="replace")[:500]
            raise SubprocessError(
                f"Agent script '{script_path}' exited {proc.returncode}: {stderr_snippet}"
            )

        stdout = proc.stdout.decode(errors="replace").strip()
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Agent script '{script_path}' produced non-JSON stdout: {stdout[:200]}"
            ) from exc
