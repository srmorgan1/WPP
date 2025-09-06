#!/usr/bin/env python3
"""
Development startup script for WPP Management.
Automatically starts both FastAPI backend and React frontend for development.
"""

import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path


def start_fastapi_server():
    """Start the FastAPI development server."""
    print("🚀 Starting FastAPI backend server...")

    # Set up Python path
    project_root = Path(__file__).parent
    src_path = project_root / "src"
    os.environ["PYTHONPATH"] = str(src_path)

    try:
        # Start FastAPI server
        cmd = ["python", "run_fastapi.py"]
        process = subprocess.Popen(cmd, cwd=project_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)

        # Stream output
        for line in iter(process.stdout.readline, ""):
            if line.strip():
                print(f"[API] {line.strip()}")

        process.wait()

    except KeyboardInterrupt:
        print("\n[API] Shutting down FastAPI server...")
        process.terminate()
    except Exception as e:
        print(f"[API] Error: {e}")


def start_react_server():
    """Start the React development server."""
    print("⚛️  Starting React frontend server...")

    web_dir = Path(__file__).parent / "web"

    if not web_dir.exists():
        print("❌ Web directory not found. Skipping React server.")
        return

    try:
        # Check if node_modules exists, if not install dependencies
        node_modules = web_dir / "node_modules"
        if not node_modules.exists():
            print("📦 Installing React dependencies...")
            subprocess.run(["npm", "install"], cwd=web_dir, check=True)

        # Start React dev server
        cmd = ["npm", "start"]
        process = subprocess.Popen(
            cmd,
            cwd=web_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env={**os.environ, "BROWSER": "none"},  # Prevent auto-opening browser
        )

        # Stream output
        for line in iter(process.stdout.readline, ""):
            if line.strip():
                print(f"[React] {line.strip()}")

        process.wait()

    except KeyboardInterrupt:
        print("\n[React] Shutting down React server...")
        process.terminate()
    except Exception as e:
        print(f"[React] Error: {e}")


def check_node_available():
    """Check if Node.js is available."""
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, check=True)
        print(f"✅ Node.js found: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Node.js not found. React frontend will not be available.")
        print("   Options:")
        print("   1. Install Node.js from https://nodejs.org/")
        print("   2. Use API-only mode (visit http://localhost:8000/docs)")
        print("   3. Use original Streamlit version")
        return False


def open_browser_after_delay():
    """Open browser after servers start up."""
    print("⏱️  Waiting for servers to start...")
    time.sleep(8)  # Give servers time to start

    try:
        print("🌐 Opening browser...")
        webbrowser.open("http://localhost:3000")  # React dev server
    except Exception as e:
        print(f"Could not open browser automatically: {e}")
        print("Manual access:")
        print("  React UI: http://localhost:3000")
        print("  API docs: http://localhost:8000/docs")


def main():
    """Main development startup."""
    print("🎯 WPP Management Development Startup")
    print("=====================================")

    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        print("❌ Must run from project root directory (where pyproject.toml is)")
        sys.exit(1)

    node_available = check_node_available()

    print("\n🚀 Starting development servers...")
    print("📋 Instructions:")
    print("   • Both servers will start automatically")
    print("   • Browser will open after servers start")
    print("   • Press Ctrl+C to stop both servers")
    print("   • Make changes to code - servers auto-reload")

    if node_available:
        print("\n🌐 Available interfaces:")
        print("   • React UI: http://localhost:3000 (recommended)")
        print("   • API docs: http://localhost:8000/docs")
    else:
        print("\n🔧 Available interfaces:")
        print("   • API docs: http://localhost:8000/docs (Node.js not available)")

    print("\n" + "=" * 50)

    try:
        # Start browser opening in background
        if node_available:
            browser_thread = threading.Thread(target=open_browser_after_delay, daemon=True)
            browser_thread.start()

        # Start both servers in separate threads
        api_thread = threading.Thread(target=start_fastapi_server, daemon=True)
        api_thread.start()

        if node_available:
            react_thread = threading.Thread(target=start_react_server, daemon=True)
            react_thread.start()

            # Wait for both threads
            api_thread.join()
            react_thread.join()
        else:
            # Just wait for API thread
            api_thread.join()

    except KeyboardInterrupt:
        print("\n\n👋 Shutting down development servers...")
        print("   All servers stopped.")

    print("✅ Development session ended.")


if __name__ == "__main__":
    main()
