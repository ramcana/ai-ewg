# Migration Guide: Upgrading to CLI-Based Pipeline

This guide helps you migrate from the script-based pipeline to the new CLI-based system.

## What's Changed

### Before (Script-Based)
```powershell
python discover_now.py
python scripts/generate-html.ps1
# Manual state tracking with files
```

### After (CLI-Based)
```powershell
ai-ewg discover
ai-ewg web build
# Automatic state tracking in SQLite registry
```

## Migration Steps

### 1. Install New Dependencies

```powershell
# Update requirements
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Verify CLI is available
ai-ewg version
```

### 2. Create Configuration File

```powershell
# Copy example config
cp config/system.yaml.example config/system.yaml

# Edit config/system.yaml with your paths
```

**Key settings to update:**
- `source_paths`: Your video directories
- `registry_db_path`: Where to store the database
- `transcription.model`: Your preferred Whisper model
- `web.site_url`: Your site URL

### 3. Initialize Registry Database

```powershell
ai-ewg db init
```

This creates `data/registry.db` with tables for:
- Episodes (with state tracking)
- Artifacts (generated files)
- People (disambiguated entities)
- Entity mentions
- Processing runs (audit trail)
- Entity cache

### 4. Import Existing Videos

```powershell
# Discover and register all existing videos
ai-ewg discover

# Check what was found
ai-ewg db status
```

The registry will:
- Compute SHA256 hashes for change detection
- Track file size and modification time
- Set initial state to `NEW`

### 5. Map Old Scripts to New Commands

| Old Script | New CLI Command | Notes |
|------------|-----------------|-------|
| `discover_now.py` | `ai-ewg discover` | Now tracks in database |
| `scripts/generate-html.ps1` | `ai-ewg web build` | Uses Jinja2 templates |
| `scripts/generate-html-ai.ps1` | `ai-ewg enrich entities` | Entity extraction |
| Manual transcription | `ai-ewg transcribe` | Integrated with registry |
| Manual diarization | `ai-ewg diarize` | Integrated with registry |

### 6. Update n8n Workflows

**Old n8n node:**
```json
{
  "command": "python",
  "arguments": ["discover_now.py"],
  "workingDirectory": "D:\\n8n\\ai-ewg"
}
```

**New n8n node:**
```json
{
  "command": "ai-ewg",
  "arguments": ["discover"],
  "workingDirectory": "D:\\n8n\\ai-ewg"
}
```

**Parse JSON output:**
```javascript
// In n8n Code node
const output = $input.first().json.stdout;
const result = JSON.parse(output);
return { success: result.success, count: result.count };
```

### 7. Migrate Existing Data (Optional)

If you have existing transcripts, enriched JSON, or HTML:

```powershell
# Register existing artifacts
python scripts/migrate_existing_artifacts.py
```

Create `scripts/migrate_existing_artifacts.py`:

```python
from pathlib import Path
from src.ai_ewg.core.registry import Registry
from src.ai_ewg.core.models import ArtifactKind, EpisodeState
from src.ai_ewg.core.settings import get_settings

settings = get_settings(Path("config/system.yaml"))
registry = Registry(settings.registry_db_path)

# Find existing transcripts
for txt_file in Path("data/transcripts/txt").glob("*.txt"):
    episode_id = txt_file.stem
    episode = registry.get_episode(episode_id)
    
    if episode:
        # Register artifact
        registry.register_artifact(
            episode_id=episode_id,
            kind=ArtifactKind.TRANSCRIPT_TXT,
            rel_path=txt_file,
        )
        
        # Update state
        registry.update_episode_state(episode_id, EpisodeState.TRANSCRIBED)
        print(f"Migrated: {episode_id}")
```

## Breaking Changes

### 1. State Management

**Before:** File-based (presence of files indicated completion)
**After:** Database-based (explicit state machine)

States: `NEW → NORMALIZED → TRANSCRIBED → DIARIZED → ENRICHED → RENDERED`

### 2. Configuration

**Before:** `.env` only
**After:** `config/system.yaml` + `.env` (YAML takes precedence)

Environment variables now use `AIEWG_` prefix:
```env
AIEWG_LOG_LEVEL=DEBUG
AIEWG_TRANSCRIPTION__MODEL=large-v3
```

### 3. Logging

**Before:** Text logs to console
**After:** Structured JSON logs to `data/logs/*.jsonl` + rich console output

### 4. Episode IDs

**Before:** Full file paths
**After:** URL-safe slugs (e.g., `newsroom-2024-bb580`)

The registry stores both the slug and absolute path.

### 5. Artifacts

**Before:** Scattered across directories
**After:** Tracked in registry with:
- Kind (transcript, diarization, HTML, etc.)
- SHA256 hash
- Generation timestamp
- Model version used

## Backward Compatibility

### Old Scripts Still Work

Your existing scripts (`discover_now.py`, etc.) continue to work. The CLI is additive, not replacing.

### Gradual Migration

You can migrate stage-by-stage:

1. Start with `ai-ewg discover` (replaces `discover_now.py`)
2. Keep using your transcription scripts
3. Gradually adopt `ai-ewg transcribe`, `ai-ewg enrich`, etc.

### Coexistence

The registry and old file-based approach can coexist:
- CLI commands check registry state
- Old scripts write files as before
- Run `ai-ewg discover` periodically to sync registry

## Testing the Migration

### 1. Dry Run Discovery

```powershell
ai-ewg discover --dry-run
```

### 2. Process One Episode

```powershell
# Pick a test episode
ai-ewg transcribe --episode newsroom-2024-bb580
ai-ewg web build --episode newsroom-2024-bb580
```

### 3. Check Database

```powershell
ai-ewg db status
```

### 4. Compare Outputs

Compare old vs new HTML output:
- Old: `data/public/shows/newsroom/newsroom-2024-bb580.html` (if it exists)
- New: Same location, but with JSON-LD structured data

## Rollback Plan

If you need to rollback:

1. **Keep old scripts** - Don't delete them during migration
2. **Database is separate** - Registry doesn't modify existing files
3. **Backup data/** - Before running CLI commands with `--force`

```powershell
# Backup
cp -r data data_backup_$(Get-Date -Format 'yyyyMMdd')

# If needed, restore
rm -r data
mv data_backup_20241019 data
```

## Performance Improvements

The new CLI system provides:

- **Idempotency**: Skip already-processed episodes automatically
- **Concurrency**: Process multiple episodes in parallel (configurable)
- **Caching**: Entity disambiguation cached in database
- **Resume**: Crash recovery via state machine
- **Audit Trail**: Full history in `runs` table

## Getting Help

```powershell
# General help
ai-ewg --help

# Command-specific help
ai-ewg discover --help
ai-ewg transcribe --help

# Check version
ai-ewg version

# Database status
ai-ewg db status
```

## Next Steps

1. Read [QUICKSTART_CLI.md](docs/QUICKSTART_CLI.md) for detailed CLI usage
2. Review [config/system.yaml.example](config/system.yaml.example) for all settings
3. Check [templates/](templates/) to customize HTML output
4. See [tests/](tests/) for example usage patterns

## Support

If you encounter issues:

1. Check `data/logs/*.jsonl` for detailed error logs
2. Run with `--verbose` flag for more output
3. Verify config with `ai-ewg db status`
4. Test with a single episode first
