"""Pydantic models for FastAPI application."""

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProgressUpdate(BaseModel):
    """WebSocket progress update message."""

    task_id: str
    status: TaskStatus
    progress: float = Field(ge=0.0, le=100.0, description="Progress percentage")
    message: str
    timestamp: datetime


class LogEntry(BaseModel):
    """Log entry model."""

    timestamp: datetime
    level: str
    message: str


class UpdateDatabaseRequest(BaseModel):
    """Request model for database update."""

    delete_existing: bool = Field(default=True, description="Whether to delete existing database")


class UpdateDatabaseResponse(BaseModel):
    """Response model for database update."""

    task_id: str
    status: TaskStatus
    message: str
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None


class GenerateReportsRequest(BaseModel):
    """Request model for report generation."""

    report_date: date | None = Field(default=None, description="Date for report generation (optional, defaults to unique date from charges table)")


class GenerateReportsResponse(BaseModel):
    """Response model for report generation."""

    task_id: str
    status: TaskStatus
    message: str
    started_at: datetime
    completed_at: datetime | None = None
    report_files: list[str] = Field(default_factory=list)
    error: str | None = None


class FileInfo(BaseModel):
    """File information model."""

    name: str
    path: str
    size: int
    created_at: datetime
    modified_at: datetime


class SpreadsheetData(BaseModel):
    """Spreadsheet data model."""

    sheet_name: str
    columns: list[str]
    data: list[list[Any]]
    is_critical: bool = Field(default=False, description="Whether this sheet contains critical errors that stop processing")


class ExcelFileData(BaseModel):
    """Excel file data model."""

    file_info: FileInfo
    sheets: list[SpreadsheetData]


class SystemStatus(BaseModel):
    """System status model."""

    database_exists: bool
    data_directory: str
    data_directory_exists: bool
    input_directory: str
    input_directory_exists: bool
    static_input_directory: str
    static_input_directory_exists: bool
    running_tasks: list[str] = Field(default_factory=list)
    uptime: float


class FileReference(BaseModel):
    """Reference to a file in the system."""

    filename: str
    file_type: str  # "excel" or "log"
    display_name: str | None = None


class TaskResultData(BaseModel):
    """Structured result data for tasks."""

    files: list[FileReference] = Field(default_factory=list)
    summary: dict[str, Any] | None = None


class TaskResult(BaseModel):
    """Generic task result model."""

    task_id: str
    task_type: str | None = None
    status: TaskStatus
    started_at: datetime
    completed_at: datetime | None = None
    result_data: TaskResultData | None = None
    error: str | None = None
    logs: list[LogEntry] = Field(default_factory=list)


class UpdateDirectoryRequest(BaseModel):
    """Request model for updating directory paths."""

    directory_path: str = Field(description="New directory path")


class UpdateDirectoryResponse(BaseModel):
    """Response model for updating directory paths."""

    success: bool
    message: str
    directory_type: str  # "input" or "static_input"


class WebSocketMessage(BaseModel):
    """WebSocket message model."""

    type: str  # "progress", "log", "complete", "error"
    task_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
