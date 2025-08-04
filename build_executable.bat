@echo off
REM Windows batch script to build WPP executable
REM Requires uv package manager to be installed

echo Starting WPP executable build process...

REM Check if we're in the project root
if not exist "pyproject.toml" (
    echo Error: Must run from project root directory
    echo Please navigate to the WPP project directory first
    pause
    exit /b 1
)

REM Check if uv is installed
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: uv package manager not found
    echo Please install uv from https://docs.astral.sh/uv/
    pause
    exit /b 1
)

echo Running build script with uv...
uv run build_executable.py

if %errorlevel% neq 0 (
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo Build completed successfully!
echo.
echo Executable files created in: dist\wpp\
echo.
echo Available executables:
echo   wpp-streamlit.exe    - Streamlit web application
echo   run-reports.exe      - Command-line reports generator
echo   update-database.exe  - Database update utility
echo.
echo To run the web app: dist\wpp\wpp-streamlit.exe
echo To run reports: dist\wpp\run-reports.exe
echo To update database: dist\wpp\update-database.exe
echo.
pause