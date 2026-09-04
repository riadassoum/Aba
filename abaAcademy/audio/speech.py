# -*- coding: utf-8 -*-
"""
abaAcademy.audio.speech
=======================

Speech policy for the academy. Every announcement goes through a manager with
this interface so behaviour is consistent and testable.

* **Cancel-before-speak.** ``announce(...)`` cancels any in-progress speech
  before queuing new text, so a new question never queues behind the previous
  one.
* **Headless by default.** This base implementation records what *would* be
  said into ``log`` instead of producing sound, which is what the unit tests
  assert against. The running application substitutes a manager backed by a real
  synthesiser (see the desktop package), keeping this same tiny surface.

The surface stays deliberately small — ``announce``, ``interrupt``,
``speak_line`` — because the policy of *what* to say and *when* lives in the
GUI's ``AccessibleDialog`` base, not here.
"""

from __future__ import annotations

from typing import List, Optional


class SpeechManager:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        # Captures what would be spoken; the tests assert against this.
        self.log: List[str] = []

    def interrupt(self) -> None:
        """Immediately stop current speech."""
        if not self.enabled:
            return

    def announce(self, text: str, *, interrupt: bool = True,
                 braille: bool = True) -> None:
        """Speak ``text`` (cancelling prior speech first by default)."""
        if not text:
            return
        self.log.append(text)
        if not self.enabled:
            return

    def speak_line(self, text: str) -> None:
        """Speak without interrupting — used to read sequential lines."""
        self.announce(text, interrupt=False)

    def last(self) -> Optional[str]:
        return self.log[-1] if self.log else None
