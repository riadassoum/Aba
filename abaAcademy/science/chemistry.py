# -*- coding: utf-8 -*-
"""
abaAcademy.science.chemistry
============================

Chemistry calculations that explain themselves:

* **Formulas**: parse H2SO4, Ca(OH)2, CuSO4·5H2O (hydrates with · or *),
  count atoms of each element and read the formula aloud in Arabic.
* **Molar mass** with the contribution of every element and its mass
  percentage, from the standard atomic weights in the periodic table data.
* **Moles, mass and particles**: convert between grams, moles and number of
  particles (Avogadro's constant, exact since the 2019 SI redefinition).
* **Balancing equations**: H2 + O2 -> H2O is balanced by finding the
  smallest whole-number solution of the atom-conservation equations (exact
  fraction arithmetic on the null space of the composition matrix).
"""

from __future__ import annotations

import math
import re
from fractions import Fraction
from functools import reduce
from typing import Dict, List, Optional, Tuple

from .periodic import BY_SYMBOL
from ..tools.ar_count import count

AVOGADRO = 6.02214076e23

_SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_ELEMENT = re.compile(r"([A-Z][a-z]?)(\d*)")


def _clean(formula: str) -> str:
    f = formula.strip().translate(_SUBSCRIPTS).translate(_AR_DIGITS)
    return f.replace(" ", "").replace("[", "(").replace("]", ")").replace("{", "(").replace("}", ")")


def parse_formula(formula: str) -> Dict[str, int]:
    """Atom counts of a formula, e.g. Ca(OH)2 -> {Ca: 1, O: 2, H: 2}."""
    f = _clean(formula)
    if not f:
        raise ValueError("اكتب صيغة كيميائية.")
    parts = re.split(r"[·•.*]", f)
    total: Dict[str, int] = {}
    for part in parts:
        if not part:
            continue
        m = re.match(r"^(\d+)(.*)$", part)
        mult = 1
        if m:
            mult, part = int(m.group(1)), m.group(2)
        for el, n in _parse_group(part).items():
            total[el] = total.get(el, 0) + n * mult
    if not total:
        raise ValueError("لم أجد عناصر في الصيغة.")
    return total


def _parse_group(s: str) -> Dict[str, int]:
    stack: List[Dict[str, int]] = [{}]
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "(":
            stack.append({})
            i += 1
        elif ch == ")":
            if len(stack) == 1:
                raise ValueError("قوس إغلاق زائد في الصيغة.")
            i += 1
            j = i
            while j < len(s) and s[j].isdigit():
                j += 1
            mult = int(s[i:j]) if j > i else 1
            i = j
            group = stack.pop()
            for el, n in group.items():
                stack[-1][el] = stack[-1].get(el, 0) + n * mult
        else:
            m = _ELEMENT.match(s, i)
            if not m:
                raise ValueError(f"لم أفهم {s[i:]} في الصيغة. الرموز تبدأ بحرف كبير، مثل Na وCl.")
            el, n = m.group(1), m.group(2)
            if el.lower() not in BY_SYMBOL or BY_SYMBOL[el.lower()].symbol != el:
                raise ValueError(f"{el} ليس رمز عنصر.")
            stack[-1][el] = stack[-1].get(el, 0) + (int(n) if n else 1)
            i = m.end()
    if len(stack) != 1:
        raise ValueError("قوس غير مغلق في الصيغة.")
    return stack[0]


def element_name(symbol: str) -> str:
    return BY_SYMBOL[symbol.lower()].name


def read_formula(formula: str) -> str:
    """'H2SO4' -> 'ذرّتا هيدروجين، وذرّة كبريت، وأربع ذرّات أكسجين'."""
    atoms = parse_formula(formula)
    words = {1: "ذرّة", 2: "ذرّتا"}
    parts = []
    for el, n in atoms.items():
        name = element_name(el)
        if n == 1:
            parts.append(f"ذرّة {name}")
        elif n == 2:
            parts.append(f"ذرّتا {name}")
        elif n <= 10:
            parts.append(f"{n} ذرّات {name}")
        else:
            parts.append(f"{n} ذرّة {name}")
    return "، و".join(parts)


def molar_mass(formula: str) -> Tuple[float, List[str]]:
    atoms = parse_formula(formula)
    total = 0.0
    rows = []
    for el, n in atoms.items():
        m = BY_SYMBOL[el.lower()].mass
        total += m * n
        rows.append((el, n, m))
    lines = [f"الصيغة {formula.strip()}: {read_formula(formula)}."]
    for el, n, m in rows:
        lines.append(f"{element_name(el)} ({el}): {n} × {m:g} = {n * m:.3f} غ/مول، "
                     f"أي {100 * n * m / total:.2f}٪ من الكتلة")
    lines.append(f"الكتلة المولية = {total:.3f} غ/مول")
    return total, lines


def convert_amount(formula: str, value: float, unit: str) -> List[str]:
    """unit: 'g' (grams), 'mol', or 'particles'."""
    if value < 0:
        raise ValueError("الكمّية لا تكون سالبة.")
    mm, _ = molar_mass(formula)
    if unit == "g":
        mol = value / mm
        steps = [f"عدد المولات = الكتلة ÷ الكتلة المولية = {value:g} ÷ {mm:.3f} = {mol:.5g} مول"]
    elif unit == "mol":
        mol = value
        steps = [f"الكتلة = عدد المولات × الكتلة المولية = {value:g} × {mm:.3f} = {mol * mm:.5g} غ"]
    elif unit == "particles":
        mol = value / AVOGADRO
        steps = [f"عدد المولات = عدد الجسيمات ÷ عدد أفوغادرو = {value:.4g} ÷ {AVOGADRO:.6g} = {mol:.5g} مول"]
    else:
        raise ValueError(unit)
    steps.append(f"النتيجة: {mol * mm:.5g} غ = {mol:.5g} مول = {mol * AVOGADRO:.4g} جسيم.")
    return steps


# ---------------------------------------------------------------------------
# balancing
# ---------------------------------------------------------------------------

_ARROWS = ("->", "→", "=>", "⟶", "=", "يعطي")


def _split_side(side: str) -> List[Tuple[int, str]]:
    out = []
    for term in side.split("+"):
        t = _clean(term)
        if not t:
            continue
        m = re.match(r"^(\d+)(.*)$", t)
        if m and m.group(2) and not m.group(2)[0].isdigit():
            out.append((int(m.group(1)), m.group(2)))
        else:
            out.append((1, t))
    return out


def parse_equation(text: str) -> Tuple[List[str], List[str]]:
    for arrow in _ARROWS:
        if arrow in text:
            left, right = text.split(arrow, 1)
            break
    else:
        raise ValueError("اكتب المعادلة بسهم بين الطرفين، مثل: H2 + O2 -> H2O")
    lhs = [f for _, f in _split_side(left)]
    rhs = [f for _, f in _split_side(right)]
    if not lhs or not rhs:
        raise ValueError("يجب أن يكون في كلّ طرف مادّة واحدة على الأقلّ.")
    return lhs, rhs


def _nullspace_vector(rows: List[List[Fraction]], n: int) -> Optional[List[Fraction]]:
    """One non-zero vector x with rows·x = 0 (reduced row echelon form)."""
    m = [r[:] for r in rows]
    pivots = []
    r = 0
    for c in range(n):
        p = next((i for i in range(r, len(m)) if m[i][c] != 0), None)
        if p is None:
            continue
        m[r], m[p] = m[p], m[r]
        pv = m[r][c]
        m[r] = [x / pv for x in m[r]]
        for i in range(len(m)):
            if i != r and m[i][c] != 0:
                f = m[i][c]
                m[i] = [a - f * b for a, b in zip(m[i], m[r])]
        pivots.append(c)
        r += 1
        if r == len(m):
            break
    free = [c for c in range(n) if c not in pivots]
    if not free:
        return None
    # choose the last free variable = 1, the other free ones = 0
    x = [Fraction(0)] * n
    x[free[-1]] = Fraction(1)
    for i, c in enumerate(pivots):
        x[c] = -sum(m[i][j] * x[j] for j in free)
    return x


def balance(text: str) -> Tuple[List[int], List[str], List[str], str]:
    """(coefficients, reactants, products, balanced text). Raises ValueError
    when the equation can't be balanced (missing element, impossible)."""
    lhs, rhs = parse_equation(text)
    species = lhs + rhs
    comps = [parse_formula(s) for s in species]
    left_el = set().union(*(comps[i] for i in range(len(lhs))))
    right_el = set().union(*(comps[i] for i in range(len(lhs), len(species))))
    if left_el != right_el:
        missing = (left_el ^ right_el)
        raise ValueError("عناصر في طرف دون الآخر: " + "، ".join(element_name(e) for e in sorted(missing)))
    elements = sorted(left_el)
    rows = []
    for el in elements:
        row = [Fraction(comps[i].get(el, 0)) * (1 if i < len(lhs) else -1) for i in range(len(species))]
        rows.append(row)
    x = _nullspace_vector(rows, len(species))
    if x is None or any(v == 0 for v in x):
        raise ValueError("تعذّرت موازنة المعادلة؛ تحقّق من الصيغ.")
    if all(v < 0 for v in x):
        x = [-v for v in x]
    if any(v < 0 for v in x):
        raise ValueError("تعذّرت موازنة المعادلة بمعاملات موجبة؛ ربما في الطرفين خطأ.")
    lcm = reduce(lambda a, b: a * b // math.gcd(a, b), (v.denominator for v in x), 1)
    ints = [int(v * lcm) for v in x]
    g = reduce(math.gcd, ints)
    ints = [v // g for v in ints]

    def side(names, coefs):
        return " + ".join((f"{c}" if c != 1 else "") + n for c, n in zip(coefs, names))
    text_out = f"{side(lhs, ints[:len(lhs)])} → {side(rhs, ints[len(lhs):])}"
    return ints, lhs, rhs, text_out


def balance_explained(text: str) -> List[str]:
    ints, lhs, rhs, out = balance(text)
    lines = [f"المعادلة الموزونة: {out}"]
    species = lhs + rhs
    comps = [parse_formula(s) for s in species]
    for el in sorted(set().union(*comps)):
        left = sum(ints[i] * comps[i].get(el, 0) for i in range(len(lhs)))
        lines.append(f"{element_name(el)}: {count(left, 'atom')} في كلّ طرف.")
    return lines
