#!/bin/bash

# Ensure the passphrase is provided
if [ -z "$GPG_PASSPHRASE" ]; then
  echo "Error: GPG_PASSPHRASE environment variable is not set."
  exit 1
fi

# Define the file suffixes to encrypt
SUFFIXES=("xlsx" "zip")

# Encrypt files with the specified suffixes
for suffix in "${SUFFIXES[@]}"; do
  for file in tests/Data/Inputs/*.$suffix tests/Data/ReferenceReports/*.$suffix; do
  echo $file
    # Skip if no files match the suffix
    [ -e "$file" ] || continue
    gpg --batch --yes --passphrase "$GPG_PASSPHRASE" --symmetric --cipher-algo AES256 --output "${file}.gpg" "$file"
    echo "Encrypted $file to ${file}.gpg"
  done
done
