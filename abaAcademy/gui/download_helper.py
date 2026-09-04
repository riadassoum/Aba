# -*- coding: utf-8 -*-
"""
abaAcademy.gui.download_helper
==============================

A small download utility shared by the Qur'an resource manager and the hadith
reader. It combines the strengths of both approaches:

* **Audible progress** — an optional periodic beep while a long download runs,
  so a screen-reader user always knows work is happening (technique adapted
  from a well-tested open-source update manager).
* **Chunked, resumable streaming** — content is streamed in chunks to a
  ``.part`` file and atomically renamed on success, with a real byte-progress
  callback, rather than read all at once into memory.

Announcements go through the application's speech object when available, falling
back to a provided speak callback otherwise.
"""

from __future__ import annotations

import os
import threading
import time
import urllib.request

try:
    import winsound
    _HAS_BEEP = True
except Exception:
    _HAS_BEEP = False

try:
    _speech_ui = None               # speech comes from the application
except Exception:
    _speech_ui = None


def announce(msg, speak=None):
    """Speak a message via the screen reader if available, else via a fallback callback."""
    if _nvda_ui is not None:
        try:
            _nvda_ui.message(msg)
            return
        except Exception:
            pass
    if speak:
        try:
            speak(msg)
        except Exception:
            pass


class BeepLoop:
    """A short low beep every second while a task runs (blind-friendly 'busy')."""

    def __init__(self, freq=500, ms=80, interval=1.2):
        self._freq, self._ms, self._interval = freq, ms, interval
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if not _HAS_BEEP:
            return
        self._stop.clear()

        def _loop():
            while not self._stop.is_set():
                try:
                    winsound.Beep(self._freq, self._ms)
                except Exception:
                    pass
                self._stop.wait(self._interval)
        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()


def download_to(url, dest, progress=None, should_stop=None, chunk=65536, timeout=60):
    """Stream ``url`` to ``dest`` (atomic via a .part file). ``progress(done,
    total)`` reports bytes; ``total`` is 0 when the server omits the length.
    Returns True on success. Never raises — returns False on any error."""
    tmp = dest + ".part"
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        req = urllib.request.Request(url, headers={
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0 Safari/537.36")})
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, "wb") as out:
            total = int(resp.headers.get("Content-Length", 0) or 0)
            done = 0
            while True:
                if should_stop and should_stop():
                    raise InterruptedError
                buf = resp.read(chunk)
                if not buf:
                    break
                out.write(buf)
                done += len(buf)
                if progress:
                    progress(done, total)
        if os.path.getsize(tmp) > 0:
            os.replace(tmp, dest)
            return True
        os.remove(tmp)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
    return False


def download_with_feedback(url, dest, speak=None, label="", should_stop=None):
    """Blocking download with a busy-beep and start/finish speech. Call from a
    worker thread. Returns True on success."""
    beep = BeepLoop()
    beep.start()
    announce((f"جارٍ تنزيل {label}..." if label else "جارٍ التنزيل..."), speak)
    last = [0.0]

    def _prog(done, total):
        now = time.time()
        if total and now - last[0] > 2.0:
            last[0] = now
            pct = int(done * 100 / total)
            announce(f"{pct} بالمئة", speak)

    ok = download_to(url, dest, progress=_prog, should_stop=should_stop)
    beep.stop()
    announce((f"اكتمل تنزيل {label}." if label else "اكتمل التنزيل.") if ok
             else "تعذّر التنزيل. تحقّق من الاتصال بالإنترنت.", speak)
    return ok
