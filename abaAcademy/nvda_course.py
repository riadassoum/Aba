# -*- coding: utf-8 -*-
"""
abaAcademy.nvda_course
======================

دورة قارئ الشاشة NVDA — NVDA's keyboard commands, lesson by lesson, with a
quiz in both directions (the keys for a task, and the task for some keys).

The commands, their keys for the desktop and laptop layouts, and their
Arabic descriptions come from NVDA itself (NV Access, GPL-2.0-or-later):
the @script declarations in globalCommands.py and the quick navigation
table in browseMode.py, with the official Arabic translation from NVDA's
nvda.po. devtools/course_builder/build_nvda.py extracts them.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "resources", "nvda", "commands.json")

INTRO = ("مفتاح NVDA هو مفتاح Insert في الوضع العادي، ويمكن جعله Caps Lock أيضًا من إعدادات لوحة المفاتيح، "
         "وهو الإعداد المعتاد في وضع الحاسوب المحمول. حين ترى NVDA+حرف فاضغط مفتاح NVDA مع ذلك الحرف. "
         "مفتاح Control يوقف الكلام فورًا، ومفتاح Shift يوقفه مؤقّتًا ثم يستأنفه. "
         "وNVDA+N يفتح قائمة البرنامج، وNVDA+1 يشغّل المساعدة التفاعلية التي تخبرك بعمل أيّ مفتاح دون تنفيذه، "
         "فاستعملها لتجرّب ما تتعلّمه هنا بأمان.")

# lesson order for a beginner: hearing, moving through text and pages, then
# finding out where you are, then the rest
ORDER = ["النُطق", "أوامر مؤشر التحرير", "أوامر مؤشر النظام", "وضع التصفّح", "أوامر حالة النظام",
         "أوامر إدخال", "أوامر استعراض النص", "أوامر مؤشر الحركة حول الكائن", "أوامر إعدادات البرنامج",
         "الأوضاع", "أدوات", "الخط البارز Braille", "الصوت", "الفأرة", "التكبير", "تصفُّح صيغ الرياضيات",
         "أوامر شاشة اللمس", "التحكُّم عن بُعد (Remote Access)", "أوامر عامّة"]


@dataclass
class Command:
    script: str
    ar: str
    en: str
    category: str
    keys: List[str]
    desktop: List[str]
    laptop: List[str]

    def keys_for(self, layout: str = "desktop") -> List[str]:
        return self.keys + (self.laptop if layout == "laptop" else self.desktop)

    def keys_text(self, layout: str = "desktop") -> str:
        ks = self.keys_for(layout)
        return " أو ".join(ks) if ks else ""


@dataclass
class Lesson:
    title: str
    commands: List[Command] = field(default_factory=list)


def load(path: str = DATA) -> List[Lesson]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)["commands"]
    by: Dict[str, Lesson] = {}
    for c in raw:
        cat = c.get("category") or "أوامر عامّة"
        cmd = Command(c["script"], c["ar"].strip().rstrip("."), c["en"], cat, c.get("keys", []),
                      c.get("desktop", []), c.get("laptop", []))
        by.setdefault(cat, Lesson(cat)).commands.append(cmd)
    lessons = [by[k] for k in ORDER if k in by] + [v for k, v in by.items() if k not in ORDER]
    return lessons


@dataclass
class Question:
    prompt: str
    options: List[str]
    answer: str
    explanation: str


def make_question(lessons: List[Lesson], layout: str = "desktop", lesson: Optional[int] = None,
                  rng: Optional[random.Random] = None) -> Optional[Question]:
    rng = rng or random.Random()
    pool = lessons[lesson].commands if lesson is not None and 0 <= lesson < len(lessons) else \
        [c for l in lessons for c in l.commands]
    pool = [c for c in pool if c.keys_for(layout)]
    everyone = [c for l in lessons for c in l.commands if c.keys_for(layout)]
    if len(pool) < 1 or len(everyone) < 4:
        return None
    c = rng.choice(pool)
    same = [x for x in pool if x is not c]
    rng.shuffle(same)
    others = [x for x in everyone if x is not c and x not in same]
    rng.shuffle(others)
    if rng.random() < 0.5:
        right = c.keys_text(layout)
        wrong = []
        for x in same + others:
            t = x.keys_text(layout)
            if t != right and t not in wrong:
                wrong.append(t)
            if len(wrong) == 3:
                break
        opts = wrong + [right]
        rng.shuffle(opts)
        return Question(f"ما مفتاح هذا الأمر: {c.ar}؟", opts, right, f"{c.ar}: {right}.")
    right = c.ar
    wrong = []
    for x in same + others:
        if x.ar != right and x.ar not in wrong:
            wrong.append(x.ar)
        if len(wrong) == 3:
            break
    opts = wrong + [right]
    rng.shuffle(opts)
    return Question(f"ماذا يفعل {c.keys_text(layout)}؟", opts, right, f"{c.keys_text(layout)}: {right}.")
