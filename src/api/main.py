"""
Main entry point for the FastAPI application.
This file is used by uvicorn to start the server.
"""

from .server import create_app

# Create the FastAPI app instance
app = create_app()

# This allows running with: uvicorn src.api.main:app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
