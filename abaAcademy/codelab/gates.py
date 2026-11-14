# -*- coding: utf-8 -*-
"""
abaAcademy.codelab.gates
========================

Digital logic for programming students: the seven basic gates, their truth
tables read aloud, binary addition with a half adder and a ripple-carry full
adder (showing every carry), and a quiz on gate outputs.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

GATES: Dict[str, Tuple[str, Callable[..., int], int, str]] = {
    "AND": ("و (AND)", lambda a, b: a & b, 2, "تعطي ١ فقط إذا كان الدخلان كلاهما ١."),
    "OR": ("أو (OR)", lambda a, b: a | b, 2, "تعطي ١ إذا كان أحد الدخلين على الأقلّ ١."),
    "NOT": ("ليس (NOT)", lambda a: 1 - a, 1, "تعكس الدخل: ١ تصبح ٠ و٠ تصبح ١."),
    "NAND": ("ليس-و (NAND)", lambda a, b: 1 - (a & b), 2, "عكس AND: تعطي ٠ فقط إذا كان الدخلان ١."),
    "NOR": ("ليس-أو (NOR)", lambda a, b: 1 - (a | b), 2, "عكس OR: تعطي ١ فقط إذا كان الدخلان ٠."),
    "XOR": ("أو الحصرية (XOR)", lambda a, b: a ^ b, 2, "تعطي ١ إذا اختلف الدخلان."),
    "XNOR": ("التكافؤ (XNOR)", lambda a, b: 1 - (a ^ b), 2, "تعطي ١ إذا تساوى الدخلان."),
}


def evaluate(gate: str, *inputs: int) -> int:
    name, fn, arity, _ = GATES[gate]
    if len(inputs) != arity:
        raise ValueError(f"البوّابة {name} تأخذ {arity} دخل.")
    if any(x not in (0, 1) for x in inputs):
        raise ValueError("الدخل يكون ٠ أو ١.")
    return fn(*inputs)


def truth_table(gate: str) -> List[str]:
    name, fn, arity, desc = GATES[gate]
    lines = [f"البوّابة {name}: {desc}"]
    for combo in itertools.product((0, 1), repeat=arity):
        ins = " و".join(str(x) for x in combo)
        lines.append(f"الدخل {ins} ← الخرج {fn(*combo)}")
    return lines


def half_adder(a: int, b: int) -> Tuple[int, int]:
    """(sum, carry)."""
    return a ^ b, a & b


def full_adder(a: int, b: int, cin: int) -> Tuple[int, int]:
    s1, c1 = half_adder(a, b)
    s, c2 = half_adder(s1, cin)
    return s, c1 | c2


def _bits(text: str) -> str:
    t = text.strip().replace(" ", "").translate(str.maketrans("٠١", "01"))
    if not t or any(c not in "01" for c in t):
        raise ValueError("اكتب عددًا ثنائيًّا من الأصفار والآحاد.")
    return t


def add_binary(a_text: str, b_text: str) -> Tuple[str, List[str]]:
    a, b = _bits(a_text), _bits(b_text)
    n = max(len(a), len(b))
    a, b = a.zfill(n), b.zfill(n)
    carry = 0
    out = []
    steps = [f"نجمع {a} + {b} من اليمين، والخانة الأولى هي الأقلّ قيمة."]
    for i in range(n - 1, -1, -1):
        x, y = int(a[i]), int(b[i])
        s, c = full_adder(x, y, carry)
        pos = n - i
        steps.append(f"الخانة {pos}: {x} + {y} + الحمل {carry} = الناتج {s} والحمل {c}"
                     f" (XOR للناتج، وAND/OR للحمل).")
        out.append(str(s))
        carry = c
    if carry:
        out.append("1")
        steps.append("يبقى حمل ١ فنضعه في خانة جديدة على اليسار.")
    result = "".join(reversed(out))
    steps.append(f"الناتج: {result}، أي {int(a, 2)} + {int(b, 2)} = {int(result, 2)} بالعشري.")
    return result, steps


@dataclass
class Question:
    prompt: str
    answer: str
    options: List[str]
    explanation: str


def make_question(rng: Optional[random.Random] = None) -> Question:
    rng = rng or random.Random()
    gate = rng.choice(list(GATES))
    name, fn, arity, desc = GATES[gate]
    ins = [rng.randint(0, 1) for _ in range(arity)]
    out = fn(*ins)
    shown = " و".join(str(x) for x in ins)
    return Question(f"ما خرج البوّابة {name} إذا كان الدخل {shown}؟", str(out), ["0", "1"],
                    f"{name}: {desc} فالخرج {out}.")


def identify_question(rng: Optional[random.Random] = None) -> Question:
    """Which gate has this truth table?"""
    rng = rng or random.Random()
    two = [g for g, v in GATES.items() if v[2] == 2]
    gate = rng.choice(two)
    fn = GATES[gate][1]
    table = "، ".join(f"{a}{b}←{fn(a, b)}" for a, b in itertools.product((0, 1), repeat=2))
    others = [g for g in two if g != gate]
    rng.shuffle(others)
    opts = [GATES[g][0] for g in [gate] + others[:3]]
    rng.shuffle(opts)
    return Question(f"أيّ بوّابة لها هذا الجدول: {table}؟", GATES[gate][0], opts,
                    f"إنها {GATES[gate][0]}: {GATES[gate][3]}")
