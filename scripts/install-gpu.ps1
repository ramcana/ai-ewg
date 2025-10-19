#!/usr/bin/env pwsh
# GPU-Optimized Installation Script
# For: AMD Threadripper PRO 5995WX + RTX 4080 + 128GB RAM

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "GPU-Optimized Whisper Installation" -ForegroundColor Cyan
Write-Host "RTX 4080 Detected System" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if venv exists
if (-not (Test-Path ".\venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "  [✓] Virtual environment created" -ForegroundColor Green
}

# Activate venv
Write-Host ""
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Verify Python
Write-Host ""
Write-Host "Checking Python version..." -ForegroundColor Yellow
$pythonVersion = python --version
Write-Host "  [✓] $pythonVersion" -ForegroundColor Green

# Upgrade pip
Write-Host ""
Write-Host "Upgrading pip, setuptools, wheel..." -ForegroundColor Yellow
python -m pip install --upgrade pip setuptools wheel --quiet
Write-Host "  [✓] Package managers upgraded" -ForegroundColor Green

# Check NVIDIA GPU
Write-Host ""
Write-Host "Checking NVIDIA GPU..." -ForegroundColor Yellow
try {
    $gpuInfo = nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>$null
    if ($gpuInfo) {
        Write-Host "  [✓] GPU Detected: $gpuInfo" -ForegroundColor Green
    }
} catch {
    Write-Host "  [!] nvidia-smi not found - GPU may not be available" -ForegroundColor Yellow
}

# Install PyTorch with CUDA support
Write-Host ""
Write-Host "Installing PyTorch with CUDA 12.1 support..." -ForegroundColor Yellow
Write-Host "  (This may take 3-5 minutes - downloading ~2GB)" -ForegroundColor Gray
pip install torch==2.1.0+cu121 torchaudio==2.1.0+cu121 --extra-index-url https://download.pytorch.org/whl/cu121 --quiet
Write-Host "  [✓] PyTorch with CUDA installed" -ForegroundColor Green

# Verify CUDA
Write-Host ""
Write-Host "Verifying CUDA availability..." -ForegroundColor Yellow
$cudaCheck = python -c "import torch; print(f'{torch.cuda.is_available()}|{torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')"
$parts = $cudaCheck -split '\|'
$cudaAvailable = $parts[0]
$gpuName = $parts[1]

if ($cudaAvailable -eq "True") {
    Write-Host "  [✓] CUDA Available: YES" -ForegroundColor Green
    Write-Host "  [✓] GPU Device: $gpuName" -ForegroundColor Green
} else {
    Write-Host "  [✗] CUDA NOT AVAILABLE - will use CPU (slow)" -ForegroundColor Red
    Write-Host "      Check NVIDIA drivers and CUDA toolkit installation" -ForegroundColor Yellow
}

# Install faster-whisper
Write-Host ""
Write-Host "Installing faster-whisper (GPU-optimized)..." -ForegroundColor Yellow
pip install faster-whisper>=0.10.0 --quiet
Write-Host "  [✓] Faster-Whisper installed" -ForegroundColor Green

# Install additional dependencies
Write-Host ""
Write-Host "Installing additional dependencies..." -ForegroundColor Yellow
pip install pyyaml numpy --quiet
Write-Host "  [✓] Additional packages installed" -ForegroundColor Green

# Test faster-whisper
Write-Host ""
Write-Host "Testing faster-whisper with GPU..." -ForegroundColor Yellow
try {
    python -c "from faster_whisper import WhisperModel; model = WhisperModel('tiny', device='cuda', compute_type='float16'); print('OK')" 2>$null | Out-Null
    Write-Host "  [✓] Faster-Whisper GPU test PASSED" -ForegroundColor Green
} catch {
    Write-Host "  [!] GPU test failed - will fall back to CPU" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Installation Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Show installed packages
Write-Host "Installed Packages:" -ForegroundColor Yellow
pip list | Select-String -Pattern "torch|whisper|numpy|yaml"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Next Steps" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Your system is ready for GPU-accelerated transcription!" -ForegroundColor White
Write-Host "2. Recommended model: large-v3 (your RTX 4080 can handle it)" -ForegroundColor White
Write-Host "3. Expected speed: 3-4 minutes per 30-min video" -ForegroundColor White
Write-Host ""
Write-Host "Test with your video:" -ForegroundColor Yellow
Write-Host "  .\test-gpu.ps1 -VideoPath 'D:\newsroom\inbox\videos\ForumDaily_E001_2025-10-15_Daily-Discussion.mp4'" -ForegroundColor Gray
Write-Host ""
Write-Host "Or use the model directly:" -ForegroundColor Yellow
Write-Host "  python" -ForegroundColor Gray
Write-Host "  >>> from faster_whisper import WhisperModel" -ForegroundColor Gray
Write-Host "  >>> model = WhisperModel('large-v3', device='cuda', compute_type='float16')" -ForegroundColor Gray
Write-Host "  >>> segments, info = model.transcribe('video.mp4')" -ForegroundColor Gray
Write-Host ""
