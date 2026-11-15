# -*- coding: utf-8 -*-
"""
abaAcademy.gui.qutrub_view
==========================

مصرّف الأفعال — type a verb, choose its bab if it has more than one, and hear
it conjugated with every pronoun in any of twelve tenses (active and
passive, indicative, subjunctive, jussive, imperative and emphatic), with
Qutrub. A quiz asks for the right form for a pronoun.
"""

from __future__ import annotations

import random

from ..arabic_lab import qutrub as cj
from .tool_base import ChoiceQuiz, ToolDialog


class QutrubDialog(ToolDialog):
    TITLE = "مصرّف الأفعال"
    SIZE = (820, 660)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.choices = []
        self.table = None
        self.add_text("اكتب أيّ فعل عربي في الماضي، مشكولًا أو غير مشكول، فتسمع تصريفه مع كل الضمائر في اثني عشر زمنًا. "
                      "التصريف بمكتبة قطرب المفتوحة لطه زروقي، وباب الفعل الثلاثي من معجم عرموز.")
        self.verb = self.add_entry("الفعل (Enter للتصريف)", on_enter=self._find)
        self.babList = self.add_list("الفعل المقصود (إن كان له أكثر من باب)", [], height=60, on_select=self._conjugate)
        self.tenseChoice = self.add_choice("الزمن", cj.TENSES, 1, on_change=self._show)
        self.out = self.add_output("التصريف", height=200)
        self.add_buttons([("صرّف", self._find)], close=False)
        self.quizPrompt = self.add_text("")
        self.quizList = self.add_list("التدريب: اختر الصيغة ثم Enter", [], height=90)
        self.quiz = ChoiceQuiz(self, self.quizList, self._make_q, prompt_ctrl=self.quizPrompt)
        self.add_buttons([("تدرّب على التصريف", self.quiz.next), ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self.rng = random.Random()
        self.finish(self.verb)
        if not cj.available():
            self._say("مكتبة التصريف غير موجودة في هذه النسخة.")

    def instructions(self) -> str:
        return ("اكتب الفعل واضغط Enter. إن كان للفعل الثلاثي أكثر من باب فاختر الباب من القائمة. "
                "ثم اختر الزمن لتسمع تصريفه، وتنقّل في مربّع التصريف سطرًا سطرًا.")

    def _find(self):
        text = self.verb.GetValue().strip()
        if not text:
            self._say("اكتب فعلًا أوّلًا.")
            return
        self.choices = cj.candidates(text)
        self.babList.Set([c.note for c in self.choices])
        if not self.choices:
            self._say("لم أجد هذا الفعل. اكتبه مشكولًا في الماضي، مثل كَتَبَ.")
            return
        self.babList.SetSelection(0)
        self._conjugate()
        if len(self.choices) > 1:
            self._say(f"للفعل {len(self.choices)} أبواب، اخترت الأوّل. " + self.out.GetValue())

    def _conjugate(self, evt=None):
        i = self.babList.GetSelection()
        if not (0 <= i < len(self.choices)):
            return
        c = self.choices[i]
        self.table = cj.conjugate(c.verb, c.haraka)
        if not self.table:
            self.out.SetValue("")
            self._say("تعذّر تصريف هذا الفعل. تأكّد أنّه فعل ماضٍ صحيح الكتابة.")
            return
        self._show(speak=evt is not None)

    def _show(self, evt=None, speak=True):
        if not self.table:
            return
        tense = cj.TENSES[self.tenseChoice.GetSelection()]
        text = f"{tense}:\n" + cj.table_text(self.table, tense)
        self.out.SetValue(text)
        if speak:
            self._say(text)

    def _make_q(self):
        return cj.make_question(self.rng)

    def on_enter_key(self) -> bool:
        focus = self.FindFocus()
        if focus is self.quizList:
            self.quiz.answer()
            return True
        if focus is self.verb:
            self._find()
            return True
        if focus is self.babList:
            self._conjugate(True)
            return True
        return False
