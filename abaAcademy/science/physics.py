# -*- coding: utf-8 -*-
"""
abaAcademy.science.physics
==========================

A school physics formula solver: pick a law, give the quantities you know,
and get the one you don't — with the law, the substitution and the unit.

Each law is stored as a residual function (left side minus right side), so
any of its variables can be the unknown: the solver finds the root
numerically (bracketing over a wide range, then bisection to full
precision). When a law has two physical solutions (a time from a quadratic,
say) the positive ones are reported.

Quantities use SI units; g = 9.81 m/s².
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

G = 9.81


@dataclass(frozen=True)
class Var:
    key: str
    name: str
    unit: str
    positive: bool = False      # e.g. mass, time: negative answers are dropped


@dataclass(frozen=True)
class Law:
    key: str
    topic: str
    name: str
    text: str                   # the law as read aloud
    variables: Tuple[Var, ...]
    residual: Callable[[Dict[str, float]], float]


def V(key, name, unit, positive=False):
    return Var(key, name, unit, positive)


LAWS: Tuple[Law, ...] = (
    Law("speed", "الحركة", "السرعة المتوسطة", "السرعة = المسافة ÷ الزمن (ع = ف ÷ ز)",
        (V("v", "السرعة", "م/ث"), V("d", "المسافة", "م"), V("t", "الزمن", "ث", True)),
        lambda x: x["v"] * x["t"] - x["d"]),
    Law("v_uat", "الحركة", "المعادلة الأولى للحركة", "ع = ع٠ + ت × ز",
        (V("v", "السرعة النهائية", "م/ث"), V("u", "السرعة الابتدائية", "م/ث"),
         V("a", "التسارع", "م/ث²"), V("t", "الزمن", "ث", True)),
        lambda x: x["u"] + x["a"] * x["t"] - x["v"]),
    Law("s_ut", "الحركة", "المعادلة الثانية للحركة", "ف = ع٠ × ز + ½ × ت × ز²",
        (V("s", "الإزاحة", "م"), V("u", "السرعة الابتدائية", "م/ث"),
         V("t", "الزمن", "ث", True), V("a", "التسارع", "م/ث²")),
        lambda x: x["u"] * x["t"] + 0.5 * x["a"] * x["t"] ** 2 - x["s"]),
    Law("v2", "الحركة", "المعادلة الثالثة للحركة", "ع² = ع٠² + ٢ × ت × ف",
        (V("v", "السرعة النهائية", "م/ث"), V("u", "السرعة الابتدائية", "م/ث"),
         V("a", "التسارع", "م/ث²"), V("s", "الإزاحة", "م")),
        lambda x: x["u"] ** 2 + 2 * x["a"] * x["s"] - x["v"] ** 2),
    Law("fall", "الحركة", "السقوط الحرّ", "ف = ½ × ج × ز² (من السكون، ج = 9.81)",
        (V("h", "الارتفاع", "م", True), V("t", "زمن السقوط", "ث", True)),
        lambda x: 0.5 * G * x["t"] ** 2 - x["h"]),
    Law("newton2", "القوى", "قانون نيوتن الثاني", "القوّة = الكتلة × التسارع (ق = ك × ت)",
        (V("F", "القوّة", "نيوتن"), V("m", "الكتلة", "كغ", True), V("a", "التسارع", "م/ث²")),
        lambda x: x["m"] * x["a"] - x["F"]),
    Law("weight", "القوى", "الوزن", "الوزن = الكتلة × تسارع الجاذبية (و = ك × ج)",
        (V("W", "الوزن", "نيوتن"), V("m", "الكتلة", "كغ", True)),
        lambda x: x["m"] * G - x["W"]),
    Law("momentum", "القوى", "كمّية الحركة", "كمّية الحركة = الكتلة × السرعة",
        (V("p", "كمّية الحركة", "كغ·م/ث"), V("m", "الكتلة", "كغ", True), V("v", "السرعة", "م/ث")),
        lambda x: x["m"] * x["v"] - x["p"]),
    Law("pressure", "القوى", "الضغط", "الضغط = القوّة ÷ المساحة",
        (V("P", "الضغط", "باسكال"), V("F", "القوّة", "نيوتن"), V("A", "المساحة", "م²", True)),
        lambda x: x["P"] * x["A"] - x["F"]),
    Law("density", "المادّة", "الكثافة", "الكثافة = الكتلة ÷ الحجم",
        (V("rho", "الكثافة", "كغ/م³", True), V("m", "الكتلة", "كغ", True), V("Vol", "الحجم", "م³", True)),
        lambda x: x["rho"] * x["Vol"] - x["m"]),
    Law("ke", "الطاقة", "الطاقة الحركية", "طح = ½ × ك × ع²",
        (V("E", "الطاقة الحركية", "جول"), V("m", "الكتلة", "كغ", True), V("v", "السرعة", "م/ث", True)),
        lambda x: 0.5 * x["m"] * x["v"] ** 2 - x["E"]),
    Law("pe", "الطاقة", "طاقة الوضع", "طو = ك × ج × ع",
        (V("E", "طاقة الوضع", "جول"), V("m", "الكتلة", "كغ", True), V("h", "الارتفاع", "م")),
        lambda x: x["m"] * G * x["h"] - x["E"]),
    Law("work", "الطاقة", "الشغل", "الشغل = القوّة × المسافة",
        (V("W", "الشغل", "جول"), V("F", "القوّة", "نيوتن"), V("d", "المسافة", "م")),
        lambda x: x["F"] * x["d"] - x["W"]),
    Law("power", "الطاقة", "القدرة", "القدرة = الشغل ÷ الزمن",
        (V("P", "القدرة", "واط"), V("W", "الشغل", "جول"), V("t", "الزمن", "ث", True)),
        lambda x: x["P"] * x["t"] - x["W"]),
    Law("ohm", "الكهرباء", "قانون أوم", "الجهد = التيار × المقاومة (ج = ت × م)",
        (V("U", "الجهد", "فولت"), V("I", "التيار", "أمبير"), V("R", "المقاومة", "أوم", True)),
        lambda x: x["I"] * x["R"] - x["U"]),
    Law("epower", "الكهرباء", "القدرة الكهربائية", "القدرة = الجهد × التيار",
        (V("P", "القدرة", "واط"), V("U", "الجهد", "فولت"), V("I", "التيار", "أمبير")),
        lambda x: x["U"] * x["I"] - x["P"]),
    Law("charge", "الكهرباء", "الشحنة", "الشحنة = التيار × الزمن",
        (V("Q", "الشحنة", "كولوم"), V("I", "التيار", "أمبير"), V("t", "الزمن", "ث", True)),
        lambda x: x["I"] * x["t"] - x["Q"]),
    Law("energy_e", "الكهرباء", "الطاقة الكهربائية", "الطاقة = القدرة × الزمن",
        (V("E", "الطاقة", "جول"), V("P", "القدرة", "واط"), V("t", "الزمن", "ث", True)),
        lambda x: x["P"] * x["t"] - x["E"]),
    Law("wave", "الموجات", "سرعة الموجة", "السرعة = التردّد × الطول الموجي",
        (V("v", "السرعة", "م/ث"), V("f", "التردّد", "هرتز", True), V("lam", "الطول الموجي", "م", True)),
        lambda x: x["f"] * x["lam"] - x["v"]),
    Law("period", "الموجات", "الزمن الدوري", "الزمن الدوري = ١ ÷ التردّد",
        (V("T", "الزمن الدوري", "ث", True), V("f", "التردّد", "هرتز", True)),
        lambda x: x["T"] * x["f"] - 1),
    Law("heat", "الحرارة", "كمّية الحرارة", "كمّية الحرارة = الكتلة × السعة الحرارية × التغيّر في الحرارة",
        (V("Q", "كمّية الحرارة", "جول"), V("m", "الكتلة", "كغ", True),
         V("c", "السعة الحرارية النوعية", "جول/(كغ·°س)", True), V("dT", "التغيّر في درجة الحرارة", "°س")),
        lambda x: x["m"] * x["c"] * x["dT"] - x["Q"]),
)

LAW_BY_KEY = {l.key: l for l in LAWS}


def topics() -> List[str]:
    out = []
    for l in LAWS:
        if l.topic not in out:
            out.append(l.topic)
    return out


def _roots(f: Callable[[float], float], positive: bool) -> List[float]:
    """Real roots of f in a wide range, by scanning sign changes on a
    logarithmic grid and refining by bisection."""
    grid = [0.0]
    for e in range(-9, 13):
        for k in (1, 2, 5):
            grid.append(k * 10.0 ** e)
    grid = sorted(set(grid))
    pts = grid if positive else sorted({-g for g in grid} | set(grid))
    roots: List[float] = []

    def safe(x):
        try:
            y = f(x)
            return y if math.isfinite(y) else None
        except (ZeroDivisionError, OverflowError, ValueError):
            return None
    prev_x, prev_y = None, None
    for x in pts:
        y = safe(x)
        if y is None:
            prev_x, prev_y = None, None
            continue
        if y == 0:
            roots.append(x)
        elif prev_y is not None and (prev_y < 0) != (y < 0):
            a, b, fa = prev_x, x, prev_y
            for _ in range(200):
                m = (a + b) / 2
                fm = safe(m)
                if fm is None:
                    break
                if (fm < 0) == (fa < 0):
                    a, fa = m, fm
                else:
                    b = m
            roots.append((a + b) / 2)
        prev_x, prev_y = x, y
    out: List[float] = []
    for r in sorted(roots):
        if positive and r <= 0:
            continue
        if not out or abs(r - out[-1]) > 1e-9 * max(1.0, abs(r)):
            out.append(r)
    return out


def fmt(x: float) -> str:
    if x == 0:
        return "0"
    if abs(x) >= 1e6 or abs(x) < 1e-3:
        return f"{x:.4g}"
    return f"{x:.4f}".rstrip("0").rstrip(".")


def solve(law_key: str, known: Dict[str, float]) -> Tuple[str, List[float], List[str]]:
    """(unknown key, solutions, explanation lines)."""
    law = LAW_BY_KEY[law_key]
    keys = [v.key for v in law.variables]
    missing = [k for k in keys if k not in known]
    if len(missing) != 1:
        raise ValueError("اترك كمّية واحدة فقط فارغة، وهي المطلوبة.")
    unknown = missing[0]
    var = next(v for v in law.variables if v.key == unknown)
    for v in law.variables:
        if v.key in known and v.positive and known[v.key] <= 0:
            raise ValueError(f"{v.name} يجب أن تكون موجبة.")

    def f(x):
        d = dict(known)
        d[unknown] = x
        return law.residual(d)
    sols = _roots(f, var.positive)
    lines = [f"القانون: {law.text}."]
    given = "، ".join(f"{v.name} = {fmt(known[v.key])} {v.unit}" for v in law.variables if v.key in known)
    lines.append(f"المعطيات: {given}.")
    if not sols:
        lines.append(f"لا توجد قيمة {('موجبة ' if var.positive else '')}لـ{var.name} تحقّق القانون بهذه المعطيات.")
    elif len(sols) == 1:
        lines.append(f"المطلوب: {var.name} = {fmt(sols[0])} {var.unit}.")
    else:
        lines.append(f"للمسألة حلّان: {var.name} = " + " أو ".join(f"{fmt(s)} {var.unit}" for s in sols) + ".")
    return unknown, sols, lines


# ---------------------------------------------------------------------------
# resistor networks
# ---------------------------------------------------------------------------

def parse_resistors(text: str) -> List[float]:
    t = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")).replace("،", " ").replace(",", " ")
    vals = []
    for tok in t.split():
        mult = 1.0
        low = tok.lower()
        if low.endswith("k"):
            mult, tok = 1000.0, tok[:-1]
        elif low.endswith("m"):
            mult, tok = 1e6, tok[:-1]
        try:
            v = float(tok) * mult
        except ValueError:
            raise ValueError(f"{tok} ليست قيمة مقاومة.")
        if v <= 0:
            raise ValueError("المقاومة يجب أن تكون موجبة.")
        vals.append(v)
    if len(vals) < 2:
        raise ValueError("اكتب مقاومتين على الأقلّ.")
    return vals


def series(rs: Sequence[float]) -> Tuple[float, List[str]]:
    total = sum(rs)
    return total, [f"على التوالي تُجمع المقاومات: {' + '.join(fmt(r) for r in rs)} = {fmt(total)} أوم."]


def parallel(rs: Sequence[float]) -> Tuple[float, List[str]]:
    inv = sum(1.0 / r for r in rs)
    total = 1.0 / inv
    lines = [f"على التوازي: ١ ÷ المكافئة = {' + '.join('1/' + fmt(r) for r in rs)} = {fmt(inv)}",
             f"المقاومة المكافئة = ١ ÷ {fmt(inv)} = {fmt(total)} أوم (أصغر من أصغر مقاومة)."]
    return total, lines


def circuit_report(rs: Sequence[float], voltage: float, arrangement: str) -> List[str]:
    if voltage <= 0:
        raise ValueError("الجهد يجب أن يكون موجبًا.")
    total, lines = (series(rs) if arrangement == "series" else parallel(rs))
    current = voltage / total
    lines.append(f"التيار الكلّي = الجهد ÷ المقاومة = {fmt(voltage)} ÷ {fmt(total)} = {fmt(current)} أمبير.")
    lines.append(f"القدرة الكلّية = الجهد × التيار = {fmt(voltage * current)} واط.")
    for i, r in enumerate(rs, 1):
        if arrangement == "series":
            lines.append(f"المقاومة {i} ({fmt(r)} أوم): التيار {fmt(current)} أ، والجهد عليها {fmt(current * r)} فولت.")
        else:
            lines.append(f"المقاومة {i} ({fmt(r)} أوم): الجهد {fmt(voltage)} فولت، والتيار فيها {fmt(voltage / r)} أ.")
    return lines
