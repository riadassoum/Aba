# -*- coding: utf-8 -*-
"""
abaAcademy.science.solutions
============================

المحاليل والحموض والغازات — the calculations of a school chemistry course,
each answered with its law and the steps: pH and pOH of strong and weak
acids and bases, molarity, dilution (M1V1 = M2V2), mass percent, and the
ideal gas law PV = nRT. Molar masses come from the periodic-table data the
chemistry calculator already uses.
"""

from __future__ import annotations

import math
from typing import List, Tuple

R_GAS = 0.082057                 # L·atm/(mol·K)
KW = 1e-14


def _fmt(x: float, digits: int = 4) -> str:
    if x == 0:
        return "0"
    if abs(x) < 1e-3 or abs(x) >= 1e6:
        m, e = f"{x:.3e}".split("e")
        return f"{m} × 10^{int(e)}"
    return f"{round(x, digits):g}"


def _pos(x: float, what: str) -> float:
    if x <= 0:
        raise ValueError(f"{what} يجب أن يكون موجبًا.")
    return x


def ph_strong_acid(conc: float, protons: int = 1) -> Tuple[float, List[str]]:
    c = _pos(conc, "التركيز") * protons
    ph = -math.log10(c)
    return ph, [f"الحمض القوي يتأيّن كلّيًّا، فتركيز أيون الهيدروجين = {_fmt(c)} مول/لتر.",
                f"pH = −لو[H⁺] = −لو({_fmt(c)}) = {_fmt(ph, 2)}.", describe_ph(ph)]


def ph_strong_base(conc: float, hydroxides: int = 1) -> Tuple[float, List[str]]:
    c = _pos(conc, "التركيز") * hydroxides
    poh = -math.log10(c)
    ph = 14 - poh
    return ph, [f"القاعدة القوية تتأيّن كلّيًّا، فتركيز الهيدروكسيد = {_fmt(c)} مول/لتر.",
                f"pOH = −لو({_fmt(c)}) = {_fmt(poh, 2)}، و pH = 14 − pOH = {_fmt(ph, 2)}.", describe_ph(ph)]


def ph_weak_acid(conc: float, ka: float) -> Tuple[float, List[str]]:
    c, ka = _pos(conc, "التركيز"), _pos(ka, "ثابت التأيّن")
    x = (-ka + math.sqrt(ka * ka + 4 * ka * c)) / 2          # exact root of x²/(c−x) = Ka
    ph = -math.log10(x)
    return ph, [f"Ka = x² ÷ (C − x)، وبحلّ المعادلة التربيعية x = [H⁺] = {_fmt(x)} مول/لتر.",
                f"نسبة التأيّن = {_fmt(100 * x / c, 2)}٪.", f"pH = −لو({_fmt(x)}) = {_fmt(ph, 2)}.", describe_ph(ph)]


def ph_weak_base(conc: float, kb: float) -> Tuple[float, List[str]]:
    c, kb = _pos(conc, "التركيز"), _pos(kb, "ثابت التأيّن")
    x = (-kb + math.sqrt(kb * kb + 4 * kb * c)) / 2
    poh = -math.log10(x)
    ph = 14 - poh
    return ph, [f"Kb = x² ÷ (C − x)، فـ x = [OH⁻] = {_fmt(x)} مول/لتر.",
                f"pOH = {_fmt(poh, 2)}، و pH = 14 − pOH = {_fmt(ph, 2)}.", describe_ph(ph)]


def from_ph(ph: float) -> List[str]:
    h = 10 ** -ph
    return [f"[H⁺] = 10^−pH = {_fmt(h)} مول/لتر.", f"pOH = 14 − {_fmt(ph, 2)} = {_fmt(14 - ph, 2)}.",
            f"[OH⁻] = {_fmt(KW / h)} مول/لتر.", describe_ph(ph)]


def describe_ph(ph: float) -> str:
    if ph < 7 - 1e-9:
        kind = "حمضي" + ("، شديد الحموضة" if ph < 3 else "")
    elif ph > 7 + 1e-9:
        kind = "قاعدي" + ("، شديد القاعدية" if ph > 11 else "")
    else:
        kind = "متعادل"
    return f"المحلول {kind}."


def molarity(moles: float = 0, grams: float = 0, molar_mass: float = 0, volume_l: float = 0) -> Tuple[float, List[str]]:
    v = _pos(volume_l, "الحجم")
    steps = []
    if grams and molar_mass:
        moles = grams / molar_mass
        steps.append(f"عدد المولات = الكتلة ÷ الكتلة المولية = {_fmt(grams)} ÷ {_fmt(molar_mass)} = {_fmt(moles)} مول.")
    _pos(moles, "عدد المولات")
    m = moles / v
    steps.append(f"المولارية = المولات ÷ الحجم باللتر = {_fmt(moles)} ÷ {_fmt(v)} = {_fmt(m)} مول/لتر.")
    return m, steps


def dilution(m1: float = 0, v1: float = 0, m2: float = 0, v2: float = 0) -> Tuple[float, List[str]]:
    """Exactly one of the four is zero (the unknown)."""
    vals = {"M1": m1, "V1": v1, "M2": m2, "V2": v2}
    unknown = [k for k, v in vals.items() if not v]
    if len(unknown) != 1:
        raise ValueError("اترك قيمة واحدة فقط فارغة (المجهول).")
    u = unknown[0]
    if u == "M1":
        r = m2 * v2 / v1
    elif u == "V1":
        r = m2 * v2 / m1
    elif u == "M2":
        r = m1 * v1 / v2
    else:
        r = m1 * v1 / m2
    vals[u] = r
    return r, ["قانون التخفيف: M1 × V1 = M2 × V2.",
               f"{u} = {_fmt(r)}" + (" مول/لتر." if u.startswith("M") else " (بوحدة الحجم نفسها)."),
               f"التحقّق: {_fmt(vals['M1'])} × {_fmt(vals['V1'])} = {_fmt(vals['M2'])} × {_fmt(vals['V2'])}."]


def mass_percent(solute_g: float, solution_g: float) -> Tuple[float, List[str]]:
    p = 100 * _pos(solute_g, "كتلة المذاب") / _pos(solution_g, "كتلة المحلول")
    return p, [f"النسبة الكتلية = كتلة المذاب ÷ كتلة المحلول × 100 = {_fmt(solute_g)} ÷ {_fmt(solution_g)} × 100 "
               f"= {_fmt(p, 2)}٪."]


def ideal_gas(p_atm: float = 0, v_l: float = 0, n: float = 0, t_k: float = 0) -> Tuple[float, List[str]]:
    vals = {"P": p_atm, "V": v_l, "n": n, "T": t_k}
    unknown = [k for k, v in vals.items() if not v]
    if len(unknown) != 1:
        raise ValueError("اترك قيمة واحدة فقط فارغة (المجهول).")
    u = unknown[0]
    if u == "P":
        r = n * R_GAS * t_k / v_l
        unit = "ضغط جوّي"
    elif u == "V":
        r = n * R_GAS * t_k / p_atm
        unit = "لتر"
    elif u == "n":
        r = p_atm * v_l / (R_GAS * t_k)
        unit = "مول"
    else:
        r = p_atm * v_l / (n * R_GAS)
        unit = f"كلفن ({_fmt(r - 273.15, 2)} درجة مئوية)"
    return r, ["قانون الغاز المثالي: P × V = n × R × T، و R = 0.0821 لتر·ضغط جوّي/(مول·كلفن).",
               f"{u} = {_fmt(r)} {unit}."]


COMMON_KA = [("حمض الخلّ (الأسيتيك)", 1.8e-5), ("حمض الفورميك (النمليك)", 1.8e-4),
             ("حمض الهيدروفلوريك", 6.8e-4), ("حمض البنزويك", 6.3e-5), ("حمض الكربونيك", 4.3e-7),
             ("حمض الهيبوكلوروز", 3.0e-8)]
COMMON_KB = [("الأمونيا", 1.8e-5), ("ميثيل أمين", 4.4e-4), ("البيريدين", 1.7e-9)]
