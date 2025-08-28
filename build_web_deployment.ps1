# PowerShell CI/CD Script for WPP Project with Web Application
# Builds the modern FastAPI + React version with full UI experience
# Automatically installs Node.js if needed for React frontend build
#
# Authentication:
#   - Set GIT_TOKEN environment variable for automated access to private repositories
#   - Without GIT_TOKEN, uses Git's default authentication (may open browser)

param(
    [string]$RepoUrl = "https://github.com/srmorgan1/WPP.git",
    [string]$Branch = "master",
    [string]$WorkDir = "C:\temp\wpp-build",
    [switch]$SkipTests,
    [switch]$CleanWorkDir,
    [switch]$KeepRepo,
    [switch]$SkipNodeInstall,
    [switch]$ApiOnly
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Color coding for output
function Write-Section {
    param([string]$Message)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host $Message -ForegroundColor White
}

# Function to check if a command exists
function Test-Command {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

# Function to execute command and check result
function Invoke-SafeCommand {
    param(
        [string]$Command,
        [string]$Arguments = "",
        [string]$ErrorMessage = "Command failed"
    )
    
    Write-Info "Executing: $Command $Arguments"
    
    if ($Arguments) {
        $process = Start-Process -FilePath $Command -ArgumentList $Arguments -Wait -PassThru -NoNewWindow
    } else {
        $process = Start-Process -FilePath $Command -Wait -PassThru -NoNewWindow
    }
    
    if ($process.ExitCode -ne 0) {
        throw "$ErrorMessage (Exit code: $($process.ExitCode))"
    }
}

# Function to install Node.js
function Install-NodeJS {
    Write-Info "Installing Node.js LTS..."
    
    # Download and install Node.js LTS
    $nodeUrl = "https://nodejs.org/dist/v20.10.0/node-v20.10.0-x64.msi"
    $nodeInstaller = Join-Path $env:TEMP "nodejs-installer.msi"
    
    try {
        Write-Info "Downloading Node.js installer..."
        Invoke-WebRequest -Uri $nodeUrl -OutFile $nodeInstaller -UseBasicParsing
        
        Write-Info "Installing Node.js (this may take a few minutes)..."
        Start-Process -FilePath "msiexec.exe" -ArgumentList "/i", $nodeInstaller, "/quiet", "/norestart" -Wait
        
        # Refresh PATH environment variable
        $env:PATH = [Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [Environment]::GetEnvironmentVariable("PATH", "User")
        
        # Wait a moment for PATH to update
        Start-Sleep -Seconds 5
        
        # Verify installation
        if (Test-Command "node") {
            $nodeVersion = node --version
            Write-Success "✓ Node.js installed: $nodeVersion"
            return $true
        } else {
            throw "Node.js installation failed - command not found after installation"
        }
        
    } catch {
        Write-Error "Failed to install Node.js: $($_.Exception.Message)"
        return $false
    } finally {
        # Clean up installer
        if (Test-Path $nodeInstaller) {
            Remove-Item $nodeInstaller -Force
        }
    }
}

try {
    Write-Section "WPP Web Application CI/CD Build Pipeline Starting"
    
    if ($ApiOnly) {
        Write-Info "🔧 API-Only Mode: Building without React frontend"
    } else {
        Write-Info "🌐 Full Web Mode: Building with React frontend + API backend"
    }
    
    # Check prerequisites
    Write-Section "Checking Prerequisites"
    
    # Check Git
    if (-not (Test-Command "git")) {
        throw "Git is not installed or not in PATH. Please install Git for Windows."
    }
    Write-Success "✓ Git found: $(git --version)"
    
    # Setup uv package manager
    if (-not (Test-Command "uv")) {
        Write-Info "uv package manager not found. Installing uv..."
        Write-Info "Note: uv will automatically download Python 3.13+ as needed for this project"
        try {
            # Install uv using the official installer
            $uvInstaller = Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -UseBasicParsing
            Invoke-Expression $uvInstaller.Content
            # Refresh PATH
            $env:PATH = [Environment]::GetEnvironmentVariable("PATH", "User") + ";" + [Environment]::GetEnvironmentVariable("PATH", "Machine")
            if (-not (Test-Command "uv")) {
                throw "Failed to install uv package manager"
            }
        } catch {
            throw "Failed to install uv: $($_.Exception.Message)"
        }
    }
    $uvVersion = uv --version 2>&1
    Write-Success "✓ uv found: $uvVersion"
    
    # Check/Install Node.js (unless API-only or explicitly skipped)
    if (-not $ApiOnly -and -not $SkipNodeInstall) {
        if (-not (Test-Command "node")) {
            Write-Warning "⚠ Node.js not found. Installing Node.js for React frontend build..."
            if (-not (Install-NodeJS)) {
                Write-Error "❌ Failed to install Node.js automatically."
                Write-Info "Options:"
                Write-Info "  1. Install Node.js manually from https://nodejs.org/"
                Write-Info "  2. Use -ApiOnly flag to build without React frontend"
                Write-Info "  3. Use -SkipNodeInstall and handle Node.js installation separately"
                throw "Node.js installation failed"
            }
        } else {
            $nodeVersion = node --version
            $npmVersion = npm --version
            Write-Success "✓ Node.js found: $nodeVersion"
            Write-Success "✓ npm found: $npmVersion"
        }
    } elseif ($ApiOnly) {
        Write-Info "🔧 Skipping Node.js check (API-only mode)"
    } else {
        Write-Info "🔧 Skipping Node.js installation (SkipNodeInstall flag set)"
    }
    
    # Setup working directory
    Write-Section "Setting Up Working Directory"
    
    if ($CleanWorkDir -and (Test-Path $WorkDir)) {
        Write-Info "Cleaning existing working directory: $WorkDir"
        Remove-Item -Path $WorkDir -Recurse -Force
    }
    
    if (-not (Test-Path $WorkDir)) {
        Write-Info "Creating working directory: $WorkDir"
        New-Item -Path $WorkDir -ItemType Directory -Force | Out-Null
    }
    
    Set-Location $WorkDir
    Write-Success "✓ Working directory ready: $WorkDir"
    
    # Clone or update repository
    Write-Section "Checking Out Source Code"
    
    # Use GIT_TOKEN if available for automated authentication
    $CloneUrl = $RepoUrl
    if ($env:GIT_TOKEN) {
        Write-Info "Using GIT_TOKEN for authentication"
        $CloneUrl = $RepoUrl -replace "https://github.com/", "https://$($env:GIT_TOKEN)@github.com/"
    } else {
        Write-Info "No GIT_TOKEN found - will use Git's default authentication (may prompt for credentials)"
    }
    
    $repoDir = Join-Path $WorkDir "WPP"
    
    if (Test-Path $repoDir) {
        Write-Info "Repository directory exists, updating..."
        Set-Location $repoDir
        
        if (Test-Path ".git") {
            git fetch origin
            git checkout $Branch
            git pull origin $Branch
            Write-Success "✓ Repository updated to latest $Branch"
        } else {
            Write-Warning "⚠ Directory exists but is not a git repository. Removing and cloning fresh."
            Set-Location $WorkDir
            Remove-Item -Path $repoDir -Recurse -Force
            git clone -b $Branch $CloneUrl
            Set-Location $repoDir
            Write-Success "✓ Repository cloned fresh"
        }
    } else {
        Write-Info "Cloning repository..."
        git clone -b $Branch $CloneUrl
        Set-Location $repoDir
        Write-Success "✓ Repository cloned: $RepoUrl (branch: $Branch)"
    }
    
    # Verify we're in the right directory
    if (-not (Test-Path "pyproject.toml")) {
        throw "Project structure verification failed - pyproject.toml not found"
    }
    
    $currentCommit = git rev-parse --short HEAD
    Write-Info "Current commit: $currentCommit"
    
    # Setup Python environment and dependencies
    Write-Section "Setting Up Python Environment"
    
    Write-Info "Syncing Python environment with uv..."
    # Add FastAPI dependencies
    Write-Info "Adding FastAPI and web dependencies..."
    uv add fastapi uvicorn websockets --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "⚠ Some web dependencies may already be present"
    }
    
    uv sync --dev
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to sync Python environment"
    }
    Write-Success "✓ Python environment ready with web dependencies"
    
    # Run tests (unless skipped)
    if (-not $SkipTests) {
        Write-Section "Running Tests"
        
        Write-Info "Running pytest with coverage..."
        try {
            $env:GPG_PASSPHRASE = $env:GPG_PASSPHRASE
            if (-not $env:GPG_PASSPHRASE) {
                Write-Warning "⚠ GPG_PASSPHRASE not set. Some tests may fail."
            }
            
            uv run pytest tests/ -v --tb=short
            if ($LASTEXITCODE -ne 0) {
                throw "Tests failed"
            }
            Write-Success "✓ All tests passed"
        } catch {
            Write-Error "Tests failed: $($_.Exception.Message)"
            throw "Test execution failed"
        }
    } else {
        Write-Warning "⚠ Tests skipped (SkipTests flag set)"
    }
    
    # Run linting
    Write-Section "Running Code Quality Checks"
    
    Write-Info "Running ruff linting..."
    uv run ruff check src/
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "⚠ Linting issues found, but continuing with build"
    } else {
        Write-Success "✓ Code quality checks passed"
    }
    
    # Build executables
    Write-Section "Building Windows Executables"
    
    if ($ApiOnly) {
        Write-Info "🔧 Building API-only executables (no React frontend)..."
        $buildScript = "build_simple_exe.py"
        $expectedExe = "wpp-web-api.exe"
    } else {
        Write-Info "🌐 Building full web application (React + FastAPI)..."
        $buildScript = "build_web_app.py"
        $expectedExe = "wpp-web-app.exe"
    }
    
    # Check if build script exists
    if (-not (Test-Path $buildScript)) {
        throw "$buildScript not found in repository"
    }
    
    # Execute the build
    try {
        Write-Info "Starting build process with $buildScript..."
        uv run python $buildScript
        if ($LASTEXITCODE -ne 0) {
            throw "Build script failed"
        }
    } catch {
        throw "Failed to execute $buildScript : $($_.Exception.Message)"
    }
    
    # Verify build output
    $distDir = Join-Path $PWD "dist\wpp"
    if (-not (Test-Path $distDir)) {
        throw "Build output directory not found: $distDir"
    }
    
    $executables = @(
        $expectedExe,
        "run-reports.exe", 
        "update-database.exe"
    )
    
    $missingExes = @()
    foreach ($exe in $executables) {
        $exePath = Join-Path $distDir $exe
        if (Test-Path $exePath) {
            $fileSize = (Get-Item $exePath).Length
            Write-Success "✓ $exe created (Size: $([math]::Round($fileSize/1MB, 2)) MB)"
        } else {
            $missingExes += $exe
        }
    }
    
    if ($missingExes.Count -gt 0) {
        Write-Error "Missing executables: $($missingExes -join ', ')"
        throw "Build verification failed - some executables were not created"
    }
    
    # Success summary
    Write-Section "Build Complete!"
    
    Write-Success "✓ Repository: $RepoUrl ($Branch)"
    Write-Success "✓ Commit: $currentCommit"
    Write-Success "✓ Tests: $(if ($SkipTests) { 'Skipped' } else { 'Passed' })"
    Write-Success "✓ Build Type: $(if ($ApiOnly) { 'API-Only' } else { 'Full Web Application' })"
    Write-Success "✓ Build: Success"
    Write-Success "✓ Output: $distDir"
    
    Write-Info "`nAvailable executables:"
    foreach ($exe in $executables) {
        Write-Info "  • $exe"
    }
    
    Write-Info "`nUsage:"
    if ($ApiOnly) {
        Write-Info "  Web API:          .\dist\wpp\wpp-web-api.exe"
        Write-Info "  API Docs:         http://localhost:8000/docs (after starting API)"
    } else {
        Write-Info "  Web Application:  .\dist\wpp\wpp-web-app.exe"
        Write-Info "  Browser Opens:    http://localhost:8000 (automatically)"
        Write-Info "  Full UI:          Modern React interface with real-time updates"
    }
    Write-Info "  Generate Reports: .\dist\wpp\run-reports.exe"
    Write-Info "  Update Database:  .\dist\wpp\update-database.exe"
    
    Write-Info "`nCustomer Experience:"
    if ($ApiOnly) {
        Write-Info "  • API server with Swagger documentation"
        Write-Info "  • REST endpoints for all operations"
        Write-Info "  • No additional installation required"
    } else {
        Write-Info "  • Complete web application with modern UI"
        Write-Info "  • Real-time progress bars and updates"
        Write-Info "  • Interactive data tables and log viewers"
        Write-Info "  • Mobile-friendly responsive design"
        Write-Info "  • No additional installation required (Python/Node.js bundled)"
    }
    
    if (-not $KeepRepo) {
        Write-Section "Cleanup"
        Write-Info "Use -KeepRepo to preserve the repository after build"
        Write-Info "Repository location: $repoDir"
    }
    
    Write-Success "`n🎉 Web Application Build Pipeline Completed Successfully!"
    
} catch {
    Write-Error "`n💥 Build pipeline failed!"
    Write-Error "Error: $($_.Exception.Message)"
    Write-Error "Location: $($_.InvocationInfo.PositionMessage)"
    
    Write-Info "`nTroubleshooting:"
    Write-Info "• Ensure all prerequisites are installed"
    Write-Info "• Check network connectivity for repository access"
    Write-Info "• For Node.js issues, try -ApiOnly flag"
    Write-Info "• Verify PowerShell execution policy: Set-ExecutionPolicy RemoteSigned"
    Write-Info "• Check that uv can access the internet for dependencies"
    
    exit 1
} finally {
    # Reset location
    if (Test-Path $WorkDir) {
        Set-Location $WorkDir
    }
}