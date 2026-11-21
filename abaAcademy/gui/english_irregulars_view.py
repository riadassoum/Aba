# -*- coding: utf-8 -*-
"""
abaAcademy.gui.english_irregulars_view
======================================

الأفعال والجموع الشاذّة في الإنجليزية — browse the irregular verbs a
learner meets most, hear the three forms with the Arabic meaning and an
example sentence, and drill the past and past participle and irregular
plurals.
"""

from __future__ import annotations

import random

from .. import english_irregulars as ei
from .tool_base import ChoiceQuiz, ToolDialog


class EnglishIrregularsDialog(ToolDialog):
    TITLE = "الأفعال والجموع الشاذّة في الإنجليزية"
    SIZE = (780, 620)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        d = ei.data()
        self.verbs, self.nouns = d["verbs"], d["nouns"]
        self.rng = random.Random()
        self.add_text(f"{len(self.verbs)} فعلًا شاذًّا و{len(self.nouns)} جمعًا شاذًّا مرتّبة بكثرة ورودها في جمل الأكاديمية: "
                      "الماضي واسم المفعول والمعنى ومثال من بنك الجمل.")
        self.kindChoice = self.add_choice("القائمة", ["الأفعال الشاذّة", "الجموع الشاذّة"], 0, on_change=self._fill)
        self.list = self.add_list("الكلمات (تنقّل بالأسهم، Enter لمثال)", [], height=180, on_select=self._show,
                                  on_activate=self._example)
        self.out = self.add_output("التفاصيل", height=90)
        self.quizPrompt = self.add_text("")
        self.quizList = self.add_list("التدريب: اختر ثم Enter", [], height=90)
        self.quiz = ChoiceQuiz(self, self.quizList, lambda: ei.make_question(self.rng), prompt_ctrl=self.quizPrompt)
        self.add_buttons([("تدرّب", self.quiz.next), ("مثال من الجمل", self._example),
                          ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self.finish(self.list)
        self._fill()

    def instructions(self) -> str:
        return ("تنقّل في القائمة بالأسهم لتسمع صيغ الفعل ومعناه، واضغط Enter لتسمع مثالًا من بنك الجمل. "
                "زرّ تدرّب يسألك عن الماضي أو اسم المفعول أو الجمع.")

    def _rows(self):
        return self.verbs if self.kindChoice.GetSelection() == 0 else self.nouns

    def _fill(self, evt=None):
        rows = self._rows()
        if self.kindChoice.GetSelection() == 0:
            self.list.Set([f"{v['base']}، {v['past']}، {v['part']}" for v in rows])
        else:
            self.list.Set([f"{n['sing']}، {n['pl']}" for n in rows])
        if rows:
            self.list.SetSelection(0)
            self._show(speak=False)

    def _current(self):
        i = self.list.GetSelection()
        rows = self._rows()
        return rows[i] if 0 <= i < len(rows) else None

    def _show(self, evt=None, speak=True):
        r = self._current()
        if not r:
            return
        if "base" in r:
            text = ei.describe_verb(r)
        else:
            m = ei.meaning(r["sing"])
            text = f"{r['sing']}، والجمع {r['pl']}" + (f". المعنى: {m}." if m else ".")
        self.out.SetValue(text)
        if speak and evt is None:
            self._say(text)

    def _example(self, evt=None):
        r = self._current()
        if not r:
            return
        forms = [r["base"], *r["past"].split(" أو "), *r["part"].split(" أو ")] if "base" in r else [r["pl"], r["sing"]]
        ex = ei.example(*forms)
        self._say(ex or "لا يوجد مثال لهذه الكلمة في بنك الجمل.")

    def on_enter_key(self) -> bool:
        focus = self.FindFocus()
        if focus is self.quizList:
            self.quiz.answer()
            return True
        if focus is self.list:
            self._example()
            return True
        return False
