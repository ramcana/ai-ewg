"""
Social Media Publishing API Endpoints

FastAPI endpoints for social media package generation, job tracking, and publishing.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from ..core.policy_engine import PlatformPolicyEngine
from ..core.package_generator import SocialMediaPackageGenerator
from ..core.social_job_tracker import SocialJobTracker, SocialJobStatus
from ..core.registry import EpisodeRegistry
from ..core.config import ConfigurationManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/social", tags=["social"])

# Global components (initialized lazily)
_policy_engine = None
_package_generator = None
_job_tracker = None
_registry = None


def _get_components():
    """Get or initialize components lazily"""
    global _policy_engine, _package_generator, _job_tracker, _registry
    
    if _policy_engine is None:
        # Get config from the app state (set by server.py)
        from pathlib import Path
        config_path = Path("config/pipeline.yaml")
        
        config_manager = ConfigurationManager(config_path)
        config = config_manager.load_config(config_path)
        
        _policy_engine = PlatformPolicyEngine()
        _package_generator = SocialMediaPackageGenerator()
        _job_tracker = SocialJobTracker(config.database.path)
        _registry = EpisodeRegistry(config.database)
    
    return _policy_engine, _package_generator, _job_tracker, _registry


# Request/Response Models
class GeneratePackagesRequest(BaseModel):
    """Request to generate social media packages"""
    episode_id: str = Field(..., description="Episode identifier")
    platforms: List[str] = Field(..., description="Target platforms (youtube, instagram, x, tiktok, facebook)")
    clip_id: Optional[str] = Field(None, description="Optional clip ID to use instead of full episode")
    metadata_overrides: Optional[Dict[str, Any]] = Field(None, description="Override metadata values")


class GeneratePackagesResponse(BaseModel):
    """Response from package generation request"""
    job_id: str
    episode_id: str
    platforms: List[str]
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Job status response"""
    job_id: str
    episode_id: str
    platforms: List[str]
    status: str
    progress: float
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    packages_generated: Dict[str, str]
    errors: Dict[str, str]
    warnings: List[str]


class PlatformRequirementsResponse(BaseModel):
    """Platform requirements response"""
    platform: str
    display_name: str
    icon: str
    video: Dict[str, Any]
    metadata: Dict[str, Any]
    features: Dict[str, Any]


class PackageListResponse(BaseModel):
    """Package list response"""
    episode_id: str
    packages: List[Dict[str, Any]]


# Background task for package generation
def generate_packages_task(job_id: str, episode_id: str, platforms: List[str], 
                          clip_id: Optional[str], metadata_overrides: Optional[Dict[str, Any]]):
    """
    Background task to generate social media packages
    
    Args:
        job_id: Job identifier
        episode_id: Episode identifier
        platforms: List of target platforms
        clip_id: Optional clip ID
        metadata_overrides: Optional metadata overrides
    """
    try:
        logger.info(f"Starting package generation job {job_id} for episode {episode_id}")
        
        # Update job status to processing
        job_tracker.update_job_status(job_id, SocialJobStatus.PROCESSING, progress=0.0)
        
        # Get episode data
        episode = registry.get_episode(episode_id)
        if not episode:
            job_tracker.update_job_status(
                job_id, 
                SocialJobStatus.FAILED,
                errors={"general": f"Episode {episode_id} not found"}
            )
            return
        
        # Prepare content dictionary
        content = _prepare_content(episode, clip_id, metadata_overrides)
        
        # Generate packages for each platform
        packages_generated = {}
        errors = {}
        warnings = []
        total_platforms = len(platforms)
        
        for idx, platform in enumerate(platforms):
            try:
                logger.info(f"Generating {platform} package for {episode_id}")
                
                # Generate package
                result = package_generator.generate_package(platform, episode_id, content)
                
                if result.success:
                    packages_generated[platform] = result.package_path
                    warnings.extend(result.warnings)
                    logger.info(f"Successfully generated {platform} package: {result.package_path}")
                else:
                    errors[platform] = "; ".join(result.errors)
                    logger.error(f"Failed to generate {platform} package: {result.errors}")
                
                # Update progress
                progress = ((idx + 1) / total_platforms) * 100
                job_tracker.update_job_status(
                    job_id,
                    SocialJobStatus.PROCESSING,
                    progress=progress,
                    packages_generated=packages_generated,
                    errors=errors,
                    warnings=warnings
                )
                
            except Exception as e:
                logger.error(f"Error generating {platform} package: {e}", exc_info=True)
                errors[platform] = str(e)
        
        # Determine final status
        if errors and not packages_generated:
            final_status = SocialJobStatus.FAILED
        elif errors:
            final_status = SocialJobStatus.COMPLETED  # Partial success
        else:
            final_status = SocialJobStatus.COMPLETED
        
        # Update final job status
        job_tracker.update_job_status(
            job_id,
            final_status,
            progress=100.0,
            packages_generated=packages_generated,
            errors=errors,
            warnings=warnings
        )
        
        logger.info(f"Completed package generation job {job_id} with status {final_status.value}")
        
    except Exception as e:
        logger.error(f"Fatal error in package generation job {job_id}: {e}", exc_info=True)
        job_tracker.update_job_status(
            job_id,
            SocialJobStatus.FAILED,
            errors={"general": str(e)}
        )


def _prepare_content(episode: Any, clip_id: Optional[str], 
                     metadata_overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Prepare content dictionary for package generation
    
    Args:
        episode: Episode object
        clip_id: Optional clip ID
        metadata_overrides: Optional metadata overrides
    
    Returns:
        Content dictionary
    """
    # Extract episode metadata
    enrichment = episode.enrichment or {}
    transcription = episode.transcription or {}
    
    # Build base metadata
    metadata = {
        'title': episode.title or enrichment.get('title', ''),
        'show_name': episode.show or enrichment.get('show_name', ''),
        'guests': enrichment.get('enriched_guests', []),
        'topics': enrichment.get('topics', []),
        'summary': enrichment.get('executive_summary', ''),
        'hook_line': _generate_hook_line(enrichment),
        'canonical_url': f"https://example.com/episodes/{episode.episode_id}",
        'hashtags': _generate_hashtags(enrichment)
    }
    
    # Apply overrides
    if metadata_overrides:
        metadata.update(metadata_overrides)
    
    # Video information
    video = {
        'source_path': episode.source_path,
        'duration_seconds': episode.duration or 0,
        'aspect_ratio': '16:9'  # Default, should be detected from video
    }
    
    # If clip_id specified, use clip instead of full episode
    if clip_id:
        # TODO: Implement clip-specific content extraction
        pass
    
    return {
        'episode_id': episode.episode_id,
        'video': video,
        'metadata': metadata,
        'enrichment': enrichment,
        'transcription': transcription
    }


def _generate_hook_line(enrichment: Dict[str, Any]) -> str:
    """Generate a hook line from enrichment data"""
    key_takeaways = enrichment.get('key_takeaways', [])
    if key_takeaways:
        return key_takeaways[0]
    
    summary = enrichment.get('executive_summary', '')
    if summary:
        # Take first sentence
        sentences = summary.split('.')
        if sentences:
            return sentences[0].strip() + '.'
    
    return "Check out this episode!"


def _generate_hashtags(enrichment: Dict[str, Any]) -> List[str]:
    """Generate hashtags from enrichment data"""
    hashtags = []
    
    # Add topic hashtags
    topics = enrichment.get('topics', [])
    for topic in topics[:5]:  # Limit to 5 topics
        # Clean and format topic as hashtag
        clean_topic = topic.replace(' ', '').replace('-', '').replace('_', '')
        hashtags.append(f"#{clean_topic}")
    
    # Add guest hashtags
    guests = enrichment.get('enriched_guests', [])
    for guest in guests[:2]:  # Limit to 2 guests
        guest_name = guest.get('name', '').replace(' ', '')
        if guest_name:
            hashtags.append(f"#{guest_name}")
    
    return hashtags


# API Endpoints
@router.post("/generate", response_model=GeneratePackagesResponse)
async def generate_social_packages(
    request: GeneratePackagesRequest,
    background_tasks: BackgroundTasks
) -> GeneratePackagesResponse:
    """
    Generate social media packages for an episode
    
    Creates packages for specified platforms with platform-specific transformations.
    Returns immediately with job_id for tracking progress.
    """
    try:
        # Get components
        policy_engine, package_generator, job_tracker, registry = _get_components()
        
        # Validate platforms
        available_platforms = policy_engine.list_platforms()
        invalid_platforms = [p for p in request.platforms if p not in available_platforms]
        if invalid_platforms:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid platforms: {', '.join(invalid_platforms)}. Available: {', '.join(available_platforms)}"
            )
        
        # Verify episode exists
        episode = registry.get_episode(request.episode_id)
        if not episode:
            raise HTTPException(status_code=404, detail=f"Episode {request.episode_id} not found")
        
        # Create job
        job_id = job_tracker.create_job(
            episode_id=request.episode_id,
            platforms=request.platforms,
            metadata={
                'clip_id': request.clip_id,
                'metadata_overrides': request.metadata_overrides
            }
        )
        
        # Start background task
        background_tasks.add_task(
            generate_packages_task,
            job_id,
            request.episode_id,
            request.platforms,
            request.clip_id,
            request.metadata_overrides
        )
        
        return GeneratePackagesResponse(
            job_id=job_id,
            episode_id=request.episode_id,
            platforms=request.platforms,
            status="pending",
            message=f"Package generation started. Track progress at /social/jobs/{job_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting package generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """
    Get status of a package generation job
    
    Returns current status, progress, and results.
    """
    _, _, job_tracker, _ = _get_components()
    job = job_tracker.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return JobStatusResponse(
        job_id=job.job_id,
        episode_id=job.episode_id,
        platforms=job.platforms,
        status=job.status.value,
        progress=job.progress,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        packages_generated=job.packages_generated,
        errors=job.errors,
        warnings=job.warnings
    )


@router.get("/jobs", response_model=List[JobStatusResponse])
async def list_jobs(
    episode_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
) -> List[JobStatusResponse]:
    """
    List package generation jobs
    
    Optionally filter by episode_id or status.
    """
    _, _, job_tracker, _ = _get_components()
    
    try:
        status_filter = SocialJobStatus(status) if status else None
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    jobs = job_tracker.list_jobs(episode_id=episode_id, status=status_filter, limit=limit)
    
    return [
        JobStatusResponse(
            job_id=job.job_id,
            episode_id=job.episode_id,
            platforms=job.platforms,
            status=job.status.value,
            progress=job.progress,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
            packages_generated=job.packages_generated,
            errors=job.errors,
            warnings=job.warnings
        )
        for job in jobs
    ]


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str) -> Dict[str, str]:
    """Delete a job"""
    _, _, job_tracker, _ = _get_components()
    success = job_tracker.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return {"message": f"Job {job_id} deleted successfully"}


@router.get("/platforms", response_model=List[str])
async def list_platforms() -> List[str]:
    """List available platforms"""
    policy_engine, _, _, _ = _get_components()
    return policy_engine.list_platforms()


@router.get("/platforms/{platform}", response_model=PlatformRequirementsResponse)
async def get_platform_requirements(platform: str) -> PlatformRequirementsResponse:
    """
    Get requirements and specifications for a platform
    
    Returns video specs, metadata limits, and feature support.
    """
    policy_engine, _, _, _ = _get_components()
    requirements = policy_engine.get_platform_requirements(platform)
    if not requirements:
        raise HTTPException(status_code=404, detail=f"Platform {platform} not found")
    
    return PlatformRequirementsResponse(
        platform=platform,
        display_name=requirements['display_name'],
        icon=requirements['icon'],
        video=requirements['video'],
        metadata=requirements['metadata'],
        features=requirements['features']
    )


@router.get("/packages/{episode_id}", response_model=PackageListResponse)
async def list_episode_packages(episode_id: str) -> PackageListResponse:
    """
    List all generated packages for an episode
    
    Returns package paths and metadata for each platform.
    """
    _, package_generator, _, _ = _get_components()
    packages = package_generator.list_packages(episode_id=episode_id)
    
    if episode_id not in packages:
        return PackageListResponse(episode_id=episode_id, packages=[])
    
    return PackageListResponse(
        episode_id=episode_id,
        packages=packages[episode_id]
    )


@router.delete("/packages/{episode_id}/{platform}")
async def delete_package(episode_id: str, platform: str) -> Dict[str, str]:
    """Delete a generated package"""
    _, package_generator, _, _ = _get_components()
    success = package_generator.delete_package(episode_id, platform)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Package not found for episode {episode_id} and platform {platform}"
        )
    
    return {"message": f"Package deleted successfully"}


@router.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """Get social media publishing statistics"""
    _, _, job_tracker, _ = _get_components()
    return job_tracker.get_stats()
