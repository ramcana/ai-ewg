"""
Database management for the Video Processing Pipeline

Provides SQLite database schema, connection management, and migration system
for tracking episode processing state and deduplication.
"""

import sqlite3
import json
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Generator
from datetime import datetime

from .logging import get_logger
from .exceptions import DatabaseError, ConfigurationError
from .config import DatabaseConfig

logger = get_logger('pipeline.database')


class DatabaseConnection:
    """Thread-safe database connection wrapper with NullPool-like behavior"""
    
    def __init__(self, db_path: str, config: DatabaseConfig):
        self.db_path = db_path
        self.config = config
        self._local = threading.local()
        self._lock = threading.Lock()
        self._connection_count = 0
        self._use_nullpool = True  # Close connections aggressively to avoid lock retention
        
    def get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            with self._lock:
                if self._connection_count >= self.config.max_connections:
                    raise DatabaseError("Maximum database connections exceeded")
                
                try:
                    conn = sqlite3.connect(
                        self.db_path,
                        timeout=self.config.connection_timeout,
                        check_same_thread=False,  # Allow connection sharing across threads
                        isolation_level=None  # Autocommit mode, we'll manage transactions explicitly
                    )
                    
                    # Configure connection with optimal SQLite settings
                    conn.row_factory = sqlite3.Row
                    
                    # Critical PRAGMAs for concurrency
                    conn.execute(f"PRAGMA journal_mode = {self.config.journal_mode}")
                    conn.execute(f"PRAGMA synchronous = {self.config.synchronous}")
                    conn.execute(f"PRAGMA busy_timeout = {self.config.busy_timeout}")
                    
                    # Additional optimizations
                    conn.execute("PRAGMA foreign_keys = ON")
                    conn.execute("PRAGMA temp_store = MEMORY")
                    conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
                    
                    self._local.connection = conn
                    self._connection_count += 1
                    
                    logger.debug("Database connection created", 
                               thread_id=threading.get_ident(),
                               connection_count=self._connection_count)
                    
                except sqlite3.Error as e:
                    raise DatabaseError(f"Failed to connect to database: {e}")
        
        return self._local.connection
    
    def close_connection(self) -> None:
        """Close thread-local connection"""
        if hasattr(self._local, 'connection') and self._local.connection:
            with self._lock:
                try:
                    self._local.connection.close()
                    self._connection_count -= 1
                    logger.debug("Database connection closed",
                               thread_id=threading.get_ident(),
                               connection_count=self._connection_count)
                except sqlite3.Error as e:
                    logger.warning("Error closing database connection", error=str(e))
                finally:
                    self._local.connection = None
    
    @contextmanager
    def transaction(self, max_retries: int = 5, retry_delay: float = 0.5, immediate: bool = True) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database transactions with aggressive retry logic
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries (exponential backoff applied)
            immediate: If True, use BEGIN IMMEDIATE (exclusive lock). Default True for writes.
        """
        conn = self.get_connection()
        begin_statement = "BEGIN IMMEDIATE" if immediate else "BEGIN DEFERRED"
        
        for attempt in range(max_retries):
            transaction_started = False
            try:
                conn.execute(begin_statement)
                transaction_started = True
                yield conn
                conn.commit()
                
                # NullPool behavior: close connection after successful transaction
                if self._use_nullpool:
                    self.close_connection()
                
                return  # Success - exit the function
            except sqlite3.OperationalError as e:
                if transaction_started:
                    try:
                        conn.rollback()
                    except:
                        pass
                
                # Close stale connection on error
                self.close_connection()
                    
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"Database locked, retrying in {wait_time}s ({attempt + 1}/{max_retries})...", 
                                 error=str(e), begin_mode=begin_statement)
                    time.sleep(wait_time)
                    continue  # Try again
                else:
                    logger.error("Database transaction failed after all retries", error=str(e), attempt=attempt + 1)
                    raise
            except Exception as e:
                if transaction_started:
                    try:
                        conn.rollback()
                    except:
                        pass
                
                # Close connection on any error
                self.close_connection()
                
                logger.error("Database transaction rolled back", error=str(e))
                raise
        
        # If we get here, all retries failed
        raise DatabaseError("Database transaction failed after all retry attempts")
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> sqlite3.Cursor:
        """Execute a query with automatic connection management"""
        conn = self.get_connection()
        try:
            if params:
                return conn.execute(query, params)
            else:
                return conn.execute(query)
        except sqlite3.Error as e:
            raise DatabaseError(f"Query execution failed: {e}")
    
    def execute_many(self, query: str, params_list: List[tuple]) -> None:
        """Execute query with multiple parameter sets"""
        conn = self.get_connection()
        try:
            conn.executemany(query, params_list)
            conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"Batch query execution failed: {e}")


class DatabaseMigration:
    """Database migration management"""
    
    def __init__(self, connection: DatabaseConnection):
        self.connection = connection
        self.migrations = self._get_migrations()
    
    def _get_migrations(self) -> Dict[int, str]:
        """Define database migrations"""
        return {
            1: '''
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    hash TEXT UNIQUE NOT NULL,
    stage TEXT NOT NULL DEFAULT 'discovered',
    source_path TEXT NOT NULL,
    metadata JSON NOT NULL,
    errors TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS processing_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_seconds REAL,
    error_message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_episodes_hash ON episodes(hash);
CREATE INDEX IF NOT EXISTS idx_episodes_stage ON episodes(stage);
CREATE INDEX IF NOT EXISTS idx_episodes_updated_at ON episodes(updated_at);
CREATE INDEX IF NOT EXISTS idx_processing_log_episode_id ON processing_log(episode_id);
CREATE INDEX IF NOT EXISTS idx_processing_log_timestamp ON processing_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_processing_log_stage_status ON processing_log(stage, status);

CREATE TRIGGER IF NOT EXISTS episodes_updated_at 
    AFTER UPDATE ON episodes
    FOR EACH ROW
BEGIN
    UPDATE episodes SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END
            ''',
            
            2: '''
ALTER TABLE episodes ADD COLUMN file_size INTEGER;
ALTER TABLE episodes ADD COLUMN duration_seconds REAL;
ALTER TABLE episodes ADD COLUMN last_modified TIMESTAMP;

CREATE TABLE IF NOT EXISTS processing_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_processing_metrics_episode_stage 
    ON processing_metrics(episode_id, stage)
            ''',
            
            3: '''
CREATE TABLE IF NOT EXISTS backup_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_path TEXT NOT NULL,
    backup_size INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    restored_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS episode_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id TEXT NOT NULL,
    depends_on_episode_id TEXT NOT NULL,
    dependency_type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE,
    FOREIGN KEY (depends_on_episode_id) REFERENCES episodes(id) ON DELETE CASCADE,
    UNIQUE(episode_id, depends_on_episode_id, dependency_type)
)
            ''',
            
            4: '''
CREATE TABLE IF NOT EXISTS json_metadata_index (
    episode_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Extracted searchable fields
    show_name TEXT,
    title TEXT,
    date TEXT,
    duration_seconds REAL,
    guest_names TEXT,
    topics TEXT,
    has_transcript BOOLEAN DEFAULT 0,
    has_enrichment BOOLEAN DEFAULT 0,
    has_editorial BOOLEAN DEFAULT 0,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_json_show_name ON json_metadata_index(show_name);
CREATE INDEX IF NOT EXISTS idx_json_date ON json_metadata_index(date);
CREATE INDEX IF NOT EXISTS idx_json_duration ON json_metadata_index(duration_seconds);

CREATE VIRTUAL TABLE IF NOT EXISTS episodes_search USING fts5(
    episode_id UNINDEXED,
    title,
    summary,
    transcript_text,
    topics,
    guest_names,
    content='json_metadata_index',
    content_rowid='rowid'
);
            ''',
            
            5: '''
-- Clips discovered for an episode
CREATE TABLE IF NOT EXISTS clips (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    score REAL NOT NULL,           -- 0..1 overall highlight score
    title TEXT,
    caption TEXT,
    hashtags TEXT,                 -- JSON array
    status TEXT NOT NULL DEFAULT 'pending',  -- pending|rendered|failed
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
);

-- Export files generated
CREATE TABLE IF NOT EXISTS clip_assets (
    id TEXT PRIMARY KEY,
    clip_id TEXT NOT NULL,
    path TEXT NOT NULL,
    variant TEXT NOT NULL,         -- 'clean','subtitled'
    aspect_ratio TEXT NOT NULL,    -- '9x16','16x9','1x1'
    size_bytes INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (clip_id) REFERENCES clips(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_clips_episode_id ON clips(episode_id);
CREATE INDEX IF NOT EXISTS idx_clips_status ON clips(status);
CREATE INDEX IF NOT EXISTS idx_clips_score ON clips(score DESC);
CREATE INDEX IF NOT EXISTS idx_clip_assets_clip_id ON clip_assets(clip_id);
            '''
        }
    
    def get_current_version(self) -> int:
        """Get current database schema version"""
        try:
            cursor = self.connection.execute_query(
                "SELECT MAX(version) FROM schema_version"
            )
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else 0
        except DatabaseError:
            # Schema version table doesn't exist yet
            return 0
    
    def migrate(self, target_version: Optional[int] = None) -> None:
        """Run database migrations"""
        current_version = self.get_current_version()
        
        if target_version is None:
            target_version = max(self.migrations.keys())
        
        if current_version >= target_version:
            logger.info("Database schema is up to date", 
                       current_version=current_version,
                       target_version=target_version)
            return
        
        logger.info("Starting database migration", 
                   current_version=current_version,
                   target_version=target_version)
        
        with self.connection.transaction() as conn:
            for version in range(current_version + 1, target_version + 1):
                if version not in self.migrations:
                    raise DatabaseError(f"Migration {version} not found")
                
                logger.info(f"Applying migration {version}")
                
                try:
                    # Execute migration SQL
                    migration_sql = self.migrations[version]
                    conn.executescript(migration_sql)
                    
                    # Record migration
                    conn.execute(
                        "INSERT INTO schema_version (version) VALUES (?)",
                        (version,)
                    )
                    
                    logger.info(f"Migration {version} completed successfully")
                    
                except sqlite3.Error as e:
                    raise DatabaseError(f"Migration {version} failed: {e}")
        
        logger.info("Database migration completed successfully",
                   final_version=target_version)
    
    def rollback(self, target_version: int) -> None:
        """Rollback database to specific version (destructive operation)"""
        current_version = self.get_current_version()
        
        if target_version >= current_version:
            logger.warning("Cannot rollback to same or higher version",
                          current_version=current_version,
                          target_version=target_version)
            return
        
        logger.warning("Starting database rollback - this is destructive!",
                      current_version=current_version,
                      target_version=target_version)
        
        # For SQLite, rollback typically means recreating the database
        # This is a simplified implementation - in production, you'd want
        # more sophisticated rollback scripts
        raise NotImplementedError("Database rollback requires manual intervention")


class DatabaseManager:
    """Main database manager for the pipeline"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.db_path = Path(config.path)
        self.connection: Optional[DatabaseConnection] = None
        self.migration: Optional[DatabaseMigration] = None
        
        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def initialize(self) -> None:
        """Initialize database connection and run migrations"""
        try:
            logger.info("Initializing database", path=str(self.db_path))
            
            # Create connection manager
            self.connection = DatabaseConnection(str(self.db_path), self.config)
            
            # Initialize migration manager
            self.migration = DatabaseMigration(self.connection)
            
            # Run migrations
            self.migration.migrate()
            
            # Verify database integrity
            self._verify_database_integrity()
            
            logger.info("Database initialization completed successfully")
            
        except Exception as e:
            logger.error("Database initialization failed", error=str(e))
            raise DatabaseError(f"Failed to initialize database: {e}")
    
    def _verify_database_integrity(self) -> None:
        """Verify database integrity and structure"""
        try:
            # Check that required tables exist
            required_tables = ['episodes', 'processing_log', 'schema_version']
            
            cursor = self.connection.execute_query(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            existing_tables = {row[0] for row in cursor.fetchall()}
            
            missing_tables = set(required_tables) - existing_tables
            if missing_tables:
                raise DatabaseError(f"Missing required tables: {missing_tables}")
            
            # Run integrity check
            cursor = self.connection.execute_query("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()
            
            if integrity_result[0] != "ok":
                raise DatabaseError(f"Database integrity check failed: {integrity_result[0]}")
            
            logger.debug("Database integrity verification passed")
            
        except sqlite3.Error as e:
            raise DatabaseError(f"Database integrity verification failed: {e}")
    
    def get_connection(self) -> DatabaseConnection:
        """Get database connection"""
        if not self.connection:
            raise DatabaseError("Database not initialized. Call initialize() first.")
        return self.connection
    
    def backup_database(self, backup_path: Optional[str] = None) -> str:
        """Create database backup"""
        if not self.connection:
            raise DatabaseError("Database not initialized")
        
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.db_path.stem}_backup_{timestamp}.db"
        
        backup_path = Path(backup_path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Use SQLite backup API for consistent backup
            source_conn = self.connection.get_connection()
            backup_conn = sqlite3.connect(str(backup_path))
            
            source_conn.backup(backup_conn)
            backup_conn.close()
            
            # Record backup in log
            backup_size = backup_path.stat().st_size
            self.connection.execute_query(
                "INSERT INTO backup_log (backup_path, backup_size) VALUES (?, ?)",
                (str(backup_path), backup_size)
            )
            
            logger.info("Database backup created successfully",
                       backup_path=str(backup_path),
                       backup_size=backup_size)
            
            return str(backup_path)
            
        except Exception as e:
            logger.error("Database backup failed", error=str(e))
            raise DatabaseError(f"Failed to create database backup: {e}")
    
    def restore_database(self, backup_path: str) -> None:
        """Restore database from backup"""
        backup_path = Path(backup_path)
        
        if not backup_path.exists():
            raise DatabaseError(f"Backup file not found: {backup_path}")
        
        try:
            # Close existing connections
            if self.connection:
                self.connection.close_connection()
            
            # Replace current database with backup
            if self.db_path.exists():
                backup_current = f"{self.db_path}.pre_restore"
                self.db_path.rename(backup_current)
            
            # Copy backup to main location
            import shutil
            shutil.copy2(backup_path, self.db_path)
            
            # Reinitialize connection
            self.initialize()
            
            # Record restore in log
            self.connection.execute_query(
                "UPDATE backup_log SET restored_at = CURRENT_TIMESTAMP WHERE backup_path = ?",
                (str(backup_path),)
            )
            
            logger.info("Database restored successfully", backup_path=str(backup_path))
            
        except Exception as e:
            logger.error("Database restore failed", error=str(e))
            raise DatabaseError(f"Failed to restore database: {e}")
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        if not self.connection:
            raise DatabaseError("Database not initialized")
        
        try:
            stats = {}
            
            # Table row counts
            cursor = self.connection.execute_query("SELECT COUNT(*) FROM episodes")
            stats['episodes_count'] = cursor.fetchone()[0]
            
            cursor = self.connection.execute_query("SELECT COUNT(*) FROM processing_log")
            stats['processing_log_count'] = cursor.fetchone()[0]
            
            # Database size
            stats['database_size'] = self.db_path.stat().st_size
            
            # Schema version
            stats['schema_version'] = self.migration.get_current_version()
            
            # Processing stage distribution
            cursor = self.connection.execute_query(
                "SELECT stage, COUNT(*) FROM episodes GROUP BY stage"
            )
            stats['stage_distribution'] = dict(cursor.fetchall())
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get database stats", error=str(e))
            raise DatabaseError(f"Failed to get database statistics: {e}")
    
    def close(self) -> None:
        """Close database connections"""
        if self.connection:
            self.connection.close_connection()
            logger.info("Database connections closed")


# Utility functions for common database operations
def create_database_manager(config: DatabaseConfig) -> DatabaseManager:
    """Factory function to create and initialize database manager"""
    manager = DatabaseManager(config)
    manager.initialize()
    return manager


def json_serializer(obj: Any) -> str:
    """JSON serializer for database storage"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return json.dumps(obj, default=str)


def json_deserializer(json_str: str) -> Any:
    """JSON deserializer for database retrieval"""
    return json.loads(json_str)