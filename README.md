# WPP Service Charge Reconciliation System

A comprehensive system for processing property management data, reconciling bank transactions, and generating service charge reports.

## Overview

The WPP system processes property management data from multiple sources including:
- Qube property management system exports
- Bank of Scotland transaction and balance files
- Property, tenant, and estate data
- Manual reference data

It generates reconciliation reports and maintains a database for historical tracking.

## Installation

### Requirements
- Python 3.13.0+
- Dependencies listed in `pyproject.toml`

### Setup
```bash
# Clone the repository
git clone <repository-url>
cd WPP

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .
```

## Configuration

The system uses a `config.toml` file for configuration. The system searches for this file in the following order:

1. **Current working directory** (`./config.toml`) - **Recommended for production**
2. **Module directory** (`src/wpp/config.toml`) - Default development location

### Configuration Structure
```toml
[DIRECTORIES]
# Root directories (OS-specific)
WPP_ROOT_DIR_POSIX = "/data/wpp"
WPP_ROOT_DIR_WINDOWS = "C:\\WPP\\Data"

[INPUTS]
# Input file patterns (wildcards supported)
TENANTS_FILE_PATTERN = "Tenants*.xlsx"
ESTATES_FILE_PATTERN = "Estates*.xlsx"
QUBE_EOD_BALANCES_PATTERN = "Qube*EOD*.xlsx"
BOS_TRANSACTIONS_PATTERN = "PreviousDayTransactionExtract_*.zip"
# ... more patterns

[REPORTS]
# Output file naming templates
WPP_REPORT_TEMPLATE = "WPP_Report_{date}.xlsx"
DATA_IMPORT_ISSUES_TEMPLATE = "Data_Import_Issues_{date}.xlsx"
```

### Directory Structure
```
{WPP_ROOT_DIR}/
├── Inputs/                       # Input data files
│   ├── Accounts.xlsx             # Bank account definitions
│   ├── Tenants.xlsx             # Property and tenant data
│   ├── Estates.xlsx             # Estate information
│   ├── Qube EOD balances.xlsx   # End of day balances
│   ├── PreviousDayTransaction*.zip # Bank transactions
│   └── EndOfDayBalanceExtract*.zip # Bank balances
├── Reports/                      # Generated reports (output)
│   ├── WPP_Report_YYYY-MM-DD.xlsx
│   └── Data_Import_Issues_YYYY-MM-DD.xlsx
├── Logs/                        # Application logs (output)
│   ├── Log_UpdateDatabase_*.txt
│   ├── Log_RunReports_*.txt
│   └── ref_matcher.csv
└── Database/                    # SQLite database (output)
    └── WPP_DB.db
```

## Usage

### Command Line Scripts

The system provides two main command-line scripts:

#### 1. Update Database
Imports data from input files into the database.

```bash
# Using uv
uv run update_database [--verbose]

# Using installed scripts
update_database [--verbose]

# Direct module execution
python -m wpp.UpdateDatabase [--verbose]

# Direct script execution
python src/wpp/UpdateDatabase.py [--verbose]
```

**Options:**
- `--verbose` or `-v`: Generate verbose logging output

#### 2. Run Reports
Generates reconciliation reports from database data.

```bash
# Using uv (with default dates)
uv run run_reports

# With specific dates
uv run run_reports --qube_date 2024-01-15 --bos_date 2024-01-15

# Using installed scripts
run_reports --qube_date 2024-01-15 --bos_date 2024-01-15 --verbose

# Direct module execution
python -m wpp.RunReports --qube_date 2024-01-15

# Direct script execution
python src/wpp/RunReports.py --qube_date 2024-01-15 --bos_date 2024-01-15
```

**Options:**
- `--qube_date` or `-q`: Date for Qube balances (YYYY-MM-DD format)
- `--bos_date` or `-b`: Date for Bank of Scotland transactions (YYYY-MM-DD format)
  - Can only be used together with `--qube_date`
  - Defaults to same as `qube_date` if not specified
- `--verbose` or `-v`: Generate verbose logging output

**Default Behavior:**
- If no dates provided, uses previous business day
- If only `qube_date` provided, uses same date for both Qube and BOS data

### Web Application

The system includes a Streamlit web interface for interactive use.

```bash
# Run the web application
streamlit run src/wpp/app.py

# Or using uv
uv run streamlit run src/wpp/app.py
```

**Web Interface Features:**
- Interactive database update
- Report generation with date selection
- Real-time display of generated reports
- Download links for reports and logs
- Progress monitoring for long-running operations

**Web Interface URL:** http://localhost:8501 (default Streamlit port)

### Executable Versions (PyInstaller)

The system can be packaged as standalone executables using PyInstaller.

#### Creating Executables

```bash
# Install PyInstaller
pip install pyinstaller

# Create executable for UpdateDatabase
pyinstaller --onefile --name update_database src/wpp/UpdateDatabase.py

# Create executable for RunReports  
pyinstaller --onefile --name run_reports src/wpp/RunReports.py

# Create executable for web app
pyinstaller --onefile --name wpp_webapp src/wpp/app.py
```

#### Using Executables

```bash
# Windows
update_database.exe --verbose
run_reports.exe --qube_date 2024-01-15 --bos_date 2024-01-15
wpp_webapp.exe

# macOS/Linux
./update_database --verbose
./run_reports --qube_date 2024-01-15 --bos_date 2024-01-15
./wpp_webapp
```

**Note:** Executables include all dependencies and can run without Python installation.

## Typical Workflow

### 1. Prepare Data
1. Place input files in the `{WPP_ROOT_DIR}/Inputs/` directory
2. Ensure files match the patterns defined in `config.toml`
3. Create the configuration file if needed

### 2. Update Database
```bash
# Import all data into database
uv run update_database --verbose
```

### 3. Generate Reports
```bash
# Generate reports for specific dates
uv run run_reports --qube_date 2024-01-15 --bos_date 2024-01-15 --verbose
```

### 4. Review Results
- Check generated reports in `{WPP_ROOT_DIR}/Reports/`
- Review logs in `{WPP_ROOT_DIR}/Logs/`
- Examine `Data_Import_Issues_*.xlsx` for any import problems

## File Types and Formats

### Input Files
- **Excel files** (`.xlsx`): Property, tenant, estate data
- **ZIP files** (`.zip`): Bank transaction and balance extracts
- **Manual reference files**: Irregular transaction references

### Output Files
- **Reports** (`.xlsx`): Main reconciliation report and import issues
- **Logs** (`.txt`, `.csv`): Processing logs and reference matching results
- **Database** (`.db`): SQLite database with processed data

## Development and Testing

### Running Tests
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/wpp --cov-report=html

# Run specific test scenarios
uv run pytest tests/test_regression.py::test_regression[scenario_default] -v
```

### Test Data Management

The system uses encrypted test data to protect sensitive information.

#### Decrypt Test Data
```bash
export GPG_PASSPHRASE="your-passphrase"
./decrypt_test_data.sh
```

#### Encrypt Test Data
```bash
export GPG_PASSPHRASE="your-passphrase"
./encrypt_test_data.sh
```

### Adding Test Scenarios
See [tests/README_Test_Scenarios.md](tests/README_Test_Scenarios.md) for detailed instructions on adding new test scenarios.

## Troubleshooting

### Common Issues

**Configuration file not found:**
```
FileNotFoundError: Configuration file 'config.toml' not found
```
- Create `config.toml` in your working directory or specify path
- Copy from `src/wpp/config.toml` as a template

**Input files not found:**
- Check file patterns in `config.toml`
- Ensure files are in the `{WPP_ROOT_DIR}/Inputs/` directory
- Verify file permissions

**Import issues:**
- Check `Data_Import_Issues_*.xlsx` for detailed error information
- Review logs in `{WPP_ROOT_DIR}/Logs/`
- Update irregular transaction references if needed

**Database errors:**
- Ensure write permissions to `{WPP_ROOT_DIR}/Database/` directory
- Check disk space availability
- Review database log files

### Logging

The system generates detailed logs for troubleshooting:

- **UpdateDatabase logs**: `Log_UpdateDatabase_*.txt`
- **RunReports logs**: `Log_RunReports_*.txt`
- **Reference matching**: `ref_matcher.csv`

Set `--verbose` flag for more detailed logging output.

## Architecture

### Core Components
- **UpdateDatabase**: Data import and database management
- **RunReports**: Report generation and reconciliation
- **Web App**: Interactive Streamlit interface
- **Configuration**: Flexible configuration management
- **Testing**: Comprehensive test suite with scenario support

### Database
- SQLite database for data storage
- Automatically created schema
- Historical data tracking
- Transaction reconciliation

### Security
- Test data encryption for sensitive information
- Configurable file paths and patterns
- No hardcoded credentials or paths

## Support and Contributing

### Getting Help
- Check logs for detailed error information
- Review configuration settings
- Consult test scenarios for examples

### Contributing
- Run tests before submitting changes: `uv run pytest`
- Follow code style: `uv run ruff check`
- Update documentation for new features
- Add test scenarios for new functionality

## License

[Add license information here]