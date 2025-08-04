import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
from faker import Faker

# Initialize Faker to generate UK-specific data
fake = Faker('en_GB')

# Column name constants
SORT_CODE_COLUMN = "Sort Code"
ACCOUNT_NUMBER_COLUMN = "Account Number"
TENANT_NAME_COLUMN = "Name"

def get_project_root() -> Path:
    """Returns the project root directory."""
    return Path(__file__).parent

def run_command(command: list[str]):
    """Runs a command and raises an exception if it fails."""
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(f"Error running command: {' '.join(command)}", file=sys.stderr)
        print(f"Stdout: {result.stdout}", file=sys.stderr)
        print(f"Stderr: {result.stderr}", file=sys.stderr)
        raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout, stderr=result.stderr)
    return result

def decrypt_files():
    """Decrypts all test data files."""
    print("Decrypting test data...")
    decrypt_script_path = get_project_root() / "decrypt_test_data.sh"
    run_command(["bash", str(decrypt_script_path)])
    print("Decryption complete.")

def encrypt_files():
    """Encrypts all test data files."""
    print("Encrypting test data...")
    encrypt_script_path = get_project_root() / "encrypt_test_data.sh"
    run_command(["bash", str(encrypt_script_path)])
    print("Encryption complete.")

def get_fake_name(name: str) -> str:
    """Generates a repeatable fake name from an original name."""
    if pd.isna(name):
        return name
    # Seed the generator for repeatability
    seed = int(hashlib.sha256(name.encode()).hexdigest(), 16)
    Faker.seed(seed)
    return fake.name()

def get_fake_sort_code(sort_code: str) -> str:
    """Generates a repeatable fake sort code in the format XX-XX-XX."""
    if pd.isna(sort_code):
        return sort_code
    # Seed the generator for repeatability
    seed = int(hashlib.sha256(str(sort_code).encode()).hexdigest(), 16)
    Faker.seed(seed)
    return f"{fake.numerify(text='%%')}-{fake.numerify(text='%%')}-{fake.numerify(text='%%')}"


def get_fake_account_number(acc_num: str) -> str:
    """Generates a repeatable fake 8-digit account number."""
    if pd.isna(acc_num):
        return acc_num
    # Seed the generator for repeatability
    seed = int(hashlib.sha256(str(acc_num).encode()).hexdigest(), 16)
    Faker.seed(seed)
    return fake.numerify(text='########')


def fake_tenant_names(tenants_file: Path) -> dict[str, str]:
    """Fakes tenant names in the Tenants.xlsx file and returns a mapping of old to new names."""
    print(f"Faking tenant names in {tenants_file}...")
    df = pd.read_excel(tenants_file)

    # Assuming the tenant name column is 'Tenant'
    name_map = {name: get_fake_name(name) for name in df[TENANT_NAME_COLUMN].unique() if pd.notna(name)}
    df[TENANT_NAME_COLUMN] = df[TENANT_NAME_COLUMN].map(name_map).fillna(df[TENANT_NAME_COLUMN])

    df.to_excel(tenants_file, index=False)
    print("Faking tenant names complete.")
    return name_map


def fake_account_details(accounts_file: Path):
    """Fakes sort codes and account numbers in the Accounts.xlsx file."""
    print(f"Faking account details in {accounts_file}...")
    df = pd.read_excel(accounts_file)

    # Create a mapping for sort codes to ensure consistency
    if SORT_CODE_COLUMN in df.columns:
        sort_code_map = {code: get_fake_sort_code(code) for code in df[SORT_CODE_COLUMN].unique() if pd.notna(code)}
        df[SORT_CODE_COLUMN] = df[SORT_CODE_COLUMN].map(sort_code_map).fillna(df[SORT_CODE_COLUMN])

    # Create a mapping for account numbers to ensure consistency
    if ACCOUNT_NUMBER_COLUMN in df.columns:
        account_number_map = {num: get_fake_account_number(num) for num in df[ACCOUNT_NUMBER_COLUMN].unique() if pd.notna(num)}
        df[ACCOUNT_NUMBER_COLUMN] = df[ACCOUNT_NUMBER_COLUMN].map(account_number_map).fillna(df[ACCOUNT_NUMBER_COLUMN])

    df.to_excel(accounts_file, index=False)
    print("Faking account details complete.")

def update_reference_reports(reports_path: Path, name_map: dict[str, str]):
    """Updates the reference reports with the new fake names."""
    print("Updating reference reports...")
    for report_file in reports_path.glob("*.xlsx"):
        print(f"  Updating {report_file.name}...")
        df = pd.read_excel(report_file)
        # Replace all occurrences of old names with new names across all columns
        for old_name, new_name in name_map.items():
            df.replace(to_replace=old_name, value=new_name, inplace=True)
        df.to_excel(report_file, index=False)
    print("Reference reports updated.")

def backup_file(file_path: Path):
    """Backs up a single file to a 'backup' subdirectory."""
    if not file_path.exists():
        print(f"Warning: {file_path} does not exist, skipping backup.", file=sys.stderr)
        return
    backup_dir = file_path.parent / "backup"
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / file_path.name
    print(f"Backing up {file_path} to {backup_path}...")
    shutil.copy2(file_path, backup_path)
    print("Backup complete.")


def main():
    """Main function to orchestrate the data faking process."""
    parser = argparse.ArgumentParser(description="Generate fake data for testing, with an option to back up original files.")
    parser.add_argument("--backup", action="store_true", help="If present, back up the xlsx files that are altered.")
    args = parser.parse_args()

    print("got here")
    if "GPG_PASSPHRASE" not in os.environ:
        print("Error: GPG_PASSPHRASE environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    root = get_project_root()
    inputs_path = root / "tests" / "Data" / "Inputs"
    reports_path = root / "tests" / "Data" / "ReferenceReports"

    tenants_file = inputs_path / "Tenants.xlsx"
    accounts_file = inputs_path / "Accounts.xlsx"

    try:
        # Decrypt all files first
        decrypt_files()

        if args.backup:
            print("Backup flag is set. Backing up files...")
            backup_file(tenants_file)
            backup_file(accounts_file)
            for report_file in reports_path.glob("*.xlsx"):
                backup_file(report_file)
            print("All backups complete.")

        # Process Tenants
        name_map = fake_tenant_names(tenants_file)

        # Process Accounts
        fake_account_details(accounts_file)

        # Update Reference Reports
        update_reference_reports(reports_path, name_map)

    finally:
        # Always re-encrypt files
        encrypt_files()
        print("Fake data generation complete. All files have been re-encrypted.")

if __name__ == "__main__":
    main()
