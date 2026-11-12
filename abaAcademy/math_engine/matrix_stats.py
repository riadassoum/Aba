# -*- coding: utf-8 -*-
"""
abaAcademy.math_engine.matrix_stats
===================================

Matrices and descriptive statistics with spoken, step-by-step working.

Matrix arithmetic uses exact fractions, so an inverse comes out as ⅓ rather
than 0.3333 and every step can be read aloud exactly as a teacher would
write it. Supported: addition, subtraction, scalar multiple, product,
transpose, determinant (cofactor expansion for 2x2/3x3, row reduction
beyond), inverse (adjugate for 2x2, Gauss–Jordan otherwise), rank, and
solving linear systems.

Statistics: mean, median, mode(s), range, quartiles (the median-of-halves
method taught in schools), interquartile range, population and sample
variance and standard deviation, a frequency table and a text histogram
that the screen can also play as tones.
"""

from __future__ import annotations

import math
from collections import Counter
from fractions import Fraction
from typing import List, Optional, Sequence, Tuple

Matrix = List[List[Fraction]]

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,")


# ---------------------------------------------------------------------------
# parsing and speaking numbers
# ---------------------------------------------------------------------------

def parse_number(text: str) -> Fraction:
    t = text.strip().translate(_AR_DIGITS).replace("−", "-")
    if not t:
        raise ValueError("empty")
    if "/" in t:
        a, b = t.split("/", 1)
        return Fraction(Fraction(a.strip()), Fraction(b.strip()))
    return Fraction(t)


def parse_matrix(text: str) -> Matrix:
    """Rows on separate lines (or separated by ';'), entries by spaces or
    commas. Fractions like 1/3 and decimals are accepted."""
    raw_rows = [r for r in text.replace(";", "\n").replace("؛", "\n").splitlines() if r.strip()]
    rows: Matrix = []
    for r in raw_rows:
        cells = [c for c in r.replace("،", " ").replace(",", " ").split() if c]
        rows.append([parse_number(c) for c in cells])
    if not rows:
        raise ValueError("المصفوفة فارغة.")
    width = len(rows[0])
    if any(len(r) != width for r in rows):
        raise ValueError("كلّ صفوف المصفوفة يجب أن تحوي العدد نفسه من العناصر.")
    return rows


def fmt(x: Fraction) -> str:
    """Exact, readable: 3, -2, 1/3, 7/2."""
    if x.denominator == 1:
        return str(x.numerator)
    return f"{x.numerator}/{x.denominator}"


def speak_number(x: Fraction) -> str:
    """'سالب ثلاثة على اثنين' style reading for fractions."""
    if x.denominator == 1:
        return f"سالب {-x.numerator}" if x < 0 else str(x.numerator)
    sign = "سالب " if x < 0 else ""
    return f"{sign}{abs(x.numerator)} على {x.denominator}"


def fmt_matrix(m: Matrix) -> str:
    width = max((len(fmt(v)) for row in m for v in row), default=1)
    return "\n".join("  ".join(fmt(v).rjust(width) for v in row) for row in m)


def speak_matrix(m: Matrix) -> str:
    rows = []
    for i, row in enumerate(m, 1):
        rows.append(f"الصفّ {i}: " + "، ".join(speak_number(v) for v in row))
    return f"مصفوفة {len(m)} في {len(m[0])}. " + ". ".join(rows) + "."


def shape(m: Matrix) -> Tuple[int, int]:
    return len(m), len(m[0])


def identity(n: int) -> Matrix:
    return [[Fraction(int(i == j)) for j in range(n)] for i in range(n)]


def copy(m: Matrix) -> Matrix:
    return [row[:] for row in m]


# ---------------------------------------------------------------------------
# operations, each returning (result, steps)
# ---------------------------------------------------------------------------

Steps = List[str]


def add(a: Matrix, b: Matrix, sign: int = 1) -> Tuple[Matrix, Steps]:
    if shape(a) != shape(b):
        raise ValueError("الجمع والطرح يتطلّبان مصفوفتين بالأبعاد نفسها.")
    op = "+" if sign > 0 else "−"
    word = "نجمع" if sign > 0 else "نطرح"
    out, steps = [], [f"{word} العناصر المتناظرة عنصرًا عنصرًا."]
    for i, (ra, rb) in enumerate(zip(a, b), 1):
        row = []
        for j, (x, y) in enumerate(zip(ra, rb), 1):
            v = x + sign * y
            row.append(v)
            steps.append(f"العنصر ({i}، {j}): {fmt(x)} {op} {fmt(y)} = {fmt(v)}")
        out.append(row)
    return out, steps


def scale(a: Matrix, k: Fraction) -> Tuple[Matrix, Steps]:
    out = [[k * v for v in row] for row in a]
    return out, [f"نضرب كلّ عنصر في {fmt(k)}."]


def transpose(a: Matrix) -> Tuple[Matrix, Steps]:
    r, c = shape(a)
    return ([[a[i][j] for i in range(r)] for j in range(c)],
            ["نجعل كلّ صفّ عمودًا: العنصر (ص، ع) يصبح (ع، ص)."])


def multiply(a: Matrix, b: Matrix) -> Tuple[Matrix, Steps]:
    ra, ca = shape(a)
    rb, cb = shape(b)
    if ca != rb:
        raise ValueError(f"لا يمكن الضرب: عدد أعمدة الأولى ({ca}) لا يساوي عدد صفوف الثانية ({rb}).")
    steps = [f"الناتج مصفوفة {ra} في {cb}. كلّ عنصر = صفّ من الأولى × عمود من الثانية."]
    out = []
    for i in range(ra):
        row = []
        for j in range(cb):
            terms = [f"{fmt(a[i][k])}×{fmt(b[k][j])}" for k in range(ca)]
            v = sum((a[i][k] * b[k][j] for k in range(ca)), Fraction(0))
            row.append(v)
            steps.append(f"العنصر ({i + 1}، {j + 1}): {' + '.join(terms)} = {fmt(v)}")
        out.append(row)
    return out, steps


def _minor(m: Matrix, i: int, j: int) -> Matrix:
    return [row[:j] + row[j + 1:] for k, row in enumerate(m) if k != i]


def determinant(m: Matrix, steps: Optional[Steps] = None, depth: int = 0) -> Fraction:
    r, c = shape(m)
    if r != c:
        raise ValueError("المحدّد معرّف للمصفوفات المربّعة فقط.")
    log = steps if steps is not None else []
    if r == 1:
        return m[0][0]
    if r == 2:
        v = m[0][0] * m[1][1] - m[0][1] * m[1][0]
        if depth == 0:
            log.append(f"للمصفوفة ٢×٢: (أ×د) − (ب×ج) = "
                       f"({fmt(m[0][0])}×{fmt(m[1][1])}) − ({fmt(m[0][1])}×{fmt(m[1][0])}) = {fmt(v)}")
        return v
    if r == 3:
        total = Fraction(0)
        log.append("نفكّ المحدّد على الصفّ الأول بالعوامل المرافقة (+ − +).")
        for j in range(3):
            sub = _minor(m, 0, j)
            d = sub[0][0] * sub[1][1] - sub[0][1] * sub[1][0]
            sign = 1 if j % 2 == 0 else -1
            term = sign * m[0][j] * d
            log.append(f"العنصر {fmt(m[0][j])} بإشارة {'+' if sign > 0 else '−'}، "
                       f"ومحدّده الأصغر {fmt(d)}: الحدّ = {fmt(term)}")
            total += term
        log.append(f"المحدّد = {fmt(total)}")
        return total
    # larger: row reduction
    a = copy(m)
    n = r
    det = Fraction(1)
    log.append("نحوّل المصفوفة إلى شكل مثلّثي بعمليات الصفوف.")
    for col in range(n):
        pivot = next((k for k in range(col, n) if a[k][col] != 0), None)
        if pivot is None:
            log.append(f"العمود {col + 1} بلا محور، فالمحدّد صفر.")
            return Fraction(0)
        if pivot != col:
            a[col], a[pivot] = a[pivot], a[col]
            det = -det
            log.append(f"بدّلنا الصفّين {col + 1} و{pivot + 1} فتنعكس الإشارة.")
        det *= a[col][col]
        for k in range(col + 1, n):
            f = a[k][col] / a[col][col]
            if f:
                a[k] = [x - f * y for x, y in zip(a[k], a[col])]
    log.append(f"المحدّد = حاصل ضرب عناصر القطر (مع الإشارة) = {fmt(det)}")
    return det


def inverse(m: Matrix) -> Tuple[Optional[Matrix], Steps]:
    r, c = shape(m)
    if r != c:
        raise ValueError("المعكوس معرّف للمصفوفات المربّعة فقط.")
    steps: Steps = []
    det = determinant(m, steps)
    if det == 0:
        steps.append("المحدّد صفر، فالمصفوفة منفردة وليس لها معكوس.")
        return None, steps
    if r == 2:
        a, b = m[0]
        cc, d = m[1]
        inv = [[d / det, -b / det], [-cc / det, a / det]]
        steps.append("معكوس ٢×٢: نبدّل عنصري القطر الرئيسي، ونعكس إشارة الآخرَين، "
                     f"ثم نقسم على المحدّد {fmt(det)}.")
        return inv, steps
    n = r
    aug = [row[:] + ident for row, ident in zip(copy(m), identity(n))]
    steps.append("طريقة جاوس-جوردان: نضع مصفوفة الوحدة بجانبها، ونجري عمليات الصفوف "
                 "حتى يصبح الجانب الأيسر مصفوفة الوحدة.")
    for col in range(n):
        pivot = next(k for k in range(col, n) if aug[k][col] != 0)
        if pivot != col:
            aug[col], aug[pivot] = aug[pivot], aug[col]
            steps.append(f"نبدّل الصفّين {col + 1} و{pivot + 1}.")
        p = aug[col][col]
        if p != 1:
            aug[col] = [x / p for x in aug[col]]
            steps.append(f"نقسم الصفّ {col + 1} على {fmt(p)}.")
        for k in range(n):
            if k != col and aug[k][col] != 0:
                f = aug[k][col]
                aug[k] = [x - f * y for x, y in zip(aug[k], aug[col])]
                steps.append(f"ص{k + 1} ← ص{k + 1} − ({fmt(f)}) × ص{col + 1}")
    return [row[n:] for row in aug], steps


def rank(m: Matrix) -> int:
    a = copy(m)
    rows, cols = shape(a)
    rk = 0
    for col in range(cols):
        pivot = next((k for k in range(rk, rows) if a[k][col] != 0), None)
        if pivot is None:
            continue
        a[rk], a[pivot] = a[pivot], a[rk]
        for k in range(rows):
            if k != rk and a[k][col] != 0:
                f = a[k][col] / a[rk][col]
                a[k] = [x - f * y for x, y in zip(a[k], a[rk])]
        rk += 1
        if rk == rows:
            break
    return rk


def solve_system(coeffs: Matrix, constants: Sequence[Fraction]) -> Tuple[Optional[List[Fraction]], Steps]:
    """Solve A·x = b by Gauss–Jordan. Returns (solution or None, steps)."""
    n, c = shape(coeffs)
    if len(constants) != n:
        raise ValueError("عدد الثوابت يجب أن يساوي عدد المعادلات.")
    aug = [row[:] + [Fraction(b)] for row, b in zip(copy(coeffs), constants)]
    steps = ["نكتب المصفوفة الموسّعة ونحلّ بطريقة جاوس-جوردان."]
    rk_a = rank(coeffs)
    rk_aug = rank(aug)
    if rk_a < rk_aug:
        steps.append("النظام غير متّسق: لا يوجد حلّ.")
        return None, steps
    if rk_a < c:
        steps.append("للنظام عدد لا نهائي من الحلول (المتغيّرات أكثر من المعادلات المستقلّة).")
        return None, steps
    for col in range(c):
        pivot = next(k for k in range(col, n) if aug[k][col] != 0)
        aug[col], aug[pivot] = aug[pivot], aug[col]
        p = aug[col][col]
        aug[col] = [x / p for x in aug[col]]
        for k in range(n):
            if k != col and aug[k][col] != 0:
                f = aug[k][col]
                aug[k] = [x - f * y for x, y in zip(aug[k], aug[col])]
    sol = [aug[i][c] for i in range(c)]
    names = variable_names(c)
    steps.append("الحلّ: " + "، ".join(f"{names[i]} = {fmt(v)}" for i, v in enumerate(sol)))
    return sol, steps


def variable_names(n: int) -> List[str]:
    base = ["س", "ص", "ع", "ل", "م", "ن"]
    return base[:n] if n <= len(base) else [f"س{i + 1}" for i in range(n)]


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------

def parse_data(text: str) -> List[float]:
    t = text.translate(_AR_DIGITS).replace("،", " ").replace(",", " ").replace(";", " ")
    out = []
    for tok in t.split():
        try:
            out.append(float(tok))
        except ValueError:
            raise ValueError(f"القيمة {tok} ليست رقمًا.")
    if not out:
        raise ValueError("لا توجد بيانات.")
    return out


def _median(sorted_vals: Sequence[float]) -> float:
    n = len(sorted_vals)
    mid = n // 2
    if n % 2:
        return sorted_vals[mid]
    return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0


def quartiles(values: Sequence[float]) -> Tuple[float, float, float]:
    """Q1, Q2, Q3 by the median-of-halves method (the median itself is
    excluded from both halves when the count is odd)."""
    s = sorted(values)
    n = len(s)
    if n == 1:
        return s[0], s[0], s[0]
    q2 = _median(s)
    lower = s[: n // 2]
    upper = s[(n + 1) // 2:]
    return _median(lower), q2, _median(upper)


def modes(values: Sequence[float]) -> List[float]:
    c = Counter(values)
    top = max(c.values())
    if top == 1 and len(c) > 1:
        return []
    return sorted(v for v, k in c.items() if k == top)


def describe(values: Sequence[float]) -> dict:
    s = sorted(values)
    n = len(s)
    mean = sum(s) / n
    ss = sum((x - mean) ** 2 for x in s)
    q1, q2, q3 = quartiles(s)
    return {
        "count": n, "sum": sum(s), "min": s[0], "max": s[-1],
        "range": s[-1] - s[0], "mean": mean, "median": q2,
        "modes": modes(s), "q1": q1, "q3": q3, "iqr": q3 - q1,
        "var_pop": ss / n, "sd_pop": math.sqrt(ss / n),
        "var_sample": ss / (n - 1) if n > 1 else float("nan"),
        "sd_sample": math.sqrt(ss / (n - 1)) if n > 1 else float("nan"),
        "sorted": s,
    }


def _num(x: float, places: int = 4) -> str:
    if isinstance(x, float) and math.isnan(x):
        return "غير معرّف"
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.{places}f}".rstrip("0").rstrip(".")


def stats_report(values: Sequence[float]) -> str:
    d = describe(values)
    mode_txt = ("لا يوجد منوال (كلّ القيم تتكرّر مرّة واحدة)" if not d["modes"]
                else "، ".join(_num(m) for m in d["modes"]))
    lines = [
        f"عدد القيم: {d['count']}، مجموعها: {_num(d['sum'])}.",
        f"مرتّبة: {'، '.join(_num(v) for v in d['sorted'])}.",
        f"الوسط الحسابي: {_num(d['sum'])} ÷ {d['count']} = {_num(d['mean'])}.",
        f"الوسيط: {_num(d['median'])}.",
        f"المنوال: {mode_txt}.",
        f"أصغر قيمة {_num(d['min'])}، وأكبر قيمة {_num(d['max'])}، والمدى {_num(d['range'])}.",
        f"الربيع الأدنى {_num(d['q1'])}، والربيع الأعلى {_num(d['q3'])}، "
        f"والمدى الربيعي {_num(d['iqr'])}.",
        f"التباين للمجتمع {_num(d['var_pop'])}، والانحراف المعياري {_num(d['sd_pop'])}.",
        f"التباين للعيّنة {_num(d['var_sample'])}، والانحراف المعياري {_num(d['sd_sample'])}.",
    ]
    return "\n".join(lines)


def frequency_table(values: Sequence[float], bins: int = 0) -> List[Tuple[str, int, float, float]]:
    """[(label, count, low, high)]. With few distinct values each value is
    its own row; otherwise equal-width classes (Sturges' rule when ``bins``
    is 0)."""
    s = sorted(values)
    distinct = sorted(set(s))
    if len(distinct) <= 10 and not bins:
        c = Counter(s)
        return [(_num(v), c[v], v, v) for v in distinct]
    k = bins or max(1, int(math.ceil(math.log2(len(s)) + 1)))
    lo, hi = s[0], s[-1]
    if hi == lo:
        return [(_num(lo), len(s), lo, hi)]
    width = (hi - lo) / k
    out = []
    for i in range(k):
        a = lo + i * width
        b = lo + (i + 1) * width
        if i == k - 1:
            count = sum(1 for x in s if a <= x <= b)
        else:
            count = sum(1 for x in s if a <= x < b)
        out.append((f"من {_num(a, 2)} إلى أقلّ من {_num(b, 2)}" if i < k - 1
                    else f"من {_num(a, 2)} إلى {_num(b, 2)}", count, a, b))
    return out


def histogram_text(values: Sequence[float], width: int = 20) -> str:
    rows = frequency_table(values)
    top = max(c for _, c, _, _ in rows) or 1
    lines = []
    for label, count, _, _ in rows:
        bar = "■" * max(0, round(count / top * width))
        lines.append(f"{label}: {count} {bar}")
    return "\n".join(lines)


def histogram_tones(values: Sequence[float], low_hz: float = 300.0,
                    high_hz: float = 1200.0) -> List[Tuple[float, float]]:
    """(frequency, duration) per class: higher pitch = more values, so the
    shape of the distribution can be heard from left to right."""
    rows = frequency_table(values)
    top = max(c for _, c, _, _ in rows) or 1
    return [(low_hz + (high_hz - low_hz) * c / top if c else 0.0, 0.25) for _, c, _, _ in rows]
