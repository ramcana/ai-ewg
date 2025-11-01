# Setup Organized Input Video Structure
# Creates folder structure matching output organization

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AI-EWG Input Structure Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Define base paths
$baseInputPath = "input_videos"
$theNewsForumPath = Join-Path $baseInputPath "TheNewsForum"

# Define show folders
$shows = @(
    "ForumDailyNews",
    "BoomAndBust",
    "CommunityProfile",
    "EconomicPulse",
    "FreedomForum"
)

# Create base structure
Write-Host "Creating folder structure..." -ForegroundColor Yellow
Write-Host ""

# Create main input folder
if (-not (Test-Path $baseInputPath)) {
    New-Item -ItemType Directory -Path $baseInputPath -Force | Out-Null
    Write-Host "✓ Created: $baseInputPath" -ForegroundColor Green
} else {
    Write-Host "✓ Exists: $baseInputPath" -ForegroundColor Gray
}

# Create TheNewsForum folder
if (-not (Test-Path $theNewsForumPath)) {
    New-Item -ItemType Directory -Path $theNewsForumPath -Force | Out-Null
    Write-Host "✓ Created: $theNewsForumPath" -ForegroundColor Green
} else {
    Write-Host "✓ Exists: $theNewsForumPath" -ForegroundColor Gray
}

# Create show folders
foreach ($show in $shows) {
    $showPath = Join-Path $theNewsForumPath $show
    if (-not (Test-Path $showPath)) {
        New-Item -ItemType Directory -Path $showPath -Force | Out-Null
        Write-Host "✓ Created: $showPath" -ForegroundColor Green
    } else {
        Write-Host "✓ Exists: $showPath" -ForegroundColor Gray
    }
}

# Create uncategorized folder
$uncategorizedPath = Join-Path $baseInputPath "_uncategorized"
if (-not (Test-Path $uncategorizedPath)) {
    New-Item -ItemType Directory -Path $uncategorizedPath -Force | Out-Null
    Write-Host "✓ Created: $uncategorizedPath" -ForegroundColor Green
} else {
    Write-Host "✓ Exists: $uncategorizedPath" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Folder Structure Created!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check for existing videos in legacy folder (info only, no moving)
$legacyPath = "test_videos\newsroom\2024"
if (Test-Path $legacyPath) {
    $videoFiles = Get-ChildItem -Path $legacyPath -Include "*.mp4","*.mkv","*.avi","*.mov" -Recurse
    
    if ($videoFiles.Count -gt 0) {
        Write-Host "ℹ️  Note: Found $($videoFiles.Count) video(s) in legacy folder: $legacyPath" -ForegroundColor Yellow
        Write-Host "   These files will remain in place (legacy folder is disabled in config)" -ForegroundColor Gray
        Write-Host "   You can manually organize them into the new structure if needed" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Input Structure:" -ForegroundColor Cyan
Write-Host "  input_videos/" -ForegroundColor White
Write-Host "  ├── TheNewsForum/" -ForegroundColor White
Write-Host "  │   ├── ForumDailyNews/" -ForegroundColor White
Write-Host "  │   ├── BoomAndBust/" -ForegroundColor White
Write-Host "  │   ├── CommunityProfile/" -ForegroundColor White
Write-Host "  │   ├── EconomicPulse/" -ForegroundColor White
Write-Host "  │   └── FreedomForum/" -ForegroundColor White
Write-Host "  └── _uncategorized/" -ForegroundColor White
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "1. Place videos in appropriate show folders" -ForegroundColor White
Write-Host "2. Restart API server to pick up new configuration" -ForegroundColor White
Write-Host "3. Run discovery in Streamlit dashboard" -ForegroundColor White
Write-Host ""
Write-Host "Commands:" -ForegroundColor Cyan
Write-Host "  Restart API: .\start-api-server.ps1" -ForegroundColor Yellow
Write-Host "  Start Dashboard: streamlit run dashboard.py" -ForegroundColor Yellow
Write-Host ""
