# -*- coding: utf-8 -*-
"""
abaAcademy.tools.sheet
======================

A small spreadsheet engine for the talking spreadsheet (الجدول الناطق):
the concepts a student meets in Excel — cells, references, ranges, formulas,
functions and recalculation — in a grid that is navigated and read by ear.

* Cells are addressed A1 … Z200. A value is a number, text, or a formula
  starting with ``=``.
* Formulas support + − × ÷ ^, comparisons, parentheses, cell references,
  ranges (``A1:B5``) and functions, in English or Arabic:
  SUM/مجموع، AVERAGE/متوسط، MIN/أصغر، MAX/أكبر، COUNT/عدد، ROUND/تقريب،
  ABS/مطلق، SQRT/جذر، IF/إذا، AND/و، OR/أو، NOT/ليس، POWER/أس، MOD/باقي،
  MEDIAN/وسيط، PRODUCT/جداء، COUNTIF/عد_إذا، SUMIF/مجموع_إذا، LEN/طول،
  CONCAT/دمج، UPPER، LOWER، INT/صحيح.
* Dependent cells recalculate automatically; circular references are
  detected and reported (#دوري) instead of looping.
* Errors follow spreadsheet conventions: #قسمة_على_صفر، #مرجع، #اسم، #قيمة.
* Sheets load from and save to CSV (UTF-8), and changes can be undone.
"""

from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

MAX_COLS = 26
MAX_ROWS = 200

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")


class SheetError(Exception):
    """A spreadsheet error value (shown in the cell, not raised to the user)."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.code = code
        self.detail = detail


ERROR_TEXT = {
    "#قسمة_على_صفر": "قسمة على صفر",
    "#مرجع": "مرجع إلى خانة غير موجودة",
    "#اسم": "دالّة أو اسم غير معروف",
    "#قيمة": "نوع قيمة غير مناسب (نصّ بدل رقم مثلًا)",
    "#دوري": "مرجع دائري: الخانة تعتمد على نفسها",
    "#صيغة": "خطأ في كتابة الصيغة",
}

Value = Union[float, str, bool, SheetError]


# ---------------------------------------------------------------------------
# addresses
# ---------------------------------------------------------------------------

def col_letter(c: int) -> str:
    return chr(ord("A") + c)


def addr(r: int, c: int) -> str:
    return f"{col_letter(c)}{r + 1}"


_ADDR = re.compile(r"^\$?([A-Za-z])\$?(\d{1,3})$")


def parse_addr(text: str) -> Tuple[int, int]:
    m = _ADDR.match(text.strip())
    if not m:
        raise ValueError(f"عنوان خانة غير صالح: {text}")
    c = ord(m.group(1).upper()) - ord("A")
    r = int(m.group(2)) - 1
    if not (0 <= r < MAX_ROWS and 0 <= c < MAX_COLS):
        raise ValueError(f"الخانة {text} خارج حدود الجدول.")
    return r, c


def range_cells(a: str, b: str) -> List[Tuple[int, int]]:
    r1, c1 = parse_addr(a)
    r2, c2 = parse_addr(b)
    return [(r, c) for r in range(min(r1, r2), max(r1, r2) + 1)
            for c in range(min(c1, c2), max(c1, c2) + 1)]


# ---------------------------------------------------------------------------
# tokenizer and parser
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"""
    \s*(?:
      (?P<num>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)
    | (?P<str>"[^"]*")
    | (?P<range>\$?[A-Za-z]\$?\d{1,3}:\$?[A-Za-z]\$?\d{1,3})
    | (?P<ref>\$?[A-Za-z]\$?\d{1,3}(?![\w؀-ۿ]))
    | (?P<name>[A-Za-z_؀-ۿ][\w؀-ۿ]*)
    | (?P<op><=|>=|<>|!=|[-+*/^%&=<>(),;×÷])
    )""", re.VERBOSE)


def tokenize(text: str) -> List[Tuple[str, str]]:
    t = text.translate(_AR_DIGITS).replace("،", ",").replace("؛", ";")
    pos, out = 0, []
    while pos < len(t):
        if t[pos].isspace():
            pos += 1
            continue
        m = _TOKEN.match(t, pos)
        if not m or m.end() == pos:
            raise SheetError("#صيغة", f"رمز غير متوقّع: {t[pos:pos + 10]}")
        kind = m.lastgroup
        val = m.group(kind)
        if kind == "op":
            val = {"×": "*", "÷": "/", ";": ",", "!=": "<>"}.get(val, val)
        out.append((kind, val))
        pos = m.end()
    return out


# AST node types: ("num", v) ("str", s) ("ref", r, c) ("range", cells)
# ("neg", x) ("bin", op, a, b) ("call", name, args) ("pct", x)

class _Parser:
    PREC = {"=": 1, "<>": 1, "<": 1, ">": 1, "<=": 1, ">=": 1, "&": 2,
            "+": 3, "-": 3, "*": 4, "/": 4, "^": 6}

    def __init__(self, tokens):
        self.t = tokens
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self):
        node = self.expr(0)
        if self.peek()[0] is not None:
            raise SheetError("#صيغة", f"رمز زائد: {self.peek()[1]}")
        return node

    def expr(self, min_prec):
        left = self.unary()
        while True:
            kind, val = self.peek()
            if kind != "op" or val not in self.PREC or self.PREC[val] < min_prec:
                return left
            self.take()
            prec = self.PREC[val]
            right = self.expr(prec if val == "^" else prec + 1)
            left = ("bin", val, left, right)

    def unary(self):
        kind, val = self.peek()
        if kind == "op" and val in "+-":
            self.take()
            node = self.unary()
            return ("neg", node) if val == "-" else node
        node = self.primary()
        k2, v2 = self.peek()
        if k2 == "op" and v2 == "%":
            self.take()
            node = ("pct", node)
        return node

    def primary(self):
        kind, val = self.take()
        if kind == "num":
            return ("num", float(val))
        if kind == "str":
            return ("str", val[1:-1])
        if kind == "ref":
            r, c = parse_addr(val.replace("$", ""))
            return ("ref", r, c)
        if kind == "range":
            a, b = val.replace("$", "").split(":")
            return ("range", range_cells(a, b))
        if kind == "name":
            k2, v2 = self.peek()
            if k2 == "op" and v2 == "(":
                self.take()
                args = []
                if self.peek() != ("op", ")"):
                    while True:
                        args.append(self.expr(0))
                        k3, v3 = self.take()
                        if v3 == ")":
                            break
                        if v3 != ",":
                            raise SheetError("#صيغة", "توقّعت فاصلة أو قوسًا")
                else:
                    self.take()
                return ("call", val, args)
            low = val.lower()
            if low in ("true", "صح"):
                return ("bool", True)
            if low in ("false", "خطأ"):
                return ("bool", False)
            raise SheetError("#اسم", val)
        if kind == "op" and val == "(":
            node = self.expr(0)
            if self.take() != ("op", ")"):
                raise SheetError("#صيغة", "قوس غير مغلق")
            return node
        raise SheetError("#صيغة", f"لم أتوقّع {val}")


def parse_formula(text: str):
    body = text[1:] if text.startswith("=") else text
    if not body.strip():
        raise SheetError("#صيغة", "صيغة فارغة")
    return _Parser(tokenize(body)).parse()


def references(node) -> Set[Tuple[int, int]]:
    out: Set[Tuple[int, int]] = set()

    def walk(n):
        k = n[0]
        if k == "ref":
            out.add((n[1], n[2]))
        elif k == "range":
            out.update(n[1])
        elif k in ("neg", "pct"):
            walk(n[1])
        elif k == "bin":
            walk(n[2])
            walk(n[3])
        elif k == "call":
            for a in n[2]:
                walk(a)
    walk(node)
    return out


# ---------------------------------------------------------------------------
# functions
# ---------------------------------------------------------------------------

def _nums(values) -> List[float]:
    out = []
    for v in values:
        if isinstance(v, SheetError):
            raise v
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            out.append(float(v))
    return out


def _num(v) -> float:
    if isinstance(v, SheetError):
        raise v
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if v == "" or v is None:
        return 0.0
    try:
        return float(str(v).translate(_AR_DIGITS))
    except ValueError:
        raise SheetError("#قيمة", f"{v} ليس رقمًا")


def _truth(v) -> bool:
    if isinstance(v, SheetError):
        raise v
    if isinstance(v, str):
        return v != ""
    return bool(v)


def _criterion(crit) -> Callable[[Value], bool]:
    """COUNTIF-style criterion: 5, ">5", "<>0", "نعم"."""
    if isinstance(crit, (int, float)) and not isinstance(crit, bool):
        return lambda v: isinstance(v, (int, float)) and float(v) == float(crit)
    s = str(crit)
    for op in ("<=", ">=", "<>", "<", ">", "="):
        if s.startswith(op):
            rest = s[len(op):]
            try:
                x = float(rest.translate(_AR_DIGITS))
            except ValueError:
                return (lambda v, r=rest: (str(v) == r)) if op == "=" else \
                    (lambda v, r=rest: (str(v) != r)) if op == "<>" else (lambda v: False)
            def cmp(v, op=op, x=x):
                if not isinstance(v, (int, float)) or isinstance(v, bool):
                    return op == "<>"
                v = float(v)
                return {"<=": v <= x, ">=": v >= x, "<>": v != x, "<": v < x,
                        ">": v > x, "=": v == x}[op]
            return cmp
    return lambda v: str(v) == s


def _round(args):
    x = _num(args[0])
    d = int(_num(args[1])) if len(args) > 1 else 0
    q = 10 ** d
    return math.floor(abs(x) * q + 0.5) / q * (1 if x >= 0 else -1)


def _median(xs):
    if not xs:
        raise SheetError("#قيمة", "لا أرقام")
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


FUNCTIONS: Dict[str, Tuple[str, Callable]] = {}


def _register(names, desc, fn):
    for n in names:
        FUNCTIONS[n.lower()] = (desc, fn)


_register(("SUM", "مجموع"), "مجموع الأرقام", lambda a, flat: sum(_nums(flat)))
_register(("AVERAGE", "متوسط"), "الوسط الحسابي",
          lambda a, flat: (lambda xs: sum(xs) / len(xs) if xs else (_ for _ in ()).throw(
              SheetError("#قسمة_على_صفر", "لا أرقام")))(_nums(flat)))
_register(("MIN", "أصغر"), "أصغر قيمة", lambda a, flat: min(_nums(flat)) if _nums(flat) else 0.0)
_register(("MAX", "أكبر"), "أكبر قيمة", lambda a, flat: max(_nums(flat)) if _nums(flat) else 0.0)
_register(("COUNT", "عدد"), "عدد الخانات الرقمية", lambda a, flat: float(len(_nums(flat))))
_register(("COUNTA", "عدد_الكل"), "عدد الخانات غير الفارغة",
          lambda a, flat: float(sum(1 for v in flat if v != "" and v is not None)))
_register(("MEDIAN", "وسيط"), "الوسيط", lambda a, flat: _median(_nums(flat)))
_register(("PRODUCT", "جداء"), "حاصل الضرب", lambda a, flat: math.prod(_nums(flat)) if _nums(flat) else 0.0)
_register(("ROUND", "تقريب"), "تقريب إلى عدد من المنازل", lambda a, flat: _round(a))
_register(("INT", "صحيح"), "الجزء الصحيح", lambda a, flat: float(math.floor(_num(a[0]))))
_register(("ABS", "مطلق"), "القيمة المطلقة", lambda a, flat: abs(_num(a[0])))
_register(("SQRT", "جذر"), "الجذر التربيعي",
          lambda a, flat: math.sqrt(_num(a[0])) if _num(a[0]) >= 0 else (_ for _ in ()).throw(
              SheetError("#قيمة", "جذر عدد سالب")))
_register(("POWER", "أس"), "رفع إلى أس", lambda a, flat: _num(a[0]) ** _num(a[1]))
_register(("MOD", "باقي"), "باقي القسمة",
          lambda a, flat: math.fmod(_num(a[0]), _num(a[1])) if _num(a[1]) else (_ for _ in ()).throw(
              SheetError("#قسمة_على_صفر")))
_register(("IF", "إذا"), "إذا تحقّق الشرط فالأولى وإلا فالثانية",
          lambda a, flat: a[1] if _truth(a[0]) else (a[2] if len(a) > 2 else False))
_register(("AND", "و"), "كلّها صحيحة", lambda a, flat: all(_truth(v) for v in flat))
_register(("OR", "أو"), "إحداها صحيحة", lambda a, flat: any(_truth(v) for v in flat))
_register(("NOT", "ليس"), "النفي", lambda a, flat: not _truth(a[0]))
_register(("LEN", "طول"), "عدد حروف النصّ", lambda a, flat: float(len(_text(a[0]))))
_register(("CONCAT", "CONCATENATE", "دمج"), "دمج النصوص", lambda a, flat: "".join(_text(v) for v in flat))
_register(("UPPER",), "أحرف كبيرة", lambda a, flat: _text(a[0]).upper())
_register(("LOWER",), "أحرف صغيرة", lambda a, flat: _text(a[0]).lower())
_register(("PI", "باي"), "النسبة التقريبية", lambda a, flat: math.pi)


def _countif(rng, crit):
    test = _criterion(crit)
    return float(sum(1 for v in rng if test(v)))


def _sumif(rng, crit, sum_rng=None):
    test = _criterion(crit)
    target = sum_rng if sum_rng is not None else rng
    total = 0.0
    for v, s in zip(rng, target):
        if test(v) and isinstance(s, (int, float)) and not isinstance(s, bool):
            total += float(s)
    return total


def _text(v) -> str:
    if isinstance(v, SheetError):
        raise v
    if isinstance(v, bool):
        return "صح" if v else "خطأ"
    if isinstance(v, float):
        return format_number(v)
    return "" if v is None else str(v)


def format_number(x: float) -> str:
    if math.isnan(x) or math.isinf(x):
        return "#قيمة"
    if abs(x - round(x)) < 1e-9 and abs(x) < 1e15:
        return str(int(round(x)))
    return f"{x:.6f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# the sheet
# ---------------------------------------------------------------------------

@dataclass
class Cell:
    raw: str = ""
    value: Value = ""
    node: object = None
    deps: Set[Tuple[int, int]] = field(default_factory=set)


class Sheet:
    def __init__(self, rows: int = 50, cols: int = 10):
        self.rows = max(1, min(MAX_ROWS, rows))
        self.cols = max(1, min(MAX_COLS, cols))
        self.cells: Dict[Tuple[int, int], Cell] = {}
        self._history: List[List[Tuple[Tuple[int, int], str]]] = []

    # -- reading -----------------------------------------------------------
    def raw(self, r: int, c: int) -> str:
        cell = self.cells.get((r, c))
        return cell.raw if cell else ""

    def value(self, r: int, c: int) -> Value:
        cell = self.cells.get((r, c))
        return cell.value if cell else ""

    def display(self, r: int, c: int) -> str:
        v = self.value(r, c)
        if isinstance(v, SheetError):
            return v.code
        return _text(v)

    def describe(self, r: int, c: int) -> str:
        raw = self.raw(r, c)
        name = addr(r, c)
        if not raw:
            return f"{name}: فارغة"
        shown = self.display(r, c)
        if raw.startswith("="):
            v = self.value(r, c)
            extra = f" ({ERROR_TEXT.get(v.code, '')})" if isinstance(v, SheetError) else ""
            return f"{name}: {shown}{extra}، الصيغة {raw}"
        return f"{name}: {shown}"

    # -- writing ---------------------------------------------------------
    def set(self, r: int, c: int, raw: str, record: bool = True) -> None:
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            raise ValueError("خارج حدود الجدول.")
        raw = (raw or "").strip()
        if record:
            self._history.append([((r, c), self.raw(r, c))])
            if len(self._history) > 200:
                self._history.pop(0)
        if not raw:
            self.cells.pop((r, c), None)
        else:
            cell = Cell(raw)
            if raw.startswith("="):
                try:
                    cell.node = parse_formula(raw)
                    cell.deps = references(cell.node)
                except SheetError as e:
                    cell.node = e
                except ValueError as e:
                    cell.node = SheetError("#مرجع", str(e))
            self.cells[(r, c)] = cell
        self.recalculate()

    def set_many(self, items: Sequence[Tuple[int, int, str]]) -> None:
        batch = [((r, c), self.raw(r, c)) for r, c, _ in items]
        self._history.append(batch)
        for r, c, raw in items:
            self.set(r, c, raw, record=False)

    def undo(self) -> bool:
        if not self._history:
            return False
        batch = self._history.pop()
        for (r, c), raw in reversed(batch):
            self.set(r, c, raw, record=False)
        return True

    def clear(self) -> None:
        self.cells.clear()
        self._history.clear()

    # -- evaluation ------------------------------------------------------
    def recalculate(self) -> None:
        state: Dict[Tuple[int, int], int] = {}      # 1 = visiting, 2 = done

        def literal(raw: str) -> Value:
            t = raw.translate(_AR_DIGITS).replace(",", "")
            try:
                return float(t)
            except ValueError:
                if t.endswith("%"):
                    try:
                        return float(t[:-1]) / 100.0
                    except ValueError:
                        pass
                return raw

        def ev(key) -> Value:
            cell = self.cells.get(key)
            if cell is None:
                return ""
            st = state.get(key)
            if st == 2:
                return cell.value
            if st == 1:
                raise SheetError("#دوري")
            state[key] = 1
            try:
                if cell.node is None:
                    cell.value = literal(cell.raw)
                elif isinstance(cell.node, SheetError):
                    cell.value = cell.node
                else:
                    try:
                        cell.value = self._eval(cell.node, ev)
                    except SheetError as e:
                        cell.value = e
                    except ZeroDivisionError:
                        cell.value = SheetError("#قسمة_على_صفر")
                    except (OverflowError, ValueError):
                        cell.value = SheetError("#قيمة")
            finally:
                state[key] = 2
            if isinstance(cell.value, SheetError) and cell.value.code == "#دوري":
                pass
            return cell.value

        for key in list(self.cells):
            try:
                ev(key)
            except SheetError as e:
                self.cells[key].value = e
                state[key] = 2

    def _eval(self, node, ev) -> Value:
        k = node[0]
        if k == "num":
            return node[1]
        if k in ("str", "bool"):
            return node[1]
        if k == "ref":
            if not (node[1] < self.rows and node[2] < self.cols):
                raise SheetError("#مرجع")
            v = ev((node[1], node[2]))
            if isinstance(v, SheetError):
                raise v
            return v
        if k == "range":
            raise SheetError("#قيمة", "استعمل النطاق داخل دالّة مثل مجموع")
        if k == "neg":
            return -_num(self._eval(node[1], ev))
        if k == "pct":
            return _num(self._eval(node[1], ev)) / 100.0
        if k == "bin":
            op = node[1]
            a = self._eval(node[2], ev)
            b = self._eval(node[3], ev)
            if op == "&":
                return _text(a) + _text(b)
            if op in ("=", "<>", "<", ">", "<=", ">="):
                if isinstance(a, str) or isinstance(b, str):
                    x, y = _text(a), _text(b)
                else:
                    x, y = _num(a), _num(b)
                return {"=": x == y, "<>": x != y, "<": x < y, ">": x > y,
                        "<=": x <= y, ">=": x >= y}[op]
            x, y = _num(a), _num(b)
            if op == "+":
                return x + y
            if op == "-":
                return x - y
            if op == "*":
                return x * y
            if op == "/":
                if y == 0:
                    raise SheetError("#قسمة_على_صفر")
                return x / y
            if op == "^":
                return x ** y
        if k == "call":
            name = node[1].lower()
            if name in ("countif", "عد_إذا"):
                if len(node[2]) != 2:
                    raise SheetError("#قيمة", "عد_إذا يحتاج نطاقًا وشرطًا")
                return _countif(self._range_values(node[2][0], ev), self._eval(node[2][1], ev))
            if name in ("sumif", "مجموع_إذا"):
                if len(node[2]) not in (2, 3):
                    raise SheetError("#قيمة")
                rng = self._range_values(node[2][0], ev)
                crit = self._eval(node[2][1], ev)
                srng = self._range_values(node[2][2], ev) if len(node[2]) == 3 else None
                return _sumif(rng, crit, srng)
            if name in ("if", "إذا"):
                if len(node[2]) < 2:
                    raise SheetError("#قيمة", "إذا يحتاج شرطًا وقيمة")
                cond = self._eval(node[2][0], ev)
                pick = node[2][1] if _truth(cond) else (node[2][2] if len(node[2]) > 2 else None)
                return False if pick is None else self._eval(pick, ev)
            if name not in FUNCTIONS:
                raise SheetError("#اسم", node[1])
            args, flat = [], []
            for a in node[2]:
                if a[0] == "range":
                    vals = self._range_values(a, ev)
                    flat.extend(vals)
                    args.append(vals)
                else:
                    v = self._eval(a, ev)
                    flat.append(v)
                    args.append(v)
            return FUNCTIONS[name][1](args, flat)
        raise SheetError("#صيغة")

    def _range_values(self, node, ev) -> List[Value]:
        if node[0] == "range":
            out = []
            for (r, c) in node[1]:
                v = ev((r, c))
                if isinstance(v, SheetError):
                    raise v
                out.append(v)
            return out
        return [self._eval(node, ev)]

    # -- bulk -------------------------------------------------------------
    def used_bounds(self) -> Tuple[int, int]:
        if not self.cells:
            return 0, 0
        return (max(r for r, _ in self.cells) + 1, max(c for _, c in self.cells) + 1)

    def row_text(self, r: int) -> str:
        _, cols = self.used_bounds()
        parts = []
        for c in range(max(cols, 1)):
            d = self.display(r, c)
            parts.append(f"{col_letter(c)}: {d or 'فارغة'}")
        return f"الصفّ {r + 1}: " + "، ".join(parts)

    def column_text(self, c: int) -> str:
        rows, _ = self.used_bounds()
        parts = []
        for r in range(max(rows, 1)):
            d = self.display(r, c)
            if d:
                parts.append(f"{r + 1}: {d}")
        return f"العمود {col_letter(c)}: " + ("، ".join(parts) or "فارغ")

    def to_csv(self, values: bool = False) -> str:
        rows, cols = self.used_bounds()
        buf = io.StringIO()
        w = csv.writer(buf)
        for r in range(rows):
            w.writerow([(self.display(r, c) if values else self.raw(r, c)) for c in range(cols)])
        return buf.getvalue()

    def load_csv(self, text: str) -> int:
        self.clear()
        reader = csv.reader(io.StringIO(text))
        n = 0
        for r, row in enumerate(reader):
            if r >= self.rows:
                break
            for c, raw in enumerate(row[:self.cols]):
                if raw.strip():
                    cell = Cell(raw.strip())
                    if cell.raw.startswith("="):
                        try:
                            cell.node = parse_formula(cell.raw)
                            cell.deps = references(cell.node)
                        except SheetError as e:
                            cell.node = e
                        except ValueError as e:
                            cell.node = SheetError("#مرجع", str(e))
                    self.cells[(r, c)] = cell
                    n += 1
        self.recalculate()
        return n

    def dependents(self, r: int, c: int) -> List[str]:
        """Cells whose formulas use this one (Excel's trace dependents)."""
        return sorted((addr(k[0], k[1]) for k, cell in self.cells.items() if (r, c) in cell.deps),
                      key=lambda a: (len(a), a))

    def fill_down(self, r: int, c: int, count: int) -> int:
        """Copy a cell's formula into the cells below, shifting relative row
        references the way spreadsheet fill-down does."""
        raw = self.raw(r, c)
        if not raw:
            return 0
        items = []
        for k in range(1, count + 1):
            if r + k >= self.rows:
                break
            items.append((r + k, c, shift_rows(raw, k)))
        if items:
            self.set_many(items)
        return len(items)


_REF_IN_FORMULA = re.compile(r'("[^"]*")|(\$?)([A-Za-z])(\$?)(\d{1,3})(?![\w؀-ۿ(])')


def shift_rows(raw: str, k: int) -> str:
    if not raw.startswith("="):
        return raw

    def rep(m):
        if m.group(1):
            return m.group(1)
        dollar_c, col, dollar_r, row = m.group(2), m.group(3), m.group(4), m.group(5)
        if dollar_r:
            return m.group(0)
        return f"{dollar_c}{col}{int(row) + k}"
    return _REF_IN_FORMULA.sub(rep, raw)


FUNCTION_HELP = [
    ("مجموع(A1:A5) أو SUM", "مجموع الأرقام"), ("متوسط(A1:A5) أو AVERAGE", "الوسط الحسابي"),
    ("أصغر / أكبر", "أصغر قيمة وأكبرها"), ("عدد(A1:A9)", "عدد الخانات التي فيها أرقام"),
    ("تقريب(A1، 2)", "تقريب إلى منزلتين"), ("إذا(A1>=50، \"ناجح\"، \"راسب\")", "اختيار بحسب شرط"),
    ("عد_إذا(A1:A9، \">=50\")", "عدد الخانات المحقّقة للشرط"),
    ("مجموع_إذا(A1:A9، \">0\")", "مجموع ما يحقّق الشرط"), ("وسيط", "الوسيط"),
    ("جذر(16)، أس(2، 3)، باقي(7، 2)، مطلق(-3)", "دوالّ رياضية"),
    ("دمج(A1، \" \"، B1) أو A1&B1", "دمج النصوص"), ("طول(A1)", "عدد الحروف"),
]
