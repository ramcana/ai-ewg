# Fix Database Lock Issues
# This script helps diagnose and fix SQLite database locks

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "Database Lock Fix Utility" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

$dbPath = "D:\n8n\ai-ewg\data\pipeline.db"

# Step 1: Check current Python processes
Write-Host "1. Checking Python processes..." -ForegroundColor Yellow
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue

if ($pythonProcesses) {
    Write-Host "   Found $($pythonProcesses.Count) Python process(es):" -ForegroundColor White
    $pythonProcesses | ForEach-Object {
        $runtime = (Get-Date) - $_.StartTime
        Write-Host "   PID $($_.Id): Started $($_.StartTime.ToString('yyyy-MM-dd HH:mm:ss')) (running for $([math]::Round($runtime.TotalHours, 1))h)" -ForegroundColor Gray
    }
    
    # Ask to kill old processes
    Write-Host "`n   Do you want to kill all Python processes? (y/N): " -ForegroundColor Yellow -NoNewline
    $response = Read-Host
    
    if ($response -eq 'y' -or $response -eq 'Y') {
        $pythonProcesses | Stop-Process -Force
        Write-Host "   ✅ All Python processes killed" -ForegroundColor Green
        Start-Sleep -Seconds 2
    }
} else {
    Write-Host "   ✅ No Python processes running" -ForegroundColor Green
}

# Step 2: Check database lock status
Write-Host "`n2. Checking database lock status..." -ForegroundColor Yellow
python scripts/diagnose-db-lock.py

# Step 3: Checkpoint WAL
Write-Host "`n3. Attempting WAL checkpoint..." -ForegroundColor Yellow
python scripts/checkpoint-wal.py

# Step 4: Enable WAL mode with optimal settings
Write-Host "`n4. Optimizing database settings..." -ForegroundColor Yellow
python scripts/enable-wal-mode.py

# Step 5: Final check
Write-Host "`n5. Final lock status check..." -ForegroundColor Yellow
python scripts/diagnose-db-lock.py

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "Fix Complete!" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "  1. Restart your API server: python -m src.api.main" -ForegroundColor White
Write-Host "  2. Run your n8n workflow" -ForegroundColor White
Write-Host "  3. If still locked, close DB Browser for SQLite`n" -ForegroundColor White
