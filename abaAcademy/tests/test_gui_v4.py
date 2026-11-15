# -*- coding: utf-8 -*-
"""Drive the 4.0 screens with real wx: typing course, braille translator,
tajweed teacher. Skipped without wx and a display (run under xvfb-run)."""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

try:
    import wx
    _app = wx.App(False) if wx.GetApp() is None else wx.GetApp()
    HAVE_WX = bool(wx.Display.GetCount())
except Exception:
    HAVE_WX = False


def pump(n=6):
    for _ in range(n):
        wx.Yield()
        time.sleep(0.005)


class _Speech:
    def __init__(self):
        self.lines = []

    def announce(self, text, **_):
        self.lines.append(str(text))

    def speak_line(self, text):
        self.lines.append(str(text))

    def interrupt(self):
        pass


@unittest.skipUnless(HAVE_WX, "wx with a display is required")
class TestV4Screens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from abaDesktop.core import build_academy
        cls.academy = build_academy(tempfile.mkdtemp())
        cls.frame = wx.Frame(None)

    @classmethod
    def tearDownClass(cls):
        cls.frame.Destroy()
        pump()

    def _open(self, cls):
        sp = _Speech()
        d = cls(self.frame, self.academy, sp)
        d.Show()
        pump()
        return d, sp

    def test_typing_course(self):
        from abaAcademy.gui.typing_course_view import TypingCourseDialog
        d, sp = self._open(TypingCourseDialog)
        try:
            self.assertGreater(d.lessonList.GetCount(), 5)
            d._start()
            line = d.session.current
            d.entry.SetValue(line)
            d._submit()
            self.assertIn("الدقّة 100", " ".join(sp.lines))
            d.entry.SetValue("x")
            d._submit()
            self.assertTrue(any("أعد السطر" in l for l in sp.lines))
            d._explain()
            d._home()
        finally:
            d.Destroy()
            pump()

    def test_braille_translator(self):
        from abaAcademy.braille_engine import louis
        from abaAcademy.gui.braille_translator_view import BrailleTranslatorDialog
        d, sp = self._open(BrailleTranslatorDialog)
        try:
            d.source.SetValue("ذهب الولد إلى المدرسة")
            d.gradeChoice.SetSelection(1)
            d._to_braille()
            cells = d.result.GetValue()
            self.assertEqual(cells, louis.translate("ذهب الولد إلى المدرسة", 2))
            d._read_dots()
            d.source.SetValue(cells)
            d._to_text()
            self.assertEqual(d.result.GetValue(), "ذهب الولد إلى المدرسة")
            d._drill_next()
            word = d._drill_word
            d.drillEntry.SetValue(word)
            d._drill_check()
            self.assertTrue(sp.lines[-1].startswith("صحيح"))
        finally:
            d.Destroy()
            pump()

    def test_tajweed(self):
        from abaAcademy.gui.tajweed_view import TajweedDialog
        d, sp = self._open(TajweedDialog)
        try:
            d.surahChoice.SetSelection(0)
            d._fill_ayat()
            d.ayahList.SetSelection(6)
            d._show_ayah()
            self.assertIn("المدّ اللازم", d.out.GetValue())
            d.ruleList.SetSelection(0)
            d._explain_rule()
            self.assertIn("أمثلة", d.out.GetValue())
            d._quiz_surah()
            self.assertGreater(d.quizList.GetCount(), 1)
            d.quizList.SetSelection(0)
            d.quiz.answer()
            self.assertEqual(d.quiz.total, 1)
        finally:
            d.Destroy()
            pump()

    def test_nvda_course(self):
        from abaAcademy.gui.nvda_course_view import NvdaCourseDialog
        d, sp = self._open(NvdaCourseDialog)
        try:
            self.assertGreater(d.lessonList.GetCount(), 5)
            d.lessonList.SetSelection(1)
            d._fill_commands()
            self.assertGreater(d.cmdList.GetCount(), 0)
            d.layoutChoice.SetSelection(1)
            d._layout_changed()
            d._quiz_lesson()
            d.quizList.SetSelection(0)
            d.quiz.answer()
            self.assertEqual(d.quiz.total, 1)
        finally:
            d.Destroy()
            pump()

    def test_world_atlas(self):
        from abaAcademy.gui.countries_view import CountriesDialog
        d, sp = self._open(CountriesDialog)
        try:
            d.search.SetValue("الرباط")
            d._filter()
            self.assertEqual(d.list.GetCount(), 1)
            d._show_speak()
            self.assertIn("درهم", d.out.GetValue())
            d.search.SetValue("")
            d.regionChoice.SetSelection(1)
            d._filter()
            self.assertGreaterEqual(d.list.GetCount(), 20)
            for k in range(len(d.quizChoice.GetItems())):
                d.quizChoice.SetSelection(k)
                d.quiz.next()
                d.quizList.SetSelection(0)
                d.quiz.answer()
            self.assertEqual(d.quiz.total, len(d.quizChoice.GetItems()))
        finally:
            d.Destroy()
            pump()

    def test_spell_dialog(self):
        from abaAcademy.gui.spell_view import SpellCheckDialog
        d, sp = self._open(SpellCheckDialog)
        try:
            d.text.SetValue("ذهبت الى المدرسه")
            d._restart()
            self.assertIsNotNone(d.current)
            d.sugList.SetSelection(0)
            d._replace()
            d.sugList.SetSelection(0) if d.sugList.GetCount() else None
            if d.current:
                d._replace()
            self.assertNotIn("المدرسه", d.text.GetValue())
        finally:
            d.Destroy()
            pump()


if __name__ == "__main__":
    unittest.main()
