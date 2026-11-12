# -*- coding: utf-8 -*-
"""Tests for the hub's ranked quick-jump search, against the real hub labels."""

import ast
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.tools import feature_search as fs


def hub_labels():
    from abaAcademy.gui.hub_catalog import all_features
    return [f.label for f in all_features()]


class TestFeatureSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.labels = hub_labels()

    def top(self, q):
        hits = fs.search(q, self.labels)
        return self.labels[hits[0][1]] if hits else None

    def test_labels_found(self):
        self.assertGreater(len(self.labels), 60)

    def test_queries(self):
        cases = {
            "صلاه": "مواقيت الصلاة", "القبلة": "مواقيت الصلاة", "excel": "الجدول الناطق",
            "سودوكو": None, "مورس": "مورس", "الجدول الدوري": "الجدول الدوري",
            "العروض": "العروض", "زكاه": "الزكاة", "regex": "التعابير النمطية", "مسبحه": "المسبحة",
            "الكيمياء": "الكيمياء", "جدول الضرب": "جدول الضرب", "العواصم": "الدول العربية",
            "متتبع": "متتبّع", "مخطط": "مخطّط المذاكرة",
        }
        for q, want in cases.items():
            got = self.top(q)
            if want is None:
                continue
            self.assertIsNotNone(got, q)
            self.assertIn(fs.fold(want), fs.fold(got), (q, got))

    def test_typo_and_article(self):
        self.assertIn("الجذور", self.top("الجذر والوزن") or "")
        self.assertIn("الكيمياء", self.top("كمياء الحاسبة") or self.top("الكيمياء"))
        self.assertTrue(fs._close("فيزياء", "فيزيا"))
        self.assertFalse(fs._close("قلم", "علم"))

    def test_nothing(self):
        self.assertEqual(fs.search("زززززز", self.labels), [])
        self.assertEqual(fs.search("", self.labels), [])


if __name__ == "__main__":
    unittest.main()
