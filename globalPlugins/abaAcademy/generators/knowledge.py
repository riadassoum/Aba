# -*- coding: utf-8 -*-
"""
abaAcademy.generators.knowledge
===============================

Fact-domain generators for the science, history, geography and general-culture
courses.

The trick that makes these unlimited is *structure*. Instead of storing a flat
list of question/answer strings -- which yields exactly one question each and
is what the old courses did -- the content packs describe **entities with
attributes**::

    {"name": "مصر",
     "attrs": {"العاصمة": "القاهرة", "القارة": "أفريقيا", "النهر": "النيل"},
     "topic": "geo.arab"}

From n entities each carrying m attributes we can ask n×m questions forwards
("what is Egypt's capital?"), another n×m backwards ("which country's capital
is Cairo?"), the same again as true/false claims, and again as typed recall.
Twenty entities with four attributes each is already several hundred distinct
items before any option-order variation -- and the distractors are automatically
*other real values of the same attribute*, so a wrong option is always the kind
of answer that could plausibly have been right, never nonsense.

Generators:
  * ``knowledge.entity``   — attribute lookup in both directions, 4 shapes
  * ``knowledge.category`` — classification: which group does X belong to
  * ``knowledge.quantity`` — numeric facts: compare, order, recall
"""

from __future__ import annotations

import json
import os
import random
from typing import Dict, List

from ..engine.models import Question, QuestionType
from . import fill_to_count, register, shuffled_options, signature_qid


_TRICK_BANK: Dict[str, List[str]] | None = None


def _trick_bank() -> Dict[str, List[str]]:
    """A shared pool of plausible wrong answers per attribute name (currencies,
    capitals, languages, chemical symbols…), harvested from real values across
    all packs. It enriches the distractor pool so even a lesson with only a few
    entities can present many convincing near-miss options — e.g. for a currency
    question the lures include other real currencies, not just the two or three
    that happen to be in the same lesson. Loaded once and cached."""
    global _TRICK_BANK
    if _TRICK_BANK is None:
        _TRICK_BANK = {}
        try:
            here = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(here, "..", "resources", "banks", "trick_answers.json")
            with open(path, encoding="utf-8") as f:
                _TRICK_BANK = json.load(f)
        except Exception:
            _TRICK_BANK = {}
    return _TRICK_BANK


def _entities(params) -> List[Dict]:
    rows = params.get("entities") or params.get("items") or []
    return [r for r in rows if isinstance(r, dict) and r.get("name")
            and isinstance(r.get("attrs"), dict)]


@register("knowledge.entity")
def gen_entity(count: int, rng: random.Random, **params) -> List[Question]:
    rows = _entities(params)
    if not rows:
        return []
    default_topic = params.get("topic", "knowledge")
    kind = params.get("kind", "")          # e.g. "الدولة", "العنصر", "الحدث"

    # Index every value seen for each attribute, so distractors for
    # "capital of Egypt" are other real capitals rather than random words.
    by_attr: Dict[str, List[str]] = {}
    for row in rows:
        for attr, value in row["attrs"].items():
            if value:
                by_attr.setdefault(attr, [])
                if str(value) not in by_attr[attr]:
                    by_attr[attr].append(str(value))
    all_names = list(dict.fromkeys(str(r["name"]) for r in rows))
    bank = _trick_bank()

    # For each attribute, collect the set of "type" words — the first word of
    # multi-word values (e.g. currency types الريال/الدينار/الدرهم, or title
    # words). These let us manufacture same-owner distractors: for «الريال
    # السعودي» we can offer «الدرهم السعودي»، «الدينار السعودي» — plausible wrong
    # answers that keep the country's OWN qualifier, so a learner can't win by
    # spotting a foreign currency. This is far better than offering another
    # country's real currency, which gives the answer away.
    type_words: Dict[str, List[str]] = {}
    for attr, values in by_attr.items():
        types = []
        for v in list(values) + bank.get(attr, []):
            parts = v.split()
            if len(parts) >= 2 and parts[0] not in types:
                types.append(parts[0])
        if len(types) >= 2:
            type_words[attr] = types

    def same_owner_variants(attr, value):
        """Distractors that keep ``value``'s qualifier but swap its type word,
        e.g. «الريال السعودي» -> «الدرهم السعودي», «الدينار السعودي». Returns []
        when the value isn't a "<type> <qualifier>" shape."""
        parts = value.split()
        if len(parts) < 2 or attr not in type_words:
            return []
        head, tail = parts[0], " ".join(parts[1:])
        out = []
        for t in type_words[attr]:
            if t != head:
                out.append(f"{t} {tail}")
        return out

    # widen each attribute's distractor pool with the shared trick bank, so
    # thin lessons still get many convincing near-misses (other real values of
    # the same kind), not just the handful present in this lesson.
    for attr, seen in list(by_attr.items()):
        for extra in bank.get(attr, []):
            if extra not in seen:
                seen.append(extra)

    builders = []
    for row in rows:
        name = str(row["name"])
        topic = row.get("topic", default_topic)
        difficulty = int(row.get("difficulty", params.get("difficulty", 1)))
        for attr, value in row["attrs"].items():
            value = str(value)
            if not value:
                continue
            peers = [v for v in by_attr.get(attr, []) if v != value]
            qid = signature_qid("knowledge.entity", f"{name}|{attr}")
            # Templates use "في" so one wording reads correctly for every
            # attribute name a pack might invent, without the generator having
            # to know Arabic grammar. The entity kind ("بلد", "عنصر") is used
            # only in the reverse direction, where it is genuinely needed.
            subject = f"«{name}»"

            def forward(name=name, attr=attr, value=value, peers=peers,
                        topic=topic, difficulty=difficulty, qid=qid,
                        subject=subject):
                # Prefer distractors that keep this entity's OWN qualifier and
                # only change the type word — «الدرهم السعودي»، «الدينار السعودي»
                # for «الريال السعودي» — so no option belongs to another country
                # and gives the answer away. Fall back to peer values only when
                # the answer isn't a "<type> <qualifier>" shape (e.g. a bare
                # capital city), where peers are the right kind of distractor.
                own = same_owner_variants(attr, value)
                if len(own) >= 3:
                    options, index = shuffled_options(rng, value, own, hard=1.0)
                elif own:
                    # a few own-variants plus a couple of peers to fill out
                    pool = own + [p for p in peers if p not in own]
                    options, index = shuffled_options(rng, value, pool, hard=0.9)
                else:
                    options, index = shuffled_options(rng, value, peers, hard=0.85)
                if len(options) < 2:
                    return None
                q = Question(qtype=QuestionType.MCQ,
                             prompt=f"ما {attr} في {subject}؟",
                             correct=index, options=options,
                             explanation=f"{attr} في {subject}: {value}.",
                             topic=topic, difficulty=difficulty)
                q.qid = qid
                return q

            def backward(name=name, attr=attr, value=value, topic=topic,
                         difficulty=difficulty, qid=qid):
                # Only meaningful when the value identifies its entity uniquely.
                owners = [r for r in rows if str(r["attrs"].get(attr, "")) == value]
                if len(owners) != 1:
                    return None
                options, index = shuffled_options(
                    rng, name, [n for n in all_names if n != name])
                if len(options) < 2:
                    return None
                label = kind or "العنصر"
                q = Question(qtype=QuestionType.MCQ,
                             prompt=f"أي {label} {attr} فيه «{value}»؟",
                             correct=index, options=options,
                             explanation=f"{attr} في «{name}»: {value}.",
                             topic=topic, difficulty=difficulty + 1)
                q.qid = qid
                return q

            def judge(name=name, attr=attr, value=value, peers=peers,
                      topic=topic, difficulty=difficulty, qid=qid,
                      subject=subject):
                claim_true = not peers or rng.random() < 0.5
                shown = value if claim_true else rng.choice(peers)
                q = Question(qtype=QuestionType.TRUE_FALSE,
                             prompt=f"في {subject}: هل {attr} «{shown}»؟",
                             correct=claim_true,
                             explanation=(f"نعم، {attr} في {subject}: {value}."
                                          if claim_true else
                                          f"لا، {attr} في {subject}: {value}، وليس {shown}."),
                             topic=topic, difficulty=difficulty)
                q.qid = qid
                return q

            def recall(name=name, attr=attr, value=value, topic=topic,
                       difficulty=difficulty, qid=qid, subject=subject):
                q = Question(qtype=QuestionType.TYPING,
                             prompt=f"اكتب {attr} في {subject}:",
                             correct=value,
                             explanation=f"{attr} في {subject}: {value}.",
                             topic=topic, difficulty=difficulty + 2)
                q.qid = qid
                return q

            builders.extend([forward, forward, backward, judge, recall])

    return [q for q in fill_to_count(builders, count, rng) if q is not None]


@register("knowledge.category")
def gen_category(count: int, rng: random.Random, **params) -> List[Question]:
    """Classification drilling.

    ``params['groups']`` maps a group name to its members::

        {"الثدييات": ["الأسد", "الحوت"], "الطيور": ["النسر", "الحمامة"]}

    Produces "which group does X belong to?", "which of these is a bird?" and
    "which one does not belong?" -- three shapes over every member, so the
    combination count grows with members × groups.
    """
    groups = params.get("groups")
    if not isinstance(groups, dict):
        return []
    groups = {str(k): [str(x) for x in v if str(x).strip()]
              for k, v in groups.items() if isinstance(v, list) and v}
    if len(groups) < 2:
        return []
    topic = params.get("topic", "knowledge.category")
    noun = params.get("noun", "العنصر")
    group_names = list(groups)

    builders = []
    for group, members in groups.items():
        others = [g for g in group_names if g != group]
        outsiders = [m for g in others for m in groups[g]]
        for member in members:
            qid = signature_qid("knowledge.category", f"{group}|{member}")

            def which_group(member=member, group=group, others=others, qid=qid):
                options, index = shuffled_options(rng, group, others)
                if len(options) < 2:
                    return None
                q = Question(qtype=QuestionType.MCQ,
                             prompt=f"إلى أي مجموعة ينتمي «{member}»؟",
                             correct=index, options=options,
                             explanation=f"«{member}» من {group}.",
                             topic=topic, difficulty=1)
                q.qid = qid
                return q

            def pick_member(member=member, group=group, outsiders=outsiders, qid=qid):
                options, index = shuffled_options(rng, member, outsiders)
                if len(options) < 2:
                    return None
                q = Question(qtype=QuestionType.MCQ,
                             prompt=f"أي {noun} التالي من {group}؟",
                             correct=index, options=options,
                             explanation=f"«{member}» من {group}.",
                             topic=topic, difficulty=2)
                q.qid = qid
                return q

            builders.extend([which_group, pick_member])

    def odd_one_out():
        group = rng.choice([g for g in group_names if len(groups[g]) >= 3])
        same = rng.sample(groups[group], 3)
        other = rng.choice([g for g in group_names if g != group])
        odd = rng.choice(groups[other])
        options = same + [odd]
        rng.shuffle(options)
        q = Question(qtype=QuestionType.MCQ,
                     prompt="أي عنصر لا ينتمي إلى المجموعة؟",
                     correct=options.index(odd), options=options,
                     explanation=f"«{odd}» من {other}، وبقية العناصر من {group}.",
                     topic=topic, difficulty=3)
        q.qid = signature_qid("knowledge.category", "odd|" + "|".join(sorted(options)))
        return q

    if any(len(v) >= 3 for v in groups.values()):
        builders.extend([odd_one_out] * max(1, len(builders) // 6))

    return [q for q in fill_to_count(builders, count, rng) if q is not None]


@register("knowledge.quantity")
def gen_quantity(count: int, rng: random.Random, **params) -> List[Question]:
    """Numeric facts: recall a value, and compare two of them.

    ``params['quantities']`` is a list of ``{"label", "value", "unit"}`` where
    ``value`` is a number. Comparison questions are generated by *computing*
    the answer from the two values, so they are correct by construction and
    every pair of rows is a fresh question -- n rows give n(n-1)/2 comparisons
    on top of n recalls.
    """
    rows = []
    for row in params.get("quantities", []) or []:
        if not isinstance(row, dict):
            continue
        try:
            value = float(row.get("value"))
        except (TypeError, ValueError):
            continue
        label = str(row.get("label", "")).strip()
        if label:
            rows.append({"label": label, "value": value,
                         "unit": str(row.get("unit", "")),
                         "display": str(row.get("display", row.get("value")))})
    if not rows:
        return []
    topic = params.get("topic", "knowledge.quantity")
    all_display = [r["display"] for r in rows]

    builders = []
    for row in rows:
        qid = signature_qid("knowledge.quantity", row["label"])

        def recall(row=row, qid=qid):
            options, index = shuffled_options(
                rng, row["display"], [d for d in all_display if d != row["display"]])
            if len(options) < 2:
                return None
            unit = f" ({row['unit']})" if row["unit"] else ""
            q = Question(qtype=QuestionType.MCQ,
                         prompt=f"كم يبلغ {row['label']}{unit}؟",
                         correct=index, options=options,
                         explanation=f"{row['label']} = {row['display']} {row['unit']}".strip() + ".",
                         topic=topic, difficulty=2)
            q.qid = qid
            return q

        builders.append(recall)

    def compare():
        if len(rows) < 2:
            return None
        a, b = rng.sample(rows, 2)
        if a["value"] == b["value"]:
            return None
        bigger = a if a["value"] > b["value"] else b
        options, index = shuffled_options(rng, bigger["label"],
                                          [x["label"] for x in (a, b)
                                           if x is not bigger])
        if len(options) < 2:
            return None
        q = Question(qtype=QuestionType.MCQ,
                     prompt=f"أيّهما أكبر: {a['label']} أم {b['label']}؟",
                     correct=index, options=options,
                     explanation=(f"{bigger['label']} أكبر "
                                  f"({a['label']} = {a['display']}، "
                                  f"{b['label']} = {b['display']})."),
                     topic=topic, difficulty=3)
        q.qid = signature_qid("knowledge.quantity",
                              "cmp|" + "|".join(sorted([a["label"], b["label"]])))
        return q

    if len(rows) >= 2:
        builders.extend([compare] * max(1, len(rows) // 2))

    return [q for q in fill_to_count(builders, count, rng) if q is not None]
