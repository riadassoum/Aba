# -*- coding: utf-8 -*-
"""
abaAcademy.typing_course
========================

دورة الكتابة باللمس — touch-typing courses for blind learners.

The lessons and keyboard layouts come from KTouch, KDE's typing tutor
(GPL-2.0-or-later), converted by devtools/course_builder/build_typing.py into
resources/typing/<id>.json: Arabic, and the English (US and UK), French,
Spanish, German, Italian and Turkish keyboards.

A blind learner cannot see the on-screen keyboard KTouch draws, so every key
is described by touch instead: which finger presses it, which row it is on,
and where it lies relative to the key with the raised marker under the
index finger (F and J on Latin keyboards, ب and ت on the Arabic one).

Typed lines are graded by alignment, so a skipped or doubled letter costs
one error, not every letter after it.
"""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .tools.ar_count import count

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "resources", "typing")

FINGERS = ["خنصر اليد اليسرى", "بنصر اليد اليسرى", "وسطى اليد اليسرى", "سبابة اليد اليسرى",
           "سبابة اليد اليمنى", "وسطى اليد اليمنى", "بنصر اليد اليمنى", "خنصر اليد اليمنى"]
HOME_ROW = 2
ROW_NAMES = {0: "صف الأرقام (الأعلى)", 1: "الصف العلوي", 2: "صف البداية (الأوسط)", 3: "الصف السفلي"}
KEY_WIDTH = 100
PASS_ACCURACY = 95

SPOKEN_CHARS = {
    " ": "مسافة", ".": "نقطة", ",": "فاصلة إنجليزية", "،": "فاصلة", "؛": "فاصلة منقوطة", ";": "فاصلة منقوطة",
    ":": "نقطتان", "?": "علامة استفهام", "؟": "علامة استفهام", "!": "علامة تعجّب", "'": "فاصلة عليا",
    '"': "علامة تنصيص", "-": "شرطة", "_": "شرطة سفلية", "(": "قوس فتح", ")": "قوس إغلاق", "/": "شرطة مائلة",
    "\\": "شرطة مائلة عكسية", "@": "علامة آت", "#": "علامة شباك", "&": "علامة و", "*": "نجمة", "+": "زائد",
    "=": "يساوي", "<": "أصغر من", ">": "أكبر من", "[": "قوس مربّع فتح", "]": "قوس مربّع إغلاق",
    "ـ": "مدّة (كشيدة)", "ء": "همزة", "ئ": "همزة على نبرة", "ؤ": "همزة على واو", "أ": "ألف همزة فوق",
    "إ": "ألف همزة تحت", "آ": "ألف مدّ", "ة": "تاء مربوطة", "ى": "ألف مقصورة", "لا": "لام ألف",
    "َ": "فتحة", "ُ": "ضمّة", "ِ": "كسرة", "ْ": "سكون", "ّ": "شدّة", "ً": "تنوين فتح", "ٌ": "تنوين ضمّ", "ٍ": "تنوين كسر",
}


def char_name(ch: str) -> str:
    if ch in SPOKEN_CHARS:
        return SPOKEN_CHARS[ch]
    if ch.isdigit():
        return f"الرقم {ch}"
    if "a" <= ch.lower() <= "z" or ch.isalpha() and ord(ch) < 0x600:
        return f"{ch} ({'حرف كبير' if ch.isupper() else 'حرف صغير'})" if ch.isalpha() and ch.lower() != ch.upper() else ch
    return ch


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------

def available() -> List[dict]:
    try:
        with open(os.path.join(DATA, "index.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


@dataclass
class Lesson:
    title: str
    new: str
    lines: List[str]


@dataclass
class Course:
    id: str
    title: str
    keys: Dict[str, dict]
    anchors: List[str]
    lessons: List[Lesson]
    credit: str = ""
    source: str = ""

    @classmethod
    def load(cls, course_id: str) -> "Course":
        with open(os.path.join(DATA, f"{course_id}.json"), encoding="utf-8") as f:
            d = json.load(f)
        return cls(d["id"], d["title"], d["keys"], d.get("anchors", []),
                   [Lesson(l["title"], l["new"], l["lines"]) for l in d["lessons"]],
                   d.get("credit", ""), d.get("source", ""))

    # -- describing keys by touch -------------------------------------------

    def _anchor_for(self, finger: int) -> Optional[str]:
        if len(self.anchors) < 2:
            return self.anchors[0] if self.anchors else None
        return self.anchors[0] if finger <= 3 else self.anchors[1]

    def describe(self, ch: str) -> str:
        """Where a character is on the keyboard, for someone who cannot see it."""
        if ch == " ":
            return "المسافة: المفتاح الطويل في أسفل اللوحة، بإبهام أيّ يد."
        info = self.keys.get(ch)
        if info is None and ch.lower() in self.keys and ch != ch.lower():
            info = dict(self.keys[ch.lower()], shift="any")
        if info is None:
            return f"{char_name(ch)}: غير موجود في هذه اللوحة."
        finger = info["finger"]
        parts = [f"{char_name(ch)}: {FINGERS[finger]}"]
        row = info["row"]
        parts.append(ROW_NAMES.get(row, f"الصف {row + 1}"))
        anchor = self._anchor_for(finger)
        if anchor and anchor in self.keys:
            a = self.keys[anchor]
            if ch == anchor:
                parts.append("على المفتاح ذي العلامة البارزة نفسه")
            else:
                shift_cols = round((info["left"] - a["left"]) / KEY_WIDTH)
                if row == HOME_ROW:
                    if shift_cols:
                        side = "يمين" if shift_cols > 0 else "يسار"
                        parts.append(f"{self._keys_text(abs(shift_cols))} {side} "
                                     f"العلامة البارزة ({char_name(anchor)})")
                else:
                    direction = "فوق" if row < HOME_ROW else "تحت"
                    parts.append(f"{direction} صف البداية، "
                                 + ("في عمود العلامة البارزة تقريبًا" if abs(shift_cols) == 0 else
                                    f"{self._keys_text(abs(shift_cols))} {'يمين' if shift_cols > 0 else 'يسار'} عمود العلامة البارزة"))
        if info.get("shift"):
            side = {"left": "الأيسر", "right": "الأيمن"}.get(info["shift"], "")
            parts.append(f"مع الضغط على Shift {side}".strip())
        if info.get("haptic"):
            parts.append("وعليه علامة بارزة تلمسها بإصبعك")
        return "، ".join(parts) + "."

    @staticmethod
    def _keys_text(n: int) -> str:
        return {1: "مفتاح واحد", 2: "مفتاحان"}.get(n, f"{n} مفاتيح" if n <= 10 else f"{n} مفتاحًا")

    def home_position(self) -> str:
        if len(self.anchors) >= 2:
            a, b = self.anchors[0], self.anchors[1]
            return (f"وضع البداية: ضع سبابة يدك اليسرى على المفتاح {char_name(a)} وسبابة يدك اليمنى على "
                    f"{char_name(b)}، وعليهما علامة بارزة. ثم ضع بقية الأصابع على المفاتيح المجاورة في الصف نفسه، "
                    f"والإبهامين على المسافة. ارجع إلى هذا الوضع بعد كل حرف.")
        return "ضع أصابعك على صف البداية، والإبهامين على المسافة."

    def lesson_intro(self, index: int) -> str:
        les = self.lessons[index]
        chars = [c for c in dict.fromkeys(les.new) if not c.isspace()]
        lines = [f"{les.title}. " + (f"الحروف الجديدة: {'، '.join(char_name(c) for c in chars)}." if chars else "")]
        lines += [self.describe(c) for c in chars]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# grading
# ---------------------------------------------------------------------------

def align(expected: str, typed: str) -> List[Tuple[str, str, str]]:
    """Edit-distance alignment: [(op, expected_char, typed_char)] where op is
    'ok', 'sub', 'del' (a letter skipped) or 'ins' (an extra letter)."""
    n, m = len(expected), len(typed)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if expected[i - 1] == typed[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
    ops = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (0 if expected[i - 1] == typed[j - 1] else 1):
            ops.append(("ok" if expected[i - 1] == typed[j - 1] else "sub", expected[i - 1], typed[j - 1]))
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            ops.append(("del", expected[i - 1], ""))
            i -= 1
        else:
            ops.append(("ins", "", typed[j - 1]))
            j -= 1
    return ops[::-1]


@dataclass
class LineResult:
    expected: str
    typed: str
    seconds: float
    errors: List[Tuple[str, str, str]]
    accuracy: int
    wpm: int

    @property
    def passed(self) -> bool:
        return self.accuracy >= PASS_ACCURACY

    def feedback(self) -> str:
        parts = [f"الدقّة {self.accuracy}٪"]
        if self.wpm:
            parts.append(f"السرعة {count(self.wpm, 'kalima')} في الدقيقة")
        if not self.errors:
            parts.append("دون أخطاء")
        else:
            details = []
            for op, e, t in self.errors[:4]:
                if op == "sub":
                    details.append(f"كتبت {char_name(t)} بدل {char_name(e)}")
                elif op == "del":
                    details.append(f"نسيت {char_name(e)}")
                else:
                    details.append(f"زدت {char_name(t)}")
            more = len(self.errors) - 4
            parts.append(count(len(self.errors), "error") + ": " + "؛ ".join(details)
                         + (f"؛ و{count(more, 'error')} أخرى" if more > 0 else ""))
        return "، ".join(parts) + "."


def grade_line(expected: str, typed: str, seconds: float) -> LineResult:
    expected = " ".join(expected.split())
    typed = " ".join(typed.split())
    ops = align(expected, typed)
    errors = [o for o in ops if o[0] != "ok"]
    accuracy = max(0, round(100 * (len(expected) - len(errors)) / len(expected))) if expected else 100
    wpm = round((len(typed) / 5) / (seconds / 60)) if seconds > 0.5 and typed else 0
    return LineResult(expected, typed, seconds, errors, accuracy, wpm)


# ---------------------------------------------------------------------------
# sessions and progress
# ---------------------------------------------------------------------------

def drill_lines(chars: str, known: str = "", n: int = 6, seed: Optional[int] = None) -> List[str]:
    """Practice lines built from the new characters (and some known ones)."""
    rnd = random.Random(seed)
    new = [c for c in dict.fromkeys(chars) if not c.isspace()]
    pool = new * 3 + [c for c in dict.fromkeys(known) if not c.isspace() and c not in new]
    if not new:
        return []
    lines = []
    for _ in range(n):
        words = []
        for _ in range(6):
            size = rnd.randint(2, 4)
            words.append("".join(rnd.choice(pool) for _ in range(size)))
        lines.append(" ".join(words))
    return lines


@dataclass
class Session:
    course: Course
    lesson_index: int
    lines: List[str] = field(default_factory=list)
    position: int = 0
    started: Optional[float] = None
    results: List[LineResult] = field(default_factory=list)

    def __post_init__(self):
        if not self.lines:
            self.lines = list(self.course.lessons[self.lesson_index].lines)

    @property
    def current(self) -> Optional[str]:
        return self.lines[self.position] if self.position < len(self.lines) else None

    @property
    def finished(self) -> bool:
        return self.position >= len(self.lines)

    def start_line(self, now: Optional[float] = None) -> None:
        self.started = now if now is not None else time.monotonic()

    def submit(self, typed: str, now: Optional[float] = None) -> LineResult:
        now = now if now is not None else time.monotonic()
        seconds = (now - self.started) if self.started is not None else 0.0
        res = grade_line(self.current or "", typed, seconds)
        self.results.append(res)
        if res.passed:
            self.position += 1
        self.started = None
        return res

    def summary(self) -> str:
        if not self.results:
            return "لم تكتب شيئًا بعد."
        acc = round(sum(r.accuracy for r in self.results) / len(self.results))
        speeds = [r.wpm for r in self.results if r.wpm]
        wpm = round(sum(speeds) / len(speeds)) if speeds else 0
        done = min(self.position, len(self.lines))
        return (f"أنهيت {done} من {len(self.lines)} سطرًا. متوسّط الدقّة {acc}٪"
                + (f"، ومتوسّط السرعة {count(wpm, 'kalima')} في الدقيقة." if wpm else "."))

    def stats(self) -> Tuple[int, int]:
        if not self.results:
            return 0, 0
        acc = round(sum(r.accuracy for r in self.results) / len(self.results))
        speeds = [r.wpm for r in self.results if r.wpm]
        return acc, (round(sum(speeds) / len(speeds)) if speeds else 0)


def progress_key(course_id: str) -> str:
    return f"typing_course_{course_id}"


def load_progress(store, course_id: str) -> dict:
    try:
        return json.loads(store.get_setting(progress_key(course_id), "{}") or "{}")
    except Exception:
        return {}


def save_lesson_result(store, course_id: str, lesson_index: int, accuracy: int, wpm: int) -> dict:
    prog = load_progress(store, course_id)
    lessons = prog.setdefault("lessons", {})
    key = str(lesson_index)
    best = lessons.get(key, {})
    if accuracy >= best.get("accuracy", 0) or wpm > best.get("wpm", 0):
        lessons[key] = {"accuracy": max(accuracy, best.get("accuracy", 0)), "wpm": max(wpm, best.get("wpm", 0)),
                        "passed": accuracy >= PASS_ACCURACY or best.get("passed", False)}
    prog["last"] = lesson_index
    try:
        store.set_setting(progress_key(course_id), json.dumps(prog))
    except Exception:
        pass
    return prog
