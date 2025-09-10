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

# Function to check if Inno Setup is available and install if needed
function Ensure-InnoSetup {
    # Check if Inno Setup is already installed
    $innoSetupPaths = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 5\ISCC.exe"
    )
    
    foreach ($path in $innoSetupPaths) {
        if (Test-Path $path) {
            Write-Success "[OK] Inno Setup found: $path"
            return $path
        }
    }
    
    Write-Warning "[WARN] Inno Setup not found. Downloading and installing..."
    
    try {
        # Download Inno Setup installer
        $innoUrl = "https://jrsoftware.org/download.php/is.exe"
        $innoInstaller = Join-Path $env:TEMP "innosetup-installer.exe"
        
        Write-Info "Downloading Inno Setup from $innoUrl..."
        Invoke-WebRequest -Uri $innoUrl -OutFile $innoInstaller -UseBasicParsing
        
        Write-Info "Installing Inno Setup (silent install)..."
        Start-Process -FilePath $innoInstaller -ArgumentList "/VERYSILENT", "/NORESTART" -Wait
        
        # Check again for installation
        foreach ($path in $innoSetupPaths) {
            if (Test-Path $path) {
                Write-Success "[OK] Inno Setup installed successfully: $path"
                return $path
            }
        }
        
        throw "Inno Setup installation verification failed"
        
    } catch {
        Write-Warning "[WARN] Failed to install Inno Setup automatically: $($_.Exception.Message)"
        Write-Info "Please install Inno Setup manually from https://jrsoftware.org/isinfo.php"
        return $null
    } finally {
        if (Test-Path $innoInstaller) {
            Remove-Item $innoInstaller -Force -ErrorAction SilentlyContinue
        }
    }
}

# Function to create Windows installer using Inno Setup
function New-WindowsInstaller {
    param(
        [string]$DistDir,
        [string]$ScriptPath = "wpp-installer.iss"
    )
    
    Write-Info "Creating Windows installer using Inno Setup..."
    
    # Ensure Inno Setup is available
    $innoPath = Ensure-InnoSetup
    if (-not $innoPath) {
        Write-Warning "[WARN] Skipping installer creation - Inno Setup not available"
        return $false
    }
    
    # Check if the Inno Setup script exists
    if (-not (Test-Path $ScriptPath)) {
        Write-Error "[ERROR] Inno Setup script not found: $ScriptPath"
        return $false
    }
    
    try {
        # Create installer directory if it doesn't exist
        $installerDir = "installer"
        if (-not (Test-Path $installerDir)) {
            New-Item -Path $installerDir -ItemType Directory -Force | Out-Null
        }
        
        Write-Info "Compiling installer with Inno Setup..."
        Write-Info "Script: $ScriptPath"
        Write-Info "Source: $DistDir"
        
        # Run Inno Setup compiler
        $isccArgs = @(
            $ScriptPath,
            "/Q"  # Quiet mode
        )
        
        $process = Start-Process -FilePath $innoPath -ArgumentList $isccArgs -Wait -PassThru -NoNewWindow
        
        if ($process.ExitCode -eq 0) {
            # Find the created installer
            $installerFile = Get-ChildItem -Path $installerDir -Filter "WPP-Setup.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($installerFile) {
                $installerSize = [math]::Round($installerFile.Length/1MB, 1)
                Write-Success "[OK] Windows installer created: $($installerFile.FullName) ($installerSize MB)"
                return $true
            } else {
                Write-Warning "[WARN] Installer compilation succeeded but output file not found"
                return $false
            }
        } else {
            Write-Error "[ERROR] Inno Setup compiler failed with exit code: $($process.ExitCode)"
            return $false
        }
        
    } catch {
        Write-Error "[ERROR] Failed to create Windows installer: $($_.Exception.Message)"
        return $false
    }
}

# Function to create Windows deployment zip package with wheels
function New-DeploymentPackage {
    param(
        [string]$DistDir,
        [string]$ExpectedExe,
        [string]$DeploymentZipName = "wpp-windows-deployment.zip"
    )
    
    Write-Info "Creating comprehensive deployment package: $DeploymentZipName"
    
    try {
        # Save zip file in the same directory as the script itself
        $scriptDir = Split-Path -Parent $PSCommandPath
        $deploymentPath = Join-Path $scriptDir $DeploymentZipName
        
        # Remove existing zip if present
        if (Test-Path $deploymentPath) {
            Remove-Item $deploymentPath -Force
            Write-Info "Removed existing deployment package"
        }
        
        # Collect all deployment items
        $zipItems = @()
        
        # Add wheel files from dist/ directory
        $wheelFiles = Get-ChildItem -Path "dist" -Filter "*.whl" -ErrorAction SilentlyContinue
        foreach ($wheel in $wheelFiles) {
            $zipItems += $wheel.FullName
            Write-Info "  - Including wheel: $($wheel.Name)"
        }
        
        # Add executables and _internal directory
        $exeItems = @(
            Join-Path $DistDir "_internal",
            Join-Path $DistDir $ExpectedExe,
            Join-Path $DistDir "run-reports.exe", 
            Join-Path $DistDir "update-database.exe"
        )
        
        foreach ($item in $exeItems) {
            if (Test-Path $item) {
                $zipItems += $item
                $itemName = Split-Path $item -Leaf
                if ($itemName -eq "_internal") {
                    Write-Info "  - Including dependencies: _internal/"
                } else {
                    Write-Info "  - Including executable: $itemName"
                }
            }
        }
        
        # Check if we have items to zip
        if ($zipItems.Count -eq 0) {
            throw "No items found to include in deployment package"
        }
        
        # Create the zip file with maximum compression
        Write-Info "Compressing $($zipItems.Count) items with maximum compression..."
        Compress-Archive -Path $zipItems -DestinationPath $deploymentPath -CompressionLevel Optimal
        
        if (Test-Path $deploymentPath) {
            $zipSize = (Get-Item $deploymentPath).Length
            Write-Success "[OK] Deployment package created: $DeploymentZipName ($([math]::Round($zipSize/1MB, 1)) MB)"
            Write-Info "Package contents:"
            Write-Info "  - Python wheels: $($wheelFiles.Count) files"
            Write-Info "  - Executables: $(($zipItems | Where-Object { $_ -like '*.exe' }).Count) files"
            Write-Info "  - Dependencies: _internal directory"
            return $true
        } else {
            throw "Zip creation failed - file not found after compression"
        }
        
    } catch {
        Write-Warning "[WARN] Failed to create deployment package: $($_.Exception.Message)"
        Write-Info "Deployment files are still available in: $DistDir"
        return $false
    }
}

# Function to build Python wheel distribution
function New-PythonWheel {
    Write-Info "Building wheel distribution..."
    
    try {
        uv build --wheel
        if ($LASTEXITCODE -ne 0) {
            throw "Wheel build failed"
        }
        
        # Verify wheel was created
        $wheelFiles = Get-ChildItem -Path "dist" -Filter "*.whl" -ErrorAction SilentlyContinue
        if ($wheelFiles.Count -eq 0) {
            throw "No wheel files found in dist/ after build"
        }
        
        foreach ($wheel in $wheelFiles) {
            $wheelSize = [math]::Round($wheel.Length/1MB, 2)
            Write-Success "[OK] Wheel created: $($wheel.Name) (Size: ${wheelSize} MB)"
        }
        
        return $true
        
    } catch {
        Write-Error "Failed to build wheel: $($_.Exception.Message)"
        return $false
    }
}

# Function to clean up intermediate build files after successful build
function Remove-IntermediateBuildFiles {
    Write-Info "Cleaning up intermediate build files..."
    
    try {
        # Clean up common build artifacts while preserving the final deployment
        $cleanupItems = @(
            "build",
            ".pytest_cache",
            "web/node_modules",
            "web/.cache",
            "src/*.egg-info"
        )
        
        $cleanedCount = 0
        foreach ($item in $cleanupItems) {
            if (Test-Path $item) {
                $itemSize = 0
                if (Test-Path $item -PathType Container) {
                    $itemSize = (Get-ChildItem -Path $item -Recurse -File | Measure-Object -Property Length -Sum).Sum
                }
                
                Remove-Item -Path $item -Recurse -Force -ErrorAction SilentlyContinue
                
                if (-not (Test-Path $item)) {
                    $cleanedCount++
                    $sizeMB = [math]::Round($itemSize / 1MB, 1)
                    Write-Info "  - Cleaned: $item ($sizeMB MB)"
                }
            }
        }
        
        # Clean Python cache files
        $pycacheFiles = Get-ChildItem -Path . -Name "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue
        foreach ($cache in $pycacheFiles) {
            Remove-Item -Path $cache.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }
        
        # Clean .pyc files
        $pycFiles = Get-ChildItem -Path . -Name "*.pyc" -Recurse -File -ErrorAction SilentlyContinue
        foreach ($pyc in $pycFiles) {
            Remove-Item -Path $pyc.FullName -Force -ErrorAction SilentlyContinue
        }
        
        Write-Success "[OK] Cleanup completed: $cleanedCount directories removed"
        
    } catch {
        Write-Warning "[WARN] Some cleanup operations failed: $($_.Exception.Message)"
        Write-Info "This doesn't affect the build results"
    }
}

# Function to prompt for build directory cleanup with timeout
function Prompt-BuildCleanup {
    param(
        [string]$WorkDir,
        [int]$TimeoutSeconds = 10
    )
    
    Write-Section "Build Directory Cleanup"
    Write-Info "Build completed successfully!"
    Write-Info "Build directory: $WorkDir"
    Write-Info ""
    Write-Host "Delete build directory and temporary files? [Y/n] (default: Y, timeout: ${TimeoutSeconds}s): " -NoNewline -ForegroundColor Yellow
    
    # Use ReadKey with timeout
    $timeout = New-TimeSpan -Seconds $TimeoutSeconds
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $response = ""
    
    while ($stopwatch.Elapsed -lt $timeout -and $response -eq "") {
        if ([Console]::KeyAvailable) {
            $key = [Console]::ReadKey($true)
            if ($key.Key -eq "Enter") {
                $response = "Y"  # Default to Yes on Enter
                break
            } elseif ($key.KeyChar -match "[YyNn]") {
                $response = $key.KeyChar.ToString().ToUpper()
                Write-Host $response
                break
            }
        }
        Start-Sleep -Milliseconds 100
    }
    
    $stopwatch.Stop()
    
    # If no response within timeout, use default
    if ($response -eq "") {
        $response = "Y"
        Write-Host "Y (timeout - using default)"
    }
    
    if ($response -eq "Y") {
        Write-Info "Removing build directory: $WorkDir"
        try {
            if (Test-Path $WorkDir) {
                Remove-Item -Path $WorkDir -Recurse -Force
                Write-Success "[OK] Build directory cleaned up"
            }
        } catch {
            Write-Warning "[WARN] Could not remove build directory: $($_.Exception.Message)"
            Write-Info "You may need to manually delete: $WorkDir"
        }
    } else {
        Write-Info "Build directory preserved: $WorkDir"
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
            Write-Success "[OK] Node.js installed: $nodeVersion"
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
        Write-Info "[CONFIG] API-Only Mode: Building without React frontend"
    } else {
        Write-Info "[WEB] Full Web Mode: Building with React frontend + API backend"
    }
    
    # Check prerequisites
    Write-Section "Checking Prerequisites"
    
    # Check Git
    if (-not (Test-Command "git")) {
        throw "Git is not installed or not in PATH. Please install Git for Windows."
    }
    Write-Success "[OK] Git found: $(git --version)"
    
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
    Write-Success "[OK] uv found: $uvVersion"
    
    # Check/Install Node.js (unless API-only or explicitly skipped)
    if (-not $ApiOnly -and -not $SkipNodeInstall) {
        if (-not (Test-Command "node")) {
            Write-Warning "[WARN] Node.js not found. Installing Node.js for React frontend build..."
            if (-not (Install-NodeJS)) {
                Write-Error "[ERROR] Failed to install Node.js automatically."
                Write-Info "Options:"
                Write-Info "  1. Install Node.js manually from https://nodejs.org/"
                Write-Info "  2. Use -ApiOnly flag to build without React frontend"
                Write-Info "  3. Use -SkipNodeInstall and handle Node.js installation separately"
                throw "Node.js installation failed"
            }
        } else {
            $nodeVersion = node --version
            $npmVersion = npm --version
            Write-Success "[OK] Node.js found: $nodeVersion"
            Write-Success "[OK] npm found: $npmVersion"
        }
    } elseif ($ApiOnly) {
        Write-Info "[CONFIG] Skipping Node.js check (API-only mode)"
    } else {
        Write-Info "[CONFIG] Skipping Node.js installation (SkipNodeInstall flag set)"
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
    # Add FastAPI dependencies
    Write-Info "Adding FastAPI and web dependencies..."
    uv add fastapi uvicorn websockets --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "[WARN] Some web dependencies may already be present"
    }
    
    uv sync --dev
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to sync Python environment"
    }
    Write-Success "[OK] Python environment ready with web dependencies"
    
    # Run tests (unless skipped)
    if (-not $SkipTests) {
        Write-Section "Running Tests"
        
        Write-Info "Running pytest with coverage..."
        try {
            $env:GPG_PASSPHRASE = $env:GPG_PASSPHRASE
            if (-not $env:GPG_PASSPHRASE) {
                Write-Warning "[WARN] GPG_PASSPHRASE not set. Some tests may fail."
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
    
    # Build Python wheel
    Write-Section "Building Python Wheel"
    
    if (-not (New-PythonWheel)) {
        throw "Python wheel build failed"
    }

    # Build executables
    Write-Section "Building Windows Executables"
    
    if ($ApiOnly) {
        Write-Info "[CONFIG] Building API-only executables (no React frontend)..."
        $buildScript = "build_simple_exe.py"
        $expectedExe = "wpp-web-api.exe"
    } else {
        Write-Info "[WEB] Building full web application (React + FastAPI)..."
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
            Write-Success "[OK] $exe created (Size: $([math]::Round($fileSize/1MB, 2)) MB)"
        } else {
            $missingExes += $exe
        }
    }
    
    if ($missingExes.Count -gt 0) {
        Write-Error "Missing executables: $($missingExes -join ', ')"
        throw "Build verification failed - some executables were not created"
    }
    
    # Create Windows deployment zip
    Write-Section "Creating Windows Deployment Package"
    
    $deploymentZip = "wpp-windows-deployment.zip"
    $zipCreated = New-DeploymentPackage -DistDir $distDir -ExpectedExe $expectedExe -DeploymentZipName $deploymentZip
    
    # Create Windows installer
    Write-Section "Creating Windows Installer"
    $installerCreated = New-WindowsInstaller -DistDir $distDir -ScriptPath "wpp-installer.iss"
    
    # Clean up intermediate build files if deployment package was created successfully
    if ($zipCreated) {
        Write-Section "Cleaning Up Build Artifacts"
        Remove-IntermediateBuildFiles
    }
    
    # Success summary
    Write-Section "Build Complete!"
    
    Write-Success "[OK] Repository: $RepoUrl ($Branch)"
    Write-Success "[OK] Commit: $currentCommit"
    Write-Success "[OK] Tests: $(if ($SkipTests) { 'Skipped' } else { 'Passed' })"
    Write-Success "[OK] Build Type: $(if ($ApiOnly) { 'API-Only' } else { 'Full Web Application' })"
    Write-Success "[OK] Build: Success"
    Write-Success "[OK] Output: $distDir"
    if (Test-Path (Join-Path $PWD $deploymentZip)) {
        Write-Success "[OK] Deployment Package: $deploymentZip"
    }
    if ($installerCreated -and (Test-Path "installer\WPP-Setup.exe")) {
        Write-Success "[OK] Windows Installer: installer\WPP-Setup.exe"
    }
    
    Write-Info "`nAvailable executables:"
    foreach ($exe in $executables) {
        Write-Info "  - $exe"
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
        Write-Info "  - API server with Swagger documentation"
        Write-Info "  - REST endpoints for all operations"
        Write-Info "  - No additional installation required"
    } else {
        Write-Info "  - Complete web application with modern UI"
        Write-Info "  - Real-time progress bars and updates"
        Write-Info "  - Interactive data tables and log viewers"
        Write-Info "  - Mobile-friendly responsive design"
        Write-Info "  - No additional installation required (Python/Node.js bundled)"
    }
    
    if (-not $KeepRepo) {
        Write-Section "Cleanup"
        Write-Info "Use -KeepRepo to preserve the repository after build"
        Write-Info "Repository location: $repoDir"
    }
    
    Write-Success "`n[SUCCESS] Web Application Build Pipeline Completed Successfully!"
    
    # Prompt for cleanup of build directory
    Prompt-BuildCleanup -WorkDir $WorkDir
    
} catch {
    Write-Error "`n[FAILED] Build pipeline failed!"
    Write-Error "Error: $($_.Exception.Message)"
    Write-Error "Location: $($_.InvocationInfo.PositionMessage)"
    
    Write-Info "`nTroubleshooting:"
    Write-Info "- Ensure all prerequisites are installed"
    Write-Info "- Check network connectivity for repository access"
    Write-Info "- For Node.js issues, try -ApiOnly flag"
    Write-Info "- Verify PowerShell execution policy: Set-ExecutionPolicy RemoteSigned"
    Write-Info "- Check that uv can access the internet for dependencies"
    
    exit 1
} finally {
    # Reset location
    if (Test-Path $WorkDir) {
        Set-Location $WorkDir
    }
}