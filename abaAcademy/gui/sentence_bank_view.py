# -*- coding: utf-8 -*-
"""
abaAcademy.gui.sentence_bank_view
=================================

بنك الجمل — about 120,000 real sentence pairs between Arabic and six
languages from Tatoeba (CC BY 2.0 FR). Search a word in either language and
hear how it is used, with the translation; or practise: hear a sentence and
choose its meaning.
"""

from __future__ import annotations

import os
import random
import re

from .tool_base import ChoiceQuiz, ToolDialog

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(HERE, "resources", "sentences")
LANGS = [("en", "الإنجليزية"), ("fr", "الفرنسية"), ("es", "الإسبانية"), ("de", "الألمانية"),
         ("it", "الإيطالية"), ("tr", "التركية")]
HARAKAT = re.compile("[ً-ْ]")
_cache = {}


def load(lang: str):
    if lang not in _cache:
        rows = []
        p = os.path.join(DIR, f"{lang}.tsv")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                for line in f:
                    a, _, b = line.rstrip("\n").partition("\t")
                    if a and b:
                        rows.append((a, b))
        _cache[lang] = rows
    return _cache[lang]


def search(rows, query: str, limit: int = 200):
    q = query.strip()
    if not q:
        return []
    if re.search("[ء-ي]", q):
        qn = HARAKAT.sub("", q)
        pat = re.compile(r"(^|[\s،.؟!\"'(])(و|ف|ب|ل|ال|وال|بال|فال|لل)?" + re.escape(qn), re.U)
        hits = [r for r in rows if pat.search(HARAKAT.sub("", r[1]))]
    else:
        pat = re.compile(r"\b" + re.escape(q.lower()) + r"\b", re.U)
        hits = [r for r in rows if pat.search(r[0].lower())]
    return hits[:limit]


class Question:
    def __init__(self, prompt, options, answer, explanation):
        self.prompt, self.options, self.answer, self.explanation = prompt, options, answer, explanation


class SentenceBankDialog(ToolDialog):
    TITLE = "بنك الجمل"
    SIZE = (840, 660)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.rng = random.Random()
        total = sum(len(load(c)) for c, _ in LANGS)
        self.add_text(f"{total} جملة حقيقية مترجمة بين العربية وست لغات، من مشروع تتويبا المفتوح. "
                      "ابحث عن كلمة بأيّ اللغتين لتسمع كيف تُستعمل، أو تدرّب على فهم الجمل.")
        self.langChoice = self.add_choice("اللغة", [n for _, n in LANGS], 0, on_change=self._search)
        self.query = self.add_entry("الكلمة (عربية أو أجنبية) ثم Enter", on_enter=self._search)
        self.results = self.add_list("الجمل (تنقّل بالأسهم)", [], height=200, on_select=self._read)
        self.quizPrompt = self.add_text("")
        self.quizList = self.add_list("التدريب: ما معنى الجملة؟ اختر ثم Enter", [], height=100)
        self.quiz = ChoiceQuiz(self, self.quizList, self._make_q, prompt_ctrl=self.quizPrompt)
        self.add_buttons([("ابحث", self._search), ("تدرّب على الفهم", self.quiz.next),
                          ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self.hits = []
        self.finish(self.query)

    def instructions(self) -> str:
        return ("اختر اللغة واكتب كلمة واضغط Enter، ثم تنقّل في الجمل بالأسهم لتسمع كل جملة وترجمتها. "
                "زرّ التدريب يعرض جملة أجنبية وأربع ترجمات تختار الصحيحة منها.")

    def _lang(self):
        return LANGS[self.langChoice.GetSelection()][0]

    def _search(self, evt=None):
        q = self.query.GetValue().strip()
        if not q:
            return
        rows = load(self._lang())
        self.hits = search(rows, q)
        self.results.Set([f"{a} — {b}" for a, b in self.hits])
        if self.hits:
            self.results.SetSelection(0)
            self._say(f"{len(self.hits)} جملة. " + self.hits[0][0] + "، " + self.hits[0][1])
        else:
            self._say(f"لم أجد {q} في جمل {LANGS[self.langChoice.GetSelection()][1]}.")

    def _read(self, evt=None):
        i = self.results.GetSelection()
        if 0 <= i < len(self.hits) and evt is None:
            self._say(f"{self.hits[i][0]}، {self.hits[i][1]}")

    def _make_q(self):
        rows = load(self._lang())
        short = [r for r in rows if 3 <= len(r[0].split()) <= 9]
        if len(short) < 4:
            return None
        right = self.rng.choice(short)
        others = self.rng.sample(short, 3)
        opts = list({o[1] for o in others if o[1] != right[1]})[:3] + [right[1]]
        self.rng.shuffle(opts)
        return Question(f"ما معنى: {right[0]}", opts, right[1], f"{right[0]}: {right[1]}")

    def on_enter_key(self) -> bool:
        focus = self.FindFocus()
        if focus is self.quizList:
            self.quiz.answer()
            return True
        if focus is self.query:
            self._search()
            return True
        if focus is self.results:
            self._read()
            return True
        return False
