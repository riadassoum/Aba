# -*- coding: utf-8 -*-
"""
abaAcademy.tools.zakat
======================

A zakat-on-wealth calculator (زكاة المال).

The learner enters what they own (cash, savings, gold and silver by weight,
trade goods, money owed to them that they expect to receive) and what they
owe now, plus today's price of a gram of gold and silver in their currency.
The calculator applies the nisab — 85 g of gold, or 595 g of silver if the
learner prefers the silver standard many scholars favour because it reaches
more of the poor — and the rate of one fortieth (2.5%) on wealth held for a
full lunar year.

It covers the common case only. Livestock, crops, buried treasure,
company shares and debts with special conditions follow other rulings, and
scholars differ in details such as worn jewellery; the screen says so and
suggests asking a trusted scholar for those.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

GOLD_NISAB_G = 85.0
SILVER_NISAB_G = 595.0
RATE = 0.025

ASSET_FIELDS = (
    ("cash", "النقد في اليد والحسابات الجارية"),
    ("savings", "المدّخرات والودائع"),
    ("gold_g", "الذهب (بالغرام، عيار ٢٤ أو ما يعادله)"),
    ("silver_g", "الفضّة (بالغرام)"),
    ("trade", "قيمة عروض التجارة (البضائع المعدّة للبيع)"),
    ("receivable", "الديون المرجوّة لك على الآخرين"),
    ("other", "أموال أخرى تجب فيها الزكاة"),
)
LIABILITY_FIELDS = (
    ("debts_due", "الديون الحالّة عليك الآن"),
)


@dataclass
class ZakatInput:
    values: Dict[str, float] = field(default_factory=dict)
    gold_price: float = 0.0          # per gram
    silver_price: float = 0.0        # per gram
    standard: str = "gold"           # "gold" | "silver"
    karat: int = 24                  # purity of the gold entered
    year_complete: bool = True       # held a full lunar year (حال الحول)


@dataclass
class ZakatResult:
    total_assets: float
    deductions: float
    net: float
    nisab: float
    due: float
    lines: List[str]


def _money(x: float) -> str:
    return f"{x:,.2f}"


def calculate(inp: ZakatInput) -> ZakatResult:
    v = {k: max(0.0, float(inp.values.get(k, 0) or 0)) for k, _ in ASSET_FIELDS + LIABILITY_FIELDS}
    if inp.standard not in ("gold", "silver"):
        raise ValueError(inp.standard)
    price = inp.gold_price if inp.standard == "gold" else inp.silver_price
    if price <= 0:
        raise ValueError("أدخل سعر غرام " + ("الذهب" if inp.standard == "gold" else "الفضّة") +
                         " اليوم بعملتك لحساب النصاب.")
    if (v["gold_g"] and inp.gold_price <= 0) or (v["silver_g"] and inp.silver_price <= 0):
        raise ValueError("أدخل سعر غرام الذهب والفضّة لتقويم ما تملكه منهما.")
    purity = max(1, min(24, int(inp.karat))) / 24.0
    gold_value = v["gold_g"] * purity * inp.gold_price
    silver_value = v["silver_g"] * inp.silver_price
    lines = []
    total = v["cash"] + v["savings"] + gold_value + silver_value + v["trade"] + v["receivable"] + v["other"]
    if gold_value:
        lines.append(f"قيمة الذهب: {v['gold_g']:g} غ × {purity * 24:g}/24 × {_money(inp.gold_price)} = {_money(gold_value)}")
    if silver_value:
        lines.append(f"قيمة الفضّة: {v['silver_g']:g} غ × {_money(inp.silver_price)} = {_money(silver_value)}")
    lines.append(f"مجموع الأموال الزكوية: {_money(total)}")
    ded = v["debts_due"]
    if ded:
        lines.append(f"يُطرح ما عليك من ديون حالّة: {_money(ded)}")
    net = max(0.0, total - ded)
    lines.append(f"صافي المال: {_money(net)}")
    nisab = (GOLD_NISAB_G if inp.standard == "gold" else SILVER_NISAB_G) * price
    std_name = (f"{GOLD_NISAB_G:g} غرامًا من الذهب" if inp.standard == "gold"
                else f"{SILVER_NISAB_G:g} غرامًا من الفضّة")
    lines.append(f"النصاب ({std_name}): {_money(nisab)}")
    due = 0.0
    if net < nisab:
        lines.append("مالك دون النصاب، فلا زكاة عليك فيه الآن.")
    elif not inp.year_complete:
        lines.append("بلغ مالك النصاب، لكن لم يحل عليه الحول (سنة قمرية) بعد؛ "
                     "تجب الزكاة عند تمام الحول إن بقي فوق النصاب.")
    else:
        due = net * RATE
        lines.append(f"الزكاة الواجبة = صافي المال × ٢٫٥٪ (ربع العشر) = {_money(net)} × 0.025 = {_money(due)}")
    return ZakatResult(total, ded, net, nisab, due, lines)


NOTE = ("هذه حاسبة للحالة الشائعة في زكاة النقود والذهب والفضّة وعروض التجارة. "
        "ولزكاة الأنعام والزروع والأسهم والحليّ الملبوس تفاصيل يختلف فيها العلماء، "
        "فاسأل عنها أهل العلم الموثوقين.")
