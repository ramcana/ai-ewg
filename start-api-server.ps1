#!/usr/bin/env pwsh
# Quick start script for the API server
# Optimized for SQLite concurrency with single-worker mode

Write-Host "🚀 Starting AI-EWG API Server..." -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path ".\venv\Scripts\Activate.ps1")) {
    Write-Host "❌ Virtual environment not found!" -ForegroundColor Red
    Write-Host "Please run: python -m venv venv" -ForegroundColor Yellow
    exit 1
}

# Check if config file exists
if (-not (Test-Path ".\config\pipeline.yaml")) {
    Write-Host "❌ Configuration file not found!" -ForegroundColor Red
    Write-Host "Expected: .\config\pipeline.yaml" -ForegroundColor Yellow
    exit 1
}

# Activate virtual environment
Write-Host "📦 Activating virtual environment..." -ForegroundColor Green
& ".\venv\Scripts\Activate.ps1"

# Display SQLite optimization info
Write-Host ""
Write-Host "🔧 SQLite Optimizations Active:" -ForegroundColor Cyan
Write-Host "   • Single-worker mode (prevents multi-process locks)" -ForegroundColor Gray
Write-Host "   • WAL journal mode (better concurrency)" -ForegroundColor Gray
Write-Host "   • 10-second busy timeout with exponential backoff" -ForegroundColor Gray
Write-Host "   • NullPool behavior (aggressive connection closing)" -ForegroundColor Gray
Write-Host ""

# Start the API server
Write-Host "🌐 Starting API server on http://0.0.0.0:8000..." -ForegroundColor Green
Write-Host ""
Write-Host "⚠️  IMPORTANT:" -ForegroundColor Yellow
Write-Host "   • Keep this window open while running n8n workflows!" -ForegroundColor Yellow
Write-Host "   • Do NOT access pipeline.db from other processes" -ForegroundColor Yellow
Write-Host "   • For high concurrency, consider migrating to PostgreSQL" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor White
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

python src/cli.py --config config/pipeline.yaml api --port 8000
