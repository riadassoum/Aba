# -*- coding: utf-8 -*-
"""
abaAcademy.tests.test_engine
============================

Engine unit tests, runnable without NVDA or wx (the whole point of the
engine/GUI split). Run with:  python -m pytest test_engine.py   or the bundled
``run_tests.py``.

Covers grading correctness across question types, Arabic normalization, the
procedural generators (determinism + anti-repetition + computed answers), the
session driver (stats, skip, adaptive refill), the SRS scheduler, lesson
isolation in the loader, and teacher-tool validation.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.engine import grading
from abaAcademy.engine.models import Question, QuestionType
from abaAcademy.engine.session import QuestionSession
from abaAcademy import generators as gen


class TestGrading(unittest.TestCase):
    def test_mcq(self):
        q = Question(QuestionType.MCQ, "?", correct=2, options=["a", "b", "c"])
        self.assertTrue(grading.grade(q, 2))
        self.assertFalse(grading.grade(q, 0))

    def test_true_false(self):
        q = Question(QuestionType.TRUE_FALSE, "?", correct=True)
        self.assertTrue(grading.grade(q, True))
        self.assertFalse(grading.grade(q, False))

    def test_typing_normalization(self):
        q = Question(QuestionType.TYPING, "?", correct="مَدْرَسَة")
        # diacritics ignored by default
        self.assertTrue(grading.grade(q, "مدرسة"))
        # accepted variants
        q2 = Question(QuestionType.TYPING, "?", correct="color", accepted=["colour"])
        self.assertTrue(grading.grade(q2, "COLOUR"))

    def test_multi_select_and_ordering(self):
        q = Question(QuestionType.MULTI_SELECT, "?", correct=[0, 2], options=["a", "b", "c"])
        self.assertTrue(grading.grade(q, [2, 0]))
        self.assertFalse(grading.grade(q, [0, 1]))
        q2 = Question(QuestionType.ORDERING, "?", correct=["x", "y", "z"])
        self.assertTrue(grading.grade(q2, ["x", "y", "z"]))
        self.assertFalse(grading.grade(q2, ["y", "x", "z"]))


class TestGenerators(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gen.load_builtin_generators()

    def test_sun_moon_computed(self):
        qs = gen.generate("ar.sun_moon", count=6, seed=1,
                          words=["الشمس", "القمر", "الرجل", "الباب"])
        self.assertTrue(qs)
        for q in qs:
            self.assertIn("اللام", q.prompt)
            self.assertIsInstance(q.correct, int)

    def test_conjugate_distractors_are_other_pronouns(self):
        qs = gen.generate("ar.conjugate", count=5, seed=2,
                          verbs=[{"stem": "كتب", "meaning": "يكتب"}])
        self.assertTrue(qs)
        for q in qs:
            self.assertEqual(len(q.options), len(set(q.options)))  # no dup options

    def test_frame_no_immediate_repeat(self):
        frames = [{"prompt": f"q{i}", "correct": f"c{i}", "distractors": ["x", "y", "z"]}
                  for i in range(10)]
        qs = gen.generate("generic.frame", count=10, seed=5, frames=frames)
        prompts = [q.prompt for q in qs]
        # dedup within batch should avoid consecutive repeats
        for a, b in zip(prompts, prompts[1:]):
            self.assertNotEqual(a, b)

    def test_deterministic_with_seed(self):
        a = gen.generate("generic.frame", count=5, seed=42,
                         frames=[{"prompt": "p", "correct": "c", "distractors": ["x", "y", "z"]}])
        b = gen.generate("generic.frame", count=5, seed=42,
                         frames=[{"prompt": "p", "correct": "c", "distractors": ["x", "y", "z"]}])
        self.assertEqual([q.prompt for q in a], [q.prompt for q in b])


class TestSession(unittest.TestCase):
    def _questions(self, n):
        return [Question(QuestionType.MCQ, f"q{i}", correct=0, options=["a", "b"], topic="t")
                for i in range(n)]

    def test_stats_and_skip(self):
        s = QuestionSession(self._questions(3))
        s.next_question(); s.submit(0)   # correct
        s.next_question(); s.submit(1)   # wrong
        s.next_question(); s.skip()      # skipped
        self.assertEqual(s.stats.correct, 1)
        self.assertEqual(s.stats.wrong, 1)
        self.assertEqual(s.stats.skipped, 1)
        self.assertAlmostEqual(s.stats.accuracy, 50.0)

    def test_adaptive_refill_on_miss(self):
        pool = self._questions(1)
        extra = self._questions(1)
        s = QuestionSession(pool, refill=lambda topic, n: list(extra))
        s.next_question()
        s.submit(1)  # wrong -> should enqueue one extra for topic
        self.assertTrue(s.has_next())

    def test_endless(self):
        s = QuestionSession([], refill=lambda topic, n: self._questions(n), endless=True)
        count = 0
        while s.has_next() and count < 15:
            s.next_question(); s.submit(0); count += 1
        self.assertEqual(count, 15)


class TestNewGenerators(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gen.load_builtin_generators()

    def test_math_arithmetic_answers_are_correct(self):
        qs = gen.generate("math.add_sub", count=10, seed=3, difficulty=2)
        self.assertTrue(qs)
        for q in qs:
            # prompt like "احسب: a + b = ؟" -> verify the stored answer matches
            body = q.prompt.split(":")[1].split("=")[0]
            body = body.replace("؟", "").strip()
            # normalize operators
            expr = body.replace("×", "*").replace("÷", "//")
            self.assertEqual(str(eval(expr)), q.correct)

    def test_math_algebra_solution_valid(self):
        qs = gen.generate("math.algebra", count=8, seed=4, difficulty=3)
        self.assertTrue(qs)
        for q in qs:
            # answer must be a positive integer string
            self.assertTrue(q.correct.isdigit())

    def test_math_endless_variety(self):
        qs = gen.generate("math.mul_div", count=30, seed=9, difficulty=3)
        prompts = [q.prompt for q in qs]
        # anti-repetition: no two consecutive identical prompts
        for a, b in zip(prompts, prompts[1:]):
            self.assertNotEqual(a, b)

    def test_language_translate(self):
        words = [
            {"word": "hello", "meaning": "مرحبا", "topic": "greet", "difficulty": 1},
            {"word": "goodbye", "meaning": "وداعا", "topic": "greet", "difficulty": 1},
            {"word": "please", "meaning": "من فضلك", "topic": "greet", "difficulty": 1},
            {"word": "thanks", "meaning": "شكرا", "topic": "greet", "difficulty": 1},
        ]
        qs = gen.generate("lang.translate", count=4, seed=1, words=words, lang="en")
        self.assertTrue(qs)
        for q in qs:
            self.assertIn(q.options[q.correct], [w["meaning"] for w in words])

    def test_language_all_exercise_types(self):
        words = [
            {"word": "hello", "meaning": "مرحبا", "topic": "greet", "difficulty": 1,
             "example": "Hello my friend", "translation": "مرحبا يا صديقي"},
            {"word": "sorry", "meaning": "آسف", "topic": "greet", "difficulty": 1,
             "example": "Sorry I am late", "translation": "آسف أنا متأخر"},
            {"word": "please", "meaning": "من فضلك", "topic": "greet", "difficulty": 1,
             "example": "Please sit down", "translation": "من فضلك اجلس"},
            {"word": "water", "meaning": "ماء", "topic": "food", "difficulty": 1,
             "example": "I drink water", "translation": "أشرب الماء"},
            {"word": "bread", "meaning": "خبز", "topic": "food", "difficulty": 1,
             "example": "I eat bread", "translation": "آكل الخبز"},
            {"word": "milk", "meaning": "حليب", "topic": "food", "difficulty": 1,
             "example": "I like milk", "translation": "أحب الحليب"},
        ]
        # true/false yields booleans and self-consistent explanations
        tf = gen.generate("lang.truefalse", count=4, seed=2, words=words, lang="en")
        self.assertTrue(tf)
        for q in tf:
            self.assertIn(q.correct, (True, False))
        # fill-blank blanks the word out of its own sentence
        fb = gen.generate("lang.fillblank", count=3, seed=3, words=words, lang="en")
        self.assertTrue(fb)
        for q in fb:
            self.assertIn("-----", q.prompt)
        # odd-one-out needs 2+ topics: here greet & food
        odd = gen.generate("lang.oddword", count=3, seed=4, words=words, lang="en")
        self.assertTrue(odd)
        # sentence ordering returns a shuffled list whose sorted form matches correct
        build = gen.generate("lang.build", count=3, seed=5, words=words, lang="en")
        self.assertTrue(build)
        for q in build:
            self.assertEqual(sorted(q.options), sorted(q.correct))
            # grading the correct order passes; a wrong order fails
            self.assertTrue(grading.grade(q, q.correct))
            if len(q.correct) > 1:
                self.assertFalse(grading.grade(q, list(reversed(q.correct))))



    def test_schedule_progression(self):
        from abaAcademy.database.store import Store
        from abaAcademy.database import srs
        tmp = tempfile.mkdtemp()
        store = Store(os.path.join(tmp, "t.db"))
        # correct fast -> interval grows over reps
        for _ in range(3):
            srs.schedule_review(store, "q1", "topic", "c", correct=True, elapsed=2.0)
        row = store.srs_get("q1")
        self.assertGreaterEqual(row["repetitions"], 3)
        self.assertGreater(row["interval_days"], 1.0)
        grown = row["interval_days"]
        # under FSRS a miss collapses the interval so the concept returns soon
        # (repetitions is a lifetime counter and is not reset)
        srs.schedule_review(store, "q1", "topic", "c", correct=False, elapsed=10.0)
        row2 = store.srs_get("q1")
        self.assertLess(row2["interval_days"], 1.0)
        self.assertLess(row2["interval_days"], grown)
        store.close()


class TestNewFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gen.load_builtin_generators()

    def test_dedup_by_prompt_keeps_different_exercise_types(self):
        from abaAcademy.academy import Academy
        qs = [
            Question(QuestionType.MCQ, "ما معنى hello؟", correct=0, options=["a", "b"]),
            Question(QuestionType.TRUE_FALSE, "هل معنى hello هو مرحبا؟", correct=True),
            Question(QuestionType.MCQ, "ما معنى hello؟", correct=0, options=["a", "b"]), # dup
        ]
        out = Academy.dedup_questions(qs)
        self.assertEqual(len(out), 2)
        prompts = [q.prompt for q in out]
        self.assertIn("ما معنى hello؟", prompts)
        self.assertIn("هل معنى hello هو مرحبا؟", prompts)

    def test_dictation_sets_speak(self):
        qs = gen.generate("lang.dictation", count=3, seed=1,
                          sentences=[{"text": "I have a car.", "translation": "لديّ سيارة"},
                                     {"text": "She is happy.", "translation": "هي سعيدة"}],
                          lang="en")
        self.assertTrue(qs)
        for q in qs:
            self.assertEqual(q.qtype, QuestionType.TYPING)
            self.assertTrue(q.speak)
            self.assertEqual(q.correct, q.speak)
            self.assertNotIn(q.speak, q.prompt)

    def test_conjugate_forms_correct(self):
        verbs = [{"infinitive": "to be", "meaning": "يكون", "tense": "المضارع البسيط",
                  "forms": {"I": "am", "you": "are", "he": "is", "she": "is",
                            "we": "are", "they": "are"}}]
        qs = gen.generate("lang.conjugate", count=8, seed=2, verbs=verbs, lang="en")
        self.assertTrue(qs)
        for q in qs:
            correct_val = q.options[q.correct] if q.qtype is QuestionType.MCQ else q.correct
            self.assertIn(correct_val, ["am", "are", "is"])


class TestTeacherValidation(unittest.TestCase):
    def test_builder_and_validate(self):
        from abaAcademy.teacher.editor import LessonBuilder
        b = LessonBuilder("t.l1", "درس تجريبي", 0).objective("هدف")
        b.text("theory", "شرح").mcq("quiz", "سؤال؟", ["أ", "ب"], 1, "شرح", "topic")
        self.assertEqual(b.validate(), [])
        # invalid: mcq correct out of range
        bad = LessonBuilder("t.l2", "درس", 0)
        bad.mcq("quiz", "?", ["a", "b"], 9)
        self.assertTrue(bad.validate())



class TestRobustness(unittest.TestCase):
    """Guards that data loaders degrade gracefully on bad input."""

    def test_editions_bad_and_oob(self):
        import tempfile, os
        from abaAcademy.gui.quran_editions import QuranEditions
        res = os.path.join(os.path.dirname(__file__), "..", "resources", "quran")
        ed = QuranEditions(res, tempfile.mkdtemp(), uthmani=["x"] * 6236)
        self.assertIsNone(ed.text("en.sahih", 0))
        self.assertIsNone(ed.text("en.sahih", 99999))
        self.assertIsNone(ed.text("zz.unknown", 1))
        self.assertIsNone(ed.get_edition("zz.unknown"))

    def test_editions_missing_resdir(self):
        import tempfile
        from abaAcademy.gui.quran_editions import QuranEditions
        ed = QuranEditions("/nonexistent-xyz", tempfile.mkdtemp())
        self.assertEqual(ed.by_type("quran"), [])

    def test_hadith_unknown(self):
        import tempfile, os
        from abaAcademy.gui.hadith_data import HadithData
        res = os.path.join(os.path.dirname(__file__), "..", "resources", "hadith")
        hd = HadithData(res, tempfile.mkdtemp())
        self.assertIsNone(hd.get("nope"))
        self.assertFalse(hd.is_offline("nope"))

    def test_verse_url(self):
        from abaAcademy.gui.quran_audio import verse_url
        self.assertEqual(verse_url("http://x/", 1, 2), "http://x/001002.mp3")
        self.assertEqual(verse_url("http://x/", 114, 6), "http://x/114006.mp3")

if __name__ == "__main__":
    unittest.main()
