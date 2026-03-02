import zipfile
from collections.abc import Generator
from pathlib import Path

# Default directories on the Linux server

SRC_DIR = Path("Archives_directory")
DEST_DIR = Path("Incourses_directory")


# Extract the course code and year and semester from the zip file name to be the name of the new folder
def _extract_course_name(zip_name: str) -> str:
    return zip_name[12:26]


def unzip_iter(
    src_dir: str | Path = SRC_DIR,
    dest_dir: str | Path = DEST_DIR,
) -> Generator[Path, None, None]:
    """Yield each course folder one at a time after unzipping.
    Multiple zip files for the same course (e.g. _A.zip, _B.zip) are
    extracted into the same folder before it is yielded.  The caller is
    responsible for cleaning up the folder when done.
    """
    src_dir = Path(src_dir)
    dest_dir = Path(dest_dir)

    if not src_dir.is_dir():
        raise FileNotFoundError(f"Source directory does not exist: {src_dir}")

    dest_dir.mkdir(parents=True, exist_ok=True)

    zip_files = sorted(src_dir.glob("*.zip"))
    if not zip_files:
        print(f"No .zip files found in {src_dir}")
        return

    # Group zip files by course name so _A/_B go into the same folder
    from collections import defaultdict
    course_zips: dict[str, list[Path]] = defaultdict(list)
    for zp in zip_files:
        course_zips[_extract_course_name(zp.name)].append(zp)

    for folder_name, zips in course_zips.items():
        extract_to = dest_dir / folder_name
        extract_to.mkdir(parents=True, exist_ok=True)

        ok = False
        for zip_path in zips:
            print(f"Extracting {zip_path.name} → {extract_to}")
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(extract_to)
                ok = True
            except zipfile.BadZipFile:
                print(f"  ⚠ Skipping {zip_path.name}: file is corrupted or truncated")

        if ok:
            yield extract_to
        else:
            print(f"  ⚠ All archives for {folder_name} were corrupt – nothing to process")


if __name__ == "__main__":
    for folder in unzip_iter():
        print(f"  Ready: {folder}")
