#!/bin/bash

# Ensure the decryption key is provided
if [ -z "$GPG_PASSPHRASE" ]; then
  echo "Error: GPG_PASSPHRASE environment variable is not set."
  exit 1
fi

# Decrypt all test data files
for file in tests/Data/Inputs/*.gpg tests/Data/ReferenceReports/*.gpg; do
  gpg --decrypt --batch --yes --passphrase "$GPG_PASSPHRASE" --output "${file%.gpg}" "$file"
  echo "Decrypted $file to ${file%.gpg}"
done
