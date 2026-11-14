# -*- coding: utf-8 -*-
"""
abaAcademy.generators.arabic
============================

Procedural Arabic-language generators. Unlike ``generic.*`` (which only shuffle
author-supplied frames), these *compute* answers from small rule tables, so one
generator yields thousands of distinct, correct items.

They are still data-driven where it matters: the word lists they draw from are
passed in via ``params`` (ultimately from the Arabic content pack's data
files), so the generator encodes the *rule*, not the vocabulary. This keeps the
"engine knows nothing about Arabic" boundary honest — these live in the
generators layer, are optional, and are only invoked when a JSON block names
them.

Generators here:
  * ``ar.sun_moon``   — is the definite article's laam pronounced or assimilated?
  * ``ar.plural``     — sound vs. broken plural recognition (from a word table)
  * ``ar.conjugate``  — present-tense pronoun+verb agreement (from a verb table)
  * ``ar.hamza_pos``  — on which seat does a medial hamza sit (strongest-vowel rule)
"""

from __future__ import annotations

import random
from typing import Dict, List

from ..engine.models import Question, QuestionType
from . import Deduper, register, signature_qid

# The 14 "sun" letters: the laam of "ال" assimilates into them (الشّمس).
SUN_LETTERS = set("تثدذرزسشصضطظلن")
# The 14 "moon" letters: the laam is pronounced clearly (القمر).
MOON_LETTERS = set("ابجحخعغفقكمهوي")


@register("ar.sun_moon")
def gen_sun_moon(count: int, rng: random.Random, **params) -> List[Question]:
    """Given definite nouns, ask whether the laam is shamsiyya or qamariyya."""
    words: List[str] = list(params.get("words", []))
    # Keep only "ال"-prefixed words whose first root letter we can classify.
    usable = []
    for w in words:
        core = w
        if core.startswith("ال") and len(core) > 2:
            first = core[2]
            if first in SUN_LETTERS or first in MOON_LETTERS:
                usable.append((core, first))
    if not usable:
        return []
    out: List[Question] = []
    dd = Deduper()
    guard = 0
    while len(out) < count and guard < count * 40:
        guard += 1
        word, first = rng.choice(usable)
        if not dd.fresh(word):
            continue
        dd.add(word)
        is_sun = first in SUN_LETTERS
        correct_label = "لام شمسية (تُدغم ولا تُنطق)" if is_sun else "لام قمرية (تُنطق واضحة)"
        wrong_label = "لام قمرية (تُنطق واضحة)" if is_sun else "لام شمسية (تُدغم ولا تُنطق)"
        options = [correct_label, wrong_label]
        rng.shuffle(options)
        q = Question(
            qtype=QuestionType.MCQ,
            prompt=f"ما نوع اللام في كلمة {word}؟",
            correct=options.index(correct_label),
            options=options,
            explanation=(f"الحرف {first} من الحروف "
                         + ("الشمسية، فتُدغم اللام فيه ويُشدَّد." if is_sun
                            else "القمرية، فتُنطق اللام واضحة.")),
            topic="ar.sun_moon",
            difficulty=1,
        )
        q.qid = signature_qid("ar.sun_moon", word)
        out.append(q)
    return out


@register("ar.plural")
def gen_plural(count: int, rng: random.Random, **params) -> List[Question]:
    """Ask for the plural of a singular noun (typing), from a data table.

    ``params['pairs']`` is a list of ``{"singular", "plural", "kind"}`` where
    kind is e.g. "سالم مذكر" / "سالم مؤنث" / "تكسير". The generator can quiz
    either the plural form (typing) or its classification (MCQ).
    """
    pairs: List[Dict] = list(params.get("pairs", []))
    if not pairs:
        return []
    kinds = sorted({p.get("kind", "") for p in pairs if p.get("kind")})
    out: List[Question] = []
    dd = Deduper()
    guard = 0
    while len(out) < count and guard < count * 40:
        guard += 1
        p = rng.choice(pairs)
        singular = p.get("singular", "")
        plural = p.get("plural", "")
        if not singular or not plural or not dd.fresh(singular):
            continue
        dd.add(singular)
        if rng.random() < 0.5 or len(kinds) < 2:
            q = Question(
                qtype=QuestionType.TYPING,
                prompt=f"اكتب جمع كلمة {singular}:",
                correct=plural,
                accepted=list(p.get("accepted", [])),
                explanation=f"جمع {singular} هو {plural}"
                            + (f" (جمع {p['kind']})." if p.get("kind") else "."),
                topic="ar.plural",
            )
        else:
            kind = p.get("kind", kinds[0])
            options = list(dict.fromkeys([kind] + kinds))[:4]
            rng.shuffle(options)
            q = Question(
                qtype=QuestionType.MCQ,
                prompt=f"ما نوع جمع {plural} (جمع {singular})؟",
                correct=options.index(kind),
                options=options,
                explanation=f"{plural} جمع {kind}.",
                topic="ar.plural",
            )
        q.qid = signature_qid("ar.plural", singular + plural)
        out.append(q)
    return out


# Present-tense prefixes/suffixes for the sound conjugation of a triliteral
# verb given its present stem. Keyed by pronoun label.
_CONJ_TABLE = {
    "أنا": ("أ", ""),
    "نحن": ("ن", ""),
    "أنتَ": ("ت", ""),
    "أنتِ": ("ت", "ين"),
    "هو": ("ي", ""),
    "هي": ("ت", ""),
    "هم": ("ي", "ون"),
    "أنتم": ("ت", "ون"),
}


@register("ar.conjugate")
def gen_conjugate(count: int, rng: random.Random, **params) -> List[Question]:
    """Conjugate a present-tense verb for a random pronoun.

    ``params['verbs']`` is a list of ``{"stem", "meaning"}`` where ``stem`` is
    the bare present stem after the subject prefix, e.g. for يكتب the stem is
    "كتب" and we prepend the pronoun's prefix. Distractors are other pronouns'
    forms of the same verb — i.e. plausible agreement mistakes.
    """
    verbs: List[Dict] = list(params.get("verbs", []))
    if not verbs:
        return []
    pronouns = list(_CONJ_TABLE.keys())
    out: List[Question] = []
    dd = Deduper()
    guard = 0
    while len(out) < count and guard < count * 60:
        guard += 1
        verb = rng.choice(verbs)
        stem = verb.get("stem", "")
        if not stem:
            continue
        pronoun = rng.choice(pronouns)
        sig = stem + "|" + pronoun
        if not dd.fresh(sig):
            continue
        dd.add(sig)
        pre, suf = _CONJ_TABLE[pronoun]
        correct = pre + stem + suf
        # Distractors: same verb, other pronouns (classic agreement errors).
        wrongs = []
        for other in rng.sample(pronouns, len(pronouns)):
            if other == pronoun:
                continue
            wpre, wsuf = _CONJ_TABLE[other]
            form = wpre + stem + wsuf
            if form != correct and form not in wrongs:
                wrongs.append(form)
            if len(wrongs) >= 3:
                break
        options = wrongs[:3] + [correct]
        options = list(dict.fromkeys(options))
        rng.shuffle(options)
        q = Question(
            qtype=QuestionType.MCQ,
            prompt=f"صرّف الفعل (الجذر المضارع {stem}، بمعنى {verb.get('meaning','')}) مع الضمير {pronoun}:",
            correct=options.index(correct),
            options=options,
            explanation=f"مع {pronoun} يكون التصريف {correct}.",
            topic="ar.conjugate",
            difficulty=2,
        )
        q.qid = signature_qid("ar.conjugate", sig)
        out.append(q)
    return out


# Seat of a medial hamza by the "strongest vowel" rule.
# priority: kasra (ئ) > damma (ؤ) > fatha (أ) > sukun (on the line-ish).
def _hamza_seat(prev_vowel: str, hamza_vowel: str) -> str:
    order = {"kasra": 3, "damma": 2, "fatha": 1, "sukun": 0}
    seat_for = {"kasra": "ئ", "damma": "ؤ", "fatha": "أ", "sukun": "ء"}
    strongest = prev_vowel if order[prev_vowel] >= order[hamza_vowel] else hamza_vowel
    return seat_for[strongest]


@register("ar.hamza_pos")
def gen_hamza_pos(count: int, rng: random.Random, **params) -> List[Question]:
    """On which seat does the medial hamza sit? Computed from vowel pairs.

    ``params['cases']`` is a list of ``{"word_hint", "prev", "hamza"}`` where
    prev/hamza are vowel names in {fatha,damma,kasra,sukun}. The correct seat
    is derived; distractors are the other three seats.
    """
    cases: List[Dict] = list(params.get("cases", []))
    if not cases:
        return []
    all_seats = ["أ", "ؤ", "ئ", "ء"]
    vowel_ar = {"fatha": "فتحة", "damma": "ضمة", "kasra": "كسرة", "sukun": "سكون"}
    out: List[Question] = []
    dd = Deduper()
    guard = 0
    while len(out) < count and guard < count * 40:
        guard += 1
        case = rng.choice(cases)
        prev = case.get("prev")
        hamza = case.get("hamza")
        if prev not in vowel_ar or hamza not in vowel_ar:
            continue
        sig = case.get("word_hint", "") + prev + hamza
        if not dd.fresh(sig):
            continue
        dd.add(sig)
        correct = _hamza_seat(prev, hamza)
        options = [correct] + [s for s in all_seats if s != correct][:3]
        options = list(dict.fromkeys(options))
        rng.shuffle(options)
        q = Question(
            qtype=QuestionType.MCQ,
            prompt=(f"همزة متوسطة حركتها {vowel_ar[hamza]} وما قبلها {vowel_ar[prev]} "
                    f"({case.get('word_hint','')}) — على أي حرف تُكتب؟"),
            correct=options.index(correct),
            options=options,
            explanation=(f"القاعدة: تُكتب الهمزة على حرف يناسب أقوى الحركتين "
                         f"(الكسرة ثم الضمة ثم الفتحة ثم السكون)، فتكون على {correct}."),
            topic="ar.hamza_pos",
            difficulty=3,
        )
        q.qid = signature_qid("ar.hamza_pos", sig)
        out.append(q)
    return out
