# -*- coding: utf-8 -*-
"""
abaAcademy.gui.tajweed_view
===========================

معلّم التجويد — pick a surah and an ayah and hear every tajweed rule in it,
word by word; study each rule with its definition and real examples from the
mushaf; then test yourself with a quiz drawn from verified annotations.
"""

from __future__ import annotations

import random

from .. import tajweed as tjm
from .tool_base import ChoiceQuiz, ToolDialog


class TajweedDialog(ToolDialog):
    TITLE = "معلّم التجويد"
    SIZE = (860, 680)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.tj = tjm.Tajweed.get()
        self.rng = random.Random()
        self.add_text("اختر سورة وآية لتسمع أحكام التجويد فيها كلمة كلمة (رواية حفص عن عاصم). "
                      + tjm.SOURCE)
        names = [f"{n}. {self.tj.surah_name(n)}" for n in range(1, 115)]
        self.surahChoice = self.add_choice("السورة", names, 0, on_change=self._fill_ayat)
        self.ayahList = self.add_list("الآيات", [], height=120, on_select=self._show_ayah,
                                      on_activate=self._show_ayah)
        self.out = self.add_output("أحكام الآية", height=150)
        self.add_buttons([("أحكام السورة كلّها", self._surah_counts)], close=False)
        rules = []
        self._rule_keys = []
        for group, keys in tjm.GROUPS:
            for k in keys:
                rules.append(f"{group}: {tjm.rule_name(k)}")
                self._rule_keys.append(k)
        self.ruleList = self.add_list("الأحكام (Enter لشرح الحكم وأمثلة من المصحف)", rules, height=110,
                                      on_activate=self._explain_rule)
        self.quizPrompt = self.add_text("")
        self.quizList = self.add_list("الاختبار: اختر الحكم ثم Enter", [], height=90)
        self.quiz = ChoiceQuiz(self, self.quizList, self._make_q, prompt_ctrl=self.quizPrompt)
        self.add_buttons([("اختبرني في هذه السورة", self._quiz_surah), ("اختبرني في القرآن كلّه", self._quiz_all),
                          ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self._quiz_scope = None
        self.finish(self.surahChoice)
        self._fill_ayat()

    def instructions(self) -> str:
        return ("اختر السورة ثم الآية بالأسهم لتسمع أحكامها. في قائمة الأحكام اضغط Enter على أيّ حكم لتسمع "
                "تعريفه وأمثلة عليه من السورة المختارة. أزرار الاختبار تسألك عن حكم كلمة من آية حقيقية.")

    def _surah(self) -> int:
        return self.surahChoice.GetSelection() + 1

    def _fill_ayat(self, evt=None):
        s = self._surah()
        items = []
        for a in range(1, self.tj.ayah_count(s) + 1):
            mark = "" if self.tj.verified(s, a) else " (دون علامات محقّقة)"
            items.append(f"الآية {a}{mark}")
        self.ayahList.Set(items)
        if items:
            self.ayahList.SetSelection(0)
            self._show_ayah(speak=False)

    def _show_ayah(self, evt=None, speak=True):
        a = self.ayahList.GetSelection() + 1
        if a <= 0:
            return
        text = self.tj.describe_ayah(self._surah(), a)
        self.out.SetValue(text)
        if speak:
            self._say(text)

    def _surah_counts(self):
        s = self._surah()
        c = self.tj.counts(s)
        if not c:
            self._say("لا توجد علامات محقّقة لهذه السورة.")
            return
        parts = [f"{tjm.rule_name(r)}: {n}" for r, n in sorted(c.items(), key=lambda x: -x[1])]
        text = f"أحكام سورة {self.tj.surah_name(s)}:\n" + "\n".join(parts)
        self.out.SetValue(text)
        self._say(text)

    def _explain_rule(self, evt=None):
        i = self.ruleList.GetSelection()
        if i < 0:
            return
        rule = self._rule_keys[i]
        lines = [tjm.rule_text(rule)]
        ex = self.tj.examples(rule, 4, surah=self._surah(), rng=self.rng) or self.tj.examples(rule, 4, rng=self.rng)
        if ex:
            lines.append("أمثلة من المصحف:")
            for s, a, m in ex:
                lines.append(f"كلمة {tjm.bare(m.word)}، سورة {self.tj.surah_name(s)} الآية {a}")
        text = "\n".join(lines)
        self.out.SetValue(text)
        self._say(text)

    def _make_q(self):
        return tjm.make_question(self.tj, surah=self._quiz_scope, rng=self.rng)

    def _quiz_surah(self):
        self._quiz_scope = self._surah()
        self.quiz.next()

    def _quiz_all(self):
        self._quiz_scope = None
        self.quiz.next()

    def on_enter_key(self) -> bool:
        focus = self.FindFocus()
        if focus is self.quizList:
            self.quiz.answer()
            return True
        if focus is self.ruleList:
            self._explain_rule()
            return True
        if focus is self.ayahList:
            self._show_ayah()
            return True
        return False
