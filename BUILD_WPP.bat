@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM WPP Web Application CI/CD Build Pipeline Launcher  
REM Double-click this file to build React + FastAPI web app from GitHub repository
REM ============================================================================

title WPP Web Application Build Pipeline

echo.
echo ================================================================================
echo                       WPP Web Application Build Pipeline
echo ================================================================================
echo.
echo This script will:
echo   1. Check out the WPP project from GitHub
echo   2. Auto-install uv package manager (if needed)
echo   3. Auto-install Node.js LTS (if needed for React frontend)
echo   4. Auto-download Python 3.13+ (via uv)
echo   5. Set up isolated Python environment and dependencies  
echo   6. Build React frontend for production
echo   7. Run tests to ensure code quality
echo   8. Build standalone Windows executables with React UI
echo.
echo Prerequisites (Fresh Machine):
echo   - Git for Windows (only dependency!)
echo   - Internet connection
echo.
echo Note: Python, Node.js and all packages are automatically managed
echo.
echo OUTPUT: Modern React web application with FastAPI backend
echo   - Full interactive UI with real-time updates
echo   - Mobile-friendly responsive design
echo   - No installation required on target machines
echo.

REM Check if PowerShell is available
where powershell >nul 2>nul
if errorlevel 1 (
    echo ERROR: PowerShell not found!
    echo Please ensure Windows PowerShell is installed.
    pause
    exit /b 1
)

REM Check if the PowerShell script exists
if not exist "build_and_deploy.ps1" (
    echo ERROR: build_and_deploy.ps1 not found!
    echo Please ensure this batch file is in the same directory as build_and_deploy.ps1
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo Starting Web Application Build Pipeline...
echo ================================================================================
echo.

REM Try to run PowerShell script with bypass execution policy
echo Launching PowerShell build script for React + FastAPI web app...
echo.

REM First attempt: Try with RemoteSigned policy (most permissive while still secure)
powershell.exe -ExecutionPolicy RemoteSigned -File "build_and_deploy.ps1" %*

REM Check if the PowerShell script succeeded
if %errorlevel% equ 0 (
    echo.
    echo ================================================================================
    echo                        WEB APPLICATION BUILD SUCCESSFUL!
    echo ================================================================================
    echo.
    echo Your React + FastAPI web application executables are ready in the dist\wpp\ directory.
    echo.
    echo Available executables:
    echo   ^> wpp-web-app.exe      - Modern React web application
    echo   ^> run-reports.exe      - Reports generator  
    echo   ^> update-database.exe  - Database updater
    echo.
    echo Customer Experience:
    echo   ^> Complete web application with modern UI
    echo   ^> Real-time progress bars and updates
    echo   ^> Interactive data tables and log viewers
    echo   ^> Mobile-friendly responsive design
    echo   ^> Browser opens automatically to http://localhost:8000
    echo   ^> No additional installation required (Python/Node.js bundled)
    echo.
    echo You can now copy these executables to any Windows machine
    echo without requiring Python, Node.js, or any runtime to be installed.
    echo.
    goto success_end
)

REM If RemoteSigned failed, try with Bypass (less secure but more permissive)
echo.
echo First attempt failed. Trying with Bypass execution policy...
echo (This is safe for local scripts but less secure)
echo.

powershell.exe -ExecutionPolicy Bypass -File "build_and_deploy.ps1" %*

if %errorlevel% equ 0 (
    echo.
    echo ================================================================================
    echo                        WEB APPLICATION BUILD SUCCESSFUL!
    echo ================================================================================
    echo.
    echo Your React + FastAPI web application executables are ready!
    goto success_end
)

REM If both attempts failed
echo.
echo ================================================================================
echo                        WEB APPLICATION BUILD FAILED!
echo ================================================================================
echo.
echo The PowerShell script encountered an error.
echo.
echo Common solutions:
echo.
echo 1. EXECUTION POLICY ISSUE:
echo    Open PowerShell as Administrator and run:
echo    Set-ExecutionPolicy RemoteSigned -Scope LocalMachine
echo.
echo 2. MISSING PREREQUISITES:
echo    - Install Git for Windows: https://git-scm.com/download/win
echo    - Python is auto-downloaded by uv (no manual install needed)
echo    - Node.js is auto-installed by the script (no manual install needed)
echo.
echo 3. NETWORK ISSUES:
echo    - Check internet connection (for downloading uv, Python, and Node.js)
echo.
echo 4. AUTHENTICATION (for private repos):
echo    Set environment variable: set GIT_TOKEN=ghp_your_github_token
echo.
echo 5. NODE.JS INSTALLATION ISSUES:
echo    Try using the -ApiOnly flag for API-only build:
echo    BUILD_WPP_WEB.bat -ApiOnly
echo.
echo 6. GPG PASSPHRASE (if tests fail):
echo    Set environment variable: set GPG_PASSPHRASE=your_passphrase
echo.
echo For detailed logging, run this command in PowerShell:
echo .\build_and_deploy.ps1 -Verbose
echo.
echo For API-only build (no React frontend):
echo .\build_and_deploy.ps1 -ApiOnly
echo.

:error_end
echo Press any key to exit...
pause >nul
exit /b 1

:success_end
echo Press any key to exit...
pause >nul
exit /b 0