# PowerShell CI/CD Script for WPP Project
# Checks out project from GitHub, runs tests, and builds Windows executables
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
    [switch]$KeepRepo
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

try {
    Write-Section "WPP CI/CD Build Pipeline Starting"
    
    # Check prerequisites
    Write-Section "Checking Prerequisites"
    
    # Check Git
    if (-not (Test-Command "git")) {
        throw "Git is not installed or not in PATH. Please install Git for Windows."
    }
    Write-Success "[OK] Git found: $(git --version)"
    
    # Setup uv package manager (will handle Python automatically)
    if (-not (Test-Command "uv")) {
        Write-Info "uv package manager not found. Installing uv..."
        Write-Info "Note: uv will automatically download Python 3.13+ as needed for this project"
        try {
            # Install uv using the official installer (standalone binary)
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
    Write-Success "[OK] uv found: $uvVersion"
    Write-Info "uv will automatically manage Python 3.13+ based on pyproject.toml requirements"
    
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
    Write-Success "[OK] Working directory ready: $WorkDir"
    
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
        
        # Check if it's a valid git repository
        if (Test-Path ".git") {
            git fetch origin
            git checkout $Branch
            git pull origin $Branch
            Write-Success "[OK] Repository updated to latest $Branch"
        } else {
            Write-Warning "[WARN] Directory exists but is not a git repository. Removing and cloning fresh."
            Set-Location $WorkDir
            Remove-Item -Path $repoDir -Recurse -Force
            git clone -b $Branch $CloneUrl
            Set-Location $repoDir
            Write-Success "[OK] Repository cloned fresh"
        }
    } else {
        Write-Info "Cloning repository..."
        git clone -b $Branch $CloneUrl
        Set-Location $repoDir
        Write-Success "[OK] Repository cloned: $RepoUrl (branch: $Branch)"
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
    uv sync --dev
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to sync Python environment"
    }
    Write-Success "[OK] Python environment ready"
    
    # Run tests (unless skipped)
    if (-not $SkipTests) {
        Write-Section "Running Tests"
        
        Write-Info "Running pytest with coverage..."
        try {
            # Set GPG_PASSPHRASE for tests (you may need to set this appropriately)
            $env:GPG_PASSPHRASE = $env:GPG_PASSPHRASE
            if (-not $env:GPG_PASSPHRASE) {
                Write-Warning "[WARN] GPG_PASSPHRASE not set. Some tests may fail."
                Write-Info "Please set the GPG_PASSPHRASE environment variable if needed."
            }
            
            uv run pytest tests/ -v --tb=short
            if ($LASTEXITCODE -ne 0) {
                throw "Tests failed"
            }
            Write-Success "[OK] All tests passed"
        } catch {
            Write-Error "Tests failed: $($_.Exception.Message)"
            throw "Test execution failed"
        }
    } else {
        Write-Warning "[WARN] Tests skipped (SkipTests flag set)"
    }
    
    # Run linting
    Write-Section "Running Code Quality Checks"
    
    Write-Info "Running ruff linting..."
    uv run ruff check src/
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "[WARN] Linting issues found, but continuing with build"
    } else {
        Write-Success "[OK] Code quality checks passed"
    }
    
    # Build executables
    Write-Section "Building Windows Executables"
    
    Write-Info "Starting executable build process..."
    
    # Check if build_executable.ps1 exists
    if (-not (Test-Path "build_executable.ps1")) {
        throw "build_executable.ps1 not found in repository"
    }
    
    # Execute the build script
    try {
        & .\build_executable.ps1
        if ($LASTEXITCODE -ne 0) {
            throw "Build executable script failed"
        }
    } catch {
        throw "Failed to execute build_executable.ps1: $($_.Exception.Message)"
    }
    
    # Verify build output
    $distDir = Join-Path $PWD "dist\wpp"
    if (-not (Test-Path $distDir)) {
        throw "Build output directory not found: $distDir"
    }
    
    $executables = @(
        "wpp-web-app.exe",
        "run-reports.exe", 
        "update-database.exe"
    )
    
    $missingExes = @()
    foreach ($exe in $executables) {
        $exePath = Join-Path $distDir $exe
        if (Test-Path $exePath) {
            $fileSize = (Get-Item $exePath).Length
            Write-Success "[OK] $exe created (Size: $([math]::Round($fileSize/1MB, 2)) MB)"
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
    
    Write-Success "[OK] Repository: $RepoUrl ($Branch)"
    Write-Success "[OK] Commit: $currentCommit"
    Write-Success "[OK] Tests: $(if ($SkipTests) { 'Skipped' } else { 'Passed' })"
    Write-Success "[OK] Build: Success"
    Write-Success "[OK] Output: $distDir"
    
    Write-Info "`nAvailable executables:"
    foreach ($exe in $executables) {
        Write-Info "  - $exe"
    }
    
    Write-Info "`nUsage:"
    Write-Info "  Web App:        .\dist\wpp\wpp-web-app.exe"
    Write-Info "  Generate Reports: .\dist\wpp\run-reports.exe"
    Write-Info "  Update Database:  .\dist\wpp\update-database.exe"
    
    if (-not $KeepRepo) {
        Write-Section "Cleanup"
        Write-Info "Use -KeepRepo to preserve the repository after build"
        Write-Info "Repository location: $repoDir"
    }
    
    Write-Success "`n[SUCCESS] Build pipeline completed successfully!"
    
} catch {
    Write-Error "`n[FAILED] Build pipeline failed!"
    Write-Error "Error: $($_.Exception.Message)"
    Write-Error "Location: $($_.InvocationInfo.PositionMessage)"
    
    Write-Info "`nTroubleshooting:"
    Write-Info "- Ensure all prerequisites are installed"
    Write-Info "- Check network connectivity for repository access"
    Write-Info "- Verify GPG_PASSPHRASE is set if tests require encrypted data"
    Write-Info "- Check PowerShell execution policy: Set-ExecutionPolicy RemoteSigned"
    
    exit 1
} finally {
    # Reset location
    if (Test-Path $WorkDir) {
        Set-Location $WorkDir
    }
}