"""
Clip registry for the Video Processing Pipeline

Manages clip metadata and asset tracking using SQLite database with atomic
operations and referential integrity.
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from .database import DatabaseManager, DatabaseConnection
from .models import ClipObject, ClipAsset, ClipStatus
from .exceptions import DatabaseError, ValidationError
from .logging import get_logger
from .clip_resource_manager import with_database_retry

logger = get_logger('pipeline.clip_registry')


class ClipRegistry:
    """
    Registry for managing clips and their assets
    
    Provides atomic operations for clip registration, status tracking,
    and asset management with referential integrity enforcement.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.connection = db_manager.get_connection()
    
    @with_database_retry("register_clip")
    def register_clip(self, clip: ClipObject) -> None:
        """
        Register a new clip in the database
        
        Args:
            clip: Clip object to register
            
        Raises:
            DatabaseError: If database operation fails
            ValidationError: If clip data is invalid
        """
        try:
            # Validate clip data
            self._validate_clip(clip)
            
            # Check if episode exists
            if not self._episode_exists(clip.episode_id):
                raise ValidationError(f"Episode not found: {clip.episode_id}")
            
            # Register clip in database
            with self.connection.transaction() as conn:
                conn.execute("""
                    INSERT INTO clips (
                        id, episode_id, start_ms, end_ms, duration_ms, score,
                        title, caption, hashtags, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    clip.id,
                    clip.episode_id,
                    clip.start_ms,
                    clip.end_ms,
                    clip.duration_ms,
                    clip.score,
                    clip.title,
                    clip.caption,
                    json.dumps(clip.hashtags),
                    clip.status.value,
                    clip.created_at.isoformat() if clip.created_at else None
                ))
            
            logger.info("Clip registered successfully",
                       clip_id=clip.id,
                       episode_id=clip.episode_id,
                       duration_ms=clip.duration_ms,
                       score=clip.score)
            
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                raise ValidationError(f"Clip ID already exists: {clip.id}")
            elif "FOREIGN KEY constraint failed" in str(e):
                raise ValidationError(f"Episode not found: {clip.episode_id}")
            else:
                raise DatabaseError(f"Clip registration failed: {e}")
        
        except Exception as e:
            logger.error("Clip registration failed",
                        clip_id=clip.id,
                        episode_id=clip.episode_id,
                        error=str(e))
            raise DatabaseError(f"Failed to register clip: {e}")
    
    @with_database_retry("get_clip")
    def get_clip(self, clip_id: str) -> Optional[ClipObject]:
        """
        Retrieve clip by ID
        
        Args:
            clip_id: Unique clip identifier
            
        Returns:
            ClipObject or None if not found
        """
        try:
            cursor = self.connection.execute_query(
                "SELECT * FROM clips WHERE id = ?",
                (clip_id,)
            )
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return self._row_to_clip(row)
            
        except Exception as e:
            logger.error("Failed to retrieve clip",
                        clip_id=clip_id,
                        error=str(e))
            raise DatabaseError(f"Failed to retrieve clip: {e}")
    
    @with_database_retry("get_clips_for_episode")
    def get_clips_for_episode(self, episode_id: str) -> List[ClipObject]:
        """
        Get all clips for an episode
        
        Args:
            episode_id: Episode to get clips for
            
        Returns:
            List of clips for the episode
        """
        try:
            cursor = self.connection.execute_query(
                "SELECT * FROM clips WHERE episode_id = ? ORDER BY start_ms",
                (episode_id,)
            )
            
            clips = []
            for row in cursor.fetchall():
                clips.append(self._row_to_clip(row))
            
            return clips
            
        except Exception as e:
            logger.error("Failed to retrieve clips for episode",
                        episode_id=episode_id,
                        error=str(e))
            raise DatabaseError(f"Failed to retrieve clips for episode: {e}")
    
    def get_clips_by_status(self, status: ClipStatus) -> List[ClipObject]:
        """
        Get all clips with a specific status
        
        Args:
            status: Clip status to filter by
            
        Returns:
            List of clips with the specified status
        """
        try:
            cursor = self.connection.execute_query(
                "SELECT * FROM clips WHERE status = ? ORDER BY score DESC",
                (status.value,)
            )
            
            clips = []
            for row in cursor.fetchall():
                clips.append(self._row_to_clip(row))
            
            return clips
            
        except Exception as e:
            logger.error("Failed to retrieve clips by status",
                        status=status.value,
                        error=str(e))
            raise DatabaseError(f"Failed to retrieve clips by status: {e}")
    
    @with_database_retry("update_clip_status")
    def update_clip_status(self, clip_id: str, status: ClipStatus) -> None:
        """
        Update clip processing status
        
        Args:
            clip_id: Clip to update
            status: New status
            
        Raises:
            DatabaseError: If update fails
            ValidationError: If clip not found
        """
        try:
            with self.connection.transaction() as conn:
                cursor = conn.execute(
                    "UPDATE clips SET status = ? WHERE id = ?",
                    (status.value, clip_id)
                )
                
                if cursor.rowcount == 0:
                    raise ValidationError(f"Clip not found: {clip_id}")
            
            logger.info("Clip status updated",
                       clip_id=clip_id,
                       status=status.value)
            
        except Exception as e:
            logger.error("Failed to update clip status",
                        clip_id=clip_id,
                        status=status.value,
                        error=str(e))
            raise DatabaseError(f"Failed to update clip status: {e}")
    
    def update_clip_metadata(self, clip_id: str, title: Optional[str] = None,
                           caption: Optional[str] = None, 
                           hashtags: Optional[List[str]] = None) -> None:
        """
        Update clip metadata
        
        Args:
            clip_id: Clip to update
            title: New title (optional)
            caption: New caption (optional)
            hashtags: New hashtags (optional)
        """
        try:
            updates = []
            params = []
            
            if title is not None:
                updates.append("title = ?")
                params.append(title)
            
            if caption is not None:
                updates.append("caption = ?")
                params.append(caption)
            
            if hashtags is not None:
                updates.append("hashtags = ?")
                params.append(json.dumps(hashtags))
            
            if not updates:
                return  # Nothing to update
            
            params.append(clip_id)
            
            with self.connection.transaction() as conn:
                cursor = conn.execute(
                    f"UPDATE clips SET {', '.join(updates)} WHERE id = ?",
                    tuple(params)
                )
                
                if cursor.rowcount == 0:
                    raise ValidationError(f"Clip not found: {clip_id}")
            
            logger.info("Clip metadata updated",
                       clip_id=clip_id,
                       updated_fields=len(updates))
            
        except Exception as e:
            logger.error("Failed to update clip metadata",
                        clip_id=clip_id,
                        error=str(e))
            raise DatabaseError(f"Failed to update clip metadata: {e}")
    
    @with_database_retry("register_asset")
    def register_asset(self, asset: ClipAsset) -> None:
        """
        Register a clip asset
        
        Args:
            asset: Clip asset to register
            
        Raises:
            DatabaseError: If database operation fails
            ValidationError: If asset data is invalid
        """
        try:
            # Validate asset data
            self._validate_asset(asset)
            
            # Check if clip exists
            if not self._clip_exists(asset.clip_id):
                raise ValidationError(f"Clip not found: {asset.clip_id}")
            
            # Register asset in database
            with self.connection.transaction() as conn:
                conn.execute("""
                    INSERT INTO clip_assets (
                        id, clip_id, path, variant, aspect_ratio, size_bytes, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    asset.id,
                    asset.clip_id,
                    asset.path,
                    asset.variant,
                    asset.aspect_ratio,
                    asset.size_bytes,
                    asset.created_at.isoformat() if asset.created_at else None
                ))
            
            logger.info("Clip asset registered successfully",
                       asset_id=asset.id,
                       clip_id=asset.clip_id,
                       variant=asset.variant,
                       aspect_ratio=asset.aspect_ratio)
            
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                raise ValidationError(f"Asset ID already exists: {asset.id}")
            elif "FOREIGN KEY constraint failed" in str(e):
                raise ValidationError(f"Clip not found: {asset.clip_id}")
            else:
                raise DatabaseError(f"Asset registration failed: {e}")
        
        except Exception as e:
            logger.error("Asset registration failed",
                        asset_id=asset.id,
                        clip_id=asset.clip_id,
                        error=str(e))
            raise DatabaseError(f"Failed to register asset: {e}")
    
    def get_assets_for_clip(self, clip_id: str) -> List[ClipAsset]:
        """
        Get all assets for a clip
        
        Args:
            clip_id: Clip to get assets for
            
        Returns:
            List of assets for the clip
        """
        try:
            cursor = self.connection.execute_query(
                "SELECT * FROM clip_assets WHERE clip_id = ? ORDER BY variant, aspect_ratio",
                (clip_id,)
            )
            
            assets = []
            for row in cursor.fetchall():
                assets.append(self._row_to_asset(row))
            
            return assets
            
        except Exception as e:
            logger.error("Failed to retrieve assets for clip",
                        clip_id=clip_id,
                        error=str(e))
            raise DatabaseError(f"Failed to retrieve assets for clip: {e}")
    
    def get_asset(self, asset_id: str) -> Optional[ClipAsset]:
        """
        Retrieve asset by ID
        
        Args:
            asset_id: Unique asset identifier
            
        Returns:
            ClipAsset or None if not found
        """
        try:
            cursor = self.connection.execute_query(
                "SELECT * FROM clip_assets WHERE id = ?",
                (asset_id,)
            )
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return self._row_to_asset(row)
            
        except Exception as e:
            logger.error("Failed to retrieve asset",
                        asset_id=asset_id,
                        error=str(e))
            raise DatabaseError(f"Failed to retrieve asset: {e}")
    
    def delete_clip(self, clip_id: str) -> None:
        """
        Delete a clip and all its assets
        
        Args:
            clip_id: Clip to delete
            
        Raises:
            DatabaseError: If deletion fails
        """
        try:
            with self.connection.transaction() as conn:
                # Delete assets first (foreign key constraint)
                conn.execute("DELETE FROM clip_assets WHERE clip_id = ?", (clip_id,))
                
                # Delete clip
                cursor = conn.execute("DELETE FROM clips WHERE id = ?", (clip_id,))
                
                if cursor.rowcount == 0:
                    raise ValidationError(f"Clip not found: {clip_id}")
            
            logger.info("Clip deleted successfully", clip_id=clip_id)
            
        except Exception as e:
            logger.error("Failed to delete clip",
                        clip_id=clip_id,
                        error=str(e))
            raise DatabaseError(f"Failed to delete clip: {e}")
    
    def get_clip_stats(self) -> Dict[str, Any]:
        """
        Get clip registry statistics
        
        Returns:
            Dictionary with clip statistics
        """
        try:
            stats = {}
            
            # Total clips
            cursor = self.connection.execute_query("SELECT COUNT(*) FROM clips")
            stats['total_clips'] = cursor.fetchone()[0]
            
            # Clips by status
            cursor = self.connection.execute_query("""
                SELECT status, COUNT(*) 
                FROM clips 
                GROUP BY status
            """)
            stats['clips_by_status'] = dict(cursor.fetchall())
            
            # Total assets
            cursor = self.connection.execute_query("SELECT COUNT(*) FROM clip_assets")
            stats['total_assets'] = cursor.fetchone()[0]
            
            # Assets by variant
            cursor = self.connection.execute_query("""
                SELECT variant, COUNT(*) 
                FROM clip_assets 
                GROUP BY variant
            """)
            stats['assets_by_variant'] = dict(cursor.fetchall())
            
            # Assets by aspect ratio
            cursor = self.connection.execute_query("""
                SELECT aspect_ratio, COUNT(*) 
                FROM clip_assets 
                GROUP BY aspect_ratio
            """)
            stats['assets_by_aspect_ratio'] = dict(cursor.fetchall())
            
            # Average clip score
            cursor = self.connection.execute_query("SELECT AVG(score) FROM clips")
            avg_score = cursor.fetchone()[0]
            stats['average_score'] = float(avg_score) if avg_score else 0.0
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get clip stats", error=str(e))
            raise DatabaseError(f"Failed to get clip stats: {e}")
    
    def _validate_clip(self, clip: ClipObject) -> None:
        """Validate clip data"""
        if not clip.id:
            raise ValidationError("Clip ID is required")
        
        if not clip.episode_id:
            raise ValidationError("Episode ID is required")
        
        if clip.start_ms < 0:
            raise ValidationError("Start time must be non-negative")
        
        if clip.end_ms <= clip.start_ms:
            raise ValidationError("End time must be greater than start time")
        
        if not 0.0 <= clip.score <= 1.0:
            raise ValidationError("Score must be between 0.0 and 1.0")
    
    def _validate_asset(self, asset: ClipAsset) -> None:
        """Validate asset data"""
        if not asset.id:
            raise ValidationError("Asset ID is required")
        
        if not asset.clip_id:
            raise ValidationError("Clip ID is required")
        
        if not asset.path:
            raise ValidationError("Asset path is required")
        
        if asset.variant not in ['clean', 'subtitled']:
            raise ValidationError("Variant must be 'clean' or 'subtitled'")
        
        if asset.aspect_ratio not in ['9x16', '16x9', '1x1']:
            raise ValidationError("Aspect ratio must be '9x16', '16x9', or '1x1'")
    
    def _episode_exists(self, episode_id: str) -> bool:
        """Check if episode exists"""
        try:
            cursor = self.connection.execute_query(
                "SELECT 1 FROM episodes WHERE id = ? LIMIT 1",
                (episode_id,)
            )
            return cursor.fetchone() is not None
        except Exception:
            return False
    
    def _clip_exists(self, clip_id: str) -> bool:
        """Check if clip exists"""
        try:
            cursor = self.connection.execute_query(
                "SELECT 1 FROM clips WHERE id = ? LIMIT 1",
                (clip_id,)
            )
            return cursor.fetchone() is not None
        except Exception:
            return False
    
    def _row_to_clip(self, row: sqlite3.Row) -> ClipObject:
        """Convert database row to ClipObject"""
        try:
            hashtags = json.loads(row['hashtags']) if row['hashtags'] else []
            
            return ClipObject(
                id=row['id'],
                episode_id=row['episode_id'],
                start_ms=row['start_ms'],
                end_ms=row['end_ms'],
                duration_ms=row['duration_ms'],
                score=row['score'],
                title=row['title'],
                caption=row['caption'],
                hashtags=hashtags,
                status=ClipStatus(row['status']),
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("Failed to parse clip data from database",
                        clip_id=row.get('id', 'unknown'),
                        error=str(e))
            raise DatabaseError(f"Failed to parse clip data: {e}")
    
    def _row_to_asset(self, row: sqlite3.Row) -> ClipAsset:
        """Convert database row to ClipAsset"""
        try:
            return ClipAsset(
                id=row['id'],
                clip_id=row['clip_id'],
                path=row['path'],
                variant=row['variant'],
                aspect_ratio=row['aspect_ratio'],
                size_bytes=row['size_bytes'],
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
            )
            
        except (KeyError, ValueError) as e:
            logger.error("Failed to parse asset data from database",
                        asset_id=row.get('id', 'unknown'),
                        error=str(e))
            raise DatabaseError(f"Failed to parse asset data: {e}")


# Utility functions for clip registry operations
def create_clip_registry(db_manager: DatabaseManager) -> ClipRegistry:
    """Factory function to create clip registry"""
    return ClipRegistry(db_manager)