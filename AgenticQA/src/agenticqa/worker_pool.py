"""Background worker pool for concurrent workflow request execution.

Polls the SQLite queue for QUEUED requests, claims them atomically, and
dispatches each to a WorkflowExecutionWorker running in its own git worktree.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from typing import Any, Dict, Optional

from .workflow_requests import PromptWorkflowStore
from .workflow_worker import WorkflowExecutionWorker

logger = logging.getLogger(__name__)

_DEFAULT_MAX_WORKERS = 3
_MAX_WORKERS_CEILING = 8
_DEFAULT_POLL_INTERVAL = 2.0


class WorkerPool:
    """Threading-based pool that processes workflow requests concurrently.

    Each worker gets its own ``WorkflowExecutionWorker`` instance and runs
    ``run_request(use_worktree=True)`` so that concurrent executions never
    collide on git state.

    Configuration via environment variables:
        AGENTICQA_MAX_WORKERS       – max concurrent workers (default 3, max 8)
        AGENTICQA_WORKER_POLL_INTERVAL – seconds between queue polls (default 2)
        AGENTICQA_WORKER_ENABLED    – set to "0" to disable the pool entirely
    """

    def __init__(
        self,
        store: PromptWorkflowStore,
        max_workers: Optional[int] = None,
        poll_interval: Optional[float] = None,
        dry_run: bool = True,
        open_pr: bool = True,
    ):
        self.store = store
        self.dry_run = dry_run
        self.open_pr = open_pr

        env_max = os.getenv("AGENTICQA_MAX_WORKERS")
        if max_workers is not None:
            self._max_workers = min(max(1, max_workers), _MAX_WORKERS_CEILING)
        elif env_max:
            self._max_workers = min(max(1, int(env_max)), _MAX_WORKERS_CEILING)
        else:
            self._max_workers = _DEFAULT_MAX_WORKERS

        env_interval = os.getenv("AGENTICQA_WORKER_POLL_INTERVAL")
        if poll_interval is not None:
            self._poll_interval = max(0.5, poll_interval)
        elif env_interval:
            self._poll_interval = max(0.5, float(env_interval))
        else:
            self._poll_interval = _DEFAULT_POLL_INTERVAL

        self._shutdown = threading.Event()
        self._active_workers: Dict[str, threading.Thread] = {}
        self._workers_lock = threading.Lock()
        self._poller_thread: Optional[threading.Thread] = None

    # ── Public API ───────────────────────────────────────────────────────────

    @property
    def active_count(self) -> int:
        with self._workers_lock:
            return len(self._active_workers)

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @property
    def is_running(self) -> bool:
        return self._poller_thread is not None and self._poller_thread.is_alive()

    def status(self) -> Dict[str, Any]:
        """Return a snapshot of pool status for API/dashboard."""
        queue_status = self.store.get_queue_status()
        return {
            "pool_running": self.is_running,
            "max_workers": self._max_workers,
            "active_workers": self.active_count,
            "available_slots": max(0, self._max_workers - self.active_count),
            **queue_status,
        }

    def start(self) -> None:
        """Start the background poller thread."""
        if self._shutdown.is_set():
            self._shutdown.clear()
        if self._poller_thread and self._poller_thread.is_alive():
            logger.warning("worker pool already running")
            return

        self._poller_thread = threading.Thread(
            target=self._poll_loop,
            name="agenticqa-pool-poller",
            daemon=True,
        )
        self._poller_thread.start()
        logger.info(
            "worker pool started: max_workers=%d, poll_interval=%.1fs",
            self._max_workers,
            self._poll_interval,
        )

    def stop(self, timeout: float = 120.0) -> None:
        """Signal shutdown and wait for active workers to finish."""
        self._shutdown.set()
        logger.info("worker pool shutdown requested, waiting for active workers...")

        # Wait for active workers
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._workers_lock:
                alive = [t for t in self._active_workers.values() if t.is_alive()]
            if not alive:
                break
            time.sleep(0.5)

        with self._workers_lock:
            still_running = [wid for wid, t in self._active_workers.items() if t.is_alive()]
        if still_running:
            logger.warning("workers still running after timeout: %s", still_running)
        else:
            logger.info("all workers stopped cleanly")

        if self._poller_thread and self._poller_thread.is_alive():
            self._poller_thread.join(timeout=5.0)

    # ── Internal ─────────────────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        """Main poller loop — runs as a daemon thread."""
        while not self._shutdown.is_set():
            try:
                self._reap_finished()
                available = self._max_workers - self.active_count
                if available <= 0:
                    self._shutdown.wait(self._poll_interval)
                    continue

                # Try to pick up work
                for _ in range(available):
                    if self._shutdown.is_set():
                        return
                    worker_id = f"w_{uuid.uuid4().hex[:8]}"
                    req = self.store.atomic_pickup(worker_id)
                    if not req:
                        break  # Queue empty
                    self._spawn_worker(worker_id, req)

            except Exception:
                logger.exception("error in pool poller loop")

            self._shutdown.wait(self._poll_interval)

    def _spawn_worker(self, worker_id: str, req: Dict[str, Any]) -> None:
        """Launch a worker thread for a claimed request."""
        request_id = req["id"]
        thread = threading.Thread(
            target=self._worker_run,
            args=(worker_id, request_id),
            name=f"agenticqa-worker-{worker_id}",
            daemon=True,
        )
        with self._workers_lock:
            self._active_workers[worker_id] = thread
        thread.start()
        logger.info("spawned worker %s for request %s", worker_id, request_id)

    def _worker_run(self, worker_id: str, request_id: str) -> None:
        """Execute a single request in an isolated worktree."""
        try:
            worker = WorkflowExecutionWorker(store=self.store)
            worker.run_request(
                request_id=request_id,
                dry_run=self.dry_run,
                open_pr=self.open_pr,
                use_worktree=True,
                worker_id=worker_id,
            )
            logger.info("worker %s completed request %s", worker_id, request_id)
        except Exception:
            logger.exception("worker %s failed on request %s", worker_id, request_id)
        finally:
            with self._workers_lock:
                self._active_workers.pop(worker_id, None)

    def _reap_finished(self) -> None:
        """Remove finished threads from the active set."""
        with self._workers_lock:
            finished = [wid for wid, t in self._active_workers.items() if not t.is_alive()]
            for wid in finished:
                del self._active_workers[wid]
