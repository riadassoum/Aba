# -*- coding: utf-8 -*-
"""
abaDesktop.tts
==============

Speech output for the standalone application.

Inside NVDA the add-on simply asked NVDA to speak. A standalone program has no
screen reader to lean on, so it needs its own voice. This module provides a
small ``Speaker`` with the same three-call surface the academy already uses
(``speak`` / ``stop`` / ``available``) and picks the best backend present on the
machine, in this order:

1. **SAPI5 via comtypes** (Windows) — the native Windows voices, best Arabic
   support, and the same engines NVDA itself can use.
2. **pyttsx3** — cross-platform wrapper (SAPI5 / NSSpeechSynthesizer / espeak).
3. **espeak-ng / espeak** subprocess — Linux fallback, good Arabic coverage.
4. **macOS ``say``** subprocess.
5. **Null backend** — logs instead of speaking, so the app still runs (and the
   test suite stays headless) when no engine is installed.

Everything speaks on a worker thread so the interface never blocks, and each new
utterance cancels the previous one, matching the responsiveness of a screen
reader.
"""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import threading

# Bundled pure-Python libraries (comtypes / pyttsx3) live in vendor/; make them
# importable so speech works with nothing to install.
try:
    from .vendored import install as _install_vendor
    _install_vendor()
except Exception:
    pass


class _Backend:
    name = "null"

    def speak(self, text: str) -> None:  # pragma: no cover - overridden
        pass

    def stop(self) -> None:
        pass

    def voices(self):
        return []

    def set_voice(self, ident) -> bool:
        return False

    def set_rate(self, rate: int) -> bool:
        return False


class NvdaBackend(_Backend):
    """Speak through NVDA itself when the screen reader is running.

    If the learner already has NVDA open, it is the best voice available: it is
    the engine they have configured, with their chosen Arabic voice, rate and
    punctuation settings, and it routes through the same audio ducking they
    expect. We talk to it through the official NVDA Controller Client DLL, which
    Microsoft-style applications use to send text to NVDA.

    The DLL is looked for beside the program first (so it can be shipped), then
    on the system path. If NVDA is not running, ``nvdaController_testIfRunning``
    returns non-zero and we refuse to construct, letting the next backend win.
    """

    name = "nvda"

    def __init__(self):
        import ctypes
        import os
        import sys

        if sys.platform != "win32":
            raise RuntimeError("NVDA controller is Windows-only")

        arch = "64" if sys.maxsize > 2 ** 32 else "32"
        names = [f"nvdaControllerClient{arch}.dll", "nvdaControllerClient.dll"]
        search = []
        # the copy shipped with the application
        try:
            from .vendored import vendor_dir
            vd = vendor_dir()
            if vd:
                search.append(os.path.join(vd, "lib"))
                search.append(vd)
        except Exception:
            pass
        base = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
                else os.path.dirname(os.path.abspath(__file__)))
        search.append(base)
        search.append(os.path.join(base, "lib"))
        if getattr(sys, "frozen", False):
            search.append(os.path.join(sys._MEIPASS, "vendor", "lib"))
        search.append("")                      # system search path
        lib = None
        for folder in search:
            for n in names:
                path = os.path.join(folder, n) if folder else n
                try:
                    lib = ctypes.windll.LoadLibrary(path)
                    break
                except Exception:
                    continue
            if lib:
                break
        if lib is None:
            raise RuntimeError("NVDA controller client DLL not found")
        # non-zero means NVDA isn't running; don't claim this backend then
        if lib.nvdaController_testIfRunning() != 0:
            raise RuntimeError("NVDA is not running")
        self._lib = lib

    def running(self):
        try:
            return self._lib.nvdaController_testIfRunning() == 0
        except Exception:
            return False

    def speak(self, text):
        try:
            self._lib.nvdaController_cancelSpeech()
            self._lib.nvdaController_speakText(text)
        except Exception:
            pass

    def stop(self):
        try:
            self._lib.nvdaController_cancelSpeech()
        except Exception:
            pass

    def voices(self):
        # NVDA owns voice selection; nothing to offer here
        return []


class Sapi5Backend(_Backend):
    """Windows SAPI5 through comtypes — the best option on Windows."""

    name = "sapi5"

    def __init__(self):
        import comtypes.client  # raises if unavailable
        self._engine = comtypes.client.CreateObject("SAPI.SpVoice")
        # 0 = synchronous, 1 = async, 2 = purge-before-speak
        self._ASYNC = 1
        self._PURGE = 2

    def speak(self, text):
        self._engine.Speak(text, self._ASYNC | self._PURGE)

    def stop(self):
        try:
            self._engine.Speak("", self._PURGE)
        except Exception:
            pass

    def voices(self):
        out = []
        try:
            for i, v in enumerate(self._engine.GetVoices()):
                out.append((i, v.GetDescription()))
        except Exception:
            pass
        return out

    def set_voice(self, ident):
        try:
            self._engine.Voice = self._engine.GetVoices()[int(ident)]
            return True
        except Exception:
            return False

    def set_rate(self, rate):
        try:
            # SAPI rate is -10..10; accept a 0..100 scale and map it
            self._engine.Rate = max(-10, min(10, int((rate - 50) / 5)))
            return True
        except Exception:
            return False


class Pyttsx3Backend(_Backend):
    name = "pyttsx3"

    def __init__(self):
        import pyttsx3
        self._engine = pyttsx3.init()

    def speak(self, text):
        try:
            self._engine.stop()
        except Exception:
            pass
        self._engine.say(text)
        self._engine.runAndWait()

    def stop(self):
        try:
            self._engine.stop()
        except Exception:
            pass

    def voices(self):
        try:
            return [(v.id, v.name) for v in self._engine.getProperty("voices")]
        except Exception:
            return []

    def set_voice(self, ident):
        try:
            self._engine.setProperty("voice", ident)
            return True
        except Exception:
            return False

    def set_rate(self, rate):
        try:
            self._engine.setProperty("rate", int(rate * 2))
            return True
        except Exception:
            return False


class ESpeakBackend(_Backend):
    """espeak-ng subprocess — reliable on Linux and has solid Arabic."""

    name = "espeak"

    def __init__(self):
        self._exe = shutil.which("espeak-ng") or shutil.which("espeak")
        if not self._exe:
            raise RuntimeError("espeak not found")
        self._proc = None
        self._rate = 160
        self._voice = "ar"

    def speak(self, text):
        self.stop()
        self._proc = subprocess.Popen(
            [self._exe, "-v", self._voice, "-s", str(self._rate), text],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def voices(self):
        return [("ar", "Arabic"), ("en", "English"), ("fr", "French")]

    def set_voice(self, ident):
        self._voice = str(ident)
        return True

    def set_rate(self, rate):
        self._rate = max(80, min(450, int(80 + rate * 3)))
        return True


class SayBackend(_Backend):
    name = "say"

    def __init__(self):
        if not shutil.which("say"):
            raise RuntimeError("say not found")
        self._proc = None

    def speak(self, text):
        self.stop()
        self._proc = subprocess.Popen(["say", text],
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)

    def stop(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass


#: engines the settings screen can offer, in preference order
BACKENDS = [NvdaBackend, Sapi5Backend, Pyttsx3Backend, ESpeakBackend, SayBackend]

#: names shown to the learner
BACKEND_LABELS = {
    "auto": "تلقائي (NVDA إن كان يعمل، وإلّا صوت النظام)",
    "nvda": "قارئ الشاشة NVDA",
    "sapi5": "أصوات ويندوز (SAPI5)",
    "pyttsx3": "محرّك النظام",
    "espeak": "eSpeak",
    "say": "أصوات ماك",
    "null": "بلا صوت",
}


def _build_backend(preferred=None):
    """Return the best available backend.

    ``preferred`` may be an engine name to force, or ``"auto"``/None to pick the
    first that works. NVDA comes first on purpose: when the screen reader is
    already running it is the voice the learner has set up, so borrowing it
    beats starting a second synthesiser that would talk over it.
    """
    order = list(BACKENDS)
    if preferred and preferred != "auto":
        by_name = {c.name: c for c in order}
        if preferred in by_name:
            # try the requested engine first, then fall back to the rest
            order = [by_name[preferred]] + [c for c in order
                                            if c.name != preferred]
    for cls in order:
        try:
            return cls()
        except Exception:
            continue
    return _Backend()


class Speaker:
    """Threaded speech with interrupt-on-new-utterance.

    The academy speaks constantly (every focus change, every answer), so
    utterances are queued on a worker thread and a new one cancels whatever is
    still playing. Blocking the UI thread on speech would make the whole app
    feel frozen.
    """

    def __init__(self, preferred=None, enabled=True):
        self.enabled = enabled
        self.backend = _build_backend(preferred)
        self.log = []                  # captured text (headless/testing)
        self._q = queue.Queue()
        self._stop_flag = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    @property
    def available(self):
        return self.backend.name != "null"

    def _run(self):
        while not self._stop_flag.is_set():
            try:
                text = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            if text is None:
                break
            try:
                self.backend.speak(text)
            except Exception:
                pass

    def speak(self, text, interrupt=True):
        from abaAcademy.speakable import speakable
        text = speakable(text)
        if not text:
            return
        self.log.append(text)
        if len(self.log) > 500:
            del self.log[:250]
        if not self.enabled:
            return
        if interrupt:
            # drop anything queued and cut off what's playing
            try:
                while True:
                    self._q.get_nowait()
            except queue.Empty:
                pass
            try:
                self.backend.stop()
            except Exception:
                pass
        self._q.put(text)

    def stop(self):
        try:
            self.backend.stop()
        except Exception:
            pass

    def shutdown(self):
        self._stop_flag.set()
        self._q.put(None)
        self.stop()

    def set_engine(self, name):
        """Switch synthesiser at runtime (from the settings screen).

        Returns the name of the engine actually in use, which may differ from
        the request if that engine isn't available on this machine."""
        try:
            self.stop()
        except Exception:
            pass
        self.backend = _build_backend(name)
        return self.backend.name

    # passthroughs for the settings screen
    def voices(self):
        return self.backend.voices()

    def set_voice(self, ident):
        return self.backend.set_voice(ident)

    def set_rate(self, rate):
        return self.backend.set_rate(rate)
