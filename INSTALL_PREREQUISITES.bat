@echo off
REM ============================================================================
REM WPP Build System Prerequisites Installer
REM ============================================================================

title WPP Prerequisites Installer

echo.
echo ================================================================================
echo                    WPP Build System Prerequisites Installer
echo ================================================================================
echo.
echo This will install the required system prerequisites for building WPP executables:
echo   • Git - Version control system for downloading source code
echo   • Node.js LTS - JavaScript runtime for building React frontend
echo.
echo Note: Python and uv will be installed automatically by the build scripts.
echo.

if not exist "install_prerequisites.ps1" (
    echo ERROR: install_prerequisites.ps1 not found!
    echo Make sure both INSTALL_PREREQUISITES.bat and install_prerequisites.ps1
    echo are in the same directory.
    echo.
    pause
    exit /b 1
)

echo Installing prerequisites with PowerShell...
echo.

powershell.exe -ExecutionPolicy RemoteSigned -File "install_prerequisites.ps1"

if %errorlevel% equ 0 (
    echo.
    echo ================================================================================
    echo                      PREREQUISITES INSTALLATION SUCCESSFUL!
    echo ================================================================================
    echo.
    echo System is now ready for WPP builds.
    echo.
    echo Next steps:
    echo   1. Close this window and reopen a new Command Prompt/PowerShell
    echo   2. Run BUILD_WPP_WEB_QUICK.bat to build WPP executables
    echo.
    echo The build system will automatically handle Python/uv installation.
    echo.
) else (
    echo.
    echo ================================================================================
    echo                        PREREQUISITES INSTALLATION FAILED!
    echo ================================================================================
    echo.
    echo The PowerShell script encountered an error.
    echo Check the output above for details.
    echo.
    echo You may need to:
    echo   • Run as Administrator
    echo   • Install Git and Node.js manually from their websites
    echo   • Check your internet connection
    echo.
    echo Manual download links:
    echo   Git: https://git-scm.com/download/windows
    echo   Node.js: https://nodejs.org/en/download/
    echo.
)

echo Press any key to exit...
pause >nul