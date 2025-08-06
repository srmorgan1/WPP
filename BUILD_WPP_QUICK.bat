@echo off
REM ============================================================================
REM WPP Quick Build - Skip Tests for Faster Building
REM ============================================================================

title WPP Quick Build (No Tests)

echo.
echo ================================================================================
echo                        WPP Quick Build (Skip Tests)
echo ================================================================================
echo.
echo This will build WPP executables WITHOUT running tests.
echo Use this for faster builds when you're confident the code is working.
echo.
echo For full builds with testing, use BUILD_WPP.bat instead.
echo.

if not exist "build_and_deploy.ps1" (
    echo ERROR: build_and_deploy.ps1 not found!
    pause
    exit /b 1
)

echo Press any key to start quick build...
pause >nul

echo.
echo Starting quick build (skipping tests)...
echo.

powershell.exe -ExecutionPolicy RemoteSigned -File "build_and_deploy.ps1" -SkipTests

if %errorlevel% equ 0 (
    echo.
    echo ================================================================================
    echo                         QUICK BUILD SUCCESSFUL!
    echo ================================================================================
    echo.
    echo Executables ready in dist\wpp\ directory
    echo.
) else (
    echo.
    echo Quick build failed. Try BUILD_WPP.bat for detailed error handling.
    echo.
)

echo Press any key to exit...
pause >nul