# WPP Build Instructions

This document describes how to use the automated CI/CD build pipeline for the WPP project.

## Quick Start

### Double-Click Method (Easiest)

**For CI/CD builds (clone from GitHub):**
- `BUILD_WPP.bat` - Full build with tests
- `BUILD_WPP_QUICK.bat` - Quick build without tests

**For local builds (current directory):**
- `build_executable.bat` - Build from current project directory

### PowerShell Method (Advanced)

```powershell
.\build_and_deploy.ps1
```

## Build Types

### CI/CD Builds (Full Pipeline)
- Clone fresh code from GitHub
- Set up clean Python environment
- Run comprehensive tests
- Build executables

### Local Builds (Development)
- Use current project directory
- Skip repository cloning
- Faster for development iteration
- Assumes dependencies already set up

## Prerequisites

### Minimum Requirements (Fresh Machine)
- **Windows PowerShell 5.1+** or **PowerShell Core 7+**
- **Git for Windows** - [Download here](https://git-scm.com/download/win)
- **Internet connection** - For downloading dependencies

### Auto-Managed Dependencies
- **Python 3.13+** - Automatically downloaded by uv based on `pyproject.toml`
- **uv package manager** - Auto-installed if not present (standalone binary)
- **All Python packages** - Managed by uv in isolated environment

### Environment Variables

#### Authentication (Optional)
- **GIT_TOKEN** - GitHub Personal Access Token for private repository access
  - **Without token**: Git opens browser for authentication (interactive)
  - **With token**: Fully automated, no prompts

#### Testing (Optional)
- **GPG_PASSPHRASE** - Required only if tests use encrypted test data

## Script Parameters

### Basic Usage
```powershell
# Default build (uses master branch)
.\build_and_deploy.ps1

# Build specific branch
.\build_and_deploy.ps1 -Branch "development"

# Skip tests for faster build
.\build_and_deploy.ps1 -SkipTests

# Automated build with token (no prompts)
$env:GIT_TOKEN = "ghp_your_token"; .\build_and_deploy.ps1

# Custom working directory
.\build_and_deploy.ps1 -WorkDir "D:\builds\wpp"
```

### Parameters Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `-RepoUrl` | String | `https://github.com/srmorgan1/WPP.git` | GitHub repository URL |
| `-Branch` | String | `master` | Git branch to build |
| `-WorkDir` | String | `C:\temp\wpp-build` | Build working directory |
| `-SkipTests` | Switch | `false` | Skip running tests |
| `-CleanWorkDir` | Switch | `false` | Clean working directory before build |
| `-KeepRepo` | Switch | `false` | Keep repository after build |

### Advanced Examples

```powershell
# Clean build with custom branch
.\build_and_deploy.ps1 -Branch "feature/new-reports" -CleanWorkDir

# Fast build without tests, keep repo for debugging
.\build_and_deploy.ps1 -SkipTests -KeepRepo

# Automated CI/CD build
$env:GIT_TOKEN = "${{ secrets.GIT_TOKEN }}"; .\build_and_deploy.ps1 -SkipTests -CleanWorkDir

# Build from fork
.\build_and_deploy.ps1 -RepoUrl "https://github.com/yourusername/WPP.git" -Branch "main"
```

## Build Process

The script follows this pipeline:

1. **Prerequisites Check**
   - Verifies Git is available
   - Auto-installs uv package manager if missing (standalone binary)

2. **Repository Setup**
   - Uses GIT_TOKEN if available for automated authentication
   - Clones or updates the repository
   - Switches to specified branch

3. **Environment Setup**
   - uv automatically downloads Python 3.13+ based on `pyproject.toml`
   - Creates isolated Python environment with uv
   - Installs all dependencies including dev dependencies

4. **Testing** (unless `-SkipTests`)
   - Runs pytest with coverage
   - Performs code quality checks with ruff

5. **Building**
   - Calls existing `build_executable.ps1` script
   - Creates standalone Windows executables

6. **Verification**
   - Confirms all expected executables were created
   - Displays file sizes and usage instructions

## Output

### Executable Files
The build creates these standalone Windows executables in `dist\wpp\`:

- **wpp-streamlit.exe** - Streamlit web application
- **run-reports.exe** - Command-line reports generator  
- **update-database.exe** - Database update utility

### Usage
```cmd
# Start web application
.\dist\wpp\wpp-streamlit.exe

# Generate reports
.\dist\wpp\run-reports.exe

# Update database
.\dist\wpp\update-database.exe
```

## Troubleshooting

### Common Issues

**"Git not found"**
- Install Git for Windows and ensure it's in PATH
- Restart PowerShell/Command Prompt after installation

**"Authentication required"**
- For private repositories without GIT_TOKEN: Git will open browser for login
- For automated builds: Set `$env:GIT_TOKEN = "ghp_your_token"`
- Create token at: GitHub → Settings → Developer settings → Personal access tokens

**"ExecutionPolicy error" (when using PowerShell directly)**
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```
*Note: The batch files handle this automatically*

**"BUILD_WPP.bat won't run"**
- Right-click the .bat file → "Run as administrator"
- Or use BUILD_WPP_QUICK.bat for a simpler version

**"Tests failing with GPG errors"**
```powershell
$env:GPG_PASSPHRASE = "your-passphrase"
.\build_and_deploy.ps1
```

**"uv installation failed"**
- Check internet connectivity
- Try manual installation: https://docs.astral.sh/uv/getting-started/installation/
- uv installs as standalone binary (~20MB download)

**"Python not found" (after uv installation)**
- This is normal - uv will download Python 3.13+ automatically on first use
- No manual Python installation required

### Build Locations

- **Working Directory**: `C:\temp\wpp-build` (default)
- **Repository**: `C:\temp\wpp-build\WPP`
- **Executables**: `C:\temp\wpp-build\WPP\dist\wpp\`

### Clean Up

```powershell
# Remove build directory
Remove-Item -Path "C:\temp\wpp-build" -Recurse -Force

# Or use the CleanWorkDir parameter
.\build_and_deploy.ps1 -CleanWorkDir
```

## Authentication Setup

### GitHub Personal Access Token

For automated builds or private repositories, create a GitHub Personal Access Token:

1. **GitHub.com** → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. **Generate new token (classic)**
3. **Select scopes**:
   - `repo` (for private repositories)
   - `public_repo` (for public repositories only)
4. **Copy the token** (starts with `ghp_`)
5. **Set environment variable**:
   ```powershell
   $env:GIT_TOKEN = "ghp_your_copied_token_here"
   ```

### Usage Examples

```powershell
# Interactive (browser authentication for private repos)
.\build_and_deploy.ps1

# Automated (no prompts)
$env:GIT_TOKEN = "ghp_your_token"; .\build_and_deploy.ps1

# Permanent token (for development machine)
[Environment]::SetEnvironmentVariable("GIT_TOKEN", "ghp_your_token", "User")
```

## CI/CD Integration

This script can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions usage
- name: Build Windows Executables
  run: |
    $env:GIT_TOKEN = "${{ secrets.GIT_TOKEN }}"
    $env:GPG_PASSPHRASE = "${{ secrets.GPG_PASSPHRASE }}"
    .\build_and_deploy.ps1 -SkipTests -CleanWorkDir
  shell: pwsh
```

For automated environments, consider using `-SkipTests` if test data setup is complex.

## Support

For issues with the build script:
1. Check the troubleshooting section above
2. Verify all prerequisites are correctly installed
3. Review error messages - the script provides detailed diagnostics
4. Test individual components (Git, Python, uv) separately

The script includes comprehensive error handling and will provide specific guidance when issues occur.