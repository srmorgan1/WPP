@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM WPP CI/CD Build Pipeline Launcher
REM Double-click this file to build Windows executables from GitHub repository
REM ============================================================================

title WPP Build Pipeline

echo.
echo ================================================================================
echo                           WPP CI/CD Build Pipeline
echo ================================================================================
echo.
echo This script will:
echo   1. Check out the WPP project from GitHub
echo   2. Set up Python environment and dependencies  
echo   3. Run tests to ensure code quality
echo   4. Build standalone Windows executables
echo.
echo Prerequisites:
echo   - Git for Windows
echo   - Python 3.13+
echo   - Internet connection
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

echo Press any key to start the build process, or Ctrl+C to cancel...
pause >nul

echo.
echo ================================================================================
echo Starting Build Pipeline...
echo ================================================================================
echo.

REM Try to run PowerShell script with bypass execution policy
echo Launching PowerShell build script...
echo.

REM First attempt: Try with RemoteSigned policy (most permissive while still secure)
powershell.exe -ExecutionPolicy RemoteSigned -File "build_and_deploy.ps1" %*

REM Check if the PowerShell script succeeded
if %errorlevel% equ 0 (
    echo.
    echo ================================================================================
    echo                              BUILD SUCCESSFUL!
    echo ================================================================================
    echo.
    echo Your Windows executables are ready in the dist\wpp\ directory.
    echo.
    echo Available executables:
    echo   ^> wpp-streamlit.exe    - Web application
    echo   ^> run-reports.exe      - Reports generator
    echo   ^> update-database.exe  - Database updater
    echo.
    echo You can now copy these executables to any Windows machine
    echo without requiring Python to be installed.
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
    echo                              BUILD SUCCESSFUL!
    echo ================================================================================
    echo.
    echo Your Windows executables are ready!
    goto success_end
)

REM If both attempts failed
echo.
echo ================================================================================
echo                              BUILD FAILED!
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
echo    - Install Python 3.13+: https://www.python.org/downloads/
echo.
echo 3. NETWORK ISSUES:
echo    - Check internet connection
echo    - Verify GitHub access: https://github.com/srmorgan1/WPP.git
echo.
echo 4. GPG PASSPHRASE (if tests fail):
echo    Set environment variable: set GPG_PASSPHRASE=your_passphrase
echo.
echo For detailed logging, run this command in PowerShell:
echo .\build_and_deploy.ps1 -Verbose
echo.

:error_end
echo Press any key to exit...
pause >nul
exit /b 1

:success_end
echo Press any key to exit...
pause >nul
exit /b 0