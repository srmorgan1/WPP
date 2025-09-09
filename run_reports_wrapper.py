#!/usr/bin/env python3
"""
Wrapper script to run RunReports as a module with proper package context.
This ensures relative imports work correctly in PyInstaller executables.
"""

import os
import sys

# Add src to Python path to ensure wpp package is importable
if hasattr(sys, "_MEIPASS"):
    # PyInstaller mode
    bundle_dir = sys._MEIPASS
else:
    # Development mode
    bundle_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(bundle_dir, "src")
    if os.path.exists(src_dir) and src_dir not in sys.path:
        sys.path.insert(0, src_dir)

# Import and run the module
import runpy

if __name__ == "__main__":
    # Use runpy to run as module, which properly handles all arguments and sys.argv
    runpy.run_module("wpp.RunReports", run_name="__main__")
