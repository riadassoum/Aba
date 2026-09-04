# -*- coding: utf-8 -*-
"""
abaAcademy.gui.progress_view
============================

A single, motivating snapshot of the learner's journey: study streak, total time,
how many topics are at each mastery level, recent achievements, and the smart
tutor's one-line recommendation. Everything is spoken clearly and kept positive
but honest — real numbers, no inflation.

This is a user-experience screen: it exists so a learner can, in a few seconds,
hear "here's how you're doing and here's a good next step," which makes returning
to study feel rewarding rather than aimless.
"""

from __future__ import annotations

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..engine.tutor import Tutor, MasteryEstimate


def _fmt_duration(seconds):
    seconds = int(seconds or 0)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h:
        return f"{h} ساعة و{m} دقيقة"
    return f"{m} دقيقة"


class ProgressDialog(AccessibleDialog):
    TITLE = "لوحة تقدّمي"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(720, 560))
        self.academy = academy
        self.tutor = Tutor(academy.store)

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label="لمحة عن رحلتك في التعلّم."), 0, wx.ALL, 8)

        self.report = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY,
                                  size=(-1, 380))
        self.report.SetName("لوحة التقدّم")
        s.Add(self.report, 1, wx.EXPAND | wx.ALL, 6)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "حدّث", lambda e: self._refresh()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "حدّد هدفي اليومي", lambda e: self._set_goal()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "اقرأ الملخّص", lambda e: self._speak_summary()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.report)
        self._summary = ""
        wx.CallAfter(self._refresh)

    def _refresh(self):
        store = self.academy.store
        lines = []

        # daily goal progress
        try:
            goal = int(store.get_setting("daily_goal", "20") or "20")
        except Exception:
            goal = 20
        try:
            today = store.today_activity()
            answered = today.get("answered", 0)
        except Exception:
            answered = 0
        if goal > 0:
            done = min(answered, goal)
            remaining = max(0, goal - answered)
            bar = self._progress_bar(answered, goal)
            lines.append(f"هدف اليوم: {answered} من {goal} سؤالًا. {bar}")
            if answered >= goal:
                lines.append("بلغت هدف اليوم — عمل رائع!")
            elif remaining:
                lines.append(f"بقي {remaining} سؤالًا لبلوغ هدفك.")
            lines.append("")

        # streak + encouragement
        try:
            streak = store.current_streak()
        except Exception:
            streak = 0
        if streak >= 1:
            lines.append(f"سلسلة الأيّام المتتالية: {streak}.")
        # study time
        try:
            secs = store.total_study_seconds()
            lines.append(f"إجمالي وقت الدراسة: {_fmt_duration(secs)}.")
        except Exception:
            pass

        # mastery breakdown
        buckets = {"mastered": 0, "strong": 0, "learning": 0,
                   "struggling": 0}
        try:
            seen = set()
            for t, w, r in (store.strongest_topics(limit=100)
                            + store.weakest_topics(limit=100)):
                if t in seen:
                    continue
                seen.add(t)
                lvl = MasteryEstimate(t, r, w).level
                if lvl in buckets:
                    buckets[lvl] += 1
        except Exception:
            pass
        if any(buckets.values()):
            lines.append("")
            lines.append("مستوى إتقانك للموضوعات:")
            lines.append(f"  - متقَنة: {buckets['mastered']}")
            lines.append(f"  - جيّدة: {buckets['strong']}")
            lines.append(f"  - قيد التعلّم: {buckets['learning']}")
            lines.append(f"  - تحتاج تدعيمًا: {buckets['struggling']}")

        # achievements
        try:
            achs = store.achievements()
        except Exception:
            achs = []
        if achs:
            lines.append("")
            lines.append("إنجازاتك:")
            for a in achs[:6]:
                name = a.get("name") or a.get("id", "")
                lines.append(f"  - {name}")

        # tutor recommendation
        lines.append("")
        lines.append("توصية المعلّم الذكي:")
        lines.append("  " + self.tutor.encouragement_ar())
        plan = self.tutor.plan_session(size=12)
        lines.append("  " + plan.explain_ar())

        report = "\n".join(lines) if lines else "ابدأ التدريب وستظهر هنا رحلتك."
        self.report.SetValue(report)
        # a compact spoken summary
        self._summary = self._make_summary(streak, buckets)
        self.announce(self._summary)

    def _make_summary(self, streak, buckets):
        bits = []
        if streak >= 2:
            bits.append(f"لديك سلسلة {streak} أيّام")
        mastered = buckets.get("mastered", 0)
        if mastered:
            bits.append(f"أتقنت {mastered} موضوعًا")
        need = buckets.get("struggling", 0)
        if need:
            bits.append(f"و{need} تحتاج تدعيمًا")
        if not bits:
            return "ابدأ التدريب لتُبنى لوحة تقدّمك."
        return "، ".join(bits) + ". " + self.tutor.encouragement_ar()

    def _progress_bar(self, done, total):
        """A short text progress indicator that reads well aloud."""
        if total <= 0:
            return ""
        pct = int(round(100 * min(done, total) / total))
        return f"({pct}٪)"

    def _set_goal(self):
        current = "20"
        try:
            current = self.academy.store.get_setting("daily_goal", "20") or "20"
        except Exception:
            pass
        dlg = wx.TextEntryDialog(
            self, "كم سؤالًا تريد حلّه يوميًا؟", "هدف يومي", current)
        if dlg.ShowModal() == wx.ID_OK:
            val = dlg.GetValue().strip().translate(
                str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
            if val.isdigit() and int(val) > 0:
                try:
                    self.academy.store.set_setting("daily_goal", str(int(val)))
                    self._say(f"حُدّد هدفك اليومي: {int(val)} سؤالًا.")
                    self._refresh()
                except Exception:
                    self._say("تعذّر حفظ الهدف.")
            else:
                self._say("اكتب رقمًا صحيحًا أكبر من صفر.")
        dlg.Destroy()

    def _say(self, text):
        self.status.SetLabel(text[:200]) if hasattr(self, "status") else None
        self.announce(text)

    def _speak_summary(self):
        self.announce(self._summary or "لا ملخّص بعد.")

    def instructions(self):
        return ("لوحة تقدّمي: تعرض سلسلة أيّامك المتتالية، وقت دراستك، وعدد الموضوعات في كل "
                "مستوى إتقان، وإنجازاتك، وتوصية المعلّم الذكي. «اقرأ الملخّص» ينطق ملخّصًا "
                "مختصرًا. Escape للإغلاق.")
