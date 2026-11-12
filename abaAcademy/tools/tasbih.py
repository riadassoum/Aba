# -*- coding: utf-8 -*-
"""
abaAcademy.tools.tasbih
=======================

An electronic tasbih counter (المسبحة). Choose a dhikr or a sequence, then
count with a single key; the counter announces milestones and moves to the
next dhikr in a sequence when its target is reached. Daily totals are kept.

The built-in sequence after the obligatory prayer is the well-known one:
سبحان الله ٣٣، الحمد لله ٣٣، الله أكبر ٣٣، ثم تمام المئة بـلا إله إلا الله
وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

KEY = "tasbih_state"

DHIKR = {
    "subhan": "سبحان الله",
    "hamd": "الحمد لله",
    "takbir": "الله أكبر",
    "tahlil": "لا إله إلا الله",
    "istighfar": "أستغفر الله",
    "salawat": "اللهم صلّ على محمد",
    "hawqala": "لا حول ولا قوة إلا بالله",
    "subhan_bihamdih": "سبحان الله وبحمده",
    "tamam": "لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير",
}

SEQUENCES = {
    "after_prayer": ("أذكار ما بعد الصلاة", [("subhan", 33), ("hamd", 33), ("takbir", 33), ("tamam", 1)]),
    "subhan": ("سبحان الله", [("subhan", 33)]),
    "istighfar": ("الاستغفار ١٠٠", [("istighfar", 100)]),
    "salawat": ("الصلاة على النبي ١٠٠", [("salawat", 100)]),
    "tahlil": ("التهليل ١٠٠", [("tahlil", 100)]),
    "subhan_bihamdih": ("سبحان الله وبحمده ١٠٠", [("subhan_bihamdih", 100)]),
    "hawqala": ("الحوقلة", [("hawqala", 33)]),
    "free": ("عدّ حرّ بلا هدف", [("subhan", 0)]),
}


@dataclass
class Counter:
    sequence: str = "after_prayer"
    step: int = 0
    count: int = 0
    daily: Dict[str, int] = field(default_factory=dict)
    finished: bool = False

    @property
    def steps(self) -> List[Tuple[str, int]]:
        return SEQUENCES[self.sequence][1]

    @property
    def current(self) -> Tuple[str, int]:
        return self.steps[min(self.step, len(self.steps) - 1)]

    def phrase(self) -> str:
        return DHIKR[self.current[0]]

    def target(self) -> int:
        return self.current[1]

    def tap(self, today: Optional[datetime.date] = None) -> str:
        """Count one. Returns what to announce (possibly empty for a plain
        count, so the learner can count silently)."""
        day = (today or datetime.date.today()).isoformat()
        if self.finished:
            return "اكتمل الورد. اضغط من جديد للبدء مرّة أخرى."
        self.count += 1
        self.daily[day] = self.daily.get(day, 0) + 1
        target = self.target()
        if target and self.count >= target:
            done = self.phrase()
            if self.step + 1 < len(self.steps):
                self.step += 1
                self.count = 0
                return f"اكتمل {done} {target} مرّة. الآن: {self.phrase()}."
            self.finished = True
            return f"اكتمل {done}. تقبّل الله."
        if target and target - self.count in (10, 3):
            return f"بقي {target - self.count}."
        if self.count % 10 == 0:
            return str(self.count)
        return ""

    def undo(self) -> None:
        if self.count > 0:
            self.count -= 1
            day = datetime.date.today().isoformat()
            if self.daily.get(day):
                self.daily[day] -= 1
        self.finished = False

    def reset(self, sequence: Optional[str] = None) -> None:
        if sequence:
            if sequence not in SEQUENCES:
                raise ValueError(sequence)
            self.sequence = sequence
        self.step = 0
        self.count = 0
        self.finished = False

    def status(self) -> str:
        t = self.target()
        if self.finished:
            return "اكتمل الورد."
        where = f" من {t}" if t else ""
        stage = f" (المرحلة {self.step + 1} من {len(self.steps)})" if len(self.steps) > 1 else ""
        return f"{self.phrase()}: {self.count}{where}{stage}."

    def today_total(self) -> int:
        return self.daily.get(datetime.date.today().isoformat(), 0)


def load(store) -> Counter:
    try:
        raw = json.loads(store.get_setting(KEY, "") or "{}")
        c = Counter(**{k: v for k, v in raw.items() if k in Counter.__dataclass_fields__})
        if c.sequence not in SEQUENCES:
            c.sequence = "after_prayer"
        return c
    except Exception:
        return Counter()


def save(store, c: Counter) -> None:
    # keep a month of daily totals
    days = sorted(c.daily)[-31:]
    c.daily = {d: c.daily[d] for d in days}
    store.set_setting(KEY, json.dumps(c.__dict__, ensure_ascii=False))
