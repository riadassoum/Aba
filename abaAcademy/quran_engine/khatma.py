# -*- coding: utf-8 -*-
"""
abaAcademy.quran_engine.khatma
==============================

The khatma planner (خطّة الختمة): finish the Qur'an in a chosen number of
days, by pages of the Madani mushaf (604 pages), by juz', or by ayat, and
see every day's portion as a start and end ayah.

Portions are cut on ayah boundaries from the bundled Qur'an data (each ayah
carries its page and juz'), so today's portion can open straight in the
Qur'an reader. The plan tracks the last ayah read and says whether the
reader is ahead of or behind schedule, and how much a day now needs to
finish on time.
"""

from __future__ import annotations

import datetime
import json
import math
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ..tools.ar_count import count

KEY = "khatma_plan"
UNITS = {"pages": "صفحات", "juz": "أجزاء", "ayat": "آيات"}
TOTAL_PAGES = 604
TOTAL_JUZ = 30

# ayah row layout in quran_data.json
S, A, N, JUZ, PAGE, HQ, TEXT = range(7)


@dataclass
class Portion:
    day: int
    date: str
    start: int          # global ayah number (1-based)
    end: int
    pages: Tuple[int, int]
    juz: Tuple[int, int]


@dataclass
class Plan:
    unit: str
    days: int
    start_date: str
    start_ayah: int = 1
    last_read: int = 0          # global ayah number reached (0 = none)
    history: List[List] = field(default_factory=list)     # [iso_date, global_ayah]

    @property
    def start(self) -> datetime.date:
        return datetime.date.fromisoformat(self.start_date)

    @property
    def end_date(self) -> datetime.date:
        return self.start + datetime.timedelta(days=self.days - 1)


def days_word(n: int) -> str:
    if n == 1:
        return "يوم واحد"
    if n == 2:
        return "يومين"
    if 3 <= n <= 10:
        return f"{n} أيام"
    return f"{n} يومًا"


class QuranIndex:
    """Ayah metadata for slicing: page, juz and surah of every ayah."""

    def __init__(self, ayat: Sequence[Sequence], surahs: Sequence[dict]):
        self.ayat = list(ayat)
        self.surahs = list(surahs)
        self.total = len(self.ayat)
        self._first_of_page: Dict[int, int] = {}
        self._first_of_juz: Dict[int, int] = {}
        for row in self.ayat:
            self._first_of_page.setdefault(row[PAGE], row[N])
            self._first_of_juz.setdefault(row[JUZ], row[N])

    @classmethod
    def load(cls, path: str) -> "QuranIndex":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(data["ayat"], data["surahs"])

    def row(self, global_n: int):
        return self.ayat[max(1, min(self.total, global_n)) - 1]

    def label(self, global_n: int) -> str:
        r = self.row(global_n)
        name = self.surahs[r[S] - 1]["name"]
        for prefix in ("سُورَةُ ", "سورة "):
            if name.startswith(prefix):
                name = name[len(prefix):]
        return f"{name} {r[A]}"

    def last_of_page(self, page: int) -> int:
        nxt = self._first_of_page.get(page + 1)
        return (nxt - 1) if nxt else self.total

    def last_of_juz(self, juz: int) -> int:
        nxt = self._first_of_juz.get(juz + 1)
        return (nxt - 1) if nxt else self.total

    def first_of_page(self, page: int) -> int:
        return self._first_of_page.get(page, 1)

    def global_of(self, surah: int, ayah: int) -> Optional[int]:
        for row in self.ayat:
            if row[S] == surah and row[A] == ayah:
                return row[N]
        return None


def make_portions(index: QuranIndex, plan: Plan) -> List[Portion]:
    """Cut the remaining text (from ``start_ayah``) into ``days`` portions as
    even as the unit allows, always ending on a whole ayah."""
    start = max(1, plan.start_ayah)
    days = max(1, plan.days)
    out: List[Portion] = []
    if plan.unit == "ayat":
        remaining = index.total - start + 1
        per = remaining / days
        cur = start
        for d in range(days):
            end = start - 1 + round(per * (d + 1))
            end = max(cur, min(index.total, end))
            if d == days - 1:
                end = index.total
            out.append(_portion(index, plan, d, cur, end))
            cur = end + 1
            if cur > index.total:
                break
        return out
    if plan.unit == "juz":
        first_unit = index.row(start)[JUZ]
        units = list(range(first_unit, TOTAL_JUZ + 1))
        last_of = index.last_of_juz
    else:
        first_unit = index.row(start)[PAGE]
        units = list(range(first_unit, TOTAL_PAGES + 1))
        last_of = index.last_of_page
    per = len(units) / days
    cur = start
    for d in range(days):
        idx = min(len(units) - 1, max(0, math.ceil(per * (d + 1)) - 1))
        end = last_of(units[idx])
        if d == days - 1:
            end = index.total
        if end < cur:
            continue
        out.append(_portion(index, plan, d, cur, end))
        cur = end + 1
        if cur > index.total:
            break
    return out


def _portion(index, plan, d, start, end) -> Portion:
    a, b = index.row(start), index.row(end)
    date = (plan.start + datetime.timedelta(days=d)).isoformat()
    return Portion(d + 1, date, start, end, (a[PAGE], b[PAGE]), (a[JUZ], b[JUZ]))


def portion_text(index: QuranIndex, p: Portion) -> str:
    pages = (f"الصفحة {p.pages[0]}" if p.pages[0] == p.pages[1]
             else f"الصفحات {p.pages[0]} إلى {p.pages[1]}")
    return (f"اليوم {p.day} ({p.date}): من {index.label(p.start)} إلى {index.label(p.end)}، "
            f"{pages}، {count(p.end - p.start + 1, 'ayah')}.")


class KhatmaStore:
    def __init__(self, store):
        self.store = store

    def load(self) -> Optional[Plan]:
        try:
            raw = json.loads(self.store.get_setting(KEY, "") or "null")
            return Plan(**raw) if raw else None
        except Exception:
            return None

    def save(self, plan: Optional[Plan]) -> None:
        self.store.set_setting(KEY, json.dumps(asdict(plan), ensure_ascii=False) if plan else "")

    def create(self, unit: str, days: int, start_date: Optional[datetime.date] = None,
               start_ayah: int = 1) -> Plan:
        if unit not in UNITS:
            raise ValueError(unit)
        if not 1 <= days <= 3650:
            raise ValueError("عدد الأيام بين ١ و٣٦٥٠.")
        plan = Plan(unit, int(days), (start_date or datetime.date.today()).isoformat(),
                    max(1, int(start_ayah)))
        self.save(plan)
        return plan

    def mark_read(self, plan: Plan, global_ayah: int,
                  day: Optional[datetime.date] = None) -> Plan:
        plan.last_read = max(plan.last_read, int(global_ayah))
        plan.history.append([(day or datetime.date.today()).isoformat(), plan.last_read])
        self.save(plan)
        return plan


def status(index: QuranIndex, plan: Plan, today: Optional[datetime.date] = None) -> List[str]:
    today = today or datetime.date.today()
    portions = make_portions(index, plan)
    if not portions:
        return ["الخطّة فارغة."]
    day_no = (today - plan.start).days + 1
    lines = []
    total_ayat = index.total - plan.start_ayah + 1
    read = max(0, plan.last_read - plan.start_ayah + 1)
    pct = round(100 * read / total_ayat) if total_ayat else 0
    lines.append(f"ختمة في {days_word(plan.days)} بال{UNITS[plan.unit]}، من {plan.start_date} "
                 f"إلى {plan.end_date.isoformat()}.")
    if plan.last_read >= index.total:
        lines.append("أتممت الختمة. تقبّل الله منك.")
        return lines
    if plan.last_read:
        lines.append(f"آخر ما قرأت: {index.label(plan.last_read)}، أي {pct}٪ من الختمة.")
    else:
        lines.append("لم تسجّل قراءة بعد.")
    if day_no < 1:
        lines.append(f"تبدأ الخطّة بعد {days_word(1 - day_no)}.")
        lines.append(portion_text(index, portions[0]))
        return lines
    if day_no > len(portions):
        lines.append("انتهت مدّة الخطّة ولم تكتمل الختمة؛ أنشئ خطّة جديدة من حيث وصلت.")
        return lines
    today_p = portions[day_no - 1]
    lines.append("ورد اليوم: " + portion_text(index, today_p))
    expected_end = portions[day_no - 2].end if day_no >= 2 else plan.start_ayah - 1
    behind = expected_end - plan.last_read
    if behind > 0:
        days_left = len(portions) - day_no + 1
        need = index.total - plan.last_read
        lines.append(f"أنت متأخّر بنحو {count(behind, 'ayah')} عن الخطّة. لتختم في موعدك تحتاج "
                     f"{count(math.ceil(need / days_left), 'ayah')} يوميًّا فيما بقي ({days_word(days_left)}).")
    elif plan.last_read >= today_p.end:
        lines.append("أنهيت ورد اليوم. بارك الله فيك.")
    elif plan.last_read > expected_end:
        lines.append("أنت على الخطّة، وقد بدأت ورد اليوم.")
    else:
        lines.append("أنت على الخطّة.")
    return lines


def suggested_days() -> List[Tuple[int, str]]:
    return [(30, "شهر (جزء يوميًّا)"), (60, "شهران (نصف جزء يوميًّا)"),
            (10, "عشرة أيام (ثلاثة أجزاء يوميًّا)"), (7, "أسبوع (نحو أربعة أجزاء ونصف يوميًّا)"),
            (15, "خمسة عشر يومًا (جزءان يوميًّا)"), (120, "أربعة أشهر (ربع جزء يوميًّا)"),
            (365, "سنة (نحو صفحتين يوميًّا)")]
