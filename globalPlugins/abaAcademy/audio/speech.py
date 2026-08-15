# -*- coding: utf-8 -*-
"""
abaAcademy.audio.speech
=======================

Central speech + braille manager. Every announcement in the application goes
through here so behavior is consistent and testable.

Key guarantees demanded by the spec:

* **Cancel-before-speak.** ``announce(...)`` cancels any in-progress speech
  before queuing new text, so a new question never queues behind the previous
  one. (This is the "cancel previous speech before reading new content"
  requirement.)
* **Braille too.** Each announcement is also written to the braille display via
  NVDA's braille API.
* **Graceful outside NVDA.** When the NVDA runtime modules aren't importable
  (unit tests, this build sandbox), the manager records messages to an internal
  log instead of raising, so logic can be tested headlessly.

The manager intentionally exposes a tiny surface — ``announce``, ``interrupt``,
``speak_line`` — because the accessibility policy (what to say, and when) lives
in the GUI's ``AccessibleDialog`` base, not here.
"""

from __future__ import annotations

from typing import List, Optional

try:  # Real NVDA runtime
    import speech as nvda_speech
    import braille as nvda_braille
    import queueHandler
    import api as nvda_api
    _NVDA = True
except Exception:  # Sandbox / unit tests
    _NVDA = False


class SpeechManager:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        # Headless capture for tests / debugging when NVDA isn't present.
        self.log: List[str] = []

    def interrupt(self) -> None:
        """Immediately stop current speech."""
        if not self.enabled:
            return
        if _NVDA:
            try:
                nvda_speech.cancelSpeech()
            except Exception:
                pass

    def announce(self, text: str, *, interrupt: bool = True,
                 braille: bool = True) -> None:
        """Speak ``text`` (cancelling prior speech first by default)."""
        if not text:
            return
        self.log.append(text)
        if not self.enabled:
            return
        if _NVDA:
            try:
                if interrupt:
                    nvda_speech.cancelSpeech()
                nvda_speech.speakMessage(text)
                if braille:
                    nvda_braille.handler.message(text)
            except Exception:
                pass

    def speak_line(self, text: str) -> None:
        """Speak without interrupting — used to read sequential lines."""
        self.announce(text, interrupt=False)

    def last(self) -> Optional[str]:
        return self.log[-1] if self.log else None
