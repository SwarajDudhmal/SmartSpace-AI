"""Bounded background work for the single-process SmartSpace demo server.

Heavy requests return HTTP 202 immediately. A random, unguessable status URL
acts as a bearer capability; clients must keep it private. Completed results
expire after five minutes. For multiple server processes, use a shared external
task queue/result store instead of this process-local executor.
"""

import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from flask import Blueprint, current_app, jsonify, url_for
from werkzeug.exceptions import HTTPException

jobs_bp = Blueprint("jobs", __name__)


class JobQueue:
    """Serialize model work and bound both pending jobs and retained results."""

    def __init__(self, max_pending=4, max_results=32, retention_seconds=300):
        """Initialize limits and a single model worker; no work starts yet."""
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="smartspace-ai")
        self.max_pending = max_pending
        self.max_results = max_results
        self.retention_seconds = retention_seconds
        self.jobs = {}
        self.lock = Lock()

    def _prune(self):
        """Expire completed results; caller must hold the queue lock."""
        now = time.monotonic()
        expired = [job_id for job_id, job in self.jobs.items()
                   if job["finished_at"] is not None
                   and now - job["finished_at"] > self.retention_seconds]
        for job_id in expired:
            del self.jobs[job_id]

    def submit(self, app, function, *args, **kwargs):
        """Return a status capability or None if pending/result capacity is full."""
        with self.lock:
            self._prune()
            pending_count = sum(not job["future"].done() for job in self.jobs.values())
            if pending_count >= self.max_pending:
                return None
            if len(self.jobs) >= self.max_results:
                completed = [key for key, job in self.jobs.items() if job["finished_at"] is not None]
                if not completed:
                    return None
                oldest = min(completed, key=lambda key: self.jobs[key]["finished_at"])
                del self.jobs[oldest]
            job_id = secrets.token_urlsafe(32)
            job = {"finished_at": None}
            future = self.executor.submit(self._run, app, function, args, kwargs)
            job["future"] = future
            self.jobs[job_id] = job
        # Register outside the lock: a completed Future runs callbacks inline.
        future.add_done_callback(lambda _: self._finish(job_id))
        return job_id

    def _finish(self, job_id):
        """Timestamp job completion so retained results have a bounded lifetime."""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]["finished_at"] = time.monotonic()

    @staticmethod
    def _run(app, function, args, kwargs):
        """Execute detached inputs under an app context; return a JSON response."""
        with app.app_context():
            try:
                return app.make_response(function(*args, **kwargs))
            except (ValueError, TypeError, KeyError) as error:
                app.logger.warning("Invalid AI task input: %s", error)
                return app.make_response((jsonify(success=False, error="Invalid room or image input."), 400))
            except HTTPException as error:
                return app.make_response((jsonify(success=False, error=error.description), error.code))
            except Exception:
                app.logger.exception("Background AI task failed")
                return app.make_response((jsonify(success=False, error="Could not prepare this design. Please retry."), 500))

    def get(self, job_id):
        """Return a job record for its capability, or None if absent/expired."""
        with self.lock:
            self._prune()
            return self.jobs.get(job_id)

    def shutdown(self):
        """Finish running work and cancel queued tasks when shutting down tests."""
        self.executor.shutdown(wait=True, cancel_futures=True)


def submit_work(function, *args, **kwargs):
    """Detach a computation from the request; return 202 or bounded-queue 503."""
    app = current_app._get_current_object()
    queue = app.extensions["ai_jobs"]
    job_id = queue.submit(app, function, *args, **kwargs)
    if job_id is None:
        return jsonify(success=False, error="The design service is busy. Please retry shortly."), 503, {"Retry-After": "2"}
    status_url = url_for("jobs.job_status", job_id=job_id)
    return jsonify(success=True, status="pending", status_url=status_url), 202, {
        "Location": status_url, "Retry-After": "1", "Cache-Control": "no-store",
    }


@jobs_bp.get("/api/jobs/<job_id>")
def job_status(job_id):
    """Return pending status or the original JSON result for a private job URL."""
    job = current_app.extensions["ai_jobs"].get(job_id)
    if job is None:
        return jsonify(success=False, error="This task expired or the server restarted. Please retry."), 404
    future = job["future"]
    if not future.done():
        return jsonify(success=True, status="running" if future.running() else "pending"), 202, {
            "Retry-After": "1", "Cache-Control": "no-store",
        }
    response = future.result()
    response.headers["Cache-Control"] = "no-store"
    return response
