# =============================================================================
# Setup Script for Interview Copilot AI (Windows PowerShell)
# =============================================================================

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Setting up Interview Copilot AI..." -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Check Python
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Python is not found. Please install Python 3.11+." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] $pythonVersion detected" -ForegroundColor Green

# Check Node.js
$nodeVersion = node -v 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Node.js is not found. Please install Node.js 18+." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Node.js $nodeVersion detected" -ForegroundColor Green

# Check ffmpeg
$ffmpegVersion = ffmpeg -version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] ffmpeg is not installed or not in PATH." -ForegroundColor Yellow
    Write-Host "          Run: winget install ffmpeg" -ForegroundColor Yellow
    Write-Host "          (Required for speech-to-text audio resampling in Phase 4)" -ForegroundColor Yellow
} else {
    Write-Host "[OK] ffmpeg is installed" -ForegroundColor Green
}

# Backend dependencies
Write-Host "`nInstalling Python backend dependencies..." -ForegroundColor Cyan
Set-Location "$PSScriptRoot\..\backend"
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to install Python dependencies." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Backend dependencies installed." -ForegroundColor Green

# Environment file
$envPath = "$PSScriptRoot\..\.env"
$envExamplePath = "$PSScriptRoot\..\.env.example"
if (-not (Test-Path $envPath)) {
    Write-Host "`nCreating .env from .env.example..." -ForegroundColor Cyan
    Copy-Item $envExamplePath $envPath
    Write-Host "[OK] Created .env. Please configure your GOOGLE_API_KEY or OPENAI_API_KEY." -ForegroundColor Yellow
}

# Frontend dependencies
Write-Host "`nInstalling Frontend dependencies..." -ForegroundColor Cyan
Set-Location "$PSScriptRoot\..\frontend"
if (Test-Path "package.json") {
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to install frontend dependencies." -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Frontend dependencies installed." -ForegroundColor Green
}

Write-Host "`n=========================================" -ForegroundColor Cyan
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "Run .\scripts\dev.ps1 to start development servers." -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
