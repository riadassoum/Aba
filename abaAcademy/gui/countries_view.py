# -*- coding: utf-8 -*-
"""
abaAcademy.gui.countries_view
=============================

أطلس دول العالم — search or browse the countries by region, hear each one's
capital, currency, population, area and neighbours, and practise with
quizzes on capitals, currencies, regions, neighbours and population.
"""

from __future__ import annotations

import random

from .. import geo_countries as geo
from .tool_base import ChoiceQuiz, ToolDialog

REGIONS = ["كل الدول", "الدول العربية", "أفريقيا", "آسيا", "أوروبا", "الأمريكتان", "أوقيانوسيا"]
QUIZZES = [("منوّع", None), ("العواصم", "capital"), ("عاصمة أيّ دولة", "country_of_capital"),
           ("العملات", "currency"), ("الموقع", "region"), ("الجيران", "neighbour"), ("عدد السكان", "bigger")]


class CountriesDialog(ToolDialog):
    TITLE = "أطلس دول العالم"
    SIZE = (840, 680)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.all = geo.load()
        self.rng = random.Random()
        self.add_text(f"{len(self.all)} دولة: الدول الأعضاء في الأمم المتحدة والدولتان المراقبتان. "
                      "البيانات من مشروع countries المفتوح ومن ويكي بيانات.")
        self.regionChoice = self.add_choice("المنطقة", REGIONS, 0, on_change=self._filter)
        self.search = self.add_entry("ابحث باسم الدولة أو العاصمة", on_enter=self._filter)
        self.search.Bind(__import__("wx").EVT_TEXT, lambda e: (e.Skip(), self._filter()))
        self.list = self.add_list("الدول", [], height=150, on_select=self._show, on_activate=self._show_speak)
        self.out = self.add_output("معلومات الدولة", height=150)
        self.quizChoice = self.add_choice("نوع الاختبار", [q[0] for q in QUIZZES], 0)
        self.quizPrompt = self.add_text("")
        self.quizList = self.add_list("الاختبار: اختر الإجابة ثم Enter", [], height=90)
        self.quiz = ChoiceQuiz(self, self.quizList, self._make_q, prompt_ctrl=self.quizPrompt)
        self.add_buttons([("ابدأ الاختبار", self.quiz.next), ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self.shown = []
        self.finish(self.search)
        self._filter()

    def instructions(self) -> str:
        return ("اكتب اسم دولة أو عاصمة، أو اختر المنطقة، ثم تنقّل في القائمة بالأسهم واضغط Enter لتسمع معلومات "
                "الدولة كاملة. الاختبار يأخذ أسئلته من المنطقة المختارة.")

    def _region(self):
        r = REGIONS[self.regionChoice.GetSelection()]
        return None if r == "كل الدول" else ("العربية" if r == "الدول العربية" else r)

    def _filter(self, evt=None):
        reg = self._region()
        rows = geo.find(self.all, self.search.GetValue())
        if reg == "العربية":
            rows = [c for c in rows if c["iso"] in geo.ARAB_LEAGUE]
        elif reg:
            rows = [c for c in rows if c.get("region") == reg]
        self.shown = rows
        self.list.Set([c["name"] for c in rows])
        if rows:
            self.list.SetSelection(0)
            self._show()

    def _current(self):
        i = self.list.GetSelection()
        return self.shown[i] if 0 <= i < len(self.shown) else None

    def _show(self, evt=None):
        c = self._current()
        if c:
            self.out.SetValue(geo.describe(c))

    def _show_speak(self, evt=None):
        c = self._current()
        if c:
            text = geo.describe(c)
            self.out.SetValue(text)
            self._say(text)

    def _make_q(self):
        return geo.make_question(self.all, QUIZZES[self.quizChoice.GetSelection()][1], self._region(), self.rng)

    def on_enter_key(self) -> bool:
        focus = self.FindFocus()
        if focus is self.quizList:
            self.quiz.answer()
            return True
        if focus is self.list:
            self._show_speak()
            return True
        return False
