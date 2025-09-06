# WPP Development Guide

This guide covers how to develop and test the WPP Management system, especially if you're not familiar with React.

## 🚀 Quick Start (No React Knowledge Needed)

### **Option 1: Test the New Web App (Easiest)**

```bash
# 1. Start the backend API
python run_fastapi.py

# 2. In another terminal, start the React frontend
cd web
npm install
npm start

# 3. Browser opens automatically at http://localhost:3000
```

That's it! The React app will automatically reload when you change files.

### **Option 2: Just Test the API (No React)**

```bash
# Start just the FastAPI backend
python run_fastapi.py

# Visit http://localhost:8000/docs for interactive API testing
```

### **Option 3: Original Streamlit (Fallback)**

```bash
# Use the original version
PYTHONPATH=src uv run streamlit run src/wpp/ui/streamlit/app.py
```

## 🛠 Development Workflow

### **Backend Changes (Python)**

When you modify Python code in `src/wpp/`:

1. **API changes**: FastAPI server auto-reloads (if running `python run_fastapi.py`)
2. **Core logic**: UpdateDatabase, RunReports, etc. - changes apply immediately
3. **Config changes**: Restart the server

### **Frontend Changes (React)**

When React is running (`npm start`), it automatically reloads when you change:

- Any file in `web/src/`
- CSS, JavaScript, or component files

**You don't need to understand React** - just modify the text/styling and it updates live.

### **Quick Frontend Edits (No React Knowledge)**

Want to change text or styling? Here are the key files:

**Change page titles or text:**
```javascript
// web/src/pages/Dashboard.js
<h2 className="text-2xl font-bold text-gray-900 mb-4">
  📊 WPP Management Dashboard  // ← Change this text
</h2>
```

**Change colors or styling:**
```css
/* web/src/index.css */
.btn-primary {
  background-color: #3b82f6;  /* ← Change button color */
}
```

**Change navigation:**
```javascript
// web/src/App.js - around line 20
const navItems = [
  { path: '/', icon: Home, label: 'Dashboard' },     // ← Change labels
  { path: '/database', icon: Database, label: 'Database' },
  { path: '/reports', icon: BarChart3, label: 'Reports' },
];
```

## 🧪 Testing Your Changes

### **Test Backend Changes**

```bash
# Run the API
python run_fastapi.py

# Test endpoints at http://localhost:8000/docs
# Or use the React frontend to test visually
```

### **Test Frontend Changes**

```bash
# Start both backend and frontend
python run_fastapi.py     # Terminal 1
cd web && npm start       # Terminal 2

# Browser auto-opens, changes appear instantly
```

### **Test Complete Integration**

```bash
# Build and test the packaged version
python build_web_app.py

# Run the built executable
./dist/wpp/wpp-web-app
```

## 📁 File Structure (What You Need to Know)

```
src/wpp/api/           # FastAPI backend (your Python domain)
├── main.py           # API endpoints
├── services.py       # Business logic (calls your UpdateDatabase, RunReports)
└── models.py         # Data structures

web/src/              # React frontend (auto-reloads, minimal changes needed)
├── pages/            # Main pages (Dashboard, Database, Reports)
├── components/       # Reusable UI pieces (tables, progress bars)
└── services/api.js   # Connects frontend to your API

src/wpp/ui/react/     # Unified app (combines API + React for packaging)
└── web_app.py        # Single executable entry point
```

## 🎯 Common Development Tasks

### **Add a New API Endpoint**

1. **Add to `src/wpp/api/main.py`:**
```python
@app.get("/api/my-new-endpoint")
async def my_new_function():
    # Your logic here
    return {"message": "Hello from new endpoint"}
```

2. **Test at:** http://localhost:8000/docs

3. **Add to React** (optional):
```javascript
// web/src/services/api.js
async getMyNewData() {
  const response = await api.get('/api/my-new-endpoint');
  return response.data;
}
```

### **Change How Reports Look**

1. **Modify the backend data** in `src/wpp/RunReports.py` (your existing code)
2. **Frontend automatically picks up changes** - no React knowledge needed

### **Add a New Page**

1. **Add API endpoint** (as above)
2. **Copy `web/src/pages/Dashboard.js`** to `MyNewPage.js`
3. **Change the content**, keep the structure
4. **Add to navigation** in `web/src/App.js`

## 🐛 Debugging

### **Backend Issues**

- Check terminal running `python run_fastapi.py`
- Visit http://localhost:8000/docs to test API directly
- Add `print()` statements in your Python code

### **Frontend Issues**

- Check terminal running `npm start`
- Open browser Developer Tools (F12)
- Look at Console tab for errors
- Network tab shows API calls

### **Integration Issues**

- Make sure both servers are running (Python + React)
- Check they're on correct ports (8000 + 3000)
- Restart both if things get stuck

## 📦 Building for Customer

### **Full Web App (Recommended)**

```bash
python build_web_app.py
# Creates: dist/wpp/wpp-web-app.exe (complete web interface)
```

### **API-Only (Fallback)**

```bash
python build_simple_exe.py  
# Creates: dist/wpp/wpp-web-api.exe (API + docs only)
```

### **Automated Build (Windows)**

```powershell
.\build_web_deployment.ps1
# Installs Node.js, builds everything automatically
```

## 💡 Tips for Non-React Developers

1. **Focus on the Python backend** - that's where your business logic lives
2. **React frontend** mostly just displays your data nicely
3. **Use the API docs** at http://localhost:8000/docs to test without React
4. **Make small changes** to React files and see what happens
5. **Copy-paste similar code** rather than writing from scratch
6. **The build process handles everything** - you don't need to understand bundling/deployment

## 🆘 When Things Go Wrong

**React won't start:**
```bash
cd web
rm -rf node_modules package-lock.json
npm install
npm start
```

**API won't start:**
```bash
# Check dependencies
uv sync

# Try running directly
PYTHONPATH=src python src/wpp/api/main.py
```

**Build fails:**
```bash
# Try API-only version
python build_simple_exe.py

# Or original Streamlit
python build_executable.py
```

**Most importantly:** You can always fall back to the original Streamlit version while developing the new web interface!