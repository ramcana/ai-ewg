"""
Async processing endpoint for n8n integration
Accepts processing requests and returns immediately while processing in background
"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import BackgroundTasks, HTTPException
from pydantic import BaseModel, HttpUrl
import httpx

from ..core import get_logger
from ..core.models import ProcessingStage

logger = get_logger('pipeline.api.async')

# In-memory job tracking (in production, use Redis or database)
active_jobs: Dict[str, Dict[str, Any]] = {}


class AsyncProcessRequest(BaseModel):
    """Request model for async processing"""
    episode_id: str
    video_path: str
    target_stage: str = "rendered"
    force_reprocess: bool = False
    callback_url: Optional[HttpUrl] = None


class AsyncProcessResponse(BaseModel):
    """Response model for async processing"""
    job_id: str
    episode_id: str
    status: str
    message: str
    submitted_at: str


async def process_episode_async(
    job_id: str,
    episode_id: str,
    video_path: str,
    target_stage: str,
    force_reprocess: bool,
    callback_url: Optional[str],
    orchestrator
):
    """
    Process episode in background and call webhook when complete
    
    Args:
        job_id: Unique job identifier
        episode_id: Episode ID
        video_path: Path to video file
        target_stage: Target processing stage
        force_reprocess: Force reprocessing
        callback_url: Webhook URL to call when complete
        orchestrator: Pipeline orchestrator instance
    """
    start_time = datetime.now()
    
    try:
        logger.info(f"Starting async processing for job {job_id}", 
                   episode_id=episode_id,
                   job_id=job_id)
        
        # Update job status
        active_jobs[job_id] = {
            "status": "processing",
            "episode_id": episode_id,
            "started_at": start_time.isoformat()
        }
        
        # Process the episode
        result = await orchestrator.process_episode(
            episode_id=episode_id,
            video_path=video_path,
            target_stage=ProcessingStage(target_stage),
            force_reprocess=force_reprocess
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Prepare callback payload
        callback_payload = {
            "job_id": job_id,
            "episode_id": episode_id,
            "filename": video_path.split('/')[-1],
            "status": "success" if result.get("success") else "failed",
            "stage": result.get("stage", "unknown"),
            "duration": duration,
            "error": result.get("error"),
            "metrics": result.get("metrics")
        }
        
        # Update job status
        active_jobs[job_id] = {
            "status": "completed",
            "episode_id": episode_id,
            "result": callback_payload,
            "completed_at": datetime.now().isoformat()
        }
        
        logger.info(f"Completed async processing for job {job_id}",
                   episode_id=episode_id,
                   job_id=job_id,
                   duration=duration,
                   success=result.get("success"))
        
        # Call webhook if provided
        if callback_url:
            await send_webhook_notification(callback_url, callback_payload)
        
    except Exception as e:
        logger.error(f"Error in async processing for job {job_id}",
                    episode_id=episode_id,
                    job_id=job_id,
                    error=str(e))
        
        # Update job status
        active_jobs[job_id] = {
            "status": "failed",
            "episode_id": episode_id,
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        }
        
        # Call webhook with error if provided
        if callback_url:
            error_payload = {
                "job_id": job_id,
                "episode_id": episode_id,
                "filename": video_path.split('/')[-1],
                "status": "failed",
                "stage": "unknown",
                "duration": (datetime.now() - start_time).total_seconds(),
                "error": str(e)
            }
            await send_webhook_notification(callback_url, error_payload)


async def send_webhook_notification(url: str, payload: Dict[str, Any]):
    """
    Send webhook notification to callback URL
    
    Args:
        url: Webhook URL
        payload: Payload to send
    """
    try:
        logger.info(f"Sending webhook notification to {url}",
                   job_id=payload.get("job_id"))
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
        logger.info(f"Webhook notification sent successfully",
                   job_id=payload.get("job_id"),
                   status_code=response.status_code)
        
    except Exception as e:
        logger.error(f"Failed to send webhook notification",
                    url=url,
                    job_id=payload.get("job_id"),
                    error=str(e))


def register_async_endpoints(app, get_orchestrator):
    """Register async processing endpoints"""
    
    @app.post("/episodes/process-async", response_model=AsyncProcessResponse)
    async def process_episode_async_endpoint(
        request: AsyncProcessRequest,
        background_tasks: BackgroundTasks,
        orchestrator=None
    ):
        """
        Submit episode for async processing
        
        Returns immediately with job_id
        Processes video in background
        Calls callback_url when complete
        """
        try:
            # Get orchestrator
            if not orchestrator:
                from .server import _server_instance
                if not _server_instance or not _server_instance.orchestrator:
                    raise HTTPException(status_code=503, detail="Pipeline orchestrator not available")
                orchestrator = _server_instance.orchestrator
            
            # Generate job ID
            job_id = str(uuid.uuid4())
            
            logger.info(f"Received async processing request",
                       job_id=job_id,
                       episode_id=request.episode_id)
            
            # Add to background tasks
            background_tasks.add_task(
                process_episode_async,
                job_id=job_id,
                episode_id=request.episode_id,
                video_path=request.video_path,
                target_stage=request.target_stage,
                force_reprocess=request.force_reprocess,
                callback_url=str(request.callback_url) if request.callback_url else None,
                orchestrator=orchestrator
            )
            
            # Return immediately
            return AsyncProcessResponse(
                job_id=job_id,
                episode_id=request.episode_id,
                status="submitted",
                message=f"Job submitted for processing. Job ID: {job_id}",
                submitted_at=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Error submitting async processing request",
                        episode_id=request.episode_id,
                        error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/jobs/{job_id}")
    async def get_job_status(job_id: str):
        """Get status of async processing job"""
        if job_id not in active_jobs:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        
        return active_jobs[job_id]
    
    @app.get("/jobs")
    async def list_jobs():
        """List all active jobs"""
        return {
            "total_jobs": len(active_jobs),
            "jobs": active_jobs
        }
