"""
Main pipeline orchestrator for the Video Processing Pipeline

Coordinates all processing stages with checkpoint recovery, batch processing,
and comprehensive error handling and monitoring.
"""

import asyncio
import time
import threading
import hashlib
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from .config import PipelineConfig, ConfigurationManager
from .logging import get_logger, PipelineLogger
from .database import DatabaseManager, create_database_manager
from .registry import EpisodeRegistry, create_episode_registry
from .models import ProcessingStage
from .exceptions import (
    PipelineError, 
    ProcessingError, 
    ConfigurationError,
    TransientError
)
from .reliability_integration import (
    pipeline_reliability, 
    initialize_reliability,
    shutdown_reliability,
    reliability_context,
    PipelineReliabilityConfig
)

logger = get_logger('pipeline.orchestrator')


@dataclass
class ProcessingResult:
    """Result of processing an episode through a stage"""
    success: bool
    stage: ProcessingStage
    episode_id: str
    duration: float
    error: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


@dataclass
class BatchProcessingStats:
    """Statistics for batch processing operations"""
    total_episodes: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time if self.end_time > 0 else time.time() - self.start_time
    
    @property
    def success_rate(self) -> float:
        return self.processed / max(1, self.total_episodes)


class PipelineOrchestrator:
    """
    Main orchestrator for the video processing pipeline
    
    Manages stage-by-stage processing with checkpoint recovery,
    batch processing, and comprehensive monitoring.
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None, config_path: Optional[str] = None):
        """
        Initialize the pipeline orchestrator
        
        Args:
            config: Pre-loaded configuration object
            config_path: Path to configuration file
        """
        if config:
            self.config = config
        else:
            config_manager = ConfigurationManager(config_path)
            self.config = config_manager.load_config()
        
        self.logger = logger
        self._stage_processors: Dict[ProcessingStage, Callable] = {}
        self._processing_stats = BatchProcessingStats()
        self._shutdown_requested = False
        self._stage_data: Dict[str, Dict[str, Any]] = {}  # Store data between stages
        
        # Initialize database and registry
        self.db_manager: Optional[DatabaseManager] = None
        self.registry: Optional[EpisodeRegistry] = None
        self._backup_thread: Optional[threading.Thread] = None
        self._last_backup_time: Optional[datetime] = None
        
        # Initialize reliability features
        reliability_config = PipelineReliabilityConfig(
            max_concurrent_episodes=self.config.processing.max_concurrent_episodes,
            max_retry_attempts=self.config.processing.max_retry_attempts,
            retry_base_delay=self.config.processing.retry_delay_seconds,
            max_memory_percent=self.config.resources.max_memory_percent,
            max_cpu_percent=self.config.resources.max_cpu_percent
        )
        initialize_reliability(reliability_config)
        
        # Initialize stage processor registry
        self._register_stage_processors()
    
    def _register_stage_processors(self) -> None:
        """Register processing functions for each stage"""
        # These will be implemented in subsequent tasks
        # For now, we define the interface
        self._stage_processors = {
            ProcessingStage.DISCOVERED: self._process_discovery_stage,
            ProcessingStage.PREPPED: self._process_prep_stage,
            ProcessingStage.TRANSCRIBED: self._process_transcription_stage,
            ProcessingStage.ENRICHED: self._process_enrichment_stage,
            ProcessingStage.RENDERED: self._process_rendering_stage
        }
    
    async def process_episode(self, episode_id: str, target_stage: ProcessingStage = ProcessingStage.RENDERED, force_reprocess: bool = False) -> ProcessingResult:
        """
        Process a single episode through the pipeline stages
        
        Args:
            episode_id: Unique identifier for the episode
            target_stage: Final stage to process to
            force_reprocess: If True, reprocess even if already at target stage
            
        Returns:
            ProcessingResult: Result of the processing operation
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Starting episode processing", 
                           episode_id=episode_id, 
                           target_stage=target_stage.value,
                           force_reprocess=force_reprocess)
            
            # Get current stage for episode (or discover if not found)
            try:
                current_stage = await self._get_episode_stage(episode_id)
            except ProcessingError as e:
                if "not found" in str(e):
                    # Episode doesn't exist - discover it first
                    self.logger.info(f"Episode not found, running discovery first", episode_id=episode_id)
                    await self.discover_episodes()
                    # Try again after discovery
                    current_stage = await self._get_episode_stage(episode_id)
                else:
                    raise
            
            # If force_reprocess, start from discovered stage
            if force_reprocess:
                current_stage = ProcessingStage.DISCOVERED
                self.logger.info(f"Force reprocessing - resetting to discovered stage", episode_id=episode_id)
            
            # Process through each required stage
            stages_to_process = self._get_stages_to_process(current_stage, target_stage)
            
            self.logger.info(f"Stages to process: {[s.value for s in stages_to_process]}", 
                           episode_id=episode_id,
                           current_stage=current_stage.value,
                           target_stage=target_stage.value)
            
            for stage in stages_to_process:
                if self._shutdown_requested:
                    raise ProcessingError("Processing interrupted by shutdown request", 
                                        stage=stage.value, episode_id=episode_id)
                
                self.logger.info(f"Processing stage: {stage.value}", episode_id=episode_id)
                stage_result = await self._process_stage(episode_id, stage)
                self.logger.info(f"Stage completed: {stage.value}, success={stage_result.success}", 
                               episode_id=episode_id, duration=stage_result.duration)
                
                if not stage_result.success:
                    return stage_result
            
            duration = time.time() - start_time
            
            result = ProcessingResult(
                success=True,
                stage=target_stage,
                episode_id=episode_id,
                duration=duration
            )
            
            self.logger.info(f"Episode processing completed successfully", 
                           episode_id=episode_id, 
                           duration=duration,
                           target_stage=target_stage.value)
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            
            self.logger.error(f"Episode processing failed", 
                            exception=e,
                            episode_id=episode_id, 
                            duration=duration)
            
            return ProcessingResult(
                success=False,
                stage=target_stage,
                episode_id=episode_id,
                duration=duration,
                error=error_msg
            )
    
    async def process_batch(self, episode_ids: List[str], 
                          target_stage: ProcessingStage = ProcessingStage.RENDERED,
                          max_concurrent: Optional[int] = None,
                          progress_callback: Optional[Callable] = None) -> BatchProcessingStats:
        """
        Process multiple episodes concurrently
        
        Args:
            episode_ids: List of episode IDs to process
            target_stage: Final stage to process to
            max_concurrent: Maximum concurrent episodes (defaults to config value)
            
        Returns:
            BatchProcessingStats: Statistics for the batch operation
        """
        if max_concurrent is None:
            max_concurrent = self.config.processing.max_concurrent_episodes
        
        stats = BatchProcessingStats(
            total_episodes=len(episode_ids),
            start_time=time.time()
        )
        
        self.logger.info(f"Starting batch processing", 
                        total_episodes=len(episode_ids),
                        max_concurrent=max_concurrent,
                        target_stage=target_stage.value)
        
        # Process episodes with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(episode_id: str) -> ProcessingResult:
            async with semaphore:
                result = await self.process_episode(episode_id, target_stage)
                
                # Call progress callback if provided
                if progress_callback:
                    progress_callback(episode_id, result)
                
                return result
        
        # Execute all tasks
        tasks = [process_with_semaphore(episode_id) for episode_id in episode_ids]
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Analyze results
            for result in results:
                if isinstance(result, Exception):
                    stats.failed += 1
                    self.logger.error("Batch processing task failed", exception=result)
                elif isinstance(result, ProcessingResult):
                    if result.success:
                        stats.processed += 1
                    else:
                        stats.failed += 1
                else:
                    stats.failed += 1
            
        except Exception as e:
            self.logger.error("Batch processing failed", exception=e)
            stats.failed = len(episode_ids) - stats.processed
        
        stats.end_time = time.time()
        
        self.logger.info(f"Batch processing completed", 
                        **{
                            'total': stats.total_episodes,
                            'processed': stats.processed,
                            'failed': stats.failed,
                            'duration': stats.duration,
                            'success_rate': stats.success_rate
                        })
        
        return stats
    
    async def _process_stage(self, episode_id: str, stage: ProcessingStage) -> ProcessingResult:
        """Process a single stage for an episode"""
        start_time = time.time()
        
        try:
            # Use reliability context for protected execution
            with reliability_context(episode_id, stage) as reliability_manager:
                self.logger.info(f"Processing stage {stage.value}", 
                               episode_id=episode_id, 
                               stage=stage.value)
                
                # Get the processor for this stage
                processor = self._stage_processors.get(stage)
                if not processor:
                    raise ProcessingError(f"No processor registered for stage {stage.value}",
                                        stage=stage.value, episode_id=episode_id)
                
                # Execute the stage processor
                await processor(episode_id)
                
                # Update episode stage (placeholder - will be implemented in registry task)
                await self._update_episode_stage(episode_id, stage)
                
                duration = time.time() - start_time
                
                # Log processing decision
                reliability_manager.log_processing_decision(
                    episode_id=episode_id,
                    stage=stage.value,
                    decision="stage_completed",
                    reasoning=f"Successfully processed {stage.value} stage",
                    metadata={"duration": duration}
                )
                
                result = ProcessingResult(
                    success=True,
                    stage=stage,
                    episode_id=episode_id,
                    duration=duration
                )
                
                self.logger.log_processing_event(episode_id, stage.value, "completed", duration)
                return result
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            
            self.logger.log_processing_event(episode_id, stage.value, "failed", duration, error_msg)
            
            return ProcessingResult(
                success=False,
                stage=stage,
                episode_id=episode_id,
                duration=duration,
                error=error_msg
            )
    
    def _get_stages_to_process(self, current_stage: ProcessingStage, 
                             target_stage: ProcessingStage) -> List[ProcessingStage]:
        """Determine which stages need to be processed"""
        all_stages = list(ProcessingStage)
        
        try:
            current_index = all_stages.index(current_stage)
            target_index = all_stages.index(target_stage)
        except ValueError as e:
            raise ProcessingError(f"Invalid stage: {e}")
        
        if target_index <= current_index:
            return []  # Already at or past target stage
        
        return all_stages[current_index + 1:target_index + 1]
    
    def request_shutdown(self) -> None:
        """Request graceful shutdown of processing"""
        self.logger.info("Shutdown requested")
        self._shutdown_requested = True
        
        # Shutdown reliability features
        shutdown_reliability()
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status"""
        from .reliability_integration import get_pipeline_health
        return get_pipeline_health()
    
    def export_metrics(self, format_type: str = "json") -> str:
        """Export comprehensive pipeline metrics"""
        from .reliability_integration import export_pipeline_metrics
        return export_pipeline_metrics(format_type)
    
    def get_processing_stats(self) -> BatchProcessingStats:
        """Get current processing statistics"""
        return self._processing_stats
    
    # Stage processors - implement actual processing logic
    async def _process_discovery_stage(self, episode_id: str) -> None:
        """Process discovery stage - already handled during registration"""
        self.logger.debug(f"Discovery stage processor called", episode_id=episode_id)
        # Episode is already discovered and registered in database
        pass
    
    async def _process_prep_stage(self, episode_id: str) -> None:
        """Process media preparation stage - extract audio"""
        from ..stages.prep_stage import PrepStageProcessor
        
        self.logger.info("Processing prep stage", episode_id=episode_id)
        
        # Get episode from registry
        episode = self.registry.get_episode(episode_id)
        if not episode:
            raise ProcessingError(f"Episode not found: {episode_id}")
        
        # Run prep processor
        processor = PrepStageProcessor()
        result = await processor.process(episode)
        
        # Update episode with audio path and media info
        if result['success']:
            self.logger.info("Prep stage completed", 
                           episode_id=episode_id,
                           audio_path=result['audio_path'])
    
    async def _process_transcription_stage(self, episode_id: str) -> None:
        """Process transcription stage - run Whisper"""
        from ..stages.transcription_stage import TranscriptionStageProcessor
        
        self.logger.info("Processing transcription stage", episode_id=episode_id)
        
        # Get episode
        episode = self.registry.get_episode(episode_id)
        if not episode:
            raise ProcessingError(f"Episode not found: {episode_id}")
        
        # Find audio path
        audio_path = f"data/audio/{episode_id}.wav"
        
        # Run transcription processor
        processor = TranscriptionStageProcessor(model_name=self.config.models.whisper)
        result = await processor.process(episode, audio_path)
        
        # Store transcript data for next stage
        self._stage_data[episode_id] = {'transcript': result}
        
        if result['success']:
            self.logger.info("Transcription stage completed",
                           episode_id=episode_id,
                           word_count=result.get('word_count', 0))
    
    async def _process_enrichment_stage(self, episode_id: str) -> None:
        """Process enrichment stage - run intelligence chain"""
        from ..stages.enrichment_stage import EnrichmentStageProcessor
        
        self.logger.info("Processing enrichment stage", episode_id=episode_id)
        
        # Get episode and transcript data
        episode = self.registry.get_episode(episode_id)
        if not episode:
            raise ProcessingError(f"Episode not found: {episode_id}")
        
        audio_path = f"data/audio/{episode_id}.wav"
        transcript_data = self._stage_data.get(episode_id, {}).get('transcript', {})
        
        # Run enrichment processor with config for Intelligence Chain V2
        processor = EnrichmentStageProcessor(
            config=self.config,
            intelligence_chain_enabled=True  # Enable Phase 2 features
        )
        result = await processor.process(episode, audio_path, transcript_data)
        
        # Store enrichment data for next stage
        if episode_id not in self._stage_data:
            self._stage_data[episode_id] = {}
        self._stage_data[episode_id]['enrichment'] = result
        
        if result['success']:
            self.logger.info("Enrichment stage completed",
                           episode_id=episode_id)
    
    async def _process_rendering_stage(self, episode_id: str) -> None:
        """Process rendering stage - generate web artifacts"""
        from ..stages.rendering_stage import RenderingStageProcessor
        
        self.logger.info("Processing rendering stage", episode_id=episode_id)
        
        # Get episode and all stage data
        episode = self.registry.get_episode(episode_id)
        if not episode:
            raise ProcessingError(f"Episode not found: {episode_id}")
        
        stage_data = self._stage_data.get(episode_id, {})
        transcript_data = stage_data.get('transcript', {})
        enrichment_data = stage_data.get('enrichment', {})
        
        # Run rendering processor
        processor = RenderingStageProcessor()
        result = await processor.process(episode, transcript_data, enrichment_data)
        
        # Clean up stage data
        if episode_id in self._stage_data:
            del self._stage_data[episode_id]
        
        if result['success']:
            self.logger.info("Rendering stage completed",
                           episode_id=episode_id,
                           html_path=result.get('html_path'))
    
    def initialize_database(self) -> None:
        """Initialize database and registry"""
        try:
            self.db_manager = create_database_manager(self.config.database)
            self.registry = create_episode_registry(self.db_manager)
            
            # Start automatic backup if enabled
            if self.config.database.backup_enabled:
                self._start_backup_scheduler()
            
            logger.info("Database and registry initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize database and registry", error=str(e))
            raise ProcessingError(f"Database initialization failed: {e}")
    
    def get_registry(self) -> EpisodeRegistry:
        """Get episode registry (initialize if needed)"""
        if not self.registry:
            self.initialize_database()
        return self.registry
    
    # Registry integration methods
    async def _get_episode_stage(self, episode_id: str) -> ProcessingStage:
        """
        Get current processing stage for episode
        
        Tries multiple strategies to find the episode:
        1. Direct episode_id lookup
        2. Filename-based lookup (for cross-platform path issues)
        """
        from .path_utils import get_filename_from_path
        
        registry = self.get_registry()
        episode = registry.get_episode(episode_id)
        
        if not episode:
            # Try filename-based lookup as fallback
            # Extract potential filename from episode_id
            # e.g., "newsroom-2024-oss096" -> look for "oss096.mp4"
            parts = episode_id.split('-')
            if len(parts) >= 3:
                potential_filename = parts[-1]  # Last part is usually the filename
                
                # Try with common video extensions
                for ext in ['.mp4', '.mkv', '.avi', '.mov']:
                    filename = f"{potential_filename}{ext}"
                    episode = registry.find_episode_by_filename(filename)
                    if episode:
                        self.logger.info(f"Found episode by filename: {episode_id} -> {episode.episode_id}")
                        return episode.processing_stage
            
            raise ProcessingError(f"Episode not found: {episode_id}")
        
        return episode.processing_stage
    
    async def _update_episode_stage(self, episode_id: str, stage: ProcessingStage) -> None:
        """Update processing stage for episode"""
        registry = self.get_registry()
        registry.update_episode_stage(episode_id, stage)
        
        self.logger.debug(f"Stage updated", episode_id=episode_id, stage=stage.value)
    
    def get_episode_status(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed status for a specific episode"""
        try:
            registry = self.get_registry()
            episode = registry.get_episode(episode_id)
            
            if not episode:
                return None
            
            return {
                'episode_id': episode.episode_id,
                'stage': episode.processing_stage.value,
                'created_at': episode.created_at.isoformat() if episode.created_at else None,
                'updated_at': episode.updated_at.isoformat() if episode.updated_at else None,
                'errors': episode.errors,
                'source_path': episode.source.path,
                'file_size': episode.source.file_size,
                'show_name': episode.metadata.show_name
            }
        except Exception as e:
            self.logger.error(f"Error getting episode status", episode_id=episode_id, error=str(e))
            return None
    
    async def discover_episodes(self) -> List:
        """
        Discover video episodes from configured source directories
        
        Scans all enabled source paths for video files and registers them
        in the database with file hash, size, and duration for deduplication.
        
        Returns:
            List of discovered Episode objects
        """
        from pathlib import Path
        from .models import EpisodeObject, SourceInfo, MediaInfo, EpisodeMetadata
        from datetime import datetime
        from .path_utils import normalize_path
        import hashlib
        import subprocess
        import json
        
        self.logger.info("Starting episode discovery")
        
        # Initialize registry if needed
        registry = self.get_registry()
        
        discovered_episodes = []
        
        # Get enabled sources from config
        for source in self.config.sources:
            if not source.enabled:
                continue
            
            # Normalize path for cross-platform compatibility
            source_path = normalize_path(source.path)
            if not source_path.exists():
                self.logger.warning(f"Source path does not exist: {source_path}")
                continue
            
            self.logger.info(f"Scanning source: {source_path}")
            
            # Find video files
            video_files = []
            for pattern in source.include:
                video_files.extend(source_path.glob(pattern))
            
            # Register each video
            for video_file in video_files:
                # Skip excluded patterns
                if any(video_file.match(exclude) for exclude in source.exclude):
                    continue
                
                # Generate episode ID
                filename = video_file.stem
                show_name = video_file.parent.parent.name  # e.g., "newsroom"
                year = video_file.parent.name  # e.g., "2024"
                episode_id = f"{show_name}-{year}-{filename.lower()}"
                
                # Calculate file hash for content-based deduplication
                file_hash = self._calculate_file_hash(video_file)
                file_size = video_file.stat().st_size
                last_modified = datetime.fromtimestamp(video_file.stat().st_mtime)
                
                # Check if file with same hash already exists (duplicate content)
                existing_by_hash = registry.get_episode_by_hash(file_hash)
                if existing_by_hash:
                    self.logger.info(f"Duplicate file detected: {video_file.name} matches {existing_by_hash.episode_id}")
                    # Update source path if different
                    if existing_by_hash.source.path != str(video_file):
                        registry.update_episode_source_path(existing_by_hash.episode_id, str(video_file))
                    discovered_episodes.append(existing_by_hash)
                    continue
                
                # Check if episode ID already exists
                existing = registry.get_episode(episode_id)
                if existing:
                    # Episode ID exists - check if it's the same file
                    if existing.content_hash == file_hash:
                        self.logger.debug(f"Episode already exists: {episode_id}")
                        discovered_episodes.append(existing)
                        continue
                    else:
                        # Same ID but different file - file was replaced
                        self.logger.warning(f"File content changed for {episode_id}, updating hash")
                        registry.update_episode_hash(episode_id, file_hash, file_size, last_modified)
                        discovered_episodes.append(existing)
                        continue
                
                # Extract video duration using ffprobe
                duration = self._get_video_duration(video_file)
                
                # Create episode object
                episode = EpisodeObject(
                    episode_id=episode_id,
                    content_hash=file_hash,
                    processing_stage=ProcessingStage.DISCOVERED,
                    source=SourceInfo(
                        path=str(video_file),
                        file_size=file_size,
                        last_modified=last_modified
                    ),
                    media=MediaInfo(
                        duration_seconds=duration
                    ),
                    metadata=EpisodeMetadata(
                        show_name=show_name,
                        show_slug=show_name.lower(),
                        title=filename
                    )
                )
                
                # Register in database
                registry.register_episode(episode)
                discovered_episodes.append(episode)
                
                self.logger.info(f"Discovered episode: {episode_id}")
        
        self.logger.info(f"Discovery complete: {len(discovered_episodes)} episodes")
        return discovered_episodes
    
    def _calculate_file_hash(self, file_path: Path, algorithm: str = 'sha256') -> str:
        """
        Calculate hash of file content for deduplication
        
        Uses SHA256 by default for better collision resistance than MD5.
        Reads file in chunks to handle large video files efficiently.
        
        Args:
            file_path: Path to the file
            algorithm: Hash algorithm ('md5', 'sha256', 'sha512')
            
        Returns:
            Hexadecimal hash string
        """
        hash_func = hashlib.new(algorithm)
        
        try:
            with open(file_path, 'rb') as f:
                # Read in 64KB chunks to handle large files
                for chunk in iter(lambda: f.read(65536), b''):
                    hash_func.update(chunk)
            
            file_hash = hash_func.hexdigest()
            self.logger.debug(f"Calculated {algorithm} hash for {file_path.name}", hash=file_hash[:16])
            return file_hash
            
        except Exception as e:
            self.logger.error(f"Failed to calculate hash for {file_path}", error=str(e))
            # Fallback to path-based hash if file can't be read
            return hashlib.md5(str(file_path).encode()).hexdigest()
    
    def _get_video_duration(self, file_path: Path) -> Optional[float]:
        """
        Extract video duration using ffprobe
        
        Args:
            file_path: Path to video file
            
        Returns:
            Duration in seconds, or None if extraction fails
        """
        try:
            import subprocess
            import json
            
            # Use ffprobe to get video duration
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(file_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                # Try to get duration from format first
                if 'format' in data and 'duration' in data['format']:
                    duration = float(data['format']['duration'])
                    self.logger.debug(f"Extracted duration for {file_path.name}", duration=duration)
                    return duration
                
                # Fallback to video stream duration
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'video' and 'duration' in stream:
                        duration = float(stream['duration'])
                        self.logger.debug(f"Extracted duration from stream for {file_path.name}", duration=duration)
                        return duration
            
            self.logger.warning(f"Could not extract duration for {file_path.name}")
            return None
            
        except subprocess.TimeoutExpired:
            self.logger.warning(f"ffprobe timeout for {file_path.name}")
            return None
        except Exception as e:
            self.logger.warning(f"Failed to extract duration for {file_path.name}", error=str(e))
            return None
    
    def list_episodes(self, stage_filter: Optional[ProcessingStage] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """List episodes with optional filtering"""
        try:
            registry = self.get_registry()
            # This would use registry methods when implemented
            # For now, return empty list
            return []
        except Exception as e:
            self.logger.error(f"Error listing episodes", error=str(e))
            return []
    
    def _start_backup_scheduler(self) -> None:
        """Start automatic database backup scheduler"""
        import threading
        
        def backup_worker():
            """Background worker for periodic backups"""
            while not self._shutdown_requested:
                try:
                    # Calculate next backup time
                    if self._last_backup_time:
                        hours_since_backup = (datetime.now() - self._last_backup_time).total_seconds() / 3600
                        if hours_since_backup < self.config.database.backup_interval_hours:
                            # Sleep until next backup time
                            sleep_seconds = (self.config.database.backup_interval_hours - hours_since_backup) * 3600
                            time.sleep(min(sleep_seconds, 300))  # Check every 5 minutes max
                            continue
                    
                    # Perform backup
                    self._perform_backup()
                    
                except Exception as e:
                    logger.error("Error in backup scheduler", error=str(e))
                    time.sleep(300)  # Wait 5 minutes before retrying
        
        # Start backup thread
        self._backup_thread = threading.Thread(target=backup_worker, daemon=True, name="DatabaseBackup")
        self._backup_thread.start()
        logger.info("Database backup scheduler started", 
                   interval_hours=self.config.database.backup_interval_hours)
    
    def _perform_backup(self) -> None:
        """Perform database backup"""
        try:
            if not self.db_manager:
                logger.warning("Cannot backup - database not initialized")
                return
            
            # Create backup
            backup_path = self.db_manager.backup_database()
            self._last_backup_time = datetime.now()
            
            logger.info("Database backup completed successfully",
                       backup_path=backup_path,
                       next_backup=self._last_backup_time + timedelta(hours=self.config.database.backup_interval_hours))
            
            # Clean up old backups (keep last 7 days)
            self._cleanup_old_backups()
            
        except Exception as e:
            logger.error("Database backup failed", error=str(e))
    
    def _cleanup_old_backups(self, keep_days: int = 7) -> None:
        """Clean up old backup files"""
        try:
            from pathlib import Path
            
            backup_dir = Path(self.config.database.path).parent
            cutoff_time = datetime.now() - timedelta(days=keep_days)
            
            # Find and delete old backups
            deleted_count = 0
            for backup_file in backup_dir.glob("*_backup_*.db"):
                if backup_file.stat().st_mtime < cutoff_time.timestamp():
                    backup_file.unlink()
                    deleted_count += 1
                    logger.debug("Deleted old backup", backup_file=str(backup_file))
            
            if deleted_count > 0:
                logger.info("Cleaned up old backups", deleted_count=deleted_count)
                
        except Exception as e:
            logger.warning("Failed to cleanup old backups", error=str(e))
    
    def shutdown(self) -> None:
        """Shutdown orchestrator and cleanup resources"""
        self._shutdown_requested = True
        
        # Perform final backup before shutdown
        if self.config.database.backup_enabled and self.db_manager:
            logger.info("Performing final backup before shutdown")
            self._perform_backup()
        
        # Wait for backup thread to finish
        if self._backup_thread and self._backup_thread.is_alive():
            self._backup_thread.join(timeout=10)
        
        # Close database connections
        if self.db_manager:
            self.db_manager.close()
        
        logger.info("Pipeline orchestrator shutdown complete")