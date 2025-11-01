# Root Directory Structure Guide

This document explains what files should remain in the root directory and why.

## ✅ Essential Files (Keep in Root)

### Documentation
- **README.md** - Main project documentation and overview
- **GETTING_STARTED.md** - Quick start guide for new users
- **ROADMAP.md** - Project roadmap and future plans

### Application Entry Points
- **dashboard.py** - Streamlit dashboard (main UI)
- **process_all_videos.py** - Batch video processing script
- **process_clips.py** - Clip generation script
- **process_episode.py** - Single episode processing script

### Server Management
- **start-api-server.ps1** - Start the FastAPI backend server
- **complete_reset_with_stop.ps1** - Complete system reset (stops services, clears data)

### Configuration
- **pyproject.toml** - Python project configuration
- **pytest.ini** - Test configuration
- **requirements.txt** - Python dependencies
- **requirements-api.txt** - API-specific dependencies
- **requirements-cli.txt** - CLI-specific dependencies
- **requirements-dev.txt** - Development dependencies

### Docker
- **Dockerfile** - Container configuration
- **.dockerignore** - Docker ignore patterns

### Git
- **.gitignore** - Git ignore patterns
- **.github/** - GitHub workflows and actions

## 📁 Essential Directories (Keep in Root)

- **src/** - Source code (core pipeline, API, stages)
- **config/** - Configuration files (pipeline.yaml, platforms, etc.)
- **components/** - Streamlit UI components
- **pages/** - Streamlit multi-page app pages
- **templates/** - HTML/Jinja2 templates
- **docs/** - Comprehensive documentation
- **scripts/** - Utility scripts
- **tests/** - Test suite
- **utils/** - Utility modules (diarization, etc.)
- **examples/** - Example configurations and usage
- **n8n_workflows/** - n8n workflow templates
- **data/** - Runtime data (database, outputs, cache)
- **logs/** - Application logs
- **venv/** - Python virtual environment

## 🗑️ Files Moved to Archive

The cleanup script moves these files to `archive/` subdirectories:

### Old Documentation → `archive/old_docs/`
- CLIP_GENERATION_FIX.md
- FSAT_RESULTS.md
- MIGRATION_SUMMARY.md
- QUICK_START_ASYNC.md
- RESTART_INSTRUCTIONS.md
- SOCIAL_PUBLISHING_COMPLETE.md
- SQLITE_FIXES_SUMMARY.md
- UNIFIED_ENVIRONMENT_GUIDE.md
- restart_api_server.md

### Database Backups → `archive/db_backups/`
- pipeline_backup_*.db (all backup files)

### Old Test Files → `archive/old_tests/`
- check_cuda.py
- check_pyannote.py
- test_clip_env.bat
- test_clip_simple.py
- test_clips_fallback.py
- test_clips_quick.py
- test_dependencies.py
- test_feed_validator_implementation.py
- test_install.py
- test_output.html
- test_phase3_robustness.py
- test_phase4_performance.py
- test_simple_import.py
- test_subtitle_debug.py
- verify_episode.py

### Old Setup Scripts → `archive/old_scripts/`
- check_schema.ps1
- cleanup_for_final_test.ps1
- clear_all_data_complete.py
- complete_reset.ps1
- fsat_phase1_checks.ps1
- fsat_phase2_discovery.ps1
- install_clip_dependencies.ps1
- install_ml_current_env.py
- migrate_to_unified_env.ps1
- prepare_fsat.ps1
- setup_cli.ps1
- setup_clip_env.py
- start_server_clip_env.bat
- start_server_new_env.py

### Empty Directories (Removed)
- output/
- outputs/
- temp/
- __pycache__/

## 🚀 Running the Cleanup

```powershell
# Review what will be moved
Get-Content cleanup_root.ps1

# Run the cleanup script
.\cleanup_root.ps1
```

## 📝 After Cleanup

Your root directory will be clean and organized:

```
ai-ewg/
├── README.md                      # Main docs
├── GETTING_STARTED.md             # Quick start
├── ROADMAP.md                     # Roadmap
├── dashboard.py                   # Streamlit UI
├── process_*.py                   # Processing scripts
├── start-api-server.ps1           # Server startup
├── complete_reset_with_stop.ps1   # Reset script
├── requirements*.txt              # Dependencies
├── pyproject.toml                 # Project config
├── src/                           # Source code
├── config/                        # Configuration
├── docs/                          # Documentation
├── data/                          # Runtime data
└── archive/                       # Archived files
    ├── old_docs/
    ├── old_tests/
    ├── db_backups/
    └── old_scripts/
```

## 🔄 Maintenance

- **Keep archived files** for reference but don't clutter root
- **Regular backups** of `data/pipeline.db` go to `archive/db_backups/`
- **New scripts** should go in `scripts/` not root
- **New docs** should go in `docs/` not root
