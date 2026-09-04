# -*- coding: utf-8 -*-
"""Tests for adopting JSON-format progress into the SQLite store.

Progress written by the older JSON backend must be visible in the application:
a learner whose file was copied across but never read saw an empty academy even
though every lesson they had finished was sitting in the file.
"""

import json
import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.database.store import Store
from abaAcademy.database.json_import import (
    import_json_document, import_json_file, has_content,
)


def _doc():
    return {
        "schema_version": 2,
        "sessions": {"1": {"session_id": 1, "course_id": "english",
                           "level_id": "level1",
                           "lesson_ids": ["english.L1.a.0"], "mode": "quiz"}},
        "attempts": [
            {"session_id": 1, "qid": "q1", "topic": "en:colours",
             "course_id": "english", "correct": 1, "skipped": 0,
             "elapsed": 2.0, "answered_at": 1785402240.0},
            {"session_id": 1, "qid": "q2", "topic": "en:colours",
             "course_id": "english", "correct": 0, "skipped": 0,
             "elapsed": 3.0, "answered_at": 1785402250.0},
        ],
        "mistakes": {"en:colours": {"topic": "en:colours",
                                    "course_id": "english",
                                    "wrong_count": 1, "right_count": 5,
                                    "last_seen": 1785402250.0}},
        "srs": {"q1": {"qid": "q1", "topic": "en:colours",
                       "course_id": "english", "ease": 2.5,
                       "interval_days": 3.0, "repetitions": 2,
                       "due_at": 1786006029.0, "last_review": 1785746829.0}},
        "lesson_progress": {"english.L1.a.0": {
            "lesson_id": "english.L1.a.0", "course_id": "english",
            "level_id": "level1", "best_score": 91, "mastery": 0.9,
            "completed": 1}},
        "achievements": {"first_correct": {"ach_id": "first_correct",
                                           "title": "أول إجابة صحيحة",
                                           "earned_at": 1785402244.0}},
        "daily_activity": {"2026-07-30": {"day": "2026-07-30", "seconds": 2411,
                                          "answered": 103, "correct": 89}},
        "settings": {"last_lesson": "english.L1.a.0", "daily_goal": "25"},
    }


class TestJsonImport(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = Store(os.path.join(self.dir, "aba_academy.db"))

    def tearDown(self):
        try:
            self.store.close()
        except Exception:
            pass

    def test_imports_every_table(self):
        counts = import_json_document(self.store, _doc())
        self.assertEqual(counts["attempts"], 2)
        self.assertEqual(counts["lessons"], 1)
        self.assertEqual(counts["srs"], 1)
        self.assertEqual(counts["achievements"], 1)

    def test_progress_is_visible_afterwards(self):
        import_json_document(self.store, _doc())
        self.assertEqual(self.store.completed_lessons("english"), 1)
        self.assertEqual(self.store.total_study_seconds(), 2411)
        self.assertEqual(self.store.get_setting("last_lesson"),
                         "english.L1.a.0")
        self.assertTrue(self.store.achievements())

    def test_existing_settings_are_not_overwritten(self):
        """A learner who already set a name/goal here keeps them."""
        self.store.set_setting("daily_goal", "40")
        import_json_document(self.store, _doc())
        self.assertEqual(self.store.get_setting("daily_goal"), "40")

    def test_has_content(self):
        path = os.path.join(self.dir, "p.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_doc(), f)
        self.assertTrue(has_content(path))
        empty = os.path.join(self.dir, "e.json")
        with open(empty, "w", encoding="utf-8") as f:
            json.dump({"settings": {}}, f)
        self.assertFalse(has_content(empty))

    def test_missing_file_is_safe(self):
        self.assertIsNone(import_json_file(self.store, "/nope/x.json"))

    def test_malformed_file_is_safe(self):
        path = os.path.join(self.dir, "bad.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertIsNone(import_json_file(self.store, path))


class TestAcademyAdoptsJson(unittest.TestCase):
    """The academy must pick the file up on open, whenever it appears."""

    def _academy(self, data_dir):
        from abaAcademy.academy import Academy
        base = os.path.abspath(os.path.join(_HERE, ".."))
        return Academy(base, data_dir)

    def test_adopted_on_open(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "aba_academy.json"), "w",
                  encoding="utf-8") as f:
            json.dump(_doc(), f)
        ac = self._academy(d)
        self.assertEqual(ac.store.completed_lessons("english"), 1)

    def test_adopted_even_if_it_arrives_later(self):
        """Setting a name first must not stop progress loading afterwards."""
        d = tempfile.mkdtemp()
        ac = self._academy(d)
        ac.store.set_setting("learner_name", "قيس")
        ac.store.set_setting("onboarded", "1")
        with open(os.path.join(d, "aba_academy.json"), "w",
                  encoding="utf-8") as f:
            json.dump(_doc(), f)
        ac2 = self._academy(d)
        self.assertEqual(ac2.store.completed_lessons("english"), 1)
        self.assertEqual(ac2.store.get_setting("learner_name"), "قيس")

    def test_not_duplicated_on_reopen(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "aba_academy.json"), "w",
                  encoding="utf-8") as f:
            json.dump(_doc(), f)
        first = self._academy(d).store.total_study_seconds()
        second = self._academy(d).store.total_study_seconds()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main(verbosity=2)
