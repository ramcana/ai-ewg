# PostgreSQL Migration Guide

## Why Migrate from SQLite to PostgreSQL?

### Current Limitations (SQLite)
- ❌ Single writer at a time (file-level locking)
- ❌ "Database is locked" errors under concurrent load
- ❌ Cannot run multiple API workers
- ❌ Windows file locking adds friction
- ❌ Limited scalability for parallel n8n workflows

### PostgreSQL Benefits
- ✅ True multi-process concurrency
- ✅ No file locking issues
- ✅ Connection pooling (5-10 concurrent connections)
- ✅ Can run multiple API workers
- ✅ Better performance under load
- ✅ Production-ready for high-concurrency workloads

## Migration Steps

### Step 1: Set Up PostgreSQL

#### Option A: Docker (Recommended)

Create `docker-compose.postgres.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: ai-ewg-postgres
    environment:
      POSTGRES_DB: pipeline
      POSTGRES_USER: pipeline_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-change_me_in_production}
      POSTGRES_INITDB_ARGS: "--encoding=UTF8 --locale=en_US.UTF-8"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_postgres.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pipeline_user -d pipeline"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  postgres_data:
    driver: local
```

Start PostgreSQL:
```powershell
docker-compose -f docker-compose.postgres.yml up -d
```

#### Option B: Local Installation (Windows)

1. Download PostgreSQL 15 from https://www.postgresql.org/download/windows/
2. Install with default settings
3. Create database:
```powershell
# Using psql
psql -U postgres
CREATE DATABASE pipeline;
CREATE USER pipeline_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE pipeline TO pipeline_user;
\q
```

### Step 2: Install Python Dependencies

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install PostgreSQL adapter
pip install psycopg2-binary==2.9.9

# Install SQLAlchemy (if not already installed)
pip install sqlalchemy==2.0.23

# Update requirements
pip freeze > requirements-postgres.txt
```

### Step 3: Create PostgreSQL Database Module

Create `src/core/database_postgres.py`:

```python
"""
PostgreSQL database implementation for the Video Processing Pipeline
"""

import threading
from contextlib import contextmanager
from typing import Optional, Generator, Dict, Any
from datetime import datetime

from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError

from .logging import get_logger
from .exceptions import DatabaseError
from .config import DatabaseConfig

logger = get_logger('pipeline.database.postgres')


class PostgresConnection:
    """PostgreSQL connection manager with connection pooling"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine: Optional[Engine] = None
        self._lock = threading.Lock()
        
    def initialize(self):
        """Initialize PostgreSQL engine with connection pooling"""
        try:
            # Build connection string
            conn_string = (
                f"postgresql+psycopg2://{self.config.user}:{self.config.password}"
                f"@{self.config.host}:{self.config.port}/{self.config.database}"
            )
            
            # Create engine with connection pooling
            self.engine = create_engine(
                conn_string,
                poolclass=QueuePool,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600,   # Recycle connections after 1 hour
                echo=False,          # Set to True for SQL debugging
                connect_args={
                    "connect_timeout": self.config.connection_timeout,
                    "application_name": "ai-ewg-pipeline"
                }
            )
            
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info("PostgreSQL connection pool initialized",
                       pool_size=self.config.pool_size,
                       max_overflow=self.config.max_overflow)
            
        except Exception as e:
            raise DatabaseError(f"Failed to initialize PostgreSQL: {e}")
    
    @contextmanager
    def transaction(self, max_retries: int = 3, retry_delay: float = 0.5) -> Generator:
        """Context manager for database transactions"""
        if not self.engine:
            raise DatabaseError("PostgreSQL engine not initialized")
        
        for attempt in range(max_retries):
            try:
                with self.engine.begin() as conn:
                    yield conn
                return  # Success
                
            except OperationalError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Transaction failed, retrying ({attempt + 1}/{max_retries})...",
                                 error=str(e))
                    import time
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    logger.error("Transaction failed after all retries", error=str(e))
                    raise DatabaseError(f"Transaction failed: {e}")
            except Exception as e:
                logger.error("Transaction error", error=str(e))
                raise DatabaseError(f"Transaction error: {e}")
        
        raise DatabaseError("Transaction failed after all retry attempts")
    
    def execute_query(self, query: str, params: Optional[dict] = None):
        """Execute a query and return results"""
        if not self.engine:
            raise DatabaseError("PostgreSQL engine not initialized")
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                return result
        except Exception as e:
            raise DatabaseError(f"Query execution failed: {e}")
    
    def close(self):
        """Close connection pool"""
        if self.engine:
            self.engine.dispose()
            logger.info("PostgreSQL connection pool closed")


# Add connection pool event listeners for monitoring
@event.listens_for(Engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    logger.debug("New PostgreSQL connection established")


@event.listens_for(Engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    logger.debug("Connection checked out from pool")


@event.listens_for(Engine, "checkin")
def receive_checkin(dbapi_conn, connection_record):
    logger.debug("Connection returned to pool")
```

### Step 4: Update Configuration

Update `src/core/config.py`:

```python
@dataclass
class DatabaseConfig:
    """Configuration for database"""
    # Common settings
    type: str = "sqlite"  # or "postgresql"
    backup_enabled: bool = True
    backup_interval_hours: int = 24
    
    # SQLite settings
    path: str = "data/pipeline.db"
    journal_mode: str = "WAL"
    synchronous: str = "NORMAL"
    busy_timeout: int = 10000
    connection_timeout: int = 10
    max_connections: int = 10
    
    # PostgreSQL settings
    host: str = "localhost"
    port: int = 5432
    database: str = "pipeline"
    user: str = "pipeline_user"
    password: str = ""
    pool_size: int = 5
    max_overflow: int = 10
```

Update `config/pipeline.yaml`:

```yaml
database:
  type: postgresql
  host: localhost
  port: 5432
  database: pipeline
  user: pipeline_user
  password: ${POSTGRES_PASSWORD}  # Use environment variable
  pool_size: 5
  max_overflow: 10
  connection_timeout: 10
  backup_enabled: true
```

### Step 5: Migrate Schema

Create `scripts/migrate_to_postgres.py`:

```python
#!/usr/bin/env python3
"""
Migrate SQLite database to PostgreSQL
"""

import sqlite3
import psycopg2
from psycopg2.extras import execute_values
import sys
from pathlib import Path

def migrate_sqlite_to_postgres(
    sqlite_path: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str
):
    """Migrate data from SQLite to PostgreSQL"""
    
    print(f"Connecting to SQLite: {sqlite_path}")
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    
    print(f"Connecting to PostgreSQL: {pg_host}:{pg_port}/{pg_database}")
    pg_conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        database=pg_database,
        user=pg_user,
        password=pg_password
    )
    pg_cursor = pg_conn.cursor()
    
    # Tables to migrate
    tables = [
        'schema_version',
        'episodes',
        'processing_log',
        'processing_metrics',
        'backup_log',
        'episode_dependencies',
        'json_metadata_index'
    ]
    
    for table in tables:
        print(f"\nMigrating table: {table}")
        
        try:
            # Get data from SQLite
            sqlite_cursor = sqlite_conn.execute(f"SELECT * FROM {table}")
            rows = sqlite_cursor.fetchall()
            
            if not rows:
                print(f"  No data in {table}")
                continue
            
            # Get column names
            columns = [description[0] for description in sqlite_cursor.description]
            
            # Convert rows to tuples
            data = [tuple(row) for row in rows]
            
            # Insert into PostgreSQL
            placeholders = ','.join(['%s'] * len(columns))
            insert_query = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
            
            execute_values(pg_cursor, insert_query, data)
            pg_conn.commit()
            
            print(f"  Migrated {len(rows)} rows")
            
        except Exception as e:
            print(f"  Error migrating {table}: {e}")
            pg_conn.rollback()
    
    # Close connections
    sqlite_conn.close()
    pg_conn.close()
    
    print("\nMigration complete!")


if __name__ == "__main__":
    import os
    
    migrate_sqlite_to_postgres(
        sqlite_path="data/pipeline.db",
        pg_host=os.getenv("POSTGRES_HOST", "localhost"),
        pg_port=int(os.getenv("POSTGRES_PORT", "5432")),
        pg_database=os.getenv("POSTGRES_DB", "pipeline"),
        pg_user=os.getenv("POSTGRES_USER", "pipeline_user"),
        pg_password=os.getenv("POSTGRES_PASSWORD", "")
    )
```

Run migration:
```powershell
$env:POSTGRES_PASSWORD="your_password"
python scripts/migrate_to_postgres.py
```

### Step 6: Update Database Manager

Update `src/core/database.py` to support both SQLite and PostgreSQL:

```python
def create_database_manager(config: DatabaseConfig) -> DatabaseManager:
    """Factory function to create database manager based on config"""
    if config.type == "postgresql":
        from .database_postgres import PostgresConnection
        # Return PostgreSQL-based manager
        # (Implementation details omitted for brevity)
    else:
        # Return SQLite-based manager (existing code)
        manager = DatabaseManager(config)
        manager.initialize()
        return manager
```

### Step 7: Update API Server for Multi-Worker

Update `src/api/server.py`:

```python
def run_server(host: str = "0.0.0.0", port: int = 8000, config_path: Optional[str] = None, reload: bool = False):
    """Run the API server"""
    app = create_app(config_path)
    
    # Check database type
    config_manager = ConfigurationManager(config_path)
    config = config_manager.load_config()
    
    if config.database.type == "postgresql":
        workers = 4  # Can use multiple workers with PostgreSQL
        logger.info(f"Starting API server with {workers} workers (PostgreSQL)")
    else:
        workers = 1  # Must use single worker with SQLite
        logger.info("Starting API server with 1 worker (SQLite)")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        workers=workers,
        reload=reload
    )
```

### Step 8: Test PostgreSQL Setup

```powershell
# Start PostgreSQL
docker-compose -f docker-compose.postgres.yml up -d

# Set password
$env:POSTGRES_PASSWORD="your_password"

# Run migration
python scripts/migrate_to_postgres.py

# Start API server
python src/cli.py --config config/pipeline.yaml api --port 8000

# Test concurrent requests
1..50 | ForEach-Object -Parallel {
    Invoke-RestMethod -Uri "http://localhost:8000/health" -Method GET
}
```

## Performance Comparison

### SQLite (Before)
- Max concurrent writes: 1
- Typical latency: 50-200ms
- Lock errors: Common under load
- Max n8n concurrency: 1-2

### PostgreSQL (After)
- Max concurrent writes: 5-10 (pool_size)
- Typical latency: 10-50ms
- Lock errors: None
- Max n8n concurrency: 10-20

## Rollback Plan

If you need to rollback to SQLite:

1. Stop API server
2. Update `config/pipeline.yaml`:
   ```yaml
   database:
     type: sqlite
     path: data/pipeline.db
   ```
3. Restart API server

Your SQLite database remains untouched during PostgreSQL testing.

## Production Checklist

- [ ] PostgreSQL container running
- [ ] Database credentials secured (use environment variables)
- [ ] Connection pooling configured (pool_size=5-10)
- [ ] Schema migrated successfully
- [ ] Data migrated and verified
- [ ] API server starts without errors
- [ ] Concurrent requests tested (no lock errors)
- [ ] n8n workflows updated (if needed)
- [ ] Monitoring configured (connection pool metrics)
- [ ] Backup strategy implemented

## Monitoring PostgreSQL

### Connection Pool Stats

```python
# Add to API health endpoint
@app.get("/health")
async def health():
    pool = db_manager.engine.pool
    return {
        "status": "healthy",
        "database": "postgresql",
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow()
    }
```

### Query Performance

```sql
-- Slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Active connections
SELECT count(*) FROM pg_stat_activity
WHERE datname = 'pipeline';
```

## Cost Considerations

### SQLite (Current)
- Cost: $0
- Maintenance: Low
- Scalability: Limited

### PostgreSQL (Docker)
- Cost: $0 (self-hosted)
- Maintenance: Medium
- Scalability: High

### PostgreSQL (Cloud)
- AWS RDS: ~$15-50/month (db.t3.micro - db.t3.small)
- Azure Database: ~$20-60/month
- Google Cloud SQL: ~$15-50/month

## Support

For migration issues:
1. Check PostgreSQL logs: `docker logs ai-ewg-postgres`
2. Verify connection: `psql -h localhost -U pipeline_user -d pipeline`
3. Test schema: `\dt` (list tables)
4. Check data: `SELECT count(*) FROM episodes;`

## References

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [SQLAlchemy Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)
- [psycopg2 Documentation](https://www.psycopg.org/docs/)
