"""Service layer for business logic."""

import asyncio
import os
import uuid
from datetime import datetime

import pandas as pd

from wpp.config import get_wpp_data_dir, get_wpp_db_file, get_wpp_log_dir, get_wpp_report_dir
from wpp.db import get_db_connection, get_single_value
from wpp.output_handler import WebOutputHandler
from wpp.RunReports import run_reports_core
from wpp.UpdateDatabase import update_database_core
from wpp.web_logger import setup_web_logger

from .models import ExcelFileData, FileInfo, FileReference, ProgressUpdate, SpreadsheetData, SystemStatus, TaskResult, TaskResultData, TaskStatus


class TaskManager:
    """Manages background tasks and their status."""

    def __init__(self):
        self._tasks: dict[str, TaskResult] = {}
        self._progress_callbacks: dict[str, list] = {}

    def create_task(self, task_type: str) -> str:
        """Create a new task and return its ID."""
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = TaskResult(task_id=task_id, task_type=task_type, status=TaskStatus.PENDING, started_at=datetime.now())
        self._progress_callbacks[task_id] = []
        return task_id

    def get_task(self, task_id: str) -> TaskResult | None:
        """Get task by ID."""
        return self._tasks.get(task_id)

    def update_task_status(self, task_id: str, status: TaskStatus, **kwargs):
        """Update task status and data."""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = status
            if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                task.completed_at = datetime.now()

            # Update any additional fields
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)

    def add_progress_callback(self, task_id: str, callback):
        """Add progress callback for task."""
        if task_id in self._progress_callbacks:
            self._progress_callbacks[task_id].append(callback)

    def notify_progress(self, task_id: str, progress: float, message: str):
        """Notify all progress callbacks for a task."""
        if task_id in self._progress_callbacks:
            task_status = self._tasks[task_id].status
            update = ProgressUpdate(task_id=task_id, status=task_status, progress=progress, message=message, timestamp=datetime.now())
            for callback in self._progress_callbacks[task_id]:
                try:
                    asyncio.create_task(callback(update))
                except Exception as e:
                    print(f"Error in progress callback: {e}")


# Global task manager instance
task_manager = TaskManager()


class DatabaseService:
    """Service for database operations."""

    @staticmethod
    async def update_database(delete_existing: bool = True, progress_callback=None) -> str:
        """Update database in background task."""
        # Check if a database update is already running
        running_updates = [task for task in task_manager._tasks.values() if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING] and task.task_type == "update_database"]

        if running_updates:
            from fastapi import HTTPException

            raise HTTPException(status_code=409, detail="A database update is already in progress")

        task_id = task_manager.create_task("update_database")

        if progress_callback:
            task_manager.add_progress_callback(task_id, progress_callback)

        # Run in background
        asyncio.create_task(DatabaseService._run_update_database(task_id, delete_existing))
        return task_id

    @staticmethod
    async def _run_update_database(task_id: str, delete_existing: bool):
        """Internal method to run database update."""
        web_output_handler = None
        result_data = None

        try:
            task_manager.update_task_status(task_id, TaskStatus.RUNNING)
            task_manager.notify_progress(task_id, 0, "Starting database update...")

            if delete_existing:
                db_file = get_wpp_db_file()
                if os.path.exists(db_file):
                    os.remove(db_file)
                    task_manager.notify_progress(task_id, 10, "Deleted existing database")

            task_manager.notify_progress(task_id, 20, "Processing source files...")

            # Create web logger callback for real-time log streaming
            async def log_callback(message: str):
                """Send log messages via progress updates."""
                try:
                    # Send log message as progress update (use 50 as neutral progress)
                    task_manager.notify_progress(task_id, 50, f"LOG: {message}")
                except Exception:
                    # Don't let logging errors break the main process
                    pass

            # Create web output callback for real-time data streaming
            async def output_callback(event_type: str, data: dict):
                """Send output data via progress updates."""
                try:
                    # Send data as progress update with event type
                    task_manager.notify_progress(task_id, 60, f"DATA: {event_type} - {len(data.get('data', []))} records")
                except Exception:
                    # Don't let output errors break the main process
                    pass

            # Create web logger and output handler
            web_logger = setup_web_logger(__name__, log_callback)
            web_output_handler = WebOutputHandler(output_callback)

            # Run the actual update using the core function with injected logger and output handler
            web_logger.info(f"Starting core database update for task {task_id}")
            result = await asyncio.get_event_loop().run_in_executor(None, update_database_core, web_logger, web_output_handler)
            web_logger.info(f"Core database update completed for task {task_id}")

            task_manager.notify_progress(task_id, 90, "Database update completed")

            # Get task result data from output handler
            web_logger.debug(f"Getting task result data from output handler for task {task_id}")
            result_data = web_output_handler.get_task_result_data()
            web_logger.debug(f"Got results for task {task_id}: {len(result_data.files) if result_data else 0} files")

            # Mark task as completed with results
            task_manager.update_task_status(task_id, TaskStatus.COMPLETED, result_data=result_data)
            web_logger.debug(f"Marked task {task_id} as completed")
            # Send final progress notification with completed status
            task_manager.notify_progress(task_id, 100, "Database update completed successfully")
            web_logger.info(f"Task {task_id} completed successfully")

        except Exception as e:
            # Even when failed, get results from the output handler
            try:
                result_data = web_output_handler.get_task_result_data()
            except Exception as fallback_error:
                if "web_logger" in locals():
                    web_logger.error(f"Error getting results from output handler: {fallback_error}")
                result_data = await DatabaseService._get_update_results()

            task_manager.update_task_status(task_id, TaskStatus.FAILED, error=str(e), result_data=result_data)
            # Send final progress notification with failed status
            task_manager.notify_progress(task_id, 0, f"Error: {str(e)}")

        except Exception as critical_error:
            # Absolute fallback - ensure task is always marked as failed
            if "web_logger" in locals():
                web_logger.critical(f"CRITICAL ERROR in database update task {task_id}: {critical_error}")
            else:
                print(f"CRITICAL ERROR in database update task {task_id}: {critical_error}")
            try:
                # Try to get minimal result data
                if result_data is None:
                    result_data = await DatabaseService._get_update_results()

                task_manager.update_task_status(task_id, TaskStatus.FAILED, error=f"Critical error: {str(critical_error)}", result_data=result_data)
                task_manager.notify_progress(task_id, 0, f"Critical error: {str(critical_error)}")
            except Exception as final_error:
                print(f"FINAL FALLBACK ERROR for task {task_id}: {final_error}")
                # Last resort - mark as failed with minimal data
                try:
                    from wpp.api.models import TaskResultData

                    task_manager.update_task_status(task_id, TaskStatus.FAILED, error=f"System error: {str(critical_error)}", result_data=TaskResultData(files=[], summary={}))
                except Exception:
                    pass  # If even this fails, at least we tried

    @staticmethod
    async def _convert_web_result_to_task_data(web_result: dict) -> TaskResultData:
        """Convert web output handler result to TaskResultData format."""
        files = []

        # For web results, we don't have actual files, but we can create references
        # to the sheets that were generated for compatibility with existing UI
        if "sheets" in web_result:
            for sheet_name, sheet_data in web_result["sheets"].items():
                files.append(FileReference(filename=f"{sheet_name.replace(' ', '_')}.json", file_type="json", display_name=sheet_name))

        return TaskResultData(files=files, summary=web_result.get("summary", {}))

    @staticmethod
    async def _get_update_results() -> TaskResultData:
        """Get results from database update."""
        files = []

        try:
            # Find latest data import issues file
            reports_dir = get_wpp_report_dir()
            if reports_dir.exists():
                issues_files = [f for f in os.listdir(reports_dir) if f.startswith("Data_Import_Issues_") and f.endswith(".xlsx")]
                if issues_files:
                    latest_issues = max(issues_files, key=lambda f: os.path.getctime(os.path.join(reports_dir, f)))
                    files.append(FileReference(filename=latest_issues, file_type="excel", display_name="Data Import Issues"))

            # Find latest log file
            log_dir = get_wpp_log_dir()
            if log_dir.exists():
                log_files = [f for f in os.listdir(log_dir) if "UpdateDatabase" in f]
                if log_files:
                    latest_log = max(log_files, key=lambda f: os.path.getctime(os.path.join(log_dir, f)))
                    files.append(FileReference(filename=latest_log, file_type="log", display_name="Database Update Log"))

        except Exception as e:
            print(f"Error getting update results: {e}")

        return TaskResultData(files=files)


class ReportsService:
    """Service for report operations."""

    @staticmethod
    async def generate_reports(report_date, progress_callback=None) -> str:
        """Generate reports in background task."""
        # Check if a report generation is already running
        running_reports = [task for task in task_manager._tasks.values() if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING] and task.task_type == "generate_reports"]

        if running_reports:
            from fastapi import HTTPException

            raise HTTPException(status_code=409, detail="A report generation is already in progress")

        task_id = task_manager.create_task("generate_reports")

        if progress_callback:
            task_manager.add_progress_callback(task_id, progress_callback)

        # Run in background
        asyncio.create_task(ReportsService._run_generate_reports(task_id, report_date))
        return task_id

    @staticmethod
    async def _run_generate_reports(task_id: str, report_date):
        """Internal method to generate reports."""
        web_output_handler = None
        result_data = None

        try:
            task_manager.update_task_status(task_id, TaskStatus.RUNNING)
            task_manager.notify_progress(task_id, 0, "Starting report generation...")

            task_manager.notify_progress(task_id, 20, "Processing data...")

            # Create web logger callback for real-time log streaming
            async def log_callback(message: str):
                """Send log messages via progress updates."""
                try:
                    # Send log message as progress update (use 40 as neutral progress)
                    task_manager.notify_progress(task_id, 40, f"LOG: {message}")
                except Exception:
                    # Don't let logging errors break the main process
                    pass

            # Create web output callback for real-time data streaming
            async def output_callback(event_type: str, data: dict):
                """Send output data via progress updates."""
                try:
                    # Send data as progress update with event type
                    task_manager.notify_progress(task_id, 60, f"DATA: {event_type} - {len(data.get('data', []))} records")
                except Exception:
                    # Don't let output errors break the main process
                    pass

            # Create web logger and output handler
            web_logger = setup_web_logger(__name__, log_callback)
            web_output_handler = WebOutputHandler(output_callback)

            # Run the actual report generation using the core function with injected logger and output handler
            print(f"DEBUG: About to call run_reports_core for task {task_id}")
            result = await asyncio.get_event_loop().run_in_executor(None, run_reports_core, report_date, report_date, web_logger, web_output_handler)
            print(f"DEBUG: run_reports_core completed for task {task_id}, result: {result}")

            task_manager.notify_progress(task_id, 80, "Reports generated, collecting files...")

            # Get task result data from output handler
            print(f"DEBUG: Getting task result data from output handler for task {task_id}")
            result_data = web_output_handler.get_task_result_data()
            print(f"DEBUG: Got results for task {task_id}: {result_data}")

            # Mark task as completed with results
            task_manager.update_task_status(task_id, TaskStatus.COMPLETED, result_data=result_data)
            # Send final progress notification with completed status
            task_manager.notify_progress(task_id, 100, "Reports generated successfully")

        except Exception as e:
            # Even when failed, try to get results from the output handler
            try:
                result_data = web_output_handler.get_task_result_data()
            except Exception as fallback_error:
                print(f"Error getting results from output handler: {fallback_error}")
                result_data = await ReportsService._get_report_results()

            task_manager.update_task_status(task_id, TaskStatus.FAILED, error=str(e), result_data=result_data)
            task_manager.notify_progress(task_id, 0, f"Error: {str(e)}")

        except Exception as critical_error:
            # Absolute fallback - ensure task is always marked as failed
            print(f"CRITICAL ERROR in report generation task {task_id}: {critical_error}")
            try:
                # Try to get minimal result data
                if result_data is None:
                    result_data = await ReportsService._get_report_results()

                task_manager.update_task_status(task_id, TaskStatus.FAILED, error=f"Critical error: {str(critical_error)}", result_data=result_data)
                task_manager.notify_progress(task_id, 0, f"Critical error: {str(critical_error)}")
            except Exception as final_error:
                print(f"FINAL FALLBACK ERROR for task {task_id}: {final_error}")
                # Last resort - mark as failed with minimal data
                try:
                    from wpp.api.models import TaskResultData

                    task_manager.update_task_status(task_id, TaskStatus.FAILED, error=f"System error: {str(critical_error)}", result_data=TaskResultData(files=[], summary={}))
                except Exception:
                    pass  # If even this fails, at least we tried

    @staticmethod
    async def _convert_web_result_to_task_data(web_result: dict) -> TaskResultData:
        """Convert web output handler result to TaskResultData format for reports."""
        files = []

        # For web results, we don't have actual files, but we can create references
        # to the sheets that were generated for compatibility with existing UI
        if "sheets" in web_result:
            for sheet_name, sheet_data in web_result["sheets"].items():
                files.append(FileReference(filename=f"{sheet_name.replace(' ', '_').replace('&', 'and')}.json", file_type="json", display_name=sheet_name))

        return TaskResultData(files=files, summary=web_result.get("summary", {}))

    @staticmethod
    async def _get_report_results() -> TaskResultData:
        """Get results from report generation."""
        files = []

        try:
            # Find latest WPP report file
            reports_dir = get_wpp_report_dir()
            if reports_dir.exists():
                report_files = [f for f in os.listdir(reports_dir) if f.startswith("WPP_Report") and f.endswith(".xlsx")]
                if report_files:
                    latest_report = max(report_files, key=lambda f: os.path.getctime(os.path.join(reports_dir, f)))
                    files.append(FileReference(filename=latest_report, file_type="excel", display_name="WPP Report"))

            # Find latest log file
            log_dir = get_wpp_log_dir()
            if log_dir.exists():
                log_files = [f for f in os.listdir(log_dir) if "RunReports" in f]
                if log_files:
                    latest_log = max(log_files, key=lambda f: os.path.getctime(os.path.join(log_dir, f)))
                    files.append(FileReference(filename=latest_log, file_type="log", display_name="Report Generation Log"))

        except Exception as e:
            print(f"Error getting report results: {e}")

        return TaskResultData(files=files)


class FileService:
    """Service for file operations."""

    @staticmethod
    async def get_excel_data(file_path: str) -> ExcelFileData | None:
        """Get Excel file data."""
        try:
            if not os.path.exists(file_path):
                return None

            # Get file info
            stat = os.stat(file_path)
            file_info = FileInfo(
                name=os.path.basename(file_path), path=file_path, size=stat.st_size, created_at=datetime.fromtimestamp(stat.st_ctime), modified_at=datetime.fromtimestamp(stat.st_mtime)
            )

            # Read Excel file
            excel_file = pd.ExcelFile(file_path)
            sheets = []

            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)

                # Convert DataFrame to our format
                sheet_data = SpreadsheetData(sheet_name=sheet_name, columns=df.columns.tolist(), data=df.values.tolist())
                sheets.append(sheet_data)

            return ExcelFileData(file_info=file_info, sheets=sheets)

        except Exception as e:
            print(f"Error reading Excel file {file_path}: {e}")
            return None

    @staticmethod
    async def get_log_content(file_path: str) -> str | None:
        """Get log file content."""
        try:
            if not os.path.exists(file_path):
                return None

            with open(file_path) as f:
                return f.read()

        except Exception as e:
            print(f"Error reading log file {file_path}: {e}")
            return None


class SystemService:
    """Service for system status."""

    @staticmethod
    async def get_system_status() -> SystemStatus:
        """Get current system status."""
        db_file = get_wpp_db_file()
        data_dir = get_wpp_data_dir()

        # Get only tasks that are actually running
        running_task_ids = [task_id for task_id, task in task_manager._tasks.items() if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]]

        return SystemStatus(
            database_exists=os.path.exists(db_file),
            data_directory=str(data_dir),
            data_directory_exists=data_dir.exists(),
            running_tasks=running_task_ids,
            uptime=0.0,  # TODO: Implement actual uptime tracking
        )

    @staticmethod
    async def get_latest_charges_date() -> str | None:
        """Get the latest date from the Charges table, if any data exists."""
        try:
            db_file = get_wpp_db_file()
            if not os.path.exists(db_file):
                return None

            db_conn = get_db_connection(db_file)
            csr = db_conn.cursor()

            # Get the most recent date from the Charges table
            sql = "SELECT MAX(at_date) FROM Charges"
            latest_date = get_single_value(csr, sql, ())

            db_conn.close()

            return latest_date if latest_date else None

        except Exception as e:
            print(f"Error getting latest charges date: {e}")
            return None
