# -*- coding: utf-8 -*-
"""
abaAcademy.science.periodic
===========================

An explorable periodic table: position (period and group), block, family,
state at room temperature, electron configuration and shell occupancy for
every element, plus question generators for practice.

The layout and families follow the standard 18-column IUPAC table, with the
lanthanides (57–71) and actinides (89–103) as separate series. Electron
configurations are built by the aufbau (Madelung) order with the well-known
exceptions measured for real atoms (Cr, Cu, Mo, Ag, Au, Pt and others);
for elements from 104 upward the configuration is a prediction, and the
screen says so.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .elements_data import ELEMENTS
from ..tools.ar_count import count

# ---------------------------------------------------------------------------
# position
# ---------------------------------------------------------------------------

_PERIOD_ENDS = (2, 10, 18, 36, 54, 86, 118)


def period_of(z: int) -> int:
    for p, end in enumerate(_PERIOD_ENDS, 1):
        if z <= end:
            return p
    raise ValueError(z)


def series_of(z: int) -> str:
    if 57 <= z <= 71:
        return "lanthanide"
    if 89 <= z <= 103:
        return "actinide"
    return ""


def group_of(z: int) -> Optional[int]:
    """IUPAC group 1-18; ``None`` for the lanthanides/actinides other than the
    first (La/Ac sit in group 3 in many school tables, but here the whole
    series is kept together)."""
    if series_of(z):
        return None
    p = period_of(z)
    start = (_PERIOD_ENDS[p - 2] + 1) if p > 1 else 1
    idx = z - start                                    # 0-based in the period
    if p == 1:
        return 1 if z == 1 else 18
    if p in (2, 3):
        return idx + 1 if idx < 2 else idx + 11
    if p in (4, 5):
        return idx + 1
    # periods 6 and 7 carry the 14-element f series after group 2
    if idx < 2:
        return idx + 1
    return idx - 14 + 1


BLOCK_NAMES = {"s": "الفئة s", "p": "الفئة p", "d": "الفئة d", "f": "الفئة f"}


def block_of(z: int) -> str:
    if series_of(z):
        return "f"
    g = group_of(z)
    if z == 2:
        return "s"
    if g in (1, 2):
        return "s"
    if 3 <= g <= 12:
        return "d"
    return "p"


# ---------------------------------------------------------------------------
# families and state
# ---------------------------------------------------------------------------

CATEGORY_NAMES = {
    "alkali": "الفلزات القلوية",
    "alkaline_earth": "الفلزات القلوية الترابية",
    "transition": "الفلزات الانتقالية",
    "post_transition": "فلزات ما بعد الانتقالية",
    "metalloid": "أشباه الفلزات",
    "nonmetal": "اللافلزات",
    "halogen": "الهالوجينات",
    "noble_gas": "الغازات النبيلة",
    "lanthanide": "اللانثانيدات",
    "actinide": "الأكتينيدات",
}

_METALLOIDS = {5, 14, 32, 33, 51, 52}
_NONMETALS = {1, 6, 7, 8, 15, 16, 34}
_POST_TRANSITION = {13, 31, 49, 50, 81, 82, 83, 84, 113, 114, 115, 116}


def category_of(z: int) -> str:
    s = series_of(z)
    if s:
        return s
    g = group_of(z)
    if z in _NONMETALS:
        return "nonmetal"
    if g == 18:
        return "noble_gas"
    if g == 17:
        return "halogen"
    if z in _METALLOIDS:
        return "metalloid"
    if z in _POST_TRANSITION:
        return "post_transition"
    if g == 1:
        return "alkali"
    if g == 2:
        return "alkaline_earth"
    return "transition"


STATE_NAMES = {"gas": "غاز", "liquid": "سائل", "solid": "صلب", "unknown": "غير مؤكّدة"}
_GASES = {1, 2, 7, 8, 9, 10, 17, 18, 36, 54, 86}
_LIQUIDS = {35, 80}


def state_of(z: int) -> str:
    """State at 25 °C and one atmosphere."""
    if z in _GASES:
        return "gas"
    if z in _LIQUIDS:
        return "liquid"
    if z >= 104:
        return "unknown"
    return "solid"


# ---------------------------------------------------------------------------
# electron configuration
# ---------------------------------------------------------------------------

_AUFBAU = ["1s", "2s", "2p", "3s", "3p", "4s", "3d", "4p", "5s", "4d", "5p",
           "6s", "4f", "5d", "6p", "7s", "5f", "6d", "7p"]
_CAP = {"s": 2, "p": 6, "d": 10, "f": 14}

# measured ground-state exceptions: orbital -> electrons, applied on top of
# the aufbau filling
_EXCEPTIONS: Dict[int, Dict[str, int]] = {
    24: {"4s": 1, "3d": 5}, 29: {"4s": 1, "3d": 10},
    41: {"5s": 1, "4d": 4}, 42: {"5s": 1, "4d": 5}, 44: {"5s": 1, "4d": 7},
    45: {"5s": 1, "4d": 8}, 46: {"5s": 0, "4d": 10}, 47: {"5s": 1, "4d": 10},
    57: {"4f": 0, "5d": 1}, 58: {"4f": 1, "5d": 1}, 64: {"4f": 7, "5d": 1},
    78: {"6s": 1, "5d": 9}, 79: {"6s": 1, "5d": 10},
    89: {"5f": 0, "6d": 1}, 90: {"5f": 0, "6d": 2}, 91: {"5f": 2, "6d": 1},
    92: {"5f": 3, "6d": 1}, 93: {"5f": 4, "6d": 1}, 96: {"5f": 7, "6d": 1},
    103: {"6d": 0, "7p": 1},
}

_NOBLE = [(2, "He"), (10, "Ne"), (18, "Ar"), (36, "Kr"), (54, "Xe"), (86, "Rn")]


def _filling(z: int) -> Dict[str, int]:
    left, out = z, {}
    for orb in _AUFBAU:
        if left <= 0:
            break
        n = min(left, _CAP[orb[-1]])
        out[orb] = n
        left -= n
    for orb, n in _EXCEPTIONS.get(z, {}).items():
        out[orb] = n
    return {o: n for o, n in out.items() if n}


def _order_key(orb: str) -> Tuple[int, int]:
    return int(orb[:-1]), "spdf".index(orb[-1])


def electron_configuration(z: int, short: bool = True) -> str:
    fill = _filling(z)
    core = ""
    if short:
        for nz, sym in reversed(_NOBLE):
            if nz < z:
                core_fill = _filling(nz)
                if all(fill.get(o, 0) >= n for o, n in core_fill.items()):
                    for o in core_fill:
                        fill[o] -= core_fill[o]
                    fill = {o: n for o, n in fill.items() if n}
                    core = f"[{sym}] "
                break
    parts = [f"{o}{n}" for o, n in sorted(fill.items(), key=lambda kv: _order_key(kv[0]))]
    return (core + " ".join(parts)).strip()


def shells(z: int) -> List[int]:
    """Electrons per shell (K, L, M, …)."""
    fill = _filling(z)
    top = max(int(o[:-1]) for o in fill)
    return [sum(n for o, n in fill.items() if int(o[:-1]) == k) for k in range(1, top + 1)]


def valence_electrons(z: int) -> Optional[int]:
    """Outer-shell electrons for main-group elements (the number school
    chemistry uses for bonding); ``None`` for d/f elements."""
    if block_of(z) not in ("s", "p"):
        return None
    return shells(z)[-1]


SHELL_LETTERS = "KLMNOPQ"


# ---------------------------------------------------------------------------
# element records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Element:
    number: int
    symbol: str
    name: str
    english: str
    mass: float

    @property
    def period(self) -> int:
        return period_of(self.number)

    @property
    def group(self) -> Optional[int]:
        return group_of(self.number)

    @property
    def block(self) -> str:
        return block_of(self.number)

    @property
    def category(self) -> str:
        return category_of(self.number)

    @property
    def state(self) -> str:
        return state_of(self.number)

    @property
    def predicted(self) -> bool:
        return self.number >= 104

    def describe(self) -> str:
        z = self.number
        pos = (f"الدورة {self.period}، المجموعة {self.group}" if self.group
               else f"الدورة {self.period}، سلسلة {CATEGORY_NAMES[self.category]}")
        mass = f"{self.mass:g}"
        conf = electron_configuration(z)
        sh = "، ".join(f"{SHELL_LETTERS[i]} {n}" for i, n in enumerate(shells(z)))
        lines = [
            f"{self.name} ({self.symbol})، العدد الذري {z}.",
            f"الكتلة الذرية {mass}.",
            f"الموقع: {pos}، {BLOCK_NAMES[self.block]}.",
            f"العائلة: {CATEGORY_NAMES[self.category]}.",
            f"الحالة في درجة حرارة الغرفة: {STATE_NAMES[self.state]}.",
            f"التوزيع الإلكتروني{' المتوقّع' if self.predicted else ''}: {conf}.",
            f"الإلكترونات في المستويات: {sh}.",
        ]
        v = valence_electrons(z)
        if v is not None:
            lines.append(f"إلكترونات التكافؤ: {v}.")
        lines.append(f"الاسم بالإنجليزية: {self.english}.")
        return "\n".join(lines)


TABLE: Tuple[Element, ...] = tuple(Element(*row) for row in ELEMENTS)
BY_NUMBER = {e.number: e for e in TABLE}
BY_SYMBOL = {e.symbol.lower(): e for e in TABLE}


def _fold(s: str) -> str:
    return (s.strip().replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
            .replace("ة", "ه").replace("ى", "ي").lower())


BY_NAME = {_fold(e.name): e for e in TABLE}
BY_NAME.update({_fold(e.english): e for e in TABLE})


def find(query: str) -> Optional[Element]:
    """By number, symbol, Arabic name or English name."""
    q = query.strip()
    if not q:
        return None
    digits = q.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    if digits.isdigit():
        return BY_NUMBER.get(int(digits))
    if q.lower() in BY_SYMBOL:
        return BY_SYMBOL[q.lower()]
    f = _fold(q)
    if f in BY_NAME:
        return BY_NAME[f]
    if f.startswith("ال") and f[2:] in BY_NAME:
        return BY_NAME[f[2:]]
    for name, el in BY_NAME.items():
        if name.startswith(f) and len(f) >= 3:
            return el
    return None


# ---------------------------------------------------------------------------
# the grid (for arrow-key exploration)
# ---------------------------------------------------------------------------

def grid() -> List[List[Optional[Element]]]:
    """7 main rows x 18 columns, then two rows for the f series (columns
    3..17 hold 15 elements each)."""
    rows: List[List[Optional[Element]]] = [[None] * 18 for _ in range(9)]
    for e in TABLE:
        s = series_of(e.number)
        if s == "lanthanide":
            rows[7][2 + e.number - 57] = e
        elif s == "actinide":
            rows[8][2 + e.number - 89] = e
        else:
            rows[e.period - 1][e.group - 1] = e
    return rows


def row_label(r: int) -> str:
    if r < 7:
        return f"الدورة {r + 1}"
    return "اللانثانيدات" if r == 7 else "الأكتينيدات"


def members(category: str) -> List[Element]:
    return [e for e in TABLE if e.category == category]


def in_group(g: int) -> List[Element]:
    return [e for e in TABLE if e.group == g]


def in_period(p: int) -> List[Element]:
    return [e for e in TABLE if e.period == p]


# ---------------------------------------------------------------------------
# practice questions
# ---------------------------------------------------------------------------

@dataclass
class Question:
    prompt: str
    answer: str
    options: List[str]
    explanation: str
    accept: Tuple[str, ...] = ()

    def check(self, text: str) -> bool:
        t = _fold(text)
        return t in {_fold(self.answer)} | {_fold(a) for a in self.accept}


QUIZ_KINDS = {
    "symbol_to_name": "من الرمز إلى الاسم",
    "name_to_symbol": "من الاسم إلى الرمز",
    "number_to_name": "من العدد الذري إلى الاسم",
    "family": "عائلة العنصر",
    "position": "الدورة والمجموعة",
    "valence": "إلكترونات التكافؤ",
}


def _pool(max_number: int) -> List[Element]:
    return [e for e in TABLE if e.number <= max_number]


def _similar(e: Element, pool: Sequence[Element], n: int, rng) -> List[Element]:
    """Distractors that a learner would really confuse: same family, then
    neighbours by number, then anything."""
    same = [x for x in pool if x is not e and x.category == e.category]
    near = sorted((x for x in pool if x is not e), key=lambda x: abs(x.number - e.number))
    rng.shuffle(same)
    picks: List[Element] = []
    for x in same + near[:8] + list(pool):
        if x is not e and x not in picks:
            picks.append(x)
        if len(picks) >= n:
            break
    return picks


def make_question(kind: str, rng: Optional[random.Random] = None,
                  max_number: int = 36) -> Question:
    rng = rng or random.Random()
    pool = _pool(max_number)
    if kind == "valence":
        pool = [e for e in pool if valence_electrons(e.number) is not None and e.number > 2]
    e = rng.choice(pool)
    if kind == "symbol_to_name":
        opts = [e.name] + [x.name for x in _similar(e, pool, 3, rng)]
        rng.shuffle(opts)
        return Question(f"ما اسم العنصر الذي رمزه {e.symbol}؟", e.name, opts,
                        f"{e.symbol} هو رمز {e.name}، وعدده الذري {e.number}.",
                        (e.english,))
    if kind == "name_to_symbol":
        opts = [e.symbol] + [x.symbol for x in _similar(e, pool, 3, rng)]
        rng.shuffle(opts)
        return Question(f"ما رمز عنصر {e.name}؟", e.symbol, opts,
                        f"رمز {e.name} هو {e.symbol} (من اسمه {e.english}).")
    if kind == "number_to_name":
        opts = [e.name] + [x.name for x in _similar(e, pool, 3, rng)]
        rng.shuffle(opts)
        return Question(f"أيّ عنصر عدده الذري {e.number}؟", e.name, opts,
                        f"العنصر رقم {e.number} هو {e.name} ({e.symbol}).", (e.symbol,))
    if kind == "family":
        right = CATEGORY_NAMES[e.category]
        others = [v for k, v in CATEGORY_NAMES.items() if k != e.category]
        rng.shuffle(others)
        opts = [right] + others[:3]
        rng.shuffle(opts)
        return Question(f"إلى أيّ عائلة ينتمي {e.name} ({e.symbol})؟", right, opts,
                        f"{e.name} من {right}.")
    if kind == "position":
        if e.group is None:
            e = rng.choice([x for x in pool if x.group is not None])
        right = f"الدورة {e.period}، المجموعة {e.group}"
        cand = set()
        for dp, dg in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1)):
            p, g = e.period + dp, e.group + dg
            if 1 <= p <= 7 and 1 <= g <= 18:
                cand.add(f"الدورة {p}، المجموعة {g}")
        cand.discard(right)
        cand = sorted(cand)
        rng.shuffle(cand)
        opts = [right] + cand[:3]
        rng.shuffle(opts)
        return Question(f"أين يقع {e.name} ({e.symbol}) في الجدول الدوري؟", right, opts,
                        f"{e.name}: {right}.")
    if kind == "valence":
        v = valence_electrons(e.number)
        right = str(v)
        others = [str(x) for x in range(1, 9) if x != v]
        rng.shuffle(others)
        opts = [right] + others[:3]
        rng.shuffle(opts)
        return Question(f"كم إلكترون تكافؤ في ذرّة {e.name} ({e.symbol})؟", right, opts,
                        f"توزيعه {electron_configuration(e.number)}، "
                        f"ففي مستواه الأخير {count(v, 'electron')}.")
    raise ValueError(kind)
