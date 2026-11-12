# -*- coding: utf-8 -*-
"""
abaAcademy.gui.spelling_view
============================

The Arabic orthography clinic. The learner picks a category (hamzat al-wasl/qat',
hamza seat, alif maqsura/ya', ta' marbuta/ha') or all, hears/reads the word to
spell, types it, and gets immediate feedback with the exact rule when wrong.
Built on ``arabic_lab.spelling_trainer``.

Because a screen reader reads the correct and the wrong spelling almost the same
(the difference is often a hamza or a dotted/undotted final letter), the drill
announces the word to spell by its *meaning/context* and the learner types it,
then hears letter-by-letter confirmation of the correct form.
"""

from __future__ import annotations

import random

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..arabic_lab import spelling_trainer as st


def _spell_out(word):
    """Letter-by-letter Arabic reading so the exact spelling is unambiguous."""
    return " ".join(word)


class SpellingDialog(AccessibleDialog):
    TITLE = "مختبر الإملاء والهمزات"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(700, 520))
        self.academy = academy
        self._rng = random.Random()
        self._item = None
        self._score = 0
        self._asked = 0

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "تدرّب على الإملاء الصعب. اختر الباب، سيُعرض عليك الخيار الصحيح والخاطئ "
            "لتختار، أو اكتب الكلمة الصحيحة. عند الخطأ تُشرح القاعدة.")),
            0, wx.ALL, 6)

        crow = wx.BoxSizer(wx.HORIZONTAL)
        crow.Add(wx.StaticText(panel, label="الباب:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self._cats = [("all", "الكل")] + st.categories()
        self.catChoice = wx.Choice(panel, choices=[n for _, n in self._cats])
        self.catChoice.SetSelection(0)
        self.bind_choice(self.catChoice, lambda e: self._new_question())
        crow.Add(self.catChoice, 0)
        s.Add(crow, 0, wx.ALL, 6)

        self.prompt = wx.StaticText(panel, label="")
        self.prompt.Wrap(660)
        s.Add(self.prompt, 0, wx.ALL, 8)

        # two-choice buttons (correct vs wrong), positions randomised
        self.choiceBox = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.choiceBox.SetName("الخيارات")
        self.choiceBox.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._answer_choice())
        s.Add(self.choiceBox, 1, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(660)
        s.Add(self.status, 0, wx.ALL, 6)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "اختر (Enter)", lambda e: self._answer_choice()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "اقرأ القاعدة", lambda e: self._read_rule()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "سؤال جديد", lambda e: self._new_question()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.catChoice)
        self.call_after(self._new_question)

    def _new_question(self):
        cat = self._cats[self.catChoice.GetSelection()][0]
        pool = st.items_for(cat)
        if not pool:
            self._say("لا عناصر في هذا الباب.")
            return
        self._item = self._rng.choice(pool)
        # present the two spellings in random order
        opts = [self._item.correct, self._item.wrong]
        self._rng.shuffle(opts)
        self._options = opts
        self.choiceBox.Set([_spell_out(o) + f"   ({o})" for o in opts])
        self.choiceBox.SetSelection(0)
        cat_name = dict(st.categories()).get(self._item.category, "")
        self.prompt.SetLabel(f"[{cat_name}] أيّ الكتابتين صحيحة؟")
        self._say(f"في باب {cat_name}: أيّ الكتابتين صحيحة؟ "
                  f"الأولى: {_spell_out(opts[0])}. الثانية: {_spell_out(opts[1])}. "
                  f"اختر بالأسهم واضغط Enter.")

    def _answer_choice(self):
        if not self._item:
            return
        i = self.choiceBox.GetSelection()
        if i < 0:
            return
        chosen = self._options[i]
        self._asked += 1
        if chosen == self._item.correct:
            self._score += 1
            self._say(f"صحيح! {self._item.correct}. {self._item.rule} "
                      f"نتيجتك {self._score} من {self._asked}.")
            self.call_later(1200, self._new_question)
        else:
            self._say(f"غير صحيح. الصواب {self._item.correct}. "
                      f"القاعدة: {self._item.rule}")

    def _read_rule(self):
        if self._item:
            self._say("القاعدة: " + self._item.rule)

    def _say(self, text):
        self.status.SetLabel(text[:200])
        self.announce(text)

    def instructions(self):
        return ("مختبر الإملاء: اختر الباب (همزة الوصل والقطع، الهمزة المتوسطة والمتطرفة، "
                "الألف المقصورة والياء، التاء المربوطة والهاء، أو الكل). تُعرض كتابتان، "
                "تُقرأ كل منهما حرفًا حرفًا، اختر الصحيحة بالأسهم واضغط Enter. عند الخطأ "
                "تُشرح القاعدة. اقرأ القاعدة يعيد شرح القاعدة. Escape للإغلاق.")
