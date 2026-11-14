# -*- coding: utf-8 -*-
"""
abaAcademy.generators.phrases
=============================

Sentence-based language generators for the graded courses (English,
Spanish, Turkish, German, Italian, French…).

Every lesson of a graded course carries ``sentences``: real, human-translated
pairs ``{"t": foreign, "ar": Arabic}`` (from the Tatoeba project), chosen so
that every word in them was introduced in this lesson or an earlier one.
From those pairs the generators make:

  * ``phr.translate`` — hear/read a foreign sentence, choose its Arabic meaning
  * ``phr.reverse``   — read an Arabic sentence, choose the foreign one
  * ``phr.build``     — put the shuffled words of the sentence in order
  * ``phr.cloze``     — choose the missing word of the sentence
  * ``phr.dictation`` — hear the sentence and type it
  * ``phr.write``     — translate the Arabic sentence by typing it

Distractors are other real sentences of similar length from the same
lesson, so a wrong option is never nonsense, and cloze lures are the
lesson's other new words.
"""

from __future__ import annotations

import random
import re
from typing import Dict, List

from ..engine.models import Question, QuestionType
from . import Deduper, register, signature_qid

_TOK = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.U)


def plain(text: str) -> str:
    """Accent-free spelling (á→a, ñ→n, ş→s, ß→ss, ı→i) so a learner on an
    Arabic keyboard layout can still answer; the explanation shows the
    accented form."""
    import unicodedata
    t = text.replace("ß", "ss").replace("ı", "i").replace("İ", "I")
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def _pairs(params) -> List[Dict]:
    return [s for s in params.get("sentences", []) if s.get("t") and s.get("ar")]


def _near(rng: random.Random, pool: List[str], correct: str, n: int = 3) -> List[str]:
    """``n`` distractors of similar length to ``correct`` (with some variety)."""
    cands = [p for p in dict.fromkeys(pool) if p and p != correct]
    rng.shuffle(cands)
    cands.sort(key=lambda p: abs(len(p) - len(correct)))
    head = cands[: n * 3]
    rng.shuffle(head)
    return head[:n]


def _topic(params, kind: str) -> str:
    return f"{params.get('lang', 'lang')}:{kind}"


def _lang_name(params) -> str:
    return params.get("lang_name", "الأجنبية")


def _loop(count, rng, items, key, make):
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 40 and items:
        guard += 1
        s = rng.choice(items)
        sig = key(s)
        if not dd.fresh(sig):
            continue
        dd.add(sig)
        q = make(s)
        if q is not None:
            out.append(q)
    return out


@register("phr.translate")
def gen_translate(count: int, rng: random.Random, **params) -> List[Question]:
    items = _pairs(params)
    if len(items) < 2:
        return []
    pool = [s["ar"] for s in items]

    def make(s):
        opts = _near(rng, pool, s["ar"]) + [s["ar"]]
        opts = list(dict.fromkeys(opts))
        if len(opts) < 2:
            return None
        rng.shuffle(opts)
        q = Question(qtype=QuestionType.MCQ,
                     prompt=f"ما معنى: {s['t']}؟",
                     speak=s["t"] if params.get("listen") else "",
                     correct=opts.index(s["ar"]), options=opts,
                     explanation=f"{s['t']} = {s['ar']}.",
                     topic=_topic(params, "sentence"), difficulty=int(params.get("difficulty", 1)))
        q.qid = signature_qid("phr.translate", s["t"])
        return q
    return _loop(count, rng, items, lambda s: s["t"], make)


@register("phr.reverse")
def gen_reverse(count: int, rng: random.Random, **params) -> List[Question]:
    items = _pairs(params)
    if len(items) < 2:
        return []
    pool = [s["t"] for s in items]

    def make(s):
        opts = list(dict.fromkeys(_near(rng, pool, s["t"]) + [s["t"]]))
        if len(opts) < 2:
            return None
        rng.shuffle(opts)
        q = Question(qtype=QuestionType.MCQ,
                     prompt=f"كيف تقول باللغة {_lang_name(params)}: {s['ar']}؟",
                     correct=opts.index(s["t"]), options=opts,
                     explanation=f"{s['ar']} = {s['t']}.",
                     topic=_topic(params, "sentence"), difficulty=int(params.get("difficulty", 1)) + 1)
        q.qid = signature_qid("phr.reverse", s["t"])
        return q
    return _loop(count, rng, items, lambda s: s["t"], make)


def _tokens(text: str) -> List[str]:
    return text.strip().rstrip(".!?؟…").replace("¿", "").replace("¡", "").split()


@register("phr.build")
def gen_build(count: int, rng: random.Random, **params) -> List[Question]:
    items = [s for s in _pairs(params) if 3 <= len(_tokens(s["t"])) <= 9
             and len(set(_tokens(s["t"]))) == len(_tokens(s["t"]))]
    if not items:
        return []

    def make(s):
        tokens = _tokens(s["t"])
        shuffled = list(tokens)
        for _ in range(6):
            rng.shuffle(shuffled)
            if shuffled != tokens:
                break
        q = Question(qtype=QuestionType.ORDERING,
                     prompt=f"رتّب الكلمات لتكوين الجملة التي معناها: {s['ar']}",
                     correct=tokens, options=shuffled,
                     explanation=f"الترتيب الصحيح: {' '.join(tokens)}.",
                     topic=_topic(params, "word_order"), difficulty=int(params.get("difficulty", 1)) + 1)
        q.qid = signature_qid("phr.build", s["t"])
        return q
    return _loop(count, rng, items, lambda s: s["t"], make)


@register("phr.cloze")
def gen_cloze(count: int, rng: random.Random, **params) -> List[Question]:
    items = _pairs(params)
    focus = [w for w in params.get("focus", []) if w]
    if not items:
        return []
    lexicon = list(dict.fromkeys(
        focus + [t for s in items for t in _TOK.findall(s["t"])]))
    focus_low = {w.lower() for w in focus}

    def make(s):
        toks = _TOK.findall(s["t"])
        cands = [t for t in toks if t.lower() in focus_low] or [t for t in toks if len(t) > 2]
        if not cands:
            return None
        target = rng.choice(cands)
        m = re.search(r"(?<![^\W\d_])" + re.escape(target) + r"(?![^\W\d_])", s["t"])
        if not m:
            return None
        blanked = s["t"][:m.start()] + "-----" + s["t"][m.end():]
        lures = [w for w in lexicon if w.lower() != target.lower()]
        rng.shuffle(lures)
        lures.sort(key=lambda w: (w.lower() not in focus_low, abs(len(w) - len(target))))
        lures = lures[:6]
        rng.shuffle(lures)
        opts = list(dict.fromkeys(lures[:3] + [target]))
        if len(opts) < 2:
            return None
        rng.shuffle(opts)
        q = Question(qtype=QuestionType.MCQ,
                     prompt=f"أكمل الفراغ: {blanked} (المعنى: {s['ar']})",
                     correct=opts.index(target), options=opts,
                     explanation=f"الجملة كاملة: {s['t']}.",
                     topic=_topic(params, "cloze"), difficulty=int(params.get("difficulty", 1)) + 1)
        q.qid = signature_qid("phr.cloze", s["t"] + "|" + target)
        return q
    return _loop(count, rng, items, lambda s: s["t"], make)


@register("phr.dictation")
def gen_dictation(count: int, rng: random.Random, **params) -> List[Question]:
    items = [s for s in _pairs(params) if len(s["t"]) <= 80]

    def make(s):
        q = Question(qtype=QuestionType.TYPING,
                     prompt="استمع إلى الجملة (Ctrl+R لإعادتها) واكتبها كما سمعتها:",
                     speak=s["t"], correct=s["t"], accepted=[plain(s["t"])],
                     explanation=f"الجملة: {s['t']} ({s['ar']}).",
                     topic=_topic(params, "dictation"), difficulty=int(params.get("difficulty", 1)) + 1)
        q.qid = signature_qid("phr.dictation", s["t"])
        return q
    return _loop(count, rng, items, lambda s: s["t"], make)


@register("phr.write")
def gen_write(count: int, rng: random.Random, **params) -> List[Question]:
    items = [s for s in _pairs(params) if len(_tokens(s["t"])) <= 7]

    def make(s):
        q = Question(qtype=QuestionType.TYPING,
                     prompt=f"اكتب باللغة {_lang_name(params)}: {s['ar']}",
                     correct=s["t"], accepted=list(s.get("alt", [])) + [plain(s["t"])],
                     explanation=f"الإجابة: {s['t']}.",
                     hint=f"تبدأ الجملة بـ {_tokens(s['t'])[0]}.",
                     topic=_topic(params, "writing"), difficulty=int(params.get("difficulty", 1)) + 2)
        q.qid = signature_qid("phr.write", s["t"])
        return q
    return _loop(count, rng, items, lambda s: s["t"], make)
