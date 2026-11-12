# -*- coding: utf-8 -*-
"""
abaAcademy.gui.prayer_view
==========================

Offline prayer times and Qibla. Pick a city (or enter coordinates), a
calculation method and the Asr school; the day's times are listed, the next
prayer is announced with the time remaining, and a month's timetable can be
produced as text. The choices are remembered.
"""

from __future__ import annotations

import datetime
import math

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog, parse_float, parse_int
from ..tools import praytimes as pt
from ..tools import hijri

_CUSTOM = "custom"


class PrayerTimesDialog(ToolDialog):
    TITLE = "مواقيت الصلاة والقبلة (دون اتصال)"
    SIZE = (780, 680)
    SETTINGS_PREFIX = "prayer_"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self._city_keys = [c.key for c in pt.CITIES] + [_CUSTOM]
        labels = [f"{c.name} — {c.country}" for c in pt.CITIES] + ["موقع آخر (إحداثيات يدوية)"]
        saved = self.setting("city", "makkah")
        sel = self._city_keys.index(saved) if saved in self._city_keys else 0
        self.cityChoice = self.add_choice("المدينة", labels, sel, on_change=self._on_city)

        self.latEntry = self.add_entry("خطّ العرض (موجب للشمال)", self.setting("lat", ""))
        self.lonEntry = self.add_entry("خطّ الطول (موجب للشرق)", self.setting("lon", ""))
        self.tzEntry = self.add_entry("فرق التوقيت عن غرينتش بالساعات", self.setting("tz", ""))

        self._method_keys = list(pt.METHODS)
        mk = self.setting("method", "")
        self.methodChoice = self.add_choice(
            "طريقة الحساب", [pt.METHODS[k].name for k in self._method_keys],
            self._method_keys.index(mk) if mk in self._method_keys else 0,
            on_change=self._calc)
        self._asr_keys = list(pt.ASR_SCHOOLS)
        ak = self.setting("asr", "standard")
        self.asrChoice = self.add_choice("حساب العصر", [pt.ASR_SCHOOLS[k][0] for k in self._asr_keys],
                                         self._asr_keys.index(ak) if ak in self._asr_keys else 0,
                                         on_change=self._calc)
        self._hl_keys = list(pt.HIGH_LAT_RULES)
        hk = self.setting("high_lat", "angle")
        self.hlChoice = self.add_choice("تعديل خطوط العرض العليا",
                                        [pt.HIGH_LAT_RULES[k] for k in self._hl_keys],
                                        self._hl_keys.index(hk) if hk in self._hl_keys else 0,
                                        on_change=self._calc)
        self.clockChoice = self.add_choice("نظام الساعة", ["١٢ ساعة", "٢٤ ساعة"],
                                           1 if self.setting("clock", "12") == "24" else 0,
                                           on_change=self._calc)
        self.dateEntry = self.add_entry("التاريخ (فارغ = اليوم)", on_enter=self._calc,
                                        hint="مثل 2026-11-03")
        self.ramadanCheck = self.add_check("رمضان (يؤخّر العشاء في تقويم أم القرى)", False,
                                           on_change=self._calc)
        self.times = self.add_list("المواقيت", height=190)
        self.add_buttons([
            ("احسب", self._calc),
            ("الصلاة القادمة", self._next),
            ("اتجاه القبلة", self._qibla),
            ("جدول الشهر", self._month_table),
        ])
        self.add_output("التفاصيل", height=120)
        self.finish(self.cityChoice)
        self._on_city(initial=True)

    # -- inputs ----------------------------------------------------------
    def _city(self):
        key = self._city_keys[self.choice_index(self.cityChoice)]
        return None if key == _CUSTOM else pt.CITY_BY_KEY[key]

    def _on_city(self, initial: bool = False) -> None:
        c = self._city()
        if c is not None:
            self.latEntry.SetValue(f"{c.lat:g}")
            self.lonEntry.SetValue(f"{c.lon:g}")
            off = pt.utc_offset_hours(c.tz, self._date(), c.std_offset)
            self.tzEntry.SetValue(f"{off:g}")
            if not initial or not self.setting("method", ""):
                if c.method in self._method_keys:
                    self.methodChoice.SetSelection(self._method_keys.index(c.method))
        else:
            # a hand-entered place is most often where this computer is
            self.tzEntry.SetValue(f"{pt.local_offset_hours(self._date()):g}")
        self._calc(quiet=initial)

    def _date(self) -> datetime.date:
        raw = getattr(self, "dateEntry", None)
        text = raw.GetValue().strip() if raw is not None else ""
        if not text:
            return datetime.date.today()
        from ..study_hub.planner import parse_date
        return parse_date(text)

    def _inputs(self):
        try:
            lat = parse_float(self.latEntry.GetValue())
            lon = parse_float(self.lonEntry.GetValue())
        except ValueError:
            raise ValueError("اكتب خطّي العرض والطول أرقامًا عشرية، مثل 33.89 و35.50.")
        try:
            tz = parse_float(self.tzEntry.GetValue())
        except ValueError:
            tz = pt.local_offset_hours(self._date())
        c = self._city()
        if c is not None:
            tz = pt.utc_offset_hours(c.tz, self._date(), c.std_offset)
        settings = pt.Settings(
            method=self._method_keys[self.choice_index(self.methodChoice)],
            asr=self._asr_keys[self.choice_index(self.asrChoice)],
            high_lat=self._hl_keys[self.choice_index(self.hlChoice)],
            ramadan=self.ramadanCheck.GetValue())
        elev = c.elevation if c is not None else 0.0
        return lat, lon, tz, settings, elev

    def _save(self, lat, lon, tz, settings) -> None:
        self.set_setting("city", self._city_keys[self.choice_index(self.cityChoice)])
        self.set_setting("lat", f"{lat:g}")
        self.set_setting("lon", f"{lon:g}")
        self.set_setting("tz", f"{tz:g}")
        self.set_setting("method", settings.method)
        self.set_setting("asr", settings.asr)
        self.set_setting("high_lat", settings.high_lat)
        self.set_setting("clock", "24" if self.choice_index(self.clockChoice) == 1 else "12")

    # -- actions ---------------------------------------------------------
    def _calc(self, quiet: bool = False) -> None:
        try:
            lat, lon, tz, settings, elev = self._inputs()
            d = self._date()
        except ValueError as exc:
            if not quiet:
                self._say(str(exc))
            return
        twelve = self.choice_index(self.clockChoice) == 0
        rows = pt.day_table(lat, lon, d, tz, settings, elev, twelve_hour=twelve)
        self.times.Set([line for _, line, _ in rows])
        self.select_index(self.times, 1)
        self._save(lat, lon, tz, settings)
        hy, hm, hd = hijri.gregorian_to_hijri(d.year, d.month, d.day)
        head = (f"{hijri.format_gregorian(d.year, d.month, d.day, d.weekday())}، "
                f"{hijri.format_hijri(hy, hm, hd)}. الطريقة: {pt.METHODS[settings.method].name}.")
        if self.output is not None:
            self.output.SetValue(head)
        if not quiet:
            self.announce(head + " " + "، ".join(line for k, line, _ in rows
                                                 if k in pt.PRAYER_KEYS))

    def _next(self) -> None:
        lat, lon, tz, settings, elev = self._inputs()
        now = datetime.datetime.now()
        c = self._city()
        if c is not None:
            # the city's clock, not this computer's, when it is elsewhere
            local = pt.local_offset_hours(now.date())
            now = now + datetime.timedelta(hours=tz - local)
        key, hours, mins = pt.next_prayer(lat, lon, now, tz, settings, elev)
        h, m = divmod(max(0, mins), 60)
        left = (f"{h} ساعة و{m} دقيقة" if h else f"{m} دقيقة")
        twelve = self.choice_index(self.clockChoice) == 0
        self.show_output(f"الصلاة القادمة: {pt.PRAYER_NAMES[key]} عند "
                         f"{pt.format_time(hours, twelve)}، بعد {left}.")

    def _qibla(self) -> None:
        lat, lon, _tz, _s, _e = self._inputs()
        self.show_output(pt.qibla_description(lat, lon))

    def _month_table(self) -> None:
        lat, lon, tz, settings, elev = self._inputs()
        d0 = self._date().replace(day=1)
        twelve = self.choice_index(self.clockChoice) == 0
        lines = []
        d = d0
        while d.month == d0.month:
            c = self._city()
            off = pt.utc_offset_hours(c.tz, d, c.std_offset) if c is not None else tz
            t = pt.PrayerCalculator(lat, lon, elev, settings).compute(d, off)
            parts = [pt.format_time(t[k], twelve) for k in pt.PRAYER_KEYS]
            lines.append(f"{d.day} {hijri.gregorian_month_name(d.month)}: "
                         + "، ".join(f"{pt.PRAYER_NAMES[k]} {v}" for k, v in zip(pt.PRAYER_KEYS, parts)))
            d += datetime.timedelta(days=1)
        self.show_output("\n".join(lines),
                         speak=f"جدول شهر {hijri.gregorian_month_name(d0.month)} جاهز في مربّع التفاصيل.",
                         focus=True)

    def instructions(self) -> str:
        return ("اختر المدينة أو أدخل إحداثيات موقعك، ثم طريقة الحساب. تظهر المواقيت في القائمة "
                "وتُحسب دون اتصال بالإنترنت. الصلاة القادمة تخبرك بالوقت المتبقّي، "
                "واتجاه القبلة يذكر الزاوية من الشمال وما يقابلها على الساعة. "
                "قد تزيد بعض المساجد دقيقة أو اثنتين احتياطًا.")
