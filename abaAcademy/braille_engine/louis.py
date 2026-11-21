# -*- coding: utf-8 -*-
"""
abaAcademy.braille_engine.louis
===============================

A small interpreter for the liblouis Arabic braille tables, so the academy
can translate any Arabic text to grade 1 (uncontracted) or grade 2
(contracted) braille, and braille back to text, without the C library.

The tables themselves ship unchanged in resources/braille/liblouis
(ar-ar-g1.utb, ar-ar-g2.ctb and the files they include), from the liblouis
project (https://liblouis.io), LGPL-2.1-or-later; see COPYING.LESSER there.

Supported opcodes are the ones these tables use: character definitions
(letter, sign, punctuation, math, digit, litdigit, space…), the number sign,
and the translation rules always, word, lowword, partword, sufword,
begword, begmidword, midword, midendword and endword, with the noback /
nofor direction prefixes. Rules are applied longest-match first at each
position, as liblouis does. ``match`` rules and emphasis are not interpreted;
the characters they cover still translate through the character
definitions.

Output is Unicode braille (U+2800…), one cell per character, which braille
displays and the academy's dot reader both understand. ``to_brf`` gives the
same cells as North American ASCII braille for embossers (.brf files).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
TABLES = os.path.join(HERE, "..", "resources", "braille", "liblouis")

CHAR_OPCODES = {"letter", "lowercase", "uppercase", "sign", "punctuation", "math", "digit", "litdigit",
                "space", "lowword_char", "base"}
RULE_OPCODES = {"always", "word", "lowword", "partword", "sufword", "begword", "begmidword", "midword",
                "midendword", "endword", "prepunc", "postpunc", "contraction"}
SKIP_OPCODES = {"display", "emphclass", "match", "hyphen", "decpoint", "midnum", "endnum", "begnum",
                "numericnocontchars", "numericmodechars", "nonumsign", "nocontractsign", "noletsign",
                "noletsignafter", "capsletter", "begcapsword", "endcapsword", "multind", "undefined",
                "grouping", "repeated", "repword", "attribute", "class", "seqdelimiter", "seqbeforechars",
                "seqafterchars", "seqafterpattern", "correct", "pass2", "pass3", "pass4", "context",
                "swapcd", "swapdd", "swapcc", "locale", "uplow", "litdigit_", "exactdots", "comp6", "compbrl"}


def _unescape(s: str) -> str:
    def rep(m):
        return chr(int(m.group(1), 16))
    s = re.sub(r"\\x([0-9a-fA-F]{4})", rep, s)
    s = re.sub(r"\\y([0-9a-fA-F]{5})", rep, s)
    return s.replace("\\s", " ").replace("\\t", "\t").replace("\\\\", "\\")


def dots_to_cells(dots: str) -> str:
    """'1245-12' -> two Unicode braille cells. '0' is a blank cell."""
    out = []
    for part in dots.split("-"):
        if not part:
            continue
        if all(0x2800 <= ord(c) <= 0x28FF for c in part):
            out.append(part)
            continue
        code = 0
        for d in part:
            if d == "0":
                continue
            n = int(d, 16) if d in "0123456789abcdef" else 0
            if 1 <= n <= 8:
                code |= 1 << (n - 1)
        out.append(chr(0x2800 + code))
    return "".join(out)


def cell_dots(cell: str) -> str:
    """Dot numbers of one Unicode braille cell, e.g. '⠃' -> '12'."""
    code = ord(cell) - 0x2800
    return "".join(str(i + 1) for i in range(8) if code & (1 << i)) or "0"


@dataclass
class Rule:
    opcode: str
    chars: str
    cells: str
    forward: bool = True
    backward: bool = True


@dataclass
class Table:
    chars: Dict[str, str] = field(default_factory=dict)        # char -> cells
    char_kind: Dict[str, str] = field(default_factory=dict)    # char -> opcode
    digits: Dict[str, str] = field(default_factory=dict)       # digit -> litdigit cells
    rules: List[Rule] = field(default_factory=list)
    numsign: str = ""
    loaded: List[str] = field(default_factory=list)

    # -- loading -----------------------------------------------------------

    def load(self, name: str, base: str = TABLES) -> "Table":
        path = os.path.join(base, name)
        if not os.path.isfile(path) or name in self.loaded:
            return self
        self.loaded.append(name)
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                forward = backward = True
                while parts and parts[0] in ("noback", "nofor"):
                    if parts[0] == "noback":
                        backward = False
                    else:
                        forward = False
                    parts = parts[1:]
                if not parts:
                    continue
                op = parts[0]
                if op == "include" and len(parts) > 1:
                    self.load(parts[1], base)
                elif op == "numsign" and len(parts) > 1:
                    self.numsign = dots_to_cells(parts[1])
                elif op in CHAR_OPCODES and len(parts) > 2:
                    ch = _unescape(parts[1])
                    cells = dots_to_cells(parts[2])
                    if op == "litdigit":
                        self.digits[ch] = cells
                    if ch not in self.chars or op == "letter":
                        self.chars[ch] = cells
                        self.char_kind[ch] = op
                elif op in RULE_OPCODES and len(parts) > 2:
                    self.rules.append(Rule(op, _unescape(parts[1]), dots_to_cells(parts[2]), forward, backward))
        self._index()
        return self

    def _index(self):
        self._by_first: Dict[str, List[Rule]] = {}
        for r in self.rules:
            if r.forward and r.chars:
                self._by_first.setdefault(r.chars[0], []).append(r)
        for lst in self._by_first.values():
            lst.sort(key=lambda r: -len(r.chars))
        self._back: Dict[str, List[Tuple[str, Rule]]] = {}
        for r in self.rules:
            if r.backward and r.cells:
                self._back.setdefault(r.cells[0], []).append((r.cells, r))
        prio = {"word": 0, "lowword": 0, "sufword": 1, "begword": 1, "prepunc": 3, "postpunc": 3}
        for lst in self._back.values():
            lst.sort(key=lambda x: (-len(x[0]), prio.get(x[1].opcode, 2)))
        # whole-word rules the table marks forward-only: a cell group that
        # stands alone as a word can still only mean that word
        self._back_words: Dict[str, str] = {}
        for r in self.rules:
            if not r.backward and r.opcode in ("word", "lowword") and r.cells:
                self._back_words.setdefault(r.cells, r.chars)
        self.arabic_letter_cells = {cells for ch, cells in self.chars.items()
                                    if self.char_kind.get(ch) == "letter" and "\u0600" <= ch <= "\u06ff"}
        # signs written with two or more cells (most mathematics), longest first
        self._multi_back: List[Tuple[str, str]] = []
        seen_cells = set()
        for ch, cells in self.chars.items():
            if len(cells) > 1 and cells not in seen_cells and not ch.isspace():
                seen_cells.add(cells)
                self._multi_back.append((cells, ch))
        self._multi_back.sort(key=lambda x: -len(x[0]))
        self._char_back: Dict[str, str] = {}
        for ch, cells in self.chars.items():
            kind = self.char_kind.get(ch)
            if len(cells) == 1 and (cells not in self._char_back or kind == "letter"):
                prev = self._char_back.get(cells)
                if prev is not None and self.char_kind.get(prev) == "letter" \
                        and not ("\u0621" <= ch <= "\u064a" and not "\u0621" <= prev <= "\u064a"):
                    continue
                self._char_back[cells] = ch
        for odd, usual in (("\u06d4", "."),):
            for cells, ch in list(self._char_back.items()):
                if ch == odd and self.chars.get(usual) == cells:
                    self._char_back[cells] = usual

    # -- helpers -------------------------------------------------------------

    def is_letter(self, ch: str) -> bool:
        return self.char_kind.get(ch) in ("letter", "lowercase", "uppercase") or ch.isalpha()

    def _position_ok(self, rule: Rule, text: str, i: int) -> bool:
        j = i + len(rule.chars)
        before = i > 0 and self.is_letter(text[i - 1])
        after = j < len(text) and self.is_letter(text[j])
        op = rule.opcode
        if op == "always" or op == "contraction":
            return op == "always"
        if op in ("word", "lowword"):
            return not before and not after
        if op == "partword":
            return before or after
        if op == "sufword":
            return not before
        if op == "begword":
            return not before and after
        if op == "begmidword":
            return after
        if op == "midword":
            return before and after
        if op == "midendword":
            return before
        if op == "endword":
            return before and not after
        if op == "prepunc":
            return not before
        if op == "postpunc":
            return not after
        return False


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

_CACHE: Dict[str, Table] = {}


def table(grade: int = 1) -> Table:
    name = "ar-ar-g2.ctb" if grade == 2 else "ar-ar-g1.utb"
    if name not in _CACHE:
        _CACHE[name] = Table().load(name)
    return _CACHE[name]


def available() -> bool:
    return os.path.isfile(os.path.join(TABLES, "ar-ar-g1.utb"))


_HARAKAT = "\u064b\u064c\u064d\u064e\u064f\u0650\u0652"


def normalize(text: str) -> str:
    """Put text in the order Arabic braille expects: the shadda straight after
    its letter (before any haraka), the dagger alef as a plain alef, and the
    small Qur'anic pause and recitation marks left out."""
    text = re.sub("([%s]+)\u0651" % _HARAKAT, "\u0651\\1", text)
    text = text.replace("\u0670", "\u0627").replace("\u0671", "\u0627").replace("\u0627\u0653", "\u0622")
    text = text.replace("\u0653", "")
    return re.sub("[\u06d6-\u06ed]", "", text)


def translate(text: str, grade: int = 1) -> str:
    """Arabic text -> Unicode braille, grade 1 or grade 2."""
    t = table(grade)
    text = normalize(text)
    out: List[str] = []
    i = 0
    in_number = False
    while i < len(text):
        ch = text[i]
        if ch in t.digits or ch.isdigit() and ch in "0123456789٠١٢٣٤٥٦٧٨٩":
            d = ch.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
            if not in_number:
                out.append(t.numsign)
                in_number = True
            out.append(t.digits.get(d, t.chars.get(d, "⠿")))
            i += 1
            continue
        if in_number and ch in ".,٫" and i + 1 < len(text) and text[i + 1].isdigit():
            out.append(t.chars.get(ch, "⠲"))
            i += 1
            continue
        in_number = False
        if ch in "\n\r":
            out.append(ch)
            i += 1
            continue
        if ch == " ":
            out.append("⠀")
            i += 1
            continue
        best = None
        for r in t._by_first.get(ch, ()):
            if text.startswith(r.chars, i) and t._position_ok(r, text, i):
                best = r
                break
        if best is not None:
            out.append(best.cells)
            i += len(best.chars)
            continue
        out.append(t.chars.get(ch, t.chars.get(ch.lower(), "⠿")))
        i += 1
    return "".join(out)


def _punc(t, c: str, opcode: str) -> str:
    for cells, r in t._back.get(c, ()):
        if cells == c and r.opcode == opcode:
            return r.chars
    return ""


def _is_end(t, braille: str, j: int) -> bool:
    """True where a word ends at j, looking past closing punctuation."""
    while j < len(braille):
        if braille[j] in "⠀ \n":
            return True
        if not _punc(t, braille[j], "postpunc"):
            return False
        j += 1
    return True


def back_translate(braille: str, grade: int = 1) -> str:
    """Unicode braille -> text. Grade 2 contractions are expanded where the
    table allows reading them back; ambiguous cells read as their letter."""
    t = table(grade)
    out: List[str] = []
    i = 0
    in_number = False
    digit_back = {v: k for k, v in t.digits.items()}
    while i < len(braille):
        c = braille[i]
        if c in "\n\r":
            out.append(c)
            i += 1
            continue
        if c in ("⠀", " "):
            out.append(" ")
            in_number = False
            i += 1
            continue
        nxt = i + len(t.numsign) if t.numsign else i
        if t.numsign and braille.startswith(t.numsign, i) and nxt < len(braille) and braille[nxt] in digit_back:
            in_number = True
            i += len(t.numsign)
            continue
        if in_number and c in digit_back:
            out.append(digit_back[c])
            i += 1
            continue
        in_number = False
        matched = False
        first = t._char_back.get(c, "")
        arabic_first = bool(first) and "\u0600" <= first[0] <= "\u06ff"
        alone_start = i == 0 or braille[i - 1] in "⠀ \n"
        for cells, ch in ([] if grade == 2 else t._multi_back):
            if braille.startswith(cells, i):
                end = i + len(cells)
                if arabic_first and not (alone_start and (end >= len(braille) or braille[end] in "⠀ \n")):
                    continue
                out.append(ch)
                i += len(cells)
                matched = True
                break
        if matched:
            continue
        # punctuation attached to a word: an opening sign before letters, a
        # closing sign after them (and before any further closing signs)
        at_start = i == 0 or braille[i - 1] in "⠀ \n"
        if at_start and not _is_end(t, braille, i + 1):
            pre = _punc(t, c, "prepunc")
            if pre:
                out.append(pre)
                i += 1
                continue
        if not at_start and _is_end(t, braille, i + 1):
            post = _punc(t, c, "postpunc")
            if post:
                out.append(post)
                i += 1
                continue
        if grade == 2:
            word_start = i == 0 or braille[i - 1] in "⠀ \n"
            if word_start:
                end = i
                while end < len(braille) and braille[end] not in "⠀ \n":
                    end += 1
                whole = braille[i:end]
                if whole in t._back_words and not any(cells == whole for cells, _ in t._back.get(c, ())):
                    out.append(t._back_words[whole])
                    i = end
                    continue
            for cells, r in t._back.get(c, ()):
                if not braille.startswith(cells, i):
                    continue
                j = i + len(cells)
                word_end = _is_end(t, braille, j)
                if r.opcode in ("word", "lowword") and not (word_start and word_end):
                    continue
                if r.opcode in ("sufword", "begword") and not word_start:
                    continue
                if r.opcode == "begword" and word_end:
                    continue
                if r.opcode == "midword" and (word_start or word_end):
                    continue
                if r.opcode == "endword" and (word_start or not word_end):
                    continue
                if r.opcode == "postpunc" and not word_end or r.opcode == "prepunc" and not word_start:
                    continue
                # a one-cell sign is also a letter or punctuation: read it as a
                # contraction only where its rule pins the position
                if len(cells) == 1 and r.opcode not in ("word", "lowword", "sufword", "begword", "endword") \
                        and cells in t.arabic_letter_cells:
                    continue
                out.append(r.chars)
                i = j
                matched = True
                break
        if matched:
            continue
        ch = t._char_back.get(c, "؟")
        if not "\u0600" <= ch[:1] <= "\u06ff":
            for cells, r in t._back.get(c, ()):
                if cells == c and r.opcode == "always" and r.chars and "\u0600" <= r.chars[0] <= "\u06ff":
                    ch = r.chars
                    break
        out.append(ch)
        i += 1
    # Arabic braille writes the shadda before its letter; text puts it after
    return re.sub("\u0651([\u0621-\u064a])", "\\1\u0651", "".join(out))


MATH_NAMES = {
    "+": "زائد", "−": "ناقص", "×": "ضرب", "÷": "قسمة", "=": "يساوي", "≠": "لا يساوي",
    "≈": "يقارب", "<": "أصغر من", ">": "أكبر من", "≤": "أصغر من أو يساوي", "≥": "أكبر من أو يساوي",
    "±": "زائد أو ناقص", "√": "الجذر التربيعي", "∛": "الجذر التكعيبي", "∞": "ما لا نهاية", "π": "باي",
    "%": "بالمئة", "٪": "بالمئة", "½": "نصف", "⅓": "ثلث", "¼": "ربع", "¾": "ثلاثة أرباع", "⅔": "ثلثان",
    "²": "تربيع (أس ٢)", "³": "تكعيب (أس ٣)", "∫": "التكامل", "∂": "التفاضل الجزئي", "∈": "ينتمي إلى",
    "∉": "لا ينتمي إلى", "⊂": "مجموعة جزئية من", "∪": "اتحاد", "∩": "تقاطع", "∅": "المجموعة الخالية",
    "∑": "مجموع", "°": "درجة", "∠": "زاوية", "⊥": "عمودي على", "∥": "يوازي", "△": "مثلّث",
    "(": "قوس مفتوح", ")": "قوس مغلق", "[": "قوس معقوف مفتوح", "]": "قوس معقوف مغلق",
    "{": "حاصرة مفتوحة", "}": "حاصرة مغلقة", "∴": "إذن", "∵": "لأنّ", "∝": "يتناسب مع", "≡": "يطابق",
}


def math_signs() -> List[Tuple[str, str, str]]:
    """(sign, Arabic name, cells) for the mathematical signs the Arabic grade 1
    table defines and that have an Arabic name here."""
    t = table(1)
    out = []
    for ch, name in MATH_NAMES.items():
        cells = t.chars.get(ch)
        if cells and "⠿" not in cells:
            out.append((ch, name, cells))
    return out


def describe_cells(braille: str, limit: int = 40) -> str:
    """Spoken form: each cell as its dot numbers."""
    parts = []
    for c in braille[:limit]:
        if c in ("⠀", " "):
            parts.append("فراغ")
        elif 0x2800 <= ord(c) <= 0x28FF:
            parts.append("نقاط " + "، ".join(cell_dots(c)))
    more = len(braille) - limit
    return "؛ ".join(parts) + (f"؛ و{more} خلية أخرى" if more > 0 else "")


# North American Braille Computer Code: the ASCII character an embosser
# prints for each of the 64 six-dot cells (index = dot bits, dot1 = 1).
_NABCC = (" A1B'K2L@CIF/MSP\"E3H9O6R^DJG>NTQ,*5<-U8V.%[$+X!&;:4\\0Z7(_?W]#Y)=")


def to_brf(braille: str, width: int = 40) -> str:
    """Unicode braille -> North American ASCII braille, wrapped to ``width``
    cells per line, for printing on a braille embosser (.brf)."""
    lines = []
    for para in braille.split("\n"):
        words = para.replace(" ", "⠀").split("⠀")
        line = ""
        for w in words:
            ascii_w = "".join(_NABCC[(ord(c) - 0x2800) & 0x3F] if 0x2800 <= ord(c) <= 0x28FF else c for c in w)
            if line and len(line) + 1 + len(ascii_w) > width:
                lines.append(line)
                line = ascii_w
            else:
                line = f"{line} {ascii_w}" if line else ascii_w
        lines.append(line)
    return "\r\n".join(lines) + "\r\n"
