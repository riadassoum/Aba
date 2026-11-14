# -*- coding: utf-8 -*-
"""
abaAcademy.speakable
====================

Text cleanup applied to everything the academy speaks.

Some Arabic voices read typographic quotation marks by name: «كلمة» comes out
as "علامة تنصيص مزدوجة للفتح، كلمة، علامة تنصيص مزدوجة للإغلاق". The academy's
own texts no longer use them, and this filter removes them from anything else
that reaches the voice (a learner's imported cards, a document, a pasted text).
"""

from __future__ import annotations

import re

_QUOTES = str.maketrans({"«": "", "»": "", "‹": "", "›": "", "“": "", "”": "", "„": "", "‟": ""})
_SPACES = re.compile(r"[ \t]{2,}")


def speakable(text) -> str:
    if not text:
        return ""
    t = str(text).translate(_QUOTES)
    return _SPACES.sub(" ", t).strip()


def has_quote_marks(text: str) -> bool:
    return any(ch in text for ch in "«»‹›“”„‟")
