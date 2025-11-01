# Data Folder Cleanup Script
# Organizes the data folder by moving old backups and cleaning up structure

Write-Host "🧹 Data Folder Cleanup Script" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Get the project root directory (parent of scripts folder)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$dataDir = Join-Path $projectRoot "data"

Write-Host "📍 Project root: $projectRoot" -ForegroundColor Gray
Write-Host "📍 Data directory: $dataDir" -ForegroundColor Gray
Write-Host ""

# Check if data directory exists
if (-not (Test-Path $dataDir)) {
    Write-Host "❌ Data directory not found at: $dataDir" -ForegroundColor Red
    exit 1
}

Write-Host "📂 Current data folder structure:" -ForegroundColor Yellow
Get-ChildItem $dataDir | ForEach-Object {
    if ($_.PSIsContainer) {
        $itemCount = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
        Write-Host "   📁 $($_.Name)/ ($itemCount items)" -ForegroundColor Gray
    } else {
        $sizeMB = [math]::Round($_.Length / 1MB, 2)
        Write-Host "   📄 $($_.Name) ($sizeMB MB)" -ForegroundColor Gray
    }
}
Write-Host ""

# Step 1: Create backups directory
Write-Host "📦 Step 1: Creating backups directory..." -ForegroundColor Cyan
$backupsDir = Join-Path $dataDir "backups"
if (-not (Test-Path $backupsDir)) {
    New-Item -ItemType Directory -Path $backupsDir -Force | Out-Null
    Write-Host "   ✅ Created: $backupsDir" -ForegroundColor Green
} else {
    Write-Host "   ℹ️  Already exists: $backupsDir" -ForegroundColor Gray
}

# Step 2: Move old database backups
Write-Host ""
Write-Host "🗄️  Step 2: Moving old database backups..." -ForegroundColor Cyan
$backupFiles = Get-ChildItem $dataDir -Filter "pipeline.db.FINAL_BACKUP-*"
if ($backupFiles.Count -gt 0) {
    foreach ($file in $backupFiles) {
        $destination = Join-Path $backupsDir $file.Name
        Move-Item -Path $file.FullName -Destination $destination -Force
        Write-Host "   ✅ Moved: $($file.Name)" -ForegroundColor Green
    }
    Write-Host "   📊 Total backups moved: $($backupFiles.Count)" -ForegroundColor Yellow
} else {
    Write-Host "   ℹ️  No backup files found" -ForegroundColor Gray
}

# Step 3: Check for old outputs directory
Write-Host ""
Write-Host "📁 Step 3: Checking for old outputs structure..." -ForegroundColor Cyan
$oldOutputsDir = Join-Path $dataDir "outputs"
if (Test-Path $oldOutputsDir) {
    $outputItems = Get-ChildItem $oldOutputsDir -Recurse -File -ErrorAction SilentlyContinue
    if ($outputItems.Count -gt 0) {
        Write-Host "   ⚠️  Found $($outputItems.Count) files in old outputs directory" -ForegroundColor Yellow
        Write-Host "   📋 Checking for clips to migrate..." -ForegroundColor Cyan
        
        # Look for episode folders with clips
        $episodeFolders = Get-ChildItem $oldOutputsDir -Directory
        foreach ($episodeFolder in $episodeFolders) {
            $clipsPath = Join-Path $episodeFolder.FullName "clips"
            if (Test-Path $clipsPath) {
                $clipFolders = Get-ChildItem $clipsPath -Directory -ErrorAction SilentlyContinue
                if ($clipFolders.Count -gt 0) {
                    Write-Host "   📦 Found clips for episode: $($episodeFolder.Name)" -ForegroundColor Yellow
                    
                    # Create new clips directory structure
                    $newClipsDir = Join-Path $dataDir "clips" $episodeFolder.Name
                    if (-not (Test-Path $newClipsDir)) {
                        New-Item -ItemType Directory -Path $newClipsDir -Force | Out-Null
                    }
                    
                    # Move clip folders
                    foreach ($clipFolder in $clipFolders) {
                        $destination = Join-Path $newClipsDir $clipFolder.Name
                        if (-not (Test-Path $destination)) {
                            Move-Item -Path $clipFolder.FullName -Destination $destination -Force
                            Write-Host "      ✅ Migrated clip: $($clipFolder.Name)" -ForegroundColor Green
                        } else {
                            Write-Host "      ⚠️  Clip already exists: $($clipFolder.Name)" -ForegroundColor Yellow
                        }
                    }
                }
            }
        }
        
        # After migration, check if outputs is empty
        $remainingItems = Get-ChildItem $oldOutputsDir -Recurse -File -ErrorAction SilentlyContinue
        if ($remainingItems.Count -eq 0) {
            Write-Host "   🗑️  Removing empty outputs directory..." -ForegroundColor Cyan
            Remove-Item $oldOutputsDir -Recurse -Force
            Write-Host "   ✅ Removed empty outputs directory" -ForegroundColor Green
        } else {
            Write-Host "   ⚠️  Outputs directory still contains $($remainingItems.Count) files" -ForegroundColor Yellow
            Write-Host "   ℹ️  Manual review recommended" -ForegroundColor Gray
        }
    } else {
        Write-Host "   🗑️  Removing empty outputs directory..." -ForegroundColor Cyan
        Remove-Item $oldOutputsDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "   ✅ Removed empty outputs directory" -ForegroundColor Green
    }
} else {
    Write-Host "   ✅ No old outputs directory found" -ForegroundColor Green
}

# Step 4: Create .gitignore for data folder
Write-Host ""
Write-Host "📝 Step 4: Creating .gitignore for data folder..." -ForegroundColor Cyan
$gitignorePath = Join-Path $dataDir ".gitignore"
$gitignoreContent = @"
# Ignore all data files except structure
*
!.gitignore
!backups/.gitkeep
!clips/.gitkeep
!transcripts/.gitkeep
!enriched/.gitkeep
!social_packages/.gitkeep
!temp/.gitkeep

# Keep directory structure
!*/
"@

Set-Content -Path $gitignorePath -Value $gitignoreContent -Force
Write-Host "   ✅ Created: .gitignore" -ForegroundColor Green

# Step 5: Create .gitkeep files for empty directories
Write-Host ""
Write-Host "📌 Step 5: Creating .gitkeep files..." -ForegroundColor Cyan
$keepDirs = @("backups", "clips", "transcripts", "enriched", "social_packages", "temp")
foreach ($dir in $keepDirs) {
    $dirPath = Join-Path $dataDir $dir
    if (Test-Path $dirPath) {
        $gitkeepPath = Join-Path $dirPath ".gitkeep"
        if (-not (Test-Path $gitkeepPath)) {
            New-Item -ItemType File -Path $gitkeepPath -Force | Out-Null
            Write-Host "   ✅ Created: $dir/.gitkeep" -ForegroundColor Green
        }
    }
}

# Step 6: Summary
Write-Host ""
Write-Host "📊 Cleanup Summary" -ForegroundColor Cyan
Write-Host "==================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📂 Final data folder structure:" -ForegroundColor Yellow
Get-ChildItem $dataDir | ForEach-Object {
    if ($_.PSIsContainer) {
        $itemCount = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
        Write-Host "   📁 $($_.Name)/ ($itemCount items)" -ForegroundColor Gray
    } else {
        if ($_.Name -like "*.db*") {
            $sizeMB = [math]::Round($_.Length / 1MB, 2)
            Write-Host "   🗄️  $($_.Name) ($sizeMB MB)" -ForegroundColor Cyan
        } elseif ($_.Name -like "*.json") {
            Write-Host "   📄 $($_.Name)" -ForegroundColor Yellow
        } else {
            Write-Host "   📄 $($_.Name)" -ForegroundColor Gray
        }
    }
}

Write-Host ""
Write-Host "✅ Data folder cleanup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Recommended next steps:" -ForegroundColor Yellow
Write-Host "   1. Review migrated clips in data/clips/" -ForegroundColor Gray
Write-Host "   2. Restart Streamlit dashboard to see updated paths" -ForegroundColor Gray
Write-Host "   3. Test clip rendering to verify new structure" -ForegroundColor Gray
Write-Host ""
