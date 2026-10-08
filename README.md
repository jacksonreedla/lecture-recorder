# Lecture Recorder

Pick a class, press **Record**, press **Stop**. The lecture is filed where the
Spring 2026 recordings live:

```
~/Documents/LSUA/<Year Season>/<COURSE>/Lecture Records/<COURSE> M-D-YY.m4a
e.g. 2026 Fall/CHEM 1201/Lecture Records/CHEM 1201 9-14-26.m4a
```

- Semester folder from the date: Jan-May Spring, Jun-Jul Summer, Aug-Dec Fall.
- Missing class / `Lecture Records` folders are created on first recording.
- Two recordings of the same class on the same day: `... (2).m4a`.
- AAC 192 kbps, 48 kHz stereo, same format as the earlier recordings.

## Run
App menu → **Lecture Recorder**, or `~/lecture-recorder/launch.sh`.
Needs only `python3` (with Tk), `ffmpeg` and PipeWire/PulseAudio.

## Next semester
Edit `classes.json` (course list, LSUA root). Nothing else changes.

## Safety nets
- **Lid close:** while recording, the app blocks lid-close sleep, so the laptop
  keeps recording when you shut it. If that is ever refused, the status line says
  to keep the lid open. The block is gone as soon as you press Stop or the app exits.
- **Crash / dead battery:** audio is written as 2-second fragments to a hidden
  `.<name>.part.m4a` next to the final file. At most ~2 s is lost. Next time the
  app opens it offers to save any cut-off recordings.
- **Wrong or muted mic:** level meter, plus a warning after 5 s of silence.
- Closing the window mid-lecture asks before stopping.

## Tests
```
python3 -m venv venv && venv/bin/pip install pytest   # once
venv/bin/python -m pytest -q
```
The recorder tests run real ffmpeg fed a generated tone, not the mic.
