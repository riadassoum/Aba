# -*- coding: utf-8 -*-
"""
abaAcademy.bootstrap
====================

Wires runtime dependencies and hands back a ready ``Academy`` plus a
``SpeechManager``. Resolves two locations:

* the add-on's own directory (bundled course packs live in ``courses/``),
* a persistent user-data directory under NVDA's config path, so the SQLite
  progress DB and any user-installed course packs survive add-on updates.

Kept separate from ``app.py`` (which owns GUI lifecycle) so the wiring can be
constructed headlessly in tests.
"""

from __future__ import annotations

import os

from .academy import Academy
from .audio.speech import SpeechManager

_ADDON_DIR = os.path.dirname(os.path.abspath(__file__))


def _user_data_dir() -> str:
    try:
        import globalVars
        base = globalVars.appArgs.configPath
    except Exception:
        base = os.path.expanduser("~")
    path = os.path.join(base, "abaAcademy")
    os.makedirs(path, exist_ok=True)
    return path


def create_academy() -> "tuple[Academy, SpeechManager]":
    speech = SpeechManager(enabled=True)
    academy = Academy(base_dir=_ADDON_DIR, user_data_dir=_user_data_dir(), speech=speech)
    # honor stored speech preference
    speech.enabled = academy.settings.get_bool("speech_enabled")
    return academy, speech
