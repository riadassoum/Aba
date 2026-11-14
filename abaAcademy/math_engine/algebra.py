# -*- coding: utf-8 -*-
"""
abaAcademy.math_engine.algebra
==============================

Three school tools that explain their working step by step, in Arabic:

* **Equation solver** for linear and quadratic equations in one unknown,
  written the way a learner types them: ``2س + 3 = 7``, ``x^2 - 5x + 6 = 0``,
  ``3x² = 12``. Exact arithmetic (fractions and simplified roots such as
  2√3), the discriminant, and complex roots when it is negative.
* **Geometry calculator**: area, perimeter, volume and surface area of the
  common plane and solid shapes, plus the Pythagorean theorem.
* **Number bases**: conversion between binary, octal, decimal and
  hexadecimal, showing the repeated division or the place values.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List, Optional, Sequence, Tuple

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")
VAR_NAMES = ("x", "س", "ص", "y", "ع", "n", "a")


def fmt(x: Fraction) -> str:
    if x.denominator == 1:
        return str(x.numerator)
    return f"{x.numerator}/{x.denominator}"


# ---------------------------------------------------------------------------
# polynomial parsing (degree ≤ 2)
# ---------------------------------------------------------------------------

def _normalise(text: str) -> Tuple[str, str]:
    t = text.translate(_AR_DIGITS)
    t = (t.replace("²", "^2").replace("−", "-").replace("×", "*").replace("÷", "/")
         .replace("**", "^").replace(" ", ""))
    var = next((v for v in VAR_NAMES if v in t), "x")
    return t, var


_TERM = re.compile(r"([+-]?)(\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?)?(\*)?(?:([^\d+\-*/^=().]))?(?:\^(\d+))?")


def parse_side(expr: str, var: str) -> Dict[int, Fraction]:
    """'3x^2-x+5' -> {2: 3, 1: -1, 0: 5}. Parentheses aren't supported."""
    if "(" in expr or ")" in expr:
        raise ValueError("اكتب المعادلة بلا أقواس، مثل 2x + 3 = 7.")
    if not expr:
        raise ValueError("أحد طرفي المعادلة فارغ.")
    coeffs: Dict[int, Fraction] = {}
    pos = 0
    while pos < len(expr):
        m = _TERM.match(expr, pos)
        if not m or m.end() == pos:
            raise ValueError(f"لم أفهم {expr[pos:]}.")
        sign, num, _star, letter, power = m.groups()
        if letter and letter != var:
            raise ValueError(f"المعادلة تحتوي على مجهولين ({var} و{letter}). الحلّ لمجهول واحد.")
        if not num and not letter:
            raise ValueError(f"لم أفهم {expr[pos:]}.")
        c = Fraction(num) if num else Fraction(1)
        if sign == "-":
            c = -c
        deg = 0
        if letter:
            deg = int(power) if power else 1
        elif power:
            c = c ** int(power)
        if deg > 2:
            raise ValueError("أحلّ المعادلات من الدرجة الأولى والثانية فقط.")
        coeffs[deg] = coeffs.get(deg, Fraction(0)) + c
        pos = m.end()
    return coeffs


def poly_text(c: Dict[int, Fraction], var: str) -> str:
    parts = []
    for deg in (2, 1, 0):
        v = c.get(deg, Fraction(0))
        if not v:
            continue
        sign = "-" if v < 0 else "+"
        a = abs(v)
        if deg == 0:
            body = fmt(a)
        else:
            body = ("" if a == 1 else fmt(a)) + var + ("²" if deg == 2 else "")
        parts.append((sign, body))
    if not parts:
        return "0"
    out = ("-" if parts[0][0] == "-" else "") + parts[0][1]
    for sign, body in parts[1:]:
        out += f" {sign} {body}"
    return out


# ---------------------------------------------------------------------------
# exact square roots
# ---------------------------------------------------------------------------

def simplify_sqrt(n: int) -> Tuple[int, int]:
    """√n = k√m with m square-free: returns (k, m)."""
    if n < 0:
        raise ValueError(n)
    k, m = 1, n
    f = 2
    while f * f <= m:
        while m % (f * f) == 0:
            m //= f * f
            k *= f
        f += 1
    return k, m


def sqrt_fraction(q: Fraction) -> Tuple[Fraction, int]:
    """√q = r·√m with r rational and m a square-free integer."""
    if q < 0:
        raise ValueError(q)
    # √(a/b) = √(ab)/b
    a, b = q.numerator, q.denominator
    k, m = simplify_sqrt(a * b)
    return Fraction(k, b), m


def surd_text(r: Fraction, m: int) -> str:
    if m == 1:
        return fmt(r)
    if r == 1:
        return f"√{m}"
    if r.denominator == 1:
        return f"{fmt(r)}√{m}"
    return f"{r.numerator}√{m}/{r.denominator}" if r.numerator != 1 else f"√{m}/{r.denominator}"


@dataclass
class Solution:
    equation: str
    degree: int
    roots: List[str]
    numeric: List[complex]
    steps: List[str]
    kind: str            # 'one' | 'two' | 'double' | 'complex' | 'none' | 'all'

    def spoken(self) -> str:
        return "\n".join(self.steps)


def solve(equation: str) -> Solution:
    if "=" not in equation:
        equation = equation + "=0"
    t, var = _normalise(equation)
    if t.count("=") != 1:
        raise ValueError("اكتب معادلة فيها علامة = واحدة.")
    left, right = t.split("=")
    L = parse_side(left, var)
    R = parse_side(right, var)
    steps = [f"المعادلة: {poly_text(L, var)} = {poly_text(R, var)}"]
    c = {d: L.get(d, Fraction(0)) - R.get(d, Fraction(0)) for d in (0, 1, 2)}
    if any(R.get(d) for d in (0, 1, 2)):
        steps.append(f"ننقل كلّ الحدود إلى الطرف الأيسر: {poly_text(c, var)} = 0")
    a, b, k = c[2], c[1], c[0]
    if a == 0 and b == 0:
        if k == 0:
            steps.append("الطرفان متساويان دائمًا: كلّ عدد حلّ للمعادلة.")
            return Solution(equation, 0, [], [], steps, "all")
        steps.append(f"نصل إلى {fmt(k)} = 0 وهذا مستحيل: لا حلّ للمعادلة.")
        return Solution(equation, 0, [], [], steps, "none")
    if a == 0:
        steps.append("معادلة من الدرجة الأولى.")
        steps.append(f"ننقل الحدّ الثابت: {poly_text({1: b}, var)} = {fmt(-k)}")
        x = -k / b
        if b != 1:
            steps.append(f"نقسم الطرفين على {fmt(b)}: {var} = {fmt(-k)} ÷ {fmt(b)} = {fmt(x)}")
        steps.append(f"الحلّ: {var} = {fmt(x)}")
        _check(steps, c, var, x)
        return Solution(equation, 1, [fmt(x)], [complex(float(x))], steps, "one")

    steps.append(f"معادلة من الدرجة الثانية: أ = {fmt(a)}، ب = {fmt(b)}، ج = {fmt(k)}.")
    if k == 0:
        steps.append(f"لا يوجد حدّ ثابت، فنُخرج {var} عاملًا مشتركًا: "
                     f"{var}({poly_text({1: a, 0: b}, var)}) = 0")
        x2 = -b / a
        roots = sorted({Fraction(0), x2})
        steps.append(f"إمّا {var} = 0 أو {var} = {fmt(x2)}")
        kind = "double" if x2 == 0 else "two"
        return Solution(equation, 2, [fmt(r) for r in roots], [complex(float(r)) for r in roots],
                        steps, kind)
    if b == 0 and (-k / a) >= 0:
        q = -k / a
        r, m = sqrt_fraction(q)
        s = surd_text(r, m)
        steps.append(f"لا يوجد حدّ في {var}: {var}² = {fmt(q)}، فنأخذ الجذر التربيعي للطرفين.")
        steps.append(f"{var} = ±{s}")
        val = math.sqrt(float(q))
        return Solution(equation, 2, [s, f"-{s}"], [complex(val), complex(-val)], steps, "two")
    disc = b * b - 4 * a * k
    steps.append(f"المميّز Δ = ب² − ٤أج = ({fmt(b)})² − ٤ × {fmt(a)} × {fmt(k)} = {fmt(disc)}")
    two_a = 2 * a
    if disc == 0:
        x = -b / two_a
        steps.append(f"المميّز صفر، فللمعادلة جذر واحد مكرّر: {var} = −ب ÷ ٢أ = {fmt(x)}")
        _check(steps, c, var, x)
        return Solution(equation, 2, [fmt(x)], [complex(float(x))], steps, "double")
    if disc > 0:
        r, m = sqrt_fraction(disc)
        if m == 1:
            x1, x2 = (-b + r) / two_a, (-b - r) / two_a
            steps.append(f"المميّز موجب ومربّع كامل (√Δ = {fmt(r)})، فللمعادلة جذران:")
            steps.append(f"{var}₁ = ({fmt(-b)} + {fmt(r)}) ÷ {fmt(two_a)} = {fmt(x1)}")
            steps.append(f"{var}₂ = ({fmt(-b)} − {fmt(r)}) ÷ {fmt(two_a)} = {fmt(x2)}")
            return Solution(equation, 2, [fmt(x1), fmt(x2)], [complex(float(x1)), complex(float(x2))],
                            steps, "two")
        p = -b / two_a
        q = r / two_a
        qs = surd_text(abs(q), m)
        steps.append(f"المميّز موجب، √Δ = {surd_text(r, m)}، فللمعادلة جذران حقيقيان:")
        steps.append(f"{var} = (−ب ± √Δ) ÷ ٢أ = {fmt(p)} ± {qs}" if p else f"{var} = ±{qs}")
        val = float(q) * math.sqrt(m)
        roots = [f"{fmt(p)} + {qs}" if p else qs, f"{fmt(p)} - {qs}" if p else f"-{qs}"]
        steps.append(f"تقريبًا: {var}₁ ≈ {float(p) + val:.4f}، {var}₂ ≈ {float(p) - val:.4f}")
        return Solution(equation, 2, roots, [complex(float(p) + val), complex(float(p) - val)],
                        steps, "two")
    r, m = sqrt_fraction(-disc)
    p = -b / two_a
    q = abs(r / two_a)
    qs = surd_text(q, m)
    steps.append("المميّز سالب: لا جذور حقيقية للمعادلة، وجذراها عددان مركّبان:")
    steps.append(f"{var} = {fmt(p)} ± {qs} ت" if p else f"{var} = ± {qs} ت")
    im = float(q) * math.sqrt(m)
    return Solution(equation, 2, [f"{fmt(p)} + {qs}i", f"{fmt(p)} - {qs}i"],
                    [complex(float(p), im), complex(float(p), -im)], steps, "complex")


def _check(steps, c, var, x: Fraction) -> None:
    val = c[2] * x * x + c[1] * x + c[0]
    steps.append(f"التحقّق: بالتعويض عن {var} بـ {fmt(x)} يكون الطرف الأيسر {fmt(val)}"
                 + (" ✓" if val == 0 else ""))


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Shape:
    key: str
    name: str
    params: Tuple[Tuple[str, str], ...]          # (key, Arabic label)
    solid: bool = False


SHAPES: Tuple[Shape, ...] = (
    Shape("square", "مربّع", (("a", "طول الضلع"),)),
    Shape("rectangle", "مستطيل", (("l", "الطول"), ("w", "العرض"))),
    Shape("triangle", "مثلّث (بالقاعدة والارتفاع)", (("b", "القاعدة"), ("h", "الارتفاع"))),
    Shape("triangle3", "مثلّث (بأضلاعه الثلاثة)", (("a", "الضلع الأول"), ("b", "الضلع الثاني"), ("c", "الضلع الثالث"))),
    Shape("circle", "دائرة", (("r", "نصف القطر"),)),
    Shape("parallelogram", "متوازي أضلاع", (("b", "القاعدة"), ("h", "الارتفاع"), ("s", "الضلع المجاور"))),
    Shape("trapezoid", "شبه منحرف", (("a", "القاعدة الكبرى"), ("b", "القاعدة الصغرى"), ("h", "الارتفاع"))),
    Shape("rhombus", "معيّن", (("d1", "القطر الأول"), ("d2", "القطر الثاني"))),
    Shape("polygon", "مضلّع منتظم", (("n", "عدد الأضلاع"), ("a", "طول الضلع"))),
    Shape("cube", "مكعّب", (("a", "طول الحرف"),), True),
    Shape("cuboid", "متوازي مستطيلات", (("l", "الطول"), ("w", "العرض"), ("h", "الارتفاع")), True),
    Shape("cylinder", "أسطوانة", (("r", "نصف القطر"), ("h", "الارتفاع")), True),
    Shape("cone", "مخروط", (("r", "نصف القطر"), ("h", "الارتفاع")), True),
    Shape("sphere", "كرة", (("r", "نصف القطر"),), True),
    Shape("pyramid", "هرم رباعي منتظم", (("a", "طول ضلع القاعدة"), ("h", "الارتفاع")), True),
)

SHAPE_BY_KEY = {s.key: s for s in SHAPES}


def _n(x: float) -> str:
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.4f}".rstrip("0").rstrip(".")


def compute_shape(key: str, values: Dict[str, float]) -> List[str]:
    s = SHAPE_BY_KEY[key]
    for k, label in s.params:
        if k not in values:
            raise ValueError(f"أدخل {label}.")
        if values[k] <= 0:
            raise ValueError(f"{label} يجب أن يكون موجبًا.")
    v = values
    pi = math.pi
    out: List[str] = [f"{s.name}:"]
    if key == "square":
        a = v["a"]
        out += [f"المساحة = الضلع² = {_n(a)}² = {_n(a * a)}",
                f"المحيط = ٤ × الضلع = {_n(4 * a)}",
                f"القطر = الضلع × √٢ ≈ {_n(a * math.sqrt(2))}"]
    elif key == "rectangle":
        l, w = v["l"], v["w"]
        out += [f"المساحة = الطول × العرض = {_n(l)} × {_n(w)} = {_n(l * w)}",
                f"المحيط = ٢ × (الطول + العرض) = {_n(2 * (l + w))}",
                f"القطر = √(الطول² + العرض²) ≈ {_n(math.hypot(l, w))}"]
    elif key == "triangle":
        b, h = v["b"], v["h"]
        out += [f"المساحة = ½ × القاعدة × الارتفاع = ½ × {_n(b)} × {_n(h)} = {_n(b * h / 2)}"]
    elif key == "triangle3":
        a, b, c = v["a"], v["b"], v["c"]
        if a + b <= c or a + c <= b or b + c <= a:
            raise ValueError("هذه الأطوال لا تكوّن مثلّثًا: مجموع أيّ ضلعين يجب أن يزيد على الثالث.")
        p = a + b + c
        sp = p / 2
        area = math.sqrt(sp * (sp - a) * (sp - b) * (sp - c))
        out += [f"المحيط = {_n(a)} + {_n(b)} + {_n(c)} = {_n(p)}",
                f"نصف المحيط ح = {_n(sp)}",
                f"المساحة بقانون هيرون = √(ح(ح−أ)(ح−ب)(ح−ج)) ≈ {_n(area)}"]
        sides = sorted([a, b, c])
        if abs(sides[0] ** 2 + sides[1] ** 2 - sides[2] ** 2) < 1e-9:
            out.append("المثلّث قائم الزاوية (يحقّق مبرهنة فيثاغورس).")
        if a == b == c:
            out.append("المثلّث متطابق الأضلاع.")
        elif a == b or b == c or a == c:
            out.append("المثلّث متطابق الضلعين.")
    elif key == "circle":
        r = v["r"]
        out += [f"المساحة = π × نق² = π × {_n(r)}² ≈ {_n(pi * r * r)}",
                f"المحيط = ٢ × π × نق ≈ {_n(2 * pi * r)}",
                f"القطر = ٢ × نق = {_n(2 * r)}"]
    elif key == "parallelogram":
        b, h, sd = v["b"], v["h"], v["s"]
        out += [f"المساحة = القاعدة × الارتفاع = {_n(b * h)}",
                f"المحيط = ٢ × (القاعدة + الضلع المجاور) = {_n(2 * (b + sd))}"]
    elif key == "trapezoid":
        a, b, h = v["a"], v["b"], v["h"]
        out += [f"المساحة = ½ × (مجموع القاعدتين) × الارتفاع = ½ × ({_n(a)} + {_n(b)}) × {_n(h)} = {_n((a + b) * h / 2)}"]
    elif key == "rhombus":
        d1, d2 = v["d1"], v["d2"]
        side = math.hypot(d1 / 2, d2 / 2)
        out += [f"المساحة = ½ × القطر الأول × القطر الثاني = {_n(d1 * d2 / 2)}",
                f"طول الضلع = √((ق١÷٢)² + (ق٢÷٢)²) ≈ {_n(side)}",
                f"المحيط = ٤ × الضلع ≈ {_n(4 * side)}"]
    elif key == "polygon":
        n, a = int(v["n"]), v["a"]
        if n < 3:
            raise ValueError("المضلّع يحتاج ثلاثة أضلاع على الأقلّ.")
        apothem = a / (2 * math.tan(pi / n))
        out += [f"المحيط = {n} × {_n(a)} = {_n(n * a)}",
                f"العامد = الضلع ÷ (٢ × ظا(١٨٠° ÷ ن)) ≈ {_n(apothem)}",
                f"المساحة = ½ × المحيط × العامد ≈ {_n(n * a * apothem / 2)}",
                f"مجموع الزوايا الداخلية = (ن − ٢) × ١٨٠° = {(n - 2) * 180}°",
                f"قياس الزاوية الداخلية = {_n((n - 2) * 180 / n)}°"]
    elif key == "cube":
        a = v["a"]
        out += [f"الحجم = الحرف³ = {_n(a ** 3)}",
                f"المساحة الكلّية = ٦ × الحرف² = {_n(6 * a * a)}",
                f"القطر الفراغي = الحرف × √٣ ≈ {_n(a * math.sqrt(3))}"]
    elif key == "cuboid":
        l, w, h = v["l"], v["w"], v["h"]
        out += [f"الحجم = الطول × العرض × الارتفاع = {_n(l * w * h)}",
                f"المساحة الكلّية = ٢(ط×ع + ط×ر + ع×ر) = {_n(2 * (l * w + l * h + w * h))}",
                f"المساحة الجانبية = محيط القاعدة × الارتفاع = {_n(2 * (l + w) * h)}"]
    elif key == "cylinder":
        r, h = v["r"], v["h"]
        out += [f"الحجم = π × نق² × ع ≈ {_n(pi * r * r * h)}",
                f"المساحة الجانبية = ٢ × π × نق × ع ≈ {_n(2 * pi * r * h)}",
                f"المساحة الكلّية = الجانبية + مساحة القاعدتين ≈ {_n(2 * pi * r * h + 2 * pi * r * r)}"]
    elif key == "cone":
        r, h = v["r"], v["h"]
        slant = math.hypot(r, h)
        out += [f"الحجم = ⅓ × π × نق² × ع ≈ {_n(pi * r * r * h / 3)}",
                f"الراسم = √(نق² + ع²) ≈ {_n(slant)}",
                f"المساحة الجانبية = π × نق × الراسم ≈ {_n(pi * r * slant)}",
                f"المساحة الكلّية ≈ {_n(pi * r * slant + pi * r * r)}"]
    elif key == "sphere":
        r = v["r"]
        out += [f"الحجم = ٤⁄٣ × π × نق³ ≈ {_n(4 / 3 * pi * r ** 3)}",
                f"المساحة السطحية = ٤ × π × نق² ≈ {_n(4 * pi * r * r)}"]
    elif key == "pyramid":
        a, h = v["a"], v["h"]
        slant = math.hypot(a / 2, h)
        out += [f"الحجم = ⅓ × مساحة القاعدة × الارتفاع = ⅓ × {_n(a * a)} × {_n(h)} = {_n(a * a * h / 3)}",
                f"الارتفاع الجانبي ≈ {_n(slant)}",
                f"المساحة الكلّية = مساحة القاعدة + ٢ × الضلع × الارتفاع الجانبي ≈ {_n(a * a + 2 * a * slant)}"]
    return out


def pythagoras(a: Optional[float] = None, b: Optional[float] = None,
               c: Optional[float] = None) -> List[str]:
    """Give two of the sides (c = hypotenuse) and get the third."""
    known = [x is not None for x in (a, b, c)]
    if sum(known) != 2:
        raise ValueError("أدخل ضلعين فقط واترك المطلوب فارغًا.")
    if c is None:
        c = math.hypot(a, b)
        return [f"الوتر² = {_n(a)}² + {_n(b)}² = {_n(a * a + b * b)}", f"الوتر = {_n(c)}"]
    leg = a if a is not None else b
    if leg >= c:
        raise ValueError("الوتر يجب أن يكون أطول من الضلع الآخر.")
    other = math.sqrt(c * c - leg * leg)
    return [f"الضلع² = الوتر² − الضلع المعلوم² = {_n(c)}² − {_n(leg)}² = {_n(c * c - leg * leg)}",
            f"الضلع المجهول = {_n(other)}"]


# ---------------------------------------------------------------------------
# number bases
# ---------------------------------------------------------------------------

BASES = {2: "الثنائي", 8: "الثماني", 10: "العشري", 16: "الست عشري"}
_DIGITS = "0123456789ABCDEF"


def parse_in_base(text: str, base: int) -> int:
    t = text.strip().upper().translate(_AR_DIGITS).replace(" ", "").replace("_", "")
    for prefix in ("0X", "0B", "0O"):
        if t.startswith(prefix):
            t = t[2:]
    if not t:
        raise ValueError("اكتب عددًا.")
    neg = t.startswith("-")
    if neg:
        t = t[1:]
    for ch in t:
        if ch not in _DIGITS[:base]:
            raise ValueError(f"الرمز {ch} غير مسموح في النظام {BASES.get(base, base)}.")
    v = int(t, base)
    return -v if neg else v


def to_base(n: int, base: int) -> str:
    if n == 0:
        return "0"
    neg = n < 0
    n = abs(n)
    out = []
    while n:
        n, r = divmod(n, base)
        out.append(_DIGITS[r])
    return ("-" if neg else "") + "".join(reversed(out))


def convert_steps(text: str, from_base: int, to_base_: int) -> List[str]:
    n = parse_in_base(text, from_base)
    steps = []
    if from_base != 10:
        digits = text.strip().upper().lstrip("-")
        for prefix in ("0X", "0B", "0O"):
            if digits.startswith(prefix):
                digits = digits[2:]
        terms = []
        L = len(digits)
        for i, ch in enumerate(digits):
            p = L - 1 - i
            terms.append(f"{int(ch, 16)}×{from_base}^{p}")
        steps.append(f"إلى العشري بقيم المنازل: {' + '.join(terms)} = {abs(n)}")
    if to_base_ != 10:
        m = abs(n)
        if m == 0:
            steps.append("الصفر صفر في كلّ الأنظمة.")
        else:
            divs = []
            while m:
                q, r = divmod(m, to_base_)
                divs.append(f"{m} ÷ {to_base_} = {q} والباقي {_DIGITS[r]}")
                m = q
            steps.append(f"القسمة المتكرّرة على {to_base_}:")
            steps += divs
            steps.append("نقرأ البواقي من الأسفل إلى الأعلى.")
    result = to_base(n, to_base_)
    steps.append(f"الناتج في النظام {BASES.get(to_base_, to_base_)}: {result}")
    return steps


def all_bases(n: int) -> str:
    return "، ".join(f"{BASES[b]}: {to_base(n, b)}" for b in (2, 8, 10, 16))
