# -*- coding: utf-8 -*-
"""
abaAcademy.generators.generic
=============================

Content-neutral generators. These carry no built-in linguistic knowledge at
all; every fact they use comes from ``params`` supplied by the JSON block.
They exist so course authors can get procedural variety without shipping a
Python generator -- the engine stays language-agnostic and the *content* lives
in the course pack.

Unlimited supply
----------------
Each generator turns its data table into a set of question *builders* and then
hands them to :func:`~abaAcademy.generators.fill_to_count`, which draws from
them until the requested count is met, reshuffling when the pool runs dry.
Previously a block asking for eight questions from a two-row table produced
exactly two and then stopped, which quietly capped every quiz and made
"endless practice" end almost immediately.

Crucially, recycling is not repetition: a single data row can be asked in
several genuinely different ways -- pick the answer, judge a claim true or
false, type the answer from memory -- and each shape re-randomises its option
set on every draw. One row therefore supports a long drill on its own, and a
handful of rows support an indefinite one.

Generators:
  * ``generic.frame``     — {prompt, correct, distractors} → MCQ / true-false / typing
  * ``generic.truefalse`` — {text, is_true, explain} → true-false
  * ``generic.pairs``     — {a, b} → both directions, MCQ / typing / true-false
  * ``generic.cloze``     — {text, answer, distractors} → fill the blank
  * ``generic.ordering``  — {items, prompt} → arrange into the correct order
"""

from __future__ import annotations

import random
from typing import Dict, List

from ..engine.models import Question, QuestionType
from . import fill_to_count, register, shuffled_options, signature_qid


def _as_list(params, *names) -> List[Dict]:
    """Read a table under any of several accepted parameter names.

    Course JSON reaches generators through several routes (inline ``params``,
    a named ``data`` file, a bare list handed under a guessed key), so being
    forgiving about the key name avoids silent empty lessons.
    """
    for name in names:
        value = params.get(name)
        if isinstance(value, list) and value:
            return [v for v in value if isinstance(v, dict)]
    return []


# ---------------------------------------------------------------------------
# generic.frame
# ---------------------------------------------------------------------------

@register("generic.frame")
def gen_frame(count: int, rng: random.Random, **params) -> List[Question]:
    frames = _as_list(params, "frames")
    default_topic = params.get("topic", "")
    if not frames:
        return []

    # Every other frame's answer is a plausible wrong answer for this one, and
    # a much better distractor than anything random.
    all_answers = list(dict.fromkeys(
        str(f.get("correct", "")) for f in frames if f.get("correct")))

    builders = []
    for frame in frames:
        prompt = str(frame.get("prompt", "")).strip()
        correct = str(frame.get("correct", "")).strip()
        if not prompt or not correct:
            continue
        topic = frame.get("topic", default_topic)
        explain = frame.get("explain", "")
        difficulty = int(frame.get("difficulty", params.get("difficulty", 1)))
        own = [str(d) for d in frame.get("distractors", [])]
        pool = own + [a for a in all_answers if a != correct]
        qid = signature_qid("generic.frame", prompt)

        def make_mcq(prompt=prompt, correct=correct, pool=pool, topic=topic,
                     explain=explain, difficulty=difficulty, qid=qid):
            options, index = shuffled_options(rng, correct, pool)
            if len(options) < 2:
                return None
            q = Question(qtype=QuestionType.MCQ, prompt=prompt, correct=index,
                         options=options, explanation=explain, topic=topic,
                         difficulty=difficulty)
            q.qid = qid
            return q

        def make_tf(prompt=prompt, correct=correct, pool=pool, topic=topic,
                    explain=explain, difficulty=difficulty, qid=qid):
            wrongs = [d for d in dict.fromkeys(pool) if d and d != correct]
            claim_true = not wrongs or rng.random() < 0.5
            shown = correct if claim_true else rng.choice(wrongs)
            note = explain if claim_true else f"الإجابة الصحيحة هي {correct}."
            q = Question(
                qtype=QuestionType.TRUE_FALSE,
                prompt=f"{prompt} — هل الإجابة {shown}؟",
                correct=claim_true, explanation=note, topic=topic,
                difficulty=difficulty)
            q.qid = qid
            return q

        def make_typing(prompt=prompt, correct=correct, topic=topic,
                        explain=explain, difficulty=difficulty, qid=qid,
                        accepted=list(frame.get("accepted", []))):
            q = Question(
                qtype=QuestionType.TYPING,
                prompt=f"{prompt} (اكتب الإجابة)",
                correct=correct, accepted=accepted,
                explanation=explain or f"الإجابة: {correct}.",
                topic=topic, difficulty=difficulty + 1)
            q.qid = qid
            return q

        # Weighted towards recognition, which is the gentler shape, but with
        # enough recall so the learner cannot coast on multiple choice alone.
        builders.extend([make_mcq, make_mcq, make_tf, make_typing])

    return [q for q in fill_to_count(builders, count, rng) if q is not None]


# ---------------------------------------------------------------------------
# generic.truefalse
# ---------------------------------------------------------------------------

@register("generic.truefalse")
def gen_truefalse(count: int, rng: random.Random, **params) -> List[Question]:
    statements = _as_list(params, "statements")
    default_topic = params.get("topic", "")
    if not statements:
        return []
    builders = []
    for st in statements:
        text = str(st.get("text", "")).strip()
        if not text:
            continue

        def make(st=st, text=text):
            q = Question(
                qtype=QuestionType.TRUE_FALSE, prompt=text,
                correct=bool(st.get("is_true", True)),
                explanation=st.get("explain", ""),
                topic=st.get("topic", default_topic),
                difficulty=int(st.get("difficulty", 1)))
            q.qid = signature_qid("generic.truefalse", text)
            return q

        builders.append(make)
    return fill_to_count(builders, count, rng)


# ---------------------------------------------------------------------------
# generic.pairs
# ---------------------------------------------------------------------------

@register("generic.pairs")
def gen_pairs(count: int, rng: random.Random, **params) -> List[Question]:
    """Term/definition drilling in both directions.

    ``params['pairs']`` is a list of ``{"a", "b"}`` (optionally ``topic``,
    ``explain``, ``difficulty``). ``a`` is the term, ``b`` its meaning,
    definition, value or counterpart. From each pair we can ask a→b and b→a, as
    multiple choice, as recall typing, or as a true/false claim -- so a table of
    twenty pairs already supports a very long drill, and a table of three
    supports an unlimited one.
    """
    pairs = _as_list(params, "pairs", "items")
    default_topic = params.get("topic", "")
    label_a = params.get("label_a", "")
    label_b = params.get("label_b", "")
    if not pairs:
        return []

    all_a = list(dict.fromkeys(str(p.get("a", "")) for p in pairs if p.get("a")))
    all_b = list(dict.fromkeys(str(p.get("b", "")) for p in pairs if p.get("b")))

    builders = []
    for pair in pairs:
        a = str(pair.get("a", "")).strip()
        b = str(pair.get("b", "")).strip()
        if not a or not b:
            continue
        topic = pair.get("topic", default_topic)
        difficulty = int(pair.get("difficulty", params.get("difficulty", 1)))
        explain = pair.get("explain", "") or f"{a} ← → {b}."
        qid = signature_qid("generic.pairs", a + "|" + b)
        ask_a = f"ما {label_b} الموافق لـ {a}؟" if label_b else f"ما الموافق لـ {a}؟"
        ask_b = f"ما {label_a} الموافق لـ {b}؟" if label_a else f"ما الموافق لـ {b}؟"

        def forward(a=a, b=b, topic=topic, explain=explain, difficulty=difficulty,
                    qid=qid, ask_a=ask_a):
            options, index = shuffled_options(rng, b, [x for x in all_b if x != b])
            if len(options) < 2:
                return None
            q = Question(qtype=QuestionType.MCQ, prompt=ask_a, correct=index,
                         options=options, explanation=explain, topic=topic,
                         difficulty=difficulty)
            q.qid = qid
            return q

        def backward(a=a, b=b, topic=topic, explain=explain, difficulty=difficulty,
                     qid=qid, ask_b=ask_b):
            options, index = shuffled_options(rng, a, [x for x in all_a if x != a])
            if len(options) < 2:
                return None
            q = Question(qtype=QuestionType.MCQ, prompt=ask_b, correct=index,
                         options=options, explanation=explain, topic=topic,
                         difficulty=difficulty)
            q.qid = qid
            return q

        def recall(a=a, b=b, topic=topic, explain=explain, difficulty=difficulty,
                   qid=qid, ask_a=ask_a, accepted=list(pair.get("accepted", []))):
            q = Question(qtype=QuestionType.TYPING, prompt=ask_a + " (اكتب الإجابة)",
                         correct=b, accepted=accepted, explanation=explain,
                         topic=topic, difficulty=difficulty + 1)
            q.qid = qid
            return q

        def judge(a=a, b=b, topic=topic, difficulty=difficulty, qid=qid):
            others = [x for x in all_b if x != b]
            claim_true = not others or rng.random() < 0.5
            shown = b if claim_true else rng.choice(others)
            q = Question(
                qtype=QuestionType.TRUE_FALSE,
                prompt=f"هل {a} يوافق {shown}؟",
                correct=claim_true,
                explanation=(f"نعم، {a} يوافق {b}." if claim_true
                             else f"لا، {a} يوافق {b} وليس {shown}."),
                topic=topic, difficulty=difficulty)
            q.qid = qid
            return q

        builders.extend([forward, forward, backward, judge, recall])

    return [q for q in fill_to_count(builders, count, rng) if q is not None]


# ---------------------------------------------------------------------------
# generic.cloze
# ---------------------------------------------------------------------------

@register("generic.cloze")
def gen_cloze(count: int, rng: random.Random, **params) -> List[Question]:
    """Fill-in-the-blank over authored sentences.

    ``params['sentences']`` is a list of ``{"text", "answer"}`` where ``text``
    contains ``{}`` (or the literal word in ``answer``) marking the gap.
    Distractors default to the other rows' answers, so wrong options are always
    the kind of thing that *could* fill that gap.
    """
    rows = _as_list(params, "sentences", "cloze", "items")
    default_topic = params.get("topic", "")
    if not rows:
        return []
    all_answers = list(dict.fromkeys(
        str(r.get("answer", "")) for r in rows if r.get("answer")))

    builders = []
    for row in rows:
        text = str(row.get("text", "")).strip()
        answer = str(row.get("answer", "")).strip()
        if not text or not answer:
            continue
        if "{}" in text:
            blanked = text.replace("{}", "ـــــ")
        elif answer in text:
            blanked = text.replace(answer, "ـــــ", 1)
        else:
            blanked = text + " (املأ الفراغ)"
        topic = row.get("topic", default_topic)
        explain = row.get("explain", "") or f"الكلمة الناقصة: {answer}."
        difficulty = int(row.get("difficulty", params.get("difficulty", 2)))
        pool = [str(d) for d in row.get("distractors", [])] + \
               [x for x in all_answers if x != answer]
        qid = signature_qid("generic.cloze", text)

        def choose(blanked=blanked, answer=answer, pool=pool, topic=topic,
                   explain=explain, difficulty=difficulty, qid=qid):
            options, index = shuffled_options(rng, answer, pool)
            if len(options) < 2:
                return None
            q = Question(qtype=QuestionType.MCQ, prompt=f"أكمل الفراغ: {blanked}",
                         correct=index, options=options, explanation=explain,
                         topic=topic, difficulty=difficulty)
            q.qid = qid
            return q

        def write(blanked=blanked, answer=answer, topic=topic, explain=explain,
                  difficulty=difficulty, qid=qid,
                  accepted=list(row.get("accepted", []))):
            q = Question(qtype=QuestionType.TYPING,
                         prompt=f"أكمل الفراغ بالكلمة المناسبة: {blanked}",
                         correct=answer, accepted=accepted, explanation=explain,
                         topic=topic, difficulty=difficulty + 1)
            q.qid = qid
            return q

        builders.extend([choose, choose, write])

    return [q for q in fill_to_count(builders, count, rng) if q is not None]


# ---------------------------------------------------------------------------
# generic.ordering
# ---------------------------------------------------------------------------

@register("generic.ordering")
def gen_ordering(count: int, rng: random.Random, **params) -> List[Question]:
    """Arrange items into their correct order (steps, chronology, magnitude).

    ``params['sequences']`` is a list of ``{"prompt", "items": [...] }`` where
    ``items`` is already in the right order. Longer sequences are sampled down
    to a window of three to five items, so one long sequence yields many
    genuinely different questions rather than a single hard one.
    """
    rows = _as_list(params, "sequences", "orders", "items")
    default_topic = params.get("topic", "")
    if not rows:
        return []
    builders = []
    for row in rows:
        items = [str(x) for x in row.get("items", []) if str(x).strip()]
        if len(items) < 3:
            continue
        prompt = str(row.get("prompt", "رتّب العناصر الترتيب الصحيح:")).strip()
        topic = row.get("topic", default_topic)
        difficulty = int(row.get("difficulty", params.get("difficulty", 2)))
        explain_tpl = row.get("explain", "")

        def make(items=items, prompt=prompt, topic=topic, difficulty=difficulty,
                 explain_tpl=explain_tpl):
            size = min(len(items), rng.randint(3, 5))
            start = rng.randint(0, len(items) - size)
            window = items[start:start + size]
            shuffled = list(window)
            for _ in range(8):
                rng.shuffle(shuffled)
                if shuffled != window:
                    break
            q = Question(
                qtype=QuestionType.ORDERING, prompt=prompt,
                correct=list(window), options=shuffled,
                explanation=explain_tpl or "الترتيب الصحيح: " + "، ".join(window) + ".",
                topic=topic, difficulty=difficulty)
            q.qid = signature_qid("generic.ordering", prompt + "|".join(window))
            return q

        builders.append(make)
    return fill_to_count(builders, count, rng)
