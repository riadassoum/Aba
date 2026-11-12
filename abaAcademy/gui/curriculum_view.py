# -*- coding: utf-8 -*-
"""
abaAcademy.gui.curriculum_view
==============================

A guided Python course from beginner to advanced. The learner moves through
levels (المبتدئ → المتقدّم جدًّا), and within each level through units. Each unit
shows an Arabic lesson and a worked example that can be run on the spot to hear
its output. Units that have practice challenges say so and hand the learner to
the code lab.

Navigation is list-based and fully spoken: choose a level, choose a unit, read
the lesson, run the example, move on. Progress (units marked read) is stored.
"""

from __future__ import annotations

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..codelab.curriculum import all_levels, total_units
from ..codelab.sandbox import run_code
from ..codelab.challenges import get_challenge


class CurriculumDialog(AccessibleDialog):
    TITLE = "دورة البرمجة (من المبتدئ إلى المتقدّم)"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(780, 640))
        self.academy = academy
        self._levels = all_levels()
        self._unit = None

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            f"دورة متكاملة في بايثون عبر {len(self._levels)} مستويات و"
            f"{total_units()} درساً. اختر المستوى ثم الدرس، اقرأ الشرح، وشغّل المثال "
            "لتسمع ناتجه.")), 0, wx.ALL, 6)

        # level + unit choosers
        crow = wx.BoxSizer(wx.HORIZONTAL)
        crow.Add(wx.StaticText(panel, label="المستوى:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.levelChoice = wx.Choice(panel, choices=[lv.title for lv in self._levels])
        self.levelChoice.SetSelection(0)
        self.bind_choice(self.levelChoice, lambda e: self._refresh_units())
        crow.Add(self.levelChoice, 0, wx.RIGHT, 12)
        crow.Add(wx.StaticText(panel, label="الدرس:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.unitChoice = wx.Choice(panel, choices=[])
        self.bind_choice(self.unitChoice, lambda e: self._load_unit())
        crow.Add(self.unitChoice, 1)
        s.Add(crow, 0, wx.EXPAND | wx.ALL, 6)

        # lesson text
        s.Add(wx.StaticText(panel, label="الشرح:"), 0, wx.LEFT, 6)
        self.lesson = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY,
                                  size=(-1, 180))
        self.lesson.SetName("شرح الدرس")
        s.Add(self.lesson, 1, wx.EXPAND | wx.ALL, 6)

        # example code + output
        s.Add(wx.StaticText(panel, label="المثال:"), 0, wx.LEFT, 6)
        self.example = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY,
                                   size=(-1, 120))
        self.example.SetName("مثال الدرس")
        s.Add(self.example, 0, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(740)
        s.Add(self.status, 0, wx.ALL, 6)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "شغّل المثال", lambda e: self._run_example()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "اقرأ الشرح", lambda e: self._read_lesson()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "التمارين", lambda e: self._say_challenges()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "الدرس التالي", lambda e: self._next_unit()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.levelChoice)
        self._refresh_units()

    def _cur_level(self):
        return self._levels[self.choice_index(self.levelChoice)]

    def _refresh_units(self):
        lv = self._cur_level()
        self.unitChoice.Set([f"{i+1}. {u.title}" for i, u in enumerate(lv.units)])
        self.unitChoice.SetSelection(0)
        self._say(f"{lv.title}. {lv.subtitle} عدد الدروس {len(lv.units)}.")
        self._load_unit()

    def _load_unit(self):
        lv = self._cur_level()
        i = self.unitChoice.GetSelection()
        if i < 0 or i >= len(lv.units):
            return
        u = lv.units[i]
        self._unit = u
        text = u.body
        if u.note:
            text += "\n\nملاحظة: " + u.note
        self.lesson.SetValue(text)
        self.example.SetValue(u.example or "(لا مثال)")
        # mark as read
        try:
            self.academy.store.set_setting(f"curr_{u.uid}", "read")
        except Exception:
            pass
        n_ch = len(u.challenges)
        extra = f" لهذا الدرس {n_ch} تمرين." if n_ch else ""
        self._say(f"الدرس: {u.title}. {u.body}{extra}")

    def _read_lesson(self):
        if self._unit:
            note = f" ملاحظة: {self._unit.note}" if self._unit.note else ""
            self._say(f"{self._unit.title}. {self._unit.body}{note}")

    def _run_example(self):
        if not self._unit or not self._unit.example:
            self._say("لا يوجد مثال لتشغيله.")
            return
        result = run_code(self._unit.example, timeout=5)
        if result.error:
            self._say("لم يعمل المثال في هذه البيئة: " + result.error)
        else:
            out = result.output.strip() if result.output.strip() else "لا مُخرجات"
            self._say("ناتج المثال: " + out)

    def _say_challenges(self):
        if not self._unit or not self._unit.challenges:
            self._say("لا تمارين مربوطة بهذا الدرس؛ جرّب المثال في مختبر البرمجة.")
            return
        titles = []
        for cid in self._unit.challenges:
            c = get_challenge(cid)
            if c:
                titles.append(c.title)
        self._say("تمارين هذا الدرس في مختبر البرمجة: " + "، ".join(titles)
                  + ". افتح مختبر البرمجة ونمط التحدّيات لحلّها.")

    def _next_unit(self):
        lv = self._cur_level()
        i = self.unitChoice.GetSelection()
        if i + 1 < len(lv.units):
            self.unitChoice.SetSelection(i + 1)
            self._load_unit()
        else:
            # move to next level
            li = self.choice_index(self.levelChoice)
            if li + 1 < len(self._levels):
                self.levelChoice.SetSelection(li + 1)
                self._refresh_units()
            else:
                self._say("أتممت كلّ الدروس! أحسنت.")

    def _say(self, text):
        self.status.SetLabel(text[:200])
        self.announce(text)

    def instructions(self):
        return ("دورة البرمجة: اختر المستوى (من المبتدئ إلى المتقدّم جدًّا) ثم الدرس. "
                "اقرأ الشرح في الحقل، وشغّل المثال لتسمع ناتجه، والتمارين لمعرفة تمارين "
                "الدرس التي تحلّها في مختبر البرمجة. الدرس التالي ينقلك للدرس أو المستوى "
                "التالي. Escape للإغلاق.")
