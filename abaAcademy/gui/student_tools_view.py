# -*- coding: utf-8 -*-
"""
abaAcademy.gui.student_tools_view
=================================

A small set of practical everyday tools in one screen:

* **تفقيط** — turn a number into its Arabic words.
* **محوّل التاريخ** — convert between Hijri and Gregorian dates, and show today's
  date in both calendars.

Both are offline and deterministic. The date converter uses the arithmetic Hijri
calendar, which can differ by a day from the moon-sighting calendar — noted in
the UI.
"""

from __future__ import annotations

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..tools.tafqit import number_to_arabic_words
from ..tools import hijri


def _to_western(s):
    return s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))


class StudentToolsDialog(AccessibleDialog):
    TITLE = "أدوات الطالب"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(700, 520))
        self.academy = academy

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)

        # -- tafqit ------------------------------------------------------
        s.Add(wx.StaticText(panel, label="تفقيط: حوّل رقماً إلى كلمات عربية."),
              0, wx.ALL, 6)
        trow = wx.BoxSizer(wx.HORIZONTAL)
        self.numEntry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.numEntry.SetName("الرقم")
        self.numEntry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._tafqit())
        trow.Add(self.numEntry, 1, wx.RIGHT, 6)
        trow.Add(self.button(panel, "فقّط", lambda e: self._tafqit()), 0)
        s.Add(trow, 0, wx.EXPAND | wx.ALL, 6)

        # -- date --------------------------------------------------------
        s.Add(wx.StaticText(panel, label=(
            "محوّل التاريخ: اكتب التاريخ (سنة شهر يوم) واختر الاتجاه. "
            "التقويم الهجري هنا حسابي، وقد يختلف يوماً عن رؤية الهلال.")),
            0, wx.ALL, 6)
        drow = wx.BoxSizer(wx.HORIZONTAL)
        self.yEntry = wx.TextCtrl(panel, size=(70, -1))
        self.yEntry.SetName("سنة")
        self.mEntry = wx.TextCtrl(panel, size=(50, -1))
        self.mEntry.SetName("شهر")
        self.dEntry = wx.TextCtrl(panel, size=(50, -1))
        self.dEntry.SetName("يوم")
        # label BEFORE each field so the screen reader associates them correctly
        drow.Add(wx.StaticText(panel, label="سنة:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        drow.Add(self.yEntry, 0, wx.RIGHT, 6)
        drow.Add(wx.StaticText(panel, label="شهر:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        drow.Add(self.mEntry, 0, wx.RIGHT, 6)
        drow.Add(wx.StaticText(panel, label="يوم:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        drow.Add(self.dEntry, 0, wx.RIGHT, 10)
        self.dirChoice = wx.Choice(panel, choices=["ميلادي إلى هجري", "هجري إلى ميلادي"])
        self.dirChoice.SetSelection(0)
        self.bind_choice(self.dirChoice, lambda e: None)
        drow.Add(self.dirChoice, 0)
        s.Add(drow, 0, wx.ALL, 6)

        brow = wx.BoxSizer(wx.HORIZONTAL)
        brow.Add(self.button(panel, "حوّل التاريخ", lambda e: self._convert_date()), 0, wx.ALL, 3)
        brow.Add(self.button(panel, "تاريخ اليوم", lambda e: self._today()), 0, wx.ALL, 3)
        brow.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(brow, 0, wx.ALL, 3)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(660)
        s.Add(self.status, 0, wx.ALL, 8)

        panel.SetSizer(s)
        self.set_first_control(self.numEntry)

    def _tafqit(self):
        raw = _to_western(self.numEntry.GetValue().strip())
        if not raw.lstrip("-").isdigit():
            self._say("اكتب رقماً صحيحاً.")
            return
        words = number_to_arabic_words(int(raw))
        self._say(f"{raw} = {words}")

    def _read_date(self):
        try:
            y = int(_to_western(self.yEntry.GetValue().strip()))
            m = int(_to_western(self.mEntry.GetValue().strip()))
            d = int(_to_western(self.dEntry.GetValue().strip()))
            return y, m, d
        except ValueError:
            return None

    def _convert_date(self):
        parts = self._read_date()
        if not parts:
            self._say("اكتب السنة والشهر واليوم بالأرقام.")
            return
        y, m, d = parts
        if self.dirChoice.GetSelection() == 0:
            hy, hm, hd = hijri.gregorian_to_hijri(y, m, d)
            self._say(f"{hijri.format_gregorian(y, m, d)} يوافق "
                      f"{hijri.format_hijri(hy, hm, hd)}")
        else:
            gy, gm, gd = hijri.hijri_to_gregorian(y, m, d)
            self._say(f"{hijri.format_hijri(y, m, d)} يوافق "
                      f"{hijri.format_gregorian(gy, gm, gd)}")

    def _today(self):
        g, h = hijri.today_both()
        self._say(f"اليوم: {g}، الموافق {h}.")

    def _say(self, text):
        self.status.SetLabel(text)
        self.announce(text)

    def instructions(self):
        return ("أدوات الطالب: «تفقيط» يحوّل رقماً إلى كلمات عربية. «محوّل التاريخ» يحوّل "
                "بين الميلادي والهجري — اكتب السنة والشهر واليوم واختر الاتجاه، أو اضغط "
                "«تاريخ اليوم». التقويم الهجري حسابي وقد يختلف يوماً عن رؤية الهلال. "
                "Escape للإغلاق.")
