# -*- coding: utf-8 -*-
"""
abaAcademy.generators.vocabulary
================================

Vocabulary generators that read the structured word database (see
``database.vocab_db``). A single word record carries part of speech, gender,
plural, root, difficulty, topic, synonyms, antonyms, typical mistakes, and
accepted spellings — rich enough to drive several question shapes with
*intelligent distractors* (wrong answers drawn from the same topic/POS, or from
the word's known "typical mistakes", never random nonsense).

Generators:
  * ``vocab.meaning``  — word -> meaning (MCQ), distractors same-topic
  * ``vocab.reverse``  — meaning -> word (typing, accepts spelling variants)
  * ``vocab.synonym``  — pick the synonym (MCQ)
  * ``vocab.antonym``  — pick the antonym (MCQ)
  * ``vocab.spelling`` — pick correct spelling among typical misspellings

All of them take ``params['words']`` — a list of word-record dicts — so the
same generators serve Arabic, English, French, or any future language pack.
"""

from __future__ import annotations

import random
from typing import Dict, List

from ..engine.models import Question, QuestionType
from . import Deduper, register, shuffled_options, signature_qid, word_similarity


def _same_topic_pool(words: List[Dict], word: Dict, key: str) -> List[str]:
    topic = word.get("topic")
    vals = [w.get(key) for w in words
            if w.get("topic") == topic and w.get(key) and w is not word]
    vals = [v for v in vals if v]
    return list(dict.fromkeys(vals))


@register("vocab.meaning")
def gen_meaning(count: int, rng: random.Random, **params) -> List[Question]:
    words: List[Dict] = [w for w in params.get("words", []) if w.get("meaning")]
    if not words:
        return []
    out: List[Question] = []
    dd = Deduper()
    guard = 0
    while len(out) < count and guard < count * 40:
        guard += 1
        w = rng.choice(words)
        if not dd.fresh(w["word"]):
            continue
        dd.add(w["word"])
        correct = w["meaning"]
        pool = _same_topic_pool(words, w, "meaning") or [x["meaning"] for x in words if x is not w]
        options, idx = shuffled_options(rng, correct, pool)
        if len(options) < 2:
            continue
        q = Question(
            qtype=QuestionType.MCQ,
            prompt=f"ما معنى «{w['word']}»؟",
            correct=idx,
            options=options,
            explanation=f"«{w['word']}» تعني «{correct}».",
            topic=f"vocab:{w.get('topic','')}",
            difficulty=int(w.get("difficulty", 1)),
        )
        q.qid = signature_qid("vocab.meaning", w["word"])
        out.append(q)
    return out


@register("vocab.reverse")
def gen_reverse(count: int, rng: random.Random, **params) -> List[Question]:
    words: List[Dict] = [w for w in params.get("words", []) if w.get("meaning")]
    if not words:
        return []
    out: List[Question] = []
    dd = Deduper()
    guard = 0
    while len(out) < count and guard < count * 40:
        guard += 1
        w = rng.choice(words)
        if not dd.fresh(w["word"]):
            continue
        dd.add(w["word"])
        q = Question(
            qtype=QuestionType.TYPING,
            prompt=f"اكتب الكلمة التي تعني «{w['meaning']}»:",
            correct=w["word"],
            accepted=list(w.get("accepted_spellings", [])),
            explanation=f"الإجابة: «{w['word']}».",
            topic=f"vocab:{w.get('topic','')}",
            difficulty=int(w.get("difficulty", 1)),
        )
        q.qid = signature_qid("vocab.reverse", w["word"])
        out.append(q)
    return out


def _relation_generator(rel_key: str, gen_id: str, prompt_tpl: str, explain_tpl: str):
    @register(gen_id)
    def _gen(count: int, rng: random.Random, **params) -> List[Question]:
        words: List[Dict] = [w for w in params.get("words", []) if w.get(rel_key)]
        if not words:
            return []
        out: List[Question] = []
        dd = Deduper()
        guard = 0
        while len(out) < count and guard < count * 40:
            guard += 1
            w = rng.choice(words)
            rels = w.get(rel_key) or []
            if not rels or not dd.fresh(w["word"]):
                continue
            dd.add(w["word"])
            correct = rng.choice(rels)
            # Distractors: same-topic words that are NOT a valid relation.
            pool = [x["word"] for x in words
                    if x.get("topic") == w.get("topic") and x is not w
                    and x["word"] not in rels and x["word"] != correct]
            pool = list(dict.fromkeys(pool))
            rng.shuffle(pool)
            options = pool[:3] + [correct]
            options = list(dict.fromkeys(options))
            if len(options) < 2:
                continue
            rng.shuffle(options)
            q = Question(
                qtype=QuestionType.MCQ,
                prompt=prompt_tpl.format(word=w["word"]),
                correct=options.index(correct),
                options=options,
                explanation=explain_tpl.format(word=w["word"], answer=correct),
                topic=f"vocab:{w.get('topic','')}",
                difficulty=int(w.get("difficulty", 1)) + 1,
            )
            q.qid = signature_qid(gen_id, w["word"] + correct)
            out.append(q)
        return out
    return _gen


gen_synonym = _relation_generator(
    "synonyms", "vocab.synonym",
    "اختر مرادفاً لكلمة «{word}»:", "من مرادفات «{word}»: «{answer}».")

gen_antonym = _relation_generator(
    "antonyms", "vocab.antonym",
    "اختر ضد كلمة «{word}»:", "ضد «{word}» هو «{answer}».")


@register("vocab.spelling")
def gen_spelling(count: int, rng: random.Random, **params) -> List[Question]:
    """Choose the correct spelling among the word's known typical mistakes."""
    words: List[Dict] = [w for w in params.get("words", []) if w.get("typical_mistakes")]
    if not words:
        return []
    out: List[Question] = []
    dd = Deduper()
    guard = 0
    while len(out) < count and guard < count * 40:
        guard += 1
        w = rng.choice(words)
        mistakes = w.get("typical_mistakes") or []
        if not mistakes or not dd.fresh(w["word"]):
            continue
        dd.add(w["word"])
        correct = w["word"]
        wrongs = list(dict.fromkeys(mistakes))
        rng.shuffle(wrongs)
        options = wrongs[:3] + [correct]
        options = list(dict.fromkeys(options))
        rng.shuffle(options)
        q = Question(
            qtype=QuestionType.MCQ,
            prompt=f"اختر الكتابة الإملائية الصحيحة للكلمة التي تعني «{w.get('meaning','')}»:",
            correct=options.index(correct),
            options=options,
            explanation=f"الكتابة الصحيحة هي «{correct}».",
            topic=f"vocab:{w.get('topic','')}",
            difficulty=int(w.get("difficulty", 1)) + 1,
        )
        q.qid = signature_qid("vocab.spelling", w["word"])
        out.append(q)
    return out
