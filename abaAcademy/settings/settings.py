# -*- coding: utf-8 -*-
"""
abaAcademy.settings.settings
============================

Typed settings facade over the database ``settings`` table. Centralizes
defaults and coercion so the rest of the app reads booleans/ints, not strings.

Settings are intentionally few and learner-facing: speech on/off, strict
tashkeel grading, questions-per-session, whether to auto-resume, and the
Arabic diacritics grading policy. Everything persists in the same SQLite file
as progress, so a learner's preferences survive add-on updates.
"""

from __future__ import annotations

from typing import Any

DEFAULTS = {
    "speech_enabled": "1",
    "strict_tashkeel": "0",
    "session_size": "12",
    "auto_resume": "1",
    "endless_batch": "10",
    "announce_progress": "1",
}


class Settings:
    def __init__(self, store):
        self._store = store

    def _get(self, key: str) -> str:
        return self._store.get_setting(key, DEFAULTS.get(key, ""))

    def get_bool(self, key: str) -> bool:
        return self._get(key) == "1"

    def get_int(self, key: str, fallback: int = 0) -> int:
        try:
            return int(self._get(key))
        except (TypeError, ValueError):
            return fallback

    def set_bool(self, key: str, value: bool) -> None:
        self._store.set_setting(key, "1" if value else "0")

    def set_int(self, key: str, value: int) -> None:
        self._store.set_setting(key, str(int(value)))

    # convenience properties
    @property
    def speech_enabled(self) -> bool:
        return self.get_bool("speech_enabled")

    @property
    def strict_tashkeel(self) -> bool:
        return self.get_bool("strict_tashkeel")

    @property
    def session_size(self) -> int:
        return self.get_int("session_size", 12)

    @property
    def difficulty_pref(self) -> str:
        """'adaptive' (tutor decides), or 'easy'/'medium'/'hard' to override."""
        v = self._get("difficulty_pref")
        return v if v in ("adaptive", "easy", "medium", "hard") else "adaptive"

    @property
    def lenient_answers(self) -> bool:
        """When True (default), accept Arabic orthographic variants (hamza,
        ta-marbuta, spacing). When False, the learner wants exact spelling."""
        v = self._get("lenient_answers")
        return v != "0"          # default on unless explicitly disabled
