#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Complete reset script - stops services and deletes ALL data
#>

Write-Host "========================================" -ForegroundColor Red
Write-Host "  COMPLETE RESET - ALL DATA WILL BE DELETED" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Red
Write-Host ""

Write-Host "⚠️  WARNING: This will:" -ForegroundColor Yellow
Write-Host "   1. Stop API server and Streamlit" -ForegroundColor Yellow
Write-Host "   2. Delete database (pipeline.db)" -ForegroundColor Yellow
Write-Host "   3. Delete all episodes and transcriptions" -ForegroundColor Yellow
Write-Host "   4. Delete all clips and outputs" -ForegroundColor Yellow
Write-Host "   5. Delete all social packages" -ForegroundColor Yellow
Write-Host "   6. Delete all cache and temporary files" -ForegroundColor Yellow
Write-Host ""

$confirmation = Read-Host "Type 'DELETE EVERYTHING' to confirm"

if ($confirmation -ne "DELETE EVERYTHING") {
    Write-Host "❌ Reset cancelled" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🛑 Step 1: Stopping services..." -ForegroundColor Yellow

# Stop Python processes (API server, Streamlit, etc.)
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    Write-Host "  Found $($pythonProcesses.Count) Python process(es)" -ForegroundColor Gray
    foreach ($proc in $pythonProcesses) {
        try {
            $proc | Stop-Process -Force
            Write-Host "  ✅ Stopped process $($proc.Id)" -ForegroundColor Green
        } catch {
            Write-Host "  ⚠️  Could not stop process $($proc.Id): $_" -ForegroundColor Yellow
        }
    }
    Start-Sleep -Seconds 2
} else {
    Write-Host "  ℹ️  No Python processes running" -ForegroundColor Gray
}

# Step 2: Backup database
Write-Host "`n📦 Step 2: Creating final backup..." -ForegroundColor Yellow
if (Test-Path "data\pipeline.db") {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupPath = "data\pipeline.db.FINAL_BACKUP-$timestamp"
    
    try {
        Copy-Item "data\pipeline.db" $backupPath -ErrorAction Stop
        Write-Host "  ✅ Final backup: $backupPath" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠️  Could not create backup: $_" -ForegroundColor Yellow
    }
}

# Step 3: Delete database
Write-Host "`n🗑️  Step 3: Deleting database..." -ForegroundColor Yellow
if (Test-Path "data\pipeline.db") {
    try {
        Remove-Item "data\pipeline.db" -Force -ErrorAction Stop
        Write-Host "  ✅ Database deleted" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ Could not delete database: $_" -ForegroundColor Red
        Write-Host "  💡 Try running script again or manually delete the file" -ForegroundColor Yellow
    }
}

# Step 4: Delete all outputs
Write-Host "`n🗑️  Step 4: Deleting outputs..." -ForegroundColor Yellow
$foldersToDelete = @("data\outputs", "data\social_packages", "data\meta", "data\cache", "data\temp")

foreach ($folder in $foldersToDelete) {
    if (Test-Path $folder) {
        try {
            $fileCount = (Get-ChildItem $folder -Recurse -File -ErrorAction SilentlyContinue).Count
            Remove-Item $folder -Recurse -Force -ErrorAction Stop
            Write-Host "  ✅ Deleted $folder ($fileCount files)" -ForegroundColor Green
        } catch {
            Write-Host "  ⚠️  Could not delete $folder : $_" -ForegroundColor Yellow
        }
    }
}

# Step 5: Clean old backups
Write-Host "`n🧹 Step 5: Cleaning old backups..." -ForegroundColor Yellow
$backups = Get-ChildItem "data\pipeline.db.backup-*" -ErrorAction SilentlyContinue
if ($backups) {
    $backupCount = $backups.Count
    $backups | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host "  ✅ Deleted $backupCount old backups" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ✅ RESET COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "System is now in a clean state." -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Start API server:" -ForegroundColor White
Write-Host "     python src/cli.py --config config/pipeline.yaml api --port 8000" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Process an episode:" -ForegroundColor White
Write-Host "     python process_episode.py" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Generate clips:" -ForegroundColor White
Write-Host "     python process_clips.py" -ForegroundColor Gray
Write-Host ""
