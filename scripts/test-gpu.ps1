#!/usr/bin/env pwsh
# GPU-Optimized Video Processing Test
# Uses faster-whisper with CUDA acceleration

param(
    [Parameter(Mandatory=$true)]
    [string]$VideoPath,
    [string]$Model = "large-v3",  # Use best model by default
    [string]$Device = "cuda",     # Use GPU
    [string]$ComputeType = "float16"  # Faster with minimal quality loss
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "GPU-Accelerated Video Processing" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Activate venv
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    & .\venv\Scripts\Activate.ps1
}

# Verify video file
if (-not (Test-Path $VideoPath)) {
    Write-Host "[✗] Video file not found: $VideoPath" -ForegroundColor Red
    exit 1
}

$videoFile = Get-Item $VideoPath
Write-Host "Video File:" -ForegroundColor Yellow
Write-Host "  Path: $($videoFile.FullName)" -ForegroundColor White
Write-Host "  Size: $([math]::Round($videoFile.Length / 1MB, 2)) MB" -ForegroundColor White
Write-Host ""

# Parse filename
$fileName = $videoFile.Name
$baseName = $fileName -replace '\.mp4$', ''
$parts = $baseName -split '_'

if ($parts.Length -lt 4) {
    Write-Host "[!] Warning: Filename doesn't match expected pattern" -ForegroundColor Yellow
    Write-Host "    Expected: {Show}_{EpisodeId}_{YYYY-MM-DD}_{Topic}.mp4" -ForegroundColor Gray
    Write-Host "    Got: $fileName" -ForegroundColor Gray
    Write-Host ""
    
    # Use defaults
    $show = if ($parts[0]) { $parts[0] } else { "UnknownShow" }
    $episodeId = if ($parts[1]) { $parts[1] } else { "E001" }
    $publishDate = if ($parts[2]) { $parts[2] } else { (Get-Date -Format "yyyy-MM-dd") }
    $topic = if ($parts.Length -gt 3) { ($parts[3..($parts.Length-1)] -join ' ') -replace '-', ' ' } else { "Episode" }
} else {
    $show = $parts[0]
    $episodeId = $parts[1]
    $publishDate = $parts[2]
    $topic = ($parts[3..($parts.Length-1)] -join ' ') -replace '-', ' '
}

Write-Host "Parsed Metadata:" -ForegroundColor Yellow
Write-Host "  Show: $show" -ForegroundColor White
Write-Host "  Episode: $episodeId" -ForegroundColor White
Write-Host "  Date: $publishDate" -ForegroundColor White
Write-Host "  Topic: $topic" -ForegroundColor White
Write-Host ""

# Setup paths
$baseDir = "D:\newsroom"
$transcriptDir = "$baseDir\outputs\assets\transcripts"
$pagesDir = "$baseDir\outputs\pages"
$transcriptBase = "$transcriptDir\$baseName"

# Create transcript directory if needed
if (-not (Test-Path $transcriptDir)) {
    New-Item -ItemType Directory -Path $transcriptDir -Force | Out-Null
}

# Transcribe with faster-whisper
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Transcription (GPU-Accelerated)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Model: $Model" -ForegroundColor Yellow
Write-Host "Device: $Device" -ForegroundColor Yellow
Write-Host "Compute Type: $ComputeType" -ForegroundColor Yellow
Write-Host ""
Write-Host "Starting transcription..." -ForegroundColor Yellow
Write-Host "(This will take 3-5 minutes for a 30-min video with large-v3)" -ForegroundColor Gray
Write-Host ""

$startTime = Get-Date

# Create Python script for transcription
$pythonScript = @"
import sys
from faster_whisper import WhisperModel
import time

# Initialize model
print("Loading model: $Model on $Device...")
start = time.time()
model = WhisperModel('$Model', device='$Device', compute_type='$ComputeType')
load_time = time.time() - start
print(f"Model loaded in {load_time:.2f} seconds")
print()

# Transcribe
print("Transcribing video...")
print(f"Video: $($videoFile.FullName)")
print()
start = time.time()

segments, info = model.transcribe(
    r'$($videoFile.FullName)',
    language='en',
    vad_filter=True,  # Skip silence for faster processing
    vad_parameters=dict(min_silence_duration_ms=500)
)

# Collect segments
all_segments = []
transcript_lines = []
vtt_lines = ['WEBVTT', '']

print("Processing segments...")
for i, segment in enumerate(segments):
    all_segments.append(segment)
    transcript_lines.append(segment.text.strip())
    
    # VTT format
    start_time = f"{int(segment.start // 3600):02d}:{int((segment.start % 3600) // 60):02d}:{segment.start % 60:06.3f}".replace('.', ',')
    end_time = f"{int(segment.end // 3600):02d}:{int((segment.end % 3600) // 60):02d}:{segment.end % 60:06.3f}".replace('.', ',')
    vtt_lines.append(f"{start_time} --> {end_time}")
    vtt_lines.append(segment.text.strip())
    vtt_lines.append('')
    
    if (i + 1) % 10 == 0:
        print(f"  Processed {i + 1} segments...")

transcribe_time = time.time() - start

# Write files
print()
print("Writing transcript files...")

# Write .txt
with open(r'$transcriptBase.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(transcript_lines))
print(f"  [✓] {len(transcript_lines)} lines written to .txt")

# Write .vtt
with open(r'$transcriptBase.vtt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(vtt_lines))
print(f"  [✓] VTT file with {len(all_segments)} segments")

# Summary
print()
print("Transcription Summary:")
print(f"  Duration: {info.duration:.2f} seconds")
print(f"  Language: {info.language} ({info.language_probability:.2%} confidence)")
print(f"  Processing time: {transcribe_time:.2f} seconds")
print(f"  Speed ratio: {info.duration / transcribe_time:.2f}x realtime")
print(f"  Total segments: {len(all_segments)}")
"@

# Run Python script
$pythonScript | python -

$endTime = Get-Date
$duration = ($endTime - $startTime).TotalSeconds

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Transcription Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Total time: $([math]::Round($duration, 2)) seconds" -ForegroundColor White
Write-Host ""

# Read transcript
if (Test-Path "$transcriptBase.txt") {
    $transcriptText = Get-Content "$transcriptBase.txt" -Raw
    Write-Host "[✓] Transcript generated: $([math]::Round($transcriptText.Length / 1KB, 2)) KB" -ForegroundColor Green
} else {
    Write-Host "[✗] Transcript file not created" -ForegroundColor Red
    exit 1
}

# Generate HTML (same as standalone test)
Write-Host ""
Write-Host "Generating HTML page..." -ForegroundColor Yellow

$lines = $transcriptText -split "`r?`n" | Where-Object { $_.Trim() -ne "" }
$firstParagraphs = ($lines | Select-Object -First 12) -join ' '
$keyTakeaway = $firstParagraphs.Substring(0, [Math]::Min(260, $firstParagraphs.Length))
if ($firstParagraphs.Length -gt 260) { $keyTakeaway += "..." }

$allText = $lines -join ' '
$summary = $allText.Substring(0, [Math]::Min(600, $allText.Length))
if ($allText.Length -gt 600) { $summary += "..." }

# Create Q&A blocks
$qaBlocks = @()
$chunkSize = 8
for ($i = 0; $i -lt $lines.Count; $i += $chunkSize) {
    $chunk = ($lines[$i..[Math]::Min($i + $chunkSize - 1, $lines.Count - 1)]) -join ' '
    $qaBlocks += @{
        question = "Segment $([Math]::Floor($i / $chunkSize) + 1)"
        answers = @(@{ speaker = "Transcript"; text = $chunk })
    }
    if ($qaBlocks.Count -ge 10) { break }
}

# Load catalog (using defaults for now - can be enhanced later to read from shows.yaml)
$hostName = "The News Forum Host"
$hostUrl = "https://www.thenewsforum.ca/hosts/default"

# Generate URL slug
$showSlug = $show.ToLower() -replace '[^a-z0-9]+', '-'
$topicSlug = $topic.ToLower() -replace '[^a-z0-9]+', '-'
$urlSlug = "/$showSlug/$episodeId-$topicSlug"

# Build JSON-LD
$topics = @($topic.ToLower() -split '\s+' | Where-Object { $_.Length -gt 3 } | Select-Object -Unique -First 6)

$headline = "Interview: $topic - $show"
$jsonLd = @{
    "@context" = "https://schema.org"
    "@type" = "NewsArticle"
    "headline" = $headline
    "datePublished" = $publishDate
    "author" = @{ "@type" = "Person"; "name" = $hostName; "url" = $hostUrl }
    "keywords" = $topics
    "mainEntityOfPage" = "https://www.thenewsforum.ca$urlSlug/"
} | ConvertTo-Json -Depth 10

# Generate HTML (simplified)
$qaHtml = ""
$index = 1
foreach ($block in $qaBlocks) {
    $qaHtml += "`n" + '<section id="q' + $index + '">' + "`n  <h3>" + $block.question + "</h3>`n"
    foreach ($answer in $block.answers) {
        $qaHtml += "  <p><strong>" + $answer.speaker + ":</strong> " + $answer.text + "</p>`n"
    }
    $qaHtml += "</section>`n"
    $index++
}

$pageTitle = "$topic - $show"
$html = '<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>' + $pageTitle + '</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="stylesheet" href="https://cdn.simplecss.org/simple.min.css">
<script type="application/ld+json">
' + $jsonLd + '
</script>
</head>
<body>
  <article>
    <h1>' + $pageTitle + '</h1>
    <p><strong>Episode:</strong> ' + $episodeId + ' - <strong>Date:</strong> ' + $publishDate + '</p>
    <div style="background:#f0f8ff;border-left:4px solid #0066cc;padding:1rem;margin:1.5rem 0;">
      <strong>Key Takeaway:</strong> ' + $keyTakeaway + '
    </div>
    <h2>Summary</h2>
    <p>' + $summary + '</p>
    <h2>Full Transcript</h2>
    ' + $qaHtml + '
    <h2>Downloads</h2>
    <p><a href="../../assets/transcripts/' + $baseName + '.txt">Transcript (.txt)</a> - <a href="../../assets/transcripts/' + $baseName + '.vtt">Subtitles (.vtt)</a></p>
  </article>
</body>
</html>'

# Write HTML
$outputDir = "$pagesDir\$showSlug\$episodeId-$topicSlug"
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

$htmlFile = "$outputDir\index.html"
$html | Out-File -FilePath $htmlFile -Encoding UTF8

Write-Host "[✓] HTML page created" -ForegroundColor Green
Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Processing Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Generated Files:" -ForegroundColor Yellow
Write-Host "  Transcript: $transcriptBase.txt" -ForegroundColor White
Write-Host "  Subtitles:  $transcriptBase.vtt" -ForegroundColor White
Write-Host "  HTML Page:  $htmlFile" -ForegroundColor White
Write-Host ""
Write-Host "URL: $urlSlug" -ForegroundColor White
Write-Host ""

$response = Read-Host "Open HTML page in browser? (Y/n)"
if ($response -ne 'n' -and $response -ne 'N') {
    Start-Process $htmlFile
}
