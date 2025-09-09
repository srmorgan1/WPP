#!/bin/bash
# WPP API Server Startup Script
# Starts the FastAPI backend server independently

set -e  # Exit on any error

echo "🚀 Starting WPP API Server..."

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

# Change to src directory for proper module loading
cd src

echo "📡 Starting API server from source..."
echo "   API Endpoints: http://127.0.0.1:8000/api/*"
echo "   Documentation: http://127.0.0.1:8000/docs"
echo "   Health Check: http://127.0.0.1:8000/api/system/status"
echo ""
echo "💡 Press Ctrl+C to stop the server"
echo "⏱️  Server will auto-shutdown based on configured timeouts"
echo ""

# Start the API server in API-only mode
exec uv run python -m wpp.ui.react.web_app --api-only