# -*- coding: utf-8 -*-
"""
abaAcademy.gui.tutor_view
=========================

The smart study companion's face. It reads the learner's history and, in plain
Arabic, tells them where they stand, what it recommends studying now and why, and
offers to start an adaptive session built to that plan (mixing new material, due
reviews, weak-topic reinforcement, and interleaved earlier material for durable
memory). It also surfaces streaks and improvements so studying feels rewarding.

The companion is transparent: every recommendation comes with a spoken reason, so
the learner understands the plan rather than being handed an opaque queue.
"""

from __future__ import annotations

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..engine.tutor import Tutor, MasteryEstimate


class TutorDialog(AccessibleDialog):
    TITLE = "المُعلّم الذكي"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(720, 560))
        self.academy = academy
        self.tutor = Tutor(academy.store)

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "مرحبًا! أنا رفيقك في الدراسة. أتابع تقدّمك وأقترح ما تحتاج مراجعته "
            "وكيف، ويتطوّر اقتراحي كلّما تحسّنت.")), 0, wx.ALL, 8)

        self.report = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY,
                                  size=(-1, 320))
        self.report.SetName("تقرير المعلّم")
        s.Add(self.report, 1, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(680)
        s.Add(self.status, 0, wx.ALL, 6)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "حدّث تقريري", lambda e: self._refresh()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "بمَ توصيني الآن؟", lambda e: self._recommend()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.report)
        wx.CallAfter(self._refresh)

    def _refresh(self):
        lines = []
        # encouragement first
        lines.append(self.tutor.encouragement_ar())
        lines.append("")
        # overall accuracy
        acc = self.tutor.recent_accuracy()
        pct = int(round(acc * 100))
        lines.append(f"دقّتك الأخيرة الإجمالية نحو {pct}٪.")
        # strongest / weakest
        try:
            strong = self.academy.store.strongest_topics(limit=3)
            weak = self.academy.store.weakest_topics(limit=3)
        except Exception:
            strong, weak = [], []
        if strong:
            names = "، ".join(self._topic_ar(t) for t, w, r in strong if r > 0)
            if names:
                lines.append("أقوى موضوعاتك: " + names + ".")
        if weak:
            weak_real = [(t, w, r) for t, w, r in weak if w > 0]
            if weak_real:
                names = "، ".join(
                    f"{self._topic_ar(t)} ({MasteryEstimate(t, r, w).label_ar()})"
                    for t, w, r in weak_real)
                lines.append("ما يحتاج تدعيمًا: " + names + ".")
        report = "\n".join(lines)
        self.report.SetValue(report)
        self.announce(report)

    def _recommend(self):
        plan = self.tutor.plan_session(size=12)
        parts = [
            "توصيتي لهذه الجلسة:",
            f"• مواد جديدة: {plan.new_count}",
            f"• مراجعة مجدولة: {plan.review_due_count}",
            f"• تدعيم نقاط الضعف: {plan.weak_count}",
            f"• أسئلة متنوّعة من دروس سابقة: {plan.interleave_count}",
            f"• مستوى الصعوبة: {plan.difficulty_target} من 3",
            "",
            "السبب: " + plan.explain_ar(),
            "",
            "افتح أيّ مقرّر وابدأ التدريب، وسأطبّق هذا المزيج تلقائيًا "
            "أثناء تقدّمك.",
        ]
        text = "\n".join(parts)
        self.report.SetValue(text)
        self.announce(text)

    def _topic_ar(self, topic):
        # reuse the mistakes-view label mapping for consistency
        try:
            from .mistakes_view import _topic_label_ar
            return _topic_label_ar(topic)
        except Exception:
            return topic

    def instructions(self):
        return ("المعلّم الذكي: «حدّث تقريري» يعرض دقّتك وأقوى موضوعاتك وما يحتاج تدعيمًا. "
                "«بمَ توصيني الآن؟» يقترح مزيج جلسة متوازنة (جديد، مراجعة مجدولة، تدعيم "
                "الضعف، وأسئلة متنوّعة من دروس سابقة) مع سبب كل اختيار، ويتكيّف مع مستواك. "
                "Escape للإغلاق.")
