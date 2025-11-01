#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Complete reset script - deletes ALL data including database
    
.DESCRIPTION
    WARNING: This script will delete:
    - Database (pipeline.db)
    - All clips and outputs
    - All social packages
    - All cache files
    - All temporary files
    
    This is a DESTRUCTIVE operation and cannot be undone!
#>

param(
    [switch]$Force
)

Write-Host "========================================" -ForegroundColor Red
Write-Host "  COMPLETE RESET - ALL DATA WILL BE DELETED" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Red
Write-Host ""

if (-not $Force) {
    Write-Host "⚠️  WARNING: This will delete:" -ForegroundColor Yellow
    Write-Host "   - Database (pipeline.db)" -ForegroundColor Yellow
    Write-Host "   - All episodes and transcriptions" -ForegroundColor Yellow
    Write-Host "   - All clips and outputs" -ForegroundColor Yellow
    Write-Host "   - All social packages" -ForegroundColor Yellow
    Write-Host "   - All cache and temporary files" -ForegroundColor Yellow
    Write-Host ""
    
    $confirmation = Read-Host "Type 'DELETE EVERYTHING' to confirm"
    
    if ($confirmation -ne "DELETE EVERYTHING") {
        Write-Host "❌ Reset cancelled" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "🗑️  Starting complete reset..." -ForegroundColor Yellow
Write-Host ""

# Step 1: Backup database before deletion
if (Test-Path "data\pipeline.db") {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupPath = "data\pipeline.db.FINAL_BACKUP-$timestamp"
    
    Write-Host "Step 1: Creating final backup..." -ForegroundColor Yellow
    try {
        Copy-Item "data\pipeline.db" $backupPath -ErrorAction Stop
        Write-Host "  ✅ Final backup created: $backupPath" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠️  Could not create backup: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "Step 1: No database found to backup" -ForegroundColor Gray
}

# Step 2: Delete database
Write-Host "`nStep 2: Deleting database..." -ForegroundColor Yellow
if (Test-Path "data\pipeline.db") {
    try {
        Remove-Item "data\pipeline.db" -Force -ErrorAction Stop
        Write-Host "  ✅ Database deleted" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ Could not delete database: $_" -ForegroundColor Red
        Write-Host "  💡 Make sure API server is stopped" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "  ℹ️  No database found" -ForegroundColor Gray
}

# Step 3: Delete all outputs
Write-Host "`nStep 3: Deleting all outputs..." -ForegroundColor Yellow
if (Test-Path "data\outputs") {
    try {
        $fileCount = (Get-ChildItem "data\outputs" -Recurse -File).Count
        Remove-Item "data\outputs" -Recurse -Force -ErrorAction Stop
        Write-Host "  ✅ Deleted outputs directory ($fileCount files)" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ Could not delete outputs: $_" -ForegroundColor Red
    }
} else {
    Write-Host "  ℹ️  No outputs directory found" -ForegroundColor Gray
}

# Step 4: Delete all social packages
Write-Host "`nStep 4: Deleting social packages..." -ForegroundColor Yellow
if (Test-Path "data\social_packages") {
    try {
        $fileCount = (Get-ChildItem "data\social_packages" -Recurse -File).Count
        Remove-Item "data\social_packages" -Recurse -Force -ErrorAction Stop
        Write-Host "  ✅ Deleted social packages ($fileCount files)" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ Could not delete social packages: $_" -ForegroundColor Red
    }
} else {
    Write-Host "  ℹ️  No social packages directory found" -ForegroundColor Gray
}

# Step 5: Delete metadata
Write-Host "`nStep 5: Deleting metadata..." -ForegroundColor Yellow
if (Test-Path "data\meta") {
    try {
        $fileCount = (Get-ChildItem "data\meta" -Recurse -File).Count
        Remove-Item "data\meta" -Recurse -Force -ErrorAction Stop
        Write-Host "  ✅ Deleted metadata ($fileCount files)" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ Could not delete metadata: $_" -ForegroundColor Red
    }
} else {
    Write-Host "  ℹ️  No metadata directory found" -ForegroundColor Gray
}

# Step 6: Delete cache
Write-Host "`nStep 6: Deleting cache..." -ForegroundColor Yellow
if (Test-Path "data\cache") {
    try {
        $fileCount = (Get-ChildItem "data\cache" -Recurse -File).Count
        Remove-Item "data\cache" -Recurse -Force -ErrorAction Stop
        Write-Host "  ✅ Deleted cache ($fileCount files)" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ Could not delete cache: $_" -ForegroundColor Red
    }
} else {
    Write-Host "  ℹ️  No cache directory found" -ForegroundColor Gray
}

# Step 7: Delete temp files
Write-Host "`nStep 7: Deleting temp files..." -ForegroundColor Yellow
if (Test-Path "data\temp") {
    try {
        $fileCount = (Get-ChildItem "data\temp" -Recurse -File).Count
        Remove-Item "data\temp" -Recurse -Force -ErrorAction Stop
        Write-Host "  ✅ Deleted temp files ($fileCount files)" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ Could not delete temp files: $_" -ForegroundColor Red
    }
} else {
    Write-Host "  ℹ️  No temp directory found" -ForegroundColor Gray
}

# Step 8: Delete old database backups (optional)
Write-Host "`nStep 8: Cleaning old database backups..." -ForegroundColor Yellow
if (Test-Path "data\pipeline.db.backup-*") {
    try {
        $backups = Get-ChildItem "data\pipeline.db.backup-*"
        $backupCount = $backups.Count
        $backups | Remove-Item -Force -ErrorAction Stop
        Write-Host "  ✅ Deleted $backupCount old backups" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠️  Could not delete some backups: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ℹ️  No old backups found" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Complete Reset Finished!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "What was deleted:" -ForegroundColor White
Write-Host "  ✅ Database (pipeline.db)" -ForegroundColor Green
Write-Host "  ✅ All episodes and transcriptions" -ForegroundColor Green
Write-Host "  ✅ All clips and outputs" -ForegroundColor Green
Write-Host "  ✅ All social packages" -ForegroundColor Green
Write-Host "  ✅ All cache and metadata" -ForegroundColor Green
Write-Host "  ✅ All temporary files" -ForegroundColor Green
Write-Host ""
Write-Host "What was preserved:" -ForegroundColor White
Write-Host "  ✅ Source video files (if in separate location)" -ForegroundColor Green
Write-Host "  ✅ Configuration files" -ForegroundColor Green
Write-Host "  ✅ Final database backup (if created)" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Start API server:" -ForegroundColor White
Write-Host "     python src/cli.py --config config/pipeline.yaml api --port 8000" -ForegroundColor Gray
Write-Host "  2. Process episodes:" -ForegroundColor White
Write-Host "     python process_episode.py" -ForegroundColor Gray
Write-Host "  3. Generate clips:" -ForegroundColor White
Write-Host "     python process_clips.py" -ForegroundColor Gray
Write-Host ""
Write-Host "✅ System is now in a clean state!" -ForegroundColor Green
