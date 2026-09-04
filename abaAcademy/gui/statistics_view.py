# -*- coding: utf-8 -*-
"""
abaAcademy.gui.statistics_view
=============================

Accessible statistics screen. Reads aggregates from the store and presents them
as a single focusable, screen-reader-friendly text report (announced on show),
plus the raw numbers in a read-only multiline field the learner can arrow
through. Covers the spec's statistics list: study time, questions answered,
accuracy, weakest/strongest topics, average response time, daily streak, and
recent activity, plus earned achievements.
"""

from __future__ import annotations

import wx

from .accessible import AccessibleDialog


def _fmt_minutes(seconds: int) -> str:
    m = seconds // 60
    if m < 60:
        return f"{m} دقيقة"
    return f"{m // 60} ساعة و{m % 60} دقيقة"


class StatisticsView(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "الإحصائيات", speech, size=(700, 560))
        self.academy = academy
        store = academy.store

        overall = store.overall_stats()
        weak = store.weakest_topics(5)
        strong = store.strongest_topics(5)
        streak = store.current_streak()
        study = store.total_study_seconds()
        achievements = store.achievements()
        activity = store.daily_activity(7)

        lines = [
            "ملخص الإحصائيات:",
            f"إجمالي وقت الدراسة: {_fmt_minutes(study)}.",
            f"عدد الأسئلة المُجابة: {overall['answered']}.",
            f"نسبة الدقة الكلية: {overall['accuracy']:.0f} بالمئة.",
            f"متوسط زمن الإجابة: {overall['avg_time']:.1f} ثانية.",
            f"سلسلة الأيام المتتالية: {streak} يوماً.",
        ]
        if weak:
            lines.append("أضعف المواضيع: " + "، ".join(
                f"{t} ({w} خطأ)" for t, w, r in weak) + ".")
        if strong:
            lines.append("أقوى المواضيع: " + "، ".join(
                f"{t} ({r} صحيحة)" for t, w, r in strong) + ".")
        if activity:
            lines.append("النشاط الأخير: " + "، ".join(
                f"{a['day']}: {a['answered']} سؤال" for a in activity) + ".")
        if achievements:
            lines.append("الإنجازات: " + "، ".join(a["title"] for a in achievements) + ".")
        else:
            lines.append("لا إنجازات بعد — استمر في التعلّم!")

        self._report = "\n".join(lines)

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.textCtrl = wx.TextCtrl(
            panel, value=self._report,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.textCtrl.SetName("تقرير الإحصائيات")
        sizer.Add(self.textCtrl, 1, wx.EXPAND | wx.ALL, 8)
        closeBtn = self.button(panel, "إغلاق", lambda e: self.close_screen())
        sizer.Add(closeBtn, 0, wx.ALIGN_RIGHT | wx.ALL, 8)
        panel.SetSizer(sizer)
        self.set_first_control(self.textCtrl)

    def instructions(self) -> str:
        return "استخدم الأسهم لقراءة التقرير سطراً سطراً. Escape للإغلاق."

    def _announce_screen(self):
        # Override to read the whole report on show.
        self.Raise()
        if self._first_control is not None:
            try:
                self._first_control.SetFocus()
            except Exception:
                pass
        self.speech.announce(self._report)
