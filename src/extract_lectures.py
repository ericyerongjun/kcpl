import re
import shutil
from pathlib import Path
from lxml import etree

INCOURSES_DIR = Path("Incourses_directory")
OUTCOURSES_DIR = Path("Outcourses_directory")

# Namespace used in the .xml metadata files
LOM_NS = {"lom": "http://www.imsglobal.org/xsd/imsmd_rootv1p2p1"}

# Regex to strip duplication suffixes like (1), (2), etc. from filenames
_DUP_SUFFIX_RE = re.compile(r"\(\d+\)(?=\.\w+$)")

# Regex to find xid references embedded in HTML body text
_XID_RE = re.compile(r"xid-(\d+_\d+)")

# Pattern to match lecture-related titles (case-insensitive)
_LECTURE_TITLE_RE = re.compile(
    r"(?i)\b(lecture|lec|chapter|chap|slide|topic|note)\b"
)


# ── Step 1: Parse imsmanifest.xml ────────────────────────────────────────
# Find all <item> elements whose <title> contains lecture-related keywords
# and return a list of identifierref values (e.g. "res00139")
def _find_lecture_refs(manifest_path: Path) -> list[tuple[str, str]]:
    """Return [(identifierref, title), ...] for lecture items."""
    tree = etree.parse(manifest_path)
    items = tree.iter("item")

    results: list[tuple[str, str]] = []
    for item in items:
        title_el = item.find("title")
        if title_el is None or title_el.text is None:
            continue
        if _LECTURE_TITLE_RE.search(title_el.text):
            ref = item.get("identifierref")
            if ref:
                results.append((ref, title_el.text))
    return results


# ── Step 2: Parse the .dat file ──────────────────────────────────────────
# Open the dat file for a given identifierref and extract all file xids
def _parse_dat_file(dat_path: Path) -> list[dict]:
    """Return a list of {xid, linkname} dicts from a .dat file."""
    tree = etree.parse(dat_path)
    files_info: list[dict] = []
    seen_xids: set[str] = set()

    # Primary: look in <FILE> elements
    for file_el in tree.iter("FILE"):
        name_el = file_el.find("NAME")
        link_el = file_el.find("LINKNAME")
        if name_el is None or name_el.text is None:
            continue
        # NAME looks like "/xid-50162148_1" → strip leading "/"
        xid = name_el.text.lstrip("/")
        linkname = link_el.get("value", "") if link_el is not None else ""
        files_info.append({"xid": xid, "linkname": linkname})
        seen_xids.add(xid)

    # Fallback: scan <TEXT> body for embedded xid-********_* references
    for text_el in tree.iter("TEXT"):
        if text_el.text is None:
            continue
        for m in _XID_RE.finditer(text_el.text):
            xid = f"xid-{m.group(1)}"
            if xid not in seen_xids:
                files_info.append({"xid": xid, "linkname": ""})
                seen_xids.add(xid)

    return files_info


# ── Step 3: Locate the actual file and read its original name ────────────
# Find the file in csfiles/home_dir/ matching __<xid>.* (excluding .xml)
# Then read the companion .xml to get the original filename from <identifier>
def _resolve_file(
    course_dir: Path,
    xid: str,
) -> tuple[Path | None, str | None]:
    home_dir = course_dir / "csfiles" / "home_dir"
    if not home_dir.is_dir():
        return None, None

    # The actual file is named __<xid>.<ext> (without .xml)
    prefix = f"__{xid}"
    candidates = [
        f for f in home_dir.iterdir()
        if f.name.startswith(prefix) and not f.name.endswith(".xml") and f.is_file()
    ]
    if not candidates:
        return None, None

    source_file = candidates[0]

    # Read the companion .xml to get the original name
    xml_meta = home_dir / f"{source_file.name}.xml"
    original_name: str | None = None

    if xml_meta.is_file():
        meta_tree = etree.parse(xml_meta)
        ident_el = meta_tree.find(".//lom:identifier", namespaces=LOM_NS)
        if ident_el is not None and ident_el.text:
            # Format: "50162148_1#/courses/COMP5113_20231_A/Lecture2_Gradient Descent(1).pdf"
            raw_name = ident_el.text.split("/")[-1]
            # Remove duplication suffixes like (1), (2)
            original_name = _DUP_SUFFIX_RE.sub("", raw_name)

    return source_file, original_name


# ── Process a single course directory ─────────────────────────────────────
def extract_lectures_from_course(
    course_dir: Path,
    outcourses_dir: str | Path = OUTCOURSES_DIR,
) -> list[Path]:
    """Extract lecture files from a single course directory into *outcourses_dir*.

    Naming convention: <course_name>_<original_filename>
    e.g. COMP5113_20231_Lecture2_Gradient Descent.pdf
    """
    outcourses_dir = Path(outcourses_dir)
    copied: list[Path] = []

    manifest = course_dir / "imsmanifest.xml"
    if not manifest.is_file():
        print(f"[SKIP] No imsmanifest.xml in {course_dir.name}")
        return copied

    course_name = course_dir.name  # e.g. COMP5113_20231
    out_dir = outcourses_dir / course_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: find lecture identifierrefs
    lecture_refs = _find_lecture_refs(manifest)
    print(f"\n[{course_name}] Found {len(lecture_refs)} lecture item(s)")

    for ref, title in lecture_refs:
        # Step 2: parse the .dat file
        dat_path = course_dir / f"{ref}.dat"
        if not dat_path.is_file():
            print(f"  [WARN] {ref}.dat not found for '{title}'")
            continue

        file_infos = _parse_dat_file(dat_path)
        if not file_infos:
            print(f"  [WARN] No files in {ref}.dat for '{title}'")
            continue

        for fi in file_infos:
            # Step 3: locate the actual file and get original name
            source_file, original_name = _resolve_file(course_dir, fi["xid"])

            if source_file is None:
                print(f"  [WARN] File not found for xid={fi['xid']} ('{title}')")
                continue

            # Determine the output filename
            if original_name:
                out_name = f"{course_name}_{original_name}"
            else:
                # Fallback: use linkname from .dat or the title
                fallback = fi["linkname"] or title
                out_name = f"{course_name}_{fallback}"

            dest_file = out_dir / out_name

            # Copy
            shutil.copy2(source_file, dest_file)
            print(f"  ✓ {source_file.name} → {out_name}")
            copied.append(dest_file)

    print(f"  Copied {len(copied)} lecture file(s) for {course_name}")
    return copied


# ── Convenience: process all courses at once ─────────────────────────────
def extract_lectures(
    incourses_dir: str | Path = INCOURSES_DIR,
    outcourses_dir: str | Path = OUTCOURSES_DIR,
) -> list[Path]:
    incourses_dir = Path(incourses_dir)
    if not incourses_dir.is_dir():
        raise FileNotFoundError(f"incourses directory not found: {incourses_dir}")

    copied: list[Path] = []
    for course_dir in sorted(incourses_dir.iterdir()):
        if course_dir.is_dir():
            copied.extend(extract_lectures_from_course(course_dir, outcourses_dir))

    print(f"\nDone – copied {len(copied)} lecture file(s) to {outcourses_dir}")
    return copied


if __name__ == "__main__":
    extract_lectures()
