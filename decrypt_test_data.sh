#!/bin/bash

# Ensure the decryption key is provided
if [ -z "$GPG_PASSPHRASE" ]; then
  echo "Error: GPG_PASSPHRASE environment variable is not set."
  exit 1
fi

# Function to decrypt files with specified suffixes in a given directory
decrypt_files() {
  local directory="$1"
  shift
  local suffixes=("$@")
  
  for suffix in "${suffixes[@]}"; do
    for file in "$directory"/*.$suffix.gpg; do
      # Skip if no files match the pattern
      [ -e "$file" ] || continue
      gpg --decrypt --batch --yes --passphrase "$GPG_PASSPHRASE" --output "${file%.gpg}" "$file"
      echo "Decrypted $file to ${file%.gpg}"
    done
  done
}

# Decrypt files in all test scenarios
for scenario_dir in tests/Data/TestScenarios/*/; do
  if [ -d "$scenario_dir" ]; then
    echo "Decrypting files in scenario: $scenario_dir"
    
    # Decrypt xlsx and zip files in scenario inputs
    decrypt_files "${scenario_dir}Inputs" "xlsx" "zip"
    
    # Decrypt xlsx files in scenario reference reports
    decrypt_files "${scenario_dir}ReferenceReports" "xlsx"
    
    # Decrypt csv files in scenario reference logs
    decrypt_files "${scenario_dir}ReferenceLogs" "csv"
  fi
done
