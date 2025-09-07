param(
    [string]$RepoUrl = "https://github.com/srmorgan1/WPP.git",
    [string]$Branch = "master", 
    [string]$WorkDir = (Join-Path $PSScriptRoot "wpp-build"),
    [switch]$SkipTests,
    [switch]$ApiOnly
)

$ErrorActionPreference = "Stop"

Write-Host "Starting WPP Web Application Build" -ForegroundColor Cyan

try {
    # Check Git
    if (-not (Get-Command "git" -ErrorAction SilentlyContinue)) {
        throw "Git is not installed"
    }
    Write-Host "Git found" -ForegroundColor Green
    
    # Check/Install Node.js (unless API-only)
    if (-not $ApiOnly) {
        if (-not (Get-Command "node" -ErrorAction SilentlyContinue)) {
            Write-Host "Node.js not found - installing..." -ForegroundColor Yellow
            $nodeUrl = "https://nodejs.org/dist/v20.10.0/node-v20.10.0-x64.msi"
            $nodeInstaller = Join-Path $env:TEMP "nodejs-installer.msi"
            
            try {
                Invoke-WebRequest -Uri $nodeUrl -OutFile $nodeInstaller -UseBasicParsing
                Start-Process -FilePath "msiexec.exe" -ArgumentList "/i", $nodeInstaller, "/quiet", "/norestart" -Wait
                $env:PATH = $env:PATH + ";C:\Program Files\nodejs"
                Start-Sleep -Seconds 5
                
                if (Get-Command "node" -ErrorAction SilentlyContinue) {
                    Write-Host "Node.js installed successfully" -ForegroundColor Green
                } else {
                    Write-Host "Node.js installation may need system restart - continuing with API-only build" -ForegroundColor Yellow
                    $ApiOnly = $true
                }
            } finally {
                if (Test-Path $nodeInstaller) { Remove-Item $nodeInstaller -Force }
            }
        } else {
            $nodeVersion = node --version
            Write-Host "Node.js found: $nodeVersion" -ForegroundColor Green
        }
    }
    
    # Setup working directory
    if (-not (Test-Path $WorkDir)) {
        New-Item -Path $WorkDir -ItemType Directory -Force | Out-Null
    }
    Set-Location $WorkDir
    Write-Host "Working directory: $WorkDir" -ForegroundColor Green
    
    # Clone repository (same as simple_build.ps1)
    $repoDir = Join-Path $WorkDir "WPP"
    if (Test-Path $repoDir) {
        Set-Location $repoDir
        git fetch origin
        git checkout $Branch
        git pull origin $Branch
        Write-Host "Repository updated" -ForegroundColor Green
    } else {
        git clone -b $Branch $RepoUrl
        Set-Location $repoDir
        Write-Host "Repository cloned" -ForegroundColor Green
    }
    
    # Check for pyproject.toml (same as simple_build.ps1)
    if (-not (Test-Path "pyproject.toml")) {
        throw "pyproject.toml not found"
    }
    
    # Install uv if not present (same as simple_build.ps1)
    if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
        Write-Host "Installing uv..." -ForegroundColor Yellow
        iwr https://astral.sh/uv/install.ps1 | iex
        $env:PATH = $env:PATH + ";" + "$env:USERPROFILE\.cargo\bin"
    }
    Write-Host "uv found" -ForegroundColor Green
    
    # Setup Python environment (same as simple_build.ps1)
    Write-Host "Setting up Python environment..." -ForegroundColor Yellow
    uv sync --dev
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to sync Python environment"
    }
    Write-Host "Python environment ready" -ForegroundColor Green
    
    # Build React frontend if not API-only
    $reactBuilt = $false
    if (-not $ApiOnly) {
        $reactDirs = @("frontend", "web", "client", "react-app", "ui", "webapp")
        $reactDir = $null
        foreach ($dir in $reactDirs) {
            if ((Test-Path $dir) -and (Test-Path "$dir\package.json")) {
                $reactDir = $dir
                break
            }
        }
        
        if ($reactDir) {
            Write-Host "Building React frontend in $reactDir..." -ForegroundColor Yellow
            Set-Location $reactDir
            
            # Install React dependencies
            Write-Host "Installing React dependencies..." -ForegroundColor Yellow
            npm install
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to install React dependencies"
            }
            Write-Host "React dependencies installed" -ForegroundColor Green
            
            # Build React production bundle
            Write-Host "Building React production bundle..." -ForegroundColor Yellow
            npm run build
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to build React frontend"
            }
            Write-Host "React frontend built successfully" -ForegroundColor Green
            
            Set-Location ..
            $reactBuilt = $true
        } else {
            Write-Host "No React frontend found - building API-only version" -ForegroundColor Yellow
        }
    }
    
    # Run tests if not skipped (same as simple_build.ps1)
    if (-not $SkipTests) {
        Write-Host "Running tests..." -ForegroundColor Yellow
        uv run pytest tests/ -v
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Tests failed, continuing with build" -ForegroundColor Yellow
        } else {
            Write-Host "Tests passed" -ForegroundColor Green
        }
    }
    
    # Run linting (same as simple_build.ps1)
    Write-Host "Running linting..." -ForegroundColor Yellow
    uv run ruff check src/
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Linting issues found, continuing" -ForegroundColor Yellow
    }
    
    # Build executables (same approach as simple_build.ps1)
    Write-Host "Building executables..." -ForegroundColor Yellow
    
    # Set environment variables to help build scripts know React is already built
    if ($reactBuilt) {
        $env:REACT_BUILD_DONE = "true"
        $env:SKIP_NPM_INSTALL = "true"
        $env:REACT_FRONTEND_BUILT = "true"
        $env:NPM_DEPENDENCIES_INSTALLED = "true"
        Write-Host "Set environment flags to skip duplicate React operations in Python script" -ForegroundColor Green
    } else {
        # Clear environment variables if React wasn't built
        $env:REACT_BUILD_DONE = $null
        $env:SKIP_NPM_INSTALL = $null
        $env:REACT_FRONTEND_BUILT = $null
        $env:NPM_DEPENDENCIES_INSTALLED = $null
    }
    
    # Set encoding to handle Unicode characters in Python scripts
    $env:PYTHONIOENCODING = "utf-8"
    
    # Get repo top level directory (parent of current WPP checkout directory)
    $topLevelDir = Split-Path -Parent (Get-Location)
    
    if (Test-Path "$topLevelDir\build_executable.ps1") {
        Set-Location $topLevelDir
        & .\build_executable.ps1
        if ($LASTEXITCODE -ne 0) {
            throw "Build failed"
        }
    } elseif (Test-Path "$topLevelDir\build_web_app.py") {
        Write-Host "Using build_web_app.py from repo top level" -ForegroundColor Yellow
        Set-Location $topLevelDir
        uv run python build_web_app.py
        if ($LASTEXITCODE -ne 0) {
            throw "build_web_app.py failed"
        }
    } elseif (Test-Path "$topLevelDir\build_executable.py") {
        Write-Host "Using build_executable.py from repo top level" -ForegroundColor Yellow
        Set-Location $topLevelDir
        uv run python build_executable.py
        if ($LASTEXITCODE -ne 0) {
            throw "build_executable.py failed"
        }
    } else {
        Write-Host "No build script found, skipping executable build" -ForegroundColor Yellow
    }
    
    Write-Host "Web application build completed successfully!" -ForegroundColor Green
    
} catch {
    Write-Host "Build failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}