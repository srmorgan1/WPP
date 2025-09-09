# WPP Management - FastAPI + React Version

This is a modern web application version of the WPP Management system, built with FastAPI backend and React frontend.

## Architecture

- **Backend**: FastAPI with Pydantic models, WebSocket support
- **Frontend**: React with Tailwind CSS, real-time updates
- **Communication**: REST API + WebSocket for real-time progress

## Quick Start

### 1. Install Python Dependencies

Make sure you have the existing WPP dependencies, then add FastAPI:

```bash
uv add fastapi uvicorn websockets
```

### 2. Start the FastAPI Backend

```bash
python run_fastapi.py
```

The API will be available at:
- http://localhost:8000 (API)
- http://localhost:8000/docs (Interactive API docs)
- ws://localhost:8000/ws (WebSocket)

### 3. Start the React Frontend

```bash
cd web
npm install
npm start
```

The web app will be available at http://localhost:3000

## Features

### ✅ Advantages over Streamlit

- **No script reloading** - Proper stateful application
- **Real-time progress** - WebSocket updates during long operations
- **Better UX** - Professional interface, proper loading states
- **Responsive design** - Works on mobile and desktop
- **API-first** - Can integrate with other tools/mobile apps
- **Production ready** - Proper error handling, logging

### 🔄 Database Operations

- Update database with real-time progress tracking
- View data import issues in interactive tables
- Monitor logs in scrollable viewer
- Option to delete existing database

### 📊 Report Generation  

- Select report dates with calendar picker
- Real-time progress during generation
- View generated reports in interactive tables
- Access generation logs

### 📈 Real-time Updates

- WebSocket connection for live progress updates
- Automatic reconnection on disconnect
- Progress bars with status indicators
- Live task monitoring

## API Endpoints

### System Status
- `GET /api/system/status` - System health and status

### Database Operations  
- `POST /api/database/update` - Start database update
- `GET /api/tasks/{task_id}` - Get task status and results

### Report Operations
- `POST /api/reports/generate` - Start report generation
- `GET /api/tasks/{task_id}` - Get task status and results

### File Operations
- `GET /api/files/excel/{file_path}` - Get Excel file data
- `GET /api/files/log/{file_path}` - Get log file content

### WebSocket
- `WS /ws` - Real-time progress updates

## File Structure

```
src/wpp/api/                # FastAPI backend
├── main.py                 # FastAPI app and endpoints
├── models.py              # Pydantic models
├── services.py            # Business logic services
└── __init__.py

web/                       # React frontend
├── src/
│   ├── components/        # Reusable components
│   ├── pages/            # Page components  
│   ├── services/         # API client
│   └── App.js            # Main app
├── package.json
└── README.md

run_fastapi.py             # Backend startup script
```

## Development

### Backend Development

The FastAPI server runs with auto-reload enabled. Changes to Python files will automatically restart the server.

### Frontend Development  

The React dev server provides hot reloading. Changes to JS/CSS files will update immediately in the browser.

### API Documentation

Visit http://localhost:8000/docs for interactive API documentation powered by Swagger UI.

## Production Deployment

### Backend
```bash
python run_fastapi.py
```

Or use a production WSGI server:
```bash
uvicorn wpp.api.main:app --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd web
npm run build
```

Serve the `web/build/` directory with a web server like nginx.

## Comparison with Streamlit

| Feature | Streamlit | FastAPI + React |
|---------|-----------|-----------------|
| Development Speed | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Real-time Updates | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| UI Flexibility | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Production Ready | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Mobile Support | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| API Integration | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| State Management | ⭐⭐ | ⭐⭐⭐⭐⭐ |

The FastAPI + React version provides a much more professional and flexible solution for production use.