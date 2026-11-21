# -*- coding: utf-8 -*-
"""
abaAcademy.gui.solar_system_view
================================

المجموعة الشمسية — move through the Sun, the planets, the Moon and the dwarf
planets and hear each one's size, mass, gravity, year and distance; then
compare them in a quiz. Figures from Wikidata.
"""

from __future__ import annotations

import random

from ..science import solar_system as ss
from .tool_base import ChoiceQuiz, ToolDialog


class SolarSystemDialog(ToolDialog):
    TITLE = "المجموعة الشمسية"
    SIZE = (780, 600)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.bodies = ss.load()
        self.rng = random.Random()
        self.add_text("الشمس والكواكب الثمانية والقمر وكوكبان قزمان، مرتّبة من الشمس إلى الخارج، بأرقام من ويكي بيانات: "
                      "الحجم والكتلة والجاذبية وطول السنة والبعد عن الشمس.")
        self.list = self.add_list("الأجرام (تنقّل بالأسهم)", [b["name"] for b in self.bodies], height=170,
                                  on_select=self._show)
        self.out = self.add_output("المعلومات", height=150)
        self.quizPrompt = self.add_text("")
        self.quizList = self.add_list("الاختبار: اختر ثم Enter", [], height=90)
        self.quiz = ChoiceQuiz(self, self.quizList, lambda: ss.make_question(self.bodies, self.rng),
                               prompt_ctrl=self.quizPrompt)
        self.add_buttons([("اختبرني", self.quiz.next), ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self.finish(self.list)
        if self.bodies:
            self.list.SetSelection(0)
            self._show(speak=False)

    def instructions(self) -> str:
        return "تنقّل بين الأجرام بالأسهم لتسمع معلومات كل جرم، واضغط اختبرني للمقارنة بينها."

    def _show(self, evt=None, speak=True):
        i = self.list.GetSelection()
        if 0 <= i < len(self.bodies):
            text = ss.describe(self.bodies[i], self.bodies)
            self.out.SetValue(text)
            if speak and evt is None:
                self._say(text)

    def on_enter_key(self) -> bool:
        focus = self.FindFocus()
        if focus is self.quizList:
            self.quiz.answer()
            return True
        if focus is self.list:
            self._show()
            return True
        return False
