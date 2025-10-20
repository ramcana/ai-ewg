# Multi-stage Dockerfile for AI Video Processing Pipeline
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ========================================
# Stage 1: Dependencies
# ========================================
FROM base as dependencies

# Copy requirements files
COPY requirements.txt requirements-api.txt ./

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install -r requirements-api.txt

# ========================================
# Stage 2: Application
# ========================================
FROM dependencies as application

# Copy application code
COPY src/ ./src/
COPY utils/ ./utils/
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY pyproject.toml pytest.ini ./

# Create necessary directories
RUN mkdir -p data/audio data/transcripts data/enriched data/public logs output

# Set Python path
ENV PYTHONPATH=/app:$PYTHONPATH

# Default command
CMD ["python", "-m", "src.cli"]

# ========================================
# Stage 3: Development (with dev tools)
# ========================================
FROM application as development

COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

# Copy tests
COPY tests/ ./tests/

# ========================================
# Stage 4: Production (minimal)
# ========================================
FROM application as production

# Remove unnecessary files
RUN rm -rf tests/ scripts/test_* .git

# Run as non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check (adjust based on your API)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Expose API port (if applicable)
EXPOSE 8000

# Run the application
CMD ["python", "-m", "src.api.server"]
