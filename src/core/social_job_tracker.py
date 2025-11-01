"""
Social Media Publishing Job Tracker

Tracks social media package generation jobs with status, progress, and results.
Integrates with the job queue system for async processing.
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SocialJobStatus(Enum):
    """Status of social media publishing job"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SocialJobResult:
    """Result of a social media package generation job"""
    job_id: str
    episode_id: str
    platforms: List[str]
    status: SocialJobStatus
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    packages_generated: Dict[str, str] = None  # platform -> package_path
    errors: Dict[str, str] = None  # platform -> error_message
    warnings: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.packages_generated is None:
            self.packages_generated = {}
        if self.errors is None:
            self.errors = {}
        if self.warnings is None:
            self.warnings = []
        if self.metadata is None:
            self.metadata = {}


class SocialJobTracker:
    """
    Tracker for social media publishing jobs
    
    Manages job lifecycle, status updates, and result storage in SQLite database.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize job tracker
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self._initialize_schema()
        logger.info(f"Social job tracker initialized with database: {self.db_path}")
    
    def _initialize_schema(self) -> None:
        """Initialize database schema for social jobs"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS social_jobs (
                    job_id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    platforms TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    progress REAL DEFAULT 0.0,
                    packages_generated TEXT,
                    errors TEXT,
                    warnings TEXT,
                    metadata TEXT,
                    FOREIGN KEY (episode_id) REFERENCES episodes(episode_id)
                )
            """)
            
            # Create index for faster lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_social_jobs_episode 
                ON social_jobs(episode_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_social_jobs_status 
                ON social_jobs(status)
            """)
            
            conn.commit()
            logger.info("Social jobs schema initialized")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize schema: {e}")
            raise
        finally:
            conn.close()
    
    def create_job(self, episode_id: str, platforms: List[str], metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new social media publishing job
        
        Args:
            episode_id: Episode identifier
            platforms: List of target platforms
            metadata: Optional job metadata
        
        Returns:
            Job ID
        """
        import uuid
        job_id = f"social_{episode_id}_{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT INTO social_jobs (
                    job_id, episode_id, platforms, status, 
                    created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                episode_id,
                json.dumps(platforms),
                SocialJobStatus.PENDING.value,
                now,
                now,
                json.dumps(metadata or {})
            ))
            conn.commit()
            logger.info(f"Created social job {job_id} for episode {episode_id}")
            return job_id
        except sqlite3.Error as e:
            logger.error(f"Failed to create job: {e}")
            raise
        finally:
            conn.close()
    
    def update_job_status(self, job_id: str, status: SocialJobStatus, 
                         progress: Optional[float] = None,
                         packages_generated: Optional[Dict[str, str]] = None,
                         errors: Optional[Dict[str, str]] = None,
                         warnings: Optional[List[str]] = None) -> None:
        """
        Update job status and progress
        
        Args:
            job_id: Job identifier
            status: New status
            progress: Progress percentage (0-100)
            packages_generated: Dict of platform -> package_path
            errors: Dict of platform -> error_message
            warnings: List of warning messages
        """
        now = datetime.now().isoformat()
        completed_at = now if status in [SocialJobStatus.COMPLETED, SocialJobStatus.FAILED] else None
        
        conn = sqlite3.connect(self.db_path)
        try:
            updates = ["status = ?", "updated_at = ?"]
            values = [status.value, now]
            
            if progress is not None:
                updates.append("progress = ?")
                values.append(progress)
            
            if packages_generated is not None:
                updates.append("packages_generated = ?")
                values.append(json.dumps(packages_generated))
            
            if errors is not None:
                updates.append("errors = ?")
                values.append(json.dumps(errors))
            
            if warnings is not None:
                updates.append("warnings = ?")
                values.append(json.dumps(warnings))
            
            if completed_at:
                updates.append("completed_at = ?")
                values.append(completed_at)
            
            values.append(job_id)
            
            query = f"UPDATE social_jobs SET {', '.join(updates)} WHERE job_id = ?"
            conn.execute(query, values)
            conn.commit()
            
            logger.info(f"Updated job {job_id} status to {status.value}")
        except sqlite3.Error as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            raise
        finally:
            conn.close()
    
    def get_job(self, job_id: str) -> Optional[SocialJobResult]:
        """
        Get job details
        
        Args:
            job_id: Job identifier
        
        Returns:
            SocialJobResult or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute("""
                SELECT * FROM social_jobs WHERE job_id = ?
            """, (job_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return self._row_to_result(row)
        except sqlite3.Error as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None
        finally:
            conn.close()
    
    def list_jobs(self, episode_id: Optional[str] = None, 
                  status: Optional[SocialJobStatus] = None,
                  limit: int = 50) -> List[SocialJobResult]:
        """
        List jobs with optional filters
        
        Args:
            episode_id: Filter by episode ID
            status: Filter by status
            limit: Maximum number of jobs to return
        
        Returns:
            List of SocialJobResult
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            query = "SELECT * FROM social_jobs WHERE 1=1"
            params = []
            
            if episode_id:
                query += " AND episode_id = ?"
                params.append(episode_id)
            
            if status:
                query += " AND status = ?"
                params.append(status.value)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            return [self._row_to_result(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to list jobs: {e}")
            return []
        finally:
            conn.close()
    
    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job
        
        Args:
            job_id: Job identifier
        
        Returns:
            True if deleted successfully
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("DELETE FROM social_jobs WHERE job_id = ?", (job_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted job {job_id}")
            return deleted
        except sqlite3.Error as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            return False
        finally:
            conn.close()
    
    def _row_to_result(self, row: sqlite3.Row) -> SocialJobResult:
        """Convert database row to SocialJobResult"""
        return SocialJobResult(
            job_id=row['job_id'],
            episode_id=row['episode_id'],
            platforms=json.loads(row['platforms']),
            status=SocialJobStatus(row['status']),
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
            progress=row['progress'],
            packages_generated=json.loads(row['packages_generated']) if row['packages_generated'] else {},
            errors=json.loads(row['errors']) if row['errors'] else {},
            warnings=json.loads(row['warnings']) if row['warnings'] else [],
            metadata=json.loads(row['metadata']) if row['metadata'] else {}
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get job statistics
        
        Returns:
            Dictionary with job statistics
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("""
                SELECT 
                    status,
                    COUNT(*) as count
                FROM social_jobs
                GROUP BY status
            """)
            
            stats = {status.value: 0 for status in SocialJobStatus}
            for row in cursor.fetchall():
                stats[row[0]] = row[1]
            
            cursor = conn.execute("SELECT COUNT(*) FROM social_jobs")
            stats['total'] = cursor.fetchone()[0]
            
            return stats
        except sqlite3.Error as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
        finally:
            conn.close()
