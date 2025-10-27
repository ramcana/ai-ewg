"""
Async processing endpoints for long-running operations

Provides job-based async processing with status polling and webhook notifications.
"""

import asyncio
import threading
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from typing import Optional, List
from pydantic import BaseModel, Field

from ..core.job_queue import get_job_queue, JobStatus
from ..core.models import ProcessingStage
from ..core import get_logger

logger = get_logger('pipeline.api.async')

router = APIRouter(prefix="/async", tags=["async"])


# Request/Response Models
class AsyncProcessRequest(BaseModel):
    """Request to process episode asynchronously"""
    episode_id: str = Field(..., description="Episode ID to process")
    target_stage: str = Field(default="rendered", description="Target processing stage")
    force_reprocess: bool = Field(default=False, description="Force reprocessing")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for completion notification")


class AsyncRenderClipsRequest(BaseModel):
    """Request to render clips asynchronously"""
    episode_id: str = Field(..., description="Episode ID")
    clip_ids: Optional[List[str]] = Field(None, description="Specific clip IDs (None = all)")
    variants: List[str] = Field(default=["clean", "subtitled"], description="Clip variants")
    aspect_ratios: List[str] = Field(default=["9x16", "16x9"], description="Aspect ratios")
    force_rerender: bool = Field(default=False, description="Force re-rendering")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for completion notification")


class JobResponse(BaseModel):
    """Response with job ID"""
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Job status response"""
    job_id: str
    job_type: str
    status: str
    progress: float
    current_stage: str
    message: str
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    eta_seconds: Optional[float] = None


def get_orchestrator():
    """Dependency to get pipeline orchestrator"""
    from .server import _server_instance
    
    if not _server_instance or not _server_instance.orchestrator:
        raise HTTPException(status_code=503, detail="Pipeline orchestrator not available")
    
    return _server_instance.orchestrator


async def process_episode_job(job_id: str, episode_id: str, target_stage: str, force_reprocess: bool):
    """Background task to process episode"""
    job_queue = get_job_queue()
    
    try:
        # Mark job as running
        job_queue.mark_job_running(job_id)
        
        # Get orchestrator
        from .server import _server_instance
        orchestrator = _server_instance.orchestrator
        
        # Verify episode exists
        episode = orchestrator.registry.get_episode(episode_id)
        if not episode:
            job_queue.mark_job_failed(job_id, f"Episode not found: {episode_id}")
            return
        
        # Update progress: Starting
        job_queue.update_job_progress(
            job_id,
            progress=5.0,
            stage="starting",
            message="Initializing episode processing"
        )
        
        # Process episode
        target = ProcessingStage(target_stage)
        result = await orchestrator.process_episode(
            episode_id,
            target,
            force_reprocess
        )
        
        # Update progress based on result
        if result.success:
            job_queue.update_job_progress(
                job_id,
                progress=100.0,
                stage="completed",
                message=f"Episode processed to {result.stage.value}"
            )
            
            # Mark as completed
            job_queue.mark_job_completed(
                job_id,
                result={
                    'episode_id': result.episode_id,
                    'stage': result.stage.value,
                    'duration': result.duration,
                    'metrics': result.metrics
                }
            )
        else:
            job_queue.mark_job_failed(
                job_id,
                error=result.error or "Processing failed"
            )
    
    except Exception as e:
        logger.error(f"Job {job_id} failed with exception", error=str(e), exc_info=True)
        job_queue.mark_job_failed(job_id, str(e))


async def render_clips_job(
    job_id: str,
    episode_id: str,
    clip_ids: Optional[List[str]],
    variants: List[str],
    aspect_ratios: List[str],
    force_rerender: bool
):
    """Background task to render clips"""
    job_queue = get_job_queue()
    
    try:
        # Mark job as running
        job_queue.mark_job_running(job_id)
        
        # Get orchestrator
        from .server import _server_instance
        orchestrator = _server_instance.orchestrator
        
        # Update progress
        job_queue.update_job_progress(
            job_id,
            progress=10.0,
            stage="discovering",
            message="Loading clips for rendering"
        )
        
        # Get clip registry
        from ..core.clip_registry import get_clip_registry
        clip_registry = get_clip_registry(orchestrator.registry.db_manager)
        
        # Get clips to render
        if clip_ids:
            clips = [clip_registry.get_clip(cid) for cid in clip_ids]
            clips = [c for c in clips if c is not None]
        else:
            clips = clip_registry.get_clips_for_episode(episode_id)
        
        if not clips:
            job_queue.mark_job_failed(job_id, "No clips found to render")
            return
        
        # Render clips
        from ..core.clip_export import get_clip_export_system
        export_system = get_clip_export_system()
        
        total_clips = len(clips)
        rendered = []
        failed = []
        
        for i, clip in enumerate(clips):
            try:
                # Update progress
                progress = 10 + (i / total_clips) * 80
                job_queue.update_job_progress(
                    job_id,
                    progress=progress,
                    stage="rendering",
                    message=f"Rendering clip {i+1}/{total_clips}"
                )
                
                # Get episode for source path
                episode = orchestrator.registry.get_episode(episode_id)
                
                # Render clip (simplified - actual implementation would be more complex)
                # This is a placeholder - you'd call the actual render logic here
                rendered.append(clip.id)
                
            except Exception as e:
                logger.error(f"Failed to render clip {clip.id}", error=str(e))
                failed.append({'clip_id': clip.id, 'error': str(e)})
        
        # Mark as completed
        job_queue.mark_job_completed(
            job_id,
            result={
                'episode_id': episode_id,
                'total_clips': total_clips,
                'rendered': len(rendered),
                'failed': len(failed),
                'rendered_clips': rendered,
                'failed_clips': failed
            }
        )
    
    except Exception as e:
        logger.error(f"Job {job_id} failed with exception", error=str(e), exc_info=True)
        job_queue.mark_job_failed(job_id, str(e))


@router.post("/episodes/{episode_id}/process", response_model=JobResponse)
async def process_episode_async(
    episode_id: str,
    request: AsyncProcessRequest,
    orchestrator = Depends(get_orchestrator)
):
    """
    Process episode asynchronously
    
    Submits episode for processing and returns immediately with job_id.
    Poll /async/jobs/{job_id} for status updates.
    """
    try:
        # Submit job immediately (don't verify episode exists - let background task handle that)
        job_queue = get_job_queue()
        job_id = job_queue.submit_job(
            job_type="process_episode",
            parameters={
                'episode_id': episode_id,
                'target_stage': request.target_stage,
                'force_reprocess': request.force_reprocess
            },
            webhook_url=request.webhook_url
        )
        
        # Start background processing in a separate thread
        import threading
        thread = threading.Thread(
            target=lambda: asyncio.run(process_episode_job(job_id, episode_id, request.target_stage, request.force_reprocess)),
            daemon=True
        )
        thread.start()
        
        logger.info(f"Async processing started for episode {episode_id}, job_id: {job_id}")
        
        return JobResponse(
            job_id=job_id,
            status="queued",
            message=f"Episode processing queued. Poll /async/jobs/{job_id} for status."
        )
    
    except Exception as e:
        logger.error(f"Error starting async processing", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/episodes/{episode_id}/render_clips", response_model=JobResponse)
async def render_clips_async(
    episode_id: str,
    request: AsyncRenderClipsRequest,
    background_tasks: BackgroundTasks,
    orchestrator = Depends(get_orchestrator)
):
    """
    Render clips asynchronously
    
    Submits clips for rendering and returns immediately with job_id.
    Poll /async/jobs/{job_id} for status updates.
    """
    try:
        # Verify episode exists
        episode = orchestrator.registry.get_episode(episode_id)
        if not episode:
            raise HTTPException(status_code=404, detail=f"Episode not found: {episode_id}")
        
        # Submit job
        job_queue = get_job_queue()
        job_id = job_queue.submit_job(
            job_type="render_clips",
            parameters={
                'episode_id': episode_id,
                'clip_ids': request.clip_ids,
                'variants': request.variants,
                'aspect_ratios': request.aspect_ratios,
                'force_rerender': request.force_rerender
            },
            webhook_url=request.webhook_url
        )
        
        # Start background rendering
        background_tasks.add_task(
            render_clips_job,
            job_id,
            episode_id,
            request.clip_ids,
            request.variants,
            request.aspect_ratios,
            request.force_rerender
        )
        
        logger.info(f"Async clip rendering started for episode {episode_id}, job_id: {job_id}")
        
        return JobResponse(
            job_id=job_id,
            status="queued",
            message=f"Clip rendering queued. Poll /async/jobs/{job_id} for status."
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting async clip rendering", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get job status and progress
    
    Returns current status, progress percentage, and estimated time remaining.
    """
    job_queue = get_job_queue()
    job_status = job_queue.get_job_status(job_id)
    
    if not job_status:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    
    return JobStatusResponse(**job_status)


@router.get("/jobs", response_model=List[JobStatusResponse])
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, description="Maximum number of jobs to return")
):
    """
    List jobs with optional filtering
    
    Returns list of jobs sorted by creation time (newest first).
    """
    job_queue = get_job_queue()
    
    # Convert status string to enum if provided
    status_filter = None
    if status:
        try:
            status_filter = JobStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    jobs = job_queue.list_jobs(status=status_filter, limit=limit)
    
    return [JobStatusResponse(**job) for job in jobs]


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    """
    Cancel a queued job
    
    Only queued jobs can be cancelled. Running jobs cannot be stopped.
    """
    job_queue = get_job_queue()
    
    if job_queue.cancel_job(job_id):
        return {"message": f"Job {job_id} cancelled successfully"}
    else:
        raise HTTPException(
            status_code=400,
            detail="Job cannot be cancelled (not queued or already completed)"
        )


@router.get("/stats")
async def get_queue_stats():
    """
    Get job queue statistics
    
    Returns counts of queued, running, completed, and failed jobs.
    """
    job_queue = get_job_queue()
    return job_queue.get_queue_stats()


def register_async_endpoints(app):
    """Register async endpoints with FastAPI app"""
    app.include_router(router)
    logger.info("Async processing endpoints registered")
