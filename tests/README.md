# AI Enrichment Pipeline Tests

This directory contains all test files for the AI enrichment pipeline components.

## Test Structure

```
tests/
├── __init__.py                 # Package initialization
├── README.md                   # This file
├── run_tests.py               # Test runner script
├── test_setup.py              # Environment and dependency tests
├── test_all_components.py     # Individual component unit tests
└── test_integration.py        # End-to-end integration tests
```

## Running Tests

### Run All Tests

```bash
python tests/run_tests.py
```

### Run Individual Tests

```bash
# Test environment setup
python tests/test_setup.py

# Test individual components
python tests/test_all_components.py

# Test full pipeline integration
python tests/test_integration.py
```

## Test Coverage

### test_setup.py

- Python environment validation
- Required package availability
- Configuration file validation
- Directory structure checks

### test_all_components.py

- Entity extraction (spaCy method)
- Diarization validation functions
- Proficiency scoring algorithms
- File I/O operations
- Error handling

### test_integration.py

- End-to-end pipeline execution
- Component integration
- Data flow validation
- Output format verification

## Test Data

Tests use synthetic data and mock objects to avoid dependencies on:

- External APIs (Wikidata, Ollama)
- Audio files
- Large language models

## Adding New Tests

1. Create test file following naming convention: `test_*.py`
2. Add to `run_tests.py` if it should be part of the main suite
3. Use proper imports for utils modules:
   ```python
   sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
   ```

## Dependencies

Tests require the same dependencies as the main pipeline:

- spacy (with en_core_web_lg model)
- requests
- Standard library modules

Optional for full functionality:

- pyannote.audio
- torch
- ollama (running locally)
