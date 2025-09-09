@echo off
REM ============================================================================
REM WPP Web Application Quick Build - Skip Tests for Faster Building
REM ============================================================================

title WPP Web Application Quick Build (No Tests)

echo.
echo ================================================================================
echo                 WPP Web Application Quick Build (Skip Tests)
echo ================================================================================
echo.
echo This will build React + FastAPI web application WITHOUT running tests.
echo Use this for faster builds when you're confident the code is working.
echo.
echo For full builds with testing, use BUILD_WPP_WEB.bat instead.
echo.
echo OUTPUT: Modern React web application with FastAPI backend
echo   - Full interactive UI with real-time updates
echo   - Mobile-friendly responsive design
echo   - No installation required on target machines
echo.

if not exist "build_and_deploy_simple.ps1" (
    echo ERROR: build_and_deploy_simple.ps1 not found!
    pause
    exit /b 1
)

echo Starting quick web application build (skipping tests)...
echo.

powershell.exe -ExecutionPolicy RemoteSigned -File "build_and_deploy_simple.ps1" -SkipTests

if %errorlevel% equ 0 (
    echo.
    echo ================================================================================
    echo                   WEB APPLICATION QUICK BUILD SUCCESSFUL!
    echo ================================================================================
    echo.
    echo React + FastAPI executables ready in dist\wpp\ directory
    echo.
    echo Available executables:
    echo   ^> wpp-web-app.exe      - Modern React web application
    echo   ^> run-reports.exe      - Reports generator
    echo   ^> update-database.exe  - Database updater
    echo.
    echo Web interface will be at: http://localhost:8000
    echo.
) else (
    echo.
    echo Quick web build failed. Try BUILD_WPP_WEB.bat for detailed error handling.
    echo.
    echo Common issues:
    echo   - Node.js installation problems: Try -ApiOnly flag
    echo   - Network connectivity for downloading dependencies
    echo   - PowerShell execution policy restrictions
    echo.
)

echo Press any key to exit...
pause >nul