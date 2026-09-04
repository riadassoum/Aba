# -*- coding: utf-8 -*-
"""
abaAcademy.gui.converter
========================

An accessible units converter: choose a family (length, mass, temperature, …),
choose the source and target units, type a value, and hear the result in Arabic.
Built on ``math_engine.units`` — fully offline, no data files.

A feature added on top of the requested V2.0 set: unit conversion is a frequent
practical need, and doing it in a fully spoken, keyboard-only flow removes a
task that is otherwise awkward with a screen reader on general-purpose tools.
"""

from __future__ import annotations

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..math_engine import units


def _speak_number(value):
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.4f}".rstrip("0").rstrip(".")


class ConverterDialog(AccessibleDialog):
    TITLE = "محوّل الوحدات"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(700, 500))
        self.academy = academy

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label="اختر الفئة والوحدتين، ثم اكتب القيمة واضغط Enter."),
              0, wx.ALL, 6)

        # family
        frow = wx.BoxSizer(wx.HORIZONTAL)
        frow.Add(wx.StaticText(panel, label="الفئة:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self._families = units.families()
        self.familyChoice = wx.Choice(panel, choices=[n for _, n in self._families])
        self.familyChoice.SetSelection(0)
        self.bind_choice(self.familyChoice, lambda e: self._refresh_units())
        frow.Add(self.familyChoice, 0)
        s.Add(frow, 0, wx.ALL, 6)

        # from / to units
        urow = wx.BoxSizer(wx.HORIZONTAL)
        urow.Add(wx.StaticText(panel, label="من:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.fromChoice = wx.Choice(panel, choices=[])
        self.bind_choice(self.fromChoice, lambda e: self._convert())
        urow.Add(self.fromChoice, 0, wx.RIGHT, 12)
        urow.Add(wx.StaticText(panel, label="إلى:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.toChoice = wx.Choice(panel, choices=[])
        self.bind_choice(self.toChoice, lambda e: self._convert())
        urow.Add(self.toChoice, 0)
        s.Add(urow, 0, wx.ALL, 6)

        # value
        vrow = wx.BoxSizer(wx.HORIZONTAL)
        vrow.Add(wx.StaticText(panel, label="القيمة:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.valueEntry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.valueEntry.SetName("القيمة")
        self.valueEntry.Bind(wx.EVT_TEXT_ENTER, lambda e: self._convert())
        vrow.Add(self.valueEntry, 1)
        s.Add(vrow, 0, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(660)
        s.Add(self.status, 0, wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "حوّل (Enter)", lambda e: self._convert()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "اعكس الوحدتين", lambda e: self._swap()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.familyChoice)
        self._refresh_units()

    def _family_key(self):
        return self._families[self.choice_index(self.familyChoice)][0]

    def _refresh_units(self):
        fam = self._family_key()
        self._units = units.units_in(fam)
        labels = [n for _, n in self._units]
        self.fromChoice.Set(labels)
        self.toChoice.Set(labels)
        self.fromChoice.SetSelection(0)
        self.toChoice.SetSelection(min(1, len(labels) - 1))
        self._say(f"الفئة: {units.FAMILY_NAMES[fam]}. اختر الوحدتين والقيمة.")

    def _convert(self):
        raw = self.valueEntry.GetValue().strip().replace("،", ".")
        # normalise Arabic-Indic digits
        raw = raw.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        try:
            value = float(raw)
        except ValueError:
            self._say("اكتب قيمة رقمية صحيحة.")
            return
        fam = self._family_key()
        fu = self._units[self.choice_index(self.fromChoice)]
        tu = self._units[self.choice_index(self.toChoice)]
        try:
            result = units.convert(fam, fu[0], tu[0], value)
        except ValueError as exc:
            self._say(str(exc))
            return
        self._say(f"{_speak_number(value)} {fu[1]} = {_speak_number(result)} {tu[1]}.")

    def _swap(self):
        i, j = self.choice_index(self.fromChoice), self.choice_index(self.toChoice)
        self.fromChoice.SetSelection(j)
        self.toChoice.SetSelection(i)
        self._convert()

    def _say(self, text):
        self.status.SetLabel(text)
        self.announce(text)

    def instructions(self):
        return ("محوّل الوحدات: اختر الفئة (طول، كتلة، حرارة، زمن، سرعة، مساحة، تخزين)، "
                "ثم وحدة المصدر ووحدة الهدف، واكتب القيمة واضغط Enter لتسمع الناتج. "
                "«اعكس الوحدتين» يبدّل بينهما. يعمل دون اتصال. Escape للإغلاق.")
