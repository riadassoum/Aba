# -*- coding: utf-8 -*-
"""
abaAcademy.generators.language
==============================

Foreign-language generators (English, French, Spanish, …) driven by a bilingual
word bank. Each word record carries the foreign word, its Arabic meaning, a
topic, a difficulty, and — crucially — a real example sentence with its Arabic
translation. That lets us generate several genuinely useful question shapes from
curated vocabulary rather than filler:

  * ``lang.translate``  — foreign word -> Arabic meaning (MCQ, same-topic distractors)
  * ``lang.word``       -> Arabic meaning -> foreign word (typing)
  * ``lang.listen``     -> "how do you say X" -> pick the foreign word (MCQ)
  * ``lang.sentence``   -> translate a real example sentence (MCQ over real translations)

These are content-neutral across languages: the same generators serve every
language pack; only the ``words`` data table (in each pack's data/ folder)
differs. Distractors are always drawn from the same topic so wrong answers are
plausible, never nonsense.
"""

from __future__ import annotations

import json
import os
import random
from typing import Dict, List

from ..engine.models import Question, QuestionType
from . import Deduper, register, shuffled_options, signature_qid, word_similarity


_LANG_BANK: Dict[str, Dict[str, List[str]]] | None = None


def _lang_bank(lang: str, key: str) -> List[str]:
    """A shared pool of real words/meanings for a language, harvested from every
    language pack, used to widen distractor pools so even a short lesson can
    offer many convincing look/sound-alike lures rather than only the handful of
    words in that lesson. ``key`` is "words" or "meanings"."""
    global _LANG_BANK
    if _LANG_BANK is None:
        _LANG_BANK = {}
        try:
            here = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(here, "..", "resources", "banks", "lang_bank.json")
            with open(path, encoding="utf-8") as f:
                _LANG_BANK = json.load(f)
        except Exception:
            _LANG_BANK = {}
    return (_LANG_BANK.get(lang, {}) or {}).get(key, [])


def _pool(params) -> List[Dict]:
    return [w for w in params.get("words", []) if w.get("word") and w.get("meaning")]


def _same_topic(words, w, key):
    vals = [x.get(key) for x in words
            if x.get("topic") == w.get("topic") and x is not w and x.get(key)]
    return list(dict.fromkeys(vals))


@register("lang.translate")
def gen_translate(count: int, rng: random.Random, **params) -> List[Question]:
    words = _pool(params)
    if not words:
        return []
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 40:
        guard += 1
        w = rng.choice(words)
        if not dd.fresh(w["word"]):
            continue
        dd.add(w["word"])
        correct = w["meaning"]
        pool = _same_topic(words, w, "meaning") or [x["meaning"] for x in words if x is not w]
        pool = list(dict.fromkeys(pool + _lang_bank(params.get("lang", ""), "meanings")))
        options, idx = shuffled_options(rng, correct, pool, sim=word_similarity)
        if len(options) < 2:
            continue
        q = Question(
            qtype=QuestionType.MCQ,
            prompt=f"ما معنى كلمة {w['word']}؟",
            correct=idx, options=options,
            explanation=f"{w['word']} تعني {correct}.",
            topic=f"{params.get('lang','lang')}:{w.get('topic','')}",
            difficulty=int(w.get("difficulty", 1)))
        q.qid = signature_qid("lang.translate", w["word"])
        out.append(q)
    return out


@register("lang.word")
def gen_word(count: int, rng: random.Random, **params) -> List[Question]:
    words = _pool(params)
    if not words:
        return []
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 40:
        guard += 1
        w = rng.choice(words)
        if not dd.fresh(w["word"]):
            continue
        dd.add(w["word"])
        q = Question(
            qtype=QuestionType.TYPING,
            prompt=f"اكتب بالكلمة الأجنبية ما معناه {w['meaning']}:",
            correct=w["word"], accepted=list(w.get("accepted", [])),
            explanation=f"الإجابة: {w['word']}.",
            topic=f"{params.get('lang','lang')}:{w.get('topic','')}",
            difficulty=int(w.get("difficulty", 1)))
        q.qid = signature_qid("lang.word", w["word"])
        out.append(q)
    return out


@register("lang.listen")
def gen_listen(count: int, rng: random.Random, **params) -> List[Question]:
    words = _pool(params)
    if not words:
        return []
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 40:
        guard += 1
        w = rng.choice(words)
        if not dd.fresh(w["word"]):
            continue
        dd.add(w["word"])
        correct = w["word"]
        # distractors are other foreign words; rank by look/sound similarity so
        # the lures are words easily confused with the answer (desert/dessert…)
        pool = _same_topic(words, w, "word") or [x["word"] for x in words if x is not w]
        pool = list(dict.fromkeys(pool + _lang_bank(params.get("lang", ""), "words")))
        options, idx = shuffled_options(rng, correct, pool, sim=word_similarity)
        if len(options) < 2:
            continue
        q = Question(
            qtype=QuestionType.MCQ,
            prompt=f"كيف تقول {w['meaning']} بالكلمة الأجنبية؟",
            correct=idx, options=options,
            explanation=f"{w['meaning']} = {correct}.",
            topic=f"{params.get('lang','lang')}:{w.get('topic','')}",
            difficulty=int(w.get("difficulty", 1)))
        q.qid = signature_qid("lang.listen", w["word"])
        out.append(q)
    return out


@register("lang.sentence")
def gen_sentence(count: int, rng: random.Random, **params) -> List[Question]:
    """Translate a real example sentence; distractors are other real translations."""
    words = [w for w in _pool(params) if w.get("example") and w.get("translation")]
    if len(words) < 2:
        return []
    all_translations = list(dict.fromkeys(w["translation"] for w in words))
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 40:
        guard += 1
        w = rng.choice(words)
        if not dd.fresh(w["example"]):
            continue
        dd.add(w["example"])
        correct = w["translation"]
        pool = [t for t in all_translations if t != correct]
        rng.shuffle(pool)
        options = pool[:3] + [correct]
        options = list(dict.fromkeys(options))
        if len(options) < 2:
            continue
        rng.shuffle(options)
        q = Question(
            qtype=QuestionType.MCQ,
            prompt=f"ما ترجمة الجملة: {w['example']}؟",
            correct=options.index(correct), options=options,
            explanation=f"الترجمة: {correct}.",
            topic=f"{params.get('lang','lang')}:{w.get('topic','')}",
            difficulty=int(w.get("difficulty", 1)) + 1)
        q.qid = signature_qid("lang.sentence", w["example"])
        out.append(q)
    return out


@register("lang.truefalse")
def gen_truefalse(count: int, rng: random.Random, **params) -> List[Question]:
    """"Word X means Y" — true or false? Half the time Y is a wrong same-topic meaning."""
    words = _pool(params)
    if len(words) < 2:
        return []
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 40:
        guard += 1
        w = rng.choice(words)
        if not dd.fresh(w["word"] + str(len(out))):
            continue
        dd.add(w["word"] + str(len(out)))
        make_true = rng.random() < 0.5
        if make_true:
            shown_meaning, is_true = w["meaning"], True
        else:
            others = _same_topic(words, w, "meaning") or [x["meaning"] for x in words if x is not w]
            others = [m for m in others if m != w["meaning"]]
            if not others:
                shown_meaning, is_true = w["meaning"], True
            else:
                shown_meaning, is_true = rng.choice(others), False
        q = Question(
            qtype=QuestionType.TRUE_FALSE,
            prompt=f"هل معنى {w['word']} هو {shown_meaning}؟",
            correct=is_true,
            explanation=(f"صحيح، {w['word']} تعني {w['meaning']}." if is_true
                         else f"خطأ، {w['word']} تعني {w['meaning']} وليس {shown_meaning}."),
            topic=f"{params.get('lang','lang')}:{w.get('topic','')}",
            difficulty=int(w.get("difficulty", 1)))
        q.qid = signature_qid("lang.truefalse", w["word"] + shown_meaning)
        out.append(q)
    return out


@register("lang.fillblank")
def gen_fillblank(count: int, rng: random.Random, **params) -> List[Question]:
    """Blank out the target word inside its real example sentence; learner picks it."""
    words = [w for w in _pool(params) if w.get("example")
             and w["word"].lower() in w["example"].lower()]
    if len(words) < 2:
        return []
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 40:
        guard += 1
        w = rng.choice(words)
        if not dd.fresh(w["example"]):
            continue
        dd.add(w["example"])
        # case-insensitive blank of the first occurrence
        low = w["example"].lower()
        idx = low.find(w["word"].lower())
        blanked = w["example"][:idx] + "-----" + w["example"][idx + len(w["word"]):]
        correct = w["word"]
        pool = _same_topic(words, w, "word") or [x["word"] for x in words if x is not w]
        pool = list(dict.fromkeys(pool + _lang_bank(params.get("lang", ""), "words")))
        options, oidx = shuffled_options(rng, correct, pool, sim=word_similarity)
        if len(options) < 2:
            continue
        q = Question(
            qtype=QuestionType.MCQ,
            prompt=f"أكمل الفراغ: {blanked} ({w['translation']})",
            correct=oidx, options=options,
            explanation=f"الكلمة الناقصة: {correct}.",
            topic=f"{params.get('lang','lang')}:{w.get('topic','')}",
            difficulty=int(w.get("difficulty", 1)) + 1)
        q.qid = signature_qid("lang.fillblank", w["example"])
        out.append(q)
    return out


@register("lang.confusable")
def gen_confusable(count: int, rng: random.Random, **params) -> List[Question]:
    """A targeted drill on look/sound-alike words. For a word, it finds the most
    confusable other word in the pool (e.g. desert/dessert, poisson/poison) and
    asks the learner to pick the one that matches the given meaning — turning the
    exact confusion the trick-answers create into focused practice. Only fires
    when a genuinely similar partner exists, so it never manufactures a fake
    pair."""
    words = _pool(params)
    if len(words) < 2:
        return []
    bank_words = _lang_bank(params.get("lang", ""), "words")
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 40:
        guard += 1
        w = rng.choice(words)
        if not dd.fresh(w["word"]):
            continue
        correct = w["word"]
        # the single most confusable other word in the pool + bank
        candidates = [x["word"] for x in words if x is not w] + list(bank_words)
        candidates = [c for c in dict.fromkeys(candidates) if c and c != correct]
        if not candidates:
            continue
        partner = max(candidates, key=lambda c: word_similarity(correct, c))
        if word_similarity(correct, partner) < 0.55:
            continue   # nothing genuinely confusable — skip
        dd.add(w["word"])
        options = [correct, partner]
        rng.shuffle(options)
        q = Question(
            qtype=QuestionType.MCQ,
            prompt=f"أيّ الكلمتين تعني {w['meaning']}؟ انتبه فهما متشابهتان.",
            correct=options.index(correct), options=options,
            explanation=f"{correct} تعني {w['meaning']}؛ لا تخلطها بـ {partner}.",
            hint=f"الكلمتان متشابهتان في الشكل؛ ركّز على الفرق بينهما.",
            topic=f"{params.get('lang','lang')}:confusable",
            difficulty=int(w.get("difficulty", 1)) + 1)
        q.qid = signature_qid("lang.confusable", w["word"])
        out.append(q)
    return out


@register("lang.oddword")
def gen_oddword(count: int, rng: random.Random, **params) -> List[Question]:
    """Pick the word that does NOT belong to the same topic as the others."""
    words = _pool(params)
    topics = {}
    for w in words:
        topics.setdefault(w.get("topic", ""), []).append(w)
    big = {t: ws for t, ws in topics.items() if len(ws) >= 3}
    if len(big) < 2:
        return []
    out, dd, guard = [], Deduper(), 0
    topic_keys = list(big.keys())
    while len(out) < count and guard < count * 40:
        guard += 1
        t = rng.choice(topic_keys)
        same = rng.sample(big[t], 3)
        other_topics = [k for k in topic_keys if k != t]
        odd_topic = rng.choice(other_topics)
        odd = rng.choice(big[odd_topic])
        sig = "|".join(sorted(w["word"] for w in same) + [odd["word"]])
        if not dd.fresh(sig):
            continue
        dd.add(sig)
        options = [w["word"] for w in same] + [odd["word"]]
        rng.shuffle(options)
        q = Question(
            qtype=QuestionType.MCQ,
            prompt="أي كلمة لا تنتمي إلى المجموعة (من حيث الموضوع)؟",
            correct=options.index(odd["word"]), options=options,
            explanation=f"{odd['word']} تخص موضوع {odd_topic} بينما البقية من {t}.",
            topic=f"{params.get('lang','lang')}:{t}",
            difficulty=2)
        q.qid = signature_qid("lang.oddword", sig)
        out.append(q)
    return out


@register("lang.build")
def gen_build(count: int, rng: random.Random, **params) -> List[Question]:
    """Reorder shuffled words of a real example sentence into the correct order."""
    words = [w for w in _pool(params) if w.get("example")
             and 3 <= len(w["example"].split()) <= 7]
    if not words:
        return []
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 40:
        guard += 1
        w = rng.choice(words)
        if not dd.fresh(w["example"]):
            continue
        dd.add(w["example"])
        # strip trailing punctuation for token list
        tokens = w["example"].rstrip(".!?").split()
        correct_order = list(tokens)
        shuffled = list(tokens)
        # ensure it's actually shuffled
        for _ in range(5):
            rng.shuffle(shuffled)
            if shuffled != correct_order:
                break
        q = Question(
            qtype=QuestionType.ORDERING,
            prompt=f"رتّب الكلمات لتكوين جملة صحيحة (المعنى: {w['translation']}):",
            correct=correct_order, options=shuffled,
            explanation=f"الجملة الصحيحة: {' '.join(correct_order)}.",
            topic=f"{params.get('lang','lang')}:{w.get('topic','')}",
            difficulty=int(w.get("difficulty", 1)) + 2)
        q.qid = signature_qid("lang.build", w["example"])
        out.append(q)
    return out


@register("lang.dictation")
def gen_dictation(count: int, rng: random.Random, **params) -> List[Question]:
    """Real dictation: the runner VOICES a sentence (via q.speak) and the learner
    types what they hear. The visible prompt is a neutral instruction, so it's
    listening+spelling practice, not copying. Sentences come from the pack's
    example sentences (or an explicit ``sentences`` list of {text, translation})."""
    sentences = list(params.get("sentences", []))
    if not sentences:
        # fall back to example sentences in the word bank
        for w in _pool(params):
            if w.get("example"):
                sentences.append({"text": w["example"], "translation": w.get("translation", "")})
    sentences = [s for s in sentences if s.get("text")]
    if not sentences:
        return []
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 40:
        guard += 1
        s = rng.choice(sentences)
        if not dd.fresh(s["text"]):
            continue
        dd.add(s["text"])
        tr = s.get("translation", "")
        q = Question(
            qtype=QuestionType.TYPING,
            prompt="استمع إلى الجملة (اضغط Ctrl+R لإعادة سماعها) ثم اكتبها كما سمعتها:",
            speak=s["text"],
            correct=s["text"],
            explanation=(f"الجملة الصحيحة: {s['text']}." + (f" ({tr})" if tr else "")),
            topic=f"{params.get('lang','lang')}:dictation",
            difficulty=int(s.get("difficulty", 2)))
        q.qid = signature_qid("lang.dictation", s["text"])
        out.append(q)
    return out


@register("lang.conjugate")
def gen_conjugate(count: int, rng: random.Random, **params) -> List[Question]:
    """Verb-conjugation drill from a table of forms. ``verbs`` is a list of
    {infinitive, meaning, tense, forms:{pronoun: form}}. Half are typed (produce
    the form), half MCQ (choose the form) with other-pronoun forms as
    distractors -- i.e. plausible agreement mistakes."""
    verbs = list(params.get("verbs", []))
    verbs = [v for v in verbs if v.get("forms")]
    if not verbs:
        return []
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 60:
        guard += 1
        v = rng.choice(verbs)
        forms = v["forms"]
        pronoun = rng.choice(list(forms.keys()))
        correct = forms[pronoun]
        sig = f"{v.get('infinitive','')}|{v.get('tense','')}|{pronoun}"
        if not dd.fresh(sig):
            continue
        dd.add(sig)
        tense = v.get("tense", "")
        meaning = v.get("meaning", "")
        stem = f"صرّف الفعل {v.get('infinitive','')}" + (f" ({meaning})" if meaning else "")
        stem += (f" في {tense}" if tense else "") + f" مع الضمير {pronoun}:"
        if rng.random() < 0.5:
            q = Question(
                qtype=QuestionType.TYPING, prompt=stem, correct=correct,
                accepted=list(v.get("accepted", {}).get(pronoun, [])),
                explanation=f"{pronoun} → {correct}.",
                topic=f"{params.get('lang','lang')}:conjugation:{v.get('tense','')}",
                difficulty=int(v.get("difficulty", 2)))
        else:
            wrongs = [f for p, f in forms.items() if f != correct]
            wrongs = list(dict.fromkeys(wrongs))
            rng.shuffle(wrongs)
            options = wrongs[:3] + [correct]
            options = list(dict.fromkeys(options))
            if len(options) < 2:
                continue
            rng.shuffle(options)
            q = Question(
                qtype=QuestionType.MCQ, prompt=stem, correct=options.index(correct),
                options=options, explanation=f"{pronoun} → {correct}.",
                topic=f"{params.get('lang','lang')}:conjugation:{v.get('tense','')}",
                difficulty=int(v.get("difficulty", 2)))
        q.qid = signature_qid("lang.conjugate", sig)
        out.append(q)
    return out


@register("lang.matching")
def gen_matching(count: int, rng: random.Random, **params) -> List[Question]:
    """Match-the-pairs: pair each foreign word with its Arabic meaning. Each
    question pairs a small set (default 4) of words drawn from the same pool, so
    the choices stay plausible. Grading compares the whole {word: meaning} map.
    """
    words = _pool(params)
    words = [w for w in words if w.get("word") and w.get("meaning")]
    if len(words) < 3:
        return []
    per = max(3, min(5, int(params.get("pairs", 4))))
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 40:
        guard += 1
        if len(words) < per:
            break
        chosen = rng.sample(words, per)
        correct = {w["word"]: w["meaning"] for w in chosen}
        sig = "|".join(sorted(correct.keys()))
        if not dd.fresh(sig):
            continue
        dd.add(sig)
        q = Question(
            qtype=QuestionType.MATCHING,
            prompt="طابق كل كلمة بمعناها الصحيح:",
            correct=correct,
            options=list(correct.values()),
            explanation="المطابقات الصحيحة: " + "، ".join(
                f"{k} = {v}" for k, v in correct.items()) + ".",
            topic=f"{params.get('lang','lang')}:matching",
            difficulty=2)
        q.qid = signature_qid("lang.matching", sig)
        out.append(q)
    return out
