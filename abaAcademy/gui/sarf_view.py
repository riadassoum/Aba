# -*- coding: utf-8 -*-
"""
abaAcademy.gui.sarf_view
========================

مختبر الصرف — look up any Arabic word (root, pattern, kind, source verb,
plural and meaning), list the family of a root, and practise broken plurals,
masdars, active participles, the present tense by bab, and transitivity.
Data: the Arramooz dictionary (GPL).
"""

from __future__ import annotations

import random

from ..arabic_lab import sarf as sf
from .tool_base import ChoiceQuiz, ToolDialog


class SarfDialog(ToolDialog):
    TITLE = "مختبر الصرف والمعجم"
    SIZE = (840, 680)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.s = sf.Sarf.get()
        self.trainer = None
        self.add_text(f"معجم صرفي فيه نحو {len(self.s.words) // 1000} ألف اسم و{len(self.s.verbs) // 1000} آلاف فعل "
                      "من معجم عرموز المفتوح لطه زروقي: اكتب كلمة لتعرف جذرها ووزنها ونوعها وجمعها ومعناها، "
                      "أو اكتب جذرًا لترى أسرته، وتدرّب على الجموع والمصادر والمشتقّات.")
        self.word = self.add_entry("الكلمة (Enter للبحث)", on_enter=self._lookup)
        self.root = self.add_entry("الجذر، مثل ك ت ب (Enter لعرض أسرته)", on_enter=self._family)
        self.out = self.add_output("النتيجة", height=170)
        self.add_buttons([("ابحث عن الكلمة", self._lookup), ("أسرة الجذر", self._family)], close=False)
        self.kindChoice = self.add_choice("نوع التدريب", ["منوّع"] + [k[1] for k in sf.KINDS], 0)
        self.quizPrompt = self.add_text("")
        self.quizList = self.add_list("التدريب: اختر الإجابة ثم Enter", [], height=100)
        self.quiz = ChoiceQuiz(self, self.quizList, self._make_q, prompt_ctrl=self.quizPrompt)
        self.add_buttons([("ابدأ التدريب", self.quiz.next), ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self.finish(self.word)

    def instructions(self) -> str:
        return ("اكتب الكلمة واضغط Enter لتسمع كل ما في المعجم عنها، أو اكتب الجذر في الحقل الثاني لتسمع الأفعال "
                "والأسماء المشتقّة منه. اختر نوع التدريب ثم ابدأ، واختر الإجابة بالأسهم ثم Enter.")

    def _lookup(self):
        q = self.word.GetValue().strip()
        if not q:
            self._say("اكتب كلمة أوّلًا.")
            return
        found = self.s.lookup(q)
        text = "\n\n".join(found) if found else f"لم أجد {q} في المعجم. جرّب الكلمة دون ال أو دون الضمائر المتّصلة."
        self.out.SetValue(text)
        self._say(text)

    def _family(self):
        q = self.root.GetValue().strip()
        if not q:
            self._say("اكتب الجذر أوّلًا.")
            return
        fam = self.s.root_family(q)
        text = (f"أسرة الجذر {q}: {len(fam)} كلمة.\n" + "، ".join(fam)) if fam else f"لم أجد الجذر {q}."
        self.out.SetValue(text)
        self._say(text)

    def _make_q(self):
        if self.trainer is None:
            self.trainer = sf.Trainer(self.s, random.Random())
        i = self.kindChoice.GetSelection()
        return self.trainer.question(None if i <= 0 else sf.KINDS[i - 1][0])

    def on_enter_key(self) -> bool:
        focus = self.FindFocus()
        if focus is self.quizList:
            self.quiz.answer()
            return True
        if focus is self.word:
            self._lookup()
            return True
        if focus is self.root:
            self._family()
            return True
        return False
