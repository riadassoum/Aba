# -*- coding: utf-8 -*-
"""
abaAcademy.gui.settings_view
============================

A learner-facing settings screen. Everything here is a real, working preference
that changes how the academy behaves, saved in the same database as progress so
it survives updates. No cosmetic toggles — each one does something:

* عدد الأسئلة في الجلسة — how many questions a practice session holds.
* الهدف اليومي — the daily goal (questions/day) the home screen tracks.
* تشكيل صارم — whether answers must match the diacritics exactly.
* المتابعة التلقائية — auto-resume the last lesson.
* نطق التقدّم — announce progress ("سؤال ٣ من ١٢") during a session.
"""

from __future__ import annotations

from .accessible import AccessibleDialog

try:
    import wx
except Exception:
    wx = None


class SettingsView(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "الإعدادات", speech, size=(560, 520))
        self.academy = academy
        self.settings = academy.settings
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label="اضبط الأكاديمية كما يناسبك. تُحفظ فوراً."),
              0, wx.ALL, 8)

        # session size
        s.Add(wx.StaticText(panel, label="عدد الأسئلة في كل جلسة تدريب:"), 0, wx.LEFT | wx.TOP, 8)
        self.sessionSpin = wx.SpinCtrl(panel, min=5, max=40,
                                       initial=self.settings.get_int("session_size", 12))
        self.sessionSpin.SetName("عدد الأسئلة في الجلسة")
        s.Add(self.sessionSpin, 0, wx.EXPAND | wx.ALL, 6)

        # daily goal
        s.Add(wx.StaticText(panel, label="الهدف اليومي (عدد الأسئلة في اليوم):"), 0, wx.LEFT | wx.TOP, 8)
        self.goalSpin = wx.SpinCtrl(panel, min=5, max=200,
                                    initial=self.settings.get_int("daily_goal", 20))
        self.goalSpin.SetName("الهدف اليومي")
        s.Add(self.goalSpin, 0, wx.EXPAND | wx.ALL, 6)

        # checkboxes for the boolean prefs
        self.strictCb = wx.CheckBox(panel, label="تشكيل صارم: يجب مطابقة الحركات تماماً")
        self.strictCb.SetValue(self.settings.get_bool("strict_tashkeel"))
        s.Add(self.strictCb, 0, wx.ALL, 6)

        self.resumeCb = wx.CheckBox(panel, label="المتابعة التلقائية لآخر درس")
        self.resumeCb.SetValue(self.settings.get_bool("auto_resume"))
        s.Add(self.resumeCb, 0, wx.ALL, 6)

        self.progressCb = wx.CheckBox(panel, label="نطق التقدّم أثناء الجلسة (سؤال ٣ من ١٢)")
        self.progressCb.SetValue(self.settings.get_bool("announce_progress"))
        s.Add(self.progressCb, 0, wx.ALL, 6)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "حفظ", lambda e: self._save()), 0, wx.ALL, 6)
        row.Add(self.button(panel, "استعادة الافتراضي", lambda e: self._defaults()), 0, wx.ALL, 6)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 6)
        s.Add(row, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        self.set_first_control(self.sessionSpin)

    def _save(self):
        self.settings.set_int("session_size", self.sessionSpin.GetValue())
        self.settings.set_int("daily_goal", self.goalSpin.GetValue())
        self.settings.set_bool("strict_tashkeel", self.strictCb.GetValue())
        self.settings.set_bool("auto_resume", self.resumeCb.GetValue())
        self.settings.set_bool("announce_progress", self.progressCb.GetValue())
        self.announce("حُفظت الإعدادات.")

    def _defaults(self):
        self.sessionSpin.SetValue(12)
        self.goalSpin.SetValue(20)
        self.strictCb.SetValue(False)
        self.resumeCb.SetValue(True)
        self.progressCb.SetValue(True)
        self._save()
        self.announce("أُعيدت الإعدادات إلى الافتراضي وحُفظت.")

    def instructions(self):
        return ("اضبط عدد أسئلة الجلسة، هدفك اليومي، وصرامة التشكيل والمتابعة ونطق التقدّم. "
                "اضغط «حفظ». Escape للإغلاق.")
