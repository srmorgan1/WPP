# Test Scenarios Guide

This guide explains how to add new test scenarios to the WPP test suite. The test system uses a scenario-based structure that allows for easy creation of multiple test configurations.

## Overview

The test system is organized around **test scenarios** - self-contained sets of input data and expected outputs that test different aspects of the application. Each scenario runs independently with its own data files.

## Directory Structure

```
tests/Data/TestScenarios/
├── scenario_default/           # Default test scenario
│   ├── Inputs/                 # Input files (.xlsx, .zip)
│   ├── ReferenceLogs/          # Expected log outputs (.txt, .csv)
│   └── ReferenceReports/       # Expected report outputs (.xlsx)
└── scenario_your_name/         # Your new scenario
    ├── Inputs/                 # Your input files
    ├── ReferenceLogs/          # Your expected logs
    └── ReferenceReports/       # Your expected reports
```

## Adding a New Test Scenario

### Step 1: Update the Scenario List

Edit `tests/test_regression.py` and add your scenario name to the `TEST_SCENARIOS` list:

```python
TEST_SCENARIOS = [
    "scenario_default",
    "scenario_your_name",       # ← Add your new scenario here
    # Add more scenarios as needed
]
```

### Step 2: Create Directory Structure

Create the directory structure for your new scenario:

```bash
mkdir -p tests/Data/TestScenarios/scenario_your_name/Inputs
mkdir -p tests/Data/TestScenarios/scenario_your_name/ReferenceLogs  
mkdir -p tests/Data/TestScenarios/scenario_your_name/ReferenceReports
```

### Step 3: Add Test Data Files

#### Required Input Files (place in `Inputs/` folder):

- `Accounts.xlsx` - Bank account definitions
- `Tenants.xlsx` - Property and tenant information
- `Estates.xlsx` - Estate/property details
- `Qube EOD balances YYYY.MM.DD.xlsx` - End of day balances
- `001 GENERAL CREDITS CLIENTS WITHOUT IDENTS.xlsx` - Transaction references
- `EndOfDayBalanceExtract_*.zip` - Bank balance extracts
- `PreviousDayTransactionExtract_*.zip` - Bank transaction extracts

#### Expected Output Files:

**Reference Logs** (place in `ReferenceLogs/` folder):
- `Log_UpdateDatabase_YYYY-MM-DD.txt` - Expected database update log
- `Log_RunReports_YYYY-MM-DD.txt` - Expected report generation log
- `ref_matcher.csv` - Expected reference matching results

**Reference Reports** (place in `ReferenceReports/` folder):
- `WPP_Report_YYYY-MM-DD.xlsx` - Expected main report
- `Data_Import_Issues_YYYY-MM-DD.xlsx` - Expected import issues report

### Step 4: Encrypt Your Test Data

After adding your test files, encrypt them using the provided script:

```bash
export GPG_PASSPHRASE="your_passphrase"
./encrypt_test_data.sh
```

This will automatically encrypt all files in your new scenario directory:
- `.xlsx` files → `.xlsx.gpg`
- `.zip` files → `.zip.gpg` 
- `.csv` files → `.csv.gpg`

### Step 5: Test Your New Scenario

Run the regression test to verify your new scenario works:

```bash
# Test only your new scenario
uv run python -m pytest tests/test_regression.py::test_regression[scenario_your_name] -v

# Test all scenarios
uv run python -m pytest tests/test_regression.py -v

# Run all tests
uv run python -m pytest tests/ -v
```

## How It Works

The scenario system uses several key components:

1. **Parameterized Tests**: `@pytest.mark.parametrize("scenario", TEST_SCENARIOS)` runs the regression test for each scenario
2. **Dynamic Path Resolution**: `get_scenario_paths()` constructs file paths based on scenario name
3. **Dependency Injection**: `@patch('wpp.config.get_wpp_data_dir')` redirects the application to use scenario-specific directories
4. **Automatic Encryption/Decryption**: Scripts automatically handle all scenario directories

## Creating Scenario Data

### Option 1: Copy and Modify Existing Scenario
```bash
cp -r tests/Data/TestScenarios/scenario_default tests/Data/TestScenarios/scenario_your_name
# Decrypt, modify files as needed, then re-encrypt
```

### Option 2: Generate New Test Data
1. Run the application with your test conditions
2. Copy the generated logs and reports to your scenario's reference directories
3. Ensure the input data produces the expected outputs
4. Encrypt all files

## Best Practices

### Scenario Naming
- Use descriptive names: `scenario_edge_cases`, `scenario_large_dataset`, `scenario_error_conditions`
- Keep names short but meaningful
- Use underscores, not spaces or hyphens

### File Organization
- Keep input files minimal but representative
- Ensure reference files match exactly what the application produces
- Include edge cases and error conditions where appropriate

### Testing Strategy
- Each scenario should test a specific aspect or condition
- Scenarios should be independent - one shouldn't depend on another
- Consider scenarios for: normal operation, edge cases, error conditions, performance testing

## Troubleshooting

### Common Issues

**Scenario not running:**
- Check that scenario name is added to `TEST_SCENARIOS` list
- Verify directory structure exists
- Ensure all required input files are present

**Test failures:**
- Compare generated outputs with reference files manually
- Check file timestamps and dynamic content in logs
- Verify encryption/decryption worked correctly

**Files not found:**
- Ensure `GPG_PASSPHRASE` environment variable is set
- Run decrypt script manually: `./decrypt_test_data.sh`
- Check that encrypted files exist (`.gpg` extensions)

**Assertion errors:**
- Log files may have timestamps or paths that need normalization
- Report files may have slight formatting differences
- Check the comparison functions in `tests/test_regression.py`

### Debugging Commands

```bash
# List scenario directories
ls -la tests/Data/TestScenarios/

# Check if files are encrypted
ls tests/Data/TestScenarios/scenario_your_name/Inputs/

# Manually decrypt for debugging
export GPG_PASSPHRASE="your_passphrase"
./decrypt_test_data.sh

# Run with verbose output
uv run python -m pytest tests/test_regression.py -v -s
```

## Example: Complete Scenario Creation

Here's a complete example of adding a scenario called `scenario_small_dataset`:

1. **Edit tests/test_regression.py:**
```python
TEST_SCENARIOS = [
    "scenario_default",
    "scenario_small_dataset",
]
```

2. **Create directories:**
```bash
mkdir -p tests/Data/TestScenarios/scenario_small_dataset/{Inputs,ReferenceLogs,ReferenceReports}
```

3. **Copy and modify data:**
```bash
# Copy from default scenario
cp tests/Data/TestScenarios/scenario_default/Inputs/* tests/Data/TestScenarios/scenario_small_dataset/Inputs/
# Modify files to contain smaller dataset
```

4. **Generate reference files:**
```bash
# Run application with small dataset
# Copy generated logs and reports to ReferenceReports/ and ReferenceLogs/
```

5. **Encrypt:**
```bash
export GPG_PASSPHRASE="your_passphrase"
./encrypt_test_data.sh
```

6. **Test:**
```bash
uv run python -m pytest tests/test_regression.py::test_regression[scenario_small_dataset] -v
```

## Summary

Adding new test scenarios requires:
- ✅ 1 line change in `tests/test_regression.py`
- ✅ Creating directory structure
- ✅ Adding test data files
- ✅ Encrypting files
- ✅ Testing the scenario

The infrastructure handles all the complexity automatically - you just provide the data and expected results!