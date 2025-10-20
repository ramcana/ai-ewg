# Installation Checklist

Use this checklist to verify your CLI upgrade is complete and working.

## ✅ Pre-Installation

- [ ] Python 3.10+ installed (`python --version`)
- [ ] Virtual environment activated (`.\venv\Scripts\Activate.ps1`)
- [ ] Git repository is clean (commit or stash changes)
- [ ] Backup of `data/` directory created (optional but recommended)

## ✅ Installation

- [ ] Updated dependencies: `pip install -r requirements.txt`
- [ ] Installed CLI: `pip install -e .`
- [ ] CLI available: `ai-ewg version` works
- [ ] Created config: `config\system.yaml` exists
- [ ] Updated paths in `config\system.yaml`
- [ ] Set secrets in `.env` (if using HF_TOKEN, etc.)

## ✅ Database Setup

- [ ] Initialized database: `ai-ewg db init`
- [ ] Database file exists: `data\registry.db`
- [ ] Database status works: `ai-ewg db status`
- [ ] Tables created (check output shows 0 episodes, 0 artifacts, etc.)

## ✅ Discovery Test

- [ ] Dry run works: `ai-ewg discover --dry-run`
- [ ] Dry run shows expected video count
- [ ] Actual discovery: `ai-ewg discover`
- [ ] Episodes registered: `ai-ewg db status` shows count > 0
- [ ] Episode IDs are URL-safe slugs (no spaces, special chars)

## ✅ Single Episode Test

Pick one episode ID from `ai-ewg db status` and test:

- [ ] Normalize: `ai-ewg normalize --episode <id>`
- [ ] State updated to NORMALIZED
- [ ] Transcribe: `ai-ewg transcribe --episode <id>` (if you have transcription code)
- [ ] Transcript files created in `data\transcripts\`
- [ ] State updated to TRANSCRIBED
- [ ] Web build: `ai-ewg web build --episode <id>` (if you have templates)
- [ ] HTML created in `data\public\shows\`

## ✅ Configuration Validation

- [ ] Config loads without errors: `ai-ewg --config config\system.yaml db status`
- [ ] Paths are absolute (no relative paths in config)
- [ ] Log directory exists: `data\logs\`
- [ ] Logs are being written: `data\logs\pipeline_*.jsonl`

## ✅ CLI Features

- [ ] Help works: `ai-ewg --help`
- [ ] Subcommand help: `ai-ewg discover --help`
- [ ] Verbose mode: `ai-ewg --verbose discover --dry-run`
- [ ] JSON output visible on stdout
- [ ] Rich console output visible on stderr

## ✅ n8n Integration (if applicable)

- [ ] n8n can execute: `ai-ewg version`
- [ ] n8n can parse JSON output
- [ ] n8n workflow updated with new commands
- [ ] Test workflow runs successfully
- [ ] Error handling works (check failed episodes)

## ✅ Documentation Review

- [ ] Read `UPGRADE_SUMMARY.md`
- [ ] Read `docs\QUICKSTART_CLI.md`
- [ ] Reviewed `config\system.yaml.example`
- [ ] Understand state machine: NEW → NORMALIZED → TRANSCRIBED → DIARIZED → ENRICHED → RENDERED

## ✅ Code Integration (Next Steps)

- [ ] Identified where to plug in transcription code
- [ ] Identified where to plug in diarization code
- [ ] Identified where to plug in enrichment code
- [ ] Identified where to plug in web generation code
- [ ] Understand how to use `registry.register_artifact()`
- [ ] Understand how to use `registry.update_episode_state()`

## ✅ Testing

- [ ] Unit tests pass: `pytest tests/test_cli.py -v`
- [ ] Registry tests pass: `pytest tests/test_registry.py -v`
- [ ] All tests pass: `pytest -v`
- [ ] Coverage report generated: `pytest --cov=src --cov-report=html`

## ✅ CI/CD (if using GitHub Actions)

- [ ] `.github\workflows\ci.yml` updated
- [ ] Push to GitHub triggers CI
- [ ] CI passes on Windows
- [ ] CI passes on Linux
- [ ] Linting passes (ruff)
- [ ] Type checking passes (mypy)

## ✅ Production Readiness

- [ ] Tested with 5+ episodes end-to-end
- [ ] Verified idempotency (re-running doesn't duplicate)
- [ ] Verified resume (can stop and restart)
- [ ] Checked logs for errors: `data\logs\*.jsonl`
- [ ] Performance acceptable (check `duration_ms` in logs)
- [ ] Database size reasonable (check `data\registry.db` size)

## ✅ Rollback Plan (if needed)

- [ ] Old scripts still available
- [ ] Backup of `data/` exists
- [ ] Know how to restore: `rm -r data; mv data_backup data`
- [ ] Can switch back to old workflow if needed

## 🎉 Installation Complete!

Once all boxes are checked, you're ready to:

1. **Integrate your existing code** into the stage stubs
2. **Update n8n workflows** to use CLI commands
3. **Process your full library** with confidence

## 📞 Support

If any checklist item fails:

1. Check logs: `data\logs\pipeline_*.jsonl`
2. Run with verbose: `ai-ewg --verbose <command>`
3. Check database: `ai-ewg db status`
4. Review documentation: `docs\QUICKSTART_CLI.md`
5. Check GitHub Issues (if applicable)

## 📝 Notes

Use this space for your own notes during installation:

```
Date installed: _______________
Python version: _______________
Issues encountered: _______________
_______________
_______________
```
