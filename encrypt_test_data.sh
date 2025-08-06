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

# Encrypt xlsx and zip files in Data/Inputs and Data/ReferenceReports
encrypt_files "tests/Data/Inputs" "xlsx" "zip"
encrypt_files "tests/Data/ReferenceReports" "xlsx" "zip"

# Encrypt csv files in Data/ReferenceLogs
encrypt_files "tests/Data/ReferenceLogs" "csv"
