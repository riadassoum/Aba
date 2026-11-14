# -*- coding: utf-8 -*-
"""
abaAcademy.gui.onboarding_view
==============================

A friendly first-run welcome. The very first time the academy is opened it
greets the learner, asks their name (used on certificates) and a daily goal,
briefly explains how to get around, and points them at a sensible first step.
It only appears once — afterwards the learner goes straight to the hub — and can
always be reopened from the help screen.
"""

from __future__ import annotations

from .accessible import AccessibleDialog

try:
    import wx
except Exception:
    wx = None


WELCOME = (
    "أهلاً بك في أكاديمية الكفيف العربي! هنا تتعلّم العربية والإنجليزية والحاسوب "
    "والقرآن وغيرها، كلها بلوحة المفاتيح وقارئ الشاشة. من الصفحة الرئيسية تصل إلى "
    "الدروس، والمصحف، والبطاقات، والألعاب، وغيرها. لنبدأ بإعداد بسيط."
)


class OnboardingView(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "مرحباً بك", speech, size=(600, 500))
        self.academy = academy
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=WELCOME), 0, wx.ALL, 10)

        s.Add(wx.StaticText(panel, label="ما اسمك؟ (يظهر على شهاداتك — اختياري)"),
              0, wx.LEFT | wx.TOP, 8)
        self.nameCtrl = wx.TextCtrl(panel)
        self.nameCtrl.SetName("اسمك")
        s.Add(self.nameCtrl, 0, wx.EXPAND | wx.ALL, 6)

        s.Add(wx.StaticText(panel, label="كم سؤالاً تريد أن تحلّ كل يوم؟ (هدفك اليومي)"),
              0, wx.LEFT | wx.TOP, 8)
        self.goalSpin = wx.SpinCtrl(panel, min=5, max=200, initial=20)
        self.goalSpin.SetName("الهدف اليومي")
        s.Add(self.goalSpin, 0, wx.EXPAND | wx.ALL, 6)

        s.Add(wx.StaticText(panel, label=(
            "نصيحة: ابدأ بـتدريب اليوم لمراجعة سريعة متنوّعة، أو كل الدورات لاختيار "
            "درس. اضغط F1 في أي شاشة لسماع اختصاراتها.")), 0, wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "ابدأ", lambda e: self._finish()), 0, wx.ALL, 6)
        s.Add(row, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        self.set_first_control(self.nameCtrl)

    def _finish(self):
        name = self.nameCtrl.GetValue().strip()
        if name:
            self.academy.settings._store.set_setting("learner_name", name)
        self.academy.settings.set_int("daily_goal", self.goalSpin.GetValue())
        # mark onboarding as seen so it won't show again
        self.academy.settings._store.set_setting("onboarded", "1")
        self.announce("رائع! كل شيء جاهز. أهلاً بك في الأكاديمية.")
        self.close_screen()

    def instructions(self):
        return ("شاشة الترحيب لأول مرة: اكتب اسمك واختر هدفك اليومي ثم ابدأ. "
                "يمكنك تغيير ذلك لاحقاً من الإعدادات. Escape للتخطّي.")
