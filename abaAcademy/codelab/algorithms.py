# -*- coding: utf-8 -*-
"""
abaAcademy.codelab.algorithms
=============================

Sorting and searching algorithms, narrated step by step: every comparison
and every swap or move is a spoken line, and the totals at the end let the
learner hear why one algorithm is faster than another on the same list.

Sorting: bubble, selection, insertion, merge and quick sort.
Searching: linear search and binary search (on the sorted list).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

MAX_STEPS = 600


@dataclass
class Run:
    name: str
    result: List[float]
    steps: List[str] = field(default_factory=list)
    comparisons: int = 0
    moves: int = 0
    truncated: bool = False

    def log(self, text: str) -> None:
        if len(self.steps) < MAX_STEPS:
            self.steps.append(text)
        else:
            self.truncated = True

    def summary(self) -> str:
        s = (f"{self.name}: عدد المقارنات {self.comparisons}، وعدد عمليات النقل والتبديل {self.moves}. "
             f"الناتج: {fmt_list(self.result)}.")
        if self.truncated:
            s += f" (عُرضت أوّل {MAX_STEPS} خطوة فقط.)"
        return s


def fmt(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def fmt_list(xs: Sequence[float]) -> str:
    return "، ".join(fmt(x) for x in xs)


def parse_list(text: str) -> List[float]:
    t = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")).replace("،", " ").replace(",", " ")
    out = []
    for tok in t.split():
        try:
            out.append(float(tok))
        except ValueError:
            raise ValueError(f"{tok} ليس رقمًا.")
    if not out:
        raise ValueError("اكتب قائمة أرقام.")
    if len(out) > 40:
        raise ValueError("القائمة طويلة؛ أربعون رقمًا على الأكثر لتبقى الخطوات مسموعة.")
    return out


def bubble(xs: Sequence[float]) -> Run:
    a = list(xs)
    r = Run("الترتيب بالفقاعات", a)
    n = len(a)
    for i in range(n - 1):
        swapped = False
        r.log(f"الجولة {i + 1}:")
        for j in range(n - 1 - i):
            r.comparisons += 1
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                r.moves += 1
                swapped = True
                r.log(f"نقارن {fmt(a[j + 1])} و{fmt(a[j])}: الأوّل أكبر فنبدّلهما ← {fmt_list(a)}")
            else:
                r.log(f"نقارن {fmt(a[j])} و{fmt(a[j + 1])}: بالترتيب، لا تبديل")
        if not swapped:
            r.log("لم يحدث تبديل في هذه الجولة، فالقائمة مرتّبة.")
            break
        r.log(f"استقرّ {fmt(a[n - 1 - i])} في مكانه الأخير.")
    return r


def selection(xs: Sequence[float]) -> Run:
    a = list(xs)
    r = Run("الترتيب بالاختيار", a)
    n = len(a)
    for i in range(n - 1):
        m = i
        for j in range(i + 1, n):
            r.comparisons += 1
            if a[j] < a[m]:
                m = j
        if m != i:
            a[i], a[m] = a[m], a[i]
            r.moves += 1
            r.log(f"أصغر ما بقي {fmt(a[i])}؛ نضعه في الموضع {i + 1} ← {fmt_list(a)}")
        else:
            r.log(f"أصغر ما بقي {fmt(a[i])} في مكانه أصلًا (الموضع {i + 1}).")
    return r


def insertion(xs: Sequence[float]) -> Run:
    a = list(xs)
    r = Run("الترتيب بالإدراج", a)
    for i in range(1, len(a)):
        key = a[i]
        j = i - 1
        shifted = 0
        while j >= 0:
            r.comparisons += 1
            if a[j] > key:
                a[j + 1] = a[j]
                r.moves += 1
                shifted += 1
                j -= 1
            else:
                break
        a[j + 1] = key
        if shifted:
            r.log(f"نأخذ {fmt(key)} ونزيح العناصر الأكبر منه (عددها {shifted}) إلى اليمين، ثم ندرجه ← {fmt_list(a)}")
        else:
            r.log(f"{fmt(key)} أكبر من كلّ ما قبله، فيبقى مكانه.")
    return r


def merge_sort(xs: Sequence[float]) -> Run:
    r = Run("الترتيب بالدمج", [])

    def sort(a: List[float], depth: int) -> List[float]:
        if len(a) <= 1:
            return a
        mid = len(a) // 2
        r.log(f"{'  ' * depth}نقسم [{fmt_list(a)}] إلى [{fmt_list(a[:mid])}] و[{fmt_list(a[mid:])}]")
        left, right = sort(a[:mid], depth + 1), sort(a[mid:], depth + 1)
        out = []
        i = j = 0
        while i < len(left) and j < len(right):
            r.comparisons += 1
            if left[i] <= right[j]:
                out.append(left[i])
                i += 1
            else:
                out.append(right[j])
                j += 1
            r.moves += 1
        r.moves += (len(left) - i) + (len(right) - j)
        out += left[i:] + right[j:]
        r.log(f"{'  ' * depth}ندمج فنحصل على [{fmt_list(out)}]")
        return out

    r.result = sort(list(xs), 0)
    return r


def quick_sort(xs: Sequence[float]) -> Run:
    a = list(xs)
    r = Run("الترتيب السريع", a)

    def part(lo: int, hi: int) -> int:
        pivot = a[hi]
        r.log(f"المحور {fmt(pivot)} للجزء [{fmt_list(a[lo:hi + 1])}]")
        i = lo
        for j in range(lo, hi):
            r.comparisons += 1
            if a[j] < pivot:
                if i != j:
                    a[i], a[j] = a[j], a[i]
                    r.moves += 1
                i += 1
        a[i], a[hi] = a[hi], a[i]
        r.moves += 1
        r.log(f"الأصغر من المحور يساره والأكبر يمينه ← {fmt_list(a)}")
        return i

    def qs(lo: int, hi: int) -> None:
        if lo < hi:
            p = part(lo, hi)
            qs(lo, p - 1)
            qs(p + 1, hi)

    qs(0, len(a) - 1)
    return r


SORTS: Dict[str, Tuple[str, Callable[[Sequence[float]], Run], str]] = {
    "bubble": ("الفقاعات", bubble, "O(n²): يقارن كلّ جارين ويبدّلهما، فيطفو الأكبر إلى الآخر."),
    "selection": ("الاختيار", selection, "O(n²): يختار أصغر ما بقي ويضعه في مكانه."),
    "insertion": ("الإدراج", insertion, "O(n²) في أسوأ حال وO(n) لقائمة شبه مرتّبة: يدرج كلّ عنصر في مكانه بين ما قبله."),
    "merge": ("الدمج", merge_sort, "O(n log n): يقسم القائمة نصفين مرّة بعد مرّة، ثم يدمج النصفين المرتّبين."),
    "quick": ("السريع", quick_sort, "O(n log n) في المتوسّط: يختار محورًا ويضع الأصغر يساره والأكبر يمينه."),
}


def compare_all(xs: Sequence[float]) -> List[str]:
    lines = []
    for key, (name, fn, _) in SORTS.items():
        run = fn(xs)
        lines.append(f"{name}: المقارنات {run.comparisons}، والنقل {run.moves}.")
    return lines


def linear_search(xs: Sequence[float], target: float) -> Run:
    r = Run("البحث الخطّي", list(xs))
    for i, x in enumerate(xs):
        r.comparisons += 1
        if x == target:
            r.log(f"الموضع {i + 1}: {fmt(x)} — وجدته.")
            return r
        r.log(f"الموضع {i + 1}: {fmt(x)} — ليس هو.")
    r.log(f"لم أجد {fmt(target)} في القائمة.")
    return r


def binary_search(xs: Sequence[float], target: float) -> Run:
    a = sorted(xs)
    r = Run("البحث الثنائي", a)
    r.log(f"نرتّب القائمة أوّلًا: {fmt_list(a)}")
    lo, hi = 0, len(a) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        r.comparisons += 1
        if a[mid] == target:
            r.log(f"الوسط الموضع {mid + 1}: {fmt(a[mid])} — وجدته.")
            return r
        if a[mid] < target:
            r.log(f"الوسط {fmt(a[mid])} أصغر من {fmt(target)}، فنبحث في النصف الأيمن.")
            lo = mid + 1
        else:
            r.log(f"الوسط {fmt(a[mid])} أكبر من {fmt(target)}، فنبحث في النصف الأيسر.")
            hi = mid - 1
    r.log(f"لم أجد {fmt(target)}.")
    return r
