# -*- coding: utf-8 -*-
"""
abaAcademy.arabic_lab.diacritizer
=================================

المشكِّل الآلي — adds the short vowels (tashkeel) to Arabic text with Mishkal
by Taha Zerrouki (GPL, https://github.com/linuxscout/mishkal) and the
libraries it is built on (Qalsadi, Asmai, Arramooz, Maskouk, Sylajone,
Naftawayh, Tashaphyne, Alyahmor, PyArabic, Qutrub), bundled in
abaAcademy/thirdparty. Vowelled text is read far more correctly by speech
synthesizers, and shows a learner how a sentence is pronounced.

Mishkal is a rule- and dictionary-based diacritizer: it is right most of
the time on ordinary prose, and the screen says plainly that its output can
contain mistakes and should be checked against a teacher or a vowelled
source for anything that matters, such as Qur'an or hadith.
"""

from __future__ import annotations

import os
import sys
import threading
import warnings
from typing import Optional

_TP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "thirdparty")
if _TP not in sys.path:
    sys.path.insert(0, _TP)



def _orjson_fallback() -> None:
    """pickledb (used by Qalsadi's optional cache) imports orjson. The
    portable build installs the real one; where it is missing, a stand-in
    with the two functions pickledb calls keeps Mishkal working."""
    try:
        import orjson  # noqa: F401
    except Exception:
        import json
        import types
        m = types.ModuleType("orjson")
        m.dumps = lambda obj, *a, **k: json.dumps(obj, ensure_ascii=False).encode("utf-8")
        m.loads = lambda data, *a, **k: json.loads(data.decode("utf-8") if isinstance(data, bytes) else data)
        m.OPT_INDENT_2 = 0
        sys.modules["orjson"] = m
    _quiet_close()


def _quiet_close() -> None:
    """Several of Mishkal's libraries close their SQLite connection in
    __del__, which at exit may run on another thread and print a harmless
    traceback; silence it."""
    import importlib
    for mod, cls in (("arramooz.arabicdictionary", "ArabicDictionary"), ("asmai.semdictionary", "SemanticDictionary"),
                     ("maskouk.collocationdictionary", "collocationDictionary")):
        try:
            c = getattr(importlib.import_module(mod), cls)
            if getattr(c, "_aba_quiet", False) or not hasattr(c, "__del__"):
                continue
            orig = c.__del__

            def _del(self, _orig=orig):
                try:
                    _orig(self)
                except Exception:
                    pass
            c.__del__ = _del
            c._aba_quiet = True
        except Exception:
            pass


_engine = None
_lock = threading.Lock()
_error: Optional[str] = None
# Mishkal's dictionaries are SQLite connections, which may only be used by the
# thread that opened them, so every call runs on this one worker thread.
from concurrent.futures import ThreadPoolExecutor  # noqa: E402
_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mishkal")


def available() -> bool:
    try:
        import mishkal  # noqa: F401
        return True
    except Exception:
        return False


def engine():
    """Load Mishkal once (it takes a couple of seconds) and keep it."""
    return _worker.submit(_load).result()


def _load():
    global _engine, _error
    with _lock:
        if _engine is None and _error is None:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    _orjson_fallback()
                    import mishkal.tashkeel as tk
                    _engine = tk.TashkeelClass()
            except Exception as e:                       # pragma: no cover - environment specific
                _error = f"{type(e).__name__}: {e}"
        return _engine


def preload() -> None:
    _worker.submit(_load)


def _run(text: str) -> str:
    e = _load()
    if e is None:
        raise RuntimeError("المشكِّل الآلي غير متاح في هذه النسخة.")
    out = []
    for line in text.split("\n"):
        out.append(e.tashkeel(line).strip() if line.strip() else line)
    return "\n".join(out)


def diacritize(text: str) -> str:
    return _worker.submit(_run, text).result()
