"""FastAPI application for WPP Management."""

from datetime import datetime

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .models import GenerateReportsRequest, GenerateReportsResponse, ProgressUpdate, SystemStatus, TaskResult, UpdateDatabaseRequest, UpdateDatabaseResponse, WebSocketMessage
from .services import DatabaseService, FileService, ReportsService, SystemService, task_manager

app = FastAPI(title="WPP Management API", description="API for WPP data management and reporting", version="1.0.0")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# WebSocket connections manager
class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                # Connection might be closed
                pass


manager = ConnectionManager()


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "WPP Management API", "version": "1.0.0"}


@app.get("/api/system/status", response_model=SystemStatus)
async def get_system_status():
    """Get current system status."""
    return await SystemService.get_system_status()


@app.post("/api/database/update", response_model=UpdateDatabaseResponse)
async def update_database(request: UpdateDatabaseRequest):
    """Start database update task."""
    try:
        # Create progress callback for WebSocket updates
        async def progress_callback(update: ProgressUpdate):
            message = WebSocketMessage(type="progress", task_id=update.task_id, data={"progress": update.progress, "message": update.message, "status": update.status})
            await manager.broadcast(message.model_dump_json())

        task_id = await DatabaseService.update_database(delete_existing=request.delete_existing, progress_callback=progress_callback)

        return UpdateDatabaseResponse(task_id=task_id, status="pending", message="Database update started", started_at=datetime.now())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reports/generate", response_model=GenerateReportsResponse)
async def generate_reports(request: GenerateReportsRequest):
    """Start report generation task."""
    try:
        # Create progress callback for WebSocket updates
        async def progress_callback(update: ProgressUpdate):
            message = WebSocketMessage(type="progress", task_id=update.task_id, data={"progress": update.progress, "message": update.message, "status": update.status})
            await manager.broadcast(message.model_dump_json())

        task_id = await ReportsService.generate_reports(report_date=request.report_date, progress_callback=progress_callback)

        return GenerateReportsResponse(task_id=task_id, status="pending", message="Report generation started", started_at=datetime.now())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tasks/{task_id}", response_model=TaskResult)
async def get_task_status(task_id: str):
    """Get task status and results."""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/api/files/excel/{filename}")
async def get_excel_data(filename: str):
    """Get Excel file data from Reports directory."""
    import os

    from wpp.config import get_wpp_report_dir

    # Construct full path in reports directory
    reports_dir = get_wpp_report_dir()
    file_path = os.path.join(reports_dir, filename)

    data = await FileService.get_excel_data(file_path)
    if not data:
        raise HTTPException(status_code=404, detail="File not found or cannot be read")
    return data


@app.get("/api/files/log/{filename}")
async def get_log_content(filename: str):
    """Get log file content from Logs directory."""
    import os

    from wpp.config import get_wpp_log_dir

    # Construct full path in logs directory
    log_dir = get_wpp_log_dir()
    file_path = os.path.join(log_dir, filename)

    content = await FileService.get_log_content(file_path)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {"content": content, "filename": filename}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle any client messages
            data = await websocket.receive_text()
            # Echo back for now - could handle commands here
            await manager.send_personal_message(f"Message received: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Mount static files for React app (in production)
# app.mount("/", StaticFiles(directory="web/build", html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
