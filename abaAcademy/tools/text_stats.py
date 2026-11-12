# -*- coding: utf-8 -*-
"""
abaAcademy.tools.text_stats
===========================

Text statistics for a student's writing: words, characters with and without
spaces, sentences, paragraphs, Arabic vs Latin letters, diacritics, average
word and sentence length, reading and speaking time, the most frequent
words (ignoring common Arabic and English function words) and repeated
words that may need varying.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Tuple

from .ar_count import count

_TASHKEEL = re.compile("[ً-ْٰ]")
_AR_LETTER = re.compile("[ء-ي]")
_LAT_LETTER = re.compile("[A-Za-z]")
_WORD = re.compile(r"[\w؀-ۿ]+(?:['’][\w]+)?")
_SENT_END = re.compile(r"[.!?؟。]+|\n\s*\n")

STOP_AR = set("""في من على إلى عن أن إن كان كانت هذا هذه ذلك التي الذي الذين ما لا لم لن قد ثم أو و
مع كل بعد قبل بين عند حتى إذا هو هي هم هن أنا نحن أنت أنتم كما أيضا أي فيه فيها به بها له لها منه
منها عليه عليها إليه وهو وهي وقد ولا وفي ومن وعلى ليس غير بل""".split())
STOP_EN = set("""the a an and or of to in on for with is are was were be been it this that as at by
from but not have has had i you he she we they his her its their our your""".split())


def analyse(text: str, wpm_read: int = 200, wpm_speak: int = 130) -> Dict[str, object]:
    words = _WORD.findall(_TASHKEEL.sub("", text))
    sentences = [s for s in _SENT_END.split(text) if _WORD.search(s)]
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    letters = len(_AR_LETTER.findall(text)) + len(_LAT_LETTER.findall(text))
    norm = [w.lower() for w in words]
    content = [w for w in norm if w not in STOP_AR and w not in STOP_EN and len(w) > 2]
    freq = Counter(content)
    return {
        "words": len(words),
        "unique": len(set(norm)),
        "chars": len(text),
        "chars_no_spaces": len(re.sub(r"\s", "", text)),
        "letters": letters,
        "arabic_letters": len(_AR_LETTER.findall(text)),
        "latin_letters": len(_LAT_LETTER.findall(text)),
        "diacritics": len(_TASHKEEL.findall(text)),
        "sentences": len(sentences),
        "paragraphs": len(paragraphs),
        "avg_word": (sum(len(w) for w in words) / len(words)) if words else 0.0,
        "avg_sentence": (len(words) / len(sentences)) if sentences else 0.0,
        "read_minutes": len(words) / wpm_read,
        "speak_minutes": len(words) / wpm_speak,
        "top": freq.most_common(10),
        "repeated": [(w, n) for w, n in freq.most_common() if n >= 3][:10],
        "long_sentences": sum(1 for s in sentences if len(_WORD.findall(s)) > 35),
    }


def _minutes(m: float) -> str:
    secs = round(m * 60)
    if secs < 60:
        return count(secs, "second")
    mins, s = divmod(secs, 60)
    return count(mins, "minute") + (f" و{count(s, 'second')}" if s else "")


def report(text: str) -> List[str]:
    if not text.strip():
        raise ValueError("اكتب نصًّا أو الصقه أولًا.")
    a = analyse(text)
    lines = [
        f"عدد الكلمات: {a['words']} (منها {count(a['unique'], 'kalima')} مختلفة).",
        f"عدد الحروف والرموز: {a['chars']}، ودون المسافات: {a['chars_no_spaces']}.",
        f"الحروف العربية: {a['arabic_letters']}، واللاتينية: {a['latin_letters']}، "
        f"وعلامات الشكل: {a['diacritics']}.",
        f"الجمل: {a['sentences']}، والفقرات: {a['paragraphs']}.",
        f"متوسّط طول الكلمة {a['avg_word']:.1f} حرف، ومتوسّط طول الجملة {a['avg_sentence']:.1f} كلمة.",
        f"وقت القراءة الصامتة نحو {_minutes(a['read_minutes'])}، ووقت الإلقاء نحو {_minutes(a['speak_minutes'])}.",
    ]
    if a["top"]:
        lines.append("أكثر الكلمات ورودًا: " + "، ".join(f"{w} ({n})" for w, n in a["top"][:6]) + ".")
    if a["repeated"]:
        lines.append("كلمات تكرّرت ثلاث مرّات أو أكثر، فكّر في تنويعها: "
                     + "، ".join(w for w, _ in a["repeated"][:6]) + ".")
    if a["long_sentences"]:
        lines.append(f"في النصّ {count(a['long_sentences'], 'case')} لجمل طويلة جدًّا (أكثر من ٣٥ كلمة)؛ "
                     f"تقسيمها يسهّل الفهم.")
    return lines
