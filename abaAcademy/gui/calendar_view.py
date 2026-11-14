# -*- coding: utf-8 -*-
"""
abaAcademy.gui.calendar_view
============================

The Hijri calendar screen: a month at a time, one line per day giving the
weekday, the Hijri date, the Gregorian date and any occasion. Arrow keys move
through the days; Page Up / Page Down change the month; Home jumps to today.
Below it, a converter with labelled day/month/year fields in either
direction, and the upcoming occasions with how many days away they are.
"""

from __future__ import annotations

import datetime

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog, parse_int
from ..tools import hijri


def _ar(n) -> str:
    return str(n).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


class CalendarDialog(ToolDialog):
    TITLE = "التقويم الهجري"
    SIZE = (780, 640)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        today = datetime.date.today()
        self._today_h = hijri.gregorian_to_hijri(today.year, today.month, today.day)
        self._year, self._month = self._today_h[0], self._today_h[1]
        self._days = []

        self.header = self.add_text("")
        self.days = self.add_list("أيام الشهر (Page Up وPage Down لتغيير الشهر، Home لليوم)",
                                  height=220, on_select=self._on_day)
        self.days.Bind(wx.EVT_KEY_DOWN, self._on_days_key)
        self.add_buttons([
            ("الشهر السابق", lambda: self._shift(-1)),
            ("الشهر التالي", lambda: self._shift(1)),
            ("اليوم", self._go_today),
            ("المناسبات القادمة", self._occasions),
        ], close=False)

        self.add_text("تحويل تاريخ:")
        self.direction = self.add_choice("اتجاه التحويل",
                                         ["من الهجري إلى الميلادي", "من الميلادي إلى الهجري"])
        self.dayEntry = self.add_entry("يوم", on_enter=self._convert)
        self.monthEntry = self.add_entry("شهر", on_enter=self._convert)
        self.yearEntry = self.add_entry("سنة", on_enter=self._convert)
        self.add_buttons([("حوّل", self._convert), ("افتح الشهر في التقويم", self._open_converted)])
        self.add_output("النتيجة", height=90)
        self.finish(self.days)
        self._fill()

    # -- month -----------------------------------------------------------
    def _fill(self, select_day: int = 0) -> None:
        try:
            self._days = hijri.hijri_month_days(self._year, self._month)
        except Exception:
            self._year, self._month = self._today_h[0], self._today_h[1]
            self._days = hijri.hijri_month_days(self._year, self._month)
        lines = []
        for d in self._days:
            hy, hm, hd = d["hijri"]
            gy, gm, gd = d["gregorian"]
            line = (f"{hijri.weekday_name(d['weekday'])} {_ar(hd)}، "
                    f"الموافق {_ar(gd)} {hijri.gregorian_month_name(gm)} {_ar(gy)}")
            if (hy, hm, hd) == self._today_h:
                line = "اليوم: " + line
            if d["occasion"]:
                line += f" — {d['occasion']}"
            lines.append(line)
        self.days.Set(lines)
        g0 = self._days[0]["gregorian"]
        g1 = self._days[-1]["gregorian"]
        self.header.SetLabel(
            f"{hijri.hijri_month_name(self._month)} {_ar(self._year)} هـ — "
            f"{len(self._days)} يومًا، من {_ar(g0[2])} {hijri.gregorian_month_name(g0[1])} "
            f"إلى {_ar(g1[2])} {hijri.gregorian_month_name(g1[1])} {_ar(g1[0])} م. "
            f"({hijri.calendar_source(self._year)})")
        idx = select_day
        if not idx and (self._year, self._month) == self._today_h[:2]:
            idx = self._today_h[2] - 1
        self.select_index(self.days, max(0, min(len(lines) - 1, idx)))

    def _shift(self, delta: int) -> None:
        self._year, self._month = hijri.add_hijri_months(self._year, self._month, delta)
        self._fill()
        self.days.SetFocus()
        self.announce(self.header.GetLabel())

    def _go_today(self) -> None:
        self._year, self._month = self._today_h[0], self._today_h[1]
        self._fill()
        self.days.SetFocus()
        i = self.days.GetSelection()
        if i >= 0:
            self.announce(self.days.GetString(i))

    def _on_day(self) -> None:
        pass   # the list item itself is spoken by the screen reader

    def _on_days_key(self, evt) -> None:
        code = evt.GetKeyCode()
        if code == wx.WXK_PAGEUP:
            self._shift(-1)
        elif code == wx.WXK_PAGEDOWN:
            self._shift(1)
        elif code == wx.WXK_HOME and evt.ControlDown():
            self._go_today()
        else:
            evt.Skip()

    def _occasions(self) -> None:
        up = hijri.upcoming_occasions(count=8)
        lines = []
        for days, label, (hy, hm, hd), (gy, gm, gd) in up:
            when = "اليوم" if days == 0 else ("غدًا" if days == 1 else f"بعد {_ar(days)} يومًا")
            lines.append(f"{label}: {when}، {_ar(hd)} {hijri.hijri_month_name(hm)} — "
                         f"{_ar(gd)} {hijri.gregorian_month_name(gm)} {_ar(gy)}")
        self.show_output("\n".join(lines) or "لا مناسبات قريبة.")

    # -- converter -------------------------------------------------------
    def _read(self):
        try:
            return (parse_int(self.yearEntry.GetValue()), parse_int(self.monthEntry.GetValue()),
                    parse_int(self.dayEntry.GetValue()))
        except ValueError:
            raise ValueError("اكتب اليوم والشهر والسنة أرقامًا.")

    def _convert(self) -> None:
        y, m, d = self._read()
        if self.choice_index(self.direction) == 0:
            gy, gm, gd = hijri.hijri_to_gregorian(y, m, d)
            wd = hijri.weekday_of_gregorian(gy, gm, gd)
            text = (f"{hijri.format_hijri(y, m, d, wd)} يوافق {hijri.format_gregorian(gy, gm, gd)}. "
                    f"({hijri.calendar_source(y)})")
            self._last = (y, m)
        else:
            try:
                wd = hijri.weekday_of_gregorian(y, m, d)
            except ValueError:
                raise ValueError("هذا التاريخ الميلادي غير موجود.")
            hy, hm, hd = hijri.gregorian_to_hijri(y, m, d)
            text = (f"{hijri.format_gregorian(y, m, d, wd)} يوافق {hijri.format_hijri(hy, hm, hd)}. "
                    f"({hijri.calendar_source(hy)})")
            self._last = (hy, hm)
        occ = hijri.occasion_of(self._last[1], d if self.choice_index(self.direction) == 0 else hd)
        if occ:
            text += f" المناسبة: {occ}."
        self.show_output(text)

    def _open_converted(self) -> None:
        last = getattr(self, "_last", None)
        if not last:
            self._convert()
            last = getattr(self, "_last", None)
        if last:
            self._year, self._month = last
            self._fill()
            self.days.SetFocus()
            self.announce(self.header.GetLabel())

    def instructions(self) -> str:
        return ("تقويم هجري شهريّ: تنقّل بين الأيام بالسهمين، وPage Up وPage Down لتغيير الشهر، "
                "وCtrl+Home لليوم. كل يوم يذكر ما يوافقه بالميلادي ومناسبته إن وُجدت. "
                "وفي الأسفل محوّل تواريخ بحقول اليوم والشهر والسنة. قد يختلف التقويم يومًا "
                "عن رؤية الهلال المحلية.")
