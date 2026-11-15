# -*- coding: utf-8 -*-
"""
abaAcademy.gui.quran_morph_view
===============================

صرف القرآن كلمة كلمة — choose a surah and an ayah, move through its words and
hear each one's parts, part of speech, root, lemma and grammar; search a
root to hear where and how often it occurs; quiz on roots and word kinds.
Data: the Quranic Arabic Corpus (GPL).
"""

from __future__ import annotations

import random

from .. import quran_morph as qm
from .tool_base import ChoiceQuiz, ToolDialog


class QuranMorphDialog(ToolDialog):
    TITLE = "صرف القرآن كلمة كلمة"
    SIZE = (860, 700)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.m = qm.Morphology.get()
        self.rng = random.Random()
        self.add_text(f"تحليل صرفي لكل كلمات القرآن الكريم ({len(self.m.words)} كلمة و{len(self.m.by_root)} جذرًا) "
                      "من مدوّنة القرآن العربية: نوع الكلمة وجذرها وأصلها وإعرابها وزمنها وضميرها ووزنها.")
        self.surahChoice = self.add_choice("السورة", [f"{n}. {self.m.surah_name(n)}" for n in range(1, 115)], 0,
                                           on_change=self._fill_ayat)
        self.ayahChoice = self.add_choice("الآية", ["1"], 0, on_change=self._fill_words)
        self.wordList = self.add_list("كلمات الآية (تنقّل بالأسهم)", [], height=130, on_select=self._show_word)
        self.out = self.add_output("التحليل", height=130)
        self.rootEntry = self.add_entry("ابحث عن جذر، مثل ر ح م (Enter)", on_enter=self._root)
        self.add_buttons([("مواضع الجذر", self._root), ("مواضع جذر الكلمة المحدّدة", self._word_root)], close=False)
        self.kindChoice = self.add_choice("نوع الاختبار", ["جذر الكلمة", "نوع الكلمة"], 0)
        self.quizPrompt = self.add_text("")
        self.quizList = self.add_list("الاختبار: اختر الإجابة ثم Enter", [], height=80)
        self.quiz = ChoiceQuiz(self, self.quizList, self._make_q, prompt_ctrl=self.quizPrompt)
        self.add_buttons([("اختبرني في هذه السورة", lambda: self._quiz(True)),
                          ("اختبرني في القرآن كله", lambda: self._quiz(False)),
                          ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self._scope = None
        self.finish(self.surahChoice)
        self._fill_ayat()

    def instructions(self) -> str:
        return ("اختر السورة والآية، ثم انتقل إلى قائمة الكلمات وتنقّل بالأسهم لتسمع تحليل كل كلمة. "
                "اكتب جذرًا واضغط Enter لتسمع عدد وروده وصيغه ومواضعه.")

    def _surah(self) -> int:
        return self.surahChoice.GetSelection() + 1

    def _fill_ayat(self, evt=None):
        n = int(self.m.surahs[self._surah() - 1]["count"])
        self.ayahChoice.Set([str(i) for i in range(1, n + 1)])
        self.ayahChoice.SetSelection(0)
        self._fill_words()

    def _fill_words(self, evt=None):
        a = self.ayahChoice.GetSelection() + 1
        self.words = self.m.by_ayah.get((self._surah(), a), [])
        self.wordList.Set([qm.plain(w.text) for w in self.words])
        if self.words:
            self.wordList.SetSelection(0)
            self._show_word(speak=False)

    def _current(self):
        i = self.wordList.GetSelection()
        return self.words[i] if 0 <= i < len(self.words) else None

    def _show_word(self, evt=None, speak=True):
        w = self._current()
        if w:
            text = self.m.describe_word(w)
            self.out.SetValue(text)
            if speak and evt is None:
                self._say(text)

    def _root(self):
        r = self.rootEntry.GetValue().strip()
        if not r:
            self._say("اكتب الجذر أوّلًا.")
            return
        text = self.m.root_report(r)
        self.out.SetValue(text)
        self._say(text.split("\n")[0])

    def _word_root(self):
        w = self._current()
        if w and w.root:
            self.rootEntry.SetValue(" ".join(w.root))
            self._root()
        else:
            self._say("ليس لهذه الكلمة جذر في المدوّنة.")

    def _make_q(self):
        kind = "root" if self.kindChoice.GetSelection() == 0 else "pos"
        return qm.make_question(self.m, kind, self._scope, self.rng)

    def _quiz(self, this_surah: bool):
        self._scope = self._surah() if this_surah else None
        self.quiz.next()

    def on_enter_key(self) -> bool:
        focus = self.FindFocus()
        if focus is self.quizList:
            self.quiz.answer()
            return True
        if focus is self.rootEntry:
            self._root()
            return True
        if focus is self.wordList:
            self._show_word()
            return True
        return False
