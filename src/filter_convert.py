import subprocess
import shutil
from pathlib import Path

# Default directory – should match extract_lectures.py output
# In server: /home/rjye/projects/research/kc_dp/outcourses
OUTCOURSES_DIR = Path("Outcourses_directory")

# Extensions to keep (before conversion)
KEEP_EXTENSIONS = {".pdf", ".pptx", ".ppt"}


def _find_soffice() -> str:
    """Locate the LibreOffice binary."""
    for name in ("libreoffice", "soffice"):
        path = shutil.which(name)
        if path:
            return path
    raise FileNotFoundError(
        "LibreOffice (libreoffice / soffice) not found on PATH. "
        "Install it to convert pptx/ppt to pdf."
    )


def _convert_to_pdf(source: Path, out_dir: Path) -> Path:
    """Convert a pptx/ppt file to pdf using LibreOffice."""
    soffice = _find_soffice()
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(source)],
        check=True,
        capture_output=True,
    )
    # LibreOffice names the output <stem>.pdf
    return out_dir / f"{source.stem}.pdf"


def filter_and_convert_course(course_dir: Path) -> dict:
    """Filter and convert files in a single course output directory.

    Deletes non-pdf/pptx/ppt files, converts pptx/ppt → pdf, keeps pdfs.
    Returns a summary dict with counts.
    """
    deleted = 0
    converted = 0
    kept = 0

    course_name = course_dir.name
    print(f"\n[{course_name}]")

    for f in sorted(course_dir.iterdir()):
        if not f.is_file():
            continue

        ext = f.suffix.lower()

        if ext not in KEEP_EXTENSIONS:
            f.unlink()
            print(f"  ✗ Deleted  {f.name}")
            deleted += 1

        elif ext in (".pptx", ".ppt"):
            try:
                pdf_path = _convert_to_pdf(f, course_dir)
                f.unlink()
                print(f"  ↻ Converted {f.name} → {pdf_path.name}")
                converted += 1
            except subprocess.CalledProcessError as e:
                print(f"  [ERR] Failed to convert {f.name}: {e.stderr.decode()}")

        else:
            kept += 1

    summary = {"kept": kept, "converted": converted, "deleted": deleted}
    print(f"  Done – kept {kept}, converted {converted}, deleted {deleted}")
    return summary


# ── Convenience: process all courses at once ─────────────────────────────
def filter_and_convert(outcourses_dir: str | Path = OUTCOURSES_DIR) -> dict:
    """Filter and convert files across all course directories."""
    outcourses_dir = Path(outcourses_dir)
    if not outcourses_dir.is_dir():
        raise FileNotFoundError(f"outcourses directory not found: {outcourses_dir}")

    totals = {"kept": 0, "converted": 0, "deleted": 0}
    for course_dir in sorted(outcourses_dir.iterdir()):
        if not course_dir.is_dir():
            continue
        s = filter_and_convert_course(course_dir)
        for k in totals:
            totals[k] += s[k]

    print(f"\nDone – kept {totals['kept']} pdf(s), converted {totals['converted']} pptx/ppt → pdf, deleted {totals['deleted']} other file(s)")
    return totals


if __name__ == "__main__":
    filter_and_convert()
