# Project Structure

Clean, organized structure for the Video Processing Pipeline with AI enhancement.

---

## 📂 Directory Layout

```
ai-ewg/
├── 📄 README.md                    # Main project documentation
├── 📄 ROADMAP.md                   # Project roadmap and future plans
├── 📄 PROJECT_STRUCTURE.md         # This file
├── 📄 requirements.txt             # Python dependencies
├── 📄 requirements-api.txt         # API-specific dependencies
│
├── 📚 docs/                        # All documentation
│   ├── README.md                   # Documentation index
│   ├── setup/                      # Installation & setup guides
│   │   ├── OLLAMA_SETUP.md
│   │   ├── QUICK_START_OLLAMA.md
│   │   ├── N8N_FOLDER_SETUP_GUIDE.md
│   │   └── N8N_TESTING_GUIDE.md
│   ├── architecture/               # System architecture
│   │   ├── N8N_ARCHITECTURE_EXPLAINED.md
│   │   └── PART1_PROCESSING_PLAN.md
│   └── updates/                    # Feature updates & fixes
│       ├── HOST_NAME_UPDATE.md
│       ├── HTML_IMPROVEMENTS_SUMMARY.md
│       ├── N8N_WORKFLOW_UPDATE.md
│       ├── OLLAMA_IMPLEMENTATION_SUMMARY.md
│       ├── REPROCESS_FOR_AI_HTML.md
│       └── WEBARTIFACT_FIX.md
│
├── ⚙️  config/                     # Configuration files
│   ├── .env                        # Environment variables (gitignored)
│   ├── .env.example                # Example environment variables
│   ├── pipeline.yaml               # Pipeline configuration
│   ├── n8n_workflow_ai_ready.json  # n8n workflow config
│   └── README_n8n_all_in_one.txt   # n8n setup notes
│
├── 🔧 scripts/                     # Utility scripts
│   ├── setup-system.ps1            # System setup script
│   ├── install-gpu.ps1             # GPU setup for Whisper
│   ├── generate-html.ps1           # HTML generation (legacy)
│   ├── generate-html-ai.ps1        # AI-enhanced HTML generation
│   ├── discover_videos.py          # Video discovery utility
│   ├── discover_videos.ps1         # Video discovery (PowerShell)
│   ├── test_api_request.ps1        # API testing script
│   ├── test_process_episode.ps1    # Episode processing test
│   └── test_folder_processing.py   # Folder processing test
│
├── 💻 src/                         # Source code
│   ├── __init__.py
│   ├── cli.py                      # Command-line interface
│   │
│   ├── api/                        # FastAPI server
│   │   ├── __init__.py
│   │   ├── server.py               # API server
│   │   ├── endpoints.py            # API endpoints
│   │   └── models.py               # Request/response models
│   │
│   ├── core/                       # Core processing modules
│   │   ├── __init__.py
│   │   ├── config.py               # Configuration management
│   │   ├── database.py             # SQLite database
│   │   ├── exceptions.py           # Custom exceptions
│   │   ├── logging.py              # Logging setup
│   │   ├── models.py               # Data models
│   │   ├── ollama_client.py        # Ollama AI client
│   │   ├── orchestrator.py         # Pipeline orchestrator
│   │   ├── web_artifacts.py        # HTML generation
│   │   ├── journalistic_formatter.py  # Article formatting
│   │   └── ...                     # Other core modules
│   │
│   ├── stages/                     # Pipeline stages
│   │   ├── __init__.py
│   │   ├── discovery_stage.py      # Video discovery
│   │   ├── preparation_stage.py    # Audio extraction
│   │   ├── transcription_stage.py  # Whisper transcription
│   │   ├── enrichment_stage.py     # AI enrichment
│   │   └── rendering_stage.py      # HTML rendering
│   │
│   └── utils/                      # Utility modules
│       ├── __init__.py
│       └── transcript_cleaner.py   # Transcript cleaning
│
├── 🧪 tests/                       # Unit & integration tests
│   ├── __init__.py
│   ├── run_tests.py                # Test runner
│   ├── test_all_components.py
│   ├── test_core_setup.py
│   └── ...                         # Other test files
│
├── 🔄 n8n_workflows/               # n8n workflow definitions
│   ├── configurable_processing_v2.json  # Main workflow
│   ├── batch_processing.json
│   ├── folder_based_processing.json
│   └── ...                         # Other workflows
│
├── 🎬 test_videos/                 # Test video files
│   └── newsroom/
│       └── 2024/
│           └── BB580.mp4           # Sample test video
│
├── 💾 data/                        # Data storage
│   ├── enriched/                   # AI enrichment results (JSON)
│   ├── public/                     # Generated HTML artifacts
│   │   └── shows/
│   │       └── {show}/
│   │           └── {episode}/
│   ├── transcripts/                # Raw transcripts
│   └── videos/                     # Processed videos
│
├── 📊 output/                      # Output artifacts
│   ├── indices/                    # Search indices
│   │   ├── hosts/
│   │   ├── shows/
│   │   └── global.json
│   └── search/                     # Search data
│
├── 📝 logs/                        # Log files
│   ├── pipeline.log                # Main pipeline log
│   └── pipeline_errors.log         # Error log
│
├── 🛠️  utils/                      # Legacy utilities (to be refactored)
│   ├── diarize.py
│   ├── disambiguate.py
│   └── ...
│
└── 🐍 venv/                        # Python virtual environment
    └── ...                         # Virtual environment files
```

---

## 🎯 Key Components

### **Source Code (`src/`)**
Main application code organized by function:
- **API**: FastAPI server for n8n integration
- **Core**: Orchestrator, database, AI clients, HTML generation
- **Stages**: Pipeline stages (discovery → rendering)
- **Utils**: Helper functions

### **Documentation (`docs/`)**
All guides and explanations:
- **Setup**: Installation and configuration guides
- **Architecture**: System design documents
- **Updates**: Feature additions and bug fixes

### **Configuration (`config/`)**
Settings and environment:
- Pipeline configuration (YAML)
- Environment variables (.env)
- n8n workflow definitions

### **Scripts (`scripts/`)**
Utility scripts for:
- System setup
- Testing
- Video discovery
- HTML generation

### **Data Flow**
```
test_videos/ → data/enriched/ → data/public/ → output/
    ↓              ↓                  ↓             ↓
  Input        AI Analysis      HTML Pages     Indices
```

---

## 🚀 Quick Start

### 1. **Setup**
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp config/.env.example config/.env
# Edit config/.env with your settings

# Start Ollama
ollama serve
```

### 2. **Run Pipeline**
```bash
# Start API server
python -m src.api.server

# Or use CLI
python -m src.cli process --episode-id "newsroom-2024-bb580"
```

### 3. **Use n8n**
```
1. Open n8n: http://localhost:5678
2. Import workflow: n8n_workflows/configurable_processing_v2.json
3. Configure and execute
```

---

## 📋 File Types

### **Python Files (`.py`)**
- Application code
- Tests
- Utilities

### **Markdown (`.md`)**
- Documentation
- Guides
- Readmes

### **JSON (`.json`)**
- Configuration
- n8n workflows
- Enrichment data

### **YAML (`.yaml`)**
- Pipeline configuration
- Settings

### **PowerShell (`.ps1`)**
- Windows automation scripts
- Setup utilities

---

## 🧹 Maintenance

### **Clean Up**
```bash
# Remove Python cache
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type d -name ".pytest_cache" -exec rm -rf {} +

# Remove log files (keep directory)
rm logs/*.log
```

### **Update Dependencies**
```bash
pip freeze > requirements.txt
```

### **Backup**
Important directories to backup:
- `data/enriched/` - AI analysis results
- `data/public/` - Generated HTML
- `config/.env` - Environment settings (DO NOT commit)

---

## 🔐 Gitignore

Not tracked by git:
- `venv/` - Virtual environment
- `__pycache__/` - Python cache
- `.pytest_cache/` - Test cache
- `config/.env` - Secrets
- `data/` - Generated data
- `output/` - Output artifacts
- `logs/*.log` - Log files

---

## 📊 Metrics

```
Total Directories: ~15 key folders
Python Modules: ~50+ files
Documentation: 13 guides
n8n Workflows: 8 workflows
Scripts: 10 utilities
```

---

## 🎯 Navigation Tips

**Looking for...**
- **Setup guide**: `docs/setup/OLLAMA_SETUP.md`
- **Architecture**: `docs/architecture/N8N_ARCHITECTURE_EXPLAINED.md`
- **Latest updates**: `docs/updates/`
- **Configuration**: `config/pipeline.yaml`
- **Testing**: `scripts/test_*.ps1` or `tests/`
- **Source code**: `src/` organized by component

---

## 🔄 Workflow

```
1. Video Input (test_videos/)
   ↓
2. Discovery Stage (src/stages/discovery_stage.py)
   ↓
3. Audio Extraction (src/stages/preparation_stage.py)
   ↓
4. Transcription (src/stages/transcription_stage.py + Whisper)
   ↓
5. AI Enrichment (src/stages/enrichment_stage.py + Ollama)
   ↓
6. HTML Generation (src/stages/rendering_stage.py + WebArtifactGenerator)
   ↓
7. Output (data/public/)
```

---

## 📞 Support

- **Documentation**: See `docs/README.md`
- **Issues**: Check `logs/pipeline.log`
- **Architecture**: Read `docs/architecture/N8N_ARCHITECTURE_EXPLAINED.md`

---

**Last Updated**: October 19, 2025  
**Version**: 1.0  
**Status**: ✅ Production Ready
