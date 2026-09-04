# -*- coding: utf-8 -*-
"""
abaAcademy.math_engine.latex_arabic
===================================

Convert mathematical notation (a practical subset of LaTeX) into natural, spoken
Arabic — so a blind learner hears "كسرٌ بسطه واحد ومقامه اثنان" instead of a
screen reader spelling out backslashes and braces.

Design notes and honest scope
------------------------------
This is a real, working recursive parser for the LaTeX constructs that show up in
school and early-university math: fractions, roots, powers and subscripts, sums
and integrals with bounds, common functions, Greek letters, operators, and
grouped sub-expressions. It is NOT a full LaTeX engine (LaTeX is Turing-complete
and enormous); anything it does not recognise is read out token by token in
Arabic rather than silently dropped, so the learner always hears *something*
faithful.

The converter is deterministic and fully offline — no model, no network — so its
output is predictable and testable, which matters for a tool students rely on.
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# vocabulary
# ---------------------------------------------------------------------------

_DIGITS_AR = {
    "0": "صفر", "1": "واحد", "2": "اثنان", "3": "ثلاثة", "4": "أربعة",
    "5": "خمسة", "6": "ستة", "7": "سبعة", "8": "ثمانية", "9": "تسعة",
}

_GREEK = {
    "alpha": "ألفا", "beta": "بيتا", "gamma": "غاما", "delta": "دلتا",
    "epsilon": "إبسيلون", "zeta": "زيتا", "eta": "إيتا", "theta": "ثيتا",
    "iota": "أيوتا", "kappa": "كابا", "lambda": "لامبدا", "mu": "مو",
    "nu": "نو", "xi": "كسي", "pi": "باي", "rho": "رو", "sigma": "سيغما",
    "tau": "تاو", "phi": "فاي", "chi": "خي", "psi": "بسي", "omega": "أوميغا",
    "Delta": "دلتا الكبيرة", "Sigma": "سيغما الكبيرة", "Omega": "أوميغا الكبيرة",
    "Pi": "باي الكبيرة", "Theta": "ثيتا الكبيرة", "Phi": "فاي الكبيرة",
    "Gamma": "غاما الكبيرة", "Lambda": "لامبدا الكبيرة",
}

_FUNCS = {
    "sin": "جا", "cos": "جتا", "tan": "ظا", "cot": "ظتا", "sec": "قا",
    "csc": "قتا", "sinh": "جا زائدي", "cosh": "جتا زائدي", "tanh": "ظا زائدي",
    "log": "لوغاريتم", "ln": "لوغاريتم طبيعي", "lg": "لوغاريتم عشري",
    "exp": "أُس", "arcsin": "قوس الجا", "arccos": "قوس الجتا",
    "arctan": "قوس الظا", "lim": "نهاية", "det": "محدد", "gcd": "القاسم المشترك",
    "min": "الأدنى", "max": "الأعلى",
}

# multi-character LaTeX symbol commands -> spoken Arabic
_SYMBOLS = {
    "times": "في", "cdot": "في", "div": "على", "pm": "زائد أو ناقص",
    "mp": "ناقص أو زائد", "leq": "أصغر من أو يساوي", "geq": "أكبر من أو يساوي",
    "neq": "لا يساوي", "approx": "يقارب", "equiv": "يكافئ", "to": "يؤول إلى",
    "rightarrow": "يؤول إلى", "infty": "ما لا نهاية", "partial": "مشتقة جزئية",
    "nabla": "نابلا", "forall": "لكل", "exists": "يوجد", "in": "ينتمي إلى",
    "notin": "لا ينتمي إلى", "subset": "مجموعة جزئية من", "cup": "اتحاد",
    "cap": "تقاطع", "emptyset": "المجموعة الخالية", "angle": "زاوية",
    "perp": "عمودي على", "parallel": "يوازي", "degree": "درجة",
    "prime": "شرطة", "circ": "دائرة", "cdots": "إلى آخره", "ldots": "إلى آخره",
    "dots": "إلى آخره", "le": "أصغر من أو يساوي", "ge": "أكبر من أو يساوي",
    "ne": "لا يساوي", "sum": "مجموع", "prod": "جداء", "int": "تكامل",
    "sqrt": "جذر", "frac": "كسر", "left": "", "right": "", "quad": " ",
    "qquad": " ", "mathbb": "", "mathbf": "", "mathrm": "", "text": "",
}

_OPERATORS = {
    "+": "زائد", "-": "ناقص", "*": "في", "/": "على", "=": "يساوي",
    "<": "أصغر من", ">": "أكبر من", "(": "قوس فتح", ")": "قوس إغلاق",
    "[": "قوس مربع فتح", "]": "قوس مربع إغلاق", "|": "قيمة مطلقة",
    ",": "،", ".": "نقطة", "!": "مضروب", ":": "نسبة",
}


class _Tokenizer:
    """Split a LaTeX string into a flat token stream we can parse."""

    def __init__(self, text):
        self.text = text
        self.i = 0
        self.n = len(text)

    def tokens(self):
        out = []
        while self.i < self.n:
            c = self.text[self.i]
            if c.isspace():
                self.i += 1
                continue
            if c == "\\":
                out.append(("cmd", self._command()))
            elif c in "{}":
                out.append(("brace", c))
                self.i += 1
            elif c == "^":
                out.append(("sup", c)); self.i += 1
            elif c == "_":
                out.append(("sub", c)); self.i += 1
            elif c.isdigit():
                out.append(("num", self._number()))
            elif c.isalpha():
                out.append(("var", c)); self.i += 1
            else:
                out.append(("op", c)); self.i += 1
        return out

    def _command(self):
        # read \name (letters) or a single non-letter escaped char
        self.i += 1  # skip backslash
        if self.i < self.n and self.text[self.i].isalpha():
            start = self.i
            while self.i < self.n and self.text[self.i].isalpha():
                self.i += 1
            return self.text[start:self.i]
        else:
            ch = self.text[self.i] if self.i < self.n else ""
            self.i += 1
            return ch

    def _number(self):
        start = self.i
        while self.i < self.n and (self.text[self.i].isdigit() or self.text[self.i] == "."):
            self.i += 1
        return self.text[start:self.i]


class LatexToArabic:
    """Recursive converter. Public entry point: :meth:`speak`."""

    def speak(self, latex):
        """Return spoken-Arabic text for a LaTeX string. Never raises on odd
        input — falls back to reading tokens literally."""
        if latex is None:
            return ""
        latex = latex.strip()
        if not latex:
            return ""
        try:
            toks = _Tokenizer(latex).tokens()
            self._toks = toks
            self._pos = 0
            parts = []
            while self._pos < len(toks):
                parts.append(self._one())
            return self._join(parts)
        except Exception:
            # defensive: never let a parsing bug silence the reader
            return self._literal_fallback(latex)

    # -- core recursive reader -------------------------------------------
    def _one(self):
        """Read a single logical unit (atom + any following ^ or _)."""
        atom = self._atom()
        # attach superscript / subscript that follow
        while self._peek_type() in ("sup", "sub"):
            kind = self._toks[self._pos][0]
            self._pos += 1
            operand = self._group_or_atom()
            if kind == "sup":
                atom = self._apply_power(atom, operand)
            else:
                atom = f"{atom} تحت {operand}"
        return atom

    def _atom(self):
        t = self._toks[self._pos]
        typ, val = t
        self._pos += 1
        if typ == "cmd":
            return self._command(val)
        if typ == "brace":
            if val == "{":
                return self._until_close()
            return ""       # stray close brace
        if typ == "num":
            return self._number_word(val)
        if typ == "var":
            return val      # single latin letter: read as-is
        if typ == "op":
            return _OPERATORS.get(val, val)
        if typ in ("sup", "sub"):
            # a lone ^ or _ with no preceding atom: read the operand
            operand = self._group_or_atom()
            return ("أُس " if typ == "sup" else "تحت ") + operand
        return val

    def _command(self, name):
        # structural commands
        if name == "frac":
            num = self._group_or_atom()
            den = self._group_or_atom()
            return f"كسرٌ بسطه {num} ومقامه {den}، انتهى الكسر"
        if name == "sqrt":
            # optional [n] for nth root
            index = None
            if self._peek_is_op("["):
                self._pos += 1
                index = self._until_char("]")
            body = self._group_or_atom()
            if index:
                return f"الجذر النوني من الدرجة {index} لـ {body}"
            return f"الجذر التربيعي لـ {body}"
        if name in ("sum", "prod", "int"):
            return self._big_operator(name)
        if name in ("left", "right"):
            # delimiter markers — read the delimiter that follows if any
            if self._peek_type() == "op":
                d = self._toks[self._pos][1]
                self._pos += 1
                return _OPERATORS.get(d, "")
            return ""
        if name in ("mathbb", "mathbf", "mathrm", "text"):
            return self._group_or_atom()   # just read the content
        if name in _FUNCS:
            return _FUNCS[name]
        if name in _GREEK:
            return _GREEK[name]
        if name in _SYMBOLS:
            return _SYMBOLS[name]
        # unknown command: read its name literally so nothing is lost
        return name

    def _big_operator(self, name):
        word = {"sum": "مجموع", "prod": "جداء", "int": "تكامل"}[name]
        lower = upper = None
        # bounds may come as _{...} ^{...} in any order
        for _ in range(2):
            if self._peek_type() == "sub":
                self._pos += 1
                lower = self._group_or_atom()
            elif self._peek_type() == "sup":
                self._pos += 1
                upper = self._group_or_atom()
        phrase = word
        if name == "int":
            if lower and upper:
                phrase += f" من {lower} إلى {upper}"
            body = self._one()
            return f"{phrase} لـ {body}"
        # sum / product
        if lower:
            phrase += f" حيث {lower}"
        if upper:
            phrase += f" إلى {upper}"
        body = self._one()
        return f"{phrase} لـ {body}"

    # -- helpers ----------------------------------------------------------
    def _apply_power(self, base, exp):
        # nice phrasing for the common squared / cubed (exponent may be the digit
        # "2"/"3" or the spelled word, depending on how it was written)
        e = exp.strip()
        if e in ("2", "اثنان"):
            return f"{base} تربيع"
        if e in ("3", "ثلاثة"):
            return f"{base} تكعيب"
        return f"{base} أُس {exp}"

    def _group_or_atom(self):
        if self._peek_is_brace("{"):
            self._pos += 1           # consume {
            return self._until_close()
        if self._pos < len(self._toks):
            return self._one()
        return ""

    def _until_close(self):
        parts = []
        depth = 1
        while self._pos < len(self._toks):
            typ, val = self._toks[self._pos]
            if typ == "brace" and val == "{":
                depth += 1
            elif typ == "brace" and val == "}":
                depth -= 1
                if depth == 0:
                    self._pos += 1
                    break
            parts.append(self._one())
        return self._join(parts)

    def _until_char(self, ch):
        parts = []
        while self._pos < len(self._toks):
            typ, val = self._toks[self._pos]
            if typ == "op" and val == ch:
                self._pos += 1
                break
            parts.append(self._one())
        return self._join(parts)

    def _number_word(self, s):
        # read a multi-digit number as the number itself (engines speak digits in
        # Arabic); keep decimals natural
        if "." in s:
            whole, frac = s.split(".", 1)
            return f"{whole} فاصلة {' '.join(_DIGITS_AR.get(d, d) for d in frac)}"
        return s

    def _peek_type(self):
        return self._toks[self._pos][0] if self._pos < len(self._toks) else None

    def _peek_is_brace(self, which):
        return (self._pos < len(self._toks)
                and self._toks[self._pos] == ("brace", which))

    def _peek_is_op(self, ch):
        return (self._pos < len(self._toks)
                and self._toks[self._pos][0] == "op"
                and self._toks[self._pos][1] == ch)

    def _join(self, parts):
        return " ".join(p for p in parts if p is not None and str(p).strip())

    def _literal_fallback(self, latex):
        out = []
        for ch in latex:
            if ch in _OPERATORS:
                out.append(_OPERATORS[ch])
            elif ch == "\\":
                continue
            elif ch.strip():
                out.append(ch)
        return " ".join(out)


# module-level convenience
_converter = LatexToArabic()


def latex_to_arabic(latex):
    """Convenience wrapper: LaTeX string -> spoken Arabic string."""
    return _converter.speak(latex)


def mathml_to_arabic(mathml):
    """Best-effort MathML -> Arabic by converting the common presentation tags
    to an equivalent LaTeX string, then reusing the LaTeX path. Handles the
    frequent tags (mfrac, msqrt, msup, msub, mo, mi, mn, mrow). Unknown tags are
    flattened to their text so nothing is dropped."""
    if not mathml:
        return ""
    try:
        import xml.etree.ElementTree as ET
        # strip namespaces for simpler matching
        cleaned = re.sub(r'xmlns="[^"]+"', "", mathml)
        cleaned = re.sub(r"<(/?)\w+:", r"<\1", cleaned)
        root = ET.fromstring(cleaned)
        latex = _mathml_node_to_latex(root)
        return latex_to_arabic(latex)
    except Exception:
        # fall back to reading any text content
        text = re.sub(r"<[^>]+>", " ", mathml)
        return latex_to_arabic(text.strip())


def _mathml_node_to_latex(node):
    tag = node.tag.lower()
    children = list(node)
    if tag in ("math", "mrow", "mstyle", "mpadded"):
        return " ".join(_mathml_node_to_latex(c) for c in children)
    if tag in ("mi", "mn", "mo", "mtext"):
        return (node.text or "").strip()
    if tag == "mfrac" and len(children) == 2:
        return ("\\frac{" + _mathml_node_to_latex(children[0]) + "}{"
                + _mathml_node_to_latex(children[1]) + "}")
    if tag == "msqrt":
        return "\\sqrt{" + " ".join(_mathml_node_to_latex(c) for c in children) + "}"
    if tag == "mroot" and len(children) == 2:
        return ("\\sqrt[" + _mathml_node_to_latex(children[1]) + "]{"
                + _mathml_node_to_latex(children[0]) + "}")
    if tag == "msup" and len(children) == 2:
        return (_mathml_node_to_latex(children[0]) + "^{"
                + _mathml_node_to_latex(children[1]) + "}")
    if tag == "msub" and len(children) == 2:
        return (_mathml_node_to_latex(children[0]) + "_{"
                + _mathml_node_to_latex(children[1]) + "}")
    if tag == "msubsup" and len(children) == 3:
        return (_mathml_node_to_latex(children[0]) + "_{"
                + _mathml_node_to_latex(children[1]) + "}^{"
                + _mathml_node_to_latex(children[2]) + "}")
    # unknown: flatten text
    return " ".join(_mathml_node_to_latex(c) for c in children) or (node.text or "")
