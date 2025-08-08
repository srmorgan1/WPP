#!/bin/bash

# Ensure the passphrase is provided
if [ -z "$GPG_PASSPHRASE" ]; then
  echo "Error: GPG_PASSPHRASE environment variable is not set."
  exit 1
fi

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

# Encrypt files in all test scenarios
for scenario_dir in tests/Data/TestScenarios/*/; do
  if [ -d "$scenario_dir" ]; then
    echo "Encrypting files in scenario: $scenario_dir"
    
    # Encrypt xlsx and zip files in scenario inputs
    encrypt_files "${scenario_dir}Inputs" "xlsx" "zip"
    
    # Encrypt xlsx files in scenario reference reports
    encrypt_files "${scenario_dir}ReferenceReports" "xlsx"
    
    # Encrypt csv files in scenario reference logs
    encrypt_files "${scenario_dir}ReferenceLogs" "csv"
  fi
done
