#!/bin/bash

# Global variables
SCENARIO=""
DATA_DIR=""

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo "Encrypt test data files for WPP regression tests"
    echo ""
    echo "Options:"
    echo "  -s, --scenario NAME      Encrypt files for specific scenario only"
    echo "  -d, --data_dir DIR       Encrypt files in specific data directory only"
    echo "                           (Inputs, ReferenceLogs, or ReferenceReports)"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  GPG_PASSPHRASE          Required GPG passphrase for encryption"
    echo ""
    echo "Examples:"
    echo "  $0                       Encrypt all scenarios and directories"
    echo "  $0 --scenario scenario_default"
    echo "  $0 -s 2025-08-01"
    echo "  $0 --data_dir Inputs"
    echo "  $0 -s scenario_default -d ReferenceLogs"
    exit 0
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -s)
                SCENARIO="$2"
                shift 2
                ;;
            --scenario)
                SCENARIO="$2"
                shift 2
                ;;
            -d)
                DATA_DIR="$2"
                shift 2
                ;;
            --data_dir)
                DATA_DIR="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                ;;
            *)
                echo "Unknown option: $1" >&2
                echo "Use -h or --help for usage information" >&2
                exit 1
                ;;
        esac
    done
}

validate_environment() {
    if [ -z "$GPG_PASSPHRASE" ]; then
        echo "Error: GPG_PASSPHRASE environment variable is not set."
        exit 1
    fi
}

validate_data_dir() {
    if [ -n "$DATA_DIR" ]; then
        case "$DATA_DIR" in
            Inputs|ReferenceLogs|ReferenceReports)
                ;;
            *)
                echo "Error: Invalid data directory '$DATA_DIR'. Must be one of: Inputs, ReferenceLogs, ReferenceReports" >&2
                exit 1
                ;;
        esac
    fi
}

# Function to encrypt files with specified suffixes in a given directory
encrypt_files() {
  local directory="$1"
  shift
  local suffixes=("$@")
  
  for suffix in "${suffixes[@]}"; do
    for file in "$directory"/*.$suffix; do
      echo $file
      # Skip if no files match the suffix
      [ -e "$file" ] || continue
      gpg --batch --yes --passphrase "$GPG_PASSPHRASE" --symmetric --cipher-algo AES256 --output "${file}.gpg" "$file"
      echo "Encrypted $file to ${file}.gpg"
    done
  done
}

build_scenario_list() {
    local scenarios=()
    if [ -n "$SCENARIO" ]; then
        # Single scenario specified - validation handled in main
        scenarios=("$SCENARIO")
    else
        # All scenarios
        for scenario_dir in tests/Data/TestScenarios/*/; do
            if [ -d "$scenario_dir" ]; then
                scenarios+=($(basename "$scenario_dir"))
            fi
        done
    fi
    printf "%s\n" "${scenarios[@]}"
}

encrypt_data_dir() {
    local dir_path="$1"
    shift
    local file_types=("$@")
    
    encrypt_files "$dir_path" "${file_types[@]}"
}

encrypt_scenario() {
    local scenario="$1"
    local scenario_dir="tests/Data/TestScenarios/$scenario"
    echo "Encrypting files in scenario: $scenario"
    
    if [ -n "$DATA_DIR" ]; then
        # Encrypt specific data directory only
        echo "  Processing data directory: $DATA_DIR"
        case "$DATA_DIR" in
            Inputs)
                encrypt_data_dir "${scenario_dir}/Inputs" "xlsx" "zip"
                ;;
            ReferenceReports)
                encrypt_data_dir "${scenario_dir}/ReferenceReports" "xlsx"
                ;;
            ReferenceLogs)
                encrypt_data_dir "${scenario_dir}/ReferenceLogs" "csv"
                ;;
        esac
    else
        # Encrypt all data directories
        encrypt_data_dir "${scenario_dir}/Inputs" "xlsx" "zip"
        encrypt_data_dir "${scenario_dir}/ReferenceReports" "xlsx"
        encrypt_data_dir "${scenario_dir}/ReferenceLogs" "csv"
    fi
}

main() {
    parse_arguments "$@"
    validate_environment
    validate_data_dir
    
    # Validate scenario directory if specific scenario requested
    if [ -n "$SCENARIO" ]; then
        local scenario_dir="tests/Data/TestScenarios/$SCENARIO"
        if [ ! -d "$scenario_dir" ]; then
            echo "Error: Scenario directory not found: $scenario_dir" >&2
            exit 1
        fi
    fi
    
    # Build scenario list
    local scenarios=()
    local temp_file="/tmp/scenarios_list.$$"
    build_scenario_list > "$temp_file"
    while IFS= read -r scenario; do
        scenarios+=("$scenario")
    done < "$temp_file"
    rm -f "$temp_file"
    
    # Encrypt files for each scenario
    for scenario in "${scenarios[@]}"; do
        encrypt_scenario "$scenario"
    done
}

# Run main function with all arguments
main "$@"
