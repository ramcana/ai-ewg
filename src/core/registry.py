"""
Episode registry for the Video Processing Pipeline

Manages episode registration, deduplication, and processing stage tracking
using SQLite database with atomic operations and referential integrity.
"""

import json
import sqlite3
import time
from datetime import datetime
from typing import Dict, List, Optional, Set, Any, Tuple
from pathlib import Path

from .database import DatabaseManager, DatabaseConnection
from .models import (
    EpisodeObject, ProcessingStage, ProcessingEvent, 
    SourceInfo, MediaInfo, EpisodeMetadata,
    TranscriptionResult, EnrichmentResult, EditorialContent
)
from .exceptions import DatabaseError, ValidationError, ProcessingError
from .logging import get_logger

logger = get_logger('pipeline.registry')


class EpisodeRegistry:
    """
    Registry for managing episodes with hash-based deduplication
    
    Provides atomic operations for episode registration, stage tracking,
    and referential integrity enforcement.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.connection = db_manager.get_connection()
    
    def register_episode(self, episode: EpisodeObject) -> bool:
        """
        Register a new episode with deduplication check
        
        Args:
            episode: Episode object to register
            
        Returns:
            bool: True if episode was registered, False if duplicate exists
            
        Raises:
            DatabaseError: If database operation fails
            ValidationError: If episode data is invalid
        """
        try:
            # Validate episode data
            self._validate_episode(episode)
            
            # Check for existing episode with same hash
            if self.is_duplicate(episode.content_hash):
                existing_episode = self.get_episode_by_hash(episode.content_hash)
                logger.info("Duplicate episode detected",
                           episode_id=episode.episode_id,
                           existing_id=existing_episode.episode_id if existing_episode else "unknown",
                           content_hash=episode.content_hash)
                return False
            
            # Check for episode ID collision
            if self.episode_exists(episode.episode_id):
                # Generate unique ID by appending suffix
                episode.episode_id = self._generate_unique_episode_id(episode.episode_id)
                logger.info("Episode ID collision resolved",
                           original_id=episode.metadata.generate_episode_id(),
                           unique_id=episode.episode_id)
            
            # Register episode in database
            with self.connection.transaction() as conn:
                # Insert episode record
                metadata_json = json.dumps(episode.to_dict())
                
                conn.execute("""
                    INSERT INTO episodes (
                        id, hash, stage, source_path, metadata, 
                        file_size, duration_seconds, last_modified,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    episode.episode_id,
                    episode.content_hash,
                    episode.processing_stage.value,
                    episode.source.path,
                    metadata_json,
                    episode.source.file_size,
                    episode.media.duration_seconds,
                    episode.source.last_modified.isoformat(),
                    episode.created_at.isoformat(),
                    episode.updated_at.isoformat()
                ))
                
                # Log registration event
                self._log_processing_event(
                    conn, episode.episode_id, "registration", "completed"
                )
            
            logger.info("Episode registered successfully",
                       episode_id=episode.episode_id,
                       content_hash=episode.content_hash,
                       stage=episode.processing_stage.value)
            
            return True
            
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: episodes.hash" in str(e):
                logger.warning("Hash collision during registration",
                              episode_id=episode.episode_id,
                              content_hash=episode.content_hash)
                return False
            else:
                raise DatabaseError(f"Episode registration failed: {e}")
        
        except Exception as e:
            logger.error("Episode registration failed",
                        episode_id=episode.episode_id,
                        error=str(e))
            raise DatabaseError(f"Failed to register episode: {e}")
    
    def get_episode(self, episode_id: str) -> Optional[EpisodeObject]:
        """
        Retrieve episode by ID
        
        Args:
            episode_id: Unique episode identifier
            
        Returns:
            EpisodeObject or None if not found
        """
        try:
            cursor = self.connection.execute_query(
                "SELECT * FROM episodes WHERE id = ?",
                (episode_id,)
            )
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return self._row_to_episode(row)
            
        except Exception as e:
            logger.error("Failed to retrieve episode",
                        episode_id=episode_id,
                        error=str(e))
            raise DatabaseError(f"Failed to retrieve episode: {e}")
    
    def get_episode_by_hash(self, content_hash: str) -> Optional[EpisodeObject]:
        """
        Retrieve episode by content hash
        
        Args:
            content_hash: Content hash to search for
            
        Returns:
            EpisodeObject or None if not found
        """
        try:
            cursor = self.connection.execute_query(
                "SELECT * FROM episodes WHERE hash = ?",
                (content_hash,)
            )
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return self._row_to_episode(row)
            
        except Exception as e:
            logger.error("Failed to retrieve episode by hash",
                        content_hash=content_hash,
                        error=str(e))
            raise DatabaseError(f"Failed to retrieve episode by hash: {e}")
    
    def update_episode_stage(self, episode_id: str, new_stage: ProcessingStage) -> None:
        """
        Update episode processing stage atomically
        
        Args:
            episode_id: Episode to update
            new_stage: New processing stage
            
        Raises:
            DatabaseError: If update fails
            ValidationError: If episode not found
        """
        try:
            with self.connection.transaction() as conn:
                # Verify episode exists
                cursor = conn.execute(
                    "SELECT stage FROM episodes WHERE id = ?",
                    (episode_id,)
                )
                
                row = cursor.fetchone()
                if not row:
                    raise ValidationError(f"Episode not found: {episode_id}")
                
                current_stage = ProcessingStage(row[0])
                
                # Update stage and timestamp
                conn.execute("""
                    UPDATE episodes 
                    SET stage = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (new_stage.value, episode_id))
                
                # Log stage transition
                self._log_processing_event(
                    conn, episode_id, new_stage.value, "started"
                )
            
            logger.info("Episode stage updated",
                       episode_id=episode_id,
                       old_stage=current_stage.value,
                       new_stage=new_stage.value)
            
        except Exception as e:
            logger.error("Failed to update episode stage",
                        episode_id=episode_id,
                        new_stage=new_stage.value,
                        error=str(e))
            raise DatabaseError(f"Failed to update episode stage: {e}")
    
    def update_episode_data(self, episode: EpisodeObject) -> None:
        """
        Update complete episode data
        
        Args:
            episode: Updated episode object
            
        Raises:
            DatabaseError: If update fails
        """
        try:
            self._validate_episode(episode)
            
            with self.connection.transaction() as conn:
                metadata_json = json.dumps(episode.to_dict())
                
                cursor = conn.execute("""
                    UPDATE episodes SET
                        stage = ?,
                        metadata = ?,
                        errors = ?,
                        file_size = ?,
                        duration_seconds = ?,
                        last_modified = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    episode.processing_stage.value,
                    metadata_json,
                    episode.errors,
                    episode.source.file_size,
                    episode.media.duration_seconds,
                    episode.source.last_modified.isoformat(),
                    episode.episode_id
                ))
                
                if cursor.rowcount == 0:
                    raise ValidationError(f"Episode not found: {episode.episode_id}")
            
            logger.info("Episode data updated",
                       episode_id=episode.episode_id,
                       stage=episode.processing_stage.value)
            
        except Exception as e:
            logger.error("Failed to update episode data",
                        episode_id=episode.episode_id,
                        error=str(e))
            raise DatabaseError(f"Failed to update episode data: {e}")
    
    def update_episode_source_path(self, episode_id: str, new_path: str) -> None:
        """
        Update episode source path (for moved/renamed files)
        
        Args:
            episode_id: Episode identifier
            new_path: New file path
        """
        try:
            with self.connection.transaction() as conn:
                cursor = conn.execute(
                    """
                    UPDATE episodes 
                    SET source_path = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (new_path, episode_id)
                )
                
                if cursor.rowcount == 0:
                    raise DatabaseError(f"Episode not found: {episode_id}")
            
            logger.info("Updated episode source path",
                       episode_id=episode_id,
                       new_path=new_path)
            
        except Exception as e:
            logger.error("Failed to update episode source path",
                        episode_id=episode_id,
                        error=str(e))
            raise DatabaseError(f"Failed to update episode source path: {e}")
    
    def update_episode_hash(self, episode_id: str, new_hash: str, file_size: int, last_modified: datetime) -> None:
        """
        Update episode hash and file metadata (for changed files)
        
        Args:
            episode_id: Episode identifier
            new_hash: New content hash
            file_size: New file size
            last_modified: New modification timestamp
        """
        try:
            with self.connection.transaction() as conn:
                cursor = conn.execute(
                    """
                    UPDATE episodes 
                    SET hash = ?,
                        file_size = ?,
                        last_modified = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (new_hash, file_size, last_modified.isoformat(), episode_id)
                )
                
                if cursor.rowcount == 0:
                    raise DatabaseError(f"Episode not found: {episode_id}")
            
            logger.warning("Updated episode hash - file content changed",
                          episode_id=episode_id,
                          new_hash=new_hash[:16])
            
        except Exception as e:
            logger.error("Failed to update episode hash",
                        episode_id=episode_id,
                        error=str(e))
            raise DatabaseError(f"Failed to update episode hash: {e}")
    
    def get_episodes_by_stage(self, stage: ProcessingStage) -> List[EpisodeObject]:
        """
        Get all episodes at a specific processing stage
        
        Args:
            stage: Processing stage to filter by
            
        Returns:
            List of episodes at the specified stage
        """
        try:
            cursor = self.connection.execute_query(
                "SELECT * FROM episodes WHERE stage = ? ORDER BY created_at",
                (stage.value,)
            )
            
            episodes = []
            for row in cursor.fetchall():
                episodes.append(self._row_to_episode(row))
            
            return episodes
            
        except Exception as e:
            logger.error("Failed to retrieve episodes by stage",
                        stage=stage.value,
                        error=str(e))
            raise DatabaseError(f"Failed to retrieve episodes by stage: {e}")
    
    def get_episodes_needing_processing(self, target_stage: ProcessingStage) -> List[EpisodeObject]:
        """
        Get episodes that need processing to reach target stage
        
        Args:
            target_stage: Target processing stage
            
        Returns:
            List of episodes needing processing
        """
        try:
            # Get all stages before target stage
            all_stages = list(ProcessingStage)
            target_index = all_stages.index(target_stage)
            
            if target_index == 0:
                return []  # No episodes need processing to reach first stage
            
            # Get episodes at stages before target
            stage_values = [stage.value for stage in all_stages[:target_index]]
            placeholders = ','.join('?' * len(stage_values))
            
            cursor = self.connection.execute_query(
                f"SELECT * FROM episodes WHERE stage IN ({placeholders}) ORDER BY created_at",
                tuple(stage_values)
            )
            
            episodes = []
            for row in cursor.fetchall():
                episodes.append(self._row_to_episode(row))
            
            return episodes
            
        except Exception as e:
            logger.error("Failed to retrieve episodes needing processing",
                        target_stage=target_stage.value,
                        error=str(e))
            raise DatabaseError(f"Failed to retrieve episodes needing processing: {e}")
    
    def is_duplicate(self, content_hash: str) -> bool:
        """
        Check if content hash already exists
        
        Args:
            content_hash: Hash to check
            
        Returns:
            True if duplicate exists
        """
        try:
            cursor = self.connection.execute_query(
                "SELECT 1 FROM episodes WHERE hash = ? LIMIT 1",
                (content_hash,)
            )
            
            return cursor.fetchone() is not None
            
        except Exception as e:
            logger.error("Failed to check for duplicate",
                        content_hash=content_hash,
                        error=str(e))
            raise DatabaseError(f"Failed to check for duplicate: {e}")
    
    def episode_exists(self, episode_id: str) -> bool:
        """
        Check if episode ID already exists
        
        Args:
            episode_id: Episode ID to check
            
        Returns:
            True if episode exists
        """
        try:
            cursor = self.connection.execute_query(
                "SELECT 1 FROM episodes WHERE id = ? LIMIT 1",
                (episode_id,)
            )
            
            return cursor.fetchone() is not None
            
        except Exception as e:
            logger.error("Failed to check episode existence",
                        episode_id=episode_id,
                        error=str(e))
            raise DatabaseError(f"Failed to check episode existence: {e}")
    
    def list_episodes(self) -> List[EpisodeObject]:
        """
        List all episodes in the registry
        
        Returns:
            List of all episode objects ordered by most recently updated
        """
        try:
            cursor = self.connection.execute_query(
                "SELECT * FROM episodes ORDER BY updated_at DESC"
            )
            
            episodes = []
            for row in cursor.fetchall():
                try:
                    episode = self._row_to_episode(row)
                    episodes.append(episode)
                except Exception as row_error:
                    logger.error("Failed to parse episode row", 
                               episode_id=row.get('id', 'unknown') if hasattr(row, 'get') else row['id'],
                               error=str(row_error),
                               exc_info=True)
                    # Continue with other episodes instead of failing completely
                    continue
            
            return episodes
            
        except Exception as e:
            logger.error("Failed to list episodes", error=str(e), exc_info=True)
            raise DatabaseError(f"Failed to list episodes: {e}")
    
    def get_all_episode_ids(self) -> Set[str]:
        """
        Get set of all existing episode IDs for uniqueness validation
        
        Returns:
            Set of all episode IDs
        """
        try:
            cursor = self.connection.execute_query("SELECT id FROM episodes")
            return {row[0] for row in cursor.fetchall()}
            
        except Exception as e:
            logger.error("Failed to retrieve episode IDs", error=str(e))
            raise DatabaseError(f"Failed to retrieve episode IDs: {e}")
    
    def find_episode_by_filename(self, filename: str) -> Optional[EpisodeObject]:
        """
        Find episode by filename (useful for cross-platform path matching)
        
        Args:
            filename: Filename to search for (e.g., "OSS096.mp4")
            
        Returns:
            EpisodeObject or None if not found
        """
        try:
            # Search for episodes where source_path contains the filename
            cursor = self.connection.execute_query(
                "SELECT * FROM episodes WHERE source_path LIKE ?",
                (f"%{filename}%",)
            )
            
            rows = cursor.fetchall()
            
            if not rows:
                return None
            
            # If multiple matches, log warning and return first
            if len(rows) > 1:
                logger.warning(f"Multiple episodes found with filename '{filename}', returning first match")
            
            return self._row_to_episode(rows[0])
            
        except Exception as e:
            logger.error("Failed to find episode by filename",
                        filename=filename,
                        error=str(e))
            raise DatabaseError(f"Failed to find episode by filename: {e}")
    
    def log_processing_event(self, episode_id: str, stage: str, status: str, 
                           duration: Optional[float] = None, 
                           error_message: Optional[str] = None) -> None:
        """
        Log a processing event
        
        Args:
            episode_id: Episode being processed
            stage: Processing stage
            status: Event status ('started', 'completed', 'failed')
            duration: Processing duration in seconds
            error_message: Error message if status is 'failed'
        """
        try:
            with self.connection.transaction() as conn:
                self._log_processing_event(
                    conn, episode_id, stage, status, duration, error_message
                )
            
        except Exception as e:
            logger.error("Failed to log processing event",
                        episode_id=episode_id,
                        stage=stage,
                        status=status,
                        error=str(e))
            # Don't raise exception for logging failures
    
    def get_processing_history(self, episode_id: str) -> List[ProcessingEvent]:
        """
        Get processing history for an episode
        
        Args:
            episode_id: Episode to get history for
            
        Returns:
            List of processing events
        """
        try:
            cursor = self.connection.execute_query("""
                SELECT episode_id, stage, status, duration_seconds, 
                       error_message, timestamp
                FROM processing_log 
                WHERE episode_id = ? 
                ORDER BY timestamp
            """, (episode_id,))
            
            events = []
            for row in cursor.fetchall():
                events.append(ProcessingEvent(
                    episode_id=row[0],
                    stage=row[1],
                    status=row[2],
                    duration_seconds=row[3],
                    error_message=row[4],
                    timestamp=datetime.fromisoformat(row[5]) if row[5] else None
                ))
            
            return events
            
        except Exception as e:
            logger.error("Failed to retrieve processing history",
                        episode_id=episode_id,
                        error=str(e))
            raise DatabaseError(f"Failed to retrieve processing history: {e}")
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics
        
        Returns:
            Dictionary with registry statistics
        """
        try:
            stats = {}
            
            # Total episodes
            cursor = self.connection.execute_query("SELECT COUNT(*) FROM episodes")
            stats['total_episodes'] = cursor.fetchone()[0]
            
            # Episodes by stage
            cursor = self.connection.execute_query("""
                SELECT stage, COUNT(*) 
                FROM episodes 
                GROUP BY stage
            """)
            stats['episodes_by_stage'] = dict(cursor.fetchall())
            
            # Recent activity (last 24 hours)
            cursor = self.connection.execute_query("""
                SELECT COUNT(*) 
                FROM processing_log 
                WHERE timestamp > datetime('now', '-1 day')
            """)
            stats['recent_activity'] = cursor.fetchone()[0]
            
            # Error rate
            cursor = self.connection.execute_query("""
                SELECT 
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                    COUNT(*) as total
                FROM processing_log 
                WHERE timestamp > datetime('now', '-1 day')
            """)
            row = cursor.fetchone()
            if row[1] > 0:
                stats['error_rate'] = row[0] / row[1]
            else:
                stats['error_rate'] = 0.0
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get registry stats", error=str(e))
            raise DatabaseError(f"Failed to get registry stats: {e}")
    
    def _validate_episode(self, episode: EpisodeObject) -> None:
        """Validate episode data"""
        if not episode.episode_id:
            raise ValidationError("Episode ID is required")
        
        if not episode.content_hash:
            raise ValidationError("Content hash is required")
        
        if not episode.source.path:
            raise ValidationError("Source path is required")
        
        if not episode.metadata.show_name:
            raise ValidationError("Show name is required")
    
    def _generate_unique_episode_id(self, base_id: str) -> str:
        """Generate unique episode ID by appending suffix"""
        existing_ids = self.get_all_episode_ids()
        
        counter = 1
        while True:
            candidate_id = f"{base_id}-{counter}"
            if candidate_id not in existing_ids:
                return candidate_id
            counter += 1
            
            # Prevent infinite loop
            if counter > 1000:
                raise ProcessingError(f"Unable to generate unique ID for {base_id}")
    
    def _row_to_episode(self, row: sqlite3.Row) -> EpisodeObject:
        """Convert database row to EpisodeObject"""
        try:
            from .models import SourceInfo, MediaInfo, EpisodeMetadata, EnrichmentResult, TranscriptionResult
            
            episode_id = row['id']
            logger.debug(f"Parsing episode {episode_id}")
            
            # Parse metadata JSON
            metadata_dict = json.loads(row['metadata']) if row['metadata'] else {}
            logger.debug(f"Metadata parsed for {episode_id}")
            
            # Create SourceInfo
            last_mod = None
            if 'last_modified' in row.keys() and row['last_modified']:
                try:
                    last_mod = datetime.fromisoformat(row['last_modified'])
                except:
                    pass
                    
            source = SourceInfo(
                path=row['source_path'],
                file_size=row['file_size'] or 0,
                last_modified=last_mod
            )
            
            # Create MediaInfo
            duration_seconds = 0
            if 'duration' in row.keys() and row['duration']:
                duration_seconds = row['duration']
            elif 'duration_seconds' in row.keys() and row['duration_seconds']:
                duration_seconds = row['duration_seconds']
                
            media = MediaInfo(
                duration_seconds=duration_seconds,
                video_codec=metadata_dict.get('video_codec') or metadata_dict.get('codec'),
                audio_codec=metadata_dict.get('audio_codec'),
                resolution=metadata_dict.get('resolution'),
                bitrate=metadata_dict.get('bitrate'),
                frame_rate=metadata_dict.get('frame_rate') or metadata_dict.get('framerate')
            )
            
            # Create EpisodeMetadata
            title = row['id']
            if 'title' in row.keys() and row['title']:
                title = row['title']
            elif 'title' in metadata_dict:
                title = metadata_dict['title']
                
            show = 'Unknown'
            if 'show' in row.keys() and row['show']:
                show = row['show']
            elif 'show' in metadata_dict:
                show = metadata_dict['show']
                
            episode_metadata = EpisodeMetadata(
                title=title,
                show_name=show,
                show_slug=metadata_dict.get('show_slug', show.lower().replace(' ', '-') if show else 'unknown'),
                season=metadata_dict.get('season'),
                episode=metadata_dict.get('episode'),
                date=metadata_dict.get('date') or metadata_dict.get('air_date'),
                topic=metadata_dict.get('topic'),
                topic_slug=metadata_dict.get('topic_slug'),
                description=metadata_dict.get('description')
            )
            
            # Parse enrichment if exists
            enrichment = None
            if 'enrichment' in row.keys() and row['enrichment']:
                try:
                    enrichment_dict = json.loads(row['enrichment']) if isinstance(row['enrichment'], str) else row['enrichment']
                    enrichment = EnrichmentResult.from_dict(enrichment_dict)
                except Exception as e:
                    logger.warning(f"Failed to parse enrichment for {row['id']}: {e}")
            elif metadata_dict.get('enrichment'):
                try:
                    enrichment = EnrichmentResult.from_dict(metadata_dict['enrichment'])
                except Exception as e:
                    logger.warning(f"Failed to parse enrichment from metadata for {row['id']}: {e}")
            
            # Parse transcription if exists
            transcription = None
            if 'transcription' in row.keys() and row['transcription']:
                try:
                    trans_dict = json.loads(row['transcription']) if isinstance(row['transcription'], str) else row['transcription']
                    transcription = TranscriptionResult.from_dict(trans_dict)
                except Exception as e:
                    logger.warning(f"Failed to parse transcription for {row['id']}: {e}")
            elif metadata_dict.get('transcription'):
                try:
                    transcription = TranscriptionResult.from_dict(metadata_dict['transcription'])
                except Exception as e:
                    logger.warning(f"Failed to parse transcription from metadata for {row['id']}: {e}")
            
            # Create EpisodeObject
            episode = EpisodeObject(
                episode_id=row['id'],
                content_hash=row['hash'],
                source=source,
                media=media,
                metadata=episode_metadata,
                processing_stage=ProcessingStage(row['stage']),
                transcription=transcription,
                enrichment=enrichment,
                errors=row['errors'],
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
            )
            
            return episode
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Failed to parse episode data from database: {type(e).__name__}: {str(e)}\n{error_details}",
                        episode_id=row['id'] if 'id' in row.keys() else 'unknown')
            raise DatabaseError(f"Failed to parse episode data: {type(e).__name__}: {e}")
    
    def _log_processing_event(self, conn: sqlite3.Connection, episode_id: str, 
                            stage: str, status: str, 
                            duration: Optional[float] = None,
                            error_message: Optional[str] = None) -> None:
        """Log processing event within transaction"""
        conn.execute("""
            INSERT INTO processing_log 
            (episode_id, stage, status, duration_seconds, error_message)
            VALUES (?, ?, ?, ?, ?)
        """, (episode_id, stage, status, duration, error_message))


# Utility functions for registry operations
def create_episode_registry(db_manager: DatabaseManager) -> EpisodeRegistry:
    """Factory function to create episode registry"""
    return EpisodeRegistry(db_manager)


def ensure_episode_uniqueness(registry: EpisodeRegistry, 
                            episode_ids: List[str]) -> List[str]:
    """
    Ensure all episode IDs are unique, generating new ones if needed
    
    Args:
        registry: Episode registry instance
        episode_ids: List of episode IDs to check
        
    Returns:
        List of unique episode IDs
    """
    existing_ids = registry.get_all_episode_ids()
    unique_ids = []
    
    for episode_id in episode_ids:
        if episode_id in existing_ids:
            unique_id = registry._generate_unique_episode_id(episode_id)
            unique_ids.append(unique_id)
        else:
            unique_ids.append(episode_id)
            existing_ids.add(episode_id)  # Track for subsequent checks
    
    return unique_ids