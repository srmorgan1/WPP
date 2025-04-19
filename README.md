# wpp

Describe your project here.

## Test Data Encryption

### Encrypt Test Data

Run the following command to encrypt test data files:

```bash
./encrypt_test_data.sh
```

### Decrypt Test Data

Before running tests, decrypt the test data files:

```bash
export GPG_PASSPHRASE="your-passphrase"
./decrypt_test_data.sh
```

### Notes

- Do not commit decrypted files to the repository.
- Store the `GPG_PASSPHRASE` securely (e.g., in GitHub Actions secrets).
