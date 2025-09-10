#!/usr/bin/env python3
"""
Simple build script for customers without Node.js.
This builds executables without the React frontend, falling back to API-only mode.
"""

import os
import shutil
import subprocess
import sys


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


def create_simple_spec():
    """Create PyInstaller spec file without React build."""
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Web application analysis (API only)
a = Analysis(
    ['src/wpp/ui/react/web_app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('src/wpp/config.toml', 'wpp/'),
        ('src/wpp/*.py', 'wpp/'),
        ('src/wpp/database/', 'wpp/database/'),
        ('src/wpp/input/', 'wpp/input/'),
        ('src/wpp/output/', 'wpp/output/'),
        ('src/wpp/utils/', 'wpp/utils/'),
        ('src/wpp/schemas/', 'wpp/schemas/'),
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
        'wpp.database',
        'wpp.database.db',
        'wpp.database.database_commands',
        'wpp.logger',
        'wpp.ref_matcher',
        'wpp.utils',
        'wpp.utils.utils',
        'wpp.utils.excel',
        'wpp.utils.exceptions',
        'wpp.input',
        'wpp.input.xml',
        'wpp.input.excel',
        'wpp.output',
        'wpp.output.output_handler',
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
    name='wpp-web-api',
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
        ('src/wpp/database/', 'wpp/database/'),
        ('src/wpp/input/', 'wpp/input/'),
        ('src/wpp/output/', 'wpp/output/'),
        ('src/wpp/utils/', 'wpp/utils/'),
        ('src/wpp/schemas/', 'wpp/schemas/'),
    ],
    hiddenimports=[
        'pandas',
        'openpyxl',
        'numpy',
        'dateutils',
        'wpp.calendars',
        'wpp.config',
        'wpp.database',
        'wpp.database.db',
        'wpp.database.database_commands',
        'wpp.logger',
        'wpp.ref_matcher',
        'wpp.utils',
        'wpp.utils.utils',
        'wpp.utils.excel',
        'wpp.utils.exceptions',
        'wpp.input',
        'wpp.input.xml',
        'wpp.input.excel',
        'wpp.output',
        'wpp.output.output_handler',
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
        ('src/wpp/database/', 'wpp/database/'),
        ('src/wpp/input/', 'wpp/input/'),
        ('src/wpp/output/', 'wpp/output/'),
        ('src/wpp/utils/', 'wpp/utils/'),
        ('src/wpp/schemas/', 'wpp/schemas/'),
    ],
    hiddenimports=[
        'pandas',
        'openpyxl',
        'numpy',
        'dateutils',
        'wpp.calendars',
        'wpp.config',
        'wpp.database',
        'wpp.database.db',
        'wpp.database.database_commands',
        'wpp.logger',
        'wpp.ref_matcher',
        'wpp.utils',
        'wpp.utils.utils',
        'wpp.utils.excel',
        'wpp.utils.exceptions',
        'wpp.input',
        'wpp.input.xml',
        'wpp.input.excel',
        'wpp.output',
        'wpp.output.output_handler',
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

    with open("wpp_simple.spec", "w") as f:
        f.write(spec_content)
    print("✅ Created PyInstaller spec file: wpp_simple.spec")


def build_executable():
    """Build the executable using PyInstaller."""
    print("🔨 Building executable with PyInstaller...")
    try:
        subprocess.run(["uv", "run", "--", "pyinstaller", "wpp_simple.spec"], check=True)
        print("✅ Build completed successfully!")
        print("📁 Executable created in: dist/wpp/")
        print("🎯 Available executables:")
        print("  - wpp-web-api (API server - access via browser at http://localhost:8000)")
        print("  - run-reports (Reports CLI)")
        print("  - update-database (Database update CLI)")
        print("💡 Note: This build includes API only. For full web UI, use build_web_app.py with Node.js")
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed with error: {e}")
        sys.exit(1)


def main():
    """Main build process."""
    print("🚀 Starting WPP simple executable build process...")
    print("💡 This builds API-only executables (no React frontend required)")

    # Ensure we're in the project root
    if not os.path.exists("pyproject.toml"):
        print("❌ Error: Must run from project root directory")
        sys.exit(1)

    # Build Python executable
    install_pyinstaller()
    clean_build_dirs()
    create_simple_spec()
    build_executable()

    print("✅ Build process completed!")
    print("🎯 To run the API server: ./dist/wpp/wpp-web-api")
    print("📊 To run reports: ./dist/wpp/run-reports")
    print("🔄 To update database: ./dist/wpp/update-database")
    print("🌐 API documentation will be at: http://localhost:8000/docs")
    print("")
    print("🔄 For full web UI, you can:")
    print("  1. Use build_web_app.py on a machine with Node.js")
    print("  2. Copy a pre-built web/build/ directory and run build_web_app.py")


if __name__ == "__main__":
    main()
