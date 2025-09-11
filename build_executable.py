#!/usr/bin/env python3
"""
Build script to create executable from WPP Python application.
Uses PyInstaller to bundle the application with all dependencies.
"""

import os
import shutil
import subprocess
import sys


def install_pyinstaller():
    """Install PyInstaller using uv."""
    try:
        subprocess.run(["uv", "run", "--", "python", "-m", "pip", "show", "pyinstaller"], check=True, capture_output=True)
        print("PyInstaller already installed")
    except subprocess.CalledProcessError:
        print("Installing PyInstaller...")
        subprocess.run(["uv", "add", "--dev", "pyinstaller"], check=True)


def clean_build_dirs():
    """Clean previous build directories."""
    dirs_to_clean = ["build", "dist"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"Cleaning {dir_name} directory...")
            shutil.rmtree(dir_name)


def create_spec_file():
    """Create PyInstaller spec file for the application."""
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Main application analysis
a = Analysis(
    ['src/wpp/ui/react/web_app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('src/wpp/config.toml', 'wpp/'),
        ('src/wpp/*.py', 'wpp/'),
        ('src/wpp/api/', 'wpp/api/'),
        ('src/wpp/database/', 'wpp/database/'),
        ('src/wpp/input/', 'wpp/input/'),
        ('src/wpp/output/__init__.py', 'wpp/output/'),
        ('src/wpp/output/*.py', 'wpp/output/'),
        ('src/wpp/utils/', 'wpp/utils/'),
        ('src/wpp/schemas/', 'wpp/schemas/'),
        ('src/wpp/ui/', 'wpp/ui/'),
        ('web/build/', 'web/build/'),
    ],
    hiddenimports=[
        'fastapi',
        'uvicorn',
        'pandas',
        'openpyxl',
        'numpy',
        'dateutils',
        'toml',
        'wpp.RunReports',
        'wpp.UpdateDatabase',
        'wpp.calendars',
        'wpp.config',
        'wpp.constants',
        'wpp.data_classes',
        'wpp.sql_queries',
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
        'wpp.api',
        'wpp.api.services',
        'wpp.ui.react.web_app',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rthook_wpp_package.py'],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Main application PYZ
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Main application executable
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
    ['run_reports_wrapper.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('src/wpp/config.toml', 'wpp/'),
        ('src/wpp/*.py', 'wpp/'),
        ('src/wpp/database/', 'wpp/database/'),
        ('src/wpp/input/', 'wpp/input/'),
        ('src/wpp/output/__init__.py', 'wpp/output/'),
        ('src/wpp/output/*.py', 'wpp/output/'),
        ('src/wpp/utils/', 'wpp/utils/'),
        ('src/wpp/schemas/', 'wpp/schemas/'),
    ],
    hiddenimports=[
        'pandas',
        'openpyxl',
        'numpy',
        'dateutils',
        'toml',
        'wpp.calendars',
        'wpp.config',
        'wpp.constants',
        'wpp.data_classes',
        'wpp.sql_queries',
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
    runtime_hooks=['rthook_wpp_package.py'],
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
    ['update_database_wrapper.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('src/wpp/config.toml', 'wpp/'),
        ('src/wpp/*.py', 'wpp/'),
        ('src/wpp/database/', 'wpp/database/'),
        ('src/wpp/input/', 'wpp/input/'),
        ('src/wpp/output/__init__.py', 'wpp/output/'),
        ('src/wpp/output/*.py', 'wpp/output/'),
        ('src/wpp/utils/', 'wpp/utils/'),
        ('src/wpp/schemas/', 'wpp/schemas/'),
    ],
    hiddenimports=[
        'pandas',
        'openpyxl',
        'numpy',
        'dateutils',
        'toml',
        'wpp.calendars',
        'wpp.config',
        'wpp.constants',
        'wpp.data_classes',
        'wpp.sql_queries',
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
    runtime_hooks=['rthook_wpp_package.py'],
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

    with open("wpp.spec", "w") as f:
        f.write(spec_content)
    print("Created PyInstaller spec file: wpp.spec")


def build_executable():
    """Build the executable using PyInstaller."""
    print("Building executable with PyInstaller...")
    try:
        subprocess.run(["uv", "run", "--", "pyinstaller", "wpp.spec"], check=True)
        print("Build completed successfully!")
        print("Executable created in: dist/wpp/")
        print("Available executables:")
        print("  - wpp-web-app (React web app)")
        print("  - run-reports (Reports CLI)")
        print("  - update-database (Database update CLI)")
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        sys.exit(1)


def main():
    """Main build process."""
    print("Starting WPP executable build process...")

    # Ensure we're in the project root
    if not os.path.exists("pyproject.toml"):
        print("Error: Must run from project root directory")
        sys.exit(1)

    install_pyinstaller()
    clean_build_dirs()
    create_spec_file()
    build_executable()

    print("\nBuild process completed!")
    print("To run the web app: ./dist/wpp/wpp-web-app")
    print("To run reports: ./dist/wpp/run-reports")
    print("To update database: ./dist/wpp/update-database")


if __name__ == "__main__":
    main()
