# -*- coding: utf-8 -*-
"""
abaAcademy.generators.braille
=============================

Braille generators that *compute* every answer from a single authoritative
table instead of relying on hand-written question banks.

Why computed
------------
The previous braille course hard-coded a few dozen multiple-choice items, one
per letter, written out by hand. That is both finite (the course ran out after
a couple of dozen questions) and fragile (a typo in one option list is a wrong
answer taught confidently to a blind learner, which is the worst kind of bug
this add-on could have).

Here the source of truth is the Unicode braille character for each sign, taken
from the standard Arabic and English braille tables. Unicode encodes the cell
directly: ``U+2800`` plus a bitmask where bit 0 is dot 1, bit 1 is dot 2, and
so on through dot 6. So the dot numbers are *derived*, never typed, and every
question and every distractor is guaranteed self-consistent.

From one table we can then ask, in both directions and several shapes:
  * ``braille.cell``   — sign → dots, dots → sign, true/false, typed dots
  * ``braille.word``   — spell a whole word cell by cell
  * ``braille.count``  — how many dots does a sign use (a real beginner skill)

Generators are unlimited: a table of twenty-eight letters supports drilling
indefinitely because each letter can be asked several ways and every option
set is resampled per draw.
"""

from __future__ import annotations

import random
from typing import Dict, List, Tuple

from ..engine.models import Question, QuestionType
from . import fill_to_count, register, shuffled_options, signature_qid

# --- authoritative tables -------------------------------------------------
# Values are the Unicode braille cell for the sign. Dot numbers are computed
# from these, so these strings are the only thing that must be right.

ARABIC_LETTERS: Dict[str, str] = {
    "ا": "\u2801", "ب": "\u2803", "ت": "\u281E", "ث": "\u2839", "ج": "\u281A",
    "ح": "\u2831", "خ": "\u282D", "د": "\u2819", "ذ": "\u282E", "ر": "\u2817",
    "ز": "\u2835", "س": "\u280E", "ش": "\u2829", "ص": "\u282F", "ض": "\u282B",
    "ط": "\u283E", "ظ": "\u283F", "ع": "\u2837", "غ": "\u2823", "ف": "\u280B",
    "ق": "\u281F", "ك": "\u2805", "ل": "\u2807", "م": "\u280D", "ن": "\u281D",
    "ه": "\u2813", "و": "\u283A", "ي": "\u280A",
}

ARABIC_EXTRA: Dict[str, str] = {
    "ى": "\u2815", "ة": "\u2821", "ال": "\u2809", "لا": "\u2827",
    "أ": "\u280C", "إ": "\u2828", "آ": "\u281C", "ؤ": "\u2833",
    "ئ": "\u283D", "ء": "\u2804",
}

ARABIC_MARKS: Dict[str, str] = {
    "الضمة": "\u2825", "الفتحة": "\u2802", "الكسرة": "\u2811",
    "تنوين الضم": "\u2822", "تنوين الفتح": "\u2830", "تنوين الكسر": "\u2814",
    "السكون": "\u2812", "الشدة": "\u2820",
}

ENGLISH_LETTERS: Dict[str, str] = {
    "a": "\u2801", "b": "\u2803", "c": "\u2809", "d": "\u2819", "e": "\u2811",
    "f": "\u280B", "g": "\u281B", "h": "\u2813", "i": "\u280A", "j": "\u281A",
    "k": "\u2805", "l": "\u2807", "m": "\u280D", "n": "\u281D", "o": "\u2815",
    "p": "\u280F", "q": "\u281F", "r": "\u2817", "s": "\u280E", "t": "\u281E",
    "u": "\u2825", "v": "\u2827", "w": "\u283A", "x": "\u282D", "y": "\u283D",
    "z": "\u2835",
}

# Digits reuse the first ten letters after the number sign (dots 3-4-5-6).
NUMBER_SIGN = "\u283C"
DIGITS: Dict[str, str] = {
    "1": "\u2801", "2": "\u2803", "3": "\u2809", "4": "\u2819", "5": "\u2811",
    "6": "\u280B", "7": "\u281B", "8": "\u2813", "9": "\u280A", "0": "\u281A",
}

PUNCTUATION: Dict[str, str] = {
    "الفاصلة": "\u2802", "الفاصلة المنقوطة": "\u2806", "النقطتان": "\u2812",
    "النقطة": "\u2832", "علامة الاستفهام": "\u2826", "علامة التعجب": "\u2816",
    "الشرطة": "\u2824", "القوس": "\u2837",
}

TABLES: Dict[str, Dict[str, str]] = {
    "arabic": ARABIC_LETTERS,
    "arabic_extra": ARABIC_EXTRA,
    "arabic_marks": ARABIC_MARKS,
    "english": ENGLISH_LETTERS,
    "digits": DIGITS,
    "punctuation": PUNCTUATION,
}


# --- derivation helpers ---------------------------------------------------

def cell_dots(cell: str) -> Tuple[int, ...]:
    """Dot numbers of a Unicode braille cell, ascending.

    ``U+2800`` is the empty cell; each set bit adds one dot, bit 0 being dot 1.
    Deriving rather than transcribing is what makes the whole course
    self-consistent.
    """
    if not cell:
        return ()
    mask = ord(cell[0]) - 0x2800
    if mask < 0 or mask > 0xFF:
        return ()
    return tuple(bit + 1 for bit in range(6) if mask & (1 << bit))


def dots_label(cell: str) -> str:
    """Arabic phrase naming a cell's dots, e.g. 'النقاط ١، ٢، ٤'."""
    dots = cell_dots(cell)
    if not dots:
        return "خلية فارغة"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    names = [arabic_digits[d] for d in dots]
    if len(names) == 1:
        return f"النقطة {names[0]}"
    return "النقاط " + "، ".join(names)


def dots_plain(cell: str) -> str:
    """Bare dot numbers, e.g. '124' -- what a learner types."""
    return "".join(str(d) for d in cell_dots(cell))


def _resolve_table(params) -> Dict[str, str]:
    """Pick the sign table a block asked for, merging several if named."""
    names = params.get("table") or params.get("tables") or "arabic"
    if isinstance(names, str):
        names = [names]
    merged: Dict[str, str] = {}
    for name in names:
        merged.update(TABLES.get(str(name), {}))
    if not merged:
        # A block may also pass an inline table of {sign: unicode cell}.
        inline = params.get("signs")
        if isinstance(inline, dict):
            merged.update({str(k): str(v) for k, v in inline.items()})
    return merged


# --- generators -----------------------------------------------------------

@register("braille.cell")
def gen_cell(count: int, rng: random.Random, **params) -> List[Question]:
    """Sign ↔ dots, in four shapes."""
    table = _resolve_table(params)
    if not table:
        return []
    topic = params.get("topic", "braille.cell")
    all_labels = [dots_label(c) for c in table.values()]
    all_signs = list(table.keys())

    builders = []
    for sign, cell in table.items():
        label = dots_label(cell)
        plain = dots_plain(cell)
        if not plain:
            continue
        qid = signature_qid("braille.cell", sign)

        def sign_to_dots(sign=sign, label=label, qid=qid):
            options, index = shuffled_options(
                rng, label, [x for x in all_labels if x != label])
            if len(options) < 2:
                return None
            q = Question(qtype=QuestionType.MCQ,
                         prompt=f"ما نقاط برايل للرمز {sign}؟",
                         correct=index, options=options,
                         explanation=f"{sign} = {label}.",
                         topic=topic, difficulty=1)
            q.qid = qid
            return q

        def dots_to_sign(sign=sign, label=label, qid=qid):
            options, index = shuffled_options(
                rng, sign, [x for x in all_signs if x != sign])
            if len(options) < 2:
                return None
            q = Question(qtype=QuestionType.MCQ,
                         prompt=f"أي رمز تمثّله {label}؟",
                         correct=index, options=options,
                         explanation=f"{label} = {sign}.",
                         topic=topic, difficulty=2)
            q.qid = qid
            return q

        def judge(sign=sign, label=label, qid=qid):
            others = [x for x in all_labels if x != label]
            claim_true = not others or rng.random() < 0.5
            shown = label if claim_true else rng.choice(others)
            q = Question(qtype=QuestionType.TRUE_FALSE,
                         prompt=f"هل يُكتب الرمز {sign} بـ{shown}؟",
                         correct=claim_true,
                         explanation=(f"نعم، {sign} = {label}." if claim_true
                                      else f"لا، {sign} = {label}."),
                         topic=topic, difficulty=1)
            q.qid = qid
            return q

        def type_dots(sign=sign, label=label, plain=plain, qid=qid):
            spaced = "، ".join(plain)
            q = Question(qtype=QuestionType.TYPING,
                         prompt=f"اكتب أرقام نقاط الرمز {sign} متتاليةً بلا فواصل:",
                         correct=plain,
                         accepted=[spaced, " ".join(plain), "-".join(plain)],
                         explanation=f"{sign} = {label}.",
                         topic=topic, difficulty=3)
            q.qid = qid
            return q

        builders.extend([sign_to_dots, sign_to_dots, dots_to_sign, judge, type_dots])

    return [q for q in fill_to_count(builders, count, rng) if q is not None]


@register("braille.count")
def gen_count(count: int, rng: random.Random, **params) -> List[Question]:
    """How many dots does a sign use? A genuine early tactile skill."""
    table = _resolve_table(params)
    if not table:
        return []
    topic = params.get("topic", "braille.count")
    arabic_numbers = ["واحدة", "اثنتان", "ثلاث", "أربع", "خمس", "ست"]
    builders = []
    for sign, cell in table.items():
        dots = cell_dots(cell)
        if not dots:
            continue

        def make(sign=sign, cell=cell, dots=dots):
            n = len(dots)
            correct = arabic_numbers[n - 1]
            options, index = shuffled_options(
                rng, correct, [x for x in arabic_numbers if x != correct])
            q = Question(qtype=QuestionType.MCQ,
                         prompt=f"كم نقطة في الرمز {sign}؟",
                         correct=index, options=options,
                         explanation=f"{sign} = {dots_label(cell)}، أي {correct} نقاط.",
                         topic=topic, difficulty=1)
            q.qid = signature_qid("braille.count", sign)
            return q

        builders.append(make)
    return fill_to_count(builders, count, rng)


@register("braille.word")
def gen_word(count: int, rng: random.Random, **params) -> List[Question]:
    """Spell a word cell by cell.

    ``params['words']`` is a plain list of words. Every letter is looked up in
    the chosen table, so no per-word answer has to be authored -- and a word
    containing a letter outside the table is skipped rather than taught wrongly.
    """
    table = _resolve_table(params)
    words = [str(w) for w in params.get("words", []) if str(w).strip()]
    if not table or not words:
        return []
    topic = params.get("topic", "braille.word")

    usable = []
    for word in words:
        letters = [ch for ch in word if ch.strip()]
        if letters and all(ch in table for ch in letters):
            usable.append((word, letters))
    if not usable:
        return []

    builders = []
    for word, letters in usable:
        qid = signature_qid("braille.word", word)

        def which_letter(word=word, letters=letters, qid=qid):
            pos = rng.randrange(len(letters))
            target = letters[pos]
            label = dots_label(table[target])
            wrong = [dots_label(table[c]) for c in table
                     if dots_label(table[c]) != label]
            options, index = shuffled_options(rng, label, wrong)
            if len(options) < 2:
                return None
            q = Question(qtype=QuestionType.MCQ,
                         prompt=f"في كلمة {word}، ما نقاط الحرف رقم {pos + 1} ({target})؟",
                         correct=index, options=options,
                         explanation=f"{target} = {label}.",
                         topic=topic, difficulty=2)
            q.qid = qid
            return q

        def spell_all(word=word, letters=letters, qid=qid):
            answer = " ".join(dots_plain(table[c]) for c in letters)
            q = Question(
                qtype=QuestionType.TYPING,
                prompt=(f"اكتب كلمة {word} بالنقاط: أرقام نقاط كل حرف "
                        f"متتاليةً، وبين الحروف مسافة."),
                correct=answer,
                accepted=["-".join(dots_plain(table[c]) for c in letters)],
                explanation="الحل: " + "، ".join(
                    f"{c} {dots_label(table[c])}" for c in letters) + ".",
                topic=topic, difficulty=4)
            q.qid = qid
            return q

        def how_many_cells(word=word, letters=letters, qid=qid):
            correct = str(len(letters))
            wrong = [str(n) for n in range(1, len(letters) + 4) if str(n) != correct]
            options, index = shuffled_options(rng, correct, wrong)
            q = Question(qtype=QuestionType.MCQ,
                         prompt=f"كم خلية برايل تحتاج لكتابة كلمة {word}؟",
                         correct=index, options=options,
                         explanation=f"{word} فيها {len(letters)} حروف، فتحتاج {len(letters)} خلايا.",
                         topic=topic, difficulty=1)
            q.qid = qid
            return q

        builders.extend([which_letter, which_letter, how_many_cells, spell_all])

    return [q for q in fill_to_count(builders, count, rng) if q is not None]
