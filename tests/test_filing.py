from datetime import date

import pytest

from filing import (date_stamp, final_from_part, find_parts, part_path, recording_path,
                    semester_folder, unique_path)


@pytest.mark.parametrize("d,expected", [
    (date(2026, 1, 14), "2026 Spring"),
    (date(2026, 5, 31), "2026 Spring"),
    (date(2026, 6, 1), "2026 Summer"),
    (date(2026, 7, 31), "2026 Summer"),
    (date(2026, 8, 24), "2026 Fall"),
    (date(2026, 12, 10), "2026 Fall"),
])
def test_semester_folder(d, expected):
    assert semester_folder(d) == expected


def test_date_stamp_matches_existing_files():
    assert date_stamp(date(2026, 1, 14)) == "1-14-26"
    assert date_stamp(date(2026, 9, 4)) == "9-4-26"
    assert date_stamp(date(2026, 11, 30)) == "11-30-26"


def test_recording_path_layout(tmp_path):
    p = recording_path(tmp_path, "CHEM 1201", date(2026, 9, 14))
    assert p == tmp_path / "2026 Fall" / "CHEM 1201" / "Lecture Records" / "CHEM 1201 9-14-26.m4a"
    assert not p.parent.exists()  # nothing created just by asking


def test_same_day_collision_gets_suffix(tmp_path):
    first = recording_path(tmp_path, "MATH 1022", date(2026, 9, 14))
    first.parent.mkdir(parents=True)
    first.write_bytes(b"x")
    second = recording_path(tmp_path, "MATH 1022", date(2026, 9, 14))
    assert second.name == "MATH 1022 9-14-26 (2).m4a"
    second.write_bytes(b"x")
    assert recording_path(tmp_path, "MATH 1022", date(2026, 9, 14)).name == "MATH 1022 9-14-26 (3).m4a"


def test_in_progress_part_reserves_name(tmp_path):
    final = tmp_path / "FREN 2101 9-14-26.m4a"
    part_path(final).write_bytes(b"x")
    assert unique_path(final).name == "FREN 2101 9-14-26 (2).m4a"
    assert unique_path(final, ignore=part_path(final)) == final


def test_part_roundtrip_and_find(tmp_path):
    final = tmp_path / "2026 Fall" / "CSCI 1250" / "Lecture Records" / "CSCI 1250 9-15-26.m4a"
    part = part_path(final)
    assert part.name == ".CSCI 1250 9-15-26.part.m4a"
    assert final_from_part(part) == final
    part.parent.mkdir(parents=True)
    part.write_bytes(b"x")
    assert find_parts(tmp_path) == [part]
    assert find_parts(tmp_path / "missing") == []
