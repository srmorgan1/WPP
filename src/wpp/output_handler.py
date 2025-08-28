"""
Output handler interface and implementations for flexible data output.
Supports both Excel file generation and real-time web streaming.
"""

import asyncio
import os
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from wpp.excel import format_all_excel_sheets_comprehensive

if TYPE_CHECKING:
    from wpp.api.models import TaskResultData


class OutputHandler(ABC):
    """Abstract interface for handling output data from core processing functions."""

    @abstractmethod
    def add_sheet(self, name: str, df: pd.DataFrame, metadata: dict | None = None, is_critical: bool = False) -> None:
        """Add a dataframe as a sheet/table to the output."""
        pass

    @abstractmethod
    def add_summary(self, key: str, data: dict[str, Any]) -> None:
        """Add summary data to the output."""
        pass

    @abstractmethod
    def add_file_reference(self, name: str, path: str, description: str | None = None) -> None:
        """Add a reference to a generated file."""
        pass

    @abstractmethod
    def add_metric(self, key: str, value: Any, description: str | None = None) -> None:
        """Add a single metric/statistic."""
        pass

    @abstractmethod
    def build(self) -> Any:
        """Finalize and return the output result."""
        pass

    @abstractmethod
    def get_task_result_data(self) -> "TaskResultData":
        """Get TaskResultData for API task completion, regardless of success/failure."""
        pass


class ExcelOutputHandler(OutputHandler):
    """Excel file output handler - maintains existing Excel generation behavior."""

    def __init__(self, file_path: str):
        """Initialize with target Excel file path."""
        self.file_path = Path(file_path)
        
        # Ensure directory exists
        os.makedirs(self.file_path.parent, exist_ok=True)

        self.writer = pd.ExcelWriter(self.file_path, engine="openpyxl")
        self.summary_data = {}
        self.file_references = {}
        self.metrics = {}
        self.sheets_added = []

    def add_sheet(self, name: str, df: pd.DataFrame, metadata: dict | None = None, is_critical: bool = False) -> None:
        """Add dataframe as Excel sheet."""
        # Clean sheet name for Excel compatibility
        clean_name = self._clean_sheet_name(name)
        df.to_excel(self.writer, sheet_name=clean_name, index=False)
        self.sheets_added.append(clean_name)
        # Note: Excel files don't need to track critical status for display purposes

    def add_summary(self, key: str, data: dict[str, Any]) -> None:
        """Store summary data - could be written as separate sheet if needed."""
        self.summary_data[key] = data

    def add_file_reference(self, name: str, path: str, description: str | None = None) -> None:
        """Store file reference."""
        self.file_references[name] = {"path": path, "description": description}

    def add_metric(self, key: str, value: Any, description: str | None = None) -> None:
        """Store metric."""
        self.metrics[key] = {"value": value, "description": description}

    def build(self) -> str:
        """Close Excel writer and return file path."""
        # Add summary sheet if we have summary data or metrics
        # if self.summary_data or self.metrics:
        #     self._add_summary_sheet()

        # Apply comprehensive formatting to all sheets
        format_all_excel_sheets_comprehensive(self.writer)

        self.writer.close()
        return str(self.file_path)

    def get_task_result_data(self) -> "TaskResultData":
        """Get TaskResultData by searching for generated Excel files and logs on disk."""
        import os

        from wpp.api.models import FileReference, TaskResultData
        from wpp.config import get_wpp_log_dir, get_wpp_report_dir

        files = []

        try:
            # Add the Excel file we just created
            if self.file_path.exists():
                files.append(FileReference(filename=self.file_path.name, file_type="excel", display_name=f"Excel Report - {self.file_path.stem}"))

            # Find latest data import issues file (for database updates)
            reports_dir = get_wpp_report_dir()
            if reports_dir.exists():
                issues_files = [f for f in os.listdir(reports_dir) if f.startswith("Data_Import_Issues_") and f.endswith(".xlsx")]
                if issues_files:
                    latest_issues = max(issues_files, key=lambda f: os.path.getctime(os.path.join(reports_dir, f)))
                    files.append(FileReference(filename=latest_issues, file_type="excel", display_name="Data Import Issues"))

            # Find latest log file
            log_dir = get_wpp_log_dir()
            if log_dir.exists():
                log_files = [f for f in os.listdir(log_dir) if any(pattern in f for pattern in ["UpdateDatabase", "RunReports"])]
                if log_files:
                    latest_log = max(log_files, key=lambda f: os.path.getctime(os.path.join(log_dir, f)))
                    files.append(FileReference(filename=latest_log, file_type="log", display_name="Process Log"))

        except Exception as e:
            print(f"Error getting Excel handler task results: {e}")

        return TaskResultData(files=files, summary=self.summary_data)

    def _clean_sheet_name(self, name: str) -> str:
        """Clean sheet name for Excel compatibility."""
        # Excel sheet names can't be longer than 31 chars and can't contain certain chars
        invalid_chars = ["\\", "/", "*", "?", ":", "[", "]"]
        clean_name = name
        for char in invalid_chars:
            clean_name = clean_name.replace(char, "_")
        return clean_name[:31]

    def _add_summary_sheet(self) -> None:
        """Add summary sheet with metrics and summary data."""
        summary_rows = []

        # Add metrics
        for key, metric in self.metrics.items():
            summary_rows.append({"Type": "Metric", "Key": key, "Value": metric["value"], "Description": metric.get("description", "")})

        # Add summary data (flatten nested dicts)
        for key, data in self.summary_data.items():
            if isinstance(data, dict):
                for subkey, value in data.items():
                    summary_rows.append({"Type": "Summary", "Key": f"{key}.{subkey}", "Value": value, "Description": ""})
            else:
                summary_rows.append({"Type": "Summary", "Key": key, "Value": data, "Description": ""})

        if summary_rows:
            summary_df = pd.DataFrame(summary_rows)
            summary_df.to_excel(self.writer, sheet_name="Summary", index=False)


class WebOutputHandler(OutputHandler):
    """Web output handler - streams data directly to web interface via callback."""

    def __init__(self, callback: Callable[[str, dict], Awaitable[None]]):
        """Initialize with callback function for streaming data.

        Args:
            callback: Async function that takes (event_type, data) and streams to web
        """
        self.callback = callback
        self.data = {"sheets": {}, "summary": {}, "file_references": {}, "metrics": {}}

    def add_sheet(self, name: str, df: pd.DataFrame, metadata: dict | None = None, is_critical: bool = False) -> None:
        """Stream sheet data directly to web interface."""
        sheet_data = {"name": name, "columns": df.columns.tolist(), "data": df.to_dict("records"), "row_count": len(df), "metadata": metadata or {}, "is_critical": is_critical}

        # Store for final result
        self.data["sheets"][name] = sheet_data

        # Stream immediately to web interface
        self._stream_async("sheet_data", sheet_data)

    def add_summary(self, key: str, data: dict[str, Any]) -> None:
        """Stream summary data to web interface."""
        self.data["summary"][key] = data
        self._stream_async("summary_data", {"key": key, "data": data})

    def add_file_reference(self, name: str, path: str, description: str | None = None) -> None:
        """Stream file reference to web interface."""
        file_ref = {"name": name, "path": path, "description": description}
        self.data["file_references"][name] = file_ref
        self._stream_async("file_reference", file_ref)

    def add_metric(self, key: str, value: Any, description: str | None = None) -> None:
        """Stream metric to web interface."""
        metric = {"key": key, "value": value, "description": description}
        self.data["metrics"][key] = metric
        self._stream_async("metric", metric)

    def build(self) -> dict[str, Any]:
        """Return collected data."""
        # Send final completion event
        self._stream_async("build_complete", {"total_sheets": len(self.data["sheets"]), "total_metrics": len(self.data["metrics"]), "summary_keys": list(self.data["summary"].keys())})
        return self.data

    def get_task_result_data(self) -> "TaskResultData":
        """Get TaskResultData from the collected web data with direct sheet access."""
        from wpp.api.models import TaskResultData

        # For web UI, return empty files list and include sheet data directly in summary
        # This avoids the unnecessary file reference complexity
        enhanced_summary = dict(self.data.get("summary", {}))
        enhanced_summary["web_sheets"] = self.data["sheets"]
        enhanced_summary["web_metrics"] = self.data.get("metrics", {})

        return TaskResultData(files=[], summary=enhanced_summary)

    def _stream_async(self, event_type: str, data: dict) -> None:
        """Helper to schedule async callback."""
        try:
            # Schedule the callback in the event loop
            if asyncio.get_event_loop().is_running():
                asyncio.create_task(self.callback(event_type, data))
        except Exception:
            # Don't let streaming errors break the main process
            pass


class CSVOutputHandler(OutputHandler):
    """CSV file output handler - specialized for single-sheet data like ref_matcher logs."""

    def __init__(self, file_path: str):
        """Initialize with target CSV file path."""
        self.file_path = Path(file_path)
        self.data_rows = []
        self.headers = None
        self.sheet_name = None
        self.summary_data = {}
        self.file_references = {}
        self.metrics = {}

        # Ensure directory exists
        os.makedirs(self.file_path.parent, exist_ok=True)

    def add_sheet(self, name: str, df: pd.DataFrame, metadata: dict | None = None, is_critical: bool = False) -> None:
        """Add dataframe data to CSV (only supports single sheet)."""
        if self.headers is not None:
            # Already have data - CSV can only handle one sheet
            return

        self.sheet_name = name
        self.headers = df.columns.tolist()
        self.data_rows = df.values.tolist()

    def add_summary(self, key: str, data: dict[str, Any]) -> None:
        """Store summary data."""
        self.summary_data[key] = data

    def add_file_reference(self, name: str, path: str, description: str | None = None) -> None:
        """Store file reference."""
        self.file_references[name] = {"path": path, "description": description}

    def add_metric(self, key: str, value: Any, description: str | None = None) -> None:
        """Store metric."""
        self.metrics[key] = {"value": value, "description": description}

    def build(self) -> str:
        """Write CSV file and return the path."""
        if self.headers and self.data_rows:
            import csv

            with open(self.file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(self.headers)
                writer.writerows(self.data_rows)

        return str(self.file_path)

    def get_task_result_data(self) -> "TaskResultData":
        """Get TaskResultData for API task completion."""
        from wpp.api.models import FileReference, TaskResultData

        files = []
        if self.file_path.exists():
            files.append(FileReference(filename=self.file_path.name, file_type="csv", display_name=f"CSV Data - {self.sheet_name or 'Data'}"))

        return TaskResultData(files=files, summary=self.summary_data)


class NullOutputHandler(OutputHandler):
    """Null object pattern - does nothing. Useful for testing or when no output needed."""

    def add_sheet(self, name: str, df: pd.DataFrame, metadata: dict | None = None, is_critical: bool = False) -> None:
        pass

    def add_summary(self, key: str, data: dict[str, Any]) -> None:
        pass

    def add_file_reference(self, name: str, path: str, description: str | None = None) -> None:
        pass

    def add_metric(self, key: str, value: Any, description: str | None = None) -> None:
        pass

    def build(self) -> None:
        return None

    def get_task_result_data(self) -> "TaskResultData":
        """Return empty TaskResultData for null handler."""
        from wpp.api.models import TaskResultData

        return TaskResultData(files=[], summary={})
