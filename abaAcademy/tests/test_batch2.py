# -*- coding: utf-8 -*-
"""Tests for Batch 2 modules: code sandbox + Arabic diagnostics, challenges,
clipboard formatter, notebook, shortcuts, and the mistakes-view topic label fix."""

import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.codelab.sandbox import run_code
from abaAcademy.codelab.ast_diagnostics import explain_syntax, explain_exception
from abaAcademy.codelab.challenges import get_challenge, check_solution
from abaAcademy.tools import clipboard_formatter as cf
from abaAcademy.tools import shortcuts_data as sd
from abaAcademy.study_hub.notebook import Notebook


class TestDiagnostics(unittest.TestCase):
    def test_missing_colon(self):
        msg = explain_syntax("if x > 5\n    print(x)")
        self.assertIn("النقطتين", msg)

    def test_indentation(self):
        msg = explain_syntax("def f():\nprint(1)")
        self.assertIn("المسافة البادئة", msg)

    def test_valid_returns_none(self):
        self.assertIsNone(explain_syntax("x = 1\nprint(x)"))

    def test_runtime_name_error(self):
        msg = explain_exception(NameError, NameError("name 'foo' is not defined"), 2)
        self.assertIn("غير معرّف", msg)
        self.assertIn("foo", msg)


class TestSandbox(unittest.TestCase):
    def test_output_capture(self):
        r = run_code("print('hi')")
        self.assertTrue(r.ok)
        self.assertEqual(r.output.strip(), "hi")

    def test_syntax_caught_before_run(self):
        r = run_code("print('unclosed")
        self.assertFalse(r.ok)
        self.assertIsNotNone(r.error)

    def test_runtime_error_explained(self):
        r = run_code("print([1][5])")
        self.assertFalse(r.ok)
        self.assertIn("النطاق", r.error)

    def test_forbidden_import(self):
        r = run_code("import os")
        self.assertFalse(r.ok)

    def test_allowed_import(self):
        r = run_code("import math\nprint(math.floor(3.7))")
        self.assertTrue(r.ok)
        self.assertEqual(r.output.strip(), "3")


class TestChallenges(unittest.TestCase):
    def test_output_challenge_pass(self):
        c = get_challenge("c01")
        ok, _ = check_solution(c, 'print("مرحبا بالعالم")')
        self.assertTrue(ok)

    def test_func_challenge_pass(self):
        c = get_challenge("c04")
        ok, _ = check_solution(c, "def is_even(n):\n    return n % 2 == 0")
        self.assertTrue(ok)

    def test_func_challenge_fail(self):
        c = get_challenge("c04")
        ok, msg = check_solution(c, "def is_even(n):\n    return True")
        self.assertFalse(ok)


class TestClipboard(unittest.TestCase):
    def test_digits_to_western(self):
        self.assertEqual(cf.to_western_digits("١٢٣"), "123")

    def test_digits_to_arabic(self):
        self.assertEqual(cf.to_arabic_digits("123"), "١٢٣")

    def test_tatweel(self):
        self.assertEqual(cf.strip_tatweel("مرحبــا"), "مرحبا")

    def test_punctuation_spacing(self):
        out = cf.fix_punctuation_spacing("مرحبا ،كيف")
        self.assertNotIn(" ،", out)
        self.assertIn("، ", out)

    def test_clean_removes_invisibles(self):
        out = cf.clean_text("a\u200fb", digits="none")
        self.assertNotIn("\u200f", out)


class TestNotebook(unittest.TestCase):
    def test_add_search_persist(self):
        d = tempfile.mkdtemp()
        nb = Notebook(d)
        nb.add("آية الكرسي", tag="قرآن")
        nb.add("درس الجمع", tag="رياضيات")
        self.assertEqual(len(nb.all()), 2)
        self.assertEqual(len(nb.search("آية")), 1)
        # reload
        nb2 = Notebook(d)
        self.assertEqual(len(nb2.all()), 2)

    def test_delete(self):
        d = tempfile.mkdtemp()
        nb = Notebook(d)
        note = nb.add("temp")
        self.assertTrue(nb.delete(note["id"]))
        self.assertEqual(len(nb.all()), 0)


class TestShortcuts(unittest.TestCase):
    def test_categories(self):
        self.assertIn("NVDA", sd.all_categories())

    def test_search(self):
        results = sd.search("نسخ")
        self.assertTrue(any("Ctrl + C" in k for _, k, _ in results))


class TestMistakesLabel(unittest.TestCase):
    def test_dotted_topic_label(self):
        from abaAcademy.gui import mistakes_view
        label = mistakes_view.MistakesView._topic_label
        self.assertIn("الجغرافيا", label(None, "geo.arab2"))
        self.assertIn("الرياضيات", label(None, "math.add"))

    def test_colon_topic_label(self):
        from abaAcademy.gui import mistakes_view
        label = mistakes_view.MistakesView._topic_label
        self.assertIn("الإنجليزية", label(None, "en:confusable"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
