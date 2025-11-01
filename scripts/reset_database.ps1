# Reset Database Script
# Backs up and clears the pipeline database for a fresh start

Write-Host "🔄 Database Reset Script" -ForegroundColor Cyan
Write-Host "========================" -ForegroundColor Cyan
Write-Host ""

# Get the project root directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$dataDir = Join-Path $projectRoot "data"
$dbPath = Join-Path $dataDir "pipeline.db"
$backupsDir = Join-Path $dataDir "backups"

Write-Host "📍 Project root: $projectRoot" -ForegroundColor Gray
Write-Host "📍 Database: $dbPath" -ForegroundColor Gray
Write-Host ""

# Check if database exists
if (-not (Test-Path $dbPath)) {
    Write-Host "ℹ️  No database found - nothing to reset" -ForegroundColor Yellow
    exit 0
}

# Create backups directory
if (-not (Test-Path $backupsDir)) {
    New-Item -ItemType Directory -Path $backupsDir -Force | Out-Null
}

# Create backup with timestamp
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path $backupsDir "pipeline.db.RESET_BACKUP-$timestamp"

Write-Host "💾 Creating backup..." -ForegroundColor Cyan
Copy-Item -Path $dbPath -Destination $backupPath -Force
Write-Host "   ✅ Backup created: $backupPath" -ForegroundColor Green

# Get database size
$dbSize = [math]::Round((Get-Item $dbPath).Length / 1MB, 2)
Write-Host "   📊 Database size: $dbSize MB" -ForegroundColor Gray
Write-Host ""

# Confirm deletion
Write-Host "⚠️  WARNING: This will delete all episode data!" -ForegroundColor Yellow
Write-Host "   - All episodes will be removed" -ForegroundColor Gray
Write-Host "   - All clips metadata will be removed" -ForegroundColor Gray
Write-Host "   - All processing history will be removed" -ForegroundColor Gray
Write-Host "   - Backup saved to: $backupPath" -ForegroundColor Gray
Write-Host ""

$confirmation = Read-Host "Type 'RESET' to confirm deletion"

if ($confirmation -ne "RESET") {
    Write-Host "❌ Reset cancelled" -ForegroundColor Red
    exit 0
}

Write-Host ""
Write-Host "🗑️  Deleting database files..." -ForegroundColor Cyan

# Delete database and related files
$dbFiles = @(
    "pipeline.db",
    "pipeline.db-shm",
    "pipeline.db-wal"
)

foreach ($file in $dbFiles) {
    $filePath = Join-Path $dataDir $file
    if (Test-Path $filePath) {
        Remove-Item -Path $filePath -Force
        Write-Host "   ✅ Deleted: $file" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "✅ Database reset complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Next steps:" -ForegroundColor Yellow
Write-Host "   1. Restart the API server" -ForegroundColor Gray
Write-Host "   2. Restart Streamlit dashboard" -ForegroundColor Gray
Write-Host "   3. Database will be recreated automatically on first use" -ForegroundColor Gray
Write-Host ""
