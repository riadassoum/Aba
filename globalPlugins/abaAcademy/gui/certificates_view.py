# -*- coding: utf-8 -*-
"""
abaAcademy.gui.certificates_view
================================

Per-course progress and completion certificates. A real academy marks
milestones: when a learner finishes every lesson in a course, they've earned a
certificate. This screen shows how far along each course is, and for finished
courses it produces a plain-text certificate the learner can read aloud, copy,
or save (via the export tool) — a concrete, motivating reward.
"""

from __future__ import annotations

import datetime

from .accessible import AccessibleDialog

try:
    import wx
except Exception:
    wx = None

AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def _ar(n):
    return str(n).translate(AR)


def certificate_text(course_title, learner_name=""):
    """Build the certificate's text (also reused by the export tool)."""
    today = datetime.date.today().isoformat()
    who = learner_name.strip() or "الطالب"
    line = "★" * 20
    return (
        f"{line}\n"
        f"       شهادة إتمام\n"
        f"     أكاديمية الكفيف العربي\n"
        f"{line}\n\n"
        f"تشهد الأكاديمية بأن {who}\n"
        f"قد أتمّ بنجاح جميع دروس دورة:\n"
        f"«{course_title}»\n\n"
        f"بتاريخ {today}\n\n"
        f"نبارك لك هذا الإنجاز، وواصل التعلّم!\n"
        f"{line}\n"
    )


class CertificatesView(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "الشهادات والتقدّم", speech, size=(640, 560))
        self.academy = academy
        self._progress = academy.course_progress()
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)

        done_courses = [p for p in self._progress if p["complete"]]
        header = (f"أتممت {_ar(len(done_courses))} من {_ar(len(self._progress))} دورات. "
                  "اختر دورة لمعرفة تقدّمك، وللدورات المكتملة يمكنك عرض شهادتك.")
        s.Add(wx.StaticText(panel, label=header), 0, wx.ALL, 8)

        self.listbox = wx.ListBox(panel, style=wx.LB_SINGLE)
        items = []
        for p in self._progress:
            mark = "✓ مكتملة — شهادة" if p["complete"] else f"{_ar(p['percent'])}٪"
            items.append(f"{p['title']}: {_ar(p['done'])} من {_ar(p['total'])} ({mark})")
        self.listbox.Set(items)
        self.listbox.SetSelection(0)
        self.listbox.SetName("قائمة الدورات وتقدّمك فيها")
        s.Add(self.listbox, 1, wx.EXPAND | wx.ALL, 6)

        s.Add(self.button(panel, "عرض الشهادة (للدورات المكتملة)", lambda e: self._show_cert()),
              0, wx.EXPAND | wx.ALL, 4)
        s.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()),
              0, wx.ALIGN_RIGHT | wx.ALL, 6)
        panel.SetSizer(s)
        self.set_first_control(self.listbox)

    def _show_cert(self):
        i = self.listbox.GetSelection()
        if i == wx.NOT_FOUND:
            return
        p = self._progress[i]
        if not p["complete"]:
            self.announce(f"دورة «{p['title']}» لم تكتمل بعد: {_ar(p['done'])} من "
                          f"{_ar(p['total'])} درساً. أكملها لتحصل على الشهادة.")
            return
        name = self.academy.settings._get("learner_name") if hasattr(self.academy.settings, "_get") else ""
        text = certificate_text(p["title"], name)
        self.show_child(_CertificateDialog(self, self.speech, p["title"], text))

    def instructions(self):
        return ("تقدّمك في كل دورة، والدورات المكتملة تمنحك شهادة. اختر دورة و«عرض الشهادة». "
                "Escape للإغلاق.")


class _CertificateDialog(AccessibleDialog):
    def __init__(self, parent, speech, title, text):
        super().__init__(parent, f"شهادة — {title}", speech, size=(600, 480))
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        t = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY, value=text)
        t.SetName("نص الشهادة")
        s.Add(t, 1, wx.EXPAND | wx.ALL, 8)
        s.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()),
              0, wx.ALIGN_RIGHT | wx.ALL, 6)
        panel.SetSizer(s)
        self.set_first_control(t)
        wx.CallAfter(lambda: self.announce("مبارك! هذه شهادة إتمامك للدورة."))

    def instructions(self):
        return "شهادة إتمامك. تنقّل بالأسهم لقراءتها، وانسخها إن شئت. Escape للإغلاق."
