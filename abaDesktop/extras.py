# -*- coding: utf-8 -*-
"""
abaDesktop.extras
=================

Capabilities the standalone build can offer that the NVDA add-on could not.

Why these were impossible inside NVDA
-------------------------------------
An NVDA add-on runs *inside* the screen reader's process. That imposed real
limits which no amount of clever code could work around:

* **No long-running background work.** Anything slow risked freezing the reader
  itself, so scheduled/batch jobs were off the table. Standalone we own our
  process and can use worker threads freely.
* **No bundled binaries or heavy dependencies.** Add-ons must stay small and
  pure-Python; shipping an audio engine or extra libraries was not acceptable.
  A distributable app bundles whatever it needs.
* **No real audio device control.** The add-on had to be polite about the
  reader's own audio. Standalone we can record and play back freely.
* **No file associations, CLI, or multi-window use.** An add-on has no
  executable of its own.

What this module provides
-------------------------
* :class:`StudyReminder` — background reminders and daily-goal nudges.
* :class:`AudioRecorder` — record spoken answers / recitation for self-review
  (used by the recitation practice screen).
* :func:`export_progress_report` — a full offline progress report as HTML.
* :func:`backup_now` / :func:`restore_backup` — one-click data backup.
* :func:`run_cli` — a command-line interface for scripted or headless use.

Every piece degrades gracefully: if an optional dependency is missing the
feature reports itself unavailable rather than breaking the app.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import threading
import time


# ---------------------------------------------------------------------------
# background study reminders
# ---------------------------------------------------------------------------

class StudyReminder:
    """Nudges the learner toward their daily goal on a background thread.

    Inside NVDA a periodic timer competing with the screen reader was a bad
    idea; here it is a plain daemon thread that costs nothing when idle.
    """

    def __init__(self, store, notify, interval_minutes=60):
        self.store = store
        self.notify = notify              # callable(text)
        self.interval = max(5, int(interval_minutes)) * 60
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.wait(self.interval):
            try:
                msg = self._check()
                if msg:
                    self.notify(msg)
            except Exception:
                pass

    def _check(self):
        try:
            goal = int(self.store.get_setting("daily_goal", "20") or "20")
            today = self.store.today_activity()
            done = today.get("answered", 0)
        except Exception:
            return None
        if goal <= 0 or done >= goal:
            return None
        remaining = goal - done
        return (f"تذكير: بقي {remaining} سؤالًا لبلوغ هدفك اليومي. "
                f"جلسة قصيرة تكفي.")


# ---------------------------------------------------------------------------
# audio recording (recitation / pronunciation practice)
# ---------------------------------------------------------------------------

class AudioRecorder:
    """Record the learner's voice for self-review.

    Useful for Qur'an recitation and language pronunciation: record, play back,
    keep or discard. Uses ``sounddevice`` when present; reports unavailable
    otherwise instead of failing.
    """

    def __init__(self, samplerate=16000, channels=1):
        self.samplerate = samplerate
        self.channels = channels
        self._frames = []
        self._stream = None
        self._sd = None
        try:
            import sounddevice as sd
            self._sd = sd
        except Exception:
            self._sd = None

    @property
    def available(self):
        return self._sd is not None

    def start(self):
        if not self.available:
            return False
        self._frames = []

        def cb(indata, _frames, _time, _status):
            self._frames.append(indata.copy())

        self._stream = self._sd.InputStream(
            samplerate=self.samplerate, channels=self.channels, callback=cb)
        self._stream.start()
        return True

    def stop(self):
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def save_wav(self, path):
        """Write the recording as a WAV using only the standard library."""
        if not self._frames:
            return None
        import array
        import wave
        try:
            import numpy as np
            data = np.concatenate(self._frames, axis=0)
            pcm = (data * 32767).astype("<i2").tobytes()
        except Exception:
            flat = []
            for chunk in self._frames:
                flat.extend(float(x) for x in chunk.flatten())
            pcm = array.array(
                "h", (int(max(-1.0, min(1.0, v)) * 32767) for v in flat)
            ).tobytes()
        with wave.open(path, "wb") as w:
            w.setnchannels(self.channels)
            w.setsampwidth(2)
            w.setframerate(self.samplerate)
            w.writeframes(pcm)
        return path


# ---------------------------------------------------------------------------
# progress report export
# ---------------------------------------------------------------------------

def export_progress_report(academy, path):
    """Write a full, self-contained RTL HTML progress report.

    The add-on could show progress on screen but had nowhere sensible to write a
    shareable file. A teacher can open this in any browser or print it.
    """
    store = academy.store
    try:
        streak = store.current_streak()
    except Exception:
        streak = 0
    try:
        seconds = store.total_study_seconds()
    except Exception:
        seconds = 0
    try:
        strong = store.strongest_topics(limit=10)
        weak = store.weakest_topics(limit=10)
    except Exception:
        strong, weak = [], []
    try:
        from abaAcademy.gui.mistakes_view import _topic_label_ar as label
    except Exception:
        def label(t):
            return t

    def rows(items):
        out = []
        for topic, wrong, right in items:
            total = wrong + right
            pct = int(round(100 * right / total)) if total else 0
            out.append(f"<tr><td>{label(topic)}</td><td>{right}</td>"
                       f"<td>{wrong}</td><td>{pct}%</td></tr>")
        return "\n".join(out) or "<tr><td colspan='4'>لا بيانات بعد</td></tr>"

    hours, mins = divmod(seconds // 60, 60)
    today = datetime.date.today().isoformat()
    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"/>
<title>تقرير التقدّم</title><style>
body{{font-family:"Amiri","Traditional Arabic",serif;direction:rtl;
text-align:right;max-width:48rem;margin:2rem auto;padding:0 1rem;}}
h1{{color:#1F4E79}} h2{{color:#2E75B6}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}
th,td{{border:1px solid #A0A0A0;padding:.4rem .6rem;text-align:right}}
th{{background:#D9E2F3}}
</style></head><body>
<h1>تقرير التقدّم — أكاديمية الكفيف العربي</h1>
<p>التاريخ: {today}</p>
<h2>ملخّص</h2>
<ul>
<li>سلسلة الأيّام المتتالية: {streak}</li>
<li>إجمالي وقت الدراسة: {hours} ساعة و{mins} دقيقة</li>
</ul>
<h2>أقوى الموضوعات</h2>
<table><thead><tr><th>الموضوع</th><th>صحيح</th><th>خطأ</th><th>الدقّة</th></tr>
</thead><tbody>{rows(strong)}</tbody></table>
<h2>ما يحتاج تدعيمًا</h2>
<table><thead><tr><th>الموضوع</th><th>صحيح</th><th>خطأ</th><th>الدقّة</th></tr>
</thead><tbody>{rows(weak)}</tbody></table>
</body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


# ---------------------------------------------------------------------------
# backup / restore
# ---------------------------------------------------------------------------

def backup_now(user_data_dir, dest_dir=None):
    """Zip the learner's whole data folder with a timestamped name."""
    dest_dir = dest_dir or os.path.join(user_data_dir, "backups")
    os.makedirs(dest_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(dest_dir, f"aba-backup-{stamp}")
    # don't recurse into the backups folder itself
    staging = base + "-staging"
    os.makedirs(staging, exist_ok=True)
    try:
        for name in os.listdir(user_data_dir):
            if name == "backups":
                continue
            src = os.path.join(user_data_dir, name)
            dst = os.path.join(staging, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        archive = shutil.make_archive(base, "zip", staging)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return archive


def restore_backup(zip_path, user_data_dir):
    """Restore a backup zip over the data folder."""
    import zipfile
    os.makedirs(user_data_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(user_data_dir)
    return user_data_dir


# ---------------------------------------------------------------------------
# command-line interface
# ---------------------------------------------------------------------------

def run_cli(argv):
    """A small CLI — impossible for an add-on, which has no executable.

    Supports: ``--stats``, ``--report PATH``, ``--backup``, ``--import-nvda``.
    Returns a process exit code.
    """
    import argparse
    from .paths import user_data_dir as _udd
    from . import migrate as _migrate

    ap = argparse.ArgumentParser(prog="aba", description="أكاديمية الكفيف العربي")
    ap.add_argument("--stats", action="store_true", help="اطبع ملخّص التقدّم")
    ap.add_argument("--report", metavar="PATH", help="صدّر تقرير التقدّم HTML")
    ap.add_argument("--backup", action="store_true", help="أنشئ نسخة احتياطية")
    ap.add_argument("--import-nvda", action="store_true",
                    help="استورد بيانات إضافة NVDA")
    args = ap.parse_args(argv)

    from . import logging_setup
    data_dir = _udd()
    logging_setup.setup(data_dir)
    if args.import_nvda:
        copied, skipped = _migrate.import_from_addon(data_dir)
        print(f"imported: {len(copied)}, skipped: {len(skipped)}")
        return 0
    if args.backup:
        print(backup_now(data_dir))
        return 0

    from .core import build_academy
    academy = build_academy(data_dir)
    if args.report:
        print(export_progress_report(academy, args.report))
        return 0
    if args.stats:
        s = academy.store
        try:
            print(f"streak: {s.current_streak()}")
            print(f"study seconds: {s.total_study_seconds()}")
            print(f"today: {s.today_activity()}")
        except Exception as exc:
            print(f"no stats: {exc}")
        return 0
    ap.print_help()
    return 0
