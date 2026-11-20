# -*- coding: utf-8 -*-
"""
abaAcademy.tools.mawarith
=========================

حاسبة المواريث — divides an estate among the heirs by the rules of ʿilm
al-farāʾiḍ as taught in the standard textbooks: the fixed shares (الفروض)
of the Qur'an, residuary heirs (العصبة) in their order, exclusion
(الحجب), the increase (العَوْل) when the shares exceed the whole, and the
return (الردّ) when they fall short with no residuary.

Where the schools differ the calculator follows one stated opinion and
says so in its explanation:
- the grandfather excludes brothers and sisters as the father does (the
  opinion of Abū Ḥanīfa; the other three schools have him share with them);
- in al-mushtaraka the full brothers get nothing (Ḥanafī and Ḥanbalī);
- the surplus returns to the fixed-share heirs other than the spouses, and to
  a spouse only when no other heir exists (as most courts apply today);
- ʿumariyyatān: the mother takes a third of what remains after the spouse.

It covers the heirs most cases involve (spouses, children and son's
children, parents and grandparents, brothers and sisters of all three kinds,
nephews and paternal uncles and their sons). It does not handle uterine
relatives (ذوو الأرحام), wills, debts, the missing, the unborn or
hermaphrodite cases; the screen says so, and that a real estate should be
settled by a qualified scholar or court.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction as Fr
from math import lcm
from typing import Dict, List, Tuple

HEIRS: List[Tuple[str, str, int]] = [
    # key, Arabic name, maximum count allowed
    ("husband", "الزوج", 1), ("wife", "الزوجة", 4),
    ("son", "الابن", 30), ("daughter", "البنت", 30),
    ("sons_son", "ابن الابن", 30), ("sons_daughter", "بنت الابن", 30),
    ("father", "الأب", 1), ("mother", "الأم", 1),
    ("grandfather", "الجدّ (أبو الأب)", 1), ("grandmother_m", "الجدّة لأم", 1), ("grandmother_f", "الجدّة لأب", 1),
    ("full_brother", "الأخ الشقيق", 30), ("full_sister", "الأخت الشقيقة", 30),
    ("pat_brother", "الأخ لأب", 30), ("pat_sister", "الأخت لأب", 30),
    ("mat_brother", "الأخ لأم", 30), ("mat_sister", "الأخت لأم", 30),
    ("full_nephew", "ابن الأخ الشقيق", 30), ("pat_nephew", "ابن الأخ لأب", 30),
    ("full_uncle", "العمّ الشقيق", 30), ("pat_uncle", "العمّ لأب", 30),
    ("full_cousin", "ابن العمّ الشقيق", 30), ("pat_cousin", "ابن العمّ لأب", 30),
]
NAME = {k: n for k, n, _ in HEIRS}
# residuary heirs by themselves, nearest first
ASABA_ORDER = ["son", "sons_son", "father", "grandfather", "full_brother", "pat_brother", "full_nephew", "pat_nephew",
               "full_uncle", "pat_uncle", "full_cousin", "pat_cousin"]
FEMALE_PARTNER = {"son": "daughter", "sons_son": "sons_daughter", "full_brother": "full_sister",
                  "pat_brother": "pat_sister"}

FRAC_NAMES = {Fr(1, 2): "النصف", Fr(1, 4): "الربع", Fr(1, 8): "الثمن", Fr(2, 3): "الثلثان", Fr(1, 3): "الثلث",
              Fr(1, 6): "السدس"}


@dataclass
class Share:
    key: str
    count: int
    fraction: Fr = Fr(0)              # the group's final share of the estate
    reason: str = ""
    excluded_by: str = ""

    @property
    def name(self) -> str:
        return NAME[self.key]


@dataclass
class Result:
    shares: List[Share]
    notes: List[str] = field(default_factory=list)
    base: int = 1                     # أصل المسألة
    awl_base: int = 0                 # the base after ʿawl, if any
    radd: bool = False

    def per_person(self, s: Share) -> Fr:
        return s.fraction / s.count if s.count else Fr(0)


def frac_name(f: Fr) -> str:
    return FRAC_NAMES.get(f, f"{f.numerator}/{f.denominator}")


def compute(heirs: Dict[str, int]) -> Result:
    h = {k: int(v) for k, v in heirs.items() if int(v or 0) > 0}
    for k in h:
        if k not in NAME:
            raise ValueError(f"وارث غير معروف: {k}")
    if h.get("husband") and h.get("wife"):
        raise ValueError("لا يجتمع زوج وزوجة في مسألة واحدة.")
    for k, _, mx in HEIRS:
        if h.get(k, 0) > mx:
            raise ValueError(f"عدد {NAME[k]} لا يزيد على {mx}.")
    if not h:
        raise ValueError("اختر الورثة أوّلًا.")

    shares: Dict[str, Share] = {k: Share(k, n) for k, n in h.items()}
    notes: List[str] = []
    has = lambda k: h.get(k, 0) > 0                       # noqa: E731
    male_desc = has("son") or has("sons_son")
    desc = male_desc or has("daughter") or has("sons_daughter")
    siblings = sum(h.get(k, 0) for k in ("full_brother", "full_sister", "pat_brother", "pat_sister",
                                         "mat_brother", "mat_sister"))

    def exclude(k: str, by: str):
        if k in shares and not shares[k].excluded_by:
            shares[k].excluded_by = by

    # -- exclusion (الحجب) ------------------------------------------------
    if has("son"):
        for k in ("sons_son", "sons_daughter"):
            exclude(k, "الابن")
    if has("father"):
        exclude("grandfather", "الأب")
        exclude("grandmother_f", "الأب")
    if has("mother"):
        exclude("grandmother_m", "الأم")
        exclude("grandmother_f", "الأم")
    if desc or has("father") or has("grandfather"):
        by = "الفرع الوارث" if desc else ("الأب" if has("father") else "الجدّ")
        exclude("mat_brother", by)
        exclude("mat_sister", by)
    blockers = [k for k in ("son", "sons_son", "father") if has(k)]
    if has("grandfather") and not has("father"):
        blockers.append("grandfather")
        if any(has(k) for k in ("full_brother", "full_sister", "pat_brother", "pat_sister")):
            notes.append("الجدّ يحجب الإخوة والأخوات هنا على قول أبي حنيفة، والمذاهب الثلاثة الأخرى تقاسمهم.")
    if blockers:
        for k in ("full_brother", "full_sister", "pat_brother", "pat_sister", "full_nephew", "pat_nephew",
                  "full_uncle", "pat_uncle", "full_cousin", "pat_cousin"):
            exclude(k, NAME[blockers[0]])
    if has("daughter") and h["daughter"] >= 2 and not has("son") and not has("sons_son"):
        exclude("sons_daughter", "البنتين فأكثر")

    def live(k: str) -> bool:
        return k in shares and not shares[k].excluded_by

    # sisters with daughters become residuaries (عصبة مع الغير)
    female_desc_only = (live("daughter") or live("sons_daughter")) and not male_desc
    full_sister_asaba = live("full_sister") and not live("full_brother") and female_desc_only
    pat_sister_asaba = (live("pat_sister") and not live("pat_brother") and female_desc_only
                        and not live("full_brother") and not full_sister_asaba)
    if live("full_brother"):
        for k in ("pat_brother", "pat_sister", "full_nephew", "pat_nephew", "full_uncle", "pat_uncle",
                  "full_cousin", "pat_cousin"):
            exclude(k, "الأخ الشقيق")
    if full_sister_asaba:
        for k in ("pat_brother", "pat_sister", "full_nephew", "pat_nephew", "full_uncle", "pat_uncle",
                  "full_cousin", "pat_cousin"):
            exclude(k, "الأخت الشقيقة مع البنت")
    if live("full_sister") and h["full_sister"] >= 2 and not live("pat_brother") and not full_sister_asaba:
        exclude("pat_sister", "الأختين الشقيقتين")

    # -- fixed shares (الفروض) --------------------------------------------
    fard: Dict[str, Fr] = {}

    def give(k: str, f: Fr, why: str):
        fard[k] = f
        shares[k].reason = f"{frac_name(f)}، {why}"

    if live("husband"):
        give("husband", Fr(1, 4) if desc else Fr(1, 2), "لوجود الفرع الوارث" if desc else "لعدم الفرع الوارث")
    if live("wife"):
        give("wife", Fr(1, 8) if desc else Fr(1, 4), ("لوجود الفرع الوارث" if desc else "لعدم الفرع الوارث")
             + ("، يقتسمنه بالتساوي" if h["wife"] > 1 else ""))
    if live("daughter") and not live("son"):
        give("daughter", Fr(1, 2) if h["daughter"] == 1 else Fr(2, 3),
             "للواحدة إذا انفردت" if h["daughter"] == 1 else "للبنتين فأكثر")
    if live("sons_daughter") and not live("sons_son"):
        if not has("daughter"):
            give("sons_daughter", Fr(1, 2) if h["sons_daughter"] == 1 else Fr(2, 3), "لعدم البنت")
        elif h["daughter"] == 1:
            give("sons_daughter", Fr(1, 6), "تكملةً للثلثين مع البنت")
    if live("father") and desc:
        give("father", Fr(1, 6), "لوجود الفرع الوارث")
    if live("grandfather") and desc:
        give("grandfather", Fr(1, 6), "لوجود الفرع الوارث وعدم الأب")
    umariyya = (live("mother") and (live("father")) and (live("husband") or live("wife")) and not desc
                and siblings < 2)
    if live("mother"):
        if desc or siblings >= 2:
            give("mother", Fr(1, 6), "لوجود الفرع الوارث" if desc else "لوجود جمع من الإخوة")
        elif not umariyya:
            give("mother", Fr(1, 3), "لعدم الفرع الوارث والجمع من الإخوة")
    grandmothers = [k for k in ("grandmother_m", "grandmother_f") if live(k)]
    for k in grandmothers:
        give(k, Fr(1, 6) / len(grandmothers), "السدس" + (" تقتسمه الجدّتان" if len(grandmothers) == 2 else ""))
        shares[k].reason = "السدس" + ("، تقتسمه الجدّتان" if len(grandmothers) == 2 else "")
    mat = [k for k in ("mat_brother", "mat_sister") if live(k)]
    n_mat = sum(h[k] for k in mat)
    if mat:
        total = Fr(1, 6) if n_mat == 1 else Fr(1, 3)
        for k in mat:
            give(k, total * h[k] / n_mat, "للإخوة لأم، الذكر والأنثى سواء")
            shares[k].reason = (("السدس للواحد" if n_mat == 1 else "الثلث يقتسمونه بالتساوي، الذكر كالأنثى"))
    if live("full_sister") and not live("full_brother") and not full_sister_asaba:
        give("full_sister", Fr(1, 2) if h["full_sister"] == 1 else Fr(2, 3),
             "للواحدة" if h["full_sister"] == 1 else "للأختين فأكثر")
    if live("pat_sister") and not live("pat_brother") and not pat_sister_asaba:
        if not has("full_sister"):
            give("pat_sister", Fr(1, 2) if h["pat_sister"] == 1 else Fr(2, 3), "لعدم الشقيقة")
        elif h.get("full_sister") == 1 and "full_sister" in fard:
            give("pat_sister", Fr(1, 6), "تكملةً للثلثين مع الشقيقة")

    if umariyya:
        spouse = Fr(1, 2) if live("husband") else Fr(1, 4)
        fard["mother"] = (1 - spouse) / 3
        shares["mother"].reason = "ثلث الباقي بعد فرض الزوج أو الزوجة (العُمَريّتان)"
        notes.append("هذه إحدى المسألتين العُمَريّتين: للأم ثلث الباقي لا ثلث الكلّ.")

    # -- residuaries (العصبة) ---------------------------------------------
    asaba_key = None
    for k in ASABA_ORDER:
        if live(k):
            asaba_key = k
            break
    sister_asaba = "full_sister" if full_sister_asaba else ("pat_sister" if pat_sister_asaba else None)
    if sister_asaba:
        rank_sister = ASABA_ORDER.index("full_brother" if sister_asaba == "full_sister" else "pat_brother")
        if asaba_key is None or ASABA_ORDER.index(asaba_key) > rank_sister or asaba_key in ("father", "grandfather"):
            if asaba_key not in ("father", "grandfather", "son", "sons_son"):
                for k in ASABA_ORDER[rank_sister:]:
                    exclude(k, NAME[sister_asaba] + " مع البنت")
                asaba_key = None
    total_fard = sum(fard.values(), Fr(0))
    base = lcm(*[f.denominator for f in fard.values()]) if fard else 1
    res = Result(list(shares.values()), notes, base)

    # al-mushtaraka: full brothers would be left with nothing
    remainder = 1 - total_fard
    receivers: List[Tuple[str, int]] = []        # (key, weight per person)
    if asaba_key:
        receivers.append((asaba_key, 2 if asaba_key in FEMALE_PARTNER else 1))
        partner = FEMALE_PARTNER.get(asaba_key)
        if partner and live(partner):
            receivers.append((partner, 1))
            fard.pop(partner, None)
    elif sister_asaba:
        receivers.append((sister_asaba, 1))
    if asaba_key in ("father", "grandfather") and desc and not male_desc:
        # 1/6 plus whatever remains
        pass
    total_fard = sum(fard.values(), Fr(0))
    base = lcm(*[f.denominator for f in fard.values()]) if fard else 1
    res.base = base
    remainder = 1 - total_fard

    final: Dict[str, Fr] = dict(fard)
    if receivers and remainder > 0:
        weights = sum(h[k] * w for k, w in receivers)
        for k, w in receivers:
            add = remainder * h[k] * w / weights
            final[k] = final.get(k, Fr(0)) + add
            extra = "الباقي تعصيبًا" + ("، للذكر مثل حظّ الأنثيين" if len(receivers) > 1 else "")
            if k == sister_asaba:
                extra = "الباقي تعصيبًا مع البنت (عصبة مع الغير)"
            shares[k].reason = (shares[k].reason + "، ثم " + extra) if k in fard else extra
    elif receivers and remainder <= 0:
        for k, _ in receivers:
            if k not in fard:
                shares[k].excluded_by = "استغراق الفروض للتركة"
                shares[k].reason = "لم يبقَ له شيء بعد أصحاب الفروض"
        if any(k == "full_brother" for k, _ in receivers) and mat:
            notes.append("هذه المسألة المشتركة: لم يبقَ للإخوة الأشقّاء شيء على قول الحنفية والحنابلة، "
                         "والمالكية والشافعية يشرّكونهم مع الإخوة لأم في الثلث.")
    if total_fard > 1:
        res.awl_base = sum(f * base for f in fard.values()).numerator if all(
            (f * base).denominator == 1 for f in fard.values()) else 0
        for k in fard:
            final[k] = fard[k] / total_fard
        notes.append(f"عالت المسألة: مجموع الفروض أكبر من التركة، فنقصت أنصبة الجميع بالنسبة نفسها"
                     + (f"، من أصل {base} إلى {res.awl_base}." if res.awl_base else "."))
    elif total_fard < 1 and not receivers:
        others = [k for k in fard if k not in ("husband", "wife")]
        if others:
            spouse = sum((fard[k] for k in fard if k in ("husband", "wife")), Fr(0))
            pool = sum((fard[k] for k in others), Fr(0))
            for k in others:
                final[k] = fard[k] + (1 - spouse - pool) * fard[k] / pool
                shares[k].reason += "، ثم ما بقي ردًّا"
            res.radd = True
            notes.append("بقي شيء بعد الفروض ولا عاصب، فرُدّ الباقي على أصحاب الفروض غير الزوجين بنسبة فروضهم.")
        elif fard:
            k = next(iter(fard))
            final[k] = Fr(1)
            shares[k].reason += "، ثم الباقي ردًّا"
            res.radd = True
            notes.append("لا وارث غير الزوج أو الزوجة، فرُدّ الباقي عليه، وهو ما عليه العمل اليوم، "
                         "والأصل عند المتقدّمين أنه لبيت المال.")
        else:
            notes.append("لا وارث من المذكورين، فالتركة لذوي الأرحام أو لبيت المال.")
    for s in res.shares:
        s.fraction = Fr(0) if s.excluded_by else final.get(s.key, Fr(0))
        if s.excluded_by and not s.reason:
            s.reason = f"محجوب بوجود {s.excluded_by}" if not s.excluded_by.startswith("استغراق") else s.excluded_by
        elif s.excluded_by:
            pass
    order = {k: i for i, (k, _, _) in enumerate(HEIRS)}
    res.shares.sort(key=lambda s: (s.excluded_by != "", order[s.key]))
    return res


FEMALE = {"wife", "daughter", "sons_daughter", "mother", "grandmother_m", "grandmother_f", "full_sister",
          "pat_sister", "mat_sister"}


def each(s: Share) -> str:
    return "لكلّ واحدة" if s.key in FEMALE else "لكلّ واحد"


def report(res: Result, estate: float = 0.0) -> List[str]:
    lines = []
    for s in res.shares:
        cnt = f" ({s.count})" if s.count > 1 else ""
        if s.excluded_by or s.fraction == 0:
            lines.append(f"{s.name}{cnt}: لا شيء، {s.reason}.")
            continue
        f = s.fraction
        line = f"{s.name}{cnt}: {f.numerator} من {f.denominator} من التركة، {s.reason}"
        if s.count > 1:
            p = res.per_person(s)
            line += f"؛ {each(s)} {p.numerator} من {p.denominator}"
        if estate:
            line += f"؛ المبلغ {round(float(f) * estate, 2):g}"
            if s.count > 1:
                line += f"، {each(s)} {round(float(res.per_person(s)) * estate, 2):g}"
        lines.append(line + ".")
    return lines + res.notes
