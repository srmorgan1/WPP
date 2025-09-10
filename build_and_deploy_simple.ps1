param(
    [string]$RepoUrl = "https://github.com/srmorgan1/WPP.git",
    [string]$Branch = "master", 
    [string]$WorkDir = (Join-Path $PSScriptRoot "wpp-build"),
    [switch]$SkipTests,
    [switch]$ApiOnly
)

$ErrorActionPreference = "Stop"

# Function to prompt for build directory cleanup with timeout
function Prompt-BuildCleanup {
    param(
        [string]$WorkDir,
        [int]$TimeoutSeconds = 10
    )
    
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "Build Directory Cleanup" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
    Write-Host "Build completed successfully!" -ForegroundColor Green
    Write-Host "Build directory: $WorkDir" -ForegroundColor White
    Write-Host ""
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
        Write-Host "Removing build directory: $WorkDir" -ForegroundColor Yellow
        try {
            if (Test-Path $WorkDir) {
                Remove-Item -Path $WorkDir -Recurse -Force
                Write-Host "[OK] Build directory cleaned up" -ForegroundColor Green
            }
        } catch {
            Write-Host "[WARN] Could not remove build directory: $($_.Exception.Message)" -ForegroundColor Yellow
            Write-Host "You may need to manually delete: $WorkDir" -ForegroundColor White
        }
    } else {
        Write-Host "Build directory preserved: $WorkDir" -ForegroundColor White
    }
}

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
    
    # Run tests (unless skipped)
    if (-not $SkipTests) {
        Write-Host "Running Tests..." -ForegroundColor Yellow
        
        Write-Host "Running pytest with coverage..." -ForegroundColor Yellow
        try {
            $env:GPG_PASSPHRASE = $env:GPG_PASSPHRASE
            if (-not $env:GPG_PASSPHRASE) {
                Write-Host "GPG_PASSPHRASE not set. Some tests may fail." -ForegroundColor Yellow
            }
            
            uv run pytest tests/ -v --tb=short
            if ($LASTEXITCODE -ne 0) {
                throw "Tests failed"
            }
            Write-Host "All tests passed" -ForegroundColor Green
        } catch {
            Write-Host "Tests failed: $($_.Exception.Message)" -ForegroundColor Red
            throw "Test execution failed"
        }
    } else {
        Write-Host "Tests skipped (SkipTests flag set)" -ForegroundColor Yellow
    }
    
    # Run linting (same as simple_build.ps1)
    Write-Host "Running linting..." -ForegroundColor Yellow
    uv run ruff check src/
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Linting issues found, continuing" -ForegroundColor Yellow
    }
    
    # Build Python wheel
    Write-Host "Building Python wheel..." -ForegroundColor Yellow
    try {
        uv build --wheel
        if ($LASTEXITCODE -ne 0) {
            throw "Wheel build failed"
        }
        
        # Verify wheel was created
        $wheelFiles = Get-ChildItem -Path "dist" -Filter "*.whl" -ErrorAction SilentlyContinue
        if ($wheelFiles.Count -eq 0) {
            Write-Host "Warning: No wheel files found in dist/" -ForegroundColor Yellow
        } else {
            foreach ($wheel in $wheelFiles) {
                $wheelSize = [math]::Round($wheel.Length/1MB, 2)
                Write-Host "Wheel created: $($wheel.Name) ($wheelSize MB)" -ForegroundColor Green
            }
        }
    } catch {
        Write-Host "Warning: Wheel build failed: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "Continuing with executable build..." -ForegroundColor Yellow
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
    
    # Look for build scripts in the checked-out repo directory (wpp-build/WPP)
    if (Test-Path "build_executable.ps1") {
        & .\build_executable.ps1
        if ($LASTEXITCODE -ne 0) {
            throw "Build failed"
        }
    } elseif (Test-Path "build_web_app.py") {
        Write-Host "Using build_web_app.py from checked-out repo" -ForegroundColor Yellow
        uv run python build_web_app.py
        if ($LASTEXITCODE -ne 0) {
            throw "build_web_app.py failed"
        }
    } elseif (Test-Path "build_executable.py") {
        Write-Host "Using build_executable.py from checked-out repo" -ForegroundColor Yellow
        uv run python build_executable.py
        if ($LASTEXITCODE -ne 0) {
            throw "build_executable.py failed"
        }
    } else {
        Write-Host "No build script found, skipping executable build" -ForegroundColor Yellow
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
                Write-Host "Inno Setup found: $path" -ForegroundColor Green
                return $path
            }
        }
        
        Write-Host "Inno Setup not found. Downloading and installing..." -ForegroundColor Yellow
        
        try {
            # Download Inno Setup installer
            $innoUrl = "https://jrsoftware.org/download.php/is.exe"
            $innoInstaller = Join-Path $env:TEMP "innosetup-installer.exe"
            
            Write-Host "Downloading Inno Setup..." -ForegroundColor Yellow
            Invoke-WebRequest -Uri $innoUrl -OutFile $innoInstaller -UseBasicParsing
            
            Write-Host "Installing Inno Setup (silent install)..." -ForegroundColor Yellow
            Start-Process -FilePath $innoInstaller -ArgumentList "/VERYSILENT", "/NORESTART" -Wait
            
            # Check again for installation
            foreach ($path in $innoSetupPaths) {
                if (Test-Path $path) {
                    Write-Host "Inno Setup installed successfully: $path" -ForegroundColor Green
                    return $path
                }
            }
            
            throw "Inno Setup installation verification failed"
            
        } catch {
            Write-Host "Failed to install Inno Setup automatically: $($_.Exception.Message)" -ForegroundColor Yellow
            Write-Host "Please install Inno Setup manually from https://jrsoftware.org/isinfo.php" -ForegroundColor Yellow
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
            [string]$ScriptPath = "wpp-installer.iss"
        )
        
        Write-Host "Creating Windows installer using Inno Setup..." -ForegroundColor Yellow
        
        # Ensure Inno Setup is available
        $innoPath = Ensure-InnoSetup
        if (-not $innoPath) {
            Write-Host "Skipping installer creation - Inno Setup not available" -ForegroundColor Yellow
            return $false
        }
        
        # Check if the Inno Setup script exists
        if (-not (Test-Path $ScriptPath)) {
            Write-Host "Inno Setup script not found: $ScriptPath" -ForegroundColor Red
            return $false
        }
        
        try {
            # Create installer directory if it doesn't exist
            $installerDir = "installer"
            if (-not (Test-Path $installerDir)) {
                New-Item -Path $installerDir -ItemType Directory -Force | Out-Null
            }
            
            Write-Host "Compiling installer with Inno Setup..." -ForegroundColor Yellow
            
            # Run Inno Setup compiler
            $process = Start-Process -FilePath $innoPath -ArgumentList $ScriptPath, "/Q" -Wait -PassThru -NoNewWindow
            
            if ($process.ExitCode -eq 0) {
                # Find the created installer
                $installerFile = Get-ChildItem -Path $installerDir -Filter "WPP-Setup.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($installerFile) {
                    $installerSize = [math]::Round($installerFile.Length/1MB, 1)
                    Write-Host "Windows installer created: $($installerFile.FullName) ($installerSize MB)" -ForegroundColor Green
                    return $true
                } else {
                    Write-Host "Installer compilation succeeded but output file not found" -ForegroundColor Yellow
                    return $false
                }
            } else {
                Write-Host "Inno Setup compiler failed with exit code: $($process.ExitCode)" -ForegroundColor Red
                return $false
            }
            
        } catch {
            Write-Host "Failed to create Windows installer: $($_.Exception.Message)" -ForegroundColor Red
            return $false
        }
    }

    # Create Windows deployment zip with wheels
    Write-Host "Creating comprehensive deployment package..." -ForegroundColor Yellow
    
    $distDir = "dist\wpp"
    # Save zip file in the same directory as the script itself  
    $scriptDir = Split-Path -Parent $PSCommandPath
    $deploymentZip = Join-Path $scriptDir "wpp-windows-deployment.zip"
    
    try {
        # Remove existing zip if present
        if (Test-Path $deploymentZip) {
            Remove-Item $deploymentZip -Force
            Write-Host "Removed existing deployment package" -ForegroundColor Yellow
        }
        
        # Collect all deployment items
        $zipItems = @()
        
        # Add wheel files from dist/ directory
        $wheelFiles = Get-ChildItem -Path "dist" -Filter "*.whl" -ErrorAction SilentlyContinue
        foreach ($wheel in $wheelFiles) {
            $zipItems += $wheel.FullName
            Write-Host "  - Including wheel: $($wheel.Name)" -ForegroundColor Cyan
        }
        
        # Check if build output exists and add executables
        if (Test-Path $distDir) {
            # Add _internal directory if it exists
            $internalDir = Join-Path $distDir "_internal"
            if (Test-Path $internalDir) {
                $zipItems += $internalDir
                Write-Host "  - Including dependencies: _internal/" -ForegroundColor Cyan
            }
            
            # Add executables if they exist
            $executables = @("wpp-web-app.exe", "run-reports.exe", "update-database.exe", "wpp-web-api.exe")
            foreach ($exe in $executables) {
                $exePath = Join-Path $distDir $exe
                if (Test-Path $exePath) {
                    $zipItems += $exePath
                    Write-Host "  - Including executable: $exe" -ForegroundColor Cyan
                }
            }
        } else {
            Write-Host "Warning: Build output directory not found: $distDir" -ForegroundColor Yellow
        }
        
        if ($zipItems.Count -gt 0) {
            # Create the zip file with maximum compression
            Write-Host "Compressing $($zipItems.Count) items with maximum compression..." -ForegroundColor Yellow
            Compress-Archive -Path $zipItems -DestinationPath $deploymentZip -CompressionLevel Optimal
            
            if (Test-Path $deploymentZip) {
                $zipSize = (Get-Item $deploymentZip).Length
                Write-Host "Deployment package created: $deploymentZip ($([math]::Round($zipSize/1MB, 1)) MB)" -ForegroundColor Green
                Write-Host "Package contents: $($wheelFiles.Count) wheels + executables + dependencies" -ForegroundColor Green
                
                # Clean up intermediate build files after successful zip creation
                Write-Host "Cleaning up intermediate build files..." -ForegroundColor Yellow
                
                $cleanupItems = @("build", ".pytest_cache", "web/node_modules", "web/.cache")
                $cleanedCount = 0
                
                foreach ($item in $cleanupItems) {
                    if (Test-Path $item) {
                        Remove-Item -Path $item -Recurse -Force -ErrorAction SilentlyContinue
                        if (-not (Test-Path $item)) {
                            $cleanedCount++
                            Write-Host "  - Cleaned: $item" -ForegroundColor DarkGreen
                        }
                    }
                }
                
                # Clean Python cache files
                Get-ChildItem -Path . -Name "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue | ForEach-Object {
                    Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
                }
                
                Get-ChildItem -Path . -Name "*.pyc" -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
                    Remove-Item -Path $_.FullName -Force -ErrorAction SilentlyContinue
                }
                
                Write-Host "Cleanup completed: $cleanedCount directories removed" -ForegroundColor Green
                
            } else {
                Write-Host "Warning: Zip creation may have failed" -ForegroundColor Yellow
            }
        } else {
            Write-Host "Warning: No items found to package" -ForegroundColor Yellow
        }
        
    } catch {
        Write-Host "Warning: Failed to create deployment package: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "Deployment files are still available in: $distDir" -ForegroundColor Yellow
    }
    
    # Create Windows installer
    Write-Host "`nCreating Windows installer..." -ForegroundColor Yellow
    $installerCreated = New-WindowsInstaller -ScriptPath "wpp-installer.iss"
    
    Write-Host "Web application build completed successfully!" -ForegroundColor Green
    
    if ($installerCreated -and (Test-Path "installer\WPP-Setup.exe")) {
        Write-Host "Windows installer available: installer\WPP-Setup.exe" -ForegroundColor Green
    }
    
    # Prompt for cleanup of build directory
    Prompt-BuildCleanup -WorkDir $WorkDir
    
} catch {
    Write-Host "Build failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}