#!/bin/bash

# Development startup script for WPP Management Web Application
# Starts both FastAPI backend and React frontend for development
# 
# Usage: ./run_web_dev.sh
# Press Ctrl+C to stop both servers

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_section() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to cleanup background processes on exit
cleanup() {
    print_info "Shutting down servers..."
    
    # Kill background jobs
    jobs -p | xargs -r kill 2>/dev/null || true
    
    # Kill any remaining processes on our ports
    pkill -f "uvicorn" 2>/dev/null || true
    pkill -f "react-scripts start" 2>/dev/null || true
    
    print_success "All servers stopped."
    exit 0
}

# Set up trap to cleanup on script exit
trap cleanup INT TERM EXIT

print_section "🎯 WPP Management Development Startup"

# Check if we're in the right directory
if [[ ! -f "pyproject.toml" ]]; then
    print_error "Must run from project root directory (where pyproject.toml is located)"
    exit 1
fi

print_success "✓ Project root directory confirmed"

# Check prerequisites
print_section "🔍 Checking Prerequisites"

# Check Python/uv
if ! command_exists uv; then
    print_error "uv is not installed. Please install uv first:"
    print_info "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
print_success "✓ uv found: $(uv --version)"

# Check Node.js
NODE_AVAILABLE=false
if command_exists node; then
    NODE_VERSION=$(node --version)
    NPM_VERSION=$(npm --version)
    print_success "✓ Node.js found: $NODE_VERSION"
    print_success "✓ npm found: $NPM_VERSION"
    NODE_AVAILABLE=true
else
    print_warning "⚠ Node.js not found. React frontend will not be available."
    print_info "  Install Node.js from: https://nodejs.org/"
    print_info "  Or use API-only mode at http://localhost:8000/docs"
fi

# Setup Python environment
print_section "🐍 Setting Up Python Environment"

print_info "Syncing Python dependencies..."
if ! uv sync --dev; then
    print_error "Failed to sync Python environment"
    exit 1
fi

# Add FastAPI dependencies if not present
print_info "Ensuring FastAPI dependencies are available..."
uv add fastapi uvicorn websockets --quiet 2>/dev/null || true

print_success "✓ Python environment ready"

# Setup React environment (if Node.js available)
if $NODE_AVAILABLE; then
    print_section "⚛️  Setting Up React Environment"
    
    if [[ ! -d "web" ]]; then
        print_warning "Web directory not found. React frontend will not be available."
        NODE_AVAILABLE=false
    else
        cd web
        
        if [[ ! -d "node_modules" ]]; then
            print_info "Installing React dependencies..."
            if ! npm install; then
                print_error "Failed to install React dependencies"
                exit 1
            fi
        else
            print_info "React dependencies already installed"
        fi
        
        cd ..
        print_success "✓ React environment ready"
    fi
fi

# Display startup information
print_section "🚀 Starting Development Servers"

print_info "📋 Instructions:"
print_info "   • Both servers will start automatically"
print_info "   • Make changes to code - servers auto-reload"
print_info "   • Press Ctrl+C to stop all servers"

if $NODE_AVAILABLE; then
    print_info ""
    print_info "🌐 Available interfaces:"
    print_info "   • React UI: http://localhost:3000 (recommended)"
    print_info "   • API docs: http://localhost:8000/docs"
else
    print_info ""
    print_info "🔧 Available interfaces:"
    print_info "   • API docs: http://localhost:8000/docs (Node.js not available)"
fi

echo -e "\n=================================================="

# Start FastAPI backend
print_info "🚀 Starting FastAPI backend server..."
export PYTHONPATH="$(pwd)/src"

# Start FastAPI in background
(
    exec python run_fastapi.py 2>&1 | while IFS= read -r line; do
        echo -e "${CYAN}[API]${NC} $line"
    done
) &
API_PID=$!

# Wait a moment for API to start
sleep 3

# Start React frontend (if available)
if $NODE_AVAILABLE; then
    print_info "⚛️  Starting React frontend server..."
    
    # Start React in background
    (
        cd web
        export BROWSER=none  # Prevent automatic browser opening
        exec npm start 2>&1 | while IFS= read -r line; do
            echo -e "${GREEN}[React]${NC} $line"
        done
    ) &
    REACT_PID=$!
    
    # Wait for React to start, then open browser
    sleep 8
    print_info "🌐 Opening browser..."
    if command_exists open; then
        open http://localhost:3000 2>/dev/null || true
    elif command_exists xdg-open; then
        xdg-open http://localhost:3000 2>/dev/null || true
    elif command_exists firefox; then
        firefox http://localhost:3000 2>/dev/null || true
    elif command_exists chrome; then
        chrome http://localhost:3000 2>/dev/null || true
    else
        print_info "Please open your browser to: http://localhost:3000"
    fi
else
    print_info "🔧 API-only mode - visit http://localhost:8000/docs for API documentation"
    
    # Open API docs if React not available
    sleep 3
    if command_exists open; then
        open http://localhost:8000/docs 2>/dev/null || true
    elif command_exists xdg-open; then
        xdg-open http://localhost:8000/docs 2>/dev/null || true
    fi
fi

print_success "✅ Development servers started!"
print_info "Press Ctrl+C to stop all servers..."

# Wait for background processes
wait