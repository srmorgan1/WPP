#!/usr/bin/env python3
"""
FastAPI server startup script for WPP Management.
"""

import os
import sys
from pathlib import Path

# Add the src directory to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Set PYTHONPATH for subprocesses
os.environ["PYTHONPATH"] = str(src_path)

if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting WPP Management FastAPI server...")
    print("📊 API will be available at: http://localhost:8000")
    print("📚 API docs will be available at: http://localhost:8000/docs")
    print("🔗 WebSocket endpoint: ws://localhost:8000/ws")

    # Use import string to enable reload properly
    uvicorn.run("wpp.api.main:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=[str(src_path)], log_level="info")
