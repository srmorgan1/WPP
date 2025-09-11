# Streamlit Removal Guide

This document outlines the steps needed to completely remove Streamlit code from the WPP project without affecting other functionality.

## Difficulty Level: **Low to Moderate** 

The React web app has completely replaced Streamlit functionality, so removal would eliminate legacy code without functional impact.

## What Needs to Be Removed

**1. Main Streamlit Files:**
- `src/wpp/ui/streamlit/` directory (entire Streamlit UI implementation)
- References in PyInstaller configs (`build_executable.py`)
- Streamlit-specific runtime hooks

**2. Dependencies:**
- `streamlit` package from `pyproject.toml`
- Any streamlit-related imports in other modules

**3. Entry Points:**
- `wpp-streamlit` executable definition
- Streamlit-specific command line interfaces

## What Would NOT Be Affected

✅ **Core Business Logic**: `UpdateDatabase.py`, `RunReports.py` - these are framework-agnostic  
✅ **React Web App**: Completely separate UI implementation  
✅ **API Layer**: FastAPI backend is independent  
✅ **Database Layer**: Database providers work with any UI  
✅ **CLI Tools**: Command-line interfaces are separate  

## Step-by-Step Removal Process

### 1. **Search and Identify All Streamlit References**
```bash
# Find all Streamlit-related files and references
grep -r "streamlit" --include="*.py" src/
grep -r "wpp-streamlit" .
grep -r "streamlit" *.py *.toml *.md
```

### 2. **Remove Streamlit Files and Directories**
- Delete `src/wpp/ui/streamlit/` directory entirely
- Remove any Streamlit-specific runtime hooks (e.g., `rthook_streamlit.py`)

### 3. **Clean Up Dependencies**
- Remove `streamlit` from `pyproject.toml` dependencies
- Run `uv sync` to update lock files
- Remove any streamlit-related packages that are no longer needed

### 4. **Update PyInstaller Configuration**
In `build_executable.py`:
- Remove `wpp-streamlit` from executable definitions
- Remove Streamlit-specific data files and hiddenimports
- Remove Streamlit runtime hooks
- Clean up any Streamlit-specific pathex or datas entries

### 5. **Update Entry Points and Scripts**
- Remove `wpp-streamlit` from `pyproject.toml` `[project.scripts]` section
- Remove any shell scripts that launch Streamlit
- Update documentation that references Streamlit

### 6. **Clean Up Import Statements**
Check these files for streamlit imports:
- `src/wpp/ui/__init__.py`
- Any modules that might import streamlit utilities
- Remove unused import statements

### 7. **Update Process Cleanup**
In `run_fastapi.py`, remove `wpp-streamlit` from:
- `expected_wpp_process_names` list
- `expected_wpp_cmdline_patterns` list

### 8. **Update Documentation and Comments**
- Remove Streamlit references from README files
- Update code comments that mention Streamlit
- Clean up any Streamlit-related configuration examples

### 9. **Verification Steps**
- Test that CLI tools still work: `python -m wpp.UpdateDatabase`
- Test that React web app still works: `./run_web_app.sh`
- Test PyInstaller builds: `python build_executable.py`
- Run any existing tests to ensure no breakage

### 10. **Git Cleanup**
- Consider if any Streamlit-related git history should be preserved
- Update .gitignore if it has Streamlit-specific entries

## Estimated Effort

- **File Removal**: 10-15 minutes
- **Dependency Cleanup**: 5 minutes  
- **PyInstaller Config**: 10 minutes
- **Testing**: 15-20 minutes to verify nothing breaks

**Total**: ~45-60 minutes of careful work

## Key Success Factors

The key is being thorough with the search phase first - find every reference before starting deletions to avoid breaking hidden dependencies. The architecture's clean separation of concerns (database providers, core business logic, UI layers) makes this a relatively safe operation.