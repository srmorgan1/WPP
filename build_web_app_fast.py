#!/usr/bin/env python3
"""
Fast build script for just the web app executable (no reports/database tools).
This skips heavy data science packages to speed up build time.
"""

import os
import shutil
import subprocess
import sys


def check_pyinstaller():
    """Check PyInstaller availability via uv."""
    try:
        subprocess.run(["uv", "run", "pyinstaller", "--version"], check=True, capture_output=True)
        print("PyInstaller available via uv")
        return True
    except subprocess.CalledProcessError:
        print("PyInstaller not available via uv - should be in pyproject.toml")
        return False


def clean_build_dirs():
    """Clean previous build directories."""
    dirs_to_clean = ["build", "dist"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"Cleaning {dir_name} directory...")
            try:
                shutil.rmtree(dir_name)
            except PermissionError as e:
                print(f"Warning: Could not clean {dir_name} - {e}")
                print("   This is usually safe to ignore - PyInstaller will overwrite files")
                continue


def create_fast_web_spec():
    """Create optimized PyInstaller spec for just the web app."""
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Fast web application analysis - web app only
a = Analysis(
    ['src/wpp/ui/react/web_app.py'],
    pathex=['.', 'src'],
    binaries=[],
    datas=[
        ('src/wpp/config.toml', 'wpp/'),
        ('src/wpp/*.py', 'wpp/'),
        ('src/wpp/api/', 'wpp/api/'),
        ('src/wpp/ui/', 'wpp/ui/'),
        ('web/build/', 'web/build/'),
    ],
    hiddenimports=[
        # Web framework essentials only
        'fastapi',
        'uvicorn',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.logging',
        'websockets',
        'websockets.server',
        'websockets.client',
        'pydantic',
        # Core WPP modules
        'wpp.api',
        'wpp.api.main',
        'wpp.api.models',
        'wpp.api.services',
        'wpp.ui',
        'wpp.ui.react',
        'wpp.ui.react.web_app',
        'wpp.config',
        'wpp.logger',
    ],
    excludes=[
        # Exclude ALL heavy data science packages
        'pandas',
        'numpy',
        'matplotlib',
        'scipy',
        'openpyxl',
        'lxml',
        'PIL',
        'Pillow',
        'pyarrow',
        'IPython',
        'jupyter',
        'notebook',
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'pytest',
        'pygments',
        'dateutil',
        'pytz',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='wpp-web-app-fast',
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

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='wpp-fast',
)
"""

    with open("wpp_web_fast.spec", "w") as f:
        f.write(spec_content)
    print("Created fast PyInstaller spec: wpp_web_fast.spec")


def build_executable():
    """Build the executable using PyInstaller."""
    print("Building FAST web app executable with PyInstaller...")
    try:
        subprocess.run(["uv", "run", "pyinstaller", "wpp_web_fast.spec"], check=True)
        print("Fast build completed successfully!")
        print("Executable created in: dist/wpp-fast/")
        print("Available executable:")
        print("  - wpp-web-app-fast (Web application with React UI)")
        print("Included web assets:")
        print("  - React frontend (web/build/)")
        print("  - All static files bundled")
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        sys.exit(1)


def main():
    """Main build process."""
    print("Starting FAST WPP web application build process...")

    # Ensure we're in the project root
    if not os.path.exists("pyproject.toml"):
        print("Error: Must run from project root directory")
        sys.exit(1)

    # Check if React frontend was already built by PowerShell script
    react_already_built = os.environ.get("REACT_BUILD_DONE") == "true"

    if not react_already_built:
        print("React frontend not pre-built. Run the PowerShell script first.")
        sys.exit(1)

    print("React frontend already built by PowerShell script")

    # Build Python executable
    if not check_pyinstaller():
        print("PyInstaller not available - ensure it's in pyproject.toml dependencies")
        sys.exit(1)

    clean_build_dirs()
    create_fast_web_spec()
    build_executable()

    print("Fast build process completed!")
    print("To run the web app: ./dist/wpp-fast/wpp-web-app-fast")
    print("Web interface will be at: http://localhost:8000")


if __name__ == "__main__":
    main()
