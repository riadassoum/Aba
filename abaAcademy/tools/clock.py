# -*- coding: utf-8 -*-
"""
abaAcademy.tools.clock
======================

A talking clock: the time and date spoken in Arabic (with the Hijri date),
a stopwatch with laps, a countdown timer, and the time now in the cities of
the prayer-times list (DST-aware where the zone database is available).
Pure logic; the screen drives it with a timer.
"""

from __future__ import annotations

import datetime
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from . import hijri
from .ar_count import count

_PERIODS = ((3, "ليلًا"), (6, "فجرًا"), (12, "صباحًا"), (15, "ظهرًا"), (18, "عصرًا"), (24, "مساءً"))


def spoken_time(t: datetime.datetime, twelve_hour: bool = True) -> str:
    h, m = t.hour, t.minute
    if not twelve_hour:
        return f"الساعة {h:02d}:{m:02d}"
    h12 = h % 12 or 12
    period = next(p for limit, p in _PERIODS if h < limit)
    if m == 0:
        mins = "تمامًا"
    elif m == 15:
        mins = "والربع"
    elif m == 30:
        mins = "والنصف"
    elif m == 45:
        h12 = (h12 % 12) + 1
        mins = "إلا ربعًا"
    else:
        mins = f"و{count(m, 'minute')}"
    return f"الساعة {h12} {mins} {period}"


def spoken_date(d: datetime.date) -> str:
    hy, hm, hd = hijri.gregorian_to_hijri(d.year, d.month, d.day)
    return (f"{hijri.weekday_name(d.weekday())} {d.day} {hijri.gregorian_month_name(d.month)} {d.year}، "
            f"الموافق {hd} {hijri.hijri_month_name(hm)} {hy} هـ")


def spoken_duration(seconds: float, tenths: bool = False) -> str:
    s = max(0.0, seconds)
    h, rem = divmod(int(s), 3600)
    m, sec = divmod(rem, 60)
    parts = []
    if h:
        parts.append(count(h, "hour"))
    if m:
        parts.append(count(m, "minute"))
    if sec or not parts:
        if tenths:
            parts.append(f"{sec + (s - int(s)):.1f} ثانية")
        else:
            parts.append(count(sec, "second"))
    return " و".join(parts)


def clock_text(seconds: float) -> str:
    s = int(max(0, seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


@dataclass
class Stopwatch:
    started: Optional[float] = None
    accumulated: float = 0.0
    laps: List[float] = field(default_factory=list)

    def now(self) -> float:
        return time.monotonic()

    @property
    def running(self) -> bool:
        return self.started is not None

    def elapsed(self) -> float:
        return self.accumulated + ((self.now() - self.started) if self.started is not None else 0.0)

    def start(self) -> None:
        if self.started is None:
            self.started = self.now()

    def stop(self) -> None:
        if self.started is not None:
            self.accumulated += self.now() - self.started
            self.started = None

    def lap(self) -> Tuple[int, float, float]:
        """(lap number, lap time, total)."""
        total = self.elapsed()
        prev = sum(self.laps)
        self.laps.append(total - prev)
        return len(self.laps), total - prev, total

    def reset(self) -> None:
        self.started = None
        self.accumulated = 0.0
        self.laps = []


@dataclass
class Countdown:
    duration: float = 0.0
    started: Optional[float] = None
    remaining_when_paused: float = 0.0
    announced: set = field(default_factory=set)

    def now(self) -> float:
        return time.monotonic()

    def set(self, seconds: float) -> None:
        if seconds <= 0:
            raise ValueError("اختر مدّة أكبر من صفر.")
        self.duration = seconds
        self.remaining_when_paused = seconds
        self.started = None
        self.announced = set()

    def start(self) -> None:
        if self.remaining_when_paused <= 0:
            raise ValueError("اضبط المدّة أوّلًا.")
        if self.started is None:
            self.started = self.now()

    def pause(self) -> None:
        if self.started is not None:
            self.remaining_when_paused = self.remaining()
            self.started = None

    @property
    def running(self) -> bool:
        return self.started is not None

    def remaining(self) -> float:
        if self.started is None:
            return self.remaining_when_paused
        return max(0.0, self.remaining_when_paused - (self.now() - self.started))

    def tick(self) -> Optional[str]:
        """Call often; returns an announcement at milestones (and once at 0)."""
        if self.started is None:
            return None
        r = self.remaining()
        if r <= 0:
            self.started = None
            self.remaining_when_paused = 0.0
            return "انتهى الوقت!"
        due = [m for m in (3600, 1800, 600, 300, 60, 30, 10, 5, 4, 3, 2, 1)
               if r <= m < self.duration and m not in self.announced]
        if due:
            # after a late tick, skip milestones already passed: say the nearest
            self.announced.update(due)
            mark = min(due)
            return ("بقي " + spoken_duration(mark)) if mark > 5 else str(mark)
        return None


def parse_duration(text: str) -> float:
    """'5' (minutes), '1:30' (m:s), '1:02:00' (h:m:s), '90ث', '2د', '1س'."""
    t = text.strip().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")).replace(" ", "")
    if not t:
        raise ValueError("اكتب المدّة.")
    try:
        if ":" in t:
            parts = [float(p) for p in t.split(":")]
            secs = 0.0
            for p in parts:
                secs = secs * 60 + p
            return secs
        units = {"ث": 1, "s": 1, "د": 60, "m": 60, "س": 3600, "h": 3600}
        if t[-1] in units:
            return float(t[:-1]) * units[t[-1]]
        return float(t) * 60
    except ValueError:
        raise ValueError("اكتب المدّة بالدقائق، أو د:ث، أو س:د:ث، مثل 5 أو 1:30.")


def world_times(now_utc: Optional[datetime.datetime] = None) -> List[str]:
    from .praytimes import CITIES, utc_offset_hours
    now_utc = now_utc or datetime.datetime.now(datetime.timezone.utc)
    seen = set()
    out = []
    for c in CITIES:
        if c.tz in seen and c.country in {x.split("—")[-1].strip() for x in out}:
            continue
        seen.add(c.tz)
        off = utc_offset_hours(c.tz, now_utc.date(), c.std_offset)
        local = now_utc + datetime.timedelta(hours=off)
        sign = "+" if off >= 0 else "−"
        out.append(f"{c.name}: {local.hour:02d}:{local.minute:02d} (غرينتش {sign}{abs(off):g}) — {c.country}")
    return out
