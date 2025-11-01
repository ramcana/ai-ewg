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
    SuccessResponse,
    EpisodeMetadata
)
from fastapi import Depends
from ..core import get_logger

logger = get_logger('pipeline.api.endpoints')


def _extract_outputs(orchestrator, episode_id: str, stage) -> Optional[Dict[str, Any]]:
    """
    Extract outputs (HTML, artifacts) for rendered episodes
    
    Args:
        orchestrator: Pipeline orchestrator instance
        episode_id: Episode identifier
        stage: Current processing stage
        
    Returns:
        Dict with outputs or None if not rendered
    """
    from pathlib import Path
    from ..core.models import ProcessingStage
    
    # Only include outputs for rendered stage
    if stage != ProcessingStage.RENDERED:
        return None
    
    outputs = {}
    
    try:
        # Get episode to find show name for path construction
        episode = orchestrator.registry.get_episode(episode_id)
        if not episode:
            return None
        
        show_name = episode.metadata.show_name if episode.metadata else "unknown"
        show_slug = episode.metadata.show_slug if episode.metadata else show_name.lower().replace(' ', '-')
        
        # Try multiple possible HTML paths
        possible_paths = [
            Path(f"data/public/shows/{show_slug}/{episode_id}/index.html"),
            Path(f"data/public/{show_slug}/{episode_id}/index.html"),
            Path(f"data/public/{episode_id}.html"),
        ]
        
        for html_path in possible_paths:
            if html_path.exists():
                try:
                    outputs["rendered_html"] = html_path.read_text(encoding='utf-8')
                    outputs["html_path"] = str(html_path)
                    logger.info(f"Included HTML output in response", 
                               episode_id=episode_id, 
                               path=str(html_path))
                    break
                except Exception as e:
                    logger.warning(f"Could not read HTML file", 
                                  path=str(html_path), 
                                  error=str(e))
        
        # Include transcript paths if available
        transcript_txt = Path(f"data/transcripts/{episode_id}.txt")
        transcript_vtt = Path(f"data/transcripts/{episode_id}.vtt")
        
        if transcript_txt.exists():
            outputs["transcript_path"] = str(transcript_txt)
        if transcript_vtt.exists():
            outputs["vtt_path"] = str(transcript_vtt)
        
        return outputs if outputs else None
        
    except Exception as e:
        logger.error(f"Error extracting outputs", 
                    episode_id=episode_id, 
                    error=str(e))
        return None


def _extract_metadata_from_registry(orchestrator, episode_id: str) -> EpisodeMetadata:
    """
    Extract normalized metadata from episode registry (SQLite JSON blob)
    
    Args:
        orchestrator: Pipeline orchestrator instance
        episode_id: Episode identifier
        
    Returns:
        EpisodeMetadata: Normalized metadata block
    """
    try:
        # Get episode from registry
        episode = orchestrator.registry.get_episode(episode_id)
        
        if not episode:
            logger.warning(f"Episode not found in registry", episode_id=episode_id)
            return EpisodeMetadata()
        
        # Extract metadata fields from episode object
        md = episode.metadata
        transcription = episode.transcription
        enrichment = episode.enrichment
        editorial = episode.editorial
        
        # Extract guests from enrichment (people.guests array)
        guests = None
        if enrichment and enrichment.entities:
            # Entities might contain people information
            people_data = enrichment.entities.get('people', {})
            if isinstance(people_data, dict):
                guests_list = people_data.get('guests', [])
                if guests_list:
                    guests = [g.get('name') for g in guests_list if isinstance(g, dict) and g.get('name')]
        
        # Get host from metadata or enrichment
        host = None
        if enrichment and enrichment.entities:
            people_data = enrichment.entities.get('people', {})
            if isinstance(people_data, dict):
                host_data = people_data.get('host', {})
                if isinstance(host_data, dict):
                    host = host_data.get('name')
        
        # Fallback to basic metadata if enrichment not available
        if not host and hasattr(md, 'host'):
            host = getattr(md, 'host', None)
        
        # Get description from editorial summary
        description = None
        if editorial:
            description = editorial.summary
        elif hasattr(md, 'description'):
            description = md.description
        
        # Get confidence from transcription
        confidence = None
        if transcription:
            confidence = transcription.confidence
        
        # Get model version from transcription
        model_version = None
        if transcription:
            model_version = transcription.model_used
        
        return EpisodeMetadata(
            show_name=md.show_name if md else None,
            title=md.title if md else None,
            host=host,
            topic=md.topic if md else None,
            guests=guests,
            date=md.date if md else None,
            description=description,
            confidence=confidence,
            model_version=model_version
        )
        
    except Exception as e:
        logger.error(f"Error extracting metadata from registry", 
                    episode_id=episode_id, 
                    error=str(e))
        # Return empty metadata on error rather than failing the request
        return EpisodeMetadata()


def get_orchestrator():
    """Dependency to get the pipeline orchestrator instance"""
    from .server import _server_instance
    
    if not _server_instance or not _server_instance.orchestrator:
        raise HTTPException(status_code=503, detail="Pipeline orchestrator not available")
    
    return _server_instance.orchestrator


def register_endpoints(app: FastAPI):
    """Register all API endpoints"""
    
    # Register clip endpoints
    from .clip_endpoints import register_clip_endpoints
    register_clip_endpoints(app)
    
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
    
    @app.delete("/episodes/{episode_id}", response_model=SuccessResponse)
    async def delete_episode(
        episode_id: str,
        delete_files: bool = Query(True, description="Delete all generated files"),
        orchestrator = Depends(get_orchestrator)
    ):
        """
        Delete an episode and optionally all its generated files
        
        This will:
        - Remove episode from database
        - Delete transcripts (txt, vtt)
        - Delete enrichment data (json)
        - Delete rendered HTML and metadata
        - Delete clips and variants
        - Delete social media packages
        - Delete audio files
        - Optionally keep or delete source video
        """
        try:
            from pathlib import Path
            import shutil
            
            logger.info(f"Deleting episode: {episode_id}", delete_files=delete_files)
            
            # Get episode info before deletion
            episode = orchestrator.registry.get_episode(episode_id)
            if not episode:
                raise HTTPException(status_code=404, detail=f"Episode not found: {episode_id}")
            
            deleted_files = []
            errors = []
            
            if delete_files:
                # Delete transcripts
                transcript_paths = [
                    Path(f"data/transcripts/txt/{episode_id}.txt"),
                    Path(f"data/transcripts/vtt/{episode_id}.vtt"),
                    Path(f"data/transcripts/{episode_id}.txt"),
                    Path(f"data/transcripts/{episode_id}.vtt"),
                ]
                
                for path in transcript_paths:
                    if path.exists():
                        try:
                            path.unlink()
                            deleted_files.append(str(path))
                            logger.debug(f"Deleted transcript: {path}")
                        except Exception as e:
                            errors.append(f"Failed to delete {path}: {e}")
                
                # Delete enrichment data
                enrichment_path = Path(f"data/enriched/{episode_id}.json")
                if enrichment_path.exists():
                    try:
                        enrichment_path.unlink()
                        deleted_files.append(str(enrichment_path))
                        logger.debug(f"Deleted enrichment: {enrichment_path}")
                    except Exception as e:
                        errors.append(f"Failed to delete {enrichment_path}: {e}")
                
                # Delete audio file
                audio_path = Path(f"data/audio/{episode_id}.wav")
                if audio_path.exists():
                    try:
                        audio_path.unlink()
                        deleted_files.append(str(audio_path))
                        logger.debug(f"Deleted audio: {audio_path}")
                    except Exception as e:
                        errors.append(f"Failed to delete {audio_path}: {e}")
                
                # Delete rendered HTML and metadata
                if episode.metadata:
                    show_slug = episode.metadata.show_slug or "unknown"
                    html_paths = [
                        Path(f"data/public/shows/{show_slug}/{episode_id}"),
                        Path(f"data/public/{show_slug}/{episode_id}"),
                        Path(f"data/public/meta/{episode_id}.json"),
                    ]
                    
                    for path in html_paths:
                        if path.exists():
                            try:
                                if path.is_dir():
                                    shutil.rmtree(path)
                                else:
                                    path.unlink()
                                deleted_files.append(str(path))
                                logger.debug(f"Deleted rendered output: {path}")
                            except Exception as e:
                                errors.append(f"Failed to delete {path}: {e}")
                
                # Delete clips
                clip_paths = [
                    Path(f"data/clips/{episode_id}"),
                    Path(f"data/outputs/{episode_id}/clips"),
                ]
                
                # Also check organized structure
                if episode.metadata and episode.metadata.show_name:
                    from .naming_service import get_naming_service
                    naming_service = get_naming_service()
                    try:
                        episode_folder = naming_service.get_episode_folder_path(
                            episode_id=episode_id,
                            show_name=episode.metadata.show_name,
                            date=episode.created_at
                        )
                        clip_paths.append(episode_folder / "clips")
                    except Exception:
                        pass
                
                for path in clip_paths:
                    if path.exists():
                        try:
                            shutil.rmtree(path)
                            deleted_files.append(str(path))
                            logger.debug(f"Deleted clips: {path}")
                        except Exception as e:
                            errors.append(f"Failed to delete {path}: {e}")
                
                # Delete social media packages
                social_path = Path(f"data/social_packages/{episode_id}")
                if social_path.exists():
                    try:
                        shutil.rmtree(social_path)
                        deleted_files.append(str(social_path))
                        logger.debug(f"Deleted social packages: {social_path}")
                    except Exception as e:
                        errors.append(f"Failed to delete {social_path}: {e}")
                
                # Delete temp files
                temp_paths = [
                    Path(f"data/temp/{episode_id}"),
                    Path(f"data/temp/uploaded/{episode_id}"),
                ]
                
                for path in temp_paths:
                    if path.exists():
                        try:
                            if path.is_dir():
                                shutil.rmtree(path)
                            else:
                                path.unlink()
                            deleted_files.append(str(path))
                            logger.debug(f"Deleted temp files: {path}")
                        except Exception as e:
                            errors.append(f"Failed to delete {path}: {e}")
            
            # Delete from database
            try:
                orchestrator.registry.delete_episode(episode_id)
                logger.info(f"Episode deleted from database: {episode_id}")
            except Exception as e:
                errors.append(f"Failed to delete from database: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to delete episode from database: {e}")
            
            return SuccessResponse(
                message=f"Episode {episode_id} deleted successfully",
                data={
                    "episode_id": episode_id,
                    "files_deleted": len(deleted_files),
                    "deleted_files": deleted_files[:10],  # Show first 10 files
                    "errors": errors if errors else None
                }
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting episode: {e}", episode_id=episode_id, exc_info=True)
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
            
            # Enrich response with normalized metadata from SQLite after processing
            metadata = _extract_metadata_from_registry(orchestrator, request.episode_id)
            
            # Include HTML and other outputs if stage is rendered
            outputs = _extract_outputs(orchestrator, request.episode_id, result.stage)
            
            return ProcessingResponse(
                success=result.success,
                episode_id=result.episode_id,
                stage=result.stage.value,
                duration=result.duration,
                error=result.error,
                metrics=result.metrics,
                metadata=metadata,
                outputs=outputs
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