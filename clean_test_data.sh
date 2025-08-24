#!/bin/bash

# Global variables
SCENARIO=""
DATA_DIR=""

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo "Clean unencrypted test data files for WPP regression tests"
    echo ""
    echo "Options:"
    echo "  -s, --scenario NAME      Clean files for specific scenario only"
    echo "  -d, --data_dir DIR       Clean files in specific data directory only"
    echo "                           (Inputs, ReferenceLogs, or ReferenceReports)"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                       Clean all scenarios and directories"
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
                echo "Unknown option: $1"
                echo "Use -h or --help for usage information"
                exit 1
                ;;
        esac
    done
}

clean_files_in_dir() {
    local dir="$1"
    local extensions=("xlsx" "csv" "zip" "xml")
    
    if [[ ! -d "$dir" ]]; then
        return
    fi
    
    for ext in "${extensions[@]}"; do
        while IFS= read -r -d '' file; do
            echo "Removing $file"
            rm "$file"
        done < <(find "$dir" -name "*.${ext}" -type f -print0)
    done
}

clean_scenario() {
    local scenario_name="$1"
    local scenario_dir="tests/Data/TestScenarios/$scenario_name"
    
    if [[ ! -d "$scenario_dir" ]]; then
        echo "Warning: Scenario directory not found: $scenario_dir"
        return
    fi
    
    echo "Cleaning files in scenario: $scenario_name"
    
    if [[ -z "$DATA_DIR" ]]; then
        # Clean all data directories
        clean_files_in_dir "$scenario_dir/Inputs"
        clean_files_in_dir "$scenario_dir/ReferenceReports"
        clean_files_in_dir "$scenario_dir/ReferenceLogs"
    else
        # Clean specific data directory
        clean_files_in_dir "$scenario_dir/$DATA_DIR"
    fi
}

main() {
    parse_arguments "$@"
    
    if [[ -n "$SCENARIO" ]]; then
        # Clean specific scenario
        clean_scenario "$SCENARIO"
    else
        # Clean all scenarios
        if [[ ! -d "tests/Data/TestScenarios" ]]; then
            echo "Error: tests/Data/TestScenarios directory not found"
            echo "Please run this script from the WPP root directory"
            exit 1
        fi
        
        for scenario_dir in tests/Data/TestScenarios/*/; do
            if [[ -d "$scenario_dir" ]]; then
                scenario_name=$(basename "$scenario_dir")
                clean_scenario "$scenario_name"
            fi
        done
    fi
}

main "$@"