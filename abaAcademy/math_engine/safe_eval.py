# -*- coding: utf-8 -*-
"""
abaAcademy.math_engine.safe_eval
================================

A safe evaluator for single-variable mathematical expressions typed by the user
(e.g. ``x^2 + 3*x - 5``, ``sin(x)/x``). We do NOT use Python's ``eval`` on user
text — that would be a security hole. Instead we compile the expression once to
Python's AST, walk it, and reject anything that isn't arithmetic over a small
whitelist of functions and constants. The result is a fast callable ``f(x)``.

This is deliberately small and auditable: only numbers, the variable, the basic
operators, parentheses, a caret treated as power, and the whitelisted names are
allowed. Anything else raises ``ValueError`` with an Arabic message.
"""

from __future__ import annotations

import ast
import math
import operator


_ALLOWED_FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "sqrt": math.sqrt, "cbrt": lambda v: math.copysign(abs(v) ** (1 / 3), v),
    "log": math.log, "ln": math.log, "log10": math.log10, "log2": math.log2,
    "exp": math.exp, "abs": abs, "floor": math.floor, "ceil": math.ceil,
}
_ALLOWED_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}

_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


class SafeFunction:
    """A compiled, sandboxed single-variable function. Call it with a float."""

    def __init__(self, expression, var="x"):
        self.source = expression
        self.var = var
        # normalise ^ to ** (common user habit) and unicode operators
        norm = (expression.replace("^", "**")
                .replace("×", "*").replace("÷", "/")
                .replace("−", "-"))
        try:
            self._tree = ast.parse(norm, mode="eval")
        except SyntaxError as exc:
            raise ValueError("صيغة الدالة غير صحيحة.") from exc
        self._validate(self._tree.body)

    def _validate(self, node):
        # walk once up front so evaluation can't hit anything unexpected
        if isinstance(node, ast.BinOp):
            if type(node.op) not in _BIN_OPS:
                raise ValueError("عملية غير مسموحة في الدالة.")
            self._validate(node.left)
            self._validate(node.right)
        elif isinstance(node, ast.UnaryOp):
            if type(node.op) not in _UNARY_OPS:
                raise ValueError("عملية غير مسموحة في الدالة.")
            self._validate(node.operand)
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
                raise ValueError("دالة غير معروفة.")
            if len(node.args) != 1 or node.keywords:
                raise ValueError("عدد وسائط غير صحيح.")
            self._validate(node.args[0])
        elif isinstance(node, ast.Name):
            if node.id != self.var and node.id not in _ALLOWED_CONSTS:
                raise ValueError(f"رمز غير معروف: {node.id}")
        elif isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise ValueError("قيمة غير رقمية.")
        else:
            raise ValueError("تعبير غير مسموح في الدالة.")

    def _eval(self, node, x):
        if isinstance(node, ast.BinOp):
            return _BIN_OPS[type(node.op)](self._eval(node.left, x),
                                           self._eval(node.right, x))
        if isinstance(node, ast.UnaryOp):
            return _UNARY_OPS[type(node.op)](self._eval(node.operand, x))
        if isinstance(node, ast.Call):
            return _ALLOWED_FUNCS[node.func.id](self._eval(node.args[0], x))
        if isinstance(node, ast.Name):
            if node.id == self.var:
                return x
            return _ALLOWED_CONSTS[node.id]
        if isinstance(node, ast.Constant):
            return node.value
        raise ValueError("تعبير غير مسموح.")

    def __call__(self, x):
        """Evaluate f(x). Returns None where the function is undefined (domain
        errors, division by zero) so the caller can treat it as a gap/asymptote
        rather than crashing."""
        try:
            v = self._eval(self._tree.body, x)
            if isinstance(v, complex):
                return None
            if v != v or v in (float("inf"), float("-inf")):  # NaN / inf
                return None
            return float(v)
        except (ValueError, ZeroDivisionError, OverflowError):
            return None
