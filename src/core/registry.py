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
                
                conn.execute("""
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
                
                if conn.rowcount == 0:
                    raise ValidationError(f"Episode not found: {episode.episode_id}")
            
            logger.info("Episode data updated",
                       episode_id=episode.episode_id,
                       stage=episode.processing_stage.value)
            
        except Exception as e:
            logger.error("Failed to update episode data",
                        episode_id=episode.episode_id,
                        error=str(e))
            raise DatabaseError(f"Failed to update episode data: {e}")
    
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
            metadata_dict = json.loads(row['metadata'])
            episode = EpisodeObject.from_dict(metadata_dict)
            
            # Override with current database values
            episode.processing_stage = ProcessingStage(row['stage'])
            episode.errors = row['errors']
            if row['created_at']:
                episode.created_at = datetime.fromisoformat(row['created_at'])
            if row['updated_at']:
                episode.updated_at = datetime.fromisoformat(row['updated_at'])
            
            return episode
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Failed to parse episode data from database",
                        episode_id=row.get('id', 'unknown'),
                        error=str(e))
            raise DatabaseError(f"Failed to parse episode data: {e}")
    
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