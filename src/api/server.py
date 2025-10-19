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
        except Exception as e:
            logger.error(f"Failed to initialize pipeline orchestrator: {e}")
            raise
    
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
    
    return app





def run_server(host: str = "0.0.0.0", port: int = 8000, config_path: Optional[str] = None):
    """
    Run the API server
    
    Args:
        host: Host to bind to
        port: Port to bind to
        config_path: Path to pipeline configuration file
    """
    app = create_app(config_path)
    
    logger.info(f"Starting API server on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    run_server()