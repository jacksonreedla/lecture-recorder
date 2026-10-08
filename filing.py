"""Where a lecture recording goes and what it is called.

Matches the layout used since Spring 2026:
    <LSUA root>/<Year Season>/<COURSE>/Lecture Records/<COURSE> M-D-YY.m4a
"""
import json
from datetime import date
from pathlib import Path

CONFIG = Path(__file__).parent / "classes.json"
RECORDS_DIR = "Lecture Records"
PART_SUFFIX = ".part.m4a"


def load_config(path=CONFIG):
    data = json.loads(Path(path).read_text())
    return Path(data["lsua_root"]).expanduser(), list(data["classes"])


def semester_folder(d: date) -> str:
    if d.month <= 5:
        season = "Spring"
    elif d.month <= 7:
        season = "Summer"
    else:
        season = "Fall"
    return f"{d.year} {season}"


def date_stamp(d: date) -> str:
    """1-14-26 style: no zero padding, two-digit year."""
    return f"{d.month}-{d.day}-{d:%y}"


def part_path(final: Path) -> Path:
    """Hidden in-progress file that sits next to the final recording."""
    return final.with_name(f".{final.stem}{PART_SUFFIX}")


def final_from_part(part: Path) -> Path:
    return part.with_name(part.name[1:-len(PART_SUFFIX)] + ".m4a")


def unique_path(path: Path, ignore: Path = None) -> Path:
    """path, or 'name (2).m4a', 'name (3).m4a'... if taken (by a file or an in-progress part).

    `ignore` is a part file that should not count as taking its own name
    (used when that part is the one being saved).
    """
    def taken(p):
        part = part_path(p)
        return p.exists() or (part.exists() and part != ignore)

    candidate, n = path, 1
    while taken(candidate):
        n += 1
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
    return candidate


def recording_path(root: Path, course: str, d: date) -> Path:
    folder = Path(root) / semester_folder(d) / course / RECORDS_DIR
    return unique_path(folder / f"{course} {date_stamp(d)}.m4a")


def find_parts(root: Path):
    """Leftover in-progress recordings (app or laptop died mid-lecture)."""
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(root.rglob(f".*{PART_SUFFIX}"))
