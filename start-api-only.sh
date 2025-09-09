#!/bin/bash
# WPP API-Only Server Startup Script  
# Starts the FastAPI backend without React frontend (pure API mode)

set -e  # Exit on any error

echo "🔧 Starting WPP API Server (API-Only Mode)..."

# Check if we're in the right directory
if [ ! -f "src/wpp/ui/react/web_app.py" ]; then
    echo "❌ Error: Please run this script from the WPP project root directory"
    echo "   Expected to find: src/wpp/ui/react/web_app.py"
    exit 1
fi

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv package manager not found"
    echo "   Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Temporarily disable React frontend by moving build directory
echo "🚫 Temporarily disabling React frontend for API-only mode..."
if [ -d "web/build" ]; then
    mv web/build web/build-temp-disabled
    FRONTEND_DISABLED=true
    echo "   React frontend disabled (pure API mode)"
else
    FRONTEND_DISABLED=false
    echo "   React frontend already disabled"
fi

# Function to cleanup on exit
cleanup() {
    if [ "$FRONTEND_DISABLED" = true ]; then
        echo ""
        echo "🔄 Re-enabling React frontend..."
        mv web/build-temp-disabled web/build
        echo "✅ React frontend restored"
    fi
}

# Set up cleanup trap
trap cleanup EXIT

# Change to src directory for proper module loading
cd src

echo ""
echo "📡 Starting API-only server..."
echo "   Mode: Pure API (No Web Interface)"
echo "   API Endpoints: http://127.0.0.1:8000/api/*"
echo "   Documentation: http://127.0.0.1:8000/docs"  
echo "   Health Check: http://127.0.0.1:8000/api/system/status"
echo ""
echo "💡 Press Ctrl+C to stop the server"
echo "⏱️  Server will auto-shutdown based on configured timeouts"
echo ""

# Start the API server
exec uv run python -m wpp.ui.react.web_app