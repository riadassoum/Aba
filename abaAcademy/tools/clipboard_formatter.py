# -*- coding: utf-8 -*-
"""
abaAcademy.tools.clipboard_formatter
====================================

Deterministic, offline Arabic text cleaning — the engine behind the "smart
clipboard formatter". Copied Arabic text is often messy for a screen-reader user:
Eastern/Western digits mixed, punctuation floating away from its word, stray
tatweel (ـــ) and soft hyphens, and runs of blank lines. Each of the functions
here fixes one specific, well-defined problem, and :func:`clean_text` applies a
chosen subset. Everything is pure ``re``/``str`` — no network, no data files, and
fully reversible in the sense that each option can be toggled independently.
"""

from __future__ import annotations

import re
import unicodedata


_ARABIC_INDIC = "٠١٢٣٤٥٦٧٨٩"
_EXTENDED_INDIC = "۰۱۲۳۴۵۶۷۸۹"   # Persian/Urdu forms
_WESTERN = "0123456789"

_TATWEEL = "\u0640"
_SOFT_HYPHEN = "\u00ad"
_ZERO_WIDTH = ["\u200b", "\u200c", "\u200d", "\ufeff", "\u200e", "\u200f"]


def to_western_digits(text):
    """Convert Arabic-Indic and Persian digits to Western (0-9)."""
    table = {}
    for i, ch in enumerate(_ARABIC_INDIC):
        table[ord(ch)] = _WESTERN[i]
    for i, ch in enumerate(_EXTENDED_INDIC):
        table[ord(ch)] = _WESTERN[i]
    return text.translate(table)


def to_arabic_digits(text):
    """Convert Western digits to Arabic-Indic (٠-٩)."""
    table = {ord(_WESTERN[i]): _ARABIC_INDIC[i] for i in range(10)}
    return text.translate(table)


def strip_tatweel(text):
    """Remove kashida/tatweel elongation characters."""
    return text.replace(_TATWEEL, "")


def strip_invisibles(text):
    """Remove soft hyphens and zero-width / bidi-control characters that clutter
    speech output."""
    text = text.replace(_SOFT_HYPHEN, "")
    for zw in _ZERO_WIDTH:
        text = text.replace(zw, "")
    return text


def fix_punctuation_spacing(text):
    """Attach Arabic/Latin punctuation to the previous word and ensure a single
    space after it. Handles ، ؛ ؟ ! : . and the Latin equivalents."""
    # remove space(s) BEFORE these punctuation marks
    text = re.sub(r"\s+([،؛؟!:\.,;?])", r"\1", text)
    # ensure exactly one space AFTER them when followed by a word char
    text = re.sub(r"([،؛؟!:،,;?])(?=\S)", r"\1 ", text)
    # collapse doubled spaces introduced above
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


def collapse_blank_lines(text):
    """Collapse 3+ consecutive newlines to a single blank line, and trim trailing
    spaces on each line."""
    text = re.sub(r"[ \t]+(\n)", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip("\n")


def normalize_spaces(text):
    """Collapse runs of spaces/tabs to one, leaving newlines intact."""
    return re.sub(r"[ \t]{2,}", " ", text)


def clean_text(text, *, digits="none", tatweel=True, invisibles=True,
               punctuation=True, blank_lines=True, spaces=True):
    """Apply the selected cleaning steps.

    ``digits``: "none" | "western" | "arabic".
    The boolean flags toggle each fix. Returns the cleaned text.
    """
    if text is None:
        return ""
    out = text
    if invisibles:
        out = strip_invisibles(out)
    if tatweel:
        out = strip_tatweel(out)
    if digits == "western":
        out = to_western_digits(out)
    elif digits == "arabic":
        out = to_arabic_digits(out)
    if punctuation:
        out = fix_punctuation_spacing(out)
    if spaces:
        out = normalize_spaces(out)
    if blank_lines:
        out = collapse_blank_lines(out)
    return out


def describe_changes(before, after):
    """A short Arabic summary of what changed, for spoken feedback."""
    if before == after:
        return "لا تغييرات؛ النص نظيف بالفعل."
    parts = []
    if len(before) != len(after):
        diff = len(before) - len(after)
        if diff > 0:
            parts.append(f"أُزيل {abs(diff)} حرفاً زائداً")
        else:
            parts.append(f"أُضيف {abs(diff)} فراغاً منظِّماً")
    return "تم تنظيف النص. " + ("، ".join(parts) + "." if parts else "")
