#!/usr/bin/env python3
"""
Unified web application that serves both FastAPI backend and React frontend.
This is the main entry point for the packaged executable.
"""

import json
import os
import signal
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Add src to Python path for imports
if hasattr(sys, "_MEIPASS"):
    # Running in PyInstaller bundle - path should already be set by runtime hook
    bundle_dir = Path(sys._MEIPASS)
    src_dir = bundle_dir
else:
    # Running in development
    bundle_dir = Path(__file__).parent.parent.parent.parent.parent
    src_dir = bundle_dir / "src"
    sys.path.insert(0, str(src_dir))

from wpp.api.models import GenerateReportsRequest, GenerateReportsResponse, ProgressUpdate, SystemStatus, TaskResult, UpdateDatabaseRequest, UpdateDatabaseResponse, WebSocketMessage
from wpp.api.services import DatabaseService, FileService, ReportsService, SystemService, task_manager


def get_static_files_dir():
    """Get the directory containing React build files."""
    if hasattr(sys, "_MEIPASS"):
        # Running in PyInstaller bundle
        return Path(sys._MEIPASS) / "web" / "build"
    else:
        # Running in development
        return Path(__file__).parent.parent.parent.parent.parent / "web" / "build"


def create_app(api_only=False):
    """Create the FastAPI application with both API and static file serving."""
    app = FastAPI(title="WPP Management", description="WPP data management and reporting application", version="2.0.0")

    # Enable CORS for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # WebSocket connections manager
    class ConnectionManager:
        def __init__(self):
            self.active_connections = []
            self.last_heartbeat = time.time()
            self.last_interaction = time.time()  # Track actual user interactions
            self.monitoring_thread = None
            self.shutdown_requested = False

        async def connect(self, websocket):
            await websocket.accept()
            self.active_connections.append(websocket)

        def disconnect(self, websocket):
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

        async def broadcast(self, message: str):
            for connection in self.active_connections[:]:  # Copy list to avoid modification during iteration
                try:
                    await connection.send_text(message)
                except Exception:
                    # Connection might be closed
                    self.disconnect(connection)

        def update_heartbeat(self):
            """Update the last heartbeat timestamp."""
            self.last_heartbeat = time.time()

        def update_interaction(self, interaction_type="unknown"):
            """Update the last user interaction timestamp."""
            self.last_interaction = time.time()
            print(f"💡 User interaction detected: {interaction_type}")

        def start_monitoring(self):
            """Start the inactivity monitoring thread."""
            if self.monitoring_thread is None or not self.monitoring_thread.is_alive():
                self.monitoring_thread = threading.Thread(target=self._monitor_inactivity, daemon=True)
                self.monitoring_thread.start()
                print("🔍 Inactivity monitoring started")

        def _monitor_inactivity(self):
            """Monitor for inactivity and shutdown if timeout exceeded."""
            # Get config values
            from wpp.config import get_max_runtime_minutes, get_no_connection_shutdown_delay, get_user_interaction_timeout

            max_runtime_minutes = get_max_runtime_minutes()
            heartbeat_timeout_minutes = get_no_connection_shutdown_delay()
            interaction_timeout_minutes = get_user_interaction_timeout()

            print(f"📊 Monitoring: max_runtime={max_runtime_minutes}m, heartbeat_timeout={heartbeat_timeout_minutes}m, interaction_timeout={interaction_timeout_minutes}m")

            start_time = time.time()

            while not self.shutdown_requested:
                current_time = time.time()

                # Check maximum runtime
                if max_runtime_minutes > 0:
                    elapsed_minutes = (current_time - start_time) / 60
                    if elapsed_minutes >= max_runtime_minutes:
                        print(f"⏰ Maximum runtime of {max_runtime_minutes} minutes exceeded. Shutting down...")
                        self._trigger_shutdown()
                        break

                # Check user interaction timeout (1 hour)
                interaction_age_minutes = (current_time - self.last_interaction) / 60
                if interaction_age_minutes >= interaction_timeout_minutes:
                    print(f"😴 No user interaction for {interaction_age_minutes:.1f} minutes (timeout: {interaction_timeout_minutes}m). Shutting down...")
                    self._trigger_shutdown()
                    break

                # Check heartbeat timeout (for connection loss detection)
                if heartbeat_timeout_minutes > 0:
                    heartbeat_age_minutes = (current_time - self.last_heartbeat) / 60
                    if heartbeat_age_minutes >= heartbeat_timeout_minutes:
                        print(f"💤 No heartbeat for {heartbeat_age_minutes:.1f} minutes (timeout: {heartbeat_timeout_minutes}m). Connection lost, shutting down...")
                        self._trigger_shutdown()
                        break

                time.sleep(30)  # Check every 30 seconds

        def _trigger_shutdown(self):
            """Trigger server shutdown."""
            self.shutdown_requested = True
            # Give a moment for any final responses
            threading.Thread(target=lambda: (time.sleep(2), os.kill(os.getpid(), signal.SIGTERM)), daemon=True).start()

    manager = ConnectionManager()

    # API Routes
    @app.get("/api/system/status", response_model=SystemStatus)
    async def get_system_status():
        return await SystemService.get_system_status()

    @app.get("/api/system/charges-date")
    async def get_charges_date():
        """Get the latest date from the Charges table for report date defaulting."""
        manager.update_interaction("get_charges_date")
        latest_date = await SystemService.get_latest_charges_date()
        return {"charges_date": latest_date}

    @app.post("/api/shutdown")
    async def shutdown_server(request: dict):
        """Handle explicit shutdown requests from the frontend."""
        reason = request.get("reason", "unknown")
        print(f"🔴 Shutdown request received: {reason}")

        # Trigger immediate shutdown
        manager.shutdown_requested = True
        threading.Thread(target=lambda: (time.sleep(0.5), os.kill(os.getpid(), signal.SIGTERM)), daemon=True).start()

        return {"status": "shutdown_initiated", "reason": reason}

    @app.post("/api/database/update", response_model=UpdateDatabaseResponse)
    async def update_database(request: UpdateDatabaseRequest):
        # Track user interaction
        manager.update_interaction("database_update")

        async def progress_callback(update: ProgressUpdate):
            message = WebSocketMessage(type="progress", task_id=update.task_id, data={"progress": update.progress, "message": update.message, "status": update.status})
            await manager.broadcast(message.model_dump_json())

        task_id = await DatabaseService.update_database(delete_existing=request.delete_existing, progress_callback=progress_callback)

        return UpdateDatabaseResponse(task_id=task_id, status="pending", message="Database update started", started_at=task_manager.get_task(task_id).started_at)

    @app.post("/api/reports/generate", response_model=GenerateReportsResponse)
    async def generate_reports(request: GenerateReportsRequest):
        # Track user interaction
        manager.update_interaction("generate_reports")

        async def progress_callback(update: ProgressUpdate):
            message = WebSocketMessage(type="progress", task_id=update.task_id, data={"progress": update.progress, "message": update.message, "status": update.status})
            await manager.broadcast(message.model_dump_json())

        task_id = await ReportsService.generate_reports(report_date=request.report_date, progress_callback=progress_callback)

        return GenerateReportsResponse(task_id=task_id, status="pending", message="Report generation started", started_at=task_manager.get_task(task_id).started_at)

    @app.get("/api/tasks/{task_id}", response_model=TaskResult)
    async def get_task_status(task_id: str):
        task = task_manager.get_task(task_id)
        if not task:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Task not found")
        return task

    @app.get("/api/files/excel/{filename}")
    async def get_excel_data(filename: str):
        import os

        from wpp.config import get_wpp_report_dir

        # Construct full path in reports directory
        reports_dir = get_wpp_report_dir()
        file_path = os.path.join(reports_dir, filename)

        data = await FileService.get_excel_data(file_path)
        if not data:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="File not found or cannot be read")
        return data

    @app.get("/api/files/log/{filename}")
    async def get_log_content(filename: str):
        import os

        from wpp.config import get_wpp_log_dir

        # Construct full path in logs directory
        log_dir = get_wpp_log_dir()
        file_path = os.path.join(log_dir, filename)

        content = await FileService.get_log_content(file_path)
        if content is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="File not found")
        return {"content": content, "filename": filename}

    @app.get("/api/files/web_data/{filename}")
    async def get_web_data(filename: str):
        """Get web data (structured sheet data) by sheet name."""
        # Extract sheet name from filename (remove .json extension)
        sheet_name = filename.replace(".json", "").replace("_", " ").replace("and", "&")

        # For web data, we need to get it from the most recent task's web output handler
        # This is a simplified approach - in a full implementation, you'd want to store
        # the web data more persistently or pass the task_id to get specific data

        # For now, return a structured response indicating this is web data
        return {"type": "web_data", "sheet_name": sheet_name, "message": "Web data should be displayed directly from task results", "filename": filename}

    @app.get("/api/debug/latest-failed-task")
    async def get_latest_failed_task():
        """Get the most recent failed task for debugging."""
        from wpp.api.services import task_manager

        # Find the most recent failed task
        failed_tasks = [task for task in task_manager._tasks.values() if task.status.value == "failed"]

        if not failed_tasks:
            return {"message": "No failed tasks found"}

        # Get the most recent failed task
        latest_task = max(failed_tasks, key=lambda t: t.started_at)

        return {
            "task_id": latest_task.task_id,
            "status": latest_task.status.value,
            "error": latest_task.error,
            "has_web_sheets": bool(latest_task.result_data and latest_task.result_data.summary and latest_task.result_data.summary.get("web_sheets")),
            "web_sheets_count": len(latest_task.result_data.summary.get("web_sheets", {})) if latest_task.result_data and latest_task.result_data.summary else 0,
            "completed_at": latest_task.completed_at.isoformat() if latest_task.completed_at else None,
        }

    @app.post("/api/test/websocket")
    async def test_websocket():
        """Test WebSocket functionality by broadcasting a test message."""
        test_message = WebSocketMessage(type="progress", task_id="test-task-123", data={"progress": 50, "message": "This is a test WebSocket message", "status": "running"})
        await manager.broadcast(test_message.model_dump_json())
        return {"message": "Test WebSocket message sent"}

    @app.get("/api/test/display-latest-errors")
    async def display_latest_errors():
        """Return the latest failed task data formatted for easy display."""
        from wpp.api.services import task_manager

        # Find the most recent failed task
        failed_tasks = [task for task in task_manager._tasks.values() if task.status.value == "failed"]

        if not failed_tasks:
            return {"error": "No failed tasks found"}

        # Get the most recent failed task
        latest_task = max(failed_tasks, key=lambda t: t.started_at)

        # Format for display
        result = {
            "task_id": latest_task.task_id,
            "status": latest_task.status.value,
            "error": latest_task.error,
            "started_at": latest_task.started_at.isoformat(),
            "completed_at": latest_task.completed_at.isoformat() if latest_task.completed_at else None,
        }

        # Add web sheets if available
        if latest_task.result_data and latest_task.result_data.summary and latest_task.result_data.summary.get("web_sheets"):
            result["web_sheets"] = latest_task.result_data.summary["web_sheets"]

        return result

    @app.post("/api/export/excel")
    async def export_to_excel(request: dict):
        """Export structured data to Excel file."""
        manager.update_interaction("export_excel")
        import tempfile

        import pandas as pd
        from fastapi.responses import FileResponse

        from wpp.output.output_handler import ExcelOutputHandler

        try:
            # Create temporary Excel file
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
                excel_path = tmp_file.name

            # Create Excel output handler
            excel_handler = ExcelOutputHandler(excel_path)

            # Extract sheets data from request
            sheets_data = request.get("sheets", {})
            report_name = request.get("reportName", "WPP_Export")

            # Convert each sheet back to DataFrame and add to Excel
            for sheet_name, sheet_info in sheets_data.items():
                if "columns" in sheet_info and "data" in sheet_info:
                    # Recreate DataFrame from structured data
                    df = pd.DataFrame(sheet_info["data"], columns=sheet_info["columns"])
                    # Add metadata if available
                    metadata = sheet_info.get("metadata", {})
                    excel_handler.add_sheet(sheet_name, df, metadata)

            # Add summary if available
            if "summary" in request:
                excel_handler.add_summary("export_info", request["summary"])

            # Build the Excel file
            result_path = excel_handler.build()

            # Return the Excel file as download
            return FileResponse(
                path=result_path,
                filename=f"{report_name}.xlsx",
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={report_name}.xlsx"},
            )

        except Exception as e:
            from fastapi import HTTPException

            raise HTTPException(status_code=500, detail=f"Excel export failed: {str(e)}")

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await manager.connect(websocket)

        try:
            while True:
                # Receive messages from client (including heartbeats)
                data = await websocket.receive_text()

                try:
                    message = json.loads(data)
                    if message.get("type") == "heartbeat":
                        manager.update_heartbeat()
                        print(f"💓 Heartbeat received from {message.get('page', 'unknown')}")
                except json.JSONDecodeError:
                    # Not JSON or not a heartbeat, just keep connection alive
                    pass

        except WebSocketDisconnect:
            manager.disconnect(websocket)

    # Serve React static files (unless in API-only mode)
    if not api_only:
        static_dir = get_static_files_dir()
    else:
        static_dir = Path("/nonexistent")  # Force API-only mode

    if static_dir.exists():
        # Mount static files
        app.mount("/static", StaticFiles(directory=static_dir / "static"), name="static")

        # Serve React app
        @app.get("/{path:path}")
        async def serve_react_app(path: str = ""):
            # Serve index.html for all routes (React Router handling)
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            else:
                return {"error": "React build files not found"}
    else:

        @app.get("/")
        async def no_frontend():
            # Redirect to the working test interface instead of showing JSON
            from fastapi.responses import RedirectResponse

            return RedirectResponse(url="/test", status_code=302)

        @app.get("/test")
        async def serve_test_page():
            """Serve the Excel export test page."""
            from pathlib import Path

            # Get the working directory where the test file is located
            test_file = Path.cwd() / "test_excel_export.html"
            if test_file.exists():
                return FileResponse(str(test_file), media_type="text/html")
            else:
                return {"error": f"Test file not found at {test_file}"}

        @app.get("/simple")
        async def serve_simple_test_page():
            """Serve the simple error display test page."""
            from pathlib import Path

            # Get the working directory where the simple test file is located
            test_file = Path.cwd() / "simple_error_display.html"
            if test_file.exists():
                return FileResponse(str(test_file), media_type="text/html")
            else:
                return {"error": f"Simple test file not found at {test_file}"}

        @app.get("/debug")
        async def serve_debug_test_page():
            """Serve the debug UI test page."""
            from pathlib import Path

            # Get the working directory where the debug test file is located
            test_file = Path.cwd() / "debug_ui_test.html"
            if test_file.exists():
                return FileResponse(str(test_file), media_type="text/html")
            else:
                return {"error": f"Debug test file not found at {test_file}"}

        @app.get("/immediate")
        async def serve_immediate_test_page():
            """Serve the immediate test page with manual controls."""
            from pathlib import Path

            # Get the working directory where the immediate test file is located
            test_file = Path.cwd() / "immediate_test.html"
            if test_file.exists():
                return FileResponse(str(test_file), media_type="text/html")
            else:
                return {"error": f"Immediate test file not found at {test_file}"}

        @app.get("/console")
        async def serve_console_debug_page():
            """Serve the console debug test page."""
            from pathlib import Path

            # Get the working directory where the console debug file is located
            test_file = Path.cwd() / "test_debug_console.html"
            if test_file.exists():
                return FileResponse(str(test_file), media_type="text/html")
            else:
                return {"error": f"Console debug file not found at {test_file}"}

    # Start monitoring immediately when app is created
    print("🔍 Starting auto-shutdown monitoring...")
    manager.start_monitoring()
    print("✅ Auto-shutdown monitoring active")

    return app


def open_browser(url: str, delay: float = 2.0):
    """Open browser after a delay."""

    def _open():
        time.sleep(delay)
        print(f"🌐 Opening browser: {url}")
        webbrowser.open(url)

    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


def main():
    """Main entry point."""
    import sys

    # Check for API-only mode flag
    api_only_mode = "--api-only" in sys.argv or os.getenv("WPP_API_ONLY", "").lower() == "true"

    if api_only_mode:
        print("🔧 Starting WPP API Server (API-Only Mode)...")
        print("   Mode: Pure API (No Web Interface)")
    else:
        print("🚀 Starting WPP Management Web Application...")

    # Initialize config (triggers copy to home directory if needed)
    from wpp.config import get_config

    get_config()
    print("✅ Configuration loaded")

    # Check if React build exists (unless in API-only mode)
    if api_only_mode:
        print("🚫 React frontend disabled (API-only mode)")
        static_dir = Path("/nonexistent")  # Will not exist
    else:
        static_dir = get_static_files_dir()
        if static_dir.exists():
            print(f"✅ React frontend found: {static_dir}")
        else:
            print(f"⚠️  React frontend not found: {static_dir}")
            print("   API will still work, but no web interface available.")

    app = create_app(api_only=api_only_mode)

    # We'll start monitoring after the app is created

    # Set up server configuration
    host = "127.0.0.1"
    port = 8000

    print(f"🔗 API Server: http://{host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")

    if static_dir.exists() and not api_only_mode:
        print(f"🌐 Web Application: http://{host}:{port}")
        # Auto-open browser
        open_browser(f"http://{host}:{port}")
    elif api_only_mode:
        print("📡 Mode: API-Only (No Web Interface)")

    print("💡 Press Ctrl+C to stop the server")

    # Run the server
    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=False,  # Reduce console noise
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down WPP Management Application...")


if __name__ == "__main__":
    main()
