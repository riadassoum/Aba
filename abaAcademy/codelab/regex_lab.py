# -*- coding: utf-8 -*-
"""
abaAcademy.codelab.regex_lab
============================

Regular expressions, explained piece by piece in Arabic and tested against
the learner's own text. ``explain(pattern)`` walks the pattern token by
token (\\d+: رقم واحد أو أكثر); ``test(pattern, text)`` lists every match
with its position and groups; ``substitute`` shows the result of re.sub.
A set of graded exercises checks the learner's pattern against texts that
must and must not match.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

_ESCAPES = {
    "d": "رقم (٠ إلى ٩)", "D": "أيّ حرف ليس رقمًا", "w": "حرف أو رقم أو شرطة سفلية",
    "W": "أيّ رمز ليس حرفًا ولا رقمًا", "s": "مسافة بيضاء (مسافة أو سطر أو جدولة)",
    "S": "أيّ رمز ليس مسافة", "b": "حدّ كلمة", "B": "ليس حدّ كلمة", "n": "سطر جديد",
    "t": "مسافة جدولة", ".": "نقطة حرفية", "\\": "شرطة مائلة عكسية حرفية",
    "A": "بداية النصّ", "Z": "نهاية النصّ",
}

_QUANT = {"*": "صفر مرّة أو أكثر", "+": "مرّة واحدة أو أكثر", "?": "اختياري (صفر أو مرّة)"}


def _describe_class(body: str) -> str:
    neg = body.startswith("^")
    if neg:
        body = body[1:]
    parts = []
    i = 0
    while i < len(body):
        if body[i] == "\\" and i + 1 < len(body):
            parts.append(_ESCAPES.get(body[i + 1], f"الرمز {body[i + 1]}"))
            i += 2
        elif i + 2 < len(body) and body[i + 1] == "-":
            parts.append(f"من {body[i]} إلى {body[i + 2]}")
            i += 3
        else:
            parts.append(f"{body[i]}")
            i += 1
    inner = "، أو ".join(parts)
    return ("أيّ رمز ما عدا: " if neg else "رمز واحد من: ") + inner


def explain(pattern: str) -> List[str]:
    """Token-by-token Arabic explanation."""
    out: List[str] = []
    i = 0
    n = len(pattern)
    group = 0

    def quant_at(j: int) -> Tuple[str, int]:
        if j >= n:
            return "", j
        ch = pattern[j]
        if ch in _QUANT:
            lazy = j + 1 < n and pattern[j + 1] == "?"
            return _QUANT[ch] + ("، بأقلّ عدد ممكن" if lazy else ""), j + 1 + lazy
        if ch == "{":
            k = pattern.find("}", j)
            if k != -1:
                body = pattern[j + 1:k]
                if "," in body:
                    a, b = body.split(",", 1)
                    if b == "":
                        txt = f"{a} مرّات أو أكثر"
                    else:
                        txt = f"من {a or 0} إلى {b} مرّات"
                else:
                    txt = f"{body} مرّات بالضبط"
                return txt, k + 1
        return "", j

    while i < n:
        ch = pattern[i]
        if ch == "\\" and i + 1 < n:
            tok = pattern[i:i + 2]
            desc = _ESCAPES.get(pattern[i + 1], f"الرمز {pattern[i + 1]} حرفيًّا")
            j = i + 2
        elif ch == "[":
            k = i + 1
            if k < n and pattern[k] == "^":
                k += 1
            if k < n and pattern[k] == "]":
                k += 1
            while k < n and pattern[k] != "]":
                k += 2 if pattern[k] == "\\" else 1
            tok = pattern[i:k + 1]
            desc = _describe_class(pattern[i + 1:k])
            j = k + 1
        elif ch == "(":
            if pattern.startswith("(?:", i):
                tok, desc, j = "(?:", "بداية مجموعة لا تُحفظ", i + 3
            elif pattern.startswith("(?P<", i):
                k = pattern.find(">", i)
                group += 1
                tok, desc, j = pattern[i:k + 1], f"بداية المجموعة {group} باسم {pattern[i + 4:k]}", k + 1
            elif pattern.startswith("(?=", i):
                tok, desc, j = "(?=", "شرط: يليه ما يأتي (دون أن يدخل في المطابقة)", i + 3
            elif pattern.startswith("(?!", i):
                tok, desc, j = "(?!", "شرط: لا يليه ما يأتي", i + 3
            else:
                group += 1
                tok, desc, j = "(", f"بداية المجموعة {group}", i + 1
        elif ch == ")":
            tok, desc, j = ")", "نهاية المجموعة", i + 1
        elif ch == "|":
            tok, desc, j = "|", "أو (بديل)", i + 1
        elif ch == ".":
            tok, desc, j = ".", "أيّ رمز ما عدا السطر الجديد", i + 1
        elif ch == "^":
            tok, desc, j = "^", "بداية السطر", i + 1
        elif ch == "$":
            tok, desc, j = "$", "نهاية السطر", i + 1
        else:
            k = i
            while k < n and pattern[k] not in "\\[]()|.^$*+?{":
                k += 1
            # a quantifier binds to the last literal only
            if k < n and pattern[k] in "*+?{" and k - i > 1:
                k -= 1
            tok = pattern[i:k] or pattern[i]
            desc = f"النصّ {tok} حرفيًّا"
            j = i + len(tok)
        q, j2 = quant_at(j)
        if q:
            tok = pattern[i:j2]
            desc = f"{desc}، {q}"
        out.append(f"{tok} ← {desc}")
        i = j2 if q else j
    return out


@dataclass
class Match:
    start: int
    end: int
    text: str
    groups: Tuple[Optional[str], ...]


def compile_pattern(pattern: str, ignore_case: bool = False, multiline: bool = True):
    flags = (re.IGNORECASE if ignore_case else 0) | (re.MULTILINE if multiline else 0)
    try:
        return re.compile(pattern, flags)
    except re.error as e:
        pos = f" عند الموضع {e.pos + 1}" if e.pos is not None else ""
        raise ValueError(f"النمط غير صالح{pos}: {_translate_error(str(e))}")


def _translate_error(msg: str) -> str:
    table = {"missing )": "قوس ) ناقص", "unbalanced parenthesis": "أقواس غير متوازنة",
             "nothing to repeat": "مكرِّر بلا شيء قبله", "unterminated character set": "مجموعة [ ] غير مغلقة",
             "bad escape": "رمز هروب غير معروف", "multiple repeat": "مكرِّران متتاليان"}
    for k, v in table.items():
        if k in msg:
            return v
    return msg


def test(pattern: str, text: str, ignore_case: bool = False, limit: int = 200) -> List[Match]:
    rx = compile_pattern(pattern, ignore_case)
    out = []
    for m in rx.finditer(text):
        out.append(Match(m.start(), m.end(), m.group(0), m.groups()))
        if len(out) >= limit:
            break
    return out


def describe_matches(matches: Sequence[Match], text: str) -> List[str]:
    lines = []
    for i, m in enumerate(matches, 1):
        line_no = text.count("\n", 0, m.start) + 1
        g = ""
        if m.groups:
            g = "، المجموعات: " + "، ".join(f"{k}: {v if v is not None else 'فارغة'}"
                                           for k, v in enumerate(m.groups, 1))
        lines.append(f"{i}. {m.text} في السطر {line_no}، من الموضع {m.start + 1}{g}")
    return lines


def substitute(pattern: str, repl: str, text: str, ignore_case: bool = False) -> Tuple[str, int]:
    rx = compile_pattern(pattern, ignore_case)
    return rx.subn(repl, text)


@dataclass(frozen=True)
class Exercise:
    title: str
    task: str
    must_match: Tuple[str, ...]
    must_not: Tuple[str, ...]
    hint: str
    full: bool = True            # the whole string must match


EXERCISES: Tuple[Exercise, ...] = (
    Exercise("أرقام فقط", "اكتب نمطًا يطابق نصًّا كلّه أرقام.", ("123", "7", "2026"),
             ("12a", "", "1 2"), "\\d تعني رقمًا، و+ مرّة أو أكثر."),
    Exercise("رمز بريدي من خمسة أرقام", "طابق خمسة أرقام بالضبط.", ("12345", "00000"),
             ("1234", "123456", "1234a"), "استعمل \\d{5}."),
    Exercise("كلمة تبدأ بحرف كبير", "طابق كلمة إنجليزية أولها حرف كبير وبقيتها صغيرة.",
             ("Ahmad", "Beirut", "X"), ("ahmad", "BEIRUT", "Ahmad1"), "[A-Z][a-z]*"),
    Exercise("رقم هاتف بشرطة", "طابق ثلاثة أرقام ثم شرطة ثم أربعة أرقام، مثل 555-1234.",
             ("555-1234", "012-0000"), ("5551234", "55-1234", "555-12345"), "\\d{3}-\\d{4}"),
    Exercise("نعم أو لا", "طابق نعم أو لا فقط.", ("نعم", "لا"), ("ربما", "نعمم", ""),
             "استعمل | بين البديلين، مع أقواس: (نعم|لا)."),
    Exercise("بريد إلكتروني بسيط", "طابق اسمًا ثم @ ثم نطاقًا فيه نقطة.",
             ("ali@mail.com", "a.b@site.org"), ("ali@mail", "@mail.com", "ali mail.com"),
             "[\\w.]+@\\w+\\.\\w+"),
    Exercise("كلمة عربية", "طابق كلمة عربية واحدة (حروف من ء إلى ي).", ("كتاب", "مدرسة"),
             ("كتاب جديد", "book", "كتاب1"), "[ء-ي]+ يغطّي الحروف العربية الأساسية."),
    Exercise("سنة هجرية أو ميلادية", "طابق أربعة أرقام تبدأ بـ 14 أو 20.",
             ("1447", "2026", "1400"), ("1999", "147", "20266"), "(14|20)\\d{2}"),
)


def check_exercise(ex: Exercise, pattern: str) -> Tuple[bool, List[str]]:
    rx = compile_pattern(pattern, multiline=False)
    problems = []
    for s in ex.must_match:
        ok = rx.fullmatch(s) if ex.full else rx.search(s)
        if not ok:
            problems.append(f"لم يطابق {s} وكان يجب أن يطابقه.")
    for s in ex.must_not:
        ok = rx.fullmatch(s) if ex.full else rx.search(s)
        if ok:
            problems.append(f"طابق {s or '(نصّ فارغ)'} وكان يجب ألّا يطابقه.")
    return not problems, problems
