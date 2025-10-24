# Getting Started - AI Video Processing Pipeline

## 🚀 Quick Start (5 Minutes)

### 1. Start the API Server
```powershell
cd D:\n8n\ai-ewg
.\venv\Scripts\Activate.ps1
python src/cli.py --config config/pipeline.yaml api --port 8000
```

### 2. Import n8n Workflow
- Open n8n: http://localhost:5678
- Import: `n8n_workflows/video_processing_FIXED_v3.json`

### 3. Run Workflow
- Set folder path: `/data/test_videos/newsroom/2024`
- Click "Execute Workflow"
- Done! ✅

---

## 📁 Project Structure

```
ai-ewg/
├── src/              # Python source code
├── config/           # Configuration files
├── n8n_workflows/    # n8n workflow definitions
├── docs/             # Documentation
├── scripts/          # Utility scripts
└── data/             # Database & output files
```

---

## 🔧 Configuration

**Edit `config/pipeline.yaml`:**
```yaml
sources:
  - path: "/data/test_videos/newsroom/2024"
    enabled: true

database:
  backup_enabled: true
  backup_interval_hours: 24
```

---

## 📚 Documentation

- **Quick Reference:** `QUICK_REFERENCE.md` - Common commands
- **Deduplication:** `docs/DEDUPLICATION_SYSTEM.md` - How duplicate detection works
- **Architecture:** `docs/architecture/` - System design
- **Troubleshooting:** Check API logs and n8n workflow output

---

## 🐛 Common Issues

### API Server Won't Start
```powershell
# Check if port 8000 is in use
netstat -ano | findstr :8000

# Use different port
python src/cli.py api --port 8001
```

### Workflow Shows "Undefined"
- Restart API server
- Re-import workflow
- Check "Continue On Fail" is enabled

### Videos Not Discovered
- Check folder path in config
- Verify files are .mp4
- Check API logs for errors

---

## 💡 Key Features

✅ **Auto-Discovery** - Scans folders for videos  
✅ **Deduplication** - SHA256 hash prevents duplicate processing  
✅ **Auto-Backup** - Database backed up every 24 hours  
✅ **Resume Processing** - Continue from any stage  
✅ **Error Handling** - Graceful failure recovery  

---

## 📖 More Information

- **Full Docs:** `docs/` folder
- **Workflow Details:** `n8n_workflows/WORKFLOW_V3_CHANGELOG.md`
- **API Docs:** http://localhost:8000/docs (when running)

---

**Need Help?** Check the logs in `logs/` directory or review the workflow execution in n8n.
