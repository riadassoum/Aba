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
    if e is sp.S.NegativeInfinity:
        return "سالب ما لا نهاية"
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
                   ("tan", "ظا"), ("log", "لو"), ("exp", "هـ^"), ("pi", "π"), ("E", "هـ"), ("oo", "∞")):
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


def _real_points(sols) -> List:
    out = []
    for r in sols:
        try:
            if r.is_real:
                out.append(r)
        except Exception:
            pass
    return sorted(out, key=lambda v: float(v))


def study(text: str) -> Tuple[str, str]:
    """دراسة الدالة: domain hints, intercepts, critical points with their
    kind, intervals of increase and decrease, inflection points and
    asymptotes, for a function of one variable."""
    e = parse(text)
    if isinstance(e, sp.Eq):
        e = e.rhs if e.lhs.is_Symbol else e.lhs - e.rhs
    v = _vars(e)
    if len(v) != 1:
        raise MathError("ادرس دالة في متغيّر واحد، مثل س^3 - 3س.")
    x = v[0]
    lines: List[str] = []
    dom = sp.calculus.util.continuous_domain(e, x, sp.S.Reals)
    if dom != sp.S.Reals:
        excluded = sp.S.Reals - dom
        if excluded.is_FiniteSet:
            lines.append("المجال: كل الأعداد الحقيقية ما عدا " + "، ".join(speak(p) for p in excluded) + ".")
        else:
            lines.append(f"المجال: {written(dom)}.")
    else:
        lines.append("المجال: كل الأعداد الحقيقية.")
    try:
        y0 = e.subs(x, 0)
        if y0.is_finite and y0.is_real:
            lines.append(f"تقطع محور الصادات عند {speak(sp.nsimplify(y0))}.")
    except Exception:
        pass
    try:
        zeros = _real_points(sp.solve(sp.Eq(e, 0), x))
        if zeros:
            lines.append("أصفار الدالة (تقطع محور السينات عند): " + "، ".join(speak(z) for z in zeros) + ".")
        else:
            lines.append("لا تقطع محور السينات.")
    except Exception:
        pass
    d1 = sp.simplify(sp.diff(e, x))
    d2 = sp.simplify(sp.diff(d1, x))
    lines.append(f"المشتقّة الأولى: {speak(d1)}.")
    try:
        crit = _real_points(sp.solve(sp.Eq(d1, 0), x))
    except Exception:
        crit = []
    for c in crit:
        val = sp.simplify(e.subs(x, c))
        k = d2.subs(x, c)
        if k.is_positive:
            kind = "نهاية صغرى محلّية"
        elif k.is_negative:
            kind = "نهاية عظمى محلّية"
        else:
            kind = "نقطة حرجة (اختبار المشتقّة الثانية لا يحسم)"
        lines.append(f"{kind} عند {speak(x)} يساوي {speak(c)}، وقيمتها {speak(val)}.")
    # monotonicity between critical points and excluded points
    try:
        cuts = sorted(set([float(c) for c in crit] + [float(p) for p in (sp.S.Reals - dom)
                                                              if (sp.S.Reals - dom).is_FiniteSet]))
        edges = [-sp.oo] + [sp.nsimplify(c) for c in cuts] + [sp.oo]
        parts = []
        for a, b in zip(edges, edges[1:]):
            if a == -sp.oo and b == sp.oo:
                t = 0
            elif a == -sp.oo:
                t = b - 1
            elif b == sp.oo:
                t = a + 1
            else:
                t = (a + b) / 2
            sl = d1.subs(x, t)
            if sl.is_real and sl != 0:
                word = "متزايدة" if sl > 0 else "متناقصة"
                parts.append(f"{word} من {speak(a)} إلى {speak(b)}")
        if parts:
            lines.append("الاطّراد: " + "، و".join(parts) + ".")
    except Exception:
        pass
    try:
        infl = []
        for c in _real_points(sp.solve(sp.Eq(d2, 0), x)):
            left, right = d2.subs(x, c - sp.Rational(1, 1000)), d2.subs(x, c + sp.Rational(1, 1000))
            if left.is_real and right.is_real and (left > 0) != (right > 0):
                infl.append(c)
        if infl:
            lines.append("نقاط الانعطاف عند " + "، ".join(speak(c) for c in infl) + ".")
    except Exception:
        pass
    try:
        excl = sp.S.Reals - dom
        if excl.is_FiniteSet:
            for p in excl:
                lim = sp.limit(e, x, p, "+")
                if lim in (sp.oo, -sp.oo):
                    lines.append(f"خطّ تقارب رأسي عند {speak(x)} يساوي {speak(p)}.")
        for side, name in ((sp.oo, "ما لا نهاية"), (-sp.oo, "سالب ما لا نهاية")):
            lim = sp.limit(e, x, side)
            if lim.is_finite:
                lines.append(f"خطّ تقارب أفقي ص يساوي {speak(lim)} عندما يتّجه {speak(x)} إلى {name}.")
            elif lim in (sp.oo, -sp.oo):
                m = sp.limit(e / x, x, side)
                if m.is_finite and m != 0:
                    c = sp.limit(e - m * x, x, side)
                    if c.is_finite:
                        lines.append(f"خطّ تقارب مائل ص يساوي {speak(m * x + c)} عند {name}.")
                else:
                    lines.append(f"عندما يتّجه {speak(x)} إلى {name} تتّجه الدالة إلى {speak(lim)}.")
    except Exception:
        pass
    return "\n".join(lines), " ".join(lines)


def taylor(text: str, point: str = "0", order: int = 5) -> Tuple[str, str]:
    e = parse(text)
    v = _vars(e)
    if len(v) != 1:
        raise MathError("متسلسلة تايلور لدالة في متغيّر واحد.")
    x = v[0]
    a = parse(point) if point.strip() else sp.Integer(0)
    r = sp.series(e, x, a, order + 1).removeO()
    where = "ماكلورين" if a == 0 else f"تايلور حول {speak(a)}"
    return written(r) + " + ...", f"متسلسلة {where} حتى الرتبة {order}: {speak(r)}، زائد حدود أعلى."


def summation(text: str, start: str = "1", end: str = "n") -> Tuple[str, str]:
    """المجموع من البداية إلى النهاية على المتغيّر ن (أو أوّل متغيّر)."""
    e = parse(text)
    v = _vars(e)
    k = sp.Symbol("k") if sp.Symbol("k") in v else (v[0] if v else sp.Symbol("k"))
    lo = parse(start) if start.strip() else sp.Integer(1)
    hi = sp.oo if end.strip() in ("∞", "oo", "مالانهاية") else parse(end or "n")
    if hi == k:
        hi = sp.Symbol("n") if k != sp.Symbol("n") else sp.Symbol("m")
    r = sp.simplify(sp.summation(e, (k, lo, hi)))
    if r.has(sp.Sum):
        return "—", "لا أستطيع إيجاد هذا المجموع بصيغة مغلقة."
    return written(r), f"مجموع {speak(e)} من {speak(k)} يساوي {speak(lo)} إلى {speak(hi)}: {speak(r)}"


OPERATIONS = [("احسب", evaluate), ("بسّط", simplify), ("فُكّ الأقواس", expand), ("حلّل إلى عوامل", factor),
              ("حلّ المعادلة", solve), ("اشتقّ", differentiate), ("كامِل", integrate), ("ادرس الدالة", study)]
