# Migrate clips from old data/outputs location to new data/clips location
# This script moves clips from data/outputs/{episode_id}/clips/ to data/clips/{episode_id}/

Write-Host "🔄 Migrating clips to new location..." -ForegroundColor Cyan
Write-Host ""

# Get the project root directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$oldClipsBase = Join-Path $projectRoot "data\outputs"
$newClipsBase = Join-Path $projectRoot "data\clips"

Write-Host "📍 Project root: $projectRoot" -ForegroundColor Gray
Write-Host "📍 Old clips location: $oldClipsBase" -ForegroundColor Gray
Write-Host "📍 New clips location: $newClipsBase" -ForegroundColor Gray
Write-Host ""

# Check if old clips directory exists
if (-not (Test-Path $oldClipsBase)) {
    Write-Host "✅ No old clips directory found - nothing to migrate" -ForegroundColor Green
    exit 0
}

# Create new clips base directory if it doesn't exist
if (-not (Test-Path $newClipsBase)) {
    New-Item -ItemType Directory -Path $newClipsBase -Force | Out-Null
    Write-Host "✅ Created new clips directory: $newClipsBase" -ForegroundColor Green
}

# Find all episode directories with clips
$episodeDirs = Get-ChildItem -Path $oldClipsBase -Directory -ErrorAction SilentlyContinue

$migratedCount = 0
$skippedCount = 0
$errorCount = 0

foreach ($episodeDir in $episodeDirs) {
    $episodeId = $episodeDir.Name
    $oldClipsPath = Join-Path $episodeDir.FullName "clips"
    $newClipsPath = Join-Path $newClipsBase $episodeId
    
    # Check if old clips directory exists for this episode
    if (-not (Test-Path $oldClipsPath)) {
        Write-Host "⏭️  Skipping $episodeId - no clips folder" -ForegroundColor Yellow
        $skippedCount++
        continue
    }
    
    # Check if clips already exist in new location
    if (Test-Path $newClipsPath) {
        Write-Host "⚠️  $episodeId - clips already exist in new location, skipping" -ForegroundColor Yellow
        $skippedCount++
        continue
    }
    
    try {
        # Move clips to new location
        Write-Host "📦 Migrating clips for episode: $episodeId" -ForegroundColor Cyan
        
        # Create parent directory if needed
        $newClipsParent = Split-Path -Parent $newClipsPath
        if (-not (Test-Path $newClipsParent)) {
            New-Item -ItemType Directory -Path $newClipsParent -Force | Out-Null
        }
        
        # Move the entire clips directory
        Move-Item -Path $oldClipsPath -Destination $newClipsPath -Force
        
        # Count files moved
        $fileCount = (Get-ChildItem -Path $newClipsPath -Recurse -File).Count
        Write-Host "   ✅ Moved $fileCount files" -ForegroundColor Green
        
        $migratedCount++
        
    } catch {
        Write-Host "   ❌ Error migrating $episodeId : $_" -ForegroundColor Red
        $errorCount++
    }
}

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Gray
Write-Host "📊 Migration Summary:" -ForegroundColor Cyan
Write-Host "   ✅ Migrated: $migratedCount episodes" -ForegroundColor Green
Write-Host "   ⏭️  Skipped: $skippedCount episodes" -ForegroundColor Yellow
Write-Host "   ❌ Errors: $errorCount episodes" -ForegroundColor Red
Write-Host ""

if ($migratedCount -gt 0) {
    Write-Host "🎉 Migration completed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📝 Note: Old data/outputs/{episode_id} directories still exist" -ForegroundColor Yellow
    Write-Host "   You can safely delete them after verifying clips work correctly" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "   To clean up old directories, run:" -ForegroundColor Gray
    Write-Host "   Get-ChildItem data\outputs -Directory | Remove-Item -Recurse -Force" -ForegroundColor Gray
} else {
    Write-Host "✅ No clips needed migration" -ForegroundColor Green
}

Write-Host ""
