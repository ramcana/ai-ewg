# Setup Script for AI-EWG CLI
# Run this to install and configure the new CLI system

Write-Host "🚀 AI-EWG CLI Setup" -ForegroundColor Cyan
Write-Host "===================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "Checking Python version..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($pythonVersion -match "Python 3\.(1[0-9]|[2-9][0-9])") {
    Write-Host "✓ $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "✗ Python 3.10+ required. Found: $pythonVersion" -ForegroundColor Red
    exit 1
}

# Check if in virtual environment
Write-Host ""
Write-Host "Checking virtual environment..." -ForegroundColor Yellow
if ($env:VIRTUAL_ENV) {
    Write-Host "✓ Virtual environment active: $env:VIRTUAL_ENV" -ForegroundColor Green
} else {
    Write-Host "⚠ No virtual environment detected" -ForegroundColor Yellow
    Write-Host "  Consider activating venv: .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
    $continue = Read-Host "Continue anyway? (y/N)"
    if ($continue -ne "y") {
        exit 0
    }
}

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to install dependencies" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Dependencies installed" -ForegroundColor Green

# Install CLI in development mode
Write-Host ""
Write-Host "Installing CLI..." -ForegroundColor Yellow
pip install -e .
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to install CLI" -ForegroundColor Red
    exit 1
}
Write-Host "✓ CLI installed" -ForegroundColor Green

# Verify CLI
Write-Host ""
Write-Host "Verifying CLI..." -ForegroundColor Yellow
$cliVersion = ai-ewg version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ CLI working: $cliVersion" -ForegroundColor Green
} else {
    Write-Host "✗ CLI not found. Try restarting your shell." -ForegroundColor Red
    exit 1
}

# Create config if needed
Write-Host ""
Write-Host "Checking configuration..." -ForegroundColor Yellow
if (Test-Path "config\system.yaml") {
    Write-Host "✓ config\system.yaml exists" -ForegroundColor Green
} else {
    Write-Host "⚠ config\system.yaml not found" -ForegroundColor Yellow
    $createConfig = Read-Host "Create from example? (Y/n)"
    if ($createConfig -ne "n") {
        Copy-Item "config\system.yaml.example" "config\system.yaml"
        Write-Host "✓ Created config\system.yaml" -ForegroundColor Green
        Write-Host "  → Edit config\system.yaml with your paths" -ForegroundColor Gray
    }
}

# Initialize database
Write-Host ""
Write-Host "Initializing registry database..." -ForegroundColor Yellow
ai-ewg db init
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Database initialized" -ForegroundColor Green
} else {
    Write-Host "✗ Database initialization failed" -ForegroundColor Red
    exit 1
}

# Check database status
Write-Host ""
Write-Host "Database status:" -ForegroundColor Yellow
ai-ewg db status

# Summary
Write-Host ""
Write-Host "🎉 Setup Complete!" -ForegroundColor Green
Write-Host "==================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Edit config\system.yaml with your video paths" -ForegroundColor White
Write-Host "  2. Run: ai-ewg discover --dry-run" -ForegroundColor White
Write-Host "  3. Run: ai-ewg discover" -ForegroundColor White
Write-Host "  4. Check: ai-ewg db status" -ForegroundColor White
Write-Host ""
Write-Host "Documentation:" -ForegroundColor Cyan
Write-Host "  • UPGRADE_SUMMARY.md - What's new" -ForegroundColor White
Write-Host "  • docs\QUICKSTART_CLI.md - CLI usage" -ForegroundColor White
Write-Host "  • MIGRATION_GUIDE.md - Migration steps" -ForegroundColor White
Write-Host ""
Write-Host "Get help: ai-ewg --help" -ForegroundColor Gray
