# WPP Build Makefile
# Provides clean, standardized build targets with intelligent dependency tracking
# Only rebuilds when source files actually change

# Source file patterns for dependency tracking
PYTHON_SOURCES := $(shell find src -name "*.py" 2>/dev/null)
TEST_SOURCES := $(shell find tests -name "*.py" 2>/dev/null)
REACT_SOURCES := $(shell find web/src -name "*.js" -o -name "*.jsx" -o -name "*.ts" -o -name "*.tsx" 2>/dev/null)
CONFIG_FILES := pyproject.toml wpp_web.spec web/package.json web/package-lock.json src/wpp/config.toml
SCRIPT_FILES := $(wildcard *.sh *.ps1)

# Build marker directory for tracking timestamps
.build-markers:
	@mkdir -p .build-markers

# Define the actual executable files we expect
EXECUTABLES := dist/wpp/wpp-web-app dist/wpp/run-reports dist/wpp/update-database

# Phony targets (always run, no file dependencies)
.PHONY: clean help test lint format force-clean deploy-to-windows

# Default target shows help
all: help

# Clean build artifacts, cache files, and build markers
clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf .build-markers/
	find src -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find src -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Clean completed"

# Intelligent build targets with dependency tracking

# Python wheel - only rebuild if Python sources or config changed
.build-markers/wheel-built: $(PYTHON_SOURCES) $(CONFIG_FILES) | .build-markers
	@echo "📦 Building Python wheel (sources changed)..."
	uv build --wheel
	@echo "✅ Wheel built: $(shell ls dist/*.whl 2>/dev/null || echo 'dist/*.whl')"
	@touch $@

# React frontend - only rebuild if React sources changed  
.build-markers/react-built: $(REACT_SOURCES) web/package.json web/package-lock.json | .build-markers
	@echo "⚛️  Building React frontend (sources changed)..."
	@if ! command -v node >/dev/null 2>&1; then \
		echo "❌ Error: Node.js not found"; \
		echo "   Install Node.js from: https://nodejs.org/"; \
		exit 1; \
	fi
	@if [ ! -f "web/package.json" ]; then \
		echo "❌ Error: web/package.json not found"; \
		exit 1; \
	fi
	cd web && npm install
	cd web && npm run build
	@echo "✅ React frontend built successfully"
	@touch $@

# PyInstaller executables - rebuild if dependencies changed OR if executables don't exist
.build-markers/executables-built: .build-markers/wheel-built .build-markers/react-built wpp_web.spec $(SCRIPT_FILES) $(EXECUTABLES) | .build-markers
	@echo "🔨 Building PyInstaller executables (dependencies changed)..."
	uv run pyinstaller wpp_web.spec --clean --noconfirm
	@echo "🎯 Executables built:"
	@ls -lh dist/wpp/*.exe dist/wpp/wpp-* dist/wpp/run-* dist/wpp/update-* 2>/dev/null || ls -lh dist/wpp/
	@echo "📁 Total size: $(shell du -sh dist/wpp/ | cut -f1)"
	@touch $@

# Force executables to be rebuilt if they don't exist
$(EXECUTABLES):
	@echo "📁 Executable missing: $@ - will trigger rebuild"

# Deployment package - only rebuild if executables changed
.build-markers/deployment-built: .build-markers/executables-built | .build-markers
	@echo "📦 Creating comprehensive deployment package (build changed)..."
	@mkdir -p dist
	@rm -f dist/wpp-deployment.zip
	@echo "📦 Packaging wheels + executables + dependencies..."
	@cd dist && zip -9 -r wpp-deployment.zip *.whl wpp/
	@if [ -f "dist/wpp-deployment.zip" ]; then \
		SIZE=$$(du -h dist/wpp-deployment.zip | cut -f1); \
		echo "✅ Deployment package created: dist/wpp-deployment.zip ($$SIZE)"; \
		echo "📦 Contents: Python wheels + executables + dependencies"; \
	else \
		echo "❌ Failed to create deployment package"; \
		exit 1; \
	fi
	@touch $@

# Public build targets that use dependency tracking
build-wheel: .build-markers/wheel-built
	@echo "✅ Python wheel is up to date"

build-react: .build-markers/react-built  
	@echo "✅ React frontend is up to date"

build-exe: .build-markers/executables-built
	@echo "✅ Executables are up to date"

build-all: .build-markers/deployment-built
	@echo ""
	@echo "🎉 BUILD COMPLETED SUCCESSFULLY!"
	@echo ""
	@echo "📦 Available artifacts:"
	@echo "  Wheel: $(shell ls dist/*.whl 2>/dev/null || echo 'None')"
	@echo "  Web App: dist/wpp/wpp-web-app"
	@echo "  CLI Tools: dist/wpp/run-reports, dist/wpp/update-database"
	@echo "  Deployment: dist/wpp-deployment.zip"
	@echo ""
	@echo "🚀 To test: ./dist/wpp/wpp-web-app"

# Development targets
test:
	@echo "🧪 Running tests..."
	uv run pytest tests/ -v

lint:
	@echo "🔍 Running linter..."
	uv run ruff check src/

format:
	@echo "✨ Formatting code..."
	uv run ruff format src/

# Quick build for development (assumes React already built, only checks Python changes)
quick-build: .build-markers/wheel-built wpp_web.spec $(SCRIPT_FILES) | .build-markers
	@echo "⚡ Quick build (assumes React already built)..."
	@if [ ! -d "web/build" ]; then \
		echo "❌ Error: React build not found at web/build/"; \
		echo "   Run 'make build-react' first for initial React build"; \
		exit 1; \
	fi
	@echo "🔨 Building executables (Python/config changed, skipping React check)..."
	uv run pyinstaller wpp_web.spec --clean --noconfirm
	@echo "🎯 Quick build executables ready:"
	@ls -lh dist/wpp/*.exe dist/wpp/wpp-* dist/wpp/run-* dist/wpp/update-* 2>/dev/null || ls -lh dist/wpp/
	@echo "⚡ Quick build completed - React dependency skipped for speed"

# Force rebuild everything (ignores timestamps)
force-rebuild:
	@echo "🔄 Force rebuilding everything (ignoring timestamps)..."
	rm -rf .build-markers/
	$(MAKE) build-all

# Create deployment zip (uses dependency tracking)
create-deployment-zip: .build-markers/deployment-built
	@echo "✅ Deployment package is up to date"

# Bundle Windows build files for transfer to Windows machines
bundle-windows-build:
	@echo "📦 Creating Windows build bundle..."
	@mkdir -p dist
	@rm -f dist/wpp-windows-build.zip
	@mkdir -p temp_bundle/wpp-windows-build
	@cp build_and_deploy.ps1 build_and_deploy_simple.ps1 install_prerequisites.ps1 BUILD_WPP.bat BUILD_WPP_SIMPLE.bat temp_bundle/wpp-windows-build/
	@cd temp_bundle && zip -r ../dist/wpp-windows-build.zip wpp-windows-build/
	@rm -rf temp_bundle
	@echo "✅ Windows build bundle created: dist/wpp-windows-build.zip"
	@echo ""
	@echo "📁 Bundle contents:"
	@echo "  build_and_deploy.ps1        - Full CI/CD script"
	@echo "  build_and_deploy_simple.ps1 - Windows-compatible script"  
	@echo "  install_prerequisites.ps1   - One-time Windows setup"
	@echo "  BUILD_WPP.bat               - Full build entry point"
	@echo "  BUILD_WPP_SIMPLE.bat        - Simple build entry point"
	@echo ""
	@echo "🚀 Transfer to Windows machine and run:"
	@echo "  1. Double-click BUILD_WPP_SIMPLE.bat (recommended)"
	@echo "  2. Or: BUILD_WPP.bat for full build"

# Deploy Windows build bundle to Parallels shared directory
deploy-to-windows: bundle-windows-build
	@echo "🚚 Deploying Windows build bundle to Parallels..."
	@mkdir -p ~/Documents/Work/WPP
	@cp dist/wpp-windows-build.zip ~/Documents/Work/WPP/
	@echo "✅ Deployment completed!"
	@echo ""
	@echo "📁 Deployed to: ~/Documents/Work/WPP/wpp-windows-build.zip"
	@echo "🖥️  Parallels users: File is now available in Windows"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Open Windows in Parallels"
	@echo "  2. Navigate to the shared WPP folder"
	@echo "  3. Extract wpp-windows-build.zip"
	@echo "  4. Double-click BUILD_WPP_SIMPLE.bat"

# Show build status and dependencies
status:
	@echo "📊 WPP Build Status"
	@echo ""
	@echo "Source Files:"
	@echo "  Python sources: $(words $(PYTHON_SOURCES)) files"
	@echo "  Test sources: $(words $(TEST_SOURCES)) files"  
	@echo "  React sources: $(words $(REACT_SOURCES)) files"
	@echo ""
	@echo "Build Status:"
	@if [ -f .build-markers/wheel-built ]; then \
		echo "  ✅ Python wheel: Built ($(shell stat -f "%Sm" .build-markers/wheel-built))"; \
	else \
		echo "  ❌ Python wheel: Not built"; \
	fi
	@if [ -f .build-markers/react-built ]; then \
		echo "  ✅ React frontend: Built ($(shell stat -f "%Sm" .build-markers/react-built))"; \
	else \
		echo "  ❌ React frontend: Not built"; \
	fi
	@if [ -f .build-markers/executables-built ]; then \
		echo "  ✅ Executables: Built ($(shell stat -f "%Sm" .build-markers/executables-built))"; \
	else \
		echo "  ❌ Executables: Not built"; \
	fi
	@if [ -f .build-markers/deployment-built ]; then \
		echo "  ✅ Deployment: Ready ($(shell stat -f "%Sm" .build-markers/deployment-built))"; \
	else \
		echo "  ❌ Deployment: Not ready"; \
	fi

# Show help
help:
	@echo "WPP Build Makefile with Intelligent Dependencies"
	@echo "Only rebuilds when source files actually change"
	@echo ""
	@echo "Available targets:"
	@echo "  make clean         - Clean build artifacts and dependency cache"
	@echo "  make build-wheel   - Build Python wheel (if sources changed)"
	@echo "  make build-react   - Build React frontend (if sources changed)"  
	@echo "  make build-exe     - Build PyInstaller executables (if deps changed)"
	@echo "  make build-all     - Build everything intelligently (recommended)"
	@echo "  make quick-build   - Fast development build (skips React dependency check)"
	@echo "  make force-rebuild - Force rebuild everything (ignore timestamps)"
	@echo "  make create-deployment-zip - Create deployment package (if needed)"
	@echo "  make bundle-windows-build - Bundle Windows build files"
	@echo "  make deploy-to-windows - Deploy Windows build to Parallels shared folder"
	@echo "  make status        - Show current build status"
	@echo "  make test          - Run tests"
	@echo "  make lint          - Run linter" 
	@echo "  make format        - Format code"
	@echo "  make help          - Show this help"
	@echo ""
	@echo "Dependency Tracking:"
	@echo "  🔍 Tracks: Python sources, React sources, config files, scripts"
	@echo "  ⚡ Speed: Only rebuilds changed components"
	@echo "  📊 Status: Run 'make status' to see what needs rebuilding"
	@echo ""
	@echo "Examples:"
	@echo "  make build-all      # Smart production build"
	@echo "  make status         # Check what needs rebuilding"
	@echo "  make force-rebuild  # Force rebuild everything"
	@echo "  make clean          # Start fresh"