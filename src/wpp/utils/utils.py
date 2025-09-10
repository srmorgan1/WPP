import glob
import os
import sys
import zipfile
from pathlib import Path
from typing import IO


def getLongestCommonSubstring(string1: str, string2: str) -> str:
    answer = ""
    len1, len2 = len(string1), len(string2)
    for i in range(len1):
        for j in range(len2):
            lcs_temp = 0
            match = ""
            while (i + lcs_temp < len1) and (j + lcs_temp < len2) and string1[i + lcs_temp] == string2[j + lcs_temp]:
                match += string2[j + lcs_temp]
                lcs_temp += 1
            if len(match) > len(answer):
                answer = match
    return answer


def is_running_via_pytest() -> bool:
    """Detect if we are running via pytest."""
    # When we are running via pytest it is loaded to the sys modules dictionary.
    _we_are_running_via_pytest: bool = "pytest" in sys.modules
    return _we_are_running_via_pytest


def open_files(file_paths: list[Path]) -> list[IO]:
    files = []
    for file_path in file_paths:
        ext = file_path.suffix
        if ext == ".zip":
            # A zip file may contain multiple zipped files
            zfile = zipfile.ZipFile(file_path)
            for finfo in zfile.infolist():
                # Mac OSX zip files contain a directory we don't want
                if "__MACOSX" not in finfo.filename:
                    files.append(zfile.open(finfo))
        else:
            files.append(file_path.open(mode="rb"))
    return files


# Open a file, which can be within a zip file
def open_file(file_path: Path | str) -> IO:
    path = Path(file_path)
    ext = path.suffix
    if ext.lower() == ".zip":
        # A zip file may contain multiple zipped files, however we only want the first one
        zfile = zipfile.ZipFile(path)
        files = [finfo for finfo in zfile.infolist() if "__MACOSX" not in finfo.filename]
        if len(files) > 1:
            raise ValueError(f"Zip file {path} must contain only only one zipped file")
        else:
            return zfile.open(files[0])
    else:
        return path.open()


def getMatchingFileNames(file_paths: str | list[str]) -> list[str]:
    files = []
    if not isinstance(file_paths, list):
        file_paths = [file_paths]

    for file_path in file_paths:
        files.extend(glob.glob(file_path))
    return sorted(files, key=os.path.getctime)


def getLatestMatchingFileName(file_path: str) -> str | None:
    files = glob.glob(file_path)
    if files:
        return max(files, key=os.path.getctime)
    else:
        return None


def getLatestMatchingFileNameInDir(wpp_dir: Path, file_name_glob: str) -> Path | None:
    files = list(wpp_dir.glob(file_name_glob))
    if files:
        return max(files, key=lambda x: x.stat().st_ctime)
    else:
        return None
