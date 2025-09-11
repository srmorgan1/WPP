#!/usr/bin/env python3
"""
PyInstaller runtime hook for WPP package.
This ensures proper package context for relative imports in bundled executables.
"""

import os
import sys

# When PyInstaller creates the executable, it sets up a temporary directory
# We need to ensure the wpp package can be properly imported with relative imports

# Get the directory where the executable is running from
if hasattr(sys, "_MEIPASS"):
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    bundle_dir = sys._MEIPASS
else:
    bundle_dir = os.path.dirname(os.path.abspath(__file__))

# Add the bundle directory to Python path to ensure wpp package is found
if bundle_dir not in sys.path:
    sys.path.insert(0, bundle_dir)

# Ensure the wpp package directory is also in the path
wpp_package_dir = os.path.join(bundle_dir, "wpp")
if os.path.exists(wpp_package_dir) and wpp_package_dir not in sys.path:
    sys.path.insert(0, os.path.dirname(wpp_package_dir))


# Set __package__ for the main module if it's not set
# This is crucial for relative imports to work
def setup_package_context():
    """Setup proper package context for relative imports."""
    import sys

    # Get the main module
    main_module = sys.modules.get("__main__")
    if main_module and hasattr(main_module, "__file__"):
        main_file = main_module.__file__

        # Set package context based on the main file being run
        if main_file:
            if "UpdateDatabase" in main_file:
                main_module.__package__ = "wpp"
                main_module.__name__ = "wpp.UpdateDatabase"
            elif "RunReports" in main_file:
                main_module.__package__ = "wpp"
                main_module.__name__ = "wpp.RunReports"
            elif "web_app" in main_file:
                main_module.__package__ = "wpp.ui.react"
                main_module.__name__ = "wpp.ui.react.web_app"
                
    # Also set up package context for any wpp modules
    for module_name, module in list(sys.modules.items()):
        if module_name.startswith("wpp.") and hasattr(module, "__file__"):
            if not hasattr(module, "__package__") or not module.__package__:
                # Derive package from module name
                parts = module_name.split(".")
                if len(parts) > 1:
                    module.__package__ = ".".join(parts[:-1])
                else:
                    module.__package__ = "wpp"

    # Ensure wpp package is properly initialized and importable
    try:
        import wpp  # noqa: F401
        import wpp.api  # noqa: F401

        # Pre-import common WPP modules to ensure they're available
        import wpp.config  # noqa: F401
        import wpp.database.db  # noqa: F401
        import wpp.logger  # noqa: F401

    except ImportError as e:
        # Don't fail silently in case of import errors
        print(f"Warning: Could not pre-import wpp modules: {e}")


# Execute the setup
setup_package_context()
