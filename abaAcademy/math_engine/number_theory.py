# -*- coding: utf-8 -*-
"""
abaAcademy.math_engine.number_theory
====================================

Numbers, explained: primality with the reason, prime factorisation as a
factor tree, divisors, GCD by Euclid's algorithm and LCM with every step,
the divisibility rules for 2–11 applied to the learner's own number, the
primes up to a limit (sieve of Eratosthenes), and perfect, square and
Fibonacci checks.

Also basic combinatorics and probability: factorials, permutations and
combinations with their formulas, and the probability of dice, coins and
drawing from a bag.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Dict, List, Tuple

LIMIT = 10 ** 12


def _check(n: int, low: int = 1) -> int:
    if not isinstance(n, int):
        raise ValueError("اكتب عددًا صحيحًا.")
    if n < low:
        raise ValueError(f"اكتب عددًا لا يقلّ عن {low}.")
    if n > LIMIT:
        raise ValueError("العدد كبير جدًّا لهذه الأداة.")
    return n


def factorize(n: int) -> Dict[int, int]:
    _check(n, 2)
    out: Dict[int, int] = {}
    d = 2
    while d * d <= n:
        while n % d == 0:
            out[d] = out.get(d, 0) + 1
            n //= d
        d += 1 if d == 2 else 2
    if n > 1:
        out[n] = out.get(n, 0) + 1
    return out


def factor_text(f: Dict[int, int]) -> str:
    sup = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
    return " × ".join(f"{p}{str(e).translate(sup) if e > 1 else ''}" for p, e in sorted(f.items()))


def factor_steps(n: int) -> List[str]:
    _check(n, 2)
    steps = []
    m = n
    d = 2
    while d * d <= m:
        while m % d == 0:
            steps.append(f"{m} ÷ {d} = {m // d}")
            m //= d
        d += 1 if d == 2 else 2
    if m > 1 and m != n:
        steps.append(f"{m} عدد أوّلي فنتوقّف.")
    f = factorize(n)
    steps.append(f"{n} = {factor_text(f)}")
    return steps


def is_prime(n: int) -> Tuple[bool, str]:
    _check(n, 1)
    if n == 1:
        return False, "الواحد ليس أوّليًّا ولا مركّبًا."
    if n < 4:
        return True, f"{n} أوّلي."
    if n % 2 == 0:
        return False, f"{n} زوجي، فيقبل القسمة على ٢."
    d = 3
    while d * d <= n:
        if n % d == 0:
            return False, f"{n} يقبل القسمة على {d} ({n} = {d} × {n // d})."
        d += 2
    return True, (f"{n} أوّلي: لا يقبل القسمة على أيّ عدد من ٢ إلى جذره التربيعي "
                  f"(نحو {math.isqrt(n)}).")


def divisors(n: int) -> List[int]:
    _check(n, 1)
    small, large = [], []
    d = 1
    while d * d <= n:
        if n % d == 0:
            small.append(d)
            if d != n // d:
                large.append(n // d)
        d += 1
    return small + large[::-1]


def gcd_steps(a: int, b: int) -> Tuple[int, List[str]]:
    _check(a, 1)
    _check(b, 1)
    steps = []
    x, y = max(a, b), min(a, b)
    while y:
        q, r = divmod(x, y)
        steps.append(f"{x} = {q} × {y} + {r}")
        x, y = y, r
    steps.append(f"آخر باقٍ غير صفري هو {x}، فالقاسم المشترك الأكبر ق.م.أ({a}، {b}) = {x}.")
    return x, steps


def lcm_steps(a: int, b: int) -> Tuple[int, List[str]]:
    g, steps = gcd_steps(a, b)
    l = a * b // g
    steps.append(f"المضاعف المشترك الأصغر = {a} × {b} ÷ {g} = {l}.")
    return l, steps


def divisibility(n: int) -> List[str]:
    _check(n, 1)
    s = str(n)
    digits = [int(c) for c in s]
    ds = sum(digits)
    lines = [
        f"٢: آخر رقم {digits[-1]} {'زوجي، فيقبل' if digits[-1] % 2 == 0 else 'فردي، فلا يقبل'} القسمة.",
        f"٣: مجموع الأرقام {ds} {'يقبل' if ds % 3 == 0 else 'لا يقبل'} القسمة على ٣.",
        f"٤: آخر رقمين {int(s[-2:])} {'يقبلان' if int(s[-2:]) % 4 == 0 else 'لا يقبلان'} القسمة على ٤.",
        f"٥: آخر رقم {digits[-1]} {'صفر أو خمسة، فيقبل' if digits[-1] in (0, 5) else 'ليس صفرًا ولا خمسة، فلا يقبل'}.",
        f"٦: {'يقبل' if n % 6 == 0 else 'لا يقبل'}، لأنه {'يقبل' if n % 2 == 0 else 'لا يقبل'} القسمة على ٢ "
        f"و{'يقبل' if n % 3 == 0 else 'لا يقبل'} القسمة على ٣.",
        f"٨: آخر ثلاثة أرقام {int(s[-3:])} {'تقبل' if int(s[-3:]) % 8 == 0 else 'لا تقبل'} القسمة على ٨.",
        f"٩: مجموع الأرقام {ds} {'يقبل' if ds % 9 == 0 else 'لا يقبل'} القسمة على ٩.",
        f"١٠: آخر رقم {'صفر، فيقبل' if digits[-1] == 0 else 'ليس صفرًا، فلا يقبل'}.",
    ]
    alt = sum(d if i % 2 == 0 else -d for i, d in enumerate(reversed(digits)))
    lines.append(f"١١: الفرق المتناوب بين الأرقام {alt} {'يقبل' if alt % 11 == 0 else 'لا يقبل'} القسمة على ١١.")
    return lines


def primes_up_to(n: int) -> List[int]:
    _check(n, 2)
    if n > 100000:
        raise ValueError("الحدّ الأعلى ١٠٠٠٠٠.")
    sieve = bytearray([1]) * (n + 1)
    sieve[0:2] = b"\x00\x00"
    for i in range(2, math.isqrt(n) + 1):
        if sieve[i]:
            sieve[i * i::i] = bytearray(len(sieve[i * i::i]))
    return [i for i in range(n + 1) if sieve[i]]


def properties(n: int) -> List[str]:
    _check(n, 1)
    out = [f"{n} عدد {'زوجي' if n % 2 == 0 else 'فردي'}."]
    r = math.isqrt(n)
    if r * r == n:
        out.append(f"مربّع كامل: {r}².")
    c = round(n ** (1 / 3))
    if c ** 3 == n:
        out.append(f"مكعّب كامل: {c}³.")
    if n > 1 and sum(divisors(n)[:-1]) == n:
        out.append("عدد تامّ: يساوي مجموع قواسمه دونه.")
    x = 5 * n * n
    if math.isqrt(x + 4) ** 2 == x + 4 or math.isqrt(x - 4) ** 2 == x - 4:
        out.append("من أعداد فيبوناتشي.")
    out.append(f"عدد قواسمه {len(divisors(n))}.")
    return out


# ---------------------------------------------------------------------------
# combinatorics and probability
# ---------------------------------------------------------------------------

def factorial_steps(n: int) -> Tuple[int, str]:
    if not 0 <= n <= 170:
        raise ValueError("اكتب عددًا من ٠ إلى ١٧٠.")
    if n <= 1:
        return 1, f"{n}! = 1"
    v = math.factorial(n)
    shown = " × ".join(str(k) for k in range(n, 0, -1)) if n <= 10 else f"{n} × {n - 1} × … × 1"
    return v, f"{n}! = {shown} = {v}"


def permutations(n: int, r: int) -> Tuple[int, str]:
    if not 0 <= r <= n <= 1000:
        raise ValueError("يجب أن يكون ٠ ≤ ر ≤ ن.")
    v = math.perm(n, r)
    return v, f"عدد التباديل ل({n}، {r}) = {n}! ÷ ({n} − {r})! = {v} (الترتيب مهمّ)."


def combinations(n: int, r: int) -> Tuple[int, str]:
    if not 0 <= r <= n <= 1000:
        raise ValueError("يجب أن يكون ٠ ≤ ر ≤ ن.")
    v = math.comb(n, r)
    return v, f"عدد التوافيق ق({n}، {r}) = {n}! ÷ ({r}! × ({n} − {r})!) = {v} (الترتيب غير مهمّ)."


def dice_sum_probability(total: int, dice: int = 2) -> Tuple[Fraction, str]:
    if not 1 <= dice <= 6:
        raise ValueError("من حجر نرد واحد إلى ستة.")
    ways = [0] * (6 * dice + 1)
    ways[0] = 1
    for _ in range(dice):
        new = [0] * (6 * dice + 1)
        for s, w in enumerate(ways):
            if w:
                for f in range(1, 7):
                    if s + f <= 6 * dice:
                        new[s + f] += w
        ways = new
    count = ways[total] if 0 <= total <= 6 * dice else 0
    p = Fraction(count, 6 ** dice)
    return p, (f"احتمال أن يكون مجموع أحجار النرد ({dice}) {total}: الحالات المناسبة {count} من {6 ** dice} "
               f"= {p.numerator}/{p.denominator} ≈ {float(p):.2%}.")


def coins_probability(heads: int, flips: int) -> Tuple[Fraction, str]:
    if not 0 <= heads <= flips <= 60:
        raise ValueError("عدد الرميات من ١ إلى ٦٠، والوجوه لا تزيد عليها.")
    p = Fraction(math.comb(flips, heads), 2 ** flips)
    return p, (f"احتمال ظهور الصورة {heads} من المرّات في {flips} من الرميات: ق({flips}، {heads}) ÷ 2^{flips} "
               f"= {p.numerator}/{p.denominator} ≈ {float(p):.2%}.")


def bag_probability(wanted: int, total: int, draws: int = 1, want_all: bool = True) -> Tuple[Fraction, str]:
    """Probability that ``draws`` balls drawn without replacement are all of
    the wanted colour (``wanted`` of ``total`` balls)."""
    if not 0 <= wanted <= total or not 1 <= draws <= total:
        raise ValueError("تحقّق من الأعداد: المطلوب لا يزيد على الكلّ، والسحبات بين ١ والكلّ.")
    p = Fraction(math.comb(wanted, draws), math.comb(total, draws)) if draws <= wanted else Fraction(0)
    return p, (f"احتمال أن تكون الكرات المسحوبة ({draws}) كلّها من النوع المطلوب ({wanted} من {total}) "
               f"= ق({wanted}، {draws}) ÷ ق({total}، {draws}) = {p.numerator}/{p.denominator} ≈ {float(p):.2%}.")
