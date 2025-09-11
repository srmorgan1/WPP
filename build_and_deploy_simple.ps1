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
    
    # Build Windows installer using Inno Setup
    Write-Host "Building Windows installer..." -ForegroundColor Yellow
    
    if (Test-Path "wpp-installer.iss") {
        # Check if Inno Setup is available
        $innoSetupPath = $null
        $possiblePaths = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
            "ISCC.exe"  # If it's in PATH
        )
        
        foreach ($path in $possiblePaths) {
            if (Test-Path $path -ErrorAction SilentlyContinue) {
                $innoSetupPath = $path
                break
            } elseif ($path -eq "ISCC.exe") {
                # Check if ISCC is in PATH
                try {
                    $null = Get-Command "ISCC" -ErrorAction Stop
                    $innoSetupPath = "ISCC.exe"
                    break
                } catch {
                    continue
                }
            }
        }
        
        if ($innoSetupPath) {
            Write-Host "Using Inno Setup: $innoSetupPath" -ForegroundColor Green
            & $innoSetupPath "wpp-installer.iss"
            if ($LASTEXITCODE -eq 0) {
                if (Test-Path "installer\WPP-Setup.exe") {
                    $installerSize = [math]::Round((Get-Item "installer\WPP-Setup.exe").Length/1MB, 1)
                    Write-Host "Windows installer built successfully: WPP-Setup.exe ($installerSize MB)" -ForegroundColor Green
                    
                    # Move installer to install_files directory (will be created later in the script)
                    $tempInstallerPath = "installer\WPP-Setup.exe"
                    Write-Host "Installer will be moved to install_files directory after zip creation" -ForegroundColor Cyan
                } else {
                    Write-Host "Installer build succeeded but WPP-Setup.exe not found" -ForegroundColor Yellow
                }
            } else {
                Write-Host "Installer build failed with exit code $LASTEXITCODE" -ForegroundColor Yellow
            }
        } else {
            Write-Host "Inno Setup not found - skipping installer build" -ForegroundColor Yellow
            Write-Host "Install Inno Setup from: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
        }
    } else {
        Write-Host "wpp-installer.iss not found - skipping installer build" -ForegroundColor Yellow
    }
    
    # Create Windows deployment zip with wheels
    Write-Host "Creating comprehensive deployment package..." -ForegroundColor Yellow
    
    # Create install_files directory in the script's parent directory
    $installFilesDir = Join-Path $PSScriptRoot "install_files"
    if (-not (Test-Path $installFilesDir)) {
        New-Item -ItemType Directory -Path $installFilesDir -Force | Out-Null
        Write-Host "Created install_files directory: $installFilesDir" -ForegroundColor Green
    }
    
    $distDir = "dist\wpp"
    $deploymentZip = Join-Path $installFilesDir "wpp-windows-deployment.zip"
    
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
        
        # Add Windows installer if it exists
        $installerFile = "installer\WPP-Setup.exe"
        if (Test-Path $installerFile) {
            $zipItems += $installerFile
            $installerSize = [math]::Round((Get-Item $installerFile).Length/1MB, 1)
            Write-Host "  - Including installer: WPP-Setup.exe ($installerSize MB)" -ForegroundColor Cyan
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
                $installerText = if (Test-Path "installer\WPP-Setup.exe") { " + installer" } else { "" }
                Write-Host "Package contents: $($wheelFiles.Count) wheels + executables + dependencies$installerText" -ForegroundColor Green
                
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
                
                # Check if we have both successful build artifacts before cleanup
                $zipSuccessful = Test-Path $deploymentZip
                $installerExists = Test-Path "installer\WPP-Setup.exe"
                $installerSuccessful = $false
                
                # Move installer to install_files directory if it exists
                if ($installerExists) {
                    $installerDestPath = Join-Path $installFilesDir "WPP-Setup.exe"
                    Move-Item "installer\WPP-Setup.exe" $installerDestPath -Force
                    $installerSize = [math]::Round((Get-Item $installerDestPath).Length/1MB, 1)
                    Write-Host "Moved installer to: $installerDestPath ($installerSize MB)" -ForegroundColor Green
                    $installerSuccessful = $true
                }
                
                # Only clean up the wpp-build folder if we have successful build artifacts
                if ($zipSuccessful -and ($installerSuccessful -or -not $installerExists)) {
                    Write-Host "Both zip and installer (if applicable) created successfully - cleaning up temporary build directory" -ForegroundColor Green
                    if (Test-Path $WorkDir) {
                        Write-Host "Removing temporary build directory: $WorkDir" -ForegroundColor Yellow
                        Remove-Item -Path $WorkDir -Recurse -Force -ErrorAction SilentlyContinue
                        if (-not (Test-Path $WorkDir)) {
                            Write-Host "Successfully removed temporary build directory" -ForegroundColor Green
                        } else {
                            Write-Host "Warning: Could not fully remove temporary build directory" -ForegroundColor Yellow
                        }
                    }
                } else {
                    Write-Host "Build artifacts incomplete - keeping temporary build directory for debugging" -ForegroundColor Yellow
                    Write-Host "Zip successful: $zipSuccessful, Installer successful: $installerSuccessful" -ForegroundColor Yellow
                }
                
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
    
    Write-Host "Web application build completed successfully!" -ForegroundColor Green
    
} catch {
    Write-Host "Build failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}