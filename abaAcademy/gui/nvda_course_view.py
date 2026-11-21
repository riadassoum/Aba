# -*- coding: utf-8 -*-
"""
abaAcademy.gui.nvda_course_view
===============================

دورة NVDA — lessons of NVDA keyboard commands by category, each command with
its keys for the desktop or laptop layout and NVDA's own Arabic description,
and a quiz in both directions.
"""

from __future__ import annotations

import random

from .. import nvda_course as nc
from .tool_base import ChoiceQuiz, ToolDialog


class NvdaCourseDialog(ToolDialog):
    TITLE = "دورة قارئ الشاشة NVDA"
    SIZE = (840, 660)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.lessons = nc.load()
        self.rng = random.Random()
        self.add_text("أوامر NVDA بلوحة المفاتيح درسًا درسًا، بالوصف العربي الرسمي من ترجمة NVDA نفسه. "
                      "ابدأ بالمقدّمة، ثم اختر الدرس واستمع إلى أوامره، ثم اختبر نفسك.")
        layout = self.setting("layout", "desktop")
        self.layoutChoice = self.add_choice("تخطيط لوحة المفاتيح", ["الحاسوب المكتبي", "الحاسوب المحمول"],
                                            1 if layout == "laptop" else 0, on_change=self._layout_changed)
        titles = [f"{l.title} ({len(l.commands)} أمرًا)" for l in self.lessons]
        self.lessonList = self.add_list("الدروس", titles, height=120, on_select=self._fill_commands,
                                        on_activate=self._read_lesson)
        self.cmdList = self.add_list("الأوامر", [], height=150)
        self.add_buttons([("المقدّمة", lambda: self._say(nc.INTRO)), ("اقرأ الدرس كاملًا", self._read_lesson)],
                         close=False)
        self.quizPrompt = self.add_text("")
        self.quizList = self.add_list("الاختبار: اختر الإجابة ثم Enter", [], height=100)
        self.quiz = ChoiceQuiz(self, self.quizList, self._make_q, prompt_ctrl=self.quizPrompt)
        self.add_buttons([("اختبرني في هذا الدرس", self._quiz_lesson), ("اختبرني في كل الأوامر", self._quiz_all),
                          ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self._scope = None
        self.finish(self.lessonList)
        self._fill_commands()

    def instructions(self) -> str:
        return ("اختر الدرس بالأسهم لترى أوامره، وتنقّل في قائمة الأوامر لتسمع كل أمر ومفتاحه. "
                "زرّ المقدّمة يشرح مفتاح NVDA. أزرار الاختبار تسألك عن مفتاح أمر أو عمل مفتاح.")

    def _layout(self) -> str:
        return "laptop" if self.layoutChoice.GetSelection() == 1 else "desktop"

    def _layout_changed(self, evt=None):
        self.set_setting("layout", self._layout())
        self._fill_commands()

    def _lesson(self) -> int:
        return self.lessonList.GetSelection()

    def _lines(self, i: int):
        out = []
        for c in self.lessons[i].commands:
            k = c.keys_text(self._layout())
            if k:
                out.append(f"{k}: {c.ar}")
        return out

    def _fill_commands(self, evt=None):
        i = self._lesson()
        if 0 <= i < len(self.lessons):
            self.cmdList.Set(self._lines(i))

    def _read_lesson(self, evt=None):
        i = self._lesson()
        if 0 <= i < len(self.lessons):
            self._say(f"درس {self.lessons[i].title}. " + "، ثم ".join(self._lines(i)))

    def _make_q(self):
        return nc.make_question(self.lessons, self._layout(), self._scope, self.rng)

    def _quiz_lesson(self):
        self._scope = self._lesson() if self._lesson() >= 0 else None
        self.quiz.next()

    def _quiz_all(self):
        self._scope = None
        self.quiz.next()

    def on_enter_key(self) -> bool:
        focus = self.FindFocus()
        if focus is self.quizList:
            self.quiz.answer()
            return True
        if focus is self.lessonList:
            self._read_lesson()
            return True
        return False
