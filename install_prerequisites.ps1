param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host "Installing WPP Build System Prerequisites" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

try {
    # Check if winget is available
    if (-not (Get-Command "winget" -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: winget is not available on this system" -ForegroundColor Red
        Write-Host "winget is required to install prerequisites automatically." -ForegroundColor Yellow
        Write-Host "Please install winget or manually install Git and Node.js" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "winget found" -ForegroundColor Green

    # Function to check if a package is installed via winget
    function Test-WingetPackage {
        param($PackageId)
        $installed = winget list --id $PackageId --exact 2>$null
        return $LASTEXITCODE -eq 0
    }

    # Install Git
    Write-Host ""
    Write-Host "Checking Git..." -ForegroundColor Yellow
    if ((Get-Command "git" -ErrorAction SilentlyContinue) -and (-not $Force)) {
        $gitVersion = git --version
        Write-Host "Git already installed: $gitVersion" -ForegroundColor Green
    } else {
        Write-Host "Installing Git..." -ForegroundColor Yellow
        winget install --id Git.Git --exact --silent --accept-package-agreements --accept-source-agreements
        # Check if git is now available (winget may return non-zero even when already installed)
        if (Get-Command "git" -ErrorAction SilentlyContinue) {
            Write-Host "Git available" -ForegroundColor Green
            # Refresh PATH for current session
            $machinePath = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
            $userPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
            $env:PATH = $machinePath + ";" + $userPath
        } else {
            Write-Host "Git installation attempted but command not found - continuing anyway" -ForegroundColor Yellow
        }
    }

    # Install Node.js
    Write-Host ""
    Write-Host "Checking Node.js..." -ForegroundColor Yellow
    if ((Get-Command "node" -ErrorAction SilentlyContinue) -and (-not $Force)) {
        $nodeVersion = node --version
        Write-Host "Node.js already installed: $nodeVersion" -ForegroundColor Green
    } else {
        Write-Host "Installing Node.js LTS..." -ForegroundColor Yellow
        winget install --id OpenJS.NodeJS.LTS --exact --silent --accept-package-agreements --accept-source-agreements
        # Check if node is now available (winget may return non-zero even when already installed)
        if (Get-Command "node" -ErrorAction SilentlyContinue) {
            Write-Host "Node.js available" -ForegroundColor Green
            # Refresh PATH for current session
            $machinePath = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
            $userPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
            $env:PATH = $machinePath + ";" + $userPath
        } else {
            Write-Host "Node.js installation attempted but command not found - continuing anyway" -ForegroundColor Yellow
        }
    }

    # Verify installations
    Write-Host ""
    Write-Host "Verifying installations..." -ForegroundColor Yellow
    
    Start-Sleep -Seconds 3  # Give time for PATH updates
    
    if (Get-Command "git" -ErrorAction SilentlyContinue) {
        $gitVersion = git --version
        Write-Host "Git verified: $gitVersion" -ForegroundColor Green
    } else {
        Write-Host "Git command not found in PATH. You may need to restart your terminal." -ForegroundColor Yellow
    }

    if (Get-Command "node" -ErrorAction SilentlyContinue) {
        $nodeVersion = node --version
        $npmVersion = npm --version
        Write-Host "Node.js verified: $nodeVersion" -ForegroundColor Green
        Write-Host "npm verified: $npmVersion" -ForegroundColor Green
    } else {
        Write-Host "Node.js command not found in PATH. You may need to restart your terminal." -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "=================================================================================" -ForegroundColor Green
    Write-Host "                        PREREQUISITES INSTALLATION COMPLETE!" -ForegroundColor Green
    Write-Host "=================================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Installed components:" -ForegroundColor White
    Write-Host "  • Git - Version control system" -ForegroundColor White
    Write-Host "  • Node.js LTS - JavaScript runtime and npm package manager" -ForegroundColor White
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor White
    Write-Host "  1. Close and reopen your terminal/PowerShell window" -ForegroundColor White
    Write-Host "  2. Run BUILD_WPP_WEB_QUICK.bat to build WPP executables" -ForegroundColor White
    Write-Host ""
    Write-Host "Note: Python/uv will be installed automatically by the build scripts" -ForegroundColor Cyan
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "=================================================================================" -ForegroundColor Red
    Write-Host "                           INSTALLATION FAILED!" -ForegroundColor Red
    Write-Host "=================================================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Manual installation options:" -ForegroundColor Yellow
    Write-Host "  • Git: https://git-scm.com/download/windows" -ForegroundColor Yellow
    Write-Host "  • Node.js: https://nodejs.org/en/download/" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "After manual installation, run BUILD_WPP_WEB_QUICK.bat" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}