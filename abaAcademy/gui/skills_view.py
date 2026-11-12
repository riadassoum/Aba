# -*- coding: utf-8 -*-
"""
abaAcademy.gui.skills_view
==========================

The zakat calculator.
"""

from __future__ import annotations

import random

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog, parse_float
from ..tools import zakat


class ZakatDialog(ToolDialog):
    TITLE = "حاسبة زكاة المال"
    SIZE = (760, 720)
    SETTINGS_PREFIX = "zakat_"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.add_text(zakat.NOTE)
        self.fields = {}
        for key, label in zakat.ASSET_FIELDS + zakat.LIABILITY_FIELDS:
            self.fields[key] = self.add_entry(label, "")
        self.goldPrice = self.add_entry("سعر غرام الذهب عيار ٢٤ اليوم بعملتك", self.setting("gold", ""))
        self.silverPrice = self.add_entry("سعر غرام الفضّة اليوم بعملتك", self.setting("silver", ""))
        self.karatChoice = self.add_choice("عيار الذهب الذي تملكه", ["٢٤", "٢٢", "٢١", "١٨"], 0)
        self.standardChoice = self.add_choice("النصاب بحسب", ["الذهب (٨٥ غرامًا)", "الفضّة (٥٩٥ غرامًا)"],
                                              1 if self.setting("standard", "gold") == "silver" else 0)
        self.yearCheck = self.add_check("مضى على المال عام هجري كامل (حال عليه الحول)", True)
        self.add_buttons([("احسب الزكاة", self._calc)])
        self.add_output("النتيجة", height=150)
        self.finish(self.fields["cash"])

    def _num(self, ctrl) -> float:
        t = ctrl.GetValue().strip()
        if not t:
            return 0.0
        try:
            return parse_float(t)
        except ValueError:
            raise ValueError(f"القيمة {t} ليست رقمًا.")

    def _calc(self) -> None:
        values = {k: self._num(c) for k, c in self.fields.items()}
        gold = self._num(self.goldPrice)
        silver = self._num(self.silverPrice)
        karat = (24, 22, 21, 18)[self.choice_index(self.karatChoice)]
        std = "silver" if self.choice_index(self.standardChoice) == 1 else "gold"
        res = zakat.calculate(zakat.ZakatInput(values, gold, silver, std, karat,
                                               self.yearCheck.GetValue()))
        if gold:
            self.set_setting("gold", f"{gold:g}")
        if silver:
            self.set_setting("silver", f"{silver:g}")
        self.set_setting("standard", std)
        self.show_output("\n".join(res.lines), speak=res.lines[-1])

    def instructions(self) -> str:
        return ("أدخل ما تملكه من نقد وذهب وفضّة وعروض تجارة، وما عليك من ديون حالّة، "
                "وسعر الغرام اليوم، ثم احسب الزكاة. الحاسبة للحالة الشائعة؛ "
                "واسأل أهل العلم في التفاصيل.")
