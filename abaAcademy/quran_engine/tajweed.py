# -*- coding: utf-8 -*-
"""
abaAcademy.quran_engine.tajweed
===============================

Lightweight, rule-based Tajweed cueing for reading mode. As a learner reads an
ayah, this flags the Tajweed rules that are *reliably detectable from the written
Uthmani text itself*, and offers a short earcon and an Arabic explanation for
each — a study aid that draws attention to where a rule applies.

Honest scope
------------
Full Tajweed is an oral discipline; many rules depend on recitation, breath, and
context that written text cannot fully determine, and authoritative Tajweed
colour-coded texts are built by scholars, not by an algorithm. We do NOT claim to
detect every rule. What this module detects are the categories that follow
deterministically from the letters present:

* **قلقلة (Qalqalah)** — the letters ق ط ب ج د when carrying sukoon.
* **مدّ (Madd) letters** — the long-vowel letters ا و ي in a madd context, with
  the obligatory madd sign where present.
* **غنّة (Ghunnah)** — noon and meem with shadda (نّ مّ).
* **حروف الشمس (Sun letters)** — the لام of "ال" assimilating into a sun letter.

Each hit is returned with the position, the rule name, and a short explanation.
The reading screen can play a subtle earcon and, on request, speak the rule. We
label this clearly in the UI as a study aid, not a certified Tajweed text.
"""

from __future__ import annotations

import math
import struct

_SR = 22050

# --- Arabic letters / marks -------------------------------------------------
_SUKOON = "\u0652"
_SHADDA = "\u0651"
_MADD_SIGN = "\u0653"        # maddah above
_FATHA = "\u064E"
_DAMMA = "\u064F"
_KASRA = "\u0650"

_QALQALAH = set("قطبجد")
_SUN_LETTERS = set("تثدذرزسشصضطظلن")
_MADD_LETTERS = set("اوي")


class TajweedRule:
    __slots__ = ("index", "kind", "name", "explanation")

    def __init__(self, index, kind, name, explanation):
        self.index = index
        self.kind = kind
        self.name = name
        self.explanation = explanation


def _following_marks(text, i):
    """Collect the diacritic marks that belong to the letter at index i (they can
    appear in either order, e.g. letter+fatha+shadda), stopping at the next base
    letter. Returns the set of mark characters."""
    marks = set()
    j = i + 1
    n = len(text)
    while j < n and _is_mark(text[j]):
        marks.add(text[j])
        j += 1
    return marks


def _is_mark(ch):
    import unicodedata
    return unicodedata.category(ch) == "Mn"


def analyse_ayah(text):
    """Return a list of TajweedRule hits for an ayah's Uthmani text. Positions are
    character indices into ``text``."""
    hits = []
    n = len(text)
    for i, ch in enumerate(text):
        marks = _following_marks(text, i)
        nxt = _next_base_letter(text, i)
        # qalqalah: a qalqalah letter carrying sukoon
        if ch in _QALQALAH and _SUKOON in marks:
            hits.append(TajweedRule(i, "qalqalah", "قلقلة",
                                    f"حرف «{ch}» ساكن: يُقلقَل بنبرة خفيفة."))
        # ghunnah: noon or meem carrying shadda
        if ch in "نم" and _SHADDA in marks:
            hits.append(TajweedRule(i, "ghunnah", "غنّة",
                                    f"«{ch}» مشدّدة: تُغَنّ بمقدار حركتين."))
        # madd: a madd letter carrying the maddah sign
        if ch in _MADD_LETTERS and _MADD_SIGN in marks:
            hits.append(TajweedRule(i, "madd", "مدّ",
                                    f"حرف مدّ «{ch}»: يُمدّ."))
        # sun-letter assimilation: 'ال' followed by a sun letter (not lam itself,
        # to exclude the divine name). The article alef is often ALEF WASLA.
        if ch == "ل" and i >= 1 and text[i - 1] in ("ا", "\u0671", "\u0627"):
            if nxt in _SUN_LETTERS and nxt != "ل":
                hits.append(TajweedRule(i, "sun", "لام شمسية",
                                        f"اللام لا تُنطق وتُدغم في «{nxt}»."))
    return hits


def _next_base_letter(text, i):
    """The next non-mark (base) letter after index i, or '' if none."""
    j = i + 1
    n = len(text)
    while j < n and _is_mark(text[j]):
        j += 1
    return text[j] if j < n else ""


def rules_summary(hits):
    """Spoken Arabic summary of which rules occur in the ayah."""
    if not hits:
        return "لا توجد أحكام تجويد بارزة يمكن كشفها من النص في هذه الآية."
    from collections import Counter
    counts = Counter(h.name for h in hits)
    parts = [f"{name} ({c})" for name, c in counts.items()]
    return "أحكام في هذه الآية: " + "، ".join(parts) + "."


# --- earcons (synthesised, no files) ---------------------------------------

def _tone(freq, dur, amp=0.35, sr=_SR):
    n = max(1, int(sr * dur))
    fade = max(1, int(sr * 0.006))
    out = bytearray()
    for i in range(n):
        env = 1.0
        if i < fade:
            env = i / fade
        elif i > n - fade:
            env = max(0.0, (n - i) / fade)
        s = amp * env * math.sin(2 * math.pi * freq * i / sr)
        v = int(max(-1, min(1, s)) * 32767)
        out += struct.pack("<hh", v, v)
    return bytes(out)


def earcon(kind):
    """A distinct, subtle earcon per rule kind. Kept short and few (all
    synthesised): qalqalah = a quick low bounce, ghunnah = a soft hum, madd = a
    longer gentle tone, sun-letter = a short two-tone slur."""
    if kind == "qalqalah":
        return _tone(180, 0.05) + _tone(120, 0.06)
    if kind == "ghunnah":
        return _tone(300, 0.18, amp=0.25)
    if kind == "madd":
        return _tone(440, 0.28, amp=0.22)
    if kind == "sun":
        return _tone(520, 0.05) + _tone(400, 0.06)
    return b""
