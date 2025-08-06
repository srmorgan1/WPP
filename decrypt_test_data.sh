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

# Decrypt xlsx and zip files in Data/Inputs and Data/ReferenceReports
decrypt_files "tests/Data/Inputs" "xlsx" "zip"
decrypt_files "tests/Data/ReferenceReports" "xlsx" "zip"

# Decrypt csv files in Data/ReferenceLogs
decrypt_files "tests/Data/ReferenceLogs" "csv"
