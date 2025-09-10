import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

from wpp.utils.utils import getLatestMatchingFileName, getLatestMatchingFileNameInDir, getLongestCommonSubstring, getMatchingFileNames, is_running_via_pytest, open_file, open_files


def test_getLongestCommonSubstring():
    """Test getLongestCommonSubstring function."""
    # Basic tests
    assert getLongestCommonSubstring("hello", "world") == "l"
    assert getLongestCommonSubstring("abcdef", "abcxyz") == "abc"
    assert getLongestCommonSubstring("", "hello") == ""
    assert getLongestCommonSubstring("hello", "") == ""
    assert getLongestCommonSubstring("", "") == ""
    assert getLongestCommonSubstring("abc", "xyz") == ""
    assert getLongestCommonSubstring("same", "same") == "same"


def test_is_running_via_pytest():
    """Test is_running_via_pytest function."""
    # This should return True when running under pytest
    assert is_running_via_pytest() is True

    # Test that it correctly checks sys.modules
    assert "pytest" in sys.modules


def test_open_files_with_regular_files():
    """Test open_files with regular text files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test files
        file1 = temp_path / "test1.txt"
        file2 = temp_path / "test2.txt"
        file1.write_text("Hello World")
        file2.write_text("Goodbye World")

        # Test open_files
        files = open_files([file1, file2])
        assert len(files) == 2

        # Clean up
        for f in files:
            f.close()


def test_open_files_with_zip_files():
    """Test open_files with zip files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create a zip file with multiple entries
        zip_file = temp_path / "test.zip"
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("file1.txt", "Content 1")
            zf.writestr("file2.txt", "Content 2")
            # Add a macOS system file that should be ignored
            zf.writestr("__MACOSX/file3.txt", "System file")

        # Test open_files
        files = open_files([zip_file])
        assert len(files) == 2  # Should ignore __MACOSX file

        # Verify content
        content1 = files[0].read().decode("utf-8")
        content2 = files[1].read().decode("utf-8")
        assert "Content" in content1
        assert "Content" in content2

        # Clean up
        for f in files:
            f.close()


def test_open_file_regular_file():
    """Test open_file with regular file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test file
        test_file = temp_path / "test.txt"
        test_file.write_text("Hello World")

        # Test open_file
        with open_file(test_file) as f:
            content = f.read()
            assert "Hello World" in content


def test_open_file_zip_file_single_entry():
    """Test open_file with zip file containing single entry."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create zip file with single entry
        zip_file = temp_path / "test.zip"
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("data.txt", "Zip content")

        # Test open_file
        with open_file(zip_file) as f:
            content = f.read().decode("utf-8")
            assert content == "Zip content"


def test_open_file_zip_file_multiple_entries():
    """Test open_file with zip file containing multiple entries (should raise error)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create zip file with multiple entries
        zip_file = temp_path / "test.zip"
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("file1.txt", "Content 1")
            zf.writestr("file2.txt", "Content 2")

        # Test that it raises ValueError
        with pytest.raises(ValueError, match="must contain only only one zipped file"):
            open_file(zip_file)


def test_open_file_zip_with_macos_files():
    """Test open_file with zip file containing macOS system files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create zip file with macOS system files
        zip_file = temp_path / "test.zip"
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("data.txt", "Real content")
            zf.writestr("__MACOSX/system_file", "System file")

        # Test open_file (should ignore __MACOSX and open the real file)
        with open_file(zip_file) as f:
            content = f.read().decode("utf-8")
            assert content == "Real content"


def test_getMatchingFileNames():
    """Test getMatchingFileNames function."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test files with different timestamps
        file1 = temp_path / "test1.txt"
        file2 = temp_path / "test2.txt"
        file3 = temp_path / "other.log"

        file1.write_text("File 1")
        file2.write_text("File 2")
        file3.write_text("Log file")

        # Test with single pattern
        pattern = str(temp_path / "test*.txt")
        files = getMatchingFileNames(pattern)
        assert len(files) == 2
        assert str(file1) in files
        assert str(file2) in files

        # Test with list of patterns
        patterns = [str(temp_path / "test*.txt"), str(temp_path / "*.log")]
        files = getMatchingFileNames(patterns)
        assert len(files) == 3


def test_getLatestMatchingFileName():
    """Test getLatestMatchingFileName function."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test files
        file1 = temp_path / "test1.txt"
        file2 = temp_path / "test2.txt"

        file1.write_text("File 1")
        file2.write_text("File 2")

        # Test with matching files
        pattern = str(temp_path / "test*.txt")
        latest_file = getLatestMatchingFileName(pattern)
        assert latest_file is not None
        assert "test" in latest_file

        # Test with no matching files
        pattern = str(temp_path / "nonexistent*.txt")
        latest_file = getLatestMatchingFileName(pattern)
        assert latest_file is None


def test_getLatestMatchingFileNameInDir():
    """Test getLatestMatchingFileNameInDir function."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test files
        file1 = temp_path / "test1.txt"
        file2 = temp_path / "test2.txt"
        other_file = temp_path / "other.log"

        file1.write_text("File 1")
        file2.write_text("File 2")
        other_file.write_text("Other file")

        # Test with matching files
        latest_file = getLatestMatchingFileNameInDir(temp_path, "test*.txt")
        assert latest_file is not None
        assert latest_file.name.startswith("test")
        assert latest_file.suffix == ".txt"

        # Test with no matching files
        latest_file = getLatestMatchingFileNameInDir(temp_path, "nonexistent*.txt")
        assert latest_file is None
