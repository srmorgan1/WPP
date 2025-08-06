@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM WPP Local Build - Build Executables from Current Directory
REM This builds executables from the current project directory (no Git clone)
REM ============================================================================

title WPP Local Build

echo.
echo ================================================================================
echo                           WPP Local Build
echo ================================================================================
echo.
echo This script will build Windows executables from the current project directory.
echo.
echo Requirements:
echo   - Must be run from the WPP project root directory
echo   - uv package manager (will be checked automatically)
echo   - Project dependencies (will be set up automatically)
echo.
echo For full CI/CD builds (including Git clone), use BUILD_WPP.bat instead.
echo.

REM Check if we're in the project root
if not exist "pyproject.toml" (
    echo ERROR: Must run from project root directory!
    echo.
    echo This file should be in the same directory as pyproject.toml
    echo.
    echo For CI/CD builds that clone from GitHub, use BUILD_WPP.bat instead.
    echo.
    pause
    exit /b 1
)

REM Check if PowerShell script exists
if not exist "build_executable.ps1" (
    echo ERROR: build_executable.ps1 not found!
    echo Please ensure the PowerShell build script is present.
    pause
    exit /b 1
)

echo Found project files. Ready to build executables...
echo.
echo Press any key to start building, or Ctrl+C to cancel...
pause >nul

echo.
echo ================================================================================
echo Starting Local Build Process...
echo ================================================================================
echo.

REM Run the PowerShell script with execution policy handling
powershell.exe -ExecutionPolicy RemoteSigned -File "build_executable.ps1"

REM If that fails, try with Bypass policy
if %errorlevel% neq 0 (
    echo.
    echo Retrying with Bypass execution policy...
    powershell.exe -ExecutionPolicy Bypass -File "build_executable.ps1"
)

REM Check final result
if %errorlevel% equ 0 (
    echo.
    echo ================================================================================
    echo                           BUILD SUCCESSFUL!
    echo ================================================================================
    echo.
    echo Your Windows executables are ready in: dist\wpp\
    echo.
    echo Available executables:
    echo   ^> wpp-streamlit.exe    - Streamlit web application
    echo   ^> run-reports.exe      - Command-line reports generator
    echo   ^> update-database.exe  - Database update utility
    echo.
    echo Usage:
    echo   Web App:          .\dist\wpp\wpp-streamlit.exe
    echo   Generate Reports: .\dist\wpp\run-reports.exe
    echo   Update Database:  .\dist\wpp\update-database.exe
    echo.
    echo These executables are fully independent and do not require
    echo Python to be installed on the target machine.
    echo.
) else (
    echo.
    echo ================================================================================
    echo                             BUILD FAILED!
    echo ================================================================================
    echo.
    echo The build process encountered an error.
    echo.
    echo Common solutions:
    echo.
    echo 1. MISSING UV PACKAGE MANAGER:
    echo    Install from: https://docs.astral.sh/uv/
    echo.
    echo 2. MISSING DEPENDENCIES:
    echo    The PowerShell script should handle this automatically
    echo.
    echo 3. WRONG DIRECTORY:
    echo    Make sure you're in the project root (with pyproject.toml)
    echo.
    echo 4. EXECUTION POLICY:
    echo    Run PowerShell as Administrator and execute:
    echo    Set-ExecutionPolicy RemoteSigned
    echo.
    echo For detailed error information, run the PowerShell script directly:
    echo .\build_executable.ps1
    echo.
)

echo Press any key to exit...
pause >nul
exit /b %errorlevel%