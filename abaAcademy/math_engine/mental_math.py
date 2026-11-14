# -*- coding: utf-8 -*-
"""
abaAcademy.math_engine.mental_math
==================================

Mental arithmetic techniques (الحساب الذهني): each technique has a short
explanation, a worked example produced from the numbers in the question,
and a generator of practice problems it is designed for. Mental arithmetic
suits blind learners especially well — it needs no paper — and the
techniques turn long multiplications into a few spoken steps.

Every worked example is computed, so the steps always match the answer.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple


@dataclass
class Problem:
    technique: str
    question: str
    answer: int
    steps: List[str]

    def check(self, text: str) -> bool:
        t = text.strip().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")).replace(",", "")
        try:
            return int(t) == self.answer
        except ValueError:
            return False


@dataclass(frozen=True)
class Technique:
    key: str
    name: str
    explanation: str
    make: Callable[[random.Random], Problem]


def _times11(rng) -> Problem:
    n = rng.randint(12, 99)
    a, b = divmod(n, 10)
    mid = a + b
    ans = n * 11
    steps = [f"نكتب رقمي {n} ونضع مجموعهما في الوسط: {a} + {b} = {mid}."]
    if mid >= 10:
        steps.append(f"المجموع {mid} أكبر من ٩، فنضع {mid % 10} في الوسط ونحمل ١ إلى {a} فيصبح {a + 1}.")
    steps.append(f"الناتج {ans}.")
    return Problem("times11", f"{n} × 11", ans, steps)


def _square5(rng) -> Problem:
    t = rng.randint(1, 12)
    n = t * 10 + 5
    ans = n * n
    return Problem("square5", f"{n}²", ans,
                   [f"نأخذ عدد العشرات {t} ونضربه في التالي له {t + 1}: {t * (t + 1)}.",
                    f"ونضع بعده ٢٥: الناتج {ans}."])


def _times5(rng) -> Problem:
    n = rng.randint(12, 998)
    ans = n * 5
    if n % 2 == 0:
        steps = [f"الضرب في ٥ = الضرب في ١٠ ثم القسمة على ٢: {n} ÷ ٢ = {n // 2}، ثم نضيف صفرًا: {ans}."]
    else:
        steps = [f"{n} × ١٠ = {n * 10}، ثم نقسم على ٢: {ans}."]
    return Problem("times5", f"{n} × 5", ans, steps)


def _times9(rng) -> Problem:
    n = rng.randint(12, 120)
    ans = n * 9
    return Problem("times9", f"{n} × 9", ans,
                   [f"الضرب في ٩ = الضرب في ١٠ ثم طرح العدد نفسه: {n * 10} − {n} = {ans}."])


def _times25(rng) -> Problem:
    n = rng.choice([x for x in range(8, 160) if x % 4 == 0] + [rng.randint(5, 99)])
    ans = n * 25
    if n % 4 == 0:
        steps = [f"الضرب في ٢٥ = الضرب في ١٠٠ ثم القسمة على ٤: {n} ÷ ٤ = {n // 4}، ثم نضيف صفرين: {ans}."]
    else:
        steps = [f"{n} × ١٠٠ = {n * 100}، ثم نقسم على ٤: {ans}."]
    return Problem("times25", f"{n} × 25", ans, steps)


def _near100(rng) -> Problem:
    a = rng.randint(88, 99)
    b = rng.randint(88, 99)
    da, db = 100 - a, 100 - b
    ans = a * b
    left = a - db
    right = da * db
    return Problem("near100", f"{a} × {b}", ans,
                   [f"نحسب بُعد كلّ عدد عن ١٠٠: {da} و{db}.",
                    f"نطرح من العدد الأول بُعدَ الثاني: {a} − {db} = {left}، وهذه أوّل خانتين.",
                    f"نضرب البُعدين: {da} × {db} = {right}، ونكتبه في خانتين: {right:02d}.",
                    f"الناتج {ans}."])


def _diff_squares(rng) -> Problem:
    m = rng.choice([20, 30, 40, 50, 60, 70, 80, 90, 100])
    d = rng.randint(1, 5)
    a, b = m - d, m + d
    ans = a * b
    return Problem("diff_squares", f"{a} × {b}", ans,
                   [f"العددان متساويا البعد عن {m}: ({m} − {d}) × ({m} + {d}) = {m}² − {d}².",
                    f"{m * m} − {d * d} = {ans}."])


def _add_round(rng) -> Problem:
    a = rng.randint(100, 899)
    b = rng.choice([x for x in range(19, 99) if x % 10 in (7, 8, 9)])
    up = (b // 10 + 1) * 10
    ans = a + b
    return Problem("add_round", f"{a} + {b}", ans,
                   [f"نقرّب {b} إلى {up}: {a} + {up} = {a + up}.",
                    f"ثم نطرح ما زدناه ({up - b}): {a + up} − {up - b} = {ans}."])


def _sub_round(rng) -> Problem:
    a = rng.randint(200, 999)
    b = rng.choice([x for x in range(19, 199) if x % 10 in (7, 8, 9)])
    up = (b // 10 + 1) * 10
    ans = a - b
    return Problem("sub_round", f"{a} − {b}", ans,
                   [f"نطرح العدد المقرّب {up}: {a} − {up} = {a - up}.",
                    f"ثم نعيد ما طرحناه زيادةً ({up - b}): {a - up} + {up - b} = {ans}."])


def _split_mult(rng) -> Problem:
    a = rng.randint(12, 49)
    b = rng.randint(3, 9)
    t, u = divmod(a, 10)
    ans = a * b
    return Problem("split_mult", f"{a} × {b}", ans,
                   [f"نجزّئ {a} إلى {t * 10} و{u}.",
                    f"{t * 10} × {b} = {t * 10 * b}، و{u} × {b} = {u * b}.",
                    f"المجموع {t * 10 * b} + {u * b} = {ans}."])


def _double_half(rng) -> Problem:
    a = rng.choice([14, 16, 18, 24, 26, 28, 32, 34, 36, 44, 48])
    b = rng.choice([15, 25, 35, 45, 55])
    ans = a * b
    return Problem("double_half", f"{a} × {b}", ans,
                   [f"نُنصّف {a} ونضاعف {b}: {a // 2} × {b * 2}.",
                    f"وهذا أسهل: الناتج {ans}."])


def _percent(rng) -> Problem:
    p = rng.choice([10, 20, 25, 50, 5, 15, 30, 75])
    base = rng.choice([40, 60, 80, 120, 200, 240, 360, 400, 480, 600, 800, 1000])
    ans = base * p // 100
    if base * p % 100:
        return _percent(rng)
    if p == 15:
        steps = [f"١٠٪ من {base} = {base // 10}، و٥٪ نصفها = {base // 20}.",
                 f"١٥٪ = {base // 10} + {base // 20} = {ans}."]
    elif p == 75:
        steps = [f"٧٥٪ = ثلاثة أرباع: {base} ÷ ٤ = {base // 4}، × ٣ = {ans}."]
    else:
        steps = [f"{p}٪ من {base} = {base} × {p} ÷ ١٠٠ = {ans}."]
    return Problem("percent", f"{p}٪ من {base}", ans, steps)


TECHNIQUES: Tuple[Technique, ...] = (
    Technique("times11", "الضرب في ١١",
              "لضرب عدد من رقمين في ١١: اكتب رقميه متباعدين وضع مجموعهما بينهما، "
              "واحمل واحدًا إن زاد المجموع على تسعة.", _times11),
    Technique("square5", "تربيع عدد آحاده ٥",
              "اضرب عدد العشرات في العدد الذي يليه، ثم ألحق ٢٥ في آخره.", _square5),
    Technique("times5", "الضرب في ٥", "اضرب في ١٠ ثم اقسم على ٢.", _times5),
    Technique("times9", "الضرب في ٩", "اضرب في ١٠ ثم اطرح العدد نفسه.", _times9),
    Technique("times25", "الضرب في ٢٥", "اضرب في ١٠٠ ثم اقسم على ٤.", _times25),
    Technique("near100", "ضرب عددين قريبين من ١٠٠",
              "احسب بُعد كلّ منهما عن ١٠٠؛ اطرح أحد البعدين من العدد الآخر، ثم ألحق حاصل ضرب "
              "البعدين في خانتين.", _near100),
    Technique("diff_squares", "فرق المربّعين",
              "إذا كان العددان على بُعد متساوٍ من عدد سهل م، فحاصل ضربهما م² ناقص مربّع البعد.",
              _diff_squares),
    Technique("add_round", "الجمع بالتقريب",
              "قرّب العدد إلى أقرب عشرة، اجمع، ثم اطرح ما زدته.", _add_round),
    Technique("sub_round", "الطرح بالتقريب",
              "اطرح العدد مقرّبًا إلى أقرب عشرة، ثم أضف ما طرحته زيادة.", _sub_round),
    Technique("split_mult", "التجزئة",
              "جزّئ العدد إلى عشرات وآحاد، واضرب كلّ جزء، ثم اجمع.", _split_mult),
    Technique("double_half", "التنصيف والمضاعفة",
              "نصّف أحد العددين وضاعف الآخر حتى يصبح الضرب سهلًا؛ الناتج لا يتغيّر.", _double_half),
    Technique("percent", "النسب المئوية",
              "١٠٪ تعني القسمة على ١٠، و٥٠٪ النصف، و٢٥٪ الربع؛ وتُركّب البقية منها.", _percent),
)
TECH_BY_KEY: Dict[str, Technique] = {t.key: t for t in TECHNIQUES}


def problem(key: Optional[str] = None, rng: Optional[random.Random] = None) -> Problem:
    rng = rng or random.Random()
    t = TECH_BY_KEY[key] if key else rng.choice(TECHNIQUES)
    return t.make(rng)


def worked_example(key: str, seed: int = 7) -> Problem:
    return TECH_BY_KEY[key].make(random.Random(seed))
