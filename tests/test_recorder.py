"""Real ffmpeg runs, fed a generated tone instead of the microphone."""
import json
import subprocess
import time

from filing import final_from_part, part_path
from recorder import Recorder, finalize

TONE = ["-re", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100"]


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                          "-show_format", str(path)], capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    return data["streams"][0], float(data["format"]["duration"])


def test_record_stop_files_a_normal_m4a(tmp_path):
    final = tmp_path / "2026 Fall" / "CHEM 1201" / "Lecture Records" / "CHEM 1201 9-14-26.m4a"
    rec = Recorder(final, input_args=TONE, inhibit=False)
    rec.start()
    time.sleep(3)
    assert rec.running()
    assert rec.level_db is not None and rec.level_db > -30  # meter sees the tone
    saved = rec.stop()

    assert saved == final and final.exists()
    assert not part_path(final).exists()
    stream, duration = probe(final)
    assert stream["codec_name"] == "aac"
    assert stream["sample_rate"] == "48000"
    assert stream["channels"] == 2
    assert 2.0 < duration < 4.5


def test_killed_recording_is_recoverable(tmp_path):
    final = tmp_path / "CSCI 1250 9-15-26.m4a"
    rec = Recorder(final, input_args=TONE, inhibit=False)
    rec.start()
    time.sleep(5)
    rec.proc.kill()  # simulate a crash / dead battery
    rec.proc.wait()

    part = part_path(final)
    assert part.exists() and not final.exists()
    saved = finalize(part)
    assert saved == final_from_part(part) == final
    _, duration = probe(saved)
    assert duration > 1.5


def test_recovery_does_not_overwrite_a_later_recording(tmp_path):
    final = tmp_path / "MATH 1022 9-14-26.m4a"
    final.write_bytes(b"later recording")
    rec = Recorder(final.with_name("x.m4a"), input_args=TONE, inhibit=False)
    rec.part = part_path(final)
    rec.start()
    time.sleep(3)
    rec.proc.kill()
    rec.proc.wait()
    saved = finalize(part_path(final))
    assert saved.name == "MATH 1022 9-14-26 (2).m4a"
    assert final.read_bytes() == b"later recording"
