# -*- coding: utf-8 -*-
"""
abaAcademy.math_engine.arithmetic
=================================

School arithmetic with worked steps:

* **Fractions**: add, subtract, multiply and divide fractions and mixed
  numbers (2 1/3), simplifying with the greatest common divisor and showing
  the common denominator.
* **Percentages**: a percentage of a number, what percent one number is of
  another, percentage change, discounts and simple/compound interest.
* **Roman numerals** in both directions (1–3999).
* **English number words** (one thousand two hundred and five), for the
  English course.
* **Times tables** drill with the learner's weak facts coming back more.
"""

from __future__ import annotations

import math
import random
import re
from fractions import Fraction
from typing import Dict, List, Optional, Tuple

_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")


# ---------------------------------------------------------------------------
# fractions
# ---------------------------------------------------------------------------

def parse_fraction(text: str) -> Fraction:
    """'3/4', '2 1/3' (mixed), '-5/6', '0.25', '7'."""
    t = text.strip().translate(_AR).replace("−", "-").replace("÷", "/")
    if not t:
        raise ValueError("اكتب كسرًا.")
    m = re.fullmatch(r"(-?)(\d+)\s+(\d+)/(\d+)", t)
    if m:
        sign = -1 if m.group(1) else 1
        whole, num, den = int(m.group(2)), int(m.group(3)), int(m.group(4))
        if den == 0:
            raise ValueError("المقام لا يكون صفرًا.")
        return sign * (whole + Fraction(num, den))
    try:
        if "/" in t:
            a, b = t.split("/", 1)
            if Fraction(b.strip()) == 0:
                raise ValueError("المقام لا يكون صفرًا.")
            return Fraction(Fraction(a.strip()), Fraction(b.strip()))
        return Fraction(t)
    except (ValueError, ZeroDivisionError) as e:
        if "المقام" in str(e):
            raise
        raise ValueError(f"{text} ليس كسرًا صالحًا.")


def show(q: Fraction, mixed: bool = True) -> str:
    if q.denominator == 1:
        return str(q.numerator)
    if mixed and abs(q) > 1:
        whole = int(abs(q.numerator) // q.denominator)
        rest = abs(q) - whole
        sign = "-" if q < 0 else ""
        return f"{sign}{whole} و{rest.numerator}/{rest.denominator}"
    return f"{q.numerator}/{q.denominator}"


def speak(q: Fraction) -> str:
    if q.denominator == 1:
        return str(q.numerator)
    sign = "سالب " if q < 0 else ""
    a = abs(q)
    if a > 1:
        whole = a.numerator // a.denominator
        rest = a - whole
        return f"{sign}{whole} و{rest.numerator} على {rest.denominator}"
    return f"{sign}{a.numerator} على {a.denominator}"


def fraction_op(a_text: str, op: str, b_text: str) -> Tuple[Fraction, List[str]]:
    a, b = parse_fraction(a_text), parse_fraction(b_text)
    steps = []
    if op in "+-":
        lcm = a.denominator * b.denominator // math.gcd(a.denominator, b.denominator)
        na = a.numerator * (lcm // a.denominator)
        nb = b.numerator * (lcm // b.denominator)
        steps.append(f"المقام المشترك (المضاعف المشترك الأصغر لـ {a.denominator} و{b.denominator}) = {lcm}.")
        steps.append(f"{show(a, False)} = {na}/{lcm}، و{show(b, False)} = {nb}/{lcm}.")
        top = na + nb if op == "+" else na - nb
        steps.append(f"{'نجمع' if op == '+' else 'نطرح'} البسطين: {na} {op} {nb} = {top}، فيكون الناتج {top}/{lcm}.")
        raw = Fraction(top, lcm) if False else (top, lcm)
        result = a + b if op == "+" else a - b
    elif op in ("*", "×"):
        top = a.numerator * b.numerator
        bot = a.denominator * b.denominator
        steps.append(f"نضرب البسطين ({a.numerator} × {b.numerator} = {top}) والمقامين "
                     f"({a.denominator} × {b.denominator} = {bot}): {top}/{bot}.")
        raw = (top, bot)
        result = a * b
    elif op in ("/", "÷"):
        if b == 0:
            raise ValueError("لا قسمة على صفر.")
        steps.append(f"القسمة على كسر = الضرب في مقلوبه: {show(a, False)} × {b.denominator}/{b.numerator}.")
        top = a.numerator * b.denominator
        bot = a.denominator * b.numerator
        if bot < 0:
            top, bot = -top, -bot
        steps.append(f"= {top}/{bot}.")
        raw = (top, bot)
        result = a / b
    else:
        raise ValueError("العملية غير معروفة.")
    top, bot = raw
    g = math.gcd(top, bot)
    if g > 1:
        steps.append(f"نبسّط بالقسمة على القاسم المشترك الأكبر {g}: {result.numerator}/{result.denominator}.")
    if abs(result) > 1 and result.denominator != 1:
        steps.append(f"وفي صورة عدد كسري: {show(result)}.")
    steps.append(f"الناتج: {show(result)}، أي تقريبًا {float(result):.4g}.")
    return result, steps


# ---------------------------------------------------------------------------
# percentages
# ---------------------------------------------------------------------------

def _n(x: float) -> str:
    return f"{x:,.2f}".rstrip("0").rstrip(".") if abs(x - round(x)) > 1e-9 else f"{round(x):,}"


def percent_of(p: float, x: float) -> str:
    return f"{_n(p)}٪ من {_n(x)} = {_n(x)} × {_n(p)} ÷ 100 = {_n(x * p / 100)}"


def what_percent(part: float, whole: float) -> str:
    if whole == 0:
        raise ValueError("الكلّ لا يكون صفرًا.")
    return f"{_n(part)} من {_n(whole)} = {_n(part)} ÷ {_n(whole)} × 100 = {_n(100 * part / whole)}٪"


def change(old: float, new: float) -> str:
    if old == 0:
        raise ValueError("القيمة الأصلية لا تكون صفرًا.")
    pct = 100 * (new - old) / old
    kind = "زيادة" if pct > 0 else ("نقص" if pct < 0 else "لا تغيّر")
    return f"التغيّر = ({_n(new)} − {_n(old)}) ÷ {_n(old)} × 100 = {_n(pct)}٪ ({kind})"


def discount(price: float, pct: float) -> str:
    off = price * pct / 100
    return (f"الخصم = {_n(price)} × {_n(pct)}٪ = {_n(off)}؛ السعر بعد الخصم = "
            f"{_n(price)} − {_n(off)} = {_n(price - off)}")


def interest(principal: float, rate: float, years: float, compound: bool) -> str:
    if compound:
        total = principal * (1 + rate / 100) ** years
        return (f"الفائدة المركّبة: {_n(principal)} × (1 + {_n(rate)}٪)^{_n(years)} = {_n(total)}، "
                f"والربح {_n(total - principal)}")
    gain = principal * rate / 100 * years
    return (f"الفائدة البسيطة = {_n(principal)} × {_n(rate)}٪ × {_n(years)} = {_n(gain)}، "
            f"والمجموع {_n(principal + gain)}")


# ---------------------------------------------------------------------------
# Roman numerals
# ---------------------------------------------------------------------------

_ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
          (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def to_roman(n: int) -> str:
    if not 1 <= n <= 3999:
        raise ValueError("الأرقام الرومانية من ١ إلى ٣٩٩٩.")
    out = []
    for v, s in _ROMAN:
        while n >= v:
            out.append(s)
            n -= v
    return "".join(out)


def from_roman(s: str) -> int:
    t = s.strip().upper()
    if not t or not re.fullmatch(r"[MDCLXVI]+", t):
        raise ValueError("الأرقام الرومانية حروفها: I V X L C D M.")
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    for i, ch in enumerate(t):
        v = vals[ch]
        if i + 1 < len(t) and vals[t[i + 1]] > v:
            total -= v
        else:
            total += v
    if to_roman(total) != t:
        raise ValueError(f"{s} ليست كتابة رومانية صحيحة؛ الصحيح لـ {total} هو {to_roman(total)}.")
    return total


def roman_steps(n: int) -> List[str]:
    steps = []
    rest = n
    for v, s in _ROMAN:
        k = rest // v
        if k:
            steps.append(f"{v} × {k} = {s * k}")
            rest -= v * k
    return steps + [f"{n} = {to_roman(n)}"]


# ---------------------------------------------------------------------------
# English number words
# ---------------------------------------------------------------------------

_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
         "fourteen fifteen sixteen seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def english_words(n: int) -> str:
    if n < 0:
        return "minus " + english_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        t, u = divmod(n, 10)
        return _TENS[t] + ("" if u == 0 else "-" + _ONES[u])
    if n < 1000:
        h, r = divmod(n, 100)
        return _ONES[h] + " hundred" + ("" if r == 0 else " and " + english_words(r))
    for value, name in ((10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")):
        if n >= value:
            q, r = divmod(n, value)
            tail = ""
            if r:
                tail = (" and " if r < 100 else " ") + english_words(r)
            return english_words(q) + f" {name}" + tail
    raise ValueError(n)


def english_ordinal(n: int) -> str:
    w = english_words(n)
    irregular = {"one": "first", "two": "second", "three": "third", "five": "fifth",
                 "eight": "eighth", "nine": "ninth", "twelve": "twelfth"}
    head, sep, last = w.rpartition(" ") if " " in w else ("", "", w)
    if "-" in last:
        a, b = last.rsplit("-", 1)
        last = a + "-" + irregular.get(b, b + "th")
    elif last in irregular:
        last = irregular[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last = last + "th"
    return (head + sep + last) if head else last


# ---------------------------------------------------------------------------
# times tables
# ---------------------------------------------------------------------------

class TimesTables:
    """Adaptive multiplication drill: each fact has a weight that rises on a
    mistake or a slow answer and falls on a quick right one."""

    def __init__(self, tables=range(2, 10), rng: Optional[random.Random] = None,
                 weights: Optional[Dict[str, float]] = None):
        self.rng = rng or random.Random()
        self.tables = list(tables)
        self.weights: Dict[str, float] = dict(weights or {})
        self.current: Optional[Tuple[int, int]] = None

    def _key(self, a, b) -> str:
        return f"{min(a, b)}x{max(a, b)}"

    def next(self) -> Tuple[int, int]:
        facts = [(a, b) for a in self.tables for b in range(1, 11)]
        w = [self.weights.get(self._key(a, b), 1.0) for a, b in facts]
        self.current = self.rng.choices(facts, weights=w, k=1)[0]
        return self.current

    def answer(self, text: str, seconds: float) -> Tuple[bool, int]:
        if self.current is None:
            raise ValueError("لا سؤال الآن.")
        a, b = self.current
        right = a * b
        try:
            got = int(text.strip().translate(_AR))
        except ValueError:
            got = None
        k = self._key(a, b)
        w = self.weights.get(k, 1.0)
        ok = got == right
        if ok:
            w = max(0.3, w * (0.6 if seconds < 4 else 0.85))
        else:
            w = min(8.0, w * 2.0 + 0.5)
        self.weights[k] = w
        return ok, right

    def weakest(self, n: int = 5) -> List[str]:
        items = sorted(self.weights.items(), key=lambda kv: -kv[1])
        return [k.replace("x", " × ") for k, v in items[:n] if v > 1.0]
