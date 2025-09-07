#!/usr/bin/env python3
"""
PyInstaller runtime hook for WPP package.
This ensures proper package context for relative imports in bundled executables.
"""

import sys
import os
from pathlib import Path

# When PyInstaller creates the executable, it sets up a temporary directory
# We need to ensure the wpp package can be properly imported with relative imports

# Get the directory where the executable is running from
if hasattr(sys, '_MEIPASS'):
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    bundle_dir = sys._MEIPASS
else:
    bundle_dir = os.path.dirname(os.path.abspath(__file__))

# Add the bundle directory to Python path to ensure wpp package is found
if bundle_dir not in sys.path:
    sys.path.insert(0, bundle_dir)

# Ensure the wpp package directory is also in the path
wpp_package_dir = os.path.join(bundle_dir, 'wpp')
if os.path.exists(wpp_package_dir) and wpp_package_dir not in sys.path:
    sys.path.insert(0, os.path.dirname(wpp_package_dir))

# Set __package__ for the main module if it's not set
# This is crucial for relative imports to work
def setup_package_context():
    """Setup proper package context for relative imports."""
    import sys
    
    # If we're running UpdateDatabase, ensure it knows it's part of the wpp package
    if hasattr(sys.modules.get('__main__'), '__file__'):
        main_file = sys.modules['__main__'].__file__
        if main_file and 'UpdateDatabase' in main_file:
            sys.modules['__main__'].__package__ = 'wpp'
    
    # Ensure wpp package is properly initialized
    try:
        import wpp
    except ImportError:
        pass

# Execute the setup
setup_package_context()