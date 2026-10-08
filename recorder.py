"""ffmpeg-backed recorder.

Records into a hidden fragmented-MP4 part file, so a crash or dead battery still
leaves a playable file, then remuxes it into a normal .m4a on stop.
"""
import os
import re
import subprocess
import threading
from collections import deque
from pathlib import Path

from filing import final_from_part, part_path, unique_path

_LEVEL_RE = re.compile(r"RMS_level=(-?[\d.]+|-?inf)")


def list_sources():
    """(names, default) of PulseAudio/PipeWire capture sources, monitors excluded."""
    try:
        out = subprocess.run(["pactl", "list", "short", "sources"],
                             capture_output=True, text=True, timeout=5).stdout
        default = subprocess.run(["pactl", "get-default-source"],
                                 capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ["default"], "default"
    names = [line.split("\t")[1] for line in out.splitlines()
             if "\t" in line and not line.split("\t")[1].endswith(".monitor")]
    return (names or ["default"]), (default or "default")


def finalize(part: Path, final: Path = None) -> Path:
    """Remux a part file into a regular .m4a. Keeps the part if that fails."""
    part = Path(part)
    final = unique_path(Path(final) if final else final_from_part(part), ignore=part)
    tmp = final.with_name(f".{final.stem}.tmp.m4a")
    res = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(part),
         "-c", "copy", "-movflags", "+faststart", str(tmp)],
        capture_output=True, text=True)
    if res.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"could not save {part.name}: {res.stderr.strip()[-300:]}")
    os.replace(tmp, final)
    part.unlink()
    return final


class Recorder:
    def __init__(self, final: Path, source="default", input_args=None, inhibit=True):
        self.final = Path(final)
        self.part = part_path(self.final)
        self.input_args = input_args or ["-f", "pulse", "-i", source]
        self.inhibit = inhibit
        self.proc = None
        self.inhibitor = None
        self.lid_inhibited = False
        self.level_db = None
        self._errors = deque(maxlen=20)

    # -- lifecycle --------------------------------------------------------
    def start(self):
        self.final.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            *self.input_args,
            # astats/ametadata pass audio through untouched; they only report the level.
            # direct=1: unbuffered, or the levels sit in a pipe buffer and the meter never moves.
            "-af", "astats=metadata=1:reset=10,"
                   "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-:direct=1",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            # Fragments every 2 s, flushed to disk as written: a crash loses at most ~2 s.
            "-f", "mp4", "-movflags", "+empty_moov+default_base_moof", "-frag_duration", "2000000",
            "-flush_packets", "1",
            str(self.part),
        ]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
        threading.Thread(target=self._read_levels, daemon=True).start()
        threading.Thread(target=self._read_errors, daemon=True).start()
        if self.inhibit:
            self._take_inhibitor()

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> Path:
        """Stop cleanly and file the recording. Returns the final path."""
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.stdin.write(b"q")
                self.proc.stdin.flush()
                self.proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait()
        self.release_inhibitor()
        if not self.part.exists():
            raise RuntimeError("nothing was recorded: " + self.last_error())
        return finalize(self.part, self.final)

    def last_error(self):
        return "\n".join(self._errors) or "no error output from ffmpeg"

    # -- sleep / lid inhibitor -------------------------------------------
    def _take_inhibitor(self):
        # `tail --pid` exits when this app dies, so a crash never leaves the lid blocked.
        self.inhibitor = subprocess.Popen(
            ["systemd-inhibit", "--what=sleep:handle-lid-switch", "--who=Lecture Recorder",
             "--why=Recording a lecture", "--mode=block",
             "tail", f"--pid={os.getpid()}", "-f", "/dev/null"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self.inhibitor.wait(timeout=1)
            self.lid_inhibited = False  # exited straight away = refused
        except subprocess.TimeoutExpired:
            self.lid_inhibited = True

    def release_inhibitor(self):
        if self.inhibitor and self.inhibitor.poll() is None:
            self.inhibitor.terminate()
            try:
                self.inhibitor.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.inhibitor.kill()
        self.inhibitor = None
        self.lid_inhibited = False

    # -- stream readers ---------------------------------------------------
    def _read_levels(self):
        for raw in self.proc.stdout:
            m = _LEVEL_RE.search(raw.decode(errors="replace"))
            if m:
                v = m.group(1)
                self.level_db = -120.0 if "inf" in v else float(v)

    def _read_errors(self):
        for raw in self.proc.stderr:
            self._errors.append(raw.decode(errors="replace").rstrip())
