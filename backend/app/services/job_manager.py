"""
Job State Management Service

Manages background job state for unified document processing pipeline.
Provides CRUD operations for job tracking, progress updates, and result storage.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum


class JobStatus(str, Enum):
    """Job execution status states"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStep(str, Enum):
    """Pipeline processing steps"""
    PARSE = "parse"
    EXTRACT = "extract"
    NORMALIZE = "normalize"
    MAP = "map"
    CALCULATE = "calculate"
    DONE = "done"


class JobManager:
    """
    Manages job state persistence and retrieval.

    Jobs are stored as JSON files in backend/data/jobs/
    Each job tracks: status, progress, current step, results, errors
    """

    def __init__(self, jobs_dir: str = None):
        """
        Initialize job manager.

        Args:
            jobs_dir: Directory to store job state files (default: backend/data/jobs/)
        """
        if jobs_dir is None:
            # Default to backend/data/jobs/
            base_dir = Path(__file__).parent.parent.parent / "data" / "jobs"
        else:
            base_dir = Path(jobs_dir)

        self.jobs_dir = base_dir
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def create_job(
        self,
        job_id: str,
        document_id: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new job with initial state.

        Args:
            job_id: Unique job identifier
            document_id: Document being processed
            options: Processing options (normalize_method, save_intermediate_steps, etc.)

        Returns:
            Job state dictionary
        """
        job_state = {
            "job_id": job_id,
            "document_id": document_id,
            "status": JobStatus.PENDING,
            "current_step": None,
            "progress": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "started_at": None,
            "completed_at": None,
            "options": options or {},
            "results": {},
            "errors": [],
            "step_timings": {}
        }

        self._save_job(job_id, job_state)
        return job_state

    def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        current_step: Optional[JobStep] = None,
        progress: Optional[int] = None,
        results: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None,
        step_timing: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Update job state.

        Args:
            job_id: Job identifier
            status: New status
            current_step: Current processing step
            progress: Progress percentage (0-100)
            results: Partial or complete results to merge
            error: Error details to append
            step_timing: Step timing to record (e.g., {"parse": 2.5})

        Returns:
            Updated job state
        """
        job_state = self.get_job(job_id)

        if job_state is None:
            raise ValueError(f"Job {job_id} not found")

        # Update fields
        if status is not None:
            job_state["status"] = status

            # Track started_at and completed_at
            if status == JobStatus.PROCESSING and job_state["started_at"] is None:
                job_state["started_at"] = datetime.utcnow().isoformat()
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                job_state["completed_at"] = datetime.utcnow().isoformat()

        if current_step is not None:
            job_state["current_step"] = current_step

        if progress is not None:
            job_state["progress"] = progress

        if results is not None:
            job_state["results"].update(results)

        if error is not None:
            job_state["errors"].append({
                **error,
                "timestamp": datetime.utcnow().isoformat()
            })

        if step_timing is not None:
            job_state["step_timings"].update(step_timing)

        job_state["updated_at"] = datetime.utcnow().isoformat()

        self._save_job(job_id, job_state)
        return job_state

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve job state.

        Args:
            job_id: Job identifier

        Returns:
            Job state dictionary or None if not found
        """
        job_file = self.jobs_dir / f"{job_id}.json"

        if not job_file.exists():
            return None

        with open(job_file, 'r') as f:
            return json.load(f)

    def list_jobs(
        self,
        document_id: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List jobs with optional filters.

        Args:
            document_id: Filter by document ID
            status: Filter by status
            limit: Maximum number of jobs to return

        Returns:
            List of job state dictionaries, sorted by created_at desc
        """
        jobs = []

        for job_file in self.jobs_dir.glob("*.json"):
            with open(job_file, 'r') as f:
                job = json.load(f)

                # Apply filters
                if document_id and job.get("document_id") != document_id:
                    continue
                if status and job.get("status") != status:
                    continue

                jobs.append(job)

        # Sort by created_at descending
        jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return jobs[:limit]

    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job.

        Args:
            job_id: Job identifier

        Returns:
            True if deleted, False if not found
        """
        job_file = self.jobs_dir / f"{job_id}.json"

        if job_file.exists():
            job_file.unlink()
            return True

        return False

    def cancel_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Mark a job as cancelled.

        Note: This only updates the status. The actual background task
        should check job status periodically and stop if cancelled.

        Args:
            job_id: Job identifier

        Returns:
            Updated job state or None if not found
        """
        job_state = self.get_job(job_id)

        if job_state is None:
            return None

        # Only cancel if in pending or processing state
        if job_state["status"] in [JobStatus.PENDING, JobStatus.PROCESSING]:
            return self.update_job(
                job_id,
                status=JobStatus.CANCELLED,
                error={
                    "step": job_state.get("current_step", "unknown"),
                    "message": "Job cancelled by user"
                }
            )

        return job_state

    def _save_job(self, job_id: str, job_state: Dict[str, Any]) -> None:
        """
        Persist job state to disk.

        Args:
            job_id: Job identifier
            job_state: Job state dictionary
        """
        job_file = self.jobs_dir / f"{job_id}.json"

        # Convert Enums to their string values for JSON serialization
        serializable_state = self._serialize_job_state(job_state)

        with open(job_file, 'w') as f:
            json.dump(serializable_state, f, indent=2)

    def _serialize_job_state(self, job_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Enum values to strings for JSON serialization.

        Args:
            job_state: Job state dictionary potentially containing Enums

        Returns:
            Dictionary with Enums converted to strings
        """
        serializable = {}
        for key, value in job_state.items():
            if isinstance(value, Enum):
                serializable[key] = value.value
            elif isinstance(value, dict):
                serializable[key] = self._serialize_job_state(value)
            elif isinstance(value, list):
                serializable[key] = [
                    item.value if isinstance(item, Enum) else item
                    for item in value
                ]
            else:
                serializable[key] = value
        return serializable

    def cleanup_old_jobs(self, days: int = 7) -> int:
        """
        Delete jobs older than specified days.

        Args:
            days: Delete jobs older than this many days

        Returns:
            Number of jobs deleted
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = 0

        for job_file in self.jobs_dir.glob("*.json"):
            with open(job_file, 'r') as f:
                job = json.load(f)
                created_at = datetime.fromisoformat(job.get("created_at", ""))

                if created_at < cutoff:
                    job_file.unlink()
                    deleted += 1

        return deleted


# Global job manager instance
_job_manager = None

def get_job_manager() -> JobManager:
    """
    Get global job manager instance (singleton pattern).

    Returns:
        JobManager instance
    """
    global _job_manager

    if _job_manager is None:
        _job_manager = JobManager()

    return _job_manager
