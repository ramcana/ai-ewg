# CI/CD Pipeline Guide

This guide explains the Continuous Integration/Continuous Deployment (CI/CD) pipeline for the AI Video Processing Pipeline project.

## Overview

The CI/CD pipeline is built with **GitHub Actions** and runs automatically on every push and pull request to ensure code quality, security, and functionality.

## Pipeline Jobs

### 1. **Lint & Code Quality** 🔍
Checks code style, formatting, and type correctness.

**Tools:**
- **Ruff**: Fast Python linter and formatter
- **MyPy**: Static type checker
- **Bandit**: Security vulnerability scanner

**Run Locally:**
```powershell
# Install dev dependencies
pip install -r requirements-dev.txt

# Run linting
ruff check .
ruff format .

# Type checking
mypy src/ utils/ --ignore-missing-imports

# Security scan
bandit -r src/ utils/
```

### 2. **Dependency Security** 🔒
Scans for known vulnerabilities in dependencies.

**Tools:**
- **Safety**: Checks dependencies against vulnerability database
- **pip-audit**: Audits Python packages for security issues

**Run Locally:**
```powershell
pip install safety pip-audit
safety check
pip-audit --requirement requirements.txt
```

### 3. **Unit Tests (CPU)** ✅
Runs pytest test suite with CPU-only tests and mocked models.

**Environment Variables:**
- `DIARIZE_DEVICE=cpu` - Force CPU mode
- `SKIP_GPU_TESTS=1` - Skip GPU-dependent tests
- `MOCK_MODELS=1` - Use mocked ML models

**Run Locally:**
```powershell
# Set environment variables
$env:DIARIZE_DEVICE="cpu"
$env:SKIP_GPU_TESTS="1"
$env:MOCK_MODELS="1"

# Run tests
pytest tests/ -v -m "not gpu"

# With coverage
pytest tests/ -v -m "not gpu" --cov=src --cov=utils --cov-report=html
```

**Test Markers:**
- `@pytest.mark.gpu` - Tests requiring GPU
- `@pytest.mark.cpu` - CPU-compatible tests
- `@pytest.mark.slow` - Long-running tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.mock` - Tests with mocked services

### 4. **Integration Tests** 🔗
Tests component interactions with lightweight scenarios.

**Run Locally:**
```powershell
$env:MOCK_MODELS="1"
$env:MOCK_OLLAMA="1"
pytest tests/test_integration.py -v -m "not gpu and not slow"
```

### 5. **Docker Build** 🐳
Builds Docker image for containerized deployment.

**Run Locally:**
```powershell
# Build image
docker build -t ai-video-pipeline:latest .

# Build specific stage
docker build --target development -t ai-video-pipeline:dev .

# Run container
docker run -it --rm ai-video-pipeline:latest
```

## Pytest Configuration

### Test Markers

Mark tests to control when they run:

```python
import pytest

# Skip in CI (GPU required)
@pytest.mark.gpu
def test_cuda_diarization():
    assert torch.cuda.is_available()

# Always runs (CPU compatible)
@pytest.mark.cpu
def test_audio_extraction():
    assert extract_audio("video.mp4")

# Skip by default (too slow)
@pytest.mark.slow
def test_full_pipeline():
    process_entire_library()

# Mock external services
@pytest.mark.mock
def test_ollama_extraction(mocker):
    mock_ollama = mocker.patch('ollama.generate')
    # Test with mocked response
```

### Running Specific Test Categories

```powershell
# CPU-only tests
pytest -m "cpu"

# Skip GPU and slow tests
pytest -m "not gpu and not slow"

# Only integration tests
pytest -m "integration"

# Only unit tests
pytest -m "unit and not integration"
```

## Local Development Workflow

### 1. Install Development Dependencies
```powershell
pip install -r requirements-dev.txt
```

### 2. Pre-commit Checks
Before committing code, run:

```powershell
# Format code
ruff format .

# Check linting
ruff check .

# Type check
mypy src/ utils/

# Run tests
pytest tests/ -m "not gpu and not slow"
```

### 3. Pre-commit Hooks (Optional)
Automate checks before every commit:

```powershell
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

## CI/CD Triggers

The pipeline runs on:

- ✅ **Push to `master`, `main`, or `dev` branches**
- ✅ **Pull requests to `master`, `main`, or `dev`**
- ✅ **Manual workflow dispatch** (via GitHub Actions UI)

## Environment Configuration

### CI Environment Variables

Set in GitHub repository settings under **Settings → Secrets and variables → Actions**:

```
CODECOV_TOKEN         # Optional: For coverage reporting
DOCKER_USERNAME       # Optional: For Docker Hub push
DOCKER_PASSWORD       # Optional: For Docker Hub push
```

### Test Environment Variables

Set in your workflow or locally:

```yaml
DIARIZE_DEVICE: cpu           # Use CPU for diarization
SKIP_GPU_TESTS: "1"          # Skip GPU-dependent tests
MOCK_MODELS: "1"             # Mock ML model loading
MOCK_OLLAMA: "1"             # Mock Ollama API calls
PYTHONPATH: /app             # Python module search path
```

## Coverage Reports

View coverage reports:

1. **Local HTML Report:**
   ```powershell
   pytest --cov=src --cov=utils --cov-report=html
   # Open htmlcov/index.html in browser
   ```

2. **CI Artifacts:**
   - Download from GitHub Actions workflow run
   - Available under "Artifacts" section

3. **Codecov (Optional):**
   - Sign up at https://codecov.io
   - Add `CODECOV_TOKEN` to GitHub secrets
   - View reports at https://codecov.io/gh/[your-username]/[repo]

## Docker Usage

### Multi-stage Builds

The Dockerfile has multiple stages:

```powershell
# Development (includes test tools)
docker build --target development -t ai-pipeline:dev .

# Production (minimal, optimized)
docker build --target production -t ai-pipeline:prod .

# Run tests in container
docker run --rm ai-pipeline:dev pytest tests/
```

### Docker Compose (Future)

For local development with dependencies:

```yaml
version: '3.8'
services:
  pipeline:
    build:
      context: .
      target: development
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - DIARIZE_DEVICE=cpu
      - MOCK_MODELS=1
```

## Troubleshooting

### Common Issues

**1. Import Errors in Tests**
```powershell
# Ensure PYTHONPATH includes project root
$env:PYTHONPATH="d:\n8n\ai-ewg"
pytest tests/
```

**2. GPU Tests Running in CI**
```python
# Mark GPU tests properly
@pytest.mark.gpu
def test_cuda_feature():
    pass
```

**3. Slow Tests Timing Out**
```python
# Mark slow tests
@pytest.mark.slow
@pytest.mark.timeout(300)  # 5 minute timeout
def test_long_process():
    pass
```

**4. Missing Dependencies in CI**
```yaml
# Ensure requirements-dev.txt includes all test dependencies
pytest>=8.0.0
pytest-mock>=3.12.0
pytest-timeout>=2.2.0
```

## Best Practices

1. ✅ **Always run tests locally before pushing**
2. ✅ **Use test markers appropriately** (`@pytest.mark.cpu`, `@pytest.mark.gpu`)
3. ✅ **Mock external services** (Ollama, Wikipedia, APIs)
4. ✅ **Keep tests fast** (< 5 seconds per test when possible)
5. ✅ **Write integration tests for critical paths**
6. ✅ **Update documentation when adding new CI features**

## Continuous Improvement

Consider adding in the future:

- **Automated dependency updates** (Dependabot, Renovate)
- **Performance benchmarking** (pytest-benchmark)
- **End-to-end tests** with real video samples
- **Deployment automation** to staging/production
- **Slack/Discord notifications** for CI status

## References

- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [Pytest Documentation](https://docs.pytest.org/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
