# PowerShell script to build WPP executable
# Requires uv package manager to be installed

Write-Host "Starting WPP executable build process..." -ForegroundColor Green

# Check if we're in the project root
if (-not (Test-Path "pyproject.toml")) {
    Write-Host "Error: Must run from project root directory" -ForegroundColor Red
    Write-Host "Please navigate to the WPP project directory first" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if uv is installed
try {
    $uvVersion = uv --version 2>$null
    Write-Host "Found uv: $uvVersion" -ForegroundColor Cyan
} catch {
    Write-Host "Error: uv package manager not found" -ForegroundColor Red
    Write-Host "Please install uv from https://docs.astral.sh/uv/" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Running build script with uv..." -ForegroundColor Yellow

try {
    uv run build_web_app.py
    if ($LASTEXITCODE -ne 0) {
        throw "Build script failed with exit code $LASTEXITCODE"
    }
} catch {
    Write-Host "Build failed: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Build completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Executable files created in: dist\wpp\" -ForegroundColor Cyan
Write-Host ""
Write-Host "Available executables:" -ForegroundColor White
Write-Host "  wpp-web-app.exe      - React web application" -ForegroundColor Gray
Write-Host "  run-reports.exe      - Command-line reports generator" -ForegroundColor Gray
Write-Host "  update-database.exe  - Database update utility" -ForegroundColor Gray
Write-Host ""
Write-Host "Usage:" -ForegroundColor White
Write-Host "  To run the web app: .\dist\wpp\wpp-web-app.exe" -ForegroundColor Gray
Write-Host "  To run reports: .\dist\wpp\run-reports.exe" -ForegroundColor Gray
Write-Host "  To update database: .\dist\wpp\update-database.exe" -ForegroundColor Gray
Write-Host ""

Read-Host "Press Enter to exit"