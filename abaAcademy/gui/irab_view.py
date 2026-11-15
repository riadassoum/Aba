# -*- coding: utf-8 -*-
"""
abaAcademy.gui.irab_view
========================

مدرّب الإعراب — a word from a real ayah, and the learner chooses its i'rab;
the book's full parsing is read after each answer. Questions can come from
the whole Qur'an or one surah, and can focus on one role.
"""

from __future__ import annotations

import random

from ..arabic_lab import irab as ir
from .tool_base import ChoiceQuiz, ToolDialog


class IrabDialog(ToolDialog):
    TITLE = "مدرّب الإعراب"
    SIZE = (840, 600)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.ir = ir.Irab.get()
        self.rng = random.Random()
        self.add_text(f"تدرّب على الإعراب بكلمات القرآن الكريم: {len(self.ir.items)} موضعًا من كتاب إعراب القرآن "
                      "الموجود في الأكاديمية. تسمع الآية والكلمة وتختار إعرابها، ثم تسمع إعراب الكتاب كاملًا.")
        self.surahChoice = self.add_choice("السورة", ["القرآن كله"] + [f"{n}. {self.ir.surah_name(n)}" for n in range(1, 115)], 0)
        counts = self.ir.counts()
        self._roles = [None] + sorted(counts, key=lambda r: -counts[r])
        self.roleChoice = self.add_choice("التركيز على", ["كل المواقع"] + [f"{r} ({counts[r]})" for r in self._roles[1:]], 0)
        self.quizPrompt = self.add_text("")
        self.quizList = self.add_list("اختر الإعراب ثم Enter", [], height=110)
        self.quiz = ChoiceQuiz(self, self.quizList, self._make_q, prompt_ctrl=self.quizPrompt)
        self.add_buttons([("سؤال جديد", self.quiz.next), ("أعد السؤال", self.quiz.repeat),
                          ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self.finish(self.surahChoice)

    def instructions(self) -> str:
        return ("اختر السورة أو القرآن كله، وموقعًا إعرابيًّا إن أردت التركيز عليه، ثم اضغط سؤال جديد. "
                "اختر الإجابة بالأسهم واضغط Enter، ثم Enter مرّة أخرى للسؤال التالي.")

    def _make_q(self):
        i = self.surahChoice.GetSelection()
        return ir.make_question(self.ir, None if i <= 0 else i, self._roles[self.roleChoice.GetSelection()], self.rng)

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.quizList:
            self.quiz.answer()
            return True
        return False
