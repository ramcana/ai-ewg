#!/usr/bin/env pwsh
# AI-Enhanced HTML Generator with Ollama
param(
    [Parameter(Mandatory=$true)]
    [string]$TranscriptPath,
    [string]$Model = "llama3.1:latest",  # Best model for analysis
    [switch]$SkipAI = $false
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AI-Enhanced HTML Page Generator" -ForegroundColor Cyan
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

# Prepare transcript for AI (limit to reasonable size)
$maxChars = 15000
$transcriptForAI = if ($transcriptText.Length -gt $maxChars) {
    $transcriptText.Substring(0, $maxChars) + "... [transcript continues]"
} else {
    $transcriptText
}

# AI Analysis with Ollama
$aiSummary = ""
$keyTakeaways = @()
$newsAnalysis = ""
$keyTopics = @()

if (-not $SkipAI) {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "AI Analysis with Ollama ($Model)" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    
    # 1. Generate Executive Summary
    Write-Host "[1/4] Generating executive summary..." -ForegroundColor Yellow
    $summaryPrompt = @"
You are a professional news analyst. Analyze this transcript and provide a concise, engaging 2-3 paragraph executive summary that captures the essence of the discussion.

Transcript:
$transcriptForAI

Provide only the summary, no preamble.
"@
    
    $summaryPrompt | ollama run $Model --nowordwrap | Tee-Object -Variable aiSummary | Out-Null
    Write-Host "  [OK] Summary generated ($($aiSummary.Length) chars)" -ForegroundColor Green
    
    # 2. Extract Key Takeaways
    Write-Host "[2/4] Extracting key takeaways..." -ForegroundColor Yellow
    $takeawaysPrompt = @"
Analyze this transcript and extract 5-7 key takeaways or insights. Format as a simple list, one per line, starting with a dash.

Transcript:
$transcriptForAI

Provide only the list, no preamble or conclusion.
"@
    
    $takeawaysText = $takeawaysPrompt | ollama run $Model --nowordwrap
    $keyTakeaways = $takeawaysText -split "`n" | Where-Object { $_.Trim() -match '^[-•*]' } | ForEach-Object { $_.Trim() -replace '^[-•*]\s*', '' }
    Write-Host "  [OK] Extracted $($keyTakeaways.Count) key takeaways" -ForegroundColor Green
    
    # 3. Deep News Analysis
    Write-Host "[3/4] Performing deep news analysis..." -ForegroundColor Yellow
    $analysisPrompt = @"
You are a news analyst. Analyze this transcript for:
1. Main themes and topics discussed
2. Significance and implications
3. Context and background
4. Potential impact or consequences

Provide a structured analysis in 2-3 paragraphs.

Transcript:
$transcriptForAI

Provide only the analysis, no preamble.
"@
    
    $analysisPrompt | ollama run $Model --nowordwrap | Tee-Object -Variable newsAnalysis | Out-Null
    Write-Host "  [OK] Analysis complete ($($newsAnalysis.Length) chars)" -ForegroundColor Green
    
    # 4. Extract Topics/Keywords
    Write-Host "[4/4] Identifying key topics..." -ForegroundColor Yellow
    $topicsPrompt = @"
Extract 8-10 key topics, themes, or keywords from this transcript. Provide only the topics as a comma-separated list.

Transcript:
$transcriptForAI

Provide only the comma-separated list, nothing else.
"@
    
    $topicsText = $topicsPrompt | ollama run $Model --nowordwrap
    $keyTopics = $topicsText -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" } | Select-Object -First 10
    Write-Host "  [OK] Identified $($keyTopics.Count) topics" -ForegroundColor Green
    Write-Host ""
}

# Create segments from transcript
Write-Host "Creating transcript segments..." -ForegroundColor Yellow
$lines = $transcriptText -split "`r?`n" | Where-Object { $_.Trim() -ne "" }
$qaBlocks = @()
$chunkSize = 10
$maxSegments = 20

for ($i = 0; $i -lt $lines.Count; $i += $chunkSize) {
    $endIdx = [Math]::Min($i + $chunkSize - 1, $lines.Count - 1)
    $chunk = ($lines[$i..$endIdx]) -join ' '
    $segmentNum = [Math]::Floor($i / $chunkSize) + 1
    $qaBlocks += @{
        number = $segmentNum
        title = ""  # Will be filled by AI
        text = $chunk
    }
    if ($qaBlocks.Count -ge $maxSegments) { break }
}
Write-Host "  Created $($qaBlocks.Count) segments" -ForegroundColor White

# Generate AI titles for segments
if (-not $SkipAI -and $qaBlocks.Count -gt 0) {
    Write-Host "[5/5] Generating segment titles with AI..." -ForegroundColor Yellow
    
    foreach ($block in $qaBlocks) {
        $segmentText = $block.text.Substring(0, [Math]::Min(500, $block.text.Length))
        $titlePrompt = @"
Generate a short, descriptive title (3-6 words) for this transcript segment. Provide ONLY the title, nothing else.

Segment text:
$segmentText

Title:
"@
        
        $title = ($titlePrompt | ollama run $Model --nowordwrap).Trim()
        # Clean up the title
        $title = $title -replace '^["'']|["'']$', ''  # Remove quotes
        $title = $title -replace '^\s*Title:\s*', ''  # Remove "Title:" prefix
        $title = $title.Trim()
        
        if ($title.Length -gt 0 -and $title.Length -lt 100) {
            $block.title = $title
        } else {
            $block.title = "Segment $($block.number)"
        }
    }
    Write-Host "  [OK] Generated titles for $($qaBlocks.Count) segments" -ForegroundColor Green
}
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

# Build JSON-LD with AI-enhanced keywords
$jsonTopics = if ($keyTopics.Count -gt 0) { $keyTopics } else { @($topic.ToLower() -split '\s+' | Where-Object { $_.Length -gt 3 } | Select-Object -First 6) }
$headline = "$topic - $show"

$jsonLd = @{
    "@context" = "https://schema.org"
    "@type" = "NewsArticle"
    "headline" = $headline
    "description" = if ($aiSummary -and $aiSummary.Length -gt 0) { 
        $descLen = [Math]::Min(200, $aiSummary.Length)
        if ($descLen -gt 0) { $aiSummary.Substring(0, $descLen) } else { "News analysis and discussion" }
    } else { "News analysis and discussion" }
    "datePublished" = $publishDate
    "author" = @{ "@type" = "Person"; "name" = $hostName; "url" = $hostUrl }
    "keywords" = $jsonTopics
    "mainEntityOfPage" = "https://www.thenewsforum.ca$urlSlug/"
} | ConvertTo-Json -Depth 10

Write-Host "Building AI-enhanced HTML page..." -ForegroundColor Yellow

# Generate HTML
$htmlParts = @()
$htmlParts += '<!doctype html>'
$htmlParts += '<html lang="en">'
$htmlParts += '<head>'
$htmlParts += '<meta charset="utf-8" />'
$htmlParts += "<title>$headline</title>"
$htmlParts += '<meta name="viewport" content="width=device-width, initial-scale=1" />'
$htmlParts += '<link rel="stylesheet" href="https://cdn.simplecss.org/simple.min.css">'
$htmlParts += '<style>'
$htmlParts += 'body { max-width: 900px; margin: 2rem auto; padding: 0 1rem; }'
$htmlParts += '.ai-badge { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 0.25rem 0.75rem; border-radius: 1rem; font-size: 0.75rem; font-weight: bold; display: inline-block; margin-left: 0.5rem; }'
$htmlParts += '.key-takeaway { background: #f0f8ff; border-left: 4px solid #0066cc; padding: 1rem; margin: 1.5rem 0; }'
$htmlParts += '.analysis-box { background: #fff9e6; border-left: 4px solid #ffa500; padding: 1rem; margin: 1.5rem 0; }'
$htmlParts += '.takeaways-list { background: #f0fff0; border-left: 4px solid #28a745; padding: 1rem; margin: 1.5rem 0; }'
$htmlParts += '.topics { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 1rem 0; }'
$htmlParts += '.topic-tag { background: #e9ecef; padding: 0.25rem 0.75rem; border-radius: 1rem; font-size: 0.875rem; }'
$htmlParts += 'section { margin: 2rem 0; padding: 1rem; border-bottom: 1px solid #eee; }'
$htmlParts += '.metadata { color: #666; font-size: 0.9rem; }'
$htmlParts += '</style>'
$htmlParts += '<script type="application/ld+json">'
$htmlParts += $jsonLd
$htmlParts += '</script>'
$htmlParts += '</head>'
$htmlParts += '<body>'
$htmlParts += '<article>'
$htmlParts += "<h1>$headline"
if (-not $SkipAI) {
    $htmlParts += '<span class="ai-badge">AI ENHANCED</span>'
}
$htmlParts += '</h1>'
$htmlParts += "<p class='metadata'><strong>Episode:</strong> $episodeId - <strong>Date:</strong> $publishDate</p>"

# AI-Generated Summary
if ($aiSummary) {
    $htmlParts += '<div class="key-takeaway">'
    $htmlParts += '<h2 style="margin-top:0;">Executive Summary</h2>'
    $htmlParts += "<p>$aiSummary</p>"
    $htmlParts += '</div>'
}

# Key Takeaways
if ($keyTakeaways.Count -gt 0) {
    $htmlParts += '<div class="takeaways-list">'
    $htmlParts += '<h2 style="margin-top:0;">Key Takeaways</h2>'
    $htmlParts += '<ul>'
    foreach ($takeaway in $keyTakeaways) {
        $htmlParts += "<li>$takeaway</li>"
    }
    $htmlParts += '</ul>'
    $htmlParts += '</div>'
}

# Topics
if ($keyTopics.Count -gt 0) {
    $htmlParts += '<h2>Topics Covered</h2>'
    $htmlParts += '<div class="topics">'
    foreach ($topic_item in $keyTopics) {
        $htmlParts += "<span class='topic-tag'>$topic_item</span>"
    }
    $htmlParts += '</div>'
}

# Deep Analysis
if ($newsAnalysis) {
    $htmlParts += '<div class="analysis-box">'
    $htmlParts += '<h2 style="margin-top:0;">Deep Analysis</h2>'
    $htmlParts += "<p>$newsAnalysis</p>"
    $htmlParts += '</div>'
}

# Full Transcript
$htmlParts += '<h2>Full Transcript</h2>'
foreach ($block in $qaBlocks) {
    $htmlParts += '<section>'
    $segmentTitle = if ($block.title) { $block.title } else { "Segment $($block.number)" }
    $htmlParts += "<h3>$segmentTitle</h3>"
    $htmlParts += "<p>$($block.text)</p>"
    $htmlParts += '</section>'
}

# Downloads
$htmlParts += '<h2>Downloads</h2>'
$htmlParts += "<p><a href=`"../../assets/transcripts/$baseName.txt`">Download Transcript (.txt)</a> - "
$htmlParts += "<a href=`"../../assets/transcripts/$baseName.vtt`">Download Subtitles (.vtt)</a></p>"

# Footer
$htmlParts += '<footer style="margin-top:2rem;padding-top:1rem;border-top:1px solid #ccc;color:#666;font-size:0.9rem;">'
$htmlParts += '<p>Transcribed with GPU-accelerated Whisper (large-v3)'
if (-not $SkipAI) {
    $htmlParts += " - AI analysis powered by Ollama ($Model)"
}
$htmlParts += '</p>'
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

Write-Host "  [OK] AI-enhanced HTML page created" -ForegroundColor Green
Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "HTML Page: $htmlFile" -ForegroundColor Yellow
Write-Host "URL: $urlSlug" -ForegroundColor Yellow
if (-not $SkipAI) {
    Write-Host ""
    Write-Host "AI Enhancements:" -ForegroundColor Cyan
    Write-Host "  - Executive Summary: $($aiSummary.Length) chars" -ForegroundColor White
    Write-Host "  - Key Takeaways: $($keyTakeaways.Count) items" -ForegroundColor White
    Write-Host "  - Deep Analysis: $($newsAnalysis.Length) chars" -ForegroundColor White
    Write-Host "  - Topics Identified: $($keyTopics.Count)" -ForegroundColor White
}
Write-Host ""

$response = Read-Host "Open HTML page in browser? (Y/n)"
if ($response -ne 'n' -and $response -ne 'N') {
    Start-Process $htmlFile
}
