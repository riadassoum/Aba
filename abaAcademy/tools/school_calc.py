# -*- coding: utf-8 -*-
"""
abaAcademy.tools.school_calc
============================

Everyday school calculations:

* **Grade average** (المعدّل): a weighted average of subject marks by
  credit hours or coefficients, with the letter grade and the 4.0 grade
  point of each mark on the commonly used scale (A ≥ 90 … F < 60).
* **What do I need?** (كم أحتاج): the mark needed in the remaining part of a
  course to reach a target average.
* **Date difference and age**, in days, weeks, months and years, for
  Gregorian or Hijri dates.

Grading scales differ between schools and universities; the screen states
which scale it uses.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

# (minimum percentage, letter, grade points, Arabic label)
SCALE = (
    (90, "A", 4.0, "ممتاز"),
    (85, "B+", 3.5, "جيّد جدًّا مرتفع"),
    (80, "B", 3.0, "جيّد جدًّا"),
    (75, "C+", 2.5, "جيّد مرتفع"),
    (70, "C", 2.0, "جيّد"),
    (65, "D+", 1.5, "مقبول مرتفع"),
    (60, "D", 1.0, "مقبول"),
    (0, "F", 0.0, "راسب"),
)


# the /20 scale of Lebanese, Maghrebi and French-system schools:
# (minimum mark out of 20, mention)
SCALE_20 = (
    (16, "ممتاز"),
    (14, "جيّد جدًّا"),
    (12, "جيّد"),
    (10, "مقبول (ناجح)"),
    (0, "راسب"),
)


def mention_20(mark20: float) -> str:
    for low, label in SCALE_20:
        if mark20 >= low:
            return label
    return "راسب"


def report_20(subjects: Sequence["Subject"]) -> Tuple[float, List[str]]:
    """The same subjects averaged on the /20 scale with coefficients."""
    total_w = sum(s.weight for s in subjects)
    avg20 = sum(s.percent / 5.0 * s.weight for s in subjects) / total_w
    lines = []
    for s in subjects:
        m = s.percent / 5.0
        lines.append(f"{s.name}: {m:.2f} على 20 ({mention_20(m)})"
                     + (f"، المعامل {s.weight:g}" if s.weight != 1 else ""))
    lines.append(f"المعدّل العام: {avg20:.2f} على 20 — {mention_20(avg20)}.")
    if avg20 < 10:
        need = (10 * total_w - sum(s.percent / 5.0 * s.weight for s in subjects))
        lines.append(f"ينقصك {need:.2f} نقطة موزونة لتبلغ معدّل النجاح ١٠.")
    return avg20, lines


def letter(percent: float) -> Tuple[str, float, str]:
    for low, l, pts, label in SCALE:
        if percent >= low:
            return l, pts, label
    return "F", 0.0, "راسب"


@dataclass
class Subject:
    name: str
    mark: float          # obtained
    out_of: float = 100.0
    weight: float = 1.0  # credit hours / coefficient

    @property
    def percent(self) -> float:
        return 100.0 * self.mark / self.out_of if self.out_of else 0.0


def parse_subjects(text: str) -> List[Subject]:
    """One subject per line: الاسم، العلامة، من، الوزن — the last two are
    optional (رياضيات 85 or فيزياء، 17، 20، 3)."""
    out = []
    tr = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")
    for ln, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.replace("،", ",").replace("\t", ",").split(",") if p.strip()]
        if len(parts) == 1:
            bits = parts[0].rsplit(" ", 1)
            parts = bits if len(bits) == 2 else parts
        name = parts[0]
        nums = []
        for p in parts[1:]:
            try:
                nums.append(float(p.translate(tr).replace("/", " ").split()[0]))
            except (ValueError, IndexError):
                raise ValueError(f"السطر {ln}: {p} ليس رقمًا.")
            if "/" in p:
                try:
                    nums.append(float(p.translate(tr).split("/")[1]))
                except ValueError:
                    pass
        if not nums:
            raise ValueError(f"السطر {ln}: أين العلامة؟")
        mark = nums[0]
        out_of = nums[1] if len(nums) > 1 else 100.0
        weight = nums[2] if len(nums) > 2 else 1.0
        if out_of <= 0 or weight <= 0 or mark < 0 or mark > out_of:
            raise ValueError(f"السطر {ln}: تحقّق من العلامة والمجموع والوزن.")
        out.append(Subject(name, mark, out_of, weight))
    if not out:
        raise ValueError("اكتب مادّة واحدة على الأقلّ.")
    return out


def average_report(subjects: Sequence[Subject]) -> Tuple[float, float, List[str]]:
    total_w = sum(s.weight for s in subjects)
    avg = sum(s.percent * s.weight for s in subjects) / total_w
    gpa = sum(letter(s.percent)[1] * s.weight for s in subjects) / total_w
    lines = []
    for s in sorted(subjects, key=lambda s: -s.percent):
        l, pts, label = letter(s.percent)
        lines.append(f"{s.name}: {s.mark:g} من {s.out_of:g} = {s.percent:.1f}٪ ({l}، {label})"
                     + (f"، الوزن {s.weight:g}" if s.weight != 1 else ""))
    l, _, label = letter(avg)
    lines.append(f"المعدّل الموزون: {avg:.2f}٪ ({l}، {label})، والمعدّل التراكمي {gpa:.2f} من 4.")
    weakest = min(subjects, key=lambda s: s.percent)
    if len(subjects) > 1:
        lines.append(f"أضعف مادّة: {weakest.name} ({weakest.percent:.1f}٪).")
    return avg, gpa, lines


def needed_mark(current_percent: float, current_weight: float, target: float) -> Tuple[Optional[float], str]:
    """Mark (in %) needed on the remaining part, which weighs 100 − current
    weight percent of the course, to finish at ``target``."""
    if not 0 < current_weight < 100:
        raise ValueError("وزن ما أنجزته يجب أن يكون بين ٠ و١٠٠٪.")
    rest = 100 - current_weight
    need = (target * 100 - current_percent * current_weight) / rest
    if need > 100:
        return None, (f"لا يمكن بلوغ {target:g}٪: حتى العلامة الكاملة في الباقي تعطيك "
                      f"{(current_percent * current_weight + 100 * rest) / 100:.1f}٪.")
    if need <= 0:
        return 0.0, f"بلغت {target:g}٪ مهما كانت علامتك في الباقي."
    return need, f"تحتاج {need:.1f}٪ في الجزء الباقي ({rest:g}٪ من المادّة) لتصل إلى {target:g}٪."


def date_difference(a: datetime.date, b: datetime.date) -> str:
    if b < a:
        a, b = b, a
    days = (b - a).days
    years = b.year - a.year - ((b.month, b.day) < (a.month, a.day))
    months_total = (b.year - a.year) * 12 + b.month - a.month - (b.day < a.day)
    months = months_total - years * 12
    anchor_m = a.month + months_total
    y = a.year + (anchor_m - 1) // 12
    m = (anchor_m - 1) % 12 + 1
    import calendar
    d = min(a.day, calendar.monthrange(y, m)[1])
    rem_days = (b - datetime.date(y, m, d)).days
    from .ar_count import count
    parts = []
    if years:
        parts.append(count(years, "year"))
    if months:
        parts.append(count(months, "month"))
    if rem_days or not parts:
        parts.append(count(rem_days, "day"))
    weeks = f"{count(days // 7, 'week')}" + (f" و{count(days % 7, 'day')}" if days % 7 else "")
    return f"الفرق: {' و'.join(parts)}، أي {count(days, 'day')}، أو {weeks}."


def age_text(birth: datetime.date, today: Optional[datetime.date] = None) -> str:
    today = today or datetime.date.today()
    if birth > today:
        raise ValueError("تاريخ الميلاد بعد اليوم.")
    from . import hijri
    years = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    hb = hijri.gregorian_to_hijri(birth.year, birth.month, birth.day)
    ht = hijri.gregorian_to_hijri(today.year, today.month, today.day)
    hyears = ht[0] - hb[0] - ((ht[1], ht[2]) < (hb[1], hb[2]))
    nxt = birth.replace(year=today.year) if not (birth.month == 2 and birth.day == 29) else \
        datetime.date(today.year, 3, 1)
    if nxt < today:
        nxt = nxt.replace(year=today.year + 1)
    from .ar_count import count
    return (f"العمر بالتقويم الميلادي {count(years, 'year')}، وبالهجري {count(hyears, 'year')}. "
            f"عشت {count((today - birth).days, 'day')}. "
            + ("ذكرى ميلادك اليوم." if nxt == today
               else f"تبقى على ذكرى ميلادك {count((nxt - today).days, 'day')}."))
