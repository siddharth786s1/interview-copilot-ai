# =============================================================================
# Dev Script — Start Frontend and Backend concurrently
# =============================================================================

$projectRoot = "$PSScriptRoot\.."

Write-Host "Starting Interview Copilot AI..." -ForegroundColor Cyan

# Check if .env exists
if (-not (Test-Path "$projectRoot\.env")) {
    Write-Host "[WARNING] .env file not found. Copying from .env.example..." -ForegroundColor Yellow
    Copy-Item "$projectRoot\.env.example" "$projectRoot\.env"
}

# Start Backend
Write-Host "Launching Backend on http://localhost:8000..." -ForegroundColor Green
$backendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\backend'; python -m uvicorn app.main:app --reload --port 8000" -PassThru

# Start Frontend
Write-Host "Launching Frontend on http://localhost:3000..." -ForegroundColor Green
$frontendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\frontend'; npm run dev" -PassThru

Write-Host "`nBoth processes launched!" -ForegroundColor Cyan
Write-Host "Backend:  http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Yellow
Write-Host "Press Ctrl+C in their respective windows to stop." -ForegroundColor Gray
