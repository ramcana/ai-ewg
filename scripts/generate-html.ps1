#!/usr/bin/env pwsh
# Generate HTML from existing transcript
param(
    [Parameter(Mandatory=$true)]
    [string]$TranscriptPath
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "HTML Page Generator" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verify transcript exists
if (-not (Test-Path $TranscriptPath)) {
    Write-Host "[ERROR] Transcript not found: $TranscriptPath" -ForegroundColor Red
    exit 1
}

$transcriptFile = Get-Item $TranscriptPath
$baseName = $transcriptFile.BaseName
$fileName = $transcriptFile.Name

Write-Host "Transcript: $fileName" -ForegroundColor Yellow
Write-Host "Size: $([math]::Round($transcriptFile.Length / 1KB, 2)) KB" -ForegroundColor Yellow
Write-Host ""

# Parse filename
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

# Read transcript
$transcriptText = Get-Content $TranscriptPath -Raw -Encoding UTF8
Write-Host "Loaded transcript: $($transcriptText.Length) characters" -ForegroundColor Green
Write-Host ""

# Generate summary and key takeaway
Write-Host "Generating summary..." -ForegroundColor Yellow
$lines = $transcriptText -split "`r?`n" | Where-Object { $_.Trim() -ne "" }
$firstParagraphs = ($lines | Select-Object -First 15) -join ' '
$keyTakeaway = $firstParagraphs.Substring(0, [Math]::Min(300, $firstParagraphs.Length))
if ($firstParagraphs.Length -gt 300) { $keyTakeaway += "..." }

$allText = $lines -join ' '
$summary = $allText.Substring(0, [Math]::Min(800, $allText.Length))
if ($allText.Length -gt 800) { $summary += "..." }

# Create Q&A blocks
$qaBlocks = @()
$chunkSize = 10
for ($i = 0; $i -lt $lines.Count; $i += $chunkSize) {
    $endIdx = [Math]::Min($i + $chunkSize - 1, $lines.Count - 1)
    $chunk = ($lines[$i..$endIdx]) -join ' '
    $segmentNum = [Math]::Floor($i / $chunkSize) + 1
    $qaBlocks += @{
        question = "Segment $segmentNum"
        text = $chunk
    }
    if ($qaBlocks.Count -ge 15) { break }
}

Write-Host "  Key Takeaway: $($keyTakeaway.Length) chars" -ForegroundColor White
Write-Host "  Summary: $($summary.Length) chars" -ForegroundColor White
Write-Host "  Created $($qaBlocks.Count) segments" -ForegroundColor White
Write-Host ""

# Setup paths
$baseDir = "D:\newsroom"
$pagesDir = "$baseDir\outputs\pages"
$hostName = "The News Forum Host"
$hostUrl = "https://www.thenewsforum.ca/hosts/default"

# Generate URL slug
$showSlug = $show.ToLower() -replace '[^a-z0-9]+', '-'
$topicSlug = $topic.ToLower() -replace '[^a-z0-9]+', '-'
$urlSlug = "/$showSlug/$episodeId-$topicSlug"

# Build JSON-LD
$topics = @($topic.ToLower() -split '\s+' | Where-Object { $_.Length -gt 3 } | Select-Object -Unique -First 6)
$headline = "$topic - $show"

$jsonLd = @{
    "@context" = "https://schema.org"
    "@type" = "NewsArticle"
    "headline" = $headline
    "datePublished" = $publishDate
    "author" = @{ "@type" = "Person"; "name" = $hostName; "url" = $hostUrl }
    "keywords" = $topics
    "mainEntityOfPage" = "https://www.thenewsforum.ca$urlSlug/"
} | ConvertTo-Json -Depth 10

Write-Host "Building HTML page..." -ForegroundColor Yellow

# Generate HTML using string builder
$htmlParts = @()
$htmlParts += '<!doctype html>'
$htmlParts += '<html lang="en">'
$htmlParts += '<head>'
$htmlParts += '<meta charset="utf-8" />'
$htmlParts += "<title>$headline</title>"
$htmlParts += '<meta name="viewport" content="width=device-width, initial-scale=1" />'
$htmlParts += '<link rel="stylesheet" href="https://cdn.simplecss.org/simple.min.css">'
$htmlParts += '<script type="application/ld+json">'
$htmlParts += $jsonLd
$htmlParts += '</script>'
$htmlParts += '</head>'
$htmlParts += '<body>'
$htmlParts += '<article>'
$htmlParts += "<h1>$headline</h1>"
$htmlParts += "<p><strong>Episode:</strong> $episodeId - <strong>Date:</strong> $publishDate</p>"
$htmlParts += '<div style="background:#f0f8ff;border-left:4px solid #0066cc;padding:1rem;margin:1.5rem 0;">'
$htmlParts += "<strong>Key Takeaway:</strong> $keyTakeaway"
$htmlParts += '</div>'
$htmlParts += '<h2>Summary</h2>'
$htmlParts += "<p>$summary</p>"
$htmlParts += '<h2>Full Transcript</h2>'

foreach ($block in $qaBlocks) {
    $htmlParts += '<section>'
    $htmlParts += "<h3>$($block.question)</h3>"
    $htmlParts += "<p>$($block.text)</p>"
    $htmlParts += '</section>'
}

$htmlParts += '<h2>Downloads</h2>'
$htmlParts += "<p><a href=`"../../assets/transcripts/$baseName.txt`">Download Transcript (.txt)</a> - "
$htmlParts += "<a href=`"../../assets/transcripts/$baseName.vtt`">Download Subtitles (.vtt)</a></p>"
$htmlParts += '<footer style="margin-top:2rem;padding-top:1rem;border-top:1px solid #ccc;color:#666;font-size:0.9rem;">'
$htmlParts += '<p>Generated by GPU-accelerated transcription system</p>'
$htmlParts += '</footer>'
$htmlParts += '</article>'
$htmlParts += '</body>'
$htmlParts += '</html>'

$html = $htmlParts -join "`n"

# Write HTML
$outputDir = "$pagesDir\$showSlug\$episodeId-$topicSlug"
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

$htmlFile = "$outputDir\index.html"
$html | Out-File -FilePath $htmlFile -Encoding UTF8

Write-Host "  [OK] HTML page created" -ForegroundColor Green
Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "HTML Page: $htmlFile" -ForegroundColor Yellow
Write-Host "URL: $urlSlug" -ForegroundColor Yellow
Write-Host ""

$response = Read-Host "Open HTML page in browser? (Y/n)"
if ($response -ne 'n' -and $response -ne 'N') {
    Start-Process $htmlFile
}
