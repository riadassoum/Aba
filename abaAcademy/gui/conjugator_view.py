# -*- coding: utf-8 -*-
"""
abaAcademy.gui.conjugator_view
==============================

The verb-conjugation screen. The learner types a triliteral verb (past 3rd-person
form, e.g. كَتَبَ / نَصَرَ), chooses a tense, and hears the full table across the
pronouns. For the sound verb the table is complete and correct; for the irregular
families (أجوف، ناقص، مثال، مضعّف، مهموز) the screen says honestly that the type
isn't supported yet rather than showing a form that might be wrong — because a
wrong صرف form would mislead the learner.
"""

from __future__ import annotations

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..arabic_lab import conjugator as cj


class ConjugatorDialog(AccessibleDialog):
    TITLE = "مصرّف الأفعال"

    TENSES = [("الماضي", "past"), ("المضارع", "present"), ("الأمر", "imperative")]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(700, 560))
        self.academy = academy

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "اكتب فعلاً ثلاثياً في صيغة الماضي للغائب (مثل: كتب، نصر، جلس)، اختر الزمن، "
            "ثم «صرّف». ملاحظة صادقة: التصريف الكامل مدعوم للأفعال الصحيحة السالمة؛ أمّا "
            "المعتلّة والمهموزة والمضعّفة فتحتاج معالجة خاصة لم تُضَف بعد، ولن نعرض لها "
            "صيغاً قد تكون خاطئة.")), 0, wx.ALL, 6)

        vrow = wx.BoxSizer(wx.HORIZONTAL)
        vrow.Add(wx.StaticText(panel, label="الفعل:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.verbEntry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.verbEntry.SetName("الفعل")
        self.verbEntry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._conjugate())
        vrow.Add(self.verbEntry, 1, wx.RIGHT, 8)
        vrow.Add(wx.StaticText(panel, label="الزمن:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.tenseChoice = wx.Choice(panel, choices=[n for n, _ in self.TENSES])
        self.tenseChoice.SetSelection(0)
        self.bind_choice(self.tenseChoice, lambda e: self._conjugate() if self.verbEntry.GetValue().strip() else None)
        vrow.Add(self.tenseChoice, 0)
        s.Add(vrow, 0, wx.EXPAND | wx.ALL, 6)

        self.table = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.table.SetName("جدول التصريف")
        s.Add(self.table, 1, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(660)
        s.Add(self.status, 0, wx.ALL, 6)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "صرّف (Enter)", lambda e: self._conjugate()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "نوع الفعل", lambda e: self._say_type()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.verbEntry)

    def _verb(self):
        # keep only Arabic letters (drop any harakat the user typed)
        raw = self.verbEntry.GetValue().strip()
        return "".join(c for c in raw if c not in "ًٌٍَُِّْ").strip()

    def _conjugate(self):
        verb = self._verb()
        if len(verb) != 3:
            self._say("اكتب فعلاً ثلاثياً (ثلاثة أحرف).")
            return
        tense = self.TENSES[self.choice_index(self.tenseChoice)][1]
        try:
            table = cj.conjugate(verb, tense)
        except ValueError as exc:
            self.table.Clear()
            self._say(str(exc))
            return
        self.table.Set([f"{pr}: {form}" for pr, form in table])
        self.select_index(self.table, 0)
        tense_name = self.TENSES[self.choice_index(self.tenseChoice)][0]
        # speak the first few then let the user arrow through
        preview = "، ".join(f"{pr} {form}" for pr, form in table[:3])
        self._say(f"تصريف «{verb}» في {tense_name}: {preview}… "
                  f"تنقّل في القائمة بالأسهم لسماع البقية.")
        self.table.SetFocus()

    def _say_type(self):
        verb = self._verb()
        if len(verb) != 3:
            self._say("اكتب فعلاً ثلاثياً أولاً.")
            return
        _, name = cj.classify(verb)
        self._say(f"نوع الفعل «{verb}»: {name}.")

    def _say(self, text):
        self.status.SetLabel(text[:200])
        self.announce(text)

    def instructions(self):
        return ("مصرّف الأفعال: اكتب فعلاً ثلاثياً في صيغة ماضي الغائب (كتب، نصر…)، اختر "
                "الزمن (الماضي، المضارع، الأمر)، ثم «صرّف» لتسمع الجدول عبر الضمائر، وتنقّل "
                "فيه بالأسهم. «نوع الفعل» يخبرك بنوعه. التصريف مدعوم للأفعال الصحيحة السالمة؛ "
                "المعتلّة والمهموزة والمضعّفة غير مدعومة بعد تفاديًا لعرض صيغ خاطئة. Escape للإغلاق.")
