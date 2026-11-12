# -*- coding: utf-8 -*-
"""
abaAcademy.gui.roots_view
=========================

The root lab (مختبر الجذور): a word's root and pattern, the Qur'anic words
from the same root, the dictionary words the stemmer groups under it, and a
practice mode (find the root, find the word from a root, find the pattern)
built on the Qur'an's scholar-checked roots.
"""

from __future__ import annotations

import random

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog, ChoiceQuiz
from ..arabic_lab import roots
from ..tools.ar_count import count


class RootsDialog(ToolDialog):
    TITLE = "مختبر الجذور والأوزان"
    SIZE = (780, 680)
    _bank = None
    _index = None

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self._rng = random.Random()
        self.wordEntry = self.add_entry("الكلمة", on_enter=self._analyse,
                                        hint="مثل: مكتبة، يستخرجون، المعلّمون")
        self.add_buttons([("حلّل", self._analyse), ("كلمات من الجذر نفسه", self._family)],
                         close=False)
        self.add_output("التحليل", height=130)
        self._kinds = list(roots.QUESTION_KINDS)
        self.kindChoice = self.add_choice("نوع التدريب", [roots.QUESTION_KINDS[k] for k in self._kinds]
                                          + ["متنوّع"], len(self._kinds))
        self.quizPrompt = self.add_text("التدريب مبنيّ على ألفاظ القرآن الكريم وجذورها المحقّقة.")
        self.options = self.add_list("الخيارات", height=110)
        self.quiz = ChoiceQuiz(self, self.options, self._make_question, prompt_ctrl=self.quizPrompt)
        self.add_buttons([("سؤال جديد", self.quiz.next),
                          ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self.finish(self.wordEntry)
        self._ensure_data()

    # -- data (shared across openings, loaded in the background) ----------
    def _ensure_data(self) -> None:
        cls = type(self)
        if cls._bank is None:
            cls._bank = roots.QuranRootBank(self.resource_path("quran", "word_analysis.json"))
            cls._bank.load_async()
        if cls._index is None:
            cls._index = roots.RootIndex.from_gzip_async(
                self.resource_path("dictionary", "arabic_words.txt.gz"))

    @property
    def bank(self):
        return type(self)._bank

    @property
    def index(self):
        return type(self)._index

    # -- actions ---------------------------------------------------------
    def _analyse(self) -> None:
        word = self.wordEntry.GetValue().strip()
        if not word:
            raise ValueError("اكتب كلمة.")
        if " " in word:
            word = word.split()[0]
        if not self.bank.ready:
            self.bank.wait(3.0)
        a = roots.analyse(word, self.bank)
        self._last = a
        lines = [a.spoken()]
        if a.root and self.bank.ready:
            lem = self.bank.lemmas_of(a.root)[:12]
            if lem:
                lines.append(f"من ألفاظ القرآن على هذا الجذر: {'، '.join(lem)}.")
        self.show_output("\n".join(lines), speak=lines[0])

    def _family(self) -> None:
        a = getattr(self, "_last", None)
        if a is None or a.word != self.wordEntry.GetValue().strip().split(" ")[0]:
            self._analyse()
            a = getattr(self, "_last", None)
        if a is None or not a.root:
            return
        if not self.index.ready:
            self._say("ما زال فهرس المعجم يُبنى، انتظر ثانيتين ثم أعد المحاولة.")
            return
        fam = self.index.family(a.root, 80)
        quran = self.bank.lemmas_of(a.root) if self.bank.ready else []
        lines = [f"الجذر {' '.join(a.root)}:"]
        if quran:
            lines.append(f"في القرآن الكريم ({count(len(quran), 'word')}): {'، '.join(quran[:40])}.")
        if fam:
            lines.append(f"في المعجم ({len(fam)} كلمة على الأقلّ بحسب المجذّع الآلي): "
                         f"{'، '.join(fam[:60])}.")
        self.show_output("\n".join(lines), speak=lines[1] if len(lines) > 1 else lines[0],
                         focus=True)

    def _make_question(self):
        if not self.bank.ready:
            self.bank.wait(3.0)
        k = self.choice_index(self.kindChoice)
        kind = self._kinds[k] if k < len(self._kinds) else None
        return roots.make_question(self.bank, self._rng, kind)

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.options:
            self.quiz.answer()
            return True
        return False

    def instructions(self) -> str:
        return ("اكتب كلمة واضغط Enter لتعرف جذرها ووزنها. الجذور من معجم ألفاظ القرآن حين تكون "
                "الكلمة قرآنية، وإلا فمن مجذّع آليّ قد يخطئ أحيانًا وتُوسم نتيجته بأنها تقريبية. "
                "وفي التدريب اختر نوع السؤال ثم سؤال جديد، واختر الإجابة بالأسهم وEnter.")
