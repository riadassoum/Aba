# -*- coding: utf-8 -*-
"""
abaAcademy.gui.english_pron_view
================================

دليل النطق الإنجليزي — type an English word to hear how it is pronounced
(an Arabic-letter approximation, the IPA, syllables and stress, sounds that
Arabic lacks, silent letters), hear the word alone, find rhymes, and practise rhyme, stress and syllable quizzes.
Data from the CMU Pronouncing Dictionary.
"""

from __future__ import annotations

import random

from .. import english_pron as ep
from .tool_base import ChoiceQuiz, ToolDialog


class EnglishPronDialog(ToolDialog):
    TITLE = "دليل النطق الإنجليزي"
    SIZE = (800, 640)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.rng = random.Random()
        self.add_text(f"نطق {len(ep.load())} كلمة إنجليزية من قاموس جامعة كارنيغي ميلون للنطق: تقريب بالحروف العربية، "
                      "والرموز الصوتية الدولية، وعدد المقاطع وموضع النبر، والأصوات التي ليست في العربية، والحروف "
                      "التي تُكتب ولا تُنطق، والكلمات التي تقافيها.")
        self.word = self.add_entry("الكلمة الإنجليزية (Enter)", on_enter=self._show)
        self.out = self.add_output("النطق", height=100)
        self.rhymeList = self.add_list("كلمات تقافيها", [], height=110,
                                       on_activate=lambda: self._pick(self.rhymeList.GetStringSelection()))
        self.kind = self.add_choice("نوع الاختبار", [k for k, _ in ep.QUIZ_KINDS], 0)
        self.prompt = self.add_text("")
        self.quizList = self.add_list("الاختبار: اختر ثم Enter", [], height=90)
        self.quiz = ChoiceQuiz(self, self.quizList, self._make, prompt_ctrl=self.prompt)
        self.add_buttons([("انطق", self._show), ("اسمع الكلمة وحدها", self._hear),
                          ("ابدأ الاختبار", self.quiz.next), ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self.finish(self.word)

    def instructions(self) -> str:
        return ("اكتب الكلمة واضغط Enter فتسمع وصف نطقها، وفي القائمة كلمات تقافيها؛ Enter على إحداها يعرض نطقها. "
                "التقريب بالحروف العربية تقريب فقط، والرموز الصوتية هي الدقيقة.")

    def _make(self):
        return ep.make_question(ep.QUIZ_KINDS[self.kind.GetSelection()][1], self.rng)

    def _pick(self, w):
        if w:
            self.word.SetValue(w)
            self._show()

    def _show(self):
        p = ep.lookup(self.word.GetValue())
        if not p:
            self._say("الكلمة ليست في القاموس.")
            return
        d = p.describe()
        self.out.SetValue(d)
        rs = ep.rhymes(p.word, 40)
        self.rhymeList.Set(rs)
        if rs:
            self.select_index(self.rhymeList, 0)
        self._say(d + (f" تقافيها {len(rs)} كلمة منها {'، '.join(rs[:5])}." if rs else ""))

    def _hear(self):
        w = self.word.GetValue().strip()
        if not w:
            return
        self._say(w)

    def on_enter_key(self) -> bool:
        f = self.FindFocus()
        if f is self.quizList:
            self.quiz.answer()
            return True
        if f is self.rhymeList:
            self._pick(self.rhymeList.GetStringSelection())
            return True
        return False
