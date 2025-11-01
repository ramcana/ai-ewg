#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Clean up redundant files from root directory
.DESCRIPTION
    Moves old documentation, test files, and database backups to appropriate locations
#>

Write-Host "🧹 Cleaning up root directory..." -ForegroundColor Cyan
Write-Host ""

# Create archive directories
$archiveDir = "archive"
$docsArchiveDir = "$archiveDir/old_docs"
$testsArchiveDir = "$archiveDir/old_tests"
$backupsArchiveDir = "$archiveDir/db_backups"
$scriptsArchiveDir = "$archiveDir/old_scripts"

Write-Host "📁 Creating archive directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $docsArchiveDir | Out-Null
New-Item -ItemType Directory -Force -Path $testsArchiveDir | Out-Null
New-Item -ItemType Directory -Force -Path $backupsArchiveDir | Out-Null
New-Item -ItemType Directory -Force -Path $scriptsArchiveDir | Out-Null

# Move old documentation files
Write-Host "`n📄 Moving old documentation..." -ForegroundColor Yellow
$oldDocs = @(
    "CLIP_GENERATION_FIX.md",
    "FSAT_RESULTS.md",
    "MIGRATION_SUMMARY.md",
    "QUICK_START_ASYNC.md",
    "RESTART_INSTRUCTIONS.md",
    "SOCIAL_PUBLISHING_COMPLETE.md",
    "SQLITE_FIXES_SUMMARY.md",
    "UNIFIED_ENVIRONMENT_GUIDE.md",
    "restart_api_server.md"
)

foreach ($doc in $oldDocs) {
    if (Test-Path $doc) {
        Move-Item $doc $docsArchiveDir -Force
        Write-Host "  ✅ Moved $doc" -ForegroundColor Green
    }
}

# Move database backups
Write-Host "`n💾 Moving database backups..." -ForegroundColor Yellow
$backups = Get-ChildItem "pipeline_backup_*.db" -ErrorAction SilentlyContinue
if ($backups) {
    foreach ($backup in $backups) {
        Move-Item $backup.FullName $backupsArchiveDir -Force
        Write-Host "  ✅ Moved $($backup.Name)" -ForegroundColor Green
    }
}

# Move old test files
Write-Host "`n🧪 Moving old test files..." -ForegroundColor Yellow
$oldTests = @(
    "check_cuda.py",
    "check_pyannote.py",
    "test_clip_env.bat",
    "test_clip_simple.py",
    "test_clips_fallback.py",
    "test_clips_quick.py",
    "test_dependencies.py",
    "test_feed_validator_implementation.py",
    "test_install.py",
    "test_output.html",
    "test_phase3_robustness.py",
    "test_phase4_performance.py",
    "test_simple_import.py",
    "test_subtitle_debug.py",
    "verify_episode.py"
)

foreach ($test in $oldTests) {
    if (Test-Path $test) {
        Move-Item $test $testsArchiveDir -Force
        Write-Host "  ✅ Moved $test" -ForegroundColor Green
    }
}

# Move old setup/migration scripts
Write-Host "`n⚙️  Moving old setup scripts..." -ForegroundColor Yellow
$oldScripts = @(
    "check_schema.ps1",
    "cleanup_for_final_test.ps1",
    "clear_all_data_complete.py",
    "complete_reset.ps1",
    "fsat_phase1_checks.ps1",
    "fsat_phase2_discovery.ps1",
    "install_clip_dependencies.ps1",
    "install_ml_current_env.py",
    "migrate_to_unified_env.ps1",
    "prepare_fsat.ps1",
    "setup_cli.ps1",
    "setup_clip_env.py",
    "start_server_clip_env.bat",
    "start_server_new_env.py"
)

foreach ($script in $oldScripts) {
    if (Test-Path $script) {
        Move-Item $script $scriptsArchiveDir -Force
        Write-Host "  ✅ Moved $script" -ForegroundColor Green
    }
}

# Clean up empty directories
Write-Host "`n🗑️  Cleaning up empty directories..." -ForegroundColor Yellow
$emptyDirs = @("output", "outputs", "temp", "__pycache__")
foreach ($dir in $emptyDirs) {
    if (Test-Path $dir) {
        $items = Get-ChildItem $dir -Force -ErrorAction SilentlyContinue
        if ($items.Count -eq 0) {
            Remove-Item $dir -Force -Recurse
            Write-Host "  ✅ Removed empty directory: $dir" -ForegroundColor Green
        }
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ✅ CLEANUP COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Summary:" -ForegroundColor Cyan
Write-Host "  • Old docs moved to: $docsArchiveDir" -ForegroundColor White
Write-Host "  • Test files moved to: $testsArchiveDir" -ForegroundColor White
Write-Host "  • DB backups moved to: $backupsArchiveDir" -ForegroundColor White
Write-Host "  • Old scripts moved to: $scriptsArchiveDir" -ForegroundColor White
Write-Host ""
Write-Host "🎯 Active files remaining in root:" -ForegroundColor Cyan
Write-Host "  • README.md - Main documentation" -ForegroundColor White
Write-Host "  • GETTING_STARTED.md - Quick start guide" -ForegroundColor White
Write-Host "  • ROADMAP.md - Project roadmap" -ForegroundColor White
Write-Host "  • dashboard.py - Streamlit dashboard" -ForegroundColor White
Write-Host "  • process_*.py - Processing scripts" -ForegroundColor White
Write-Host "  • complete_reset_with_stop.ps1 - Reset script" -ForegroundColor White
Write-Host "  • start-api-server.ps1 - API server startup" -ForegroundColor White
Write-Host ""
