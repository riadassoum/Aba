# -*- coding: utf-8 -*-
"""
abaAcademy.math_lab
===================

المختبر الرياضي الرمزي — algebra and calculus with SymPy (BSD licence,
https://www.sympy.org): simplify, expand and factor expressions, solve
equations and systems, differentiate, integrate and take limits, with the
answer both written and read aloud in Arabic mathematical language
(س زائد ثلاثة الكلّ تربيع، الجذر التربيعي لـ…).

Input may use Arabic variables (س ص ع) and Arabic-Indic digits; ^ is a
power and a number next to a letter multiplies (2س means 2×س). Only the
characters of mathematics are accepted before anything is parsed.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

try:
    import sympy as sp
    from sympy.parsing.sympy_parser import (convert_xor, implicit_multiplication_application, parse_expr,
                                            standard_transformations)
    AVAILABLE = True
except Exception:                                   # pragma: no cover - optional dependency
    sp = None
    AVAILABLE = False

AR_VARS = {"س": "x", "ص": "y", "ع": "z", "ن": "n", "ك": "k", "ت": "t", "ل": "l", "م": "m"}
SPOKEN_VARS = {v: k for k, v in AR_VARS.items()}
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫×÷−", "0123456789.*/-")
FUNCS = {"جا": "sin", "جتا": "cos", "ظا": "tan", "لو": "log", "جذر": "sqrt", "هـ": "E", "ط": "pi"}
SAFE = re.compile(r"^[0-9a-zA-Z+\-*/^().,= \t]*$")
ALLOWED_NAMES = {"x", "y", "z", "n", "k", "t", "l", "m", "a", "b", "c", "sin", "cos", "tan", "cot", "sec", "csc",
                 "asin", "acos", "atan", "log", "ln", "exp", "sqrt", "pi", "E", "e", "abs", "Abs", "factorial", "oo",
                 "sinh", "cosh", "tanh", "floor", "ceiling"}


class MathError(ValueError):
    pass


def normalise(text: str) -> str:
    t = text.strip().translate(DIGITS)
    for ar, en in sorted(FUNCS.items(), key=lambda x: -len(x[0])):
        t = t.replace(ar, f" {en} ")
    for ar, en in AR_VARS.items():
        t = t.replace(ar, en)
    t = t.replace("ln", "log").replace("√", "sqrt")
    return t


def parse(text: str):
    if not AVAILABLE:
        raise MathError("مكتبة SymPy غير موجودة في هذه النسخة.")
    t = normalise(text)
    if not t or not SAFE.match(t):
        raise MathError("اكتب تعبيرًا رياضيًّا فقط: أرقام ومتغيّرات وعمليات وأقواس.")
    for name in re.findall(r"[A-Za-z_]+", t):
        if name not in ALLOWED_NAMES and not (len(name) <= 3 and all(ch in "xyznktlmabc" for ch in name)):
            raise MathError(f"لا أعرف {name}. المتغيّرات المتاحة س ص ع، والدوال جا جتا ظا لو جذر.")
    tr = standard_transformations + (implicit_multiplication_application, convert_xor)
    local = {"e": sp.E, "ln": sp.log, "abs": sp.Abs}
    try:
        if t.count("=") == 1:
            left, right = t.split("=")
            return sp.Eq(parse_expr(left, local_dict=local, transformations=tr),
                         parse_expr(right, local_dict=local, transformations=tr))
        return parse_expr(t, local_dict=local, transformations=tr)
    except Exception:
        raise MathError("لم أفهم التعبير. تأكّد من الأقواس والعمليات.")


# -- reading aloud -----------------------------------------------------------

NUM_WORDS = {0: "صفر", 1: "واحد", 2: "اثنان", 3: "ثلاثة", 4: "أربعة", 5: "خمسة", 6: "ستة", 7: "سبعة",
             8: "ثمانية", 9: "تسعة", 10: "عشرة"}
FN_NAMES = {"sin": "جا", "cos": "جتا", "tan": "ظا", "cot": "ظتا", "log": "اللوغاريتم الطبيعي لـ", "exp": "هـ أس",
            "asin": "جا العكسي لـ", "acos": "جتا العكسي لـ", "atan": "ظا العكسي لـ", "Abs": "القيمة المطلقة لـ",
            "factorial": "مضروب"}


def _num(n) -> str:
    if n.is_Integer:
        v = int(n)
        if 0 <= v <= 10:
            return NUM_WORDS[v]
        return str(v)
    if n.is_Rational:
        return f"{_num(sp.Integer(n.p))} على {_num(sp.Integer(n.q))}"
    return str(sp.N(n, 6))


def _grouped(e) -> str:
    s = speak(e)
    return f"قوس {s} أغلق القوس" if (e.is_Add or (e.is_Mul and len(e.args) > 1 and not e.args[0].is_Number)) else s


def speak(e) -> str:
    """Arabic reading of a SymPy expression."""
    if e is sp.pi:
        return "باي"
    if e is sp.E:
        return "هـ"
    if e is sp.oo:
        return "ما لا نهاية"
    if e is sp.zoo or e is sp.nan:
        return "غير معرّف"
    if isinstance(e, sp.Eq):
        return f"{speak(e.lhs)} يساوي {speak(e.rhs)}"
    if e.is_Symbol:
        return SPOKEN_VARS.get(str(e), str(e))
    if e.is_Number:
        if e.is_negative:
            return "سالب " + _num(-e)
        return _num(e)
    if e.is_Add:
        terms = e.as_ordered_terms()
        out = speak(terms[0])
        for t in terms[1:]:
            c, rest = t.as_coeff_Mul()
            if c.is_negative:
                out += " ناقص " + speak(-t)
            else:
                out += " زائد " + speak(t)
        return out
    if e.is_Mul:
        num, den = sp.fraction(e)
        if den != 1:
            return f"{_grouped(num)} على {_grouped(den)}"
        c, rest = e.as_coeff_Mul()
        if c.is_negative:
            return "سالب " + speak(-e)
        parts = [_grouped(a) for a in e.as_ordered_factors()]
        return " في ".join(parts) if not (len(parts) == 2 and e.args[0].is_Number) else f"{parts[0]} {parts[1]}"
    if e.is_Pow:
        b, x = e.args
        if x == sp.Rational(1, 2):
            return f"الجذر التربيعي لـ {_grouped(b)}"
        if x == sp.Rational(1, 3):
            return f"الجذر التكعيبي لـ {_grouped(b)}"
        if x == -1:
            return f"واحد على {_grouped(b)}"
        if x.is_negative:
            return f"واحد على {speak(b ** (-x))}"
        base = _grouped(b) if not (b.is_Symbol or b.is_Number) else speak(b)
        if not (b.is_Symbol or b.is_Number):
            base += " الكلّ"
        if x == 2:
            return f"{base} تربيع"
        if x == 3:
            return f"{base} تكعيب"
        return f"{base} أس {_grouped(x)}"
    if e.is_Function:
        name = type(e).__name__
        arg = ", ".join(speak(a) for a in e.args)
        word = FN_NAMES.get(name, name)
        return f"{word} {arg}" if word.endswith("لـ") or word in ("جا", "جتا", "ظا", "ظتا", "مضروب", "هـ أس") else f"{word}({arg})"
    if isinstance(e, sp.Integral):
        return f"تكامل {speak(e.args[0])}"
    return str(e)


def written(e) -> str:
    s = sp.sstr(e).replace("**", "^").replace("*", "×").replace("sqrt", "√")
    for en, ar in SPOKEN_VARS.items():
        s = re.sub(rf"\b{en}\b", ar, s)
    for en, ar in (("asin", "جا⁻¹"), ("acos", "جتا⁻¹"), ("atan", "ظا⁻¹"), ("sin", "جا"), ("cos", "جتا"),
                   ("tan", "ظا"), ("log", "لو"), ("exp", "هـ^"), ("pi", "π")):
        s = re.sub(rf"\b{en}\b", ar, s)
    return s.replace("Eq(", "معادلة(")


# -- operations --------------------------------------------------------------

def _vars(e) -> List:
    return sorted(e.free_symbols, key=lambda s: str(s))


def simplify(text: str) -> Tuple[str, str]:
    r = sp.simplify(parse(text))
    return written(r), speak(r)


def expand(text: str) -> Tuple[str, str]:
    r = sp.expand(parse(text))
    return written(r), speak(r)


def factor(text: str) -> Tuple[str, str]:
    e = parse(text)
    r = sp.factorint(int(e)) if e.is_Integer else sp.factor(e)
    if isinstance(r, dict):
        parts = [f"{p}^{k}" if k > 1 else str(p) for p, k in r.items()]
        spoken = " في ".join(f"{p} أس {k}" if k > 1 else str(p) for p, k in r.items())
        return " × ".join(parts), spoken
    return written(r), speak(r)


def solve(text: str) -> Tuple[str, str]:
    """One equation (or expression = 0), or several separated by commas."""
    parts = [p for p in text.replace("،", ",").split(",") if p.strip()]
    eqs = []
    for p in parts:
        e = parse(p)
        eqs.append(e if isinstance(e, sp.Eq) else sp.Eq(e, 0))
    syms = sorted(set().union(*[q.free_symbols for q in eqs]), key=str)
    if not syms:
        ok = all(bool(q) for q in eqs)
        return ("صحيحة" if ok else "خاطئة"), ("المساواة صحيحة." if ok else "المساواة خاطئة.")
    sol = sp.solve(eqs, syms, dict=True)
    if not sol:
        return "لا حلّ", "ليس للمعادلة حلّ."
    written_parts, spoken_parts = [], []
    for s in sol:
        w = "، ".join(f"{written(k)} = {written(v)}" for k, v in s.items())
        sp_ = "، و".join(f"{speak(k)} يساوي {speak(v)}" for k, v in s.items())
        written_parts.append(w)
        spoken_parts.append(sp_)
    if len(sol) == 1:
        return written_parts[0], "الحلّ: " + spoken_parts[0] + "."
    n = len(sol)
    count = "حلّان" if n == 2 else (f"{n} حلول" if n <= 10 else f"{n} حلًّا")
    return " أو ".join(written_parts), f"للمعادلة {count}: " + "، أو ".join(spoken_parts) + "."


def differentiate(text: str) -> Tuple[str, str]:
    e = parse(text)
    v = _vars(e)
    if not v:
        return "0", "المشتقّة صفر لأن التعبير ثابت."
    r = sp.simplify(sp.diff(e, v[0]))
    return written(r), f"مشتقّة التعبير بالنسبة إلى {speak(v[0])}: {speak(r)}"


def integrate(text: str) -> Tuple[str, str]:
    e = parse(text)
    v = _vars(e) or [sp.Symbol("x")]
    r = sp.integrate(e, v[0])
    if r.has(sp.Integral):
        return "—", "لا أستطيع إيجاد تكامل هذا التعبير بصيغة مغلقة."
    return written(r) + " + C", f"التكامل بالنسبة إلى {speak(v[0])}: {speak(r)}، زائد ثابت التكامل."


def evaluate(text: str) -> Tuple[str, str]:
    e = parse(text)
    if e.free_symbols:
        raise MathError("في التعبير متغيّرات؛ استعمل التبسيط أو الحلّ بدل الحساب.")
    exact = sp.nsimplify(e) if not e.is_Number else e
    value = sp.N(e, 10)
    w = f"{written(exact)} ≈ {value}" if exact != value else str(value)
    return w, f"{speak(exact)}، أي تقريبًا {str(sp.N(e, 6))}"


def limit(text: str, point: str) -> Tuple[str, str]:
    e = parse(text)
    v = _vars(e)
    if not v:
        return written(e), speak(e)
    p = parse(point) if point.strip() not in ("∞", "oo", "مالانهاية") else sp.oo
    r = sp.limit(e, v[0], p)
    return written(r), f"النهاية عندما يقترب {speak(v[0])} من {speak(p)}: {speak(r)}"


OPERATIONS = [("احسب", evaluate), ("بسّط", simplify), ("فُكّ الأقواس", expand), ("حلّل إلى عوامل", factor),
              ("حلّ المعادلة", solve), ("اشتقّ", differentiate), ("كامِل", integrate)]
