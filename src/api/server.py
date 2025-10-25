"""
FastAPI server for n8n integration endpoints

Provides REST API endpoints for pipeline operations, status monitoring,
and webhook handlers for n8n workflow integration.
"""

import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional

from ..core import PipelineOrchestrator, ConfigurationManager, get_logger
from .endpoints import register_endpoints
from .async_processing import register_async_endpoints

logger = get_logger('pipeline.api')


class APIServer:
    """API server for pipeline operations"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.orchestrator: Optional[PipelineOrchestrator] = None
        self.app: Optional[FastAPI] = None
    
    async def startup(self):
        """Initialize pipeline orchestrator on startup"""
        try:
            self.orchestrator = PipelineOrchestrator(config_path=self.config_path)
            logger.info("Pipeline orchestrator initialized for API server")
            
            # Initialize database and registry
            self.orchestrator.initialize_database()
            logger.info("Database and registry initialized")
            
            # Verify SQLite configuration
            self._verify_sqlite_config()
            
        except Exception as e:
            logger.error(f"Failed to initialize pipeline orchestrator: {e}")
            raise
    
    def _verify_sqlite_config(self):
        """Verify SQLite is configured correctly for concurrency"""
        try:
            db_manager = self.orchestrator.registry.db_manager
            conn = db_manager.connection.get_connection()
            
            # Check journal mode
            cursor = conn.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0]
            
            # Check busy timeout
            cursor = conn.execute("PRAGMA busy_timeout")
            busy_timeout = cursor.fetchone()[0]
            
            logger.info("SQLite configuration verified",
                       journal_mode=journal_mode,
                       busy_timeout_ms=busy_timeout)
            
            if journal_mode != "wal":
                logger.warning("SQLite not in WAL mode - may experience locking issues",
                             current_mode=journal_mode)
            
            if busy_timeout < 5000:
                logger.warning("SQLite busy_timeout is low - may experience locking issues",
                             current_timeout_ms=busy_timeout)
                             
        except Exception as e:
            logger.warning("Could not verify SQLite configuration", error=str(e))
    
    async def shutdown(self):
        """Cleanup on shutdown"""
        if self.orchestrator:
            self.orchestrator.request_shutdown()
            logger.info("Pipeline orchestrator shutdown requested")


# Global server instance
_server_instance: Optional[APIServer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    global _server_instance
    
    # Startup
    if _server_instance:
        await _server_instance.startup()
    
    yield
    
    # Shutdown
    if _server_instance:
        await _server_instance.shutdown()


def create_app(config_path: Optional[str] = None) -> FastAPI:
    """
    Create FastAPI application with pipeline integration
    
    Args:
        config_path: Path to pipeline configuration file
        
    Returns:
        FastAPI: Configured application instance
    """
    global _server_instance
    
    # Create server instance
    _server_instance = APIServer(config_path)
    
    # Create FastAPI app
    app = FastAPI(
        title="Video Processing Pipeline API",
        description="REST API for n8n integration with video processing pipeline",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Store server instance in app state
    app.state.server = _server_instance
    
    # Register API endpoints
    register_endpoints(app)
    
    # Register async processing endpoints
    from .endpoints import get_orchestrator
    register_async_endpoints(app, get_orchestrator)
    
    return app





def run_server(host: str = "0.0.0.0", port: int = 8000, config_path: Optional[str] = None, reload: bool = False):
    """
    Run the API server with single-worker mode (required for SQLite)
    
    Args:
        host: Host to bind to
        port: Port to bind to
        config_path: Path to pipeline configuration file
        reload: Enable auto-reload for development (still uses single worker)
    
    Note:
        CRITICAL: This server MUST run with workers=1 to avoid SQLite locking issues.
        Multiple workers will cause "database is locked" errors.
    """
    app = create_app(config_path)
    
    logger.info(f"Starting API server on {host}:{port}")
    logger.info("Running in single-worker mode (required for SQLite)")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        workers=1,  # CRITICAL: Single worker only for SQLite
        reload=reload
    )


if __name__ == "__main__":
    run_server()