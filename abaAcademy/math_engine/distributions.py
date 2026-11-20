# -*- coding: utf-8 -*-
"""
abaAcademy.math_engine.distributions
====================================

التوزيعات الاحتمالية — the distributions of a statistics course, each with
its law shown: binomial, Poisson, geometric, discrete uniform, normal and
Student's t, for the probability of a value, at most a value, at least a
value, or between two values; their mean, variance and standard deviation;
z-scores; and confidence intervals for a mean. Pure Python (math.erf and a
numerical t distribution), so nothing extra is needed.
"""

from __future__ import annotations

import math
from typing import List, Tuple

KINDS = ["ذات الحدّين", "بواسون", "الهندسي", "المنتظم المتقطّع", "الطبيعي", "ستيودنت t"]
QUERIES = ["يساوي", "أقلّ من أو يساوي", "أكبر من أو يساوي", "بين قيمتين (شاملًا)"]


def _f(x: float) -> str:
    return f"{x:.6g}"


def normal_cdf(x: float, mu: float = 0.0, sigma: float = 1.0) -> float:
    return 0.5 * (1 + math.erf((x - mu) / (sigma * math.sqrt(2))))


def normal_inv(p: float) -> float:
    """Inverse of the standard normal CDF by bisection (enough for tables)."""
    if not 0 < p < 1:
        raise ValueError("الاحتمال بين صفر وواحد.")
    lo, hi = -40.0, 40.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if normal_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _t_pdf(x: float, df: float) -> float:
    return (math.gamma((df + 1) / 2) / (math.sqrt(df * math.pi) * math.gamma(df / 2))
            * (1 + x * x / df) ** (-(df + 1) / 2))


def t_cdf(x: float, df: float) -> float:
    """Simpson integration of the density from 0 to |x|."""
    if df <= 0:
        raise ValueError("درجات الحرية موجبة.")
    a = abs(x)
    n = 2000
    h = a / n if a else 0
    s = _t_pdf(0, df) + _t_pdf(a, df)
    for i in range(1, n):
        s += (4 if i % 2 else 2) * _t_pdf(i * h, df)
    area = s * h / 3
    return 0.5 + area if x >= 0 else 0.5 - area


def t_inv(p: float, df: float) -> float:
    lo, hi = -100.0, 100.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _pmf(kind: str, k: int, p1: float, p2: float) -> float:
    if kind == "ذات الحدّين":
        n, p = int(p1), p2
        return math.comb(n, k) * p ** k * (1 - p) ** (n - k) if 0 <= k <= n else 0.0
    if kind == "بواسون":
        lam = p1
        return math.exp(-lam) * lam ** k / math.factorial(k) if k >= 0 else 0.0
    if kind == "الهندسي":
        p = p1
        return (1 - p) ** (k - 1) * p if k >= 1 else 0.0
    if kind == "المنتظم المتقطّع":
        a, b = int(p1), int(p2)
        return 1 / (b - a + 1) if a <= k <= b else 0.0
    raise ValueError(kind)


def _support(kind: str, p1: float, p2: float) -> Tuple[int, int]:
    if kind == "ذات الحدّين":
        return 0, int(p1)
    if kind == "بواسون":
        return 0, int(p1 + 12 * math.sqrt(p1) + 30)
    if kind == "الهندسي":
        return 1, int(60 / max(p1, 1e-3)) + 10
    return int(p1), int(p2)


def check_params(kind: str, p1: float, p2: float) -> None:
    if kind == "ذات الحدّين" and (p1 < 0 or p1 != int(p1) or not 0 <= p2 <= 1):
        raise ValueError("ذات الحدّين: عدد المحاولات ن عدد صحيح، والاحتمال ح بين صفر وواحد.")
    if kind == "بواسون" and p1 <= 0:
        raise ValueError("بواسون: المعدّل لامدا موجب.")
    if kind == "الهندسي" and not 0 < p1 <= 1:
        raise ValueError("الهندسي: احتمال النجاح بين صفر وواحد.")
    if kind == "المنتظم المتقطّع" and p2 < p1:
        raise ValueError("المنتظم: الحدّ الأعلى لا يقلّ عن الأدنى.")
    if kind == "الطبيعي" and p2 <= 0:
        raise ValueError("الطبيعي: الانحراف المعياري موجب.")
    if kind == "ستيودنت t" and p1 <= 0:
        raise ValueError("t: درجات الحرية موجبة.")


def moments(kind: str, p1: float, p2: float) -> Tuple[float, float]:
    if kind == "ذات الحدّين":
        return p1 * p2, p1 * p2 * (1 - p2)
    if kind == "بواسون":
        return p1, p1
    if kind == "الهندسي":
        return 1 / p1, (1 - p1) / p1 ** 2
    if kind == "المنتظم المتقطّع":
        n = p2 - p1 + 1
        return (p1 + p2) / 2, (n * n - 1) / 12
    if kind == "الطبيعي":
        return p1, p2 ** 2
    return 0.0, (p1 / (p1 - 2) if p1 > 2 else float("inf"))


LAWS = {"ذات الحدّين": "ل(س = ك) = ق(ن، ك) × ح^ك × (1 − ح)^(ن − ك)",
        "بواسون": "ل(س = ك) = هـ^(−لامدا) × لامدا^ك ÷ ك!",
        "الهندسي": "ل(س = ك) = (1 − ح)^(ك − 1) × ح، عدد المحاولات حتى أوّل نجاح",
        "المنتظم المتقطّع": "ل(س = ك) = 1 ÷ (ب − أ + 1)",
        "الطبيعي": "ل(س ≤ x) = Φ((x − مو) ÷ سيغما)، و z = (x − مو) ÷ سيغما",
        "ستيودنت t": "التوزيع المتماثل حول الصفر بدرجات حرية د"}


def probability(kind: str, p1: float, p2: float, query: str, a: float, b: float = 0.0) -> Tuple[float, List[str]]:
    check_params(kind, p1, p2)
    steps = [f"القانون: {LAWS[kind]}."]
    if kind in ("الطبيعي", "ستيودنت t"):
        cdf = (lambda x: normal_cdf(x, p1, p2)) if kind == "الطبيعي" else (lambda x: t_cdf(x, p1))
        if kind == "الطبيعي":
            steps.append(f"z للقيمة {_f(a)} = ({_f(a)} − {_f(p1)}) ÷ {_f(p2)} = {_f((a - p1) / p2)}.")
        if query == "يساوي":
            steps.append("في التوزيع المتّصل احتمال قيمة واحدة بعينها صفر.")
            r = 0.0
        elif query == "أقلّ من أو يساوي":
            r = cdf(a)
        elif query == "أكبر من أو يساوي":
            r = 1 - cdf(a)
        else:
            if b < a:
                a, b = b, a
            r = cdf(b) - cdf(a)
            if kind == "الطبيعي":
                steps.append(f"z للقيمة {_f(b)} = {_f((b - p1) / p2)}.")
    else:
        lo, hi = _support(kind, p1, p2)
        k1 = int(round(a))
        if query == "يساوي":
            ks = [k1]
        elif query == "أقلّ من أو يساوي":
            ks = list(range(lo, min(k1, hi) + 1))
        elif query == "أكبر من أو يساوي":
            ks = list(range(lo, k1)) if k1 > lo else []
        else:
            k2 = int(round(b))
            k1, k2 = min(k1, k2), max(k1, k2)
            ks = list(range(max(k1, lo), min(k2, hi) + 1))
        s = sum(_pmf(kind, k, p1, p2) for k in ks)
        if query == "أكبر من أو يساوي":
            r = 1 - s
            steps.append(f"ل(س ≥ {k1}) = 1 − ل(س ≤ {k1 - 1}) = 1 − {_f(s)}.")
        else:
            r = s
            if len(ks) <= 6:
                steps.append(" + ".join(f"ل(س={k})={_f(_pmf(kind, k, p1, p2))}" for k in ks) or "لا قيم.")
    mean, var = moments(kind, p1, p2)
    steps.append(f"الاحتمال = {_f(r)}، أي {_f(100 * r)}٪.")
    steps.append(f"التوقّع (المتوسّط) = {_f(mean)}، والتباين = {_f(var)}، والانحراف المعياري = {_f(math.sqrt(var))}.")
    return r, steps


def confidence_interval(mean: float, sd: float, n: int, level: float = 0.95,
                        known_sigma: bool = False) -> Tuple[float, float, List[str]]:
    if n < 2 or sd <= 0 or not 0 < level < 1:
        raise ValueError("حجم العيّنة 2 فأكثر، والانحراف موجب، ومستوى الثقة بين صفر وواحد.")
    alpha = 1 - level
    if known_sigma or n >= 30:
        crit = normal_inv(1 - alpha / 2)
        name = f"z = {_f(crit)}"
    else:
        crit = t_inv(1 - alpha / 2, n - 1)
        name = f"t بدرجات حرية {n - 1} = {_f(crit)}"
    se = sd / math.sqrt(n)
    lo, hi = mean - crit * se, mean + crit * se
    return lo, hi, [f"الخطأ المعياري = الانحراف ÷ جذر ن = {_f(sd)} ÷ جذر {n} = {_f(se)}.",
                    f"القيمة الحرجة {name}.", f"هامش الخطأ = {_f(crit * se)}.",
                    f"فترة الثقة {_f(100 * level)}٪: من {_f(lo)} إلى {_f(hi)}."]
