"""
API endpoints for n8n integration

Provides REST endpoints for pipeline operations, status monitoring,
and webhook handlers for workflow integration.
"""

import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse

from ..core.models import ProcessingStage
from .models import (
    ProcessEpisodeRequest,
    ProcessBatchRequest,
    WebhookRequest,
    ProcessingResponse,
    BatchProcessingResponse,
    EpisodeStatusResponse,
    SystemHealthResponse,
    PipelineStatsResponse,
    ConfigurationResponse,
    ErrorResponse,
    SuccessResponse
)
from fastapi import Depends
from ..core import get_logger

logger = get_logger('pipeline.api.endpoints')


def get_orchestrator():
    """Dependency to get the pipeline orchestrator instance"""
    from .server import _server_instance
    
    if not _server_instance or not _server_instance.orchestrator:
        raise HTTPException(status_code=503, detail="Pipeline orchestrator not available")
    
    return _server_instance.orchestrator


def register_endpoints(app: FastAPI):
    """Register all API endpoints"""
    
    @app.get("/", response_model=Dict[str, str])
    async def root():
        """Root endpoint"""
        return {
            "service": "Video Processing Pipeline API",
            "version": "1.0.0",
            "status": "running"
        }
    
    @app.get("/health", response_model=SystemHealthResponse)
    async def get_health(orchestrator = Depends(get_orchestrator)):
        """Get system health status"""
        try:
            health = orchestrator.get_system_health()
            
            return SystemHealthResponse(**health)
            
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/status", response_model=PipelineStatsResponse)
    async def get_status(orchestrator = Depends(get_orchestrator)):
        """Get pipeline processing statistics"""
        try:
            stats = orchestrator.get_processing_stats()
            
            return PipelineStatsResponse(
                total_episodes=stats.total_episodes,
                processed=stats.processed,
                failed=stats.failed,
                success_rate=stats.success_rate,
                duration=stats.duration
            )
            
        except Exception as e:
            logger.error(f"Error getting pipeline status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/config", response_model=ConfigurationResponse)
    async def get_configuration(orchestrator = Depends(get_orchestrator)):
        """Get current pipeline configuration"""
        try:
            config = orchestrator.config
            
            return ConfigurationResponse(
                sources=[source.__dict__ for source in config.sources],
                processing=config.processing.__dict__,
                models=config.models.__dict__,
                thresholds=config.thresholds.__dict__
            )
            
        except Exception as e:
            logger.error(f"Error getting configuration: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/episodes", response_model=List[EpisodeStatusResponse])
    async def list_episodes(
        stage: Optional[str] = Query(None, description="Filter by processing stage"),
        limit: int = Query(20, description="Maximum number of episodes to return"),
        orchestrator = Depends(get_orchestrator)
    ):
        """List episodes with optional filtering"""
        try:
            stage_filter = ProcessingStage(stage) if stage else None
            episodes = orchestrator.list_episodes(stage_filter, limit)
            
            return [EpisodeStatusResponse(**episode) for episode in episodes]
            
        except Exception as e:
            logger.error(f"Error listing episodes: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/episodes/{episode_id}", response_model=EpisodeStatusResponse)
    async def get_episode_status(episode_id: str, orchestrator = Depends(get_orchestrator)):
        """Get status for a specific episode"""
        try:
            status = orchestrator.get_episode_status(episode_id)
            
            if not status:
                raise HTTPException(status_code=404, detail=f"Episode not found: {episode_id}")
            
            return EpisodeStatusResponse(**status)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting episode status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/episodes/discover", response_model=Dict[str, Any])
    async def discover_episodes(orchestrator = Depends(get_orchestrator)):
        """Discover new video episodes from configured source directories"""
        try:
            logger.info("Discovering episodes via API")
            
            # Run discovery
            episodes = await orchestrator.discover_episodes()
            
            # Return discovered episodes
            discovered = []
            for episode in episodes:
                discovered.append({
                    "episode_id": episode.episode_id,
                    "source_path": episode.source.path,
                    "show": episode.metadata.show_name,
                    "title": episode.metadata.title
                })
            
            logger.info(f"Discovery completed", count=len(discovered))
            
            return {
                "success": True,
                "discovered_count": len(discovered),
                "episodes": discovered
            }
            
        except Exception as e:
            logger.error(f"Error discovering episodes: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/episodes/process", response_model=ProcessingResponse)
    async def process_episode(
        request: ProcessEpisodeRequest,
        background_tasks: BackgroundTasks,
        orchestrator = Depends(get_orchestrator)
    ):
        """Process a single episode"""
        try:
            logger.info(f"Processing episode via API", 
                       episode_id=request.episode_id, 
                       target_stage=request.target_stage.value,
                       force_reprocess=request.force_reprocess)
            
            # Process episode
            result = await orchestrator.process_episode(
                request.episode_id, 
                request.target_stage,
                request.force_reprocess
            )
            
            return ProcessingResponse(
                success=result.success,
                episode_id=result.episode_id,
                stage=result.stage.value,
                duration=result.duration,
                error=result.error,
                metrics=result.metrics
            )
            
        except Exception as e:
            logger.error(f"Error processing episode: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/episodes/batch", response_model=BatchProcessingResponse)
    async def process_batch(
        request: ProcessBatchRequest,
        background_tasks: BackgroundTasks,
        orchestrator = Depends(get_orchestrator)
    ):
        """Process multiple episodes in batch"""
        try:
            logger.info(f"Processing batch via API", 
                       episode_count=len(request.episode_ids),
                       target_stage=request.target_stage.value)
            
            # Process batch
            stats = await orchestrator.process_batch(
                request.episode_ids,
                request.target_stage,
                request.max_concurrent
            )
            
            # Create individual results (simplified for now)
            results = []
            for episode_id in request.episode_ids:
                results.append(ProcessingResponse(
                    success=True,  # Would need individual tracking
                    episode_id=episode_id,
                    stage=request.target_stage.value,
                    duration=stats.duration / len(request.episode_ids),
                    error=None,
                    metrics=None
                ))
            
            return BatchProcessingResponse(
                total_episodes=stats.total_episodes,
                processed=stats.processed,
                failed=stats.failed,
                success_rate=stats.success_rate,
                duration=stats.duration,
                results=results
            )
            
        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/webhooks/trigger", response_model=SuccessResponse)
    async def webhook_trigger(
        request: WebhookRequest,
        background_tasks: BackgroundTasks
    ):
        """Handle webhook triggers from n8n workflows"""
        try:
            logger.info(f"Webhook received", 
                       event_type=request.event_type,
                       data_keys=list(request.data.keys()))
            
            # Handle different webhook events
            if request.event_type == "video_discovered":
                # Trigger processing for newly discovered video
                episode_id = request.data.get("episode_id")
                if episode_id:
                    background_tasks.add_task(
                        _process_episode_background,
                        episode_id,
                        ProcessingStage.RENDERED
                    )
            
            elif request.event_type == "batch_process":
                # Trigger batch processing
                episode_ids = request.data.get("episode_ids", [])
                if episode_ids:
                    background_tasks.add_task(
                        _process_batch_background,
                        episode_ids,
                        ProcessingStage.RENDERED
                    )
            
            elif request.event_type == "health_check":
                # Perform health check - we'll get orchestrator inside the condition
                from .server import _server_instance
                if _server_instance and _server_instance.orchestrator:
                    health = _server_instance.orchestrator.get_system_health()
                    return SuccessResponse(
                        message="Health check completed",
                        data=health
                    )
            
            return SuccessResponse(
                message=f"Webhook {request.event_type} processed successfully"
            )
            
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/metrics/export")
    async def export_metrics(
        format_type: str = Query("json", description="Export format (json, csv)"),
        orchestrator = Depends(get_orchestrator)
    ):
        """Export pipeline metrics"""
        try:
            metrics = orchestrator.export_metrics(format_type)
            
            if format_type == "json":
                return JSONResponse(content=metrics)
            else:
                return JSONResponse(content={"metrics": metrics})
            
        except Exception as e:
            logger.error(f"Error exporting metrics: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/control/shutdown", response_model=SuccessResponse)
    async def shutdown_pipeline(orchestrator = Depends(get_orchestrator)):
        """Request graceful shutdown of pipeline"""
        try:
            orchestrator.request_shutdown()
            
            return SuccessResponse(message="Shutdown requested")
            
        except Exception as e:
            logger.error(f"Error requesting shutdown: {e}")
            raise HTTPException(status_code=500, detail=str(e))


async def _process_episode_background(episode_id: str, target_stage: ProcessingStage):
    """Background task for processing episodes"""
    try:
        from .server import _server_instance
        if _server_instance and _server_instance.orchestrator:
            result = await _server_instance.orchestrator.process_episode(episode_id, target_stage)
            
            logger.info(f"Background episode processing completed",
                       episode_id=episode_id,
                       success=result.success,
                       duration=result.duration)
        
    except Exception as e:
        logger.error(f"Background episode processing failed",
                    episode_id=episode_id,
                    error=str(e))


async def _process_batch_background(episode_ids: List[str], target_stage: ProcessingStage):
    """Background task for batch processing"""
    try:
        from .server import _server_instance
        if _server_instance and _server_instance.orchestrator:
            stats = await _server_instance.orchestrator.process_batch(episode_ids, target_stage)
            
            logger.info(f"Background batch processing completed",
                       total=stats.total_episodes,
                       processed=stats.processed,
                       failed=stats.failed,
                       duration=stats.duration)
        
    except Exception as e:
        logger.error(f"Background batch processing failed",
                    episode_count=len(episode_ids),
                    error=str(e))