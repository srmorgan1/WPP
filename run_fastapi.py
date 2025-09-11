#!/usr/bin/env python3
"""
FastAPI server startup script for WPP Management.
"""

import os
import sys
import psutil
import time
from pathlib import Path

# Add the src directory to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Set PYTHONPATH for subprocesses
os.environ["PYTHONPATH"] = str(src_path)


def kill_existing_wpp_processes():
    """Kill existing WPP processes in two steps:
    1. Kill processes listening on WPP ports that match expected names
    2. Kill any processes that match expected WPP names (whether listening or not)
    """
    print("🔍 Checking for existing WPP server processes...")
    killed_any = False
    killed_pids = set()  # Track killed PIDs to avoid double-killing
    
    # WPP ports and expected process identifiers
    wpp_ports = [8000, 3000]  # FastAPI and React dev server
    
    # Expected WPP process names and command line patterns
    expected_wpp_process_names = [
        'python',
        'python3',
        'uvicorn',
        'node',
        'npm',
        'wpp-streamlit',
        'wpp-update-db', 
        'wpp-run-reports'
    ]
    
    expected_wpp_cmdline_patterns = [
        'run_fastapi.py',
        'uvicorn.*wpp',
        'react-scripts',
        'wpp-streamlit',
        'wpp-update-db',
        'wpp-run-reports'
    ]
    
    def is_expected_wpp_process(process):
        """Check if a process matches expected WPP process characteristics with ultra-careful validation."""
        try:
            process_name = process.name().lower()
            cmdline = ' '.join(process.cmdline()).lower()
            cwd = getattr(process, 'cwd', lambda: '')() or ''
            
            project_root_str = str(project_root.resolve()).lower()
            
            # ULTRA-CAREFUL: Only kill processes that are DEFINITELY WPP-related
            
            # 1. Direct WPP executable matches (safest)
            wpp_executable_names = ['wpp-streamlit', 'wpp-update-db', 'wpp-run-reports']
            for exe_name in wpp_executable_names:
                if exe_name in process_name or exe_name in cmdline:
                    return True
            
            # 2. Python processes: MUST have WPP-specific patterns AND be in our project directory
            if 'python' in process_name:
                is_in_project = project_root_str in cwd.lower()
                has_wpp_pattern = any(pattern in cmdline for pattern in [
                    'run_fastapi.py', 
                    'wpp/api/main', 
                    'wpp.api.main',
                    'uvicorn.*wpp'
                ])
                
                if is_in_project and has_wpp_pattern:
                    return True
            
            # 3. Node/npm processes: MUST have react-scripts AND be in our web directory
            if 'node' in process_name or 'npm' in process_name:
                is_in_web_dir = f"{project_root_str}/web" in cwd.lower()
                has_react_scripts = 'react-scripts' in cmdline
                
                if is_in_web_dir and has_react_scripts:
                    return True
            
            # 4. Uvicorn processes: MUST contain wpp in command line
            if 'uvicorn' in process_name:
                if 'wpp' in cmdline:
                    return True
                    
            return False
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def kill_process_safely(process, reason):
        """Kill a process safely with graceful termination first."""
        nonlocal killed_any, killed_pids
        
        try:
            if process.pid in killed_pids:
                return  # Already killed
                
            print(f"🔧 Killing WPP process ({reason})")
            print(f"   PID: {process.pid}, Name: {process.name()}")
            print(f"   Command: {' '.join(process.cmdline())[:100]}...")
            
            process.terminate()
            killed_pids.add(process.pid)
            
            # Wait for graceful shutdown, then force kill if needed
            try:
                process.wait(timeout=3)
            except psutil.TimeoutExpired:
                print(f"⚠️  Force killing process {process.pid}")
                process.kill()
            
            killed_any = True
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"⚠️  Could not kill process {process.pid}: {e}")
    
    try:
        current_pid = os.getpid()
        
        # STEP 1: Kill processes listening on WPP ports that match expected names
        print("📍 Step 1: Checking processes listening on WPP ports (8000, 3000)...")
        for port in wpp_ports:
            try:
                for conn in psutil.net_connections():
                    if (conn.laddr.port == port and 
                        conn.status == psutil.CONN_LISTEN and
                        conn.pid and conn.pid != current_pid):
                        try:
                            process = psutil.Process(conn.pid)
                            
                            if is_expected_wpp_process(process):
                                kill_process_safely(process, f"listening on port {port}")
                            else:
                                print(f"⚠️  Found non-WPP process on port {port}")
                                print(f"   PID: {conn.pid}, Name: {process.name()}")
                                print(f"   Command: {' '.join(process.cmdline())[:100]}...")
                                print(f"   ❌ Skipping - not a confirmed WPP process")
                                
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                            print(f"⚠️  Could not access process {conn.pid}: {e}")
            except (psutil.AccessDenied, PermissionError) as e:
                print(f"⚠️  Could not check connections for port {port}: {e}")
                continue
        
        # STEP 2: Kill any processes that match expected WPP names (whether listening or not)
        print("📍 Step 2: Checking all processes for WPP name matches...")
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
            try:
                if proc.info['pid'] == current_pid or proc.info['pid'] in killed_pids:
                    continue  # Don't kill ourselves or already killed processes
                
                process = psutil.Process(proc.info['pid'])
                
                if is_expected_wpp_process(process):
                    kill_process_safely(process, "matching WPP process pattern")
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process may have already died or we don't have permission
                continue
            except Exception as e:
                # Only show detailed errors for unexpected exceptions
                if "pid" not in str(e).lower():
                    print(f"⚠️  Unexpected error checking process: {e}")
                continue
        
        if killed_any:
            print("✅ Cleaned up existing WPP processes")
            print("⏳ Waiting for processes to fully terminate...")
            time.sleep(2)
        else:
            print("✅ No existing WPP processes found")
            
    except Exception as e:
        print(f"⚠️  Error during process cleanup: {e}")
        print("🚀 Continuing with server startup...")


if __name__ == "__main__":
    import uvicorn

    # Clean up existing processes first
    kill_existing_wpp_processes()
    
    print("🚀 Starting WPP Management FastAPI server...")
    print("📊 API will be available at: http://localhost:8000")
    print("📚 API docs will be available at: http://localhost:8000/docs")
    print("🔗 WebSocket endpoint: ws://localhost:8000/ws")

    # Use import string to enable reload properly
    uvicorn.run("wpp.api.main:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=[str(src_path)], log_level="info")
