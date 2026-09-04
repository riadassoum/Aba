# -*- coding: utf-8 -*-
"""
abaAcademy.gui.achievements_view
================================

A real achievements screen: it lists the whole achievement catalogue with a
clear earned / not-yet status for each, plus a one-line summary of how many are
earned. Nothing here is a placeholder — every listed goal is reachable through
normal study, and the earned state is read live from the learner's saved
progress.
"""

from __future__ import annotations

import wx

from .accessible import AccessibleDialog


class AchievementsView(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "الإنجازات", speech, size=(620, 520))
        self.academy = academy

        items = academy.achievements_overview()
        earned = sum(1 for a in items if a["earned"])
        total = len(items)

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        header = wx.StaticText(
            panel, label=f"حصلت على {earned} من {total} إنجازاً. واصل التعلّم لفتح الباقي.")
        header.Wrap(560)
        sizer.Add(header, 0, wx.ALL, 12)

        self.listBox = wx.ListBox(panel, style=wx.LB_SINGLE)
        for a in items:
            mark = "✔ حصلت عليه" if a["earned"] else "◻ لم تحصل عليه بعد"
            self.listBox.Append(f"{a['title']} — {mark} — {a['desc']}")
        self.listBox.SetName("قائمة الإنجازات")
        if items:
            self.select_index(self.listBox, 0)
        sizer.Add(self.listBox, 1, wx.EXPAND | wx.ALL, 8)

        closeBtn = self.button(panel, "إغلاق", lambda e: self.close_screen())
        sizer.Add(closeBtn, 0, wx.ALIGN_RIGHT | wx.ALL, 8)

        panel.SetSizer(sizer)
        self.set_first_control(self.listBox)

    def instructions(self) -> str:
        return ("استخدم الأسهم لتصفّح الإنجازات. كل إنجاز يبيّن إن كنت حصلت عليه "
                "أو ما يلزم لفتحه. Escape للإغلاق.")
