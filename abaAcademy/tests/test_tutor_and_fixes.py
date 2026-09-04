# -*- coding: utf-8 -*-
"""Tests for this round of fixes: the capital-distractor bug, lenient Arabic
answer matching, no-duplicate-in-a-lesson, and the adaptive tutor planner."""

import os
import random
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.generators.knowledge import gen_entity
from abaAcademy.engine.models import Question, QuestionType
from abaAcademy.engine.grading import _typing_matches
from abaAcademy.engine.session import QuestionSession
from abaAcademy.engine.tutor import Tutor, MasteryEstimate


_ENTITIES = [
    {"name": "الإمارات", "attrs": {"العاصمة": "أبو ظبي", "العملة": "الدرهم الإماراتي"}},
    {"name": "السعودية", "attrs": {"العاصمة": "الرياض", "العملة": "الريال السعودي"}},
    {"name": "مصر", "attrs": {"العاصمة": "القاهرة", "العملة": "الجنيه المصري"}},
    {"name": "إثيوبيا", "attrs": {"العاصمة": "أديس أبابا", "العملة": "البِر الإثيوبي"}},
    {"name": "باكستان", "attrs": {"العاصمة": "إسلام آباد", "العملة": "الروبية الباكستانية"}},
    {"name": "الأردن", "attrs": {"العاصمة": "عمّان", "العملة": "الدينار الأردني"}},
]


class TestCapitalDistractors(unittest.TestCase):
    def test_no_frankenstein_place_names(self):
        # The bug produced hybrids by swapping the first word of a place name:
        # «أبو ظبي» -> «إسلام ظبي», «أديس ظبي». Such a hybrid shares its TAIL with
        # the real capital but has a different, real HEAD from another capital.
        # Assert no option is exactly that kind of manufactured hybrid.
        heads, tails = set(), set()
        real_capitals = set()
        for e in _ENTITIES:
            cap = e["attrs"]["العاصمة"]
            real_capitals.add(cap)
            parts = cap.split()
            if len(parts) >= 2:
                heads.add(parts[0])
                tails.add(" ".join(parts[1:]))
        for seed in range(60):
            qs = gen_entity(30, random.Random(seed), entities=_ENTITIES,
                            topic="geo.test")
            for q in qs:
                if q.qtype != QuestionType.MCQ or "العاصمة" not in q.prompt:
                    continue
                for opt in q.options:
                    if opt in real_capitals:
                        continue
                    parts = opt.split()
                    if len(parts) >= 2:
                        head, tail = parts[0], " ".join(parts[1:])
                        is_hybrid = (head in heads and tail in tails
                                     and opt not in real_capitals)
                        self.assertFalse(is_hybrid,
                                         f"manufactured hybrid capital: {opt}")

    def test_currency_trick_still_works(self):
        # currencies SHOULD still get same-owner distractors (keep qualifier)
        saw_trick = False
        for seed in range(40):
            qs = gen_entity(30, random.Random(seed), entities=_ENTITIES,
                            topic="geo.test")
            for q in qs:
                if q.qtype != QuestionType.MCQ or "العملة" not in q.prompt:
                    continue
                if "السعودية" in q.prompt:
                    # distractors should keep «السعودي» and swap the type word
                    others = [o for i, o in enumerate(q.options) if i != q.correct]
                    if any(o.endswith("السعودي") for o in others):
                        saw_trick = True
        self.assertTrue(saw_trick, "currency same-owner distractors disappeared")


class TestLenientMatching(unittest.TestCase):
    def test_hamza_and_space_variants(self):
        for v in ["أبو ظبي", "أبوظبي", "ابوظبي", "ابو ظبي", "أبو ظبى"]:
            self.assertTrue(_typing_matches("أبو ظبي", v, False), v)

    def test_ta_marbuta(self):
        self.assertTrue(_typing_matches("مكة", "مكه", False))

    def test_still_rejects_wrong(self):
        for v in ["الرياض", "دبي", "أبو ظبيي", "القاهرة"]:
            self.assertFalse(_typing_matches("أبو ظبي", v, False), v)


class TestSessionDedup(unittest.TestCase):
    def _mk(self, qid, topic="t"):
        q = Question(qtype=QuestionType.MCQ, prompt=qid, correct=0,
                     options=["a", "b"], topic=topic)
        q.qid = qid
        return q

    def test_initial_duplicates_removed(self):
        qs = [self._mk("q1"), self._mk("q2"), self._mk("q1"), self._mk("q3")]
        s = QuestionSession(qs)
        shown = []
        while s.has_next():
            q = s.next_question()
            if q is None:
                break
            shown.append(q.qid)
            s.submit(0)
        self.assertEqual(shown, ["q1", "q2", "q3"])

    def test_refill_wont_repeat_shown(self):
        pool = [self._mk("a"), self._mk("b")]
        # a refill that keeps offering an already-shown qid
        s = QuestionSession([self._mk("a")], endless=True,
                            refill=lambda topic, n: [self._mk("a"), self._mk("c")])
        first = s.next_question()
        s.submit(0)
        got = [first.qid]
        for _ in range(3):
            if s.has_next():
                q = s.next_question()
                if q:
                    got.append(q.qid)
                    s.submit(0)
        # "a" must appear only once even though refill keeps returning it
        self.assertEqual(got.count("a"), 1)


class TestTutorPlanner(unittest.TestCase):
    class _Store:
        def __init__(self, weak, strong):
            self._w, self._s = weak, strong
        def weakest_topics(self, limit=5):
            return self._w[:limit]
        def strongest_topics(self, limit=5):
            return self._s[:limit]
        def current_streak(self):
            return 4

    def test_struggling_gets_easier_and_more_review(self):
        st = self._Store(weak=[("t1", 8, 2), ("t2", 6, 1)], strong=[])
        plan = Tutor(st).plan_session(current_topic="t1", size=12)
        self.assertEqual(plan.difficulty_target, 1)
        self.assertEqual(plan.total, 12)
        self.assertGreater(plan.weak_count, 0)

    def test_strong_gets_harder_and_more_new(self):
        st = self._Store(weak=[], strong=[("t1", 1, 20)])
        plan = Tutor(st).plan_session(current_topic="t1", size=12)
        self.assertEqual(plan.difficulty_target, 3)
        self.assertGreater(plan.new_count, plan.weak_count)

    def test_mastery_labels(self):
        self.assertEqual(MasteryEstimate("x", 0, 0).level, "new")
        self.assertEqual(MasteryEstimate("x", 20, 0).level, "mastered")
        self.assertEqual(MasteryEstimate("x", 1, 5).level, "struggling")

    def test_interleave_present_in_plan(self):
        st = self._Store(weak=[], strong=[("t1", 1, 20)])
        plan = Tutor(st).plan_session(current_topic="t1", size=12)
        self.assertGreater(plan.interleave_count, 0)


class TestDistinctAttributes(unittest.TestCase):
    """A capital question and a currency/language question about the SAME country
    are different questions and must both be askable — dedup must not collapse
    them."""

    ENTS = [{"name": "الإمارات",
             "attrs": {"العاصمة": "أبو ظبي", "العملة": "الدرهم الإماراتي",
                       "اللغة": "العربية"}}]

    def test_each_attribute_has_its_own_qid(self):
        qs = gen_entity(30, random.Random(1), entities=self.ENTS, topic="t")
        by_attr = {}
        for q in qs:
            for attr in ("العاصمة", "العملة", "اللغة"):
                if attr in q.prompt:
                    by_attr.setdefault(attr, set()).add(q.qid)
        qids = [list(v)[0] for v in by_attr.values()]
        self.assertEqual(len(qids), 3)
        self.assertEqual(len(set(qids)), 3)   # all distinct

    def test_dedup_keeps_all_three_attributes(self):
        from abaAcademy.academy import Academy
        qs = gen_entity(30, random.Random(1), entities=self.ENTS, topic="t")
        deduped = Academy.dedup_questions(qs)
        attrs = set()
        for q in deduped:
            for attr in ("العاصمة", "العملة", "اللغة"):
                if attr in q.prompt:
                    attrs.add(attr)
        self.assertEqual(attrs, {"العاصمة", "العملة", "اللغة"})


class TestLeniencyToggle(unittest.TestCase):
    def test_lenient_accepts_variants(self):
        self.assertTrue(_typing_matches("أبو ظبي", "ابو ظبي", False, True))

    def test_strict_rejects_hamza_variant(self):
        self.assertFalse(_typing_matches("أبو ظبي", "ابو ظبي", False, False))

    def test_strict_accepts_exact(self):
        self.assertTrue(_typing_matches("أبو ظبي", "أبو ظبي", False, False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
