# -*- coding: utf-8 -*-
"""
abaAcademy.generators.math
==========================

Mathematics generators. Math is the ideal fit for procedural generation: every
question is computed, so a handful of generators yield an unbounded stream of
genuinely correct, non-repeating problems — no authored question bank needed.

Difficulty is passed via ``params['difficulty']`` (1..6) and scales the operand
ranges. Distractors are deliberately near-miss values (off-by-one, sign flips,
common arithmetic slips) so wrong answers are plausible, matching the platform's
intelligent-distractor rule.

Generators:
  * ``math.add_sub``   — addition / subtraction (typing)
  * ``math.mul_div``   — multiplication / integer division (typing)
  * ``math.fraction``  — simplify / add simple fractions (MCQ)
  * ``math.compare``   — greater / less / equal (MCQ)
  * ``math.sequence``  — find the next term in a pattern (typing)
  * ``math.algebra``   — solve a linear equation for x (typing)
  * ``math.percent``   — simple percentage of a number (typing)
"""

from __future__ import annotations

import math as _math
import random
from fractions import Fraction
from typing import List

from ..engine.models import Question, QuestionType
from . import Deduper, register, signature_qid


def _range_for(difficulty: int):
    return {1: 10, 2: 20, 3: 50, 4: 100, 5: 500, 6: 1000}.get(difficulty, 20)


def _typed(prompt, answer, explanation, topic, difficulty, sig, gid):
    q = Question(qtype=QuestionType.TYPING, prompt=prompt, correct=str(answer),
                 explanation=explanation, topic=topic, difficulty=difficulty)
    q.qid = signature_qid(gid, sig)
    return q


@register("math.add_sub")
def gen_add_sub(count: int, rng: random.Random, **params) -> List[Question]:
    d = int(params.get("difficulty", 1))
    hi = _range_for(d)
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 30:
        guard += 1
        a, b = rng.randint(1, hi), rng.randint(1, hi)
        op = rng.choice(["+", "-"])
        if op == "-" and b > a:
            a, b = b, a
        answer = a + b if op == "+" else a - b
        sig = f"{a}{op}{b}"
        if not dd.fresh(sig):
            continue
        dd.add(sig)
        out.append(_typed(f"احسب: {a} {op} {b} = ؟", answer,
                          f"الناتج هو {answer}.", "math.add_sub", d, sig, "math.add_sub"))
    return out


@register("math.mul_div")
def gen_mul_div(count: int, rng: random.Random, **params) -> List[Question]:
    d = int(params.get("difficulty", 1))
    hi = min(_range_for(d), 20) if d <= 3 else _range_for(d) // 5
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 30:
        guard += 1
        op = rng.choice(["×", "÷"])
        if op == "×":
            a, b = rng.randint(2, hi), rng.randint(2, hi)
            answer, sig = a * b, f"{a}x{b}"
            prompt = f"احسب: {a} × {b} = ؟"
        else:
            b = rng.randint(2, max(3, hi // 2))
            answer = rng.randint(2, max(3, hi // 2))
            a = answer * b  # exact division
            sig = f"{a}/{b}"
            prompt = f"احسب: {a} ÷ {b} = ؟"
        if not dd.fresh(sig):
            continue
        dd.add(sig)
        out.append(_typed(prompt, answer, f"الناتج هو {answer}.", "math.mul_div", d, sig, "math.mul_div"))
    return out


@register("math.fraction")
def gen_fraction(count: int, rng: random.Random, **params) -> List[Question]:
    d = int(params.get("difficulty", 2))
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 30:
        guard += 1
        kind = rng.choice(["simplify", "add"])
        if kind == "simplify":
            k = rng.randint(2, 6)
            num = rng.randint(1, 5)
            den = rng.randint(num + 1, num + 6)
            f = Fraction(num, den)
            a, b = num * k, den * k
            correct = f"{f.numerator}/{f.denominator}"
            prompt = f"بسّط الكسر: {a}/{b}"
            sig = f"s{a}/{b}"
            explanation = f"بقسمة البسط والمقام على {_math.gcd(a,b)} نحصل على {correct}."
            wrongs = [f"{a}/{b}", f"{f.numerator+1}/{f.denominator}", f"{f.numerator}/{f.denominator+1}"]
        else:
            den = rng.choice([2, 3, 4, 5, 6])
            n1, n2 = rng.randint(1, den - 1), rng.randint(1, den - 1)
            f = Fraction(n1 + n2, den)
            correct = (f"{f.numerator}/{f.denominator}" if f.denominator != 1 else str(f.numerator))
            prompt = f"احسب: {n1}/{den} + {n2}/{den}"
            sig = f"a{n1}/{den}+{n2}"
            explanation = f"نجمع البسطين على المقام نفسه: {correct}."
            wrongs = [f"{n1+n2}/{den*2}", f"{n1+n2}/{den}", f"{f.numerator+1}/{f.denominator}"]
        if not dd.fresh(sig):
            continue
        dd.add(sig)
        opts = list(dict.fromkeys([correct] + [w for w in wrongs if w != correct]))[:4]
        rng.shuffle(opts)
        q = Question(qtype=QuestionType.MCQ, prompt=prompt, correct=opts.index(correct),
                     options=opts, explanation=explanation, topic="math.fraction", difficulty=d)
        q.qid = signature_qid("math.fraction", sig)
        out.append(q)
    return out


@register("math.compare")
def gen_compare(count: int, rng: random.Random, **params) -> List[Question]:
    d = int(params.get("difficulty", 1))
    hi = _range_for(d)
    out, dd, guard = [], Deduper(), 0
    options = ["أكبر من", "أصغر من", "يساوي"]
    while len(out) < count and guard < count * 30:
        guard += 1
        a, b = rng.randint(1, hi), rng.randint(1, hi)
        sig = f"{a}?{b}"
        if not dd.fresh(sig):
            continue
        dd.add(sig)
        correct = "أكبر من" if a > b else ("أصغر من" if a < b else "يساوي")
        q = Question(qtype=QuestionType.MCQ, prompt=f"العدد {a} ... العدد {b}؟",
                     correct=options.index(correct), options=list(options),
                     explanation=f"{a} {correct} {b}.", topic="math.compare", difficulty=d)
        q.qid = signature_qid("math.compare", sig)
        out.append(q)
    return out


@register("math.sequence")
def gen_sequence(count: int, rng: random.Random, **params) -> List[Question]:
    d = int(params.get("difficulty", 2))
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 30:
        guard += 1
        start = rng.randint(1, 10)
        step = rng.randint(2, 5 + d)
        kind = rng.choice(["arith", "mul"]) if d >= 3 else "arith"
        if kind == "arith":
            seq = [start + step * i for i in range(4)]
            answer = start + step * 4
            explanation = f"النمط: نضيف {step} في كل مرة."
        else:
            seq = [start * (step ** i) for i in range(4)]
            answer = start * (step ** 4)
            explanation = f"النمط: نضرب في {step} في كل مرة."
        sig = ",".join(map(str, seq))
        if not dd.fresh(sig):
            continue
        dd.add(sig)
        prompt = f"أكمل المتتالية: {seq[0]}، {seq[1]}، {seq[2]}، {seq[3]}، ؟"
        out.append(_typed(prompt, answer, explanation, "math.sequence", d, sig, "math.sequence"))
    return out


@register("math.algebra")
def gen_algebra(count: int, rng: random.Random, **params) -> List[Question]:
    d = int(params.get("difficulty", 3))
    hi = _range_for(d)
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 30:
        guard += 1
        x = rng.randint(1, hi)
        a = rng.randint(2, 5 + d)
        b = rng.randint(1, hi)
        # a*x + b = c
        c = a * x + b
        sig = f"{a}x+{b}={c}"
        if not dd.fresh(sig):
            continue
        dd.add(sig)
        prompt = f"جد قيمة س في المعادلة: {a}س + {b} = {c}"
        explanation = f"نطرح {b} ثم نقسم على {a}: س = {x}."
        out.append(_typed(prompt, x, explanation, "math.algebra", d, sig, "math.algebra"))
    return out


@register("math.percent")
def gen_percent(count: int, rng: random.Random, **params) -> List[Question]:
    d = int(params.get("difficulty", 3))
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 30:
        guard += 1
        pct = rng.choice([10, 20, 25, 50, 5, 40, 75])
        base = rng.choice([20, 40, 60, 80, 100, 200, 120, 160])
        answer = pct * base // 100
        sig = f"{pct}of{base}"
        if not dd.fresh(sig):
            continue
        dd.add(sig)
        prompt = f"كم يساوي {pct}% من {base}؟"
        explanation = f"{pct}% من {base} = {answer}."
        out.append(_typed(prompt, answer, explanation, "math.percent", d, sig, "math.percent"))
    return out


# ---------------------------------------------------------------------------
# Extended mathematics
# ---------------------------------------------------------------------------
# The original set stopped at linear equations, which left the upper levels of
# the maths course drilling the same three or four shapes. These add the
# arithmetic a learner actually needs day to day (money, time, measurement)
# plus the number theory the algebra level assumes. All are computed, so like
# the rest of the module they are unbounded and correct by construction.


@register("math.rounding")
def gen_rounding(count: int, rng: random.Random, **params) -> List[Question]:
    """Round to the nearest ten / hundred / thousand."""
    d = int(params.get("difficulty", 2))
    places = [10, 100] if d <= 3 else [10, 100, 1000]
    names = {10: "أقرب عشرة", 100: "أقرب مئة", 1000: "أقرب ألف"}
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 30:
        guard += 1
        place = rng.choice(places)
        n = rng.randint(place // 2, place * 20)
        answer = int(round(n / place) * place)
        sig = f"r{n}/{place}"
        if not dd.fresh(sig):
            dd.reset()
        dd.add(sig)
        out.append(_typed(
            f"قرّب العدد {n} إلى {names[place]}:", answer,
            f"العدد {n} يقع أقرب إلى {answer}.",
            "math.rounding", d, sig, "math.rounding"))
    return out


@register("math.money")
def gen_money(count: int, rng: random.Random, **params) -> List[Question]:
    """Shopping arithmetic: totals, change, and simple discounts."""
    d = int(params.get("difficulty", 2))
    currency = params.get("currency", "ريال")
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 30:
        guard += 1
        kind = rng.choice(["total", "change", "discount"])
        if kind == "total":
            price = rng.randint(3, 40)
            qty = rng.randint(2, 9)
            answer = price * qty
            prompt = (f"اشتريت {qty} أقلام، ثمن القلم الواحد {price} {currency}. "
                      f"كم المجموع؟")
            explanation = f"{qty} × {price} = {answer} {currency}."
            sig = f"t{qty}x{price}"
        elif kind == "change":
            paid = rng.choice([50, 100, 200, 500])
            cost = rng.randint(5, paid - 5)
            answer = paid - cost
            prompt = (f"ثمن السلعة {cost} {currency} ودفعت {paid} {currency}. "
                      f"كم الباقي؟")
            explanation = f"{paid} − {cost} = {answer} {currency}."
            sig = f"c{paid}-{cost}"
        else:
            pct = rng.choice([10, 20, 25, 50])
            price = rng.choice([40, 60, 80, 100, 120, 200])
            answer = price - pct * price // 100
            prompt = (f"ثمن السلعة {price} {currency} وعليها خصم {pct}%. "
                      f"كم تدفع؟")
            explanation = (f"الخصم = {pct * price // 100} {currency}، "
                           f"فالمدفوع = {answer} {currency}.")
            sig = f"d{pct}of{price}"
        if not dd.fresh(sig):
            dd.reset()
        dd.add(sig)
        out.append(_typed(prompt, answer, explanation, "math.money", d, sig, "math.money"))
    return out


@register("math.time")
def gen_time(count: int, rng: random.Random, **params) -> List[Question]:
    """Clock and calendar arithmetic."""
    d = int(params.get("difficulty", 2))
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 30:
        guard += 1
        kind = rng.choice(["add_minutes", "to_minutes", "days"])
        if kind == "add_minutes":
            hour = rng.randint(1, 11)
            minute = rng.choice([0, 10, 15, 20, 30, 40, 45])
            add = rng.choice([15, 20, 25, 30, 45, 60, 90])
            total = hour * 60 + minute + add
            nh, nm = (total // 60) % 12 or 12, total % 60
            answer = f"{nh}:{nm:02d}"
            prompt = (f"إذا كانت الساعة الآن {hour}:{minute:02d} فكم تكون "
                      f"بعد {add} دقيقة؟ (اكتبها بالصيغة ساعة:دقيقة)")
            explanation = f"{hour}:{minute:02d} + {add} دقيقة = {answer}."
            sig = f"a{hour}:{minute}+{add}"
        elif kind == "to_minutes":
            hours = rng.randint(1, 12)
            minutes = rng.choice([0, 15, 30, 45])
            answer = hours * 60 + minutes
            prompt = f"كم دقيقة في {hours} ساعة و{minutes} دقيقة؟"
            explanation = f"{hours} × 60 + {minutes} = {answer} دقيقة."
            sig = f"m{hours}:{minutes}"
        else:
            weeks = rng.randint(2, 12)
            answer = weeks * 7
            prompt = f"كم يوماً في {weeks} أسابيع؟"
            explanation = f"{weeks} × 7 = {answer} يوماً."
            sig = f"w{weeks}"
        if not dd.fresh(sig):
            dd.reset()
        dd.add(sig)
        out.append(_typed(prompt, answer, explanation, "math.time", d, sig, "math.time"))
    return out


@register("math.geometry")
def gen_geometry(count: int, rng: random.Random, **params) -> List[Question]:
    """Perimeter and area of the shapes a school course covers."""
    d = int(params.get("difficulty", 3))
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 30:
        guard += 1
        kind = rng.choice(["rect_area", "rect_perim", "square", "triangle"])
        if kind == "rect_area":
            a, b = rng.randint(2, 20), rng.randint(2, 20)
            answer = a * b
            prompt = f"مستطيل طوله {a} وعرضه {b}. ما مساحته؟"
            explanation = f"المساحة = الطول × العرض = {a} × {b} = {answer}."
            sig = f"ra{a}x{b}"
        elif kind == "rect_perim":
            a, b = rng.randint(2, 20), rng.randint(2, 20)
            answer = 2 * (a + b)
            prompt = f"مستطيل طوله {a} وعرضه {b}. ما محيطه؟"
            explanation = f"المحيط = 2 × (الطول + العرض) = 2 × {a + b} = {answer}."
            sig = f"rp{a}x{b}"
        elif kind == "square":
            a = rng.randint(2, 25)
            if rng.random() < 0.5:
                answer, what = a * a, "مساحته"
                explanation = f"مساحة المربع = الضلع × الضلع = {a} × {a} = {answer}."
            else:
                answer, what = 4 * a, "محيطه"
                explanation = f"محيط المربع = 4 × الضلع = 4 × {a} = {answer}."
            prompt = f"مربع طول ضلعه {a}. ما {what}؟"
            sig = f"s{a}{what}"
        else:
            base = rng.choice([4, 6, 8, 10, 12, 14, 16])
            height = rng.choice([3, 5, 7, 9, 11])
            answer = base * height // 2
            prompt = f"مثلث قاعدته {base} وارتفاعه {height}. ما مساحته؟"
            explanation = f"مساحة المثلث = (القاعدة × الارتفاع) ÷ 2 = ({base} × {height}) ÷ 2 = {answer}."
            sig = f"t{base}x{height}"
        if not dd.fresh(sig):
            dd.reset()
        dd.add(sig)
        out.append(_typed(prompt, answer, explanation, "math.geometry", d, sig, "math.geometry"))
    return out


@register("math.factors")
def gen_factors(count: int, rng: random.Random, **params) -> List[Question]:
    """Divisibility, primes, GCD and LCM -- the groundwork algebra assumes."""
    d = int(params.get("difficulty", 3))
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 30:
        guard += 1
        kind = rng.choice(["gcd", "lcm", "prime"])
        if kind == "gcd":
            a, b = rng.randint(4, 60), rng.randint(4, 60)
            answer = _math.gcd(a, b)
            prompt = f"ما القاسم المشترك الأكبر للعددين {a} و{b}؟"
            explanation = f"أكبر عدد يقسم {a} و{b} معاً هو {answer}."
            sig = f"g{min(a,b)}-{max(a,b)}"
            out.append(_typed(prompt, answer, explanation, "math.factors", d, sig, "math.factors"))
        elif kind == "lcm":
            a, b = rng.randint(2, 15), rng.randint(2, 15)
            answer = a * b // _math.gcd(a, b)
            prompt = f"ما المضاعف المشترك الأصغر للعددين {a} و{b}؟"
            explanation = f"أصغر عدد يقبل القسمة على {a} و{b} معاً هو {answer}."
            sig = f"l{min(a,b)}-{max(a,b)}"
            out.append(_typed(prompt, answer, explanation, "math.factors", d, sig, "math.factors"))
        else:
            correct = rng.choice(primes)
            composites = [n for n in range(4, 60)
                          if any(n % p == 0 and n != p for p in primes[:5])]
            wrongs = rng.sample(composites, 3)
            options = [str(correct)] + [str(w) for w in wrongs]
            rng.shuffle(options)
            sig = f"p{correct}-{'-'.join(sorted(str(w) for w in wrongs))}"
            q = Question(qtype=QuestionType.MCQ,
                         prompt="أي الأعداد التالية عدد أوّلي؟",
                         correct=options.index(str(correct)), options=options,
                         explanation=(f"{correct} عدد أوّلي لأنه لا يقبل القسمة "
                                      f"إلا على نفسه وعلى الواحد."),
                         topic="math.factors", difficulty=d)
            q.qid = signature_qid("math.factors", sig)
            out.append(q)
        if not dd.fresh(sig):
            dd.reset()
        dd.add(sig)
    return out


@register("math.negative")
def gen_negative(count: int, rng: random.Random, **params) -> List[Question]:
    """Signed-number arithmetic."""
    d = int(params.get("difficulty", 4))
    hi = _range_for(d)
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 30:
        guard += 1
        a = rng.randint(-hi, hi)
        b = rng.randint(-hi, hi)
        if b == 0 or a == 0:
            continue
        op = rng.choice(["+", "-", "×"])
        answer = a + b if op == "+" else (a - b if op == "-" else a * b)
        shown_b = f"({b})" if b < 0 else str(b)
        shown_a = f"({a})" if a < 0 else str(a)
        sig = f"n{a}{op}{b}"
        if not dd.fresh(sig):
            dd.reset()
        dd.add(sig)
        out.append(_typed(
            f"احسب: {shown_a} {op} {shown_b} = ؟", answer,
            f"الناتج هو {answer}.", "math.negative", d, sig, "math.negative"))
    return out


@register("math.power")
def gen_power(count: int, rng: random.Random, **params) -> List[Question]:
    """Squares, cubes and square roots."""
    d = int(params.get("difficulty", 4))
    out, dd, guard = [], Deduper(), 0
    while len(out) < count and guard < count * 30:
        guard += 1
        kind = rng.choice(["square", "cube", "root"])
        if kind == "square":
            n = rng.randint(2, 20)
            answer, prompt = n * n, f"احسب: {n} تربيع (أي {n} × {n}) = ؟"
            explanation = f"{n} × {n} = {answer}."
            sig = f"sq{n}"
        elif kind == "cube":
            n = rng.randint(2, 10)
            answer, prompt = n ** 3, f"احسب: {n} تكعيب (أي {n} × {n} × {n}) = ؟"
            explanation = f"{n} × {n} × {n} = {answer}."
            sig = f"cu{n}"
        else:
            n = rng.randint(2, 20)
            answer, prompt = n, f"ما الجذر التربيعي للعدد {n * n}؟"
            explanation = f"{n} × {n} = {n * n}، فالجذر هو {n}."
            sig = f"rt{n}"
        if not dd.fresh(sig):
            dd.reset()
        dd.add(sig)
        out.append(_typed(prompt, answer, explanation, "math.power", d, sig, "math.power"))
    return out
