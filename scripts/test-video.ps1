#!/usr/bin/env pwsh
# Simple GPU Video Transcription Test
param(
    [Parameter(Mandatory=$true)]
    [string]$VideoPath,
    [string]$Model = "large-v3",
    [string]$Device = "cpu"  # Use CPU by default (cuDNN issues on some systems)
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "GPU Video Transcription Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Activate venv if needed
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    & .\venv\Scripts\Activate.ps1
}

# Add cuDNN DLLs to PATH for GPU support
$cudnnPath = "d:\n8n\tnf-transcripts\venv\lib\site-packages\nvidia\cudnn\bin"
if (Test-Path $cudnnPath) {
    $env:PATH = "$cudnnPath;$env:PATH"
    Write-Host "[INFO] Added cuDNN to PATH for GPU support" -ForegroundColor Gray
}

# Verify video exists
if (-not (Test-Path $VideoPath)) {
    Write-Host "[ERROR] Video not found: $VideoPath" -ForegroundColor Red
    exit 1
}

$videoFile = Get-Item $VideoPath
Write-Host "Video: $($videoFile.Name)" -ForegroundColor Yellow
Write-Host "Size: $([math]::Round($videoFile.Length / 1MB, 2)) MB" -ForegroundColor Yellow
Write-Host ""

# Parse filename
$fileName = $videoFile.Name
$baseName = $fileName -replace '\.mp4$', ''
$parts = $baseName -split '_'

$show = if ($parts[0]) { $parts[0] } else { "Show" }
$episodeId = if ($parts[1]) { $parts[1] } else { "E001" }
$publishDate = if ($parts[2]) { $parts[2] } else { (Get-Date -Format "yyyy-MM-dd") }
$topic = if ($parts.Length -gt 3) { ($parts[3..($parts.Length-1)] -join ' ') -replace '-', ' ' } else { "Episode" }

Write-Host "Show: $show" -ForegroundColor White
Write-Host "Episode: $episodeId" -ForegroundColor White
Write-Host "Date: $publishDate" -ForegroundColor White
Write-Host "Topic: $topic" -ForegroundColor White
Write-Host ""

# Setup paths
$baseDir = "D:\newsroom"
$transcriptDir = "$baseDir\outputs\assets\transcripts"
$transcriptBase = "$transcriptDir\$baseName"

if (-not (Test-Path $transcriptDir)) {
    New-Item -ItemType Directory -Path $transcriptDir -Force | Out-Null
}

# Transcribe with faster-whisper
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting GPU Transcription" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Model: $Model" -ForegroundColor Yellow
Write-Host "Device: $Device" -ForegroundColor Yellow
if ($Device -eq "cpu") {
    Write-Host "This will take 20-30 minutes for a 1-hour video (CPU mode)..." -ForegroundColor Gray
} else {
    Write-Host "This will take 6-8 minutes for a 1-hour video (GPU mode)..." -ForegroundColor Gray
}
Write-Host ""

$startTime = Get-Date

# Create Python transcription script
$pythonCode = @'
import sys
from faster_whisper import WhisperModel
import time

video_path = sys.argv[1]
model_name = sys.argv[2]
output_base = sys.argv[3]
device = sys.argv[4] if len(sys.argv) > 4 else "cpu"

print(f"Loading model on {device}...")
start = time.time()
compute_type = "float16" if device == "cuda" else "int8"
model = WhisperModel(model_name, device=device, compute_type=compute_type)
print(f"Model loaded in {time.time() - start:.2f}s\n")

print("Transcribing...")
start = time.time()

segments, info = model.transcribe(
    video_path,
    language="en",
    vad_filter=True,
    vad_parameters=dict(min_silence_duration_ms=500)
)

# Collect segments
all_segments = list(segments)
transcript_lines = [seg.text.strip() for seg in all_segments]

# Write .txt
with open(output_base + '.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(transcript_lines))

# Write .vtt
vtt_lines = ['WEBVTT', '']
for seg in all_segments:
    start_time = f"{int(seg.start // 3600):02d}:{int((seg.start % 3600) // 60):02d}:{seg.start % 60:06.3f}".replace('.', ',')
    end_time = f"{int(seg.end // 3600):02d}:{int((seg.end % 3600) // 60):02d}:{seg.end % 60:06.3f}".replace('.', ',')
    vtt_lines.append(f"{start_time} --> {end_time}")
    vtt_lines.append(seg.text.strip())
    vtt_lines.append('')

with open(output_base + '.vtt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(vtt_lines))

elapsed = time.time() - start
print(f"\nTranscription complete!")
print(f"Duration: {info.duration:.2f}s")
print(f"Processing time: {elapsed:.2f}s")
print(f"Speed: {info.duration / elapsed:.2f}x realtime")
print(f"Segments: {len(all_segments)}")
'@

# Save and run Python script
$pythonCode | Out-File -FilePath "transcribe_temp.py" -Encoding UTF8
python transcribe_temp.py "$($videoFile.FullName)" "$Model" "$transcriptBase" "$Device"
Remove-Item "transcribe_temp.py"

$endTime = Get-Date
$duration = ($endTime - $startTime).TotalSeconds

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Total time: $([math]::Round($duration, 2)) seconds" -ForegroundColor White
Write-Host ""

# Verify files
if (Test-Path "$transcriptBase.txt") {
    $txtSize = (Get-Item "$transcriptBase.txt").Length
    Write-Host "[OK] Transcript: $transcriptBase.txt ($([math]::Round($txtSize / 1KB, 2)) KB)" -ForegroundColor Green
}

if (Test-Path "$transcriptBase.vtt") {
    $vttSize = (Get-Item "$transcriptBase.vtt").Length
    Write-Host "[OK] Subtitles: $transcriptBase.vtt ($([math]::Round($vttSize / 1KB, 2)) KB)" -ForegroundColor Green
}

Write-Host ""
Write-Host "Files saved to: $transcriptDir" -ForegroundColor Yellow
Write-Host ""
Write-Host "Next: Run the standalone test script to generate HTML page" -ForegroundColor Gray
Write-Host "  .\test-standalone.ps1 -TestVideo `"$fileName`"" -ForegroundColor Gray
Write-Host ""
