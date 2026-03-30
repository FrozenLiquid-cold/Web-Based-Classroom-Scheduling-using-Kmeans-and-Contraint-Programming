"""Simple in-process task queue for scheduling jobs (per-college FIFO)."""
import threading
import time
import uuid
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, Tuple

from .db import SessionLocal
from .scheduler.scheduler import run_scheduler


class JobRecord:
    def __init__(self, key: str, payload: Dict[str, Any]):
        self.id = str(uuid.uuid4())
        self.key = key
        self.payload = payload
        self.status = "pending"  # pending | running | succeeded | failed
        self.status_message = "Queued, waiting to start..."  # Detailed progress message
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        # Progressive phase updates
        self.partial_items: list = []  # Items scheduled so far
        self.current_phase: str = ""  # e.g. "PE/PATHFIT", "MAJORS", "GE/MINORS"
        self.total_subjects: int = 0  # Total subjects to schedule


class QueueManager:
    """
    Lightweight per-key FIFO queue that offloads heavy scheduling work
    to a dedicated thread pool so FastAPI request handlers return quickly.
    """

    def __init__(self, max_workers: int = 2):
        self.queues: Dict[str, deque] = defaultdict(deque)
        self.jobs: Dict[str, JobRecord] = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    # ------------------------------------------------------------------#
    # Public API
    # ------------------------------------------------------------------#
    def enqueue(self, key: str, payload: Dict[str, Any]) -> Tuple[str, bool]:
        """
        Queue a job; dedupe identical payloads for the same key if they are
        pending or running. Returns (job_id, already_queued_flag).
        """
        with self.lock:
            for job in self.jobs.values():
                if job.key == key and job.status in ("pending", "running"):
                    if job.payload == payload:
                        return job.id, True

            job = JobRecord(key, payload)
            self.jobs[job.id] = job
            self.queues[key].append(job)
            self._start_worker_if_needed(key)
            return job.id, False

    def get_status(self, job_id: str) -> Dict[str, Any]:
        job = self.jobs.get(job_id)
        if not job:
            return {"status": "not_found"}
        return {
            "job_id": job.id,
            "status": job.status,
            "status_message": job.status_message,
            "error": job.error,
            "result": job.result,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "partial_items": job.partial_items,
            "current_phase": job.current_phase,
            "total_subjects": job.total_subjects,
        }
    
    def update_status_message(self, job_id: str, message: str) -> None:
        """Update the detailed status message for a running job."""
        job = self.jobs.get(job_id)
        if job:
            job.status_message = message
    
    def find_active_job_for_course(self, course_id: int, semester: int) -> Optional[str]:
        """
        Find an active (pending or running) job for a given course and semester.
        Returns the job_id if found, None otherwise.
        """
        with self.lock:
            for job in self.jobs.values():
                if job.status in ("pending", "running"):
                    payload = job.payload
                    if (payload.get("course_id") == course_id and 
                        payload.get("semester") == semester):
                        return job.id
        return None

    # ------------------------------------------------------------------#
    # Internal helpers
    # ------------------------------------------------------------------#
    def _start_worker_if_needed(self, key: str) -> None:
        """
        Launch a background future for this key if it isn’t already processing.
        """
        if getattr(self, "_active_workers", None) is None:
            self._active_workers = {}
        if key in self._active_workers:
            return
        future = self.executor.submit(self._worker_loop, key)
        self._active_workers[key] = future

    def _worker_loop(self, key: str) -> None:
        """
        Drain the per-key queue in FIFO order. Each job is executed with
        its own SQLAlchemy session and OR-Tools invocation.
        """
        while True:
            with self.lock:
                if not self.queues[key]:
                    self._active_workers.pop(key, None)
                    return
                job: JobRecord = self.queues[key].popleft()

            job.status = "running"
            job.status_message = "Initializing scheduler..."
            job.started_at = time.time()

            try:
                db = SessionLocal()
                try:
                    requested_year = job.payload.get("year")
                    try:
                        year_value = int(requested_year) if requested_year is not None else 1
                    except (TypeError, ValueError):
                        year_value = 1

                    # Create a progress callback that updates the job's status message
                    def progress_callback(message: str) -> None:
                        job.status_message = message

                    # Create a phase callback for progressive timetable updates
                    def phase_callback(phase_name: str, items_so_far: list, total_subjects: int) -> None:
                        job.current_phase = phase_name
                        job.partial_items = list(items_so_far)  # Copy to avoid mutation
                        job.total_subjects = total_subjects

                    items, diagnostics = run_scheduler(
                        db=db,
                        course_id=job.payload["course_id"],
                        year=year_value,
                        years=job.payload.get("years"),
                        semester=job.payload["semester"],
                        subject_ids=job.payload.get("subject_ids"),
                        use_cp=True,
                        max_time_seconds=job.payload.get("max_time_seconds", 120.0),
                        use_kmeans=job.payload.get("use_kmeans", True),
                        k_clusters=job.payload.get("k_clusters", 3),
                        weight_slots=job.payload.get("weight_slots", 2.0),
                        force_refit=job.payload.get("force_refit", False),
                        block_capacity_overrides=job.payload.get("block_capacities"),
                        blocks_count=job.payload.get("blocks_count"),
                        progress_callback=progress_callback,
                        phase_callback=phase_callback,
                    )
                    job.result = {"items": items, "count": len(items), "diagnostics": diagnostics}
                    job.status_message = f"Completed! Scheduled {len(items)} items."
                    
                    # Note: Schedule is NOT automatically saved - user must click "Save" button
                    # to persist it to the database. This allows users to regenerate if needed.
                    
                    job.status = "succeeded"
                finally:
                    db.close()
            except Exception as exc:  # noqa: BLE001
                job.error = str(exc)
                job.status_message = f"Failed: {str(exc)[:100]}"
                job.status = "failed"
            finally:
                job.finished_at = time.time()

# Singleton manager
queue_manager = QueueManager()


