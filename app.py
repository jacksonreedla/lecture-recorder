"""Lecture Recorder: pick a class, press Record, press Stop.

The recording is filed as <LSUA>/<Year Season>/<COURSE>/Lecture Records/<COURSE> M-D-YY.m4a
"""
import subprocess
import time
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from filing import final_from_part, find_parts, load_config, recording_path
from recorder import Recorder, finalize, list_sources

SILENCE_DB = -60.0
SILENCE_WARN_S = 5


def notify(title, body):
    try:
        subprocess.Popen(["notify-send", "-a", "Lecture Recorder", title, body])
    except OSError:
        pass


class App:
    def __init__(self, root):
        self.root = root
        self.lsua_root, classes = load_config()
        self.rec = None
        self.started = 0.0
        self.quiet_since = None
        self.last_saved = None

        root.title("Lecture Recorder")
        root.resizable(False, False)
        frm = ttk.Frame(root, padding=16)
        frm.grid()

        ttk.Label(frm, text="Class").grid(row=0, column=0, sticky="w")
        self.course = tk.StringVar(value=classes[0])
        self.course_box = ttk.Combobox(frm, textvariable=self.course, values=classes,
                                       state="readonly", width=28)
        self.course_box.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(frm, text="Mic").grid(row=1, column=0, sticky="w")
        sources, default = list_sources()
        self.source = tk.StringVar(value=default if default in sources else sources[0])
        self.source_box = ttk.Combobox(frm, textvariable=self.source, values=sources,
                                       state="readonly", width=28)
        self.source_box.grid(row=1, column=1, sticky="ew", pady=4)

        self.button = tk.Button(frm, text="● Record", font=("Sans", 16, "bold"),
                                bg="#c62828", fg="white", activebackground="#e53935",
                                activeforeground="white", command=self.toggle, height=2)
        self.button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 8))

        self.timer = ttk.Label(frm, text="00:00:00", font=("Monospace", 20))
        self.timer.grid(row=3, column=0, columnspan=2)

        self.meter = tk.Canvas(frm, height=12, width=300, bg="#222", highlightthickness=0)
        self.meter.grid(row=4, column=0, columnspan=2, pady=6)
        self.meter_bar = self.meter.create_rectangle(0, 0, 0, 12, fill="#43a047", width=0)

        self.status = ttk.Label(frm, text="Ready.", wraplength=320, justify="left")
        self.status.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self.open_btn = ttk.Button(frm, text="Open folder", command=self.open_folder,
                                   state="disabled")
        self.open_btn.grid(row=6, column=0, columnspan=2, sticky="e", pady=(8, 0))

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(300, self.offer_recovery)
        self.tick()

    # -- actions ------------------------------------------------------------
    def toggle(self):
        if self.rec:
            self.stop()
        else:
            self.start()

    def start(self):
        final = recording_path(self.lsua_root, self.course.get(), date.today())
        self.rec = Recorder(final, source=self.source.get())
        try:
            self.rec.start()
        except OSError as e:
            self.rec = None
            messagebox.showerror("Lecture Recorder", f"Could not start ffmpeg: {e}")
            return
        self.started = time.monotonic()
        self.quiet_since = None
        self.button.config(text="■ Stop", bg="#424242", activebackground="#616161")
        self.course_box.config(state="disabled")
        self.source_box.config(state="disabled")
        self.root.after(1200, self.show_recording_status)

    def show_recording_status(self):
        if not self.rec:
            return
        msg = f"Recording to {self.rec.final.name}"
        if not self.rec.lid_inhibited:
            msg += "\n⚠ Couldn't block lid-close sleep. Keep the lid open."
        self.set_status(msg)

    def stop(self, crashed=False):
        rec, self.rec = self.rec, None
        self.button.config(text="● Record", bg="#c62828", activebackground="#e53935")
        self.course_box.config(state="readonly")
        self.source_box.config(state="readonly")
        self.set_level(None)
        self.set_status("Saving…")
        self.root.update_idletasks()
        try:
            saved = rec.stop()
        except RuntimeError as e:
            self.set_status(f"Not saved: {e}")
            messagebox.showerror("Lecture Recorder", f"Recording was not saved.\n\n{e}")
            return False
        self.last_saved = saved
        self.open_btn.config(state="normal")
        prefix = "Recording stopped unexpectedly, saved what was captured:" if crashed else "Saved:"
        self.set_status(f"{prefix}\n{saved.relative_to(self.lsua_root)}")
        notify("Lecture saved", saved.name)
        if crashed:
            messagebox.showwarning("Lecture Recorder",
                                   f"The recorder stopped on its own.\n\n{rec.last_error()}\n\n"
                                   f"What was recorded is saved as {saved.name}.")
        return True

    def offer_recovery(self):
        parts = find_parts(self.lsua_root)
        if not parts:
            return
        names = "\n".join(final_from_part(p).name for p in parts)
        if not messagebox.askyesno("Unfinished recordings",
                                   f"These recordings were cut off (app or laptop shut down):\n\n"
                                   f"{names}\n\nSave what was captured?"):
            return
        saved, failed = [], []
        for p in parts:
            try:
                saved.append(finalize(p).name)
            except RuntimeError as e:
                failed.append(str(e))
        msg = f"Recovered {len(saved)} recording(s)."
        if failed:
            msg += "\n\nCould not recover:\n" + "\n".join(failed)
        messagebox.showinfo("Lecture Recorder", msg)

    def open_folder(self):
        if self.last_saved:
            subprocess.Popen(["xdg-open", str(self.last_saved.parent)])

    def on_close(self):
        if self.rec:
            if not messagebox.askyesno("Lecture Recorder",
                                       "A lecture is recording. Stop, save it, and quit?"):
                return
            self.stop()
        self.root.destroy()

    # -- UI loop --------------------------------------------------------------
    def tick(self):
        if self.rec:
            if not self.rec.running():
                self.stop(crashed=True)
            else:
                secs = int(time.monotonic() - self.started)
                self.timer.config(text=f"{secs // 3600:02}:{secs // 60 % 60:02}:{secs % 60:02}")
                level = self.rec.level_db
                self.set_level(level)
                if level is not None and level < SILENCE_DB:
                    self.quiet_since = self.quiet_since or time.monotonic()
                    if time.monotonic() - self.quiet_since > SILENCE_WARN_S:
                        self.set_status("⚠ No sound for a few seconds. Is the right mic selected?")
                elif self.quiet_since:
                    self.quiet_since = None
                    self.show_recording_status()
        self.root.after(200, self.tick)

    def set_level(self, db):
        width = 0 if db is None else max(0.0, min(1.0, (db + 60) / 60)) * 300
        self.meter.coords(self.meter_bar, 0, 0, width, 12)

    def set_status(self, text):
        self.status.config(text=text)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
