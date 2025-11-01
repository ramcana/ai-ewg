# Clear All Generated Data - Fresh Start
# This script removes all generated data while preserving source files and configuration

Write-Host "🧹 Clearing all generated data for fresh start..." -ForegroundColor Cyan
Write-Host ""

# Stop any running processes
Write-Host "🛑 Checking for running processes..." -ForegroundColor Yellow
$apiProcess = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*api*" }
if ($apiProcess) {
    Write-Host "  ⚠️  API server is running. Please stop it first (Ctrl+C in the terminal)" -ForegroundColor Red
    Write-Host "  Press Enter after stopping the server to continue..."
    Read-Host
}

# Backup database (optional)
Write-Host "💾 Creating database backup..." -ForegroundColor Yellow
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "archive/db_backups"
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
}

if (Test-Path "data/pipeline.db") {
    Copy-Item "data/pipeline.db" "$backupDir/pipeline_backup_$timestamp.db"
    Write-Host "  ✅ Database backed up to: $backupDir/pipeline_backup_$timestamp.db" -ForegroundColor Green
}

Write-Host ""
Write-Host "🗑️  Removing generated data..." -ForegroundColor Yellow
Write-Host ""

# 1. Clear database
Write-Host "📊 Clearing database..." -ForegroundColor Cyan
if (Test-Path "data/pipeline.db") {
    Remove-Item "data/pipeline.db" -Force
    Write-Host "  ✅ Removed pipeline.db" -ForegroundColor Green
}
if (Test-Path "data/pipeline.db-shm") {
    Remove-Item "data/pipeline.db-shm" -Force
}
if (Test-Path "data/pipeline.db-wal") {
    Remove-Item "data/pipeline.db-wal" -Force
}

# 2. Clear outputs
Write-Host "📁 Clearing outputs..." -ForegroundColor Cyan
if (Test-Path "data/outputs") {
    $outputCount = (Get-ChildItem "data/outputs" -Recurse -File).Count
    Remove-Item "data/outputs" -Recurse -Force
    Write-Host "  ✅ Removed data/outputs ($outputCount files)" -ForegroundColor Green
}

# 3. Clear transcripts
Write-Host "📝 Clearing transcripts..." -ForegroundColor Cyan
if (Test-Path "data/transcripts") {
    $transcriptCount = (Get-ChildItem "data/transcripts" -Recurse -File).Count
    Remove-Item "data/transcripts" -Recurse -Force
    Write-Host "  ✅ Removed data/transcripts ($transcriptCount files)" -ForegroundColor Green
}

# 4. Clear social packages
Write-Host "📱 Clearing social packages..." -ForegroundColor Cyan
if (Test-Path "data/social_packages") {
    $socialCount = (Get-ChildItem "data/social_packages" -Recurse -File).Count
    Remove-Item "data/social_packages" -Recurse -Force
    Write-Host "  ✅ Removed data/social_packages ($socialCount files)" -ForegroundColor Green
}

# 5. Clear clips
Write-Host "🎬 Clearing clips..." -ForegroundColor Cyan
if (Test-Path "data/clips") {
    $clipCount = (Get-ChildItem "data/clips" -Recurse -File).Count
    Remove-Item "data/clips" -Recurse -Force
    Write-Host "  ✅ Removed data/clips ($clipCount files)" -ForegroundColor Green
}

# 6. Clear temp uploaded files
Write-Host "📤 Clearing temp uploads..." -ForegroundColor Cyan
if (Test-Path "data/temp/uploaded") {
    $uploadCount = (Get-ChildItem "data/temp/uploaded" -File).Count
    Get-ChildItem "data/temp/uploaded" -File | Remove-Item -Force
    Write-Host "  ✅ Removed $uploadCount uploaded file(s)" -ForegroundColor Green
}

# 7. Clear logs (optional - keep recent ones)
Write-Host "📋 Clearing old logs..." -ForegroundColor Cyan
if (Test-Path "logs") {
    $oldLogs = Get-ChildItem "logs" -Filter "*.log" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) }
    if ($oldLogs) {
        $oldLogs | Remove-Item -Force
        Write-Host "  ✅ Removed $($oldLogs.Count) old log file(s)" -ForegroundColor Green
    } else {
        Write-Host "  ℹ️  No old logs to remove" -ForegroundColor Gray
    }
}

# 8. Clear cache directories
Write-Host "🗂️  Clearing caches..." -ForegroundColor Cyan
$cacheDirs = @("staging", "__pycache__", ".pytest_cache")
foreach ($dir in $cacheDirs) {
    if (Test-Path $dir) {
        Remove-Item $dir -Recurse -Force
        Write-Host "  ✅ Removed $dir" -ForegroundColor Green
    }
}

# Clear Python cache recursively
Get-ChildItem -Path . -Filter "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force
Write-Host "  ✅ Removed all __pycache__ directories" -ForegroundColor Green

# 9. Recreate necessary directories
Write-Host ""
Write-Host "📁 Recreating directory structure..." -ForegroundColor Yellow
$directories = @(
    "data/outputs",
    "data/transcripts/txt",
    "data/transcripts/vtt", 
    "data/transcripts/json",
    "data/social_packages",
    "data/clips",
    "data/temp/uploaded",
    "logs"
)

foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  ✅ Created $dir" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ✅ CLEANUP COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "📊 Summary:" -ForegroundColor Yellow
Write-Host "  • Database cleared and backed up"
Write-Host "  • All outputs removed"
Write-Host "  • All transcripts removed"
Write-Host "  • All social packages removed"
Write-Host "  • All clips removed"
Write-Host "  • Temp uploads cleared"
Write-Host "  • Cache directories cleared"
Write-Host "  • Directory structure recreated"
Write-Host ""

Write-Host "🎯 What's preserved:" -ForegroundColor Yellow
Write-Host "  • Source videos in test_videos/"
Write-Host "  • Configuration files"
Write-Host "  • Code and scripts"
Write-Host "  • Virtual environment"
Write-Host "  • Database backup in archive/db_backups/"
Write-Host ""

Write-Host "🚀 Next steps:" -ForegroundColor Cyan
Write-Host "  1. Restart API server: python src/cli.py --config config/pipeline.yaml api --port 8000"
Write-Host "  2. Process episodes with new naming system"
Write-Host "  3. Episodes will now use organized folder structure!"
Write-Host ""
Write-Host "✨ Ready for fresh start with new naming system!" -ForegroundColor Green
