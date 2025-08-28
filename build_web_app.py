#!/usr/bin/env python3
"""
Build script to create web app executable that includes React frontend.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def check_node_installed():
    """Check if Node.js is installed."""
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, check=True)
        print(f"✅ Node.js found: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Node.js not found. Please install Node.js to build the React frontend.")
        print("   You can download it from: https://nodejs.org/")
        return False


def install_react_dependencies():
    """Install React dependencies."""
    web_dir = Path("web")
    if not web_dir.exists():
        print("❌ Web directory not found!")
        return False

    print("📦 Installing React dependencies...")
    try:
        subprocess.run(["npm", "install"], cwd=web_dir, check=True)
        print("✅ React dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install React dependencies: {e}")
        return False


def build_react_app():
    """Build the React app for production."""
    web_dir = Path("web")
    build_dir = web_dir / "build"

    # Clean previous build
    if build_dir.exists():
        print("🧹 Cleaning previous React build...")
        shutil.rmtree(build_dir)

    print("🔨 Building React app for production...")
    try:
        subprocess.run(["npm", "run", "build"], cwd=web_dir, check=True)
        print("✅ React app built successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to build React app: {e}")
        return False


def install_pyinstaller():
    """Install PyInstaller using uv."""
    try:
        subprocess.run(["uv", "run", "--", "python", "-m", "pip", "show", "pyinstaller"], check=True, capture_output=True)
        print("✅ PyInstaller already installed")
    except subprocess.CalledProcessError:
        print("📦 Installing PyInstaller...")
        subprocess.run(["uv", "add", "--dev", "pyinstaller"], check=True)
        print("✅ PyInstaller installed")


def clean_build_dirs():
    """Clean previous build directories."""
    dirs_to_clean = ["build", "dist"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"🧹 Cleaning {dir_name} directory...")
            shutil.rmtree(dir_name)


def create_web_app_spec():
    """Create PyInstaller spec file for the web application."""
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Web application analysis
a = Analysis(
    ['src/wpp/ui/react/web_app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('src/wpp/config.toml', 'wpp/'),
        ('src/wpp/*.py', 'wpp/'),
        ('web/build/', 'web/build/'),
    ],
    hiddenimports=[
        'fastapi',
        'uvicorn',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.websockets_impl',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.logging',
        'websockets',
        'websockets.server',
        'websockets.client',
        'websockets.legacy.server',
        'websockets.legacy.client',
        'pydantic',
        'pandas',
        'openpyxl',
        'numpy',
        'dateutils',
        'wpp.RunReports',
        'wpp.UpdateDatabase',
        'wpp.calendars',
        'wpp.config',
        'wpp.db',
        'wpp.logger',
        'wpp.ref_matcher',
        'wpp.utils',
        'wpp.api.main',
        'wpp.api.models',
        'wpp.api.services',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Web app PYZ
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Web app executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='wpp-web-app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# RunReports analysis
run_reports_a = Analysis(
    ['src/wpp/RunReports.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('src/wpp/config.toml', 'wpp/'),
        ('src/wpp/*.py', 'wpp/'),
    ],
    hiddenimports=[
        'pandas',
        'openpyxl',
        'numpy',
        'dateutils',
        'wpp.calendars',
        'wpp.config',
        'wpp.db',
        'wpp.logger',
        'wpp.ref_matcher',
        'wpp.utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

run_reports_pyz = PYZ(run_reports_a.pure, run_reports_a.zipped_data, cipher=block_cipher)

run_reports_exe = EXE(
    run_reports_pyz,
    run_reports_a.scripts,
    [],
    exclude_binaries=True,
    name='run-reports',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# UpdateDatabase analysis
update_db_a = Analysis(
    ['src/wpp/UpdateDatabase.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('src/wpp/config.toml', 'wpp/'),
        ('src/wpp/*.py', 'wpp/'),
    ],
    hiddenimports=[
        'pandas',
        'openpyxl',
        'numpy',
        'dateutils',
        'wpp.calendars',
        'wpp.config',
        'wpp.db',
        'wpp.logger',
        'wpp.ref_matcher',
        'wpp.utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

update_db_pyz = PYZ(update_db_a.pure, update_db_a.zipped_data, cipher=block_cipher)

update_db_exe = EXE(
    update_db_pyz,
    update_db_a.scripts,
    [],
    exclude_binaries=True,
    name='update-database',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Collect all executables and dependencies
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    run_reports_exe,
    run_reports_a.binaries,
    run_reports_a.zipfiles,
    run_reports_a.datas,
    update_db_exe,
    update_db_a.binaries,
    update_db_a.zipfiles,
    update_db_a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='wpp',
)
"""

    with open("wpp_web.spec", "w") as f:
        f.write(spec_content)
    print("✅ Created PyInstaller spec file: wpp_web.spec")


def build_executable():
    """Build the executable using PyInstaller."""
    print("🔨 Building executable with PyInstaller...")
    try:
        subprocess.run(["uv", "run", "--", "pyinstaller", "wpp_web.spec"], check=True)
        print("✅ Build completed successfully!")
        print("📁 Executable created in: dist/wpp/")
        print("🎯 Available executables:")
        print("  - wpp-web-app (Web application with React UI)")
        print("  - run-reports (Reports CLI)")
        print("  - update-database (Database update CLI)")
        print("🌐 Included web assets:")
        print("  - React frontend (web/build/)")
        print("  - All static files bundled")
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed with error: {e}")
        sys.exit(1)


def main():
    """Main build process."""
    print("🚀 Starting WPP web application build process...")

    # Ensure we're in the project root
    if not os.path.exists("pyproject.toml"):
        print("❌ Error: Must run from project root directory")
        sys.exit(1)

    # Check if Node.js is available for building React app
    if not check_node_installed():
        print("⚠️  Node.js not found. You have options:")
        print("   1. Install Node.js and run this script again")
        print("   2. Get a pre-built React bundle from another machine")
        print("   3. Use the original Streamlit version (build_executable.py)")
        sys.exit(1)

    # Install React dependencies and build
    if not install_react_dependencies():
        sys.exit(1)

    if not build_react_app():
        sys.exit(1)

    # Build Python executable
    install_pyinstaller()
    clean_build_dirs()
    create_web_app_spec()
    build_executable()

    print("✅ Build process completed!")
    print("🎯 To run the web app: ./dist/wpp/wpp-web-app")
    print("📊 To run reports: ./dist/wpp/run-reports")
    print("🔄 To update database: ./dist/wpp/update-database")
    print("🌐 Web interface will be at: http://localhost:8000")


if __name__ == "__main__":
    main()
