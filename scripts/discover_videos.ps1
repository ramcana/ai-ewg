$folder = "D:\n8n\TNF-Transcripts\test_videos\newsroom\2024"
$show = "newsroom"

Write-Host "Activating virtual environment..."
& ".\venv\Scripts\Activate.ps1"

Write-Host "Discovering videos in: $folder"
Write-Host "Show name: $show"
Write-Host ""

python discover_videos.py $folder --show $show
