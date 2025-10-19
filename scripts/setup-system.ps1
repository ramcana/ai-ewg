#!/usr/bin/env pwsh
# n8n Video Processing System - Setup Script
# This script creates the required directory structure and initial catalog files

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "n8n Video Processing System Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$baseDir = "D:\newsroom"

# Define directory structure
$directories = @(
    "$baseDir\inbox\videos",
    "$baseDir\outputs\pages",
    "$baseDir\outputs\assets\transcripts",
    "$baseDir\catalog",
    "$baseDir\processed",
    "$baseDir\logs"
)

# Create directories
Write-Host "Creating directory structure..." -ForegroundColor Yellow
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  [+] Created: $dir" -ForegroundColor Green
    } else {
        Write-Host "  [✓] Exists: $dir" -ForegroundColor Gray
    }
}

# Create initial catalog files
Write-Host ""
Write-Host "Creating catalog files..." -ForegroundColor Yellow

# shows.yaml
$showsYaml = @"
# Show and Host Configuration
# Format: Map show identifiers to host information
shows:
  - id: my-generation
    name: "My Generation"
    host:
      name: "The News Forum Host"
      profileUrl: "https://www.thenewsforum.ca/hosts/default"
    description: "Exploring perspectives across generations"
    
  # Add more shows here following the same pattern
  # - id: show-slug
  #   name: "Show Display Name"
  #   host:
  #     name: "Host Name"
  #     profileUrl: "https://www.thenewsforum.ca/hosts/host-slug"
  #   description: "Brief show description"
"@

# guests.yaml
$guestsYaml = @"
# Guest Profile Database
# Format: List of known guests with profile URLs and expertise
guests:
  - name: "Sample Guest"
    profileUrl: "https://example.com/guest"
    expertise: ["Technology", "Innovation"]
    bio: "Brief bio of the guest"
    
  # Add more guests here:
  # - name: "Guest Name"
  #   profileUrl: "https://linkedin.com/in/username"
  #   expertise: ["Topic1", "Topic2"]
  #   bio: "One-line bio"
"@

# related.yaml
$relatedYaml = @"
# Related Content Links by Topic
# Format: Map topics to related articles/resources
topics:
  AI:
    - title: "Introduction to Artificial Intelligence"
      url: "https://www.thenewsforum.ca/topics/ai-intro"
      description: "Foundational concepts in AI"
      
  technology:
    - title: "Technology Trends 2025"
      url: "https://www.thenewsforum.ca/topics/tech-trends"
      description: "Latest technology developments"
      
  # Add more topics and related links:
  # topic-name:
  #   - title: "Resource Title"
  #     url: "https://example.com/resource"
  #     description: "Brief description"
"@

# citations.yaml
$citationsYaml = @"
# Academic and Source Citations by Topic
# Format: Map topics to academic papers, studies, and authoritative sources
topics:
  AI:
    - title: "Attention Is All You Need"
      url: "https://arxiv.org/abs/1706.03762"
      authors: "Vaswani et al."
      year: 2017
      type: "Academic Paper"
      
  # Add more citations:
  # topic-name:
  #   - title: "Paper/Article Title"
  #     url: "https://source.com/citation"
  #     authors: "Author Names"
  #     year: 2025
  #     type: "Academic Paper|Report|Article"
"@

# Write catalog files
$catalogFiles = @{
    "$baseDir\catalog\shows.yaml" = $showsYaml
    "$baseDir\catalog\guests.yaml" = $guestsYaml
    "$baseDir\catalog\related.yaml" = $relatedYaml
    "$baseDir\catalog\citations.yaml" = $citationsYaml
}

foreach ($file in $catalogFiles.Keys) {
    if (-not (Test-Path $file)) {
        $catalogFiles[$file] | Out-File -FilePath $file -Encoding UTF8
        Write-Host "  [+] Created: $file" -ForegroundColor Green
    } else {
        Write-Host "  [✓] Exists: $file (not overwriting)" -ForegroundColor Gray
    }
}

# Create processed tracking file
$processedFile = "$baseDir\processed\video-hashes.json"
if (-not (Test-Path $processedFile)) {
    '{}' | Out-File -FilePath $processedFile -Encoding UTF8
    Write-Host "  [+] Created: $processedFile" -ForegroundColor Green
} else {
    Write-Host "  [✓] Exists: $processedFile" -ForegroundColor Gray
}

# Create environment variables template
Write-Host ""
Write-Host "Creating environment configuration template..." -ForegroundColor Yellow

$envTemplate = @"
# n8n Environment Variables Configuration
# Copy these to your n8n settings (docker-compose.yml or n8n config)

# === REQUIRED PATHS ===
NN_INBOX=D:\newsroom\inbox\videos
NN_TR_OUT=D:\newsroom\outputs\assets\transcripts
NN_PAGES=D:\newsroom\outputs\pages
NN_CATALOG=D:\newsroom\catalog
NN_PROCESSED=D:\newsroom\processed\video-hashes.json
NN_LOGS=D:\newsroom\logs

# === WHISPER CONFIGURATION ===
WHISPER_CMD=whisper
WHISPER_MODEL=medium
WHISPER_LANGUAGE=en

# === SITE CONFIGURATION ===
NN_PUBLIC_BASE_URL=https://www.thenewsforum.ca
NN_SITE_NAME=The News Forum
NN_DEFAULT_HOST_NAME=The News Forum Host
NN_DEFAULT_HOST_URL=https://www.thenewsforum.ca/hosts/default

# === OPTIONAL: OLLAMA (Local LLM) ===
OLLAMA_ENABLED=false
OLLAMA_MODEL=llama3.1:8b
OLLAMA_API=http://localhost:11434/api/generate

# === OPTIONAL: ADVANCED ===
NN_DEBUG_MODE=false
NN_MAX_CONCURRENT=3
"@

$envFile = "$baseDir\.env.template"
$envTemplate | Out-File -FilePath $envFile -Encoding UTF8
Write-Host "  [+] Created: $envFile" -ForegroundColor Green

# Create README for inbox
$inboxReadme = @"
# Video Inbox

Drop your video files here for processing.

## Filename Convention

**Format:** `{Show}_{EpisodeId}_{YYYY-MM-DD}_{Topic-Keywords}.mp4`

### Examples:
- `MyGeneration_S02E07_2025-10-16_AI-in-Industry.mp4`
- `TechTalks_E123_2025-09-20_Quantum-Computing.mp4`
- `NewsHour_NH-2025-10-15_Climate-Policy.mp4`

### Rules:
- **Show:** Must match an entry in `catalog/shows.yaml`
- **EpisodeId:** Unique identifier (S##E##, E###, or custom format)
- **Date:** YYYY-MM-DD format
- **Topic:** Dash-separated keywords (used for URL slug)

## Processing

The n8n workflow scans this folder every 10 minutes and:
1. Transcribes the video using Whisper
2. Extracts metadata and generates summary
3. Creates structured HTML page with JSON-LD
4. Outputs to `outputs/pages/`

Processed videos are tracked in `processed/video-hashes.json` to avoid re-processing.
"@

$inboxReadme | Out-File -FilePath "$baseDir\inbox\videos\README.md" -Encoding UTF8
Write-Host "  [+] Created: $baseDir\inbox\videos\README.md" -ForegroundColor Green

# System verification
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "System Verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check Python
Write-Host ""
Write-Host "Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  [✓] $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  [✗] Python not found - Install Python 3.8+ from python.org" -ForegroundColor Red
}

# Check ffmpeg
Write-Host ""
Write-Host "Checking ffmpeg..." -ForegroundColor Yellow
try {
    $ffmpegVersion = ffmpeg -version 2>&1 | Select-Object -First 1
    Write-Host "  [✓] $ffmpegVersion" -ForegroundColor Green
} catch {
    Write-Host "  [✗] ffmpeg not found - Install from ffmpeg.org" -ForegroundColor Red
}

# Check Whisper
Write-Host ""
Write-Host "Checking Whisper..." -ForegroundColor Yellow
try {
    $whisperCheck = whisper --help 2>&1
    if ($whisperCheck) {
        Write-Host "  [✓] Whisper is installed" -ForegroundColor Green
    }
} catch {
    Write-Host "  [✗] Whisper not found" -ForegroundColor Red
    Write-Host "      Install with: pip install openai-whisper" -ForegroundColor Yellow
}

# Check n8n
Write-Host ""
Write-Host "Checking n8n..." -ForegroundColor Yellow
try {
    $n8nVersion = n8n --version 2>&1
    Write-Host "  [✓] n8n version $n8nVersion" -ForegroundColor Green
} catch {
    Write-Host "  [!] n8n not found in PATH (may be running in Docker)" -ForegroundColor Yellow
}

# Check Ollama (optional)
Write-Host ""
Write-Host "Checking Ollama (optional)..." -ForegroundColor Yellow
try {
    $ollamaVersion = ollama --version 2>&1
    Write-Host "  [✓] $ollamaVersion" -ForegroundColor Green
} catch {
    Write-Host "  [!] Ollama not installed (optional for LLM features)" -ForegroundColor Gray
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Review and customize catalog files in: $baseDir\catalog" -ForegroundColor White
Write-Host "  2. Configure n8n environment variables from: $baseDir\.env.template" -ForegroundColor White
Write-Host "  3. Import the workflow into n8n: n8n_workflow_all_in_one.json" -ForegroundColor White
Write-Host "  4. Test with a sample video in: $baseDir\inbox\videos" -ForegroundColor White
Write-Host ""
Write-Host "Documentation: See AUDIT_AND_SETUP.md for full details" -ForegroundColor Gray
Write-Host ""
