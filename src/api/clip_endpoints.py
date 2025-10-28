"""
API endpoints for clip generation operations

Provides REST endpoints for clip discovery, rendering, and management
integrated with the automated clip generation system.
"""

from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pathlib import Path

from ..core import get_logger
from ..core.models import ProcessingStage, ClipStatus
from .models import (
    ClipDiscoveryRequest,
    ClipRenderRequest,
    BulkRenderRequest,
    ClipDiscoveryResponse,
    ClipRenderResponse,
    BulkRenderResponse,
    ClipMetadata,
    ClipAssetInfo,
    ErrorResponse
)

logger = get_logger('pipeline.api.clip_endpoints')


def get_orchestrator():
    """Dependency to get the pipeline orchestrator instance"""
    from .server import _server_instance
    
    if not _server_instance or not _server_instance.orchestrator:
        raise HTTPException(status_code=503, detail="Pipeline orchestrator not available")
    
    return _server_instance.orchestrator


def get_clip_registry():
    """Dependency to get the clip registry instance"""
    orchestrator = get_orchestrator()
    
    # Import here to avoid circular imports
    from ..core.clip_registry import ClipRegistry
    
    # Get or create clip registry
    if not hasattr(orchestrator, '_clip_registry'):
        # ClipRegistry expects a DatabaseManager, not a path
        orchestrator._clip_registry = ClipRegistry(orchestrator.registry.db_manager)
    
    return orchestrator._clip_registry


def get_clip_discovery_engine():
    """Dependency to get the clip discovery engine"""
    orchestrator = get_orchestrator()
    
    # Import here to avoid circular imports
    from ..core.clip_discovery import ClipDiscoveryEngine
    
    # Get or create clip discovery engine
    if not hasattr(orchestrator, '_clip_discovery_engine'):
        orchestrator._clip_discovery_engine = ClipDiscoveryEngine(
            orchestrator.config,
            orchestrator.registry
        )
    
    return orchestrator._clip_discovery_engine


def get_clip_export_system():
    """Dependency to get the clip export system"""
    orchestrator = get_orchestrator()
    
    # Import here to avoid circular imports
    from ..core.clip_export import ClipExportSystem
    
    # Get or create clip export system
    if not hasattr(orchestrator, '_clip_export_system'):
        orchestrator._clip_export_system = ClipExportSystem()
    
    return orchestrator._clip_export_system


def _convert_clip_to_metadata(clip) -> ClipMetadata:
    """Convert internal clip object to API metadata"""
    return ClipMetadata(
        id=clip.id,
        episode_id=clip.episode_id,
        start_ms=clip.start_ms,
        end_ms=clip.end_ms,
        duration_ms=clip.duration_ms,
        score=clip.score,
        title=clip.title,
        caption=clip.caption,
        hashtags=clip.hashtags,
        status=clip.status,
        created_at=clip.created_at.isoformat() if clip.created_at else None
    )


def _convert_asset_to_info(asset) -> ClipAssetInfo:
    """Convert internal asset object to API info"""
    return ClipAssetInfo(
        id=asset.id,
        path=asset.path,
        variant=asset.variant,
        aspect_ratio=asset.aspect_ratio,
        size_bytes=asset.size_bytes,
        created_at=asset.created_at.isoformat() if asset.created_at else None
    )


def _get_resolution_for_aspect_ratio(aspect_ratio: str) -> str:
    """Get standard resolution for aspect ratio"""
    resolution_map = {
        "9x16": "1080x1920",  # Vertical/Portrait
        "16x9": "1920x1080",  # Horizontal/Landscape
        "1x1": "1080x1080"    # Square
    }
    return resolution_map.get(aspect_ratio, "1920x1080")


def register_clip_endpoints(app: FastAPI):
    """Register clip generation API endpoints"""
    
    @app.post("/episodes/{episode_id}/discover_clips", response_model=ClipDiscoveryResponse)
    async def discover_clips(
        episode_id: str,
        request: ClipDiscoveryRequest = ClipDiscoveryRequest(),
        orchestrator = Depends(get_orchestrator),
        clip_registry = Depends(get_clip_registry),
        discovery_engine = Depends(get_clip_discovery_engine)
    ):
        """
        Discover clips for an episode with idempotent behavior
        
        This endpoint identifies potential clip segments from processed episodes
        using topic segmentation and highlight scoring. If clips have already
        been discovered for this episode, returns existing clips unless
        configuration parameters differ significantly.
        """
        try:
            logger.info(f"Discovering clips for episode", 
                       episode_id=episode_id,
                       max_clips=request.max_clips,
                       min_duration=request.min_duration_ms,
                       max_duration=request.max_duration_ms)
            
            # Check if episode exists and is processed
            episode = orchestrator.registry.get_episode(episode_id)
            if not episode:
                raise HTTPException(status_code=404, detail=f"Episode not found: {episode_id}")
            
            if episode.processing_stage != ProcessingStage.RENDERED:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Episode must be in RENDERED stage for clip discovery. Current stage: {episode.processing_stage.value}"
                )
            
            # Check for existing clips (idempotent behavior)
            existing_clips = clip_registry.get_clips_for_episode(episode_id)
            
            if existing_clips:
                logger.info(f"Found existing clips for episode", 
                           episode_id=episode_id, 
                           count=len(existing_clips))
                
                # Convert to API format
                clip_metadata = [_convert_clip_to_metadata(clip) for clip in existing_clips]
                
                return ClipDiscoveryResponse(
                    success=True,
                    episode_id=episode_id,
                    clips_discovered=len(existing_clips),
                    clips=clip_metadata,
                    message=f"Returned {len(existing_clips)} existing clips"
                )
            
            # Discover new clips
            clips = await discovery_engine.discover_clips(
                episode_id=episode_id,
                max_clips=request.max_clips,
                min_duration_ms=request.min_duration_ms,
                max_duration_ms=request.max_duration_ms,
                aspect_ratios=request.aspect_ratios,
                score_threshold=request.score_threshold
            )
            
            # Register clips in database
            for clip in clips:
                clip_registry.register_clip(clip)
            
            # Convert to API format
            clip_metadata = [_convert_clip_to_metadata(clip) for clip in clips]
            
            logger.info(f"Discovered clips for episode", 
                       episode_id=episode_id, 
                       count=len(clips))
            
            return ClipDiscoveryResponse(
                success=True,
                episode_id=episode_id,
                clips_discovered=len(clips),
                clips=clip_metadata,
                message=f"Discovered {len(clips)} new clips"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error discovering clips", 
                        episode_id=episode_id, 
                        error=str(e),
                        exc_info=True)
            
            return ClipDiscoveryResponse(
                success=False,
                episode_id=episode_id,
                clips_discovered=0,
                clips=[],
                error=str(e)
            )
    
    @app.post("/clips/{clip_id}/render", response_model=ClipRenderResponse)
    async def render_clip(
        clip_id: str,
        request: ClipRenderRequest = ClipRenderRequest(),
        clip_registry = Depends(get_clip_registry),
        export_system = Depends(get_clip_export_system),
        orchestrator = Depends(get_orchestrator)
    ):
        """
        Render a specific clip in requested variants and aspect ratios
        
        Generates video files for the specified clip with support for
        multiple variants (clean/subtitled) and aspect ratios.
        Returns asset paths and metadata with standardized response format.
        """
        try:
            logger.info(f"Rendering clip", 
                       clip_id=clip_id,
                       variants=request.variants,
                       aspect_ratios=request.aspect_ratios)
            
            # Get clip from registry
            clip = clip_registry.get_clip(clip_id)
            if not clip:
                raise HTTPException(status_code=404, detail=f"Clip not found: {clip_id}")
            
            # Get episode to find source video
            episode = orchestrator.registry.get_episode(clip.episode_id)
            if not episode:
                raise HTTPException(status_code=404, detail=f"Episode not found: {clip.episode_id}")
            
            # Check for existing assets if not forcing re-render
            existing_assets = clip_registry.get_assets_for_clip(clip_id)
            
            if existing_assets and not request.force_rerender:
                # Filter existing assets by requested variants and aspect ratios
                matching_assets = [
                    asset for asset in existing_assets
                    if asset.variant in request.variants and asset.aspect_ratio in request.aspect_ratios
                ]
                
                if matching_assets:
                    logger.info(f"Found existing assets for clip", 
                               clip_id=clip_id, 
                               count=len(matching_assets))
                    
                    asset_info = [_convert_asset_to_info(asset) for asset in matching_assets]
                    
                    return ClipRenderResponse(
                        success=True,
                        clip_id=clip_id,
                        assets_generated=len(matching_assets),
                        assets=asset_info,
                        message=f"Returned {len(matching_assets)} existing assets"
                    )
            
            # Create clip specification from clip object
            from ..core.clip_specification import ClipSpecification, ClipVariantSpec
            
            # Create variant specifications
            variant_specs = []
            for variant in request.variants:
                for aspect_ratio in request.aspect_ratios:
                    # Generate output path directly to data/clips (not using naming service folder structure)
                    from pathlib import Path
                    
                    output_path = str(Path("data/clips") / clip.episode_id / clip.id / f"{aspect_ratio}_{variant}.mp4")
                    
                    variant_spec = ClipVariantSpec(
                        variant=variant,
                        aspect_ratio=aspect_ratio,
                        output_path=output_path
                    )
                    variant_specs.append(variant_spec)
            
            clip_spec = ClipSpecification(
                clip_id=clip.id,
                episode_id=clip.episode_id,
                start_ms=clip.start_ms,
                end_ms=clip.end_ms,
                duration_ms=clip.duration_ms,
                score=clip.score,
                title=clip.title,
                caption=clip.caption,
                hashtags=clip.hashtags,
                variants=variant_specs
            )
            
            # Render clip assets (resolve relative path to absolute)
            assets = export_system.render_clip(
                clip_spec=clip_spec,
                source_path=str(episode.source.get_absolute_path()),
                transcript=episode.transcription
            )
            
            # Register assets in database
            for asset in assets:
                clip_registry.register_asset(asset)
            
            # Update clip status to rendered
            clip_registry.update_clip_status(clip_id, ClipStatus.RENDERED)
            
            # Convert to API format
            asset_info = [_convert_asset_to_info(asset) for asset in assets]
            
            logger.info(f"Rendered clip assets", 
                       clip_id=clip_id, 
                       count=len(assets))
            
            return ClipRenderResponse(
                success=True,
                clip_id=clip_id,
                assets_generated=len(assets),
                assets=asset_info,
                message=f"Generated {len(assets)} new assets"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error rendering clip", 
                        clip_id=clip_id, 
                        error=str(e))
            
            # Update clip status to failed
            try:
                clip_registry.update_clip_status(clip_id, ClipStatus.FAILED)
            except:
                pass
            
            return ClipRenderResponse(
                success=False,
                clip_id=clip_id,
                assets_generated=0,
                assets=[],
                error=str(e)
            )
    
    @app.post("/episodes/{episode_id}/render_clips", response_model=BulkRenderResponse)
    async def render_clips_bulk(
        episode_id: str,
        background_tasks: BackgroundTasks,
        request: BulkRenderRequest = BulkRenderRequest(),
        clip_registry = Depends(get_clip_registry),
        export_system = Depends(get_clip_export_system),
        orchestrator = Depends(get_orchestrator)
    ):
        """
        Render multiple clips for an episode in batch
        
        Processes multiple clips with filtering by status or score thresholds.
        Supports asynchronous processing for large batches to prevent timeouts.
        """
        try:
            logger.info(f"Bulk rendering clips for episode", 
                       episode_id=episode_id,
                       clip_ids=request.clip_ids,
                       score_threshold=request.score_threshold,
                       status_filter=request.status_filter)
            
            # Get clips for episode
            if request.clip_ids:
                # Render specific clips
                clips = []
                for clip_id in request.clip_ids:
                    clip = clip_registry.get_clip(clip_id)
                    if clip and clip.episode_id == episode_id:
                        clips.append(clip)
            else:
                # Get all clips for episode
                clips = clip_registry.get_clips_for_episode(episode_id)
            
            if not clips:
                raise HTTPException(status_code=404, detail=f"No clips found for episode: {episode_id}")
            
            # Apply filters
            filtered_clips = []
            for clip in clips:
                # Score threshold filter
                if request.score_threshold and clip.score < request.score_threshold:
                    continue
                
                # Status filter
                if request.status_filter and clip.status != request.status_filter:
                    continue
                
                filtered_clips.append(clip)
            
            if not filtered_clips:
                return BulkRenderResponse(
                    success=True,
                    episode_id=episode_id,
                    clips_processed=0,
                    clips_successful=0,
                    clips_failed=0,
                    results=[],
                    message="No clips matched the specified filters"
                )
            
            # Get episode for source path
            episode = orchestrator.registry.get_episode(episode_id)
            if not episode:
                raise HTTPException(status_code=404, detail=f"Episode not found: {episode_id}")
            
            # Validate episode has source path
            if not episode.source or not episode.source.path:
                raise HTTPException(status_code=400, detail=f"Episode {episode_id} has no source video path")
            
            # Check if source file exists (resolve relative path to absolute)
            from pathlib import Path
            source_path = episode.source.get_absolute_path()
            if not source_path.exists():
                raise HTTPException(status_code=400, detail=f"Source video file not found: {source_path}")
            
            # Process clips
            results = []
            successful = 0
            failed = 0
            
            for clip in filtered_clips:
                try:
                    # Check for existing assets if not forcing re-render
                    existing_assets = clip_registry.get_assets_for_clip(clip.id)
                    
                    if existing_assets and not request.force_rerender:
                        # Filter existing assets by requested variants and aspect ratios
                        matching_assets = [
                            asset for asset in existing_assets
                            if asset.variant in request.variants and asset.aspect_ratio in request.aspect_ratios
                        ]
                        
                        if matching_assets:
                            asset_info = [_convert_asset_to_info(asset) for asset in matching_assets]
                            
                            results.append(ClipRenderResponse(
                                success=True,
                                clip_id=clip.id,
                                assets_generated=len(matching_assets),
                                assets=asset_info,
                                message=f"Used {len(matching_assets)} existing assets"
                            ))
                            successful += 1
                            continue
                    
                    # Create clip specification from clip object
                    from ..core.clip_specification import ClipSpecification, ClipVariantSpec
                    
                    # Create variant specifications
                    variant_specs = []
                    for variant in request.variants:
                        for aspect_ratio in request.aspect_ratios:
                            # Generate output path directly to data/clips (not using naming service folder structure)
                            from pathlib import Path
                            
                            output_path = str(Path("data/clips") / clip.episode_id / clip.id / f"{aspect_ratio}_{variant}.mp4")
                            
                            variant_spec = ClipVariantSpec(
                                variant=variant,
                                aspect_ratio=aspect_ratio,
                                output_path=output_path
                            )
                            variant_specs.append(variant_spec)
                    
                    clip_spec = ClipSpecification(
                        clip_id=clip.id,
                        episode_id=clip.episode_id,
                        start_ms=clip.start_ms,
                        end_ms=clip.end_ms,
                        duration_ms=clip.duration_ms,
                        score=clip.score,
                        title=clip.title,
                        caption=clip.caption,
                        hashtags=clip.hashtags,
                        variants=variant_specs
                    )
                    
                    # Render clip assets (resolve relative path to absolute)
                    assets = export_system.render_clip(
                        clip_spec=clip_spec,
                        source_path=str(episode.source.get_absolute_path()),
                        transcript=episode.transcription
                    )
                    
                    # Register assets in database
                    for asset in assets:
                        clip_registry.register_asset(asset)
                    
                    # Update clip status to rendered
                    clip_registry.update_clip_status(clip.id, ClipStatus.RENDERED)
                    
                    # Convert to API format
                    asset_info = [_convert_asset_to_info(asset) for asset in assets]
                    
                    results.append(ClipRenderResponse(
                        success=True,
                        clip_id=clip.id,
                        assets_generated=len(assets),
                        assets=asset_info,
                        message=f"Generated {len(assets)} new assets"
                    ))
                    successful += 1
                    
                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    logger.error(f"Error rendering clip in batch", 
                                clip_id=clip.id, 
                                error=str(e),
                                traceback=error_details,
                                exc_info=True)
                    print(f"\n{'='*80}")
                    print(f"CLIP RENDERING ERROR - Clip ID: {clip.id}")
                    print(f"{'='*80}")
                    print(error_details)
                    print(f"{'='*80}\n")
                    
                    # Update clip status to failed
                    try:
                        clip_registry.update_clip_status(clip.id, ClipStatus.FAILED)
                    except:
                        pass
                    
                    results.append(ClipRenderResponse(
                        success=False,
                        clip_id=clip.id,
                        assets_generated=0,
                        assets=[],
                        error=str(e)
                    ))
                    failed += 1
            
            logger.info(f"Bulk clip rendering completed", 
                       episode_id=episode_id,
                       processed=len(filtered_clips),
                       successful=successful,
                       failed=failed)
            
            return BulkRenderResponse(
                success=True,
                episode_id=episode_id,
                clips_processed=len(filtered_clips),
                clips_successful=successful,
                clips_failed=failed,
                results=results,
                message=f"Processed {len(filtered_clips)} clips: {successful} successful, {failed} failed"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in bulk clip rendering", 
                        episode_id=episode_id, 
                        error=str(e))
            
            return BulkRenderResponse(
                success=False,
                episode_id=episode_id,
                clips_processed=0,
                clips_successful=0,
                clips_failed=0,
                results=[],
                error=str(e)
            )