# -*- coding: utf-8 -*-
"""
abaAcademy.study_hub.planner
============================

The study planner (مخطّط المذاكرة): exams, homework and personal goals with
due dates, and a daily plan that spreads the remaining study time evenly
over the days left.

Every item has an estimate of the study minutes it needs; logging minutes
against it (or finishing a pomodoro tagged with its subject) reduces what's
left. خطّة اليوم then says, for each open item, how many minutes today
keeps it on track — so a learner who falls behind sees the daily load rise
instead of discovering it the night before the exam.

Stored as JSON in the academy's settings (key ``study_planner``).
"""

from __future__ import annotations

import datetime
import json
import math
import uuid
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

KEY = "study_planner"

KINDS = {"exam": "امتحان", "homework": "واجب", "project": "مشروع", "goal": "هدف شخصي"}


@dataclass
class Item:
    id: str
    title: str
    kind: str
    subject: str
    due: str                    # ISO date
    minutes_needed: int
    minutes_done: int = 0
    done: bool = False
    notes: str = ""
    log: List[List] = field(default_factory=list)      # [iso_date, minutes]

    @property
    def due_date(self) -> datetime.date:
        return datetime.date.fromisoformat(self.due)

    def days_left(self, today: Optional[datetime.date] = None) -> int:
        today = today or datetime.date.today()
        return (self.due_date - today).days

    @property
    def minutes_left(self) -> int:
        return max(0, self.minutes_needed - self.minutes_done)

    def daily_minutes(self, today: Optional[datetime.date] = None) -> int:
        """Minutes per day from today until the day before it's due (on the
        day itself for homework and goals)."""
        if self.done or not self.minutes_left:
            return 0
        days = self.days_left(today)
        span = days if self.kind == "exam" else days + 1
        if span <= 0:
            return self.minutes_left
        return int(math.ceil(self.minutes_left / span))

    def progress(self) -> int:
        if not self.minutes_needed:
            return 100 if self.done else 0
        return min(100, round(100 * self.minutes_done / self.minutes_needed))


def _when(days: int) -> str:
    if days < 0:
        return f"فات موعده منذ {-days} يوم" if days < -1 else "فات موعده أمس"
    if days == 0:
        return "اليوم"
    if days == 1:
        return "غدًا"
    if days == 2:
        return "بعد غد"
    return f"بعد {days} يومًا" if days > 10 else f"بعد {days} أيام"


class Planner:
    def __init__(self, store):
        self.store = store

    def _load(self) -> List[Item]:
        try:
            raw = json.loads(self.store.get_setting(KEY, "[]") or "[]")
            return [Item(**{k: v for k, v in r.items() if k in Item.__dataclass_fields__})
                    for r in raw]
        except Exception:
            return []

    def _save(self, items: List[Item]) -> None:
        self.store.set_setting(KEY, json.dumps([asdict(i) for i in items], ensure_ascii=False))

    def items(self, include_done: bool = False) -> List[Item]:
        out = [i for i in self._load() if include_done or not i.done]
        out.sort(key=lambda i: (i.done, i.due, i.title))
        return out

    def add(self, title: str, due: datetime.date, kind: str = "exam", subject: str = "",
            minutes_needed: int = 120, notes: str = "") -> Item:
        title = " ".join((title or "").split())
        if not title:
            raise ValueError("اكتب عنوانًا.")
        if kind not in KINDS:
            raise ValueError(kind)
        item = Item(uuid.uuid4().hex[:10], title, kind, subject.strip(), due.isoformat(),
                    max(0, int(minutes_needed)), notes=notes.strip())
        items = self._load()
        items.append(item)
        self._save(items)
        return item

    def update(self, item_id: str, **fields) -> bool:
        items = self._load()
        for i in items:
            if i.id == item_id:
                for k, v in fields.items():
                    if k == "due" and isinstance(v, datetime.date):
                        v = v.isoformat()
                    if k in Item.__dataclass_fields__ and k != "id":
                        setattr(i, k, v)
                self._save(items)
                return True
        return False

    def delete(self, item_id: str) -> bool:
        items = self._load()
        new = [i for i in items if i.id != item_id]
        if len(new) == len(items):
            return False
        self._save(new)
        return True

    def log_minutes(self, item_id: str, minutes: int,
                    day: Optional[datetime.date] = None) -> Optional[Item]:
        if minutes <= 0:
            return None
        items = self._load()
        for i in items:
            if i.id == item_id:
                i.minutes_done += int(minutes)
                i.log.append([(day or datetime.date.today()).isoformat(), int(minutes)])
                if i.minutes_done >= i.minutes_needed and i.kind != "exam":
                    i.done = True
                self._save(items)
                return i
        return None

    def log_subject(self, subject: str, minutes: int) -> Optional[Item]:
        """Credit study time to the soonest open item of that subject (used
        when a pomodoro tagged with a subject finishes)."""
        subject = (subject or "").strip()
        if not subject:
            return None
        for i in self.items():
            if i.subject == subject and i.days_left() >= 0:
                return self.log_minutes(i.id, minutes)
        return None

    def set_done(self, item_id: str, done: bool = True) -> bool:
        return self.update(item_id, done=done)

    # -- summaries -------------------------------------------------------
    def describe(self, i: Item, today: Optional[datetime.date] = None) -> str:
        parts = [f"{KINDS.get(i.kind, i.kind)}: {i.title}"]
        if i.subject:
            parts.append(f"({i.subject})")
        if i.done:
            parts.append("— أُنجز")
            return " ".join(parts)
        text = " ".join(parts) + f" — {_when(i.days_left(today))} ({i.due})"
        if i.minutes_needed:
            text += f"، أنجزت {i.progress()}٪، وبقي {i.minutes_left} دقيقة"
            d = i.daily_minutes(today)
            if d:
                text += f"، أي {d} دقيقة يوميًّا"
        return text

    def today_plan(self, today: Optional[datetime.date] = None) -> List[str]:
        today = today or datetime.date.today()
        lines = []
        total = 0
        for i in self.items():
            d = i.daily_minutes(today)
            days = i.days_left(today)
            if days < 0:
                lines.append(f"متأخّر: {i.title} — {_when(days)}، بقي {i.minutes_left} دقيقة.")
                continue
            if d:
                total += d
                lines.append(f"{i.title}: {d} دقيقة اليوم ({KINDS.get(i.kind, i.kind)} {_when(days)}).")
            elif days <= 1:
                lines.append(f"{i.title}: {_when(days)}.")
        if not lines:
            return ["لا شيء مطلوب اليوم. أضف امتحانًا أو واجبًا لتبدأ خطّتك."]
        head = f"خطّة اليوم: {total} دقيقة مذاكرة إجمالًا." if total else "خطّة اليوم:"
        return [head] + lines

    def upcoming(self, days: int = 7, today: Optional[datetime.date] = None) -> List[Item]:
        today = today or datetime.date.today()
        return [i for i in self.items() if 0 <= i.days_left(today) <= days]

    def week_minutes(self, today: Optional[datetime.date] = None) -> Dict[str, int]:
        """Minutes logged per day over the last seven days (oldest first)."""
        today = today or datetime.date.today()
        days = [(today - datetime.timedelta(days=k)).isoformat() for k in range(6, -1, -1)]
        out = {d: 0 for d in days}
        for i in self._load():
            for day, mins in i.log:
                if day in out:
                    out[day] += int(mins)
        return out

    def subjects(self) -> List[str]:
        seen = []
        for i in self._load():
            if i.subject and i.subject not in seen:
                seen.append(i.subject)
        return seen


def parse_date(text: str, today: Optional[datetime.date] = None) -> datetime.date:
    """Accepts 2026-11-03, 3/11/2026, 3-11 (this year), or a number of days
    from today ('5' or '+5'), and the words اليوم / غدًا / بعد غد."""
    today = today or datetime.date.today()
    t = (text or "").strip().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    words = {"اليوم": 0, "غدا": 1, "غدًا": 1, "بكرة": 1, "بعد غد": 2}
    if t in words:
        return today + datetime.timedelta(days=words[t])
    if t.lstrip("+").isdigit():
        return today + datetime.timedelta(days=int(t.lstrip("+")))
    for sep in ("-", "/", "."):
        if sep in t:
            parts = [p for p in t.split(sep) if p]
            try:
                nums = [int(p) for p in parts]
            except ValueError:
                break
            if len(nums) == 3 and nums[0] > 31:
                return datetime.date(nums[0], nums[1], nums[2])
            if len(nums) == 3:
                return datetime.date(nums[2], nums[1], nums[0])
            if len(nums) == 2:
                d = datetime.date(today.year, nums[1], nums[0])
                if d < today:
                    d = datetime.date(today.year + 1, nums[1], nums[0])
                return d
    raise ValueError("لم أفهم التاريخ. اكتبه مثل 2026-11-03 أو 3/11 أو عدد الأيام من اليوم.")
