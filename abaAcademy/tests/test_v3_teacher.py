# -*- coding: utf-8 -*-
"""Tests for the quiz builder and the weekly report."""

import datetime
import os
import random
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.teacher import quiz_builder as qb
from abaAcademy.study_hub import weekly_report as wr, planner


class MemStore(dict):
    def get_setting(self, k, d=None):
        return self.get(k, d)

    def set_setting(self, k, v):
        self[k] = v


class TestQuizBuilder(unittest.TestCase):
    def setUp(self):
        self.store = qb.QuizStore(MemStore())

    def test_validation(self):
        for bad in (qb.Question("mcq", "س؟", ["أ"]), qb.Question("mcq", "", ["أ", "ب"]),
                    qb.Question("short", "س؟"), qb.Question("mcq", "س؟", ["أ", "أ"]),
                    qb.Question("zz", "س؟")):
            with self.assertRaises(ValueError):
                bad.validate()

    def test_checking(self):
        q = qb.Question("short", "جمع كتاب؟", answers=["كتب"])
        self.assertTrue(q.check("كُتُب"))
        self.assertFalse(q.check("كتاب"))
        tf = qb.Question("tf", "س", truth=False)
        self.assertTrue(tf.check(False))
        self.assertTrue(tf.check("خطأ"))
        self.assertFalse(tf.check("صح"))
        mcq = qb.Question("mcq", "س", ["إجابة", "أخرى"], 0)
        self.assertTrue(mcq.check("اجابة"))

    def test_full_run_with_shuffled_options(self):
        quiz = qb.sample_quiz()
        self.store.save_quiz(quiz)
        for seed in range(10):
            r = qb.Runner(quiz, "طالب", random.Random(seed))
            while not r.done:
                q = r.question
                if q.kind == "short":
                    r.answer(q.answers[0])
                else:
                    r.answer(r.shown_options().index(q.correct_text()))
            a = r.finish()
            self.assertEqual(a.score, quiz.total_points)
            self.store.record(a)
        self.assertEqual(len(self.store.results(quiz.id)), 10)
        self.assertIn("طالب", self.store.results_csv())
        self.assertEqual(len(self.store.question_stats(quiz)), len(quiz.questions))

    def test_wrong_answers_and_time_limit(self):
        quiz = qb.sample_quiz()
        quiz.shuffle = False
        r = qb.Runner(quiz, "س")
        ok, fb = r.answer(1)
        self.assertFalse(ok)
        self.assertIn("الصواب", fb)
        quiz.time_limit = 1
        r2 = qb.Runner(quiz, "س")
        r2.attempt.started -= 120
        ok, fb = r2.answer(0)
        self.assertEqual(fb, "انتهى الوقت.")
        self.assertTrue(r2.done)

    def test_share_roundtrip(self):
        quiz = qb.sample_quiz()
        self.store.save_quiz(quiz)
        copy = self.store.import_quiz(quiz.to_json())
        self.assertNotEqual(copy.id, quiz.id)
        self.assertEqual(len(copy.questions), len(quiz.questions))
        with self.assertRaises(ValueError):
            self.store.import_quiz("not json")
        with self.assertRaises(ValueError):
            self.store.import_quiz('{"title": "x"}')

    def test_crud(self):
        q = self.store.create("اختبار")
        self.assertEqual(self.store.get(q.id).title, "اختبار")
        self.assertTrue(self.store.delete(q.id))
        with self.assertRaises(ValueError):
            self.store.create("  ")


class TestWeeklyReport(unittest.TestCase):
    def test_sections(self):
        st = MemStore()
        today = datetime.date(2026, 10, 18)
        p = planner.Planner(st)
        item = p.add("امتحان", today + datetime.timedelta(days=3), "exam", "علوم", 120)
        p.log_minutes(item.id, 40, today)
        st.set_setting("pomodoro_2026-10-17", "1500")
        st.set_setting("game_scores", '{"g2048": 512}')
        secs = dict(wr.sections(st, today))
        self.assertIn("40", secs["المذاكرة"][0])
        self.assertIn("التركيز", secs)
        self.assertIn("أفضل النتائج في الألعاب", secs)
        html = wr.to_html(st, "سارة", today)
        self.assertIn('dir="rtl"', html)
        self.assertIn("سارة", html)

    def test_empty(self):
        self.assertIn("المذاكرة", wr.text(MemStore()))


if __name__ == "__main__":
    unittest.main()
