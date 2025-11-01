"""
Simple in-memory job queue for async processing

Provides a lightweight job queue system without requiring Redis/Celery.
For production, consider migrating to Celery + Redis.
"""

import uuid
import asyncio
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import deque
import threading
from .logging import get_logger

logger = get_logger('pipeline.job_queue')


class JobStatus(Enum):
    """Job processing status"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Represents a processing job"""
    job_id: str
    job_type: str  # 'process_episode', 'render_clips', etc.
    parameters: Dict[str, Any]
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0
    current_stage: str = "queued"
    message: str = "Job queued"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    webhook_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary"""
        return {
            'job_id': self.job_id,
            'job_type': self.job_type,
            'parameters': self.parameters,
            'status': self.status.value,
            'progress': self.progress,
            'current_stage': self.current_stage,
            'message': self.message,
            'result': self.result,
            'error': self.error,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'eta_seconds': self.estimate_remaining_time()
        }
    
    def estimate_remaining_time(self) -> Optional[float]:
        """Estimate remaining time based on progress"""
        if self.status == JobStatus.COMPLETED:
            return 0.0
        
        if not self.started_at or self.progress <= 0:
            return None
        
        elapsed = (datetime.now() - self.started_at).total_seconds()
        if self.progress > 0:
            total_estimated = elapsed / (self.progress / 100.0)
            remaining = total_estimated - elapsed
            return max(0, remaining)
        
        return None


class JobQueue:
    """
    Simple in-memory job queue
    
    Manages async job processing with status tracking and progress updates.
    Thread-safe for concurrent access.
    """
    
    def __init__(self, max_workers: int = 2):
        """
        Initialize job queue
        
        Args:
            max_workers: Maximum number of concurrent jobs
        """
        self.max_workers = max_workers
        self.jobs: Dict[str, Job] = {}
        self.queue: deque = deque()
        self.running_jobs: Dict[str, Job] = {}
        self.lock = threading.Lock()
        self.workers_running = False
        
        logger.info(f"Job queue initialized with {max_workers} workers")
    
    def submit_job(
        self,
        job_type: str,
        parameters: Dict[str, Any],
        webhook_url: Optional[str] = None
    ) -> str:
        """
        Submit a new job to the queue
        
        Args:
            job_type: Type of job ('process_episode', 'render_clips', etc.)
            parameters: Job parameters
            webhook_url: Optional webhook URL for notifications
            
        Returns:
            str: Job ID
        """
        job_id = str(uuid.uuid4())
        
        job = Job(
            job_id=job_id,
            job_type=job_type,
            parameters=parameters,
            webhook_url=webhook_url
        )
        
        with self.lock:
            self.jobs[job_id] = job
            self.queue.append(job_id)
        
        logger.info(f"Job submitted: {job_id} ({job_type})")
        
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        with self.lock:
            return self.jobs.get(job_id)
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status as dictionary"""
        job = self.get_job(job_id)
        return job.to_dict() if job else None
    
    def update_job_progress(
        self,
        job_id: str,
        progress: float,
        stage: str,
        message: str
    ):
        """Update job progress"""
        with self.lock:
            job = self.jobs.get(job_id)
            if job:
                job.progress = progress
                job.current_stage = stage
                job.message = message
                logger.debug(f"Job {job_id} progress: {progress}% - {stage}")
    
    def mark_job_running(self, job_id: str):
        """Mark job as running"""
        with self.lock:
            job = self.jobs.get(job_id)
            if job:
                job.status = JobStatus.RUNNING
                job.started_at = datetime.now()
                self.running_jobs[job_id] = job
                logger.info(f"Job started: {job_id}")
    
    def mark_job_completed(
        self,
        job_id: str,
        result: Dict[str, Any]
    ):
        """Mark job as completed"""
        with self.lock:
            job = self.jobs.get(job_id)
            if job:
                job.status = JobStatus.COMPLETED
                job.progress = 100.0
                job.result = result
                job.completed_at = datetime.now()
                
                if job_id in self.running_jobs:
                    del self.running_jobs[job_id]
                
                logger.info(f"Job completed: {job_id}")
                
                # Trigger webhook if configured
                if job.webhook_url:
                    self._trigger_webhook(job)
    
    def mark_job_failed(
        self,
        job_id: str,
        error: str
    ):
        """Mark job as failed"""
        with self.lock:
            job = self.jobs.get(job_id)
            if job:
                job.status = JobStatus.FAILED
                job.error = error
                job.completed_at = datetime.now()
                
                if job_id in self.running_jobs:
                    del self.running_jobs[job_id]
                
                logger.error(f"Job failed: {job_id} - {error}")
                
                # Trigger webhook if configured
                if job.webhook_url:
                    self._trigger_webhook(job)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued job"""
        with self.lock:
            job = self.jobs.get(job_id)
            if job and job.status == JobStatus.QUEUED:
                job.status = JobStatus.CANCELLED
                # Remove from queue
                try:
                    self.queue.remove(job_id)
                except ValueError:
                    pass
                logger.info(f"Job cancelled: {job_id}")
                return True
        return False
    
    def get_next_job(self) -> Optional[str]:
        """Get next job from queue"""
        with self.lock:
            # Check if we can run more jobs
            if len(self.running_jobs) >= self.max_workers:
                return None
            
            # Get next queued job
            while self.queue:
                job_id = self.queue.popleft()
                job = self.jobs.get(job_id)
                
                if job and job.status == JobStatus.QUEUED:
                    return job_id
            
            return None
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        with self.lock:
            queued = sum(1 for j in self.jobs.values() if j.status == JobStatus.QUEUED)
            running = len(self.running_jobs)
            completed = sum(1 for j in self.jobs.values() if j.status == JobStatus.COMPLETED)
            failed = sum(1 for j in self.jobs.values() if j.status == JobStatus.FAILED)
            
            return {
                'queued': queued,
                'running': running,
                'completed': completed,
                'failed': failed,
                'total': len(self.jobs),
                'max_workers': self.max_workers
            }
    
    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 50
    ) -> list[Dict[str, Any]]:
        """List jobs with optional filtering"""
        with self.lock:
            jobs = list(self.jobs.values())
            
            if status:
                jobs = [j for j in jobs if j.status == status]
            
            # Sort by created_at descending
            jobs.sort(key=lambda j: j.created_at, reverse=True)
            
            return [j.to_dict() for j in jobs[:limit]]
    
    def _trigger_webhook(self, job: Job):
        """Trigger webhook notification (async)"""
        if not job.webhook_url:
            return
        
        try:
            import requests
            import threading
            
            def send_webhook():
                try:
                    payload = job.to_dict()
                    response = requests.post(
                        job.webhook_url,
                        json=payload,
                        timeout=10
                    )
                    logger.info(f"Webhook triggered for job {job.job_id}: {response.status_code}")
                except Exception as e:
                    logger.error(f"Webhook failed for job {job.job_id}: {e}")
            
            # Send webhook in background thread
            thread = threading.Thread(target=send_webhook, daemon=True)
            thread.start()
            
        except Exception as e:
            logger.error(f"Error triggering webhook: {e}")
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove old completed/failed jobs"""
        with self.lock:
            cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
            
            jobs_to_remove = []
            for job_id, job in self.jobs.items():
                if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    if job.completed_at and job.completed_at.timestamp() < cutoff:
                        jobs_to_remove.append(job_id)
            
            for job_id in jobs_to_remove:
                del self.jobs[job_id]
            
            if jobs_to_remove:
                logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")


# Global job queue instance
_job_queue: Optional[JobQueue] = None


def get_job_queue(max_workers: int = 2) -> JobQueue:
    """Get or create global job queue instance"""
    global _job_queue
    
    if _job_queue is None:
        _job_queue = JobQueue(max_workers=max_workers)
    
    return _job_queue
