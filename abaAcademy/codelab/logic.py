# -*- coding: utf-8 -*-
"""
abaAcademy.codelab.logic
========================

Propositional logic for programming and maths students: parse an
expression, build its truth table, and classify it (tautology,
contradiction, contingent). Two expressions can be checked for
equivalence, and the screen reads the truth table row by row.

Accepted syntax, in Arabic or English or symbols:
    و  and  &  ∧  &&        —  conjunction
    أو  or   |  ∨  ||        —  disjunction
    ليس  not  !  ~  ¬        —  negation
    يؤدي  ->  →  implies    —  implication
    يكافئ  <->  ↔  iff      —  equivalence
    xor  ⊕  أو_الحصري       —  exclusive or
Variables are single words (أ، ب، p, q, x1 …); parentheses group.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple, Union

_OPS = {
    "not": ("not", 4), "ليس": ("not", 4), "!": ("not", 4), "~": ("not", 4), "¬": ("not", 4),
    "and": ("and", 3), "و": ("and", 3), "&": ("and", 3), "&&": ("and", 3), "∧": ("and", 3),
    "xor": ("xor", 2), "⊕": ("xor", 2), "أو_الحصري": ("xor", 2),
    "or": ("or", 2), "أو": ("or", 2), "|": ("or", 2), "||": ("or", 2), "∨": ("or", 2),
    "->": ("imp", 1), "→": ("imp", 1), "implies": ("imp", 1), "يؤدي": ("imp", 1), "يستلزم": ("imp", 1),
    "<->": ("iff", 0), "↔": ("iff", 0), "iff": ("iff", 0), "يكافئ": ("iff", 0),
}
OP_NAMES = {"not": "ليس", "and": "و", "or": "أو", "xor": "أو الحصري", "imp": "يؤدي إلى",
            "iff": "يكافئ"}
_TOKEN = re.compile(r"\s*(<->|->|&&|\|\||[()!~¬∧∨→↔⊕&|]|[^\s()!~¬∧∨→↔⊕&|]+)")
_TRUE = {"1", "true", "صح", "صواب", "T"}
_FALSE = {"0", "false", "خطأ", "F"}

Node = Union[str, bool, Tuple]


def tokenize(text: str) -> List[str]:
    pos, out = 0, []
    text = text.strip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ValueError(f"لم أفهم {text[pos:]}.")
        out.append(m.group(1))
        pos = m.end()
    return out


class _Parser:
    def __init__(self, tokens: Sequence[str]):
        self.t = list(tokens)
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self) -> Node:
        node = self.expr(0)
        if self.peek() is not None:
            raise ValueError(f"رمز زائد: {self.peek()}.")
        return node

    def expr(self, min_prec: int) -> Node:
        left = self.unary()
        while True:
            tok = self.peek()
            op = _OPS.get(tok.lower() if tok else None) if tok else None
            if not op or op[0] == "not" or op[1] < min_prec:
                return left
            name, prec = op
            self.take()
            # implication is right-associative
            right = self.expr(prec if name == "imp" else prec + 1)
            left = (name, left, right)

    def unary(self) -> Node:
        tok = self.take()
        if tok is None:
            raise ValueError("التعبير ناقص.")
        op = _OPS.get(tok.lower())
        if op and op[0] == "not":
            return ("not", self.unary())
        if tok == "(":
            node = self.expr(0)
            if self.take() != ")":
                raise ValueError("قوس غير مغلق.")
            return node
        if tok == ")" or op:
            raise ValueError(f"لم أتوقّع {tok} هنا.")
        if tok in _TRUE:
            return True
        if tok in _FALSE:
            return False
        return tok


def parse(text: str) -> Node:
    if not text.strip():
        raise ValueError("اكتب تعبيرًا منطقيًّا.")
    return _Parser(tokenize(text)).parse()


def variables(node: Node) -> List[str]:
    out: List[str] = []

    def walk(n):
        if isinstance(n, tuple):
            for c in n[1:]:
                walk(c)
        elif isinstance(n, str) and n not in out:
            out.append(n)
    walk(node)
    return out


def evaluate(node: Node, env: Dict[str, bool]) -> bool:
    if isinstance(node, bool):
        return node
    if isinstance(node, str):
        return env[node]
    op = node[0]
    if op == "not":
        return not evaluate(node[1], env)
    a = evaluate(node[1], env)
    b = evaluate(node[2], env)
    return {"and": a and b, "or": a or b, "xor": a != b,
            "imp": (not a) or b, "iff": a == b}[op]


def to_text(node: Node) -> str:
    if isinstance(node, bool):
        return "صح" if node else "خطأ"
    if isinstance(node, str):
        return node
    if node[0] == "not":
        return f"ليس {to_text(node[1])}"
    return f"({to_text(node[1])} {OP_NAMES[node[0]]} {to_text(node[2])})"


@dataclass
class TruthTable:
    expression: str
    variables: List[str]
    rows: List[Tuple[Tuple[bool, ...], bool]]

    @property
    def kind(self) -> str:
        results = [r for _, r in self.rows]
        if all(results):
            return "tautology"
        if not any(results):
            return "contradiction"
        return "contingent"

    def kind_text(self) -> str:
        return {"tautology": "تحصيل حاصل (صحيح دائمًا)",
                "contradiction": "تناقض (خاطئ دائمًا)",
                "contingent": "ممكن (يصدق في بعض الحالات)"}[self.kind]

    def row_text(self, i: int) -> str:
        values, result = self.rows[i]
        parts = [f"{v} {'صح' if b else 'خطأ'}" for v, b in zip(self.variables, values)]
        return f"الصفّ {i + 1}: " + "، ".join(parts) + f" ← النتيجة {'صح' if result else 'خطأ'}"

    def text(self) -> str:
        head = " | ".join(self.variables + ["النتيجة"])
        lines = [head]
        for values, r in self.rows:
            lines.append(" | ".join(("1" if b else "0") for b in values) + f" | {'1' if r else '0'}")
        return "\n".join(lines)

    def true_rows(self) -> List[int]:
        return [i for i, (_, r) in enumerate(self.rows) if r]


def truth_table(text: str, max_vars: int = 6) -> TruthTable:
    node = parse(text)
    vs = variables(node)
    if len(vs) > max_vars:
        raise ValueError(f"عدد المتغيّرات كبير ({len(vs)}). الحدّ {max_vars}.")
    rows = []
    for combo in itertools.product([True, False], repeat=len(vs)):
        rows.append((combo, evaluate(node, dict(zip(vs, combo)))))
    return TruthTable(text, vs, rows)


def equivalent(a: str, b: str) -> Tuple[bool, str]:
    na, nb = parse(a), parse(b)
    vs = variables(na)
    for v in variables(nb):
        if v not in vs:
            vs.append(v)
    for combo in itertools.product([True, False], repeat=len(vs)):
        env = dict(zip(vs, combo))
        if evaluate(na, env) != evaluate(nb, env):
            case = "، ".join(f"{v} {'صح' if b_ else 'خطأ'}" for v, b_ in env.items())
            return False, f"غير متكافئين: عندما {case} يختلف الناتج."
    return True, "التعبيران متكافئان في كلّ الحالات."


LAWS = (
    ("قانونا دي مورغان", "ليس (أ و ب)", "ليس أ أو ليس ب"),
    ("قانونا دي مورغان", "ليس (أ أو ب)", "ليس أ و ليس ب"),
    ("النفي المزدوج", "ليس ليس أ", "أ"),
    ("الاستلزام", "أ -> ب", "ليس أ أو ب"),
    ("عكس النقيض", "أ -> ب", "ليس ب -> ليس أ"),
    ("التوزيع", "أ و (ب أو ج)", "(أ و ب) أو (أ و ج)"),
    ("الامتصاص", "أ أو (أ و ب)", "أ"),
    ("التكافؤ", "أ <-> ب", "(أ -> ب) و (ب -> أ)"),
)
