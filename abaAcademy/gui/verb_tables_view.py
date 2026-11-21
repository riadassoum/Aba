# -*- coding: utf-8 -*-
"""
abaAcademy.gui.verb_tables_view
===============================

تصريف الأفعال الأجنبية — type a French, Spanish or Italian verb and hear it
conjugated with every person in any simple tense, with its English meaning
where known; practise with a drill on the most frequent verbs.
Data: verbecc / Verbiste (LGPL / GPL).
"""

from __future__ import annotations

import random

from .. import verb_tables as vt
from .tool_base import ChoiceQuiz, ToolDialog

LANG_KEYS = list(vt.LANGS)


class VerbTablesDialog(ToolDialog):
    TITLE = "تصريف الأفعال الفرنسية والإسبانية والإيطالية"
    SIZE = (820, 640)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.rng = random.Random()
        self.add_text("اكتب فعلًا في المصدر (مثل aller أو tener أو essere) فتسمع تصريفه مع كل الضمائر في الأزمنة "
                      "البسيطة. نحو أربعة وعشرين ألف فعل من مشروعي verbecc وVerbiste المفتوحين.")
        self.langChoice = self.add_choice("اللغة", [vt.LANGS[k] for k in LANG_KEYS], 0, on_change=self._lang_changed)
        self.verb = self.add_entry("الفعل في المصدر (Enter)", on_enter=self._show)
        self.tenseChoice = self.add_choice("الزمن", [], 0, on_change=lambda e=None: self._show())
        self.out = self.add_output("التصريف", height=170)
        self.commonList = self.add_list("أكثر الأفعال استعمالًا (Enter لعرض تصريفه)", [], height=110,
                                        on_activate=self._pick_common)
        self.quizPrompt = self.add_text("")
        self.quizList = self.add_list("التدريب: اختر الصيغة ثم Enter", [], height=90)
        self.quiz = ChoiceQuiz(self, self.quizList, self._make_q, prompt_ctrl=self.quizPrompt)
        self.add_buttons([("صرّف", self._show), ("تدرّب", self.quiz.next),
                          ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self.finish(self.verb)
        self._lang_changed()

    def instructions(self) -> str:
        return ("اختر اللغة واكتب الفعل في المصدر واضغط Enter، ثم اختر الزمن لتسمع تصريفه. "
                "أو اختر فعلًا من قائمة الأفعال الشائعة. زرّ تدرّب يسألك عن صيغة الفعل مع ضمير.")

    def _lang(self) -> str:
        return LANG_KEYS[self.langChoice.GetSelection()]

    def _lang_changed(self, evt=None):
        lang = self._lang()
        self._tenses = vt.tenses(lang)
        self.tenseChoice.Set([vt.TENSE_NAMES[t] for t in self._tenses])
        if self._tenses:
            self.tenseChoice.SetSelection(0)
        self._common = vt.common(lang, 200)
        self.commonList.Set([f"{v} ({vt.english(lang, v)})" if vt.english(lang, v) else v for v in self._common])

    def _show(self, evt=None):
        verb = self.verb.GetValue().strip()
        if not verb:
            self._say("اكتب فعلًا أوّلًا.")
            return
        lang = self._lang()
        if vt.conjugate(lang, verb) is None:
            self._say(f"لم أجد الفعل {verb} في أفعال {vt.LANGS[lang]}. اكتبه في المصدر.")
            return
        i = self.tenseChoice.GetSelection()
        tense = self._tenses[i] if 0 <= i < len(self._tenses) else self._tenses[0]
        meaning = vt.english(lang, verb)
        head = f"{verb}" + (f" ({meaning})" if meaning else "") + f"، {vt.TENSE_NAMES[tense]}:"
        text = head + "\n" + vt.table_text(lang, verb, tense)
        self.out.SetValue(text)
        self._say(text)

    def _pick_common(self, evt=None):
        i = self.commonList.GetSelection()
        if 0 <= i < len(self._common):
            self.verb.SetValue(self._common[i])
            self._show()

    def _make_q(self):
        return vt.make_question(self._lang(), self.rng)

    def on_enter_key(self) -> bool:
        focus = self.FindFocus()
        if focus is self.quizList:
            self.quiz.answer()
            return True
        if focus is self.verb:
            self._show()
            return True
        if focus is self.commonList:
            self._pick_common()
            return True
        return False
