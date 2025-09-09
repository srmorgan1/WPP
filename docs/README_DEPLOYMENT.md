# WPP Management - Deployment Guide

This document covers how to build and deploy the WPP Management application in different configurations.

## 📋 Overview

The WPP Management system can be built in three different ways, all using PyInstaller to create standalone executables that require no Python installation on the customer machine.

## 🎯 Deployment Options

### **Option 1: Full Web App (Recommended for Customers)**
```bash
python build_web_app.py
```

**What it does:**
- Builds React frontend for production
- Bundles FastAPI backend + React UI into single executable
- Creates professional web interface with real-time updates

**Requirements during build:**
- Node.js 16+ (for building React)
- Python with uv
- All project dependencies

**Customer gets:**
- `dist/wpp/wpp-web-app.exe` - Complete web application
- `dist/wpp/run-reports.exe` - CLI reports tool  
- `dist/wpp/update-database.exe` - CLI database tool
- Full web UI at http://localhost:8000
- **No Node.js or Python required on customer machine**

**Features:**
- ✅ Modern responsive web interface
- ✅ Real-time progress bars during operations
- ✅ Interactive data tables for Excel files
- ✅ Scrollable log viewers
- ✅ Professional navigation and routing
- ✅ Mobile-friendly design
- ✅ No script reloading issues

---

### **Option 2: API-Only (Fallback)**
```bash
python build_simple_exe.py
```

**What it does:**
- Creates API server without React frontend
- Smaller bundle size
- Provides REST API with auto-generated documentation

**Requirements during build:**
- Python with uv only (no Node.js needed)

**Customer gets:**
- `dist/wpp/wpp-web-api.exe` - API server
- `dist/wpp/run-reports.exe` - CLI reports tool
- `dist/wpp/update-database.exe` - CLI database tool
- API documentation at http://localhost:8000/docs

**Use when:**
- Node.js not available for building
- Want smaller deployment size
- Customer comfortable with API/Swagger interface

---

### **Option 3: Original Streamlit (Legacy)**
```bash
python build_executable.py
```

**What it does:**
- Builds original Streamlit version
- Same executable creation as before

**Customer gets:**
- `dist/wpp/wpp-streamlit.exe` - Streamlit web app
- CLI tools as above

**Known issues:**
- Script reloading problems
- Limited real-time capabilities
- CSS/styling conflicts

## 🚀 Build Process Details

### **How PyInstaller Works (Same for All Options)**

All build scripts follow the same PyInstaller process:

1. **Install PyInstaller**: `uv add --dev pyinstaller`
2. **Clean previous builds**: Remove `build/` and `dist/` directories
3. **Create spec file**: Define what to bundle and how
4. **Run PyInstaller**: `uv run -- pyinstaller [spec-file]`
5. **Bundle everything**: Python interpreter, dependencies, app code, assets

### **What Gets Bundled**

**All versions include:**
- Python interpreter
- All Python dependencies (pandas, openpyxl, etc.)
- WPP application code
- Configuration files
- Core business logic (UpdateDatabase, RunReports)

**Full Web App additionally includes:**
- React frontend (pre-built)
- Static assets (CSS, JS, images)
- FastAPI web server
- WebSocket support for real-time updates

## 📁 Final Customer Package

**Customer receives a single folder:**
```
dist/wpp/
├── wpp-web-app.exe          # Main web application (or wpp-web-api.exe)
├── run-reports.exe          # CLI reports tool
├── update-database.exe      # CLI database tool
├── [hundreds of dependency files bundled by PyInstaller]
└── [static assets if web version]
```

**Customer usage:**
1. Copy the `dist/wpp/` folder to their machine
2. Run `wpp-web-app.exe` (double-click or command line)
3. Browser opens automatically to http://localhost:8000
4. Full web interface available
5. **No installation required - everything is bundled**

## 🔧 Developer Build Instructions

### **For Full Web App (Recommended)**

**Prerequisites:**
- Node.js 16+ installed
- Python with uv
- All project dependencies

**Build steps:**
```bash
# Ensure you're in project root
cd /path/to/WPP

# Build everything (React + Python executables)
python build_web_app.py

# Result: dist/wpp/ folder ready for customer
```

### **For API-Only (Fallback)**

**Prerequisites:**
- Python with uv only

**Build steps:**
```bash
# Ensure you're in project root
cd /path/to/WPP

# Build API-only executables
python build_simple_exe.py

# Result: dist/wpp/ folder with API server
```

## 💡 Recommendations

**For customer deployment:**
1. **Use Option 1** (Full Web App) - provides best user experience
2. **Build on developer machine** with Node.js available
3. **Deliver `dist/wpp/` folder** to customer
4. **Customer just runs the executable** - no technical setup required

**For development/testing:**
- Use `python run_fastapi.py` and `cd web && npm start` for live development
- Use build scripts only for final packaging

## 🆚 Comparison with Streamlit Version

| Feature | Streamlit | FastAPI + React |
|---------|-----------|-----------------|
| **Development Speed** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Real-time Updates** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **UI Flexibility** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Production Ready** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Mobile Support** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **State Management** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Customer Experience** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Build Complexity** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

## 🚨 Troubleshooting

**If React build fails:**
- Use `build_simple_exe.py` instead
- Customer gets API with Swagger documentation
- Still fully functional, just different interface

**If PyInstaller fails:**
- Check all dependencies are installed
- Try cleaning build directories manually
- Ensure you're in project root directory

**On customer machine:**
- No Python installation needed
- No Node.js installation needed
- Just run the executable from the `dist/wpp/` folder