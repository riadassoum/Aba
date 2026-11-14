# -*- coding: utf-8 -*-
"""
abaAcademy.deck_import
======================

Bring flashcards in from other programs and send them back out.

Reads CSV, TSV, semicolon- or bar-separated text and Anki's "Notes in plain
text" export. The encoding (UTF-8 with or without BOM, UTF-16, or Windows
Arabic cp1256) and the separator are detected automatically; Anki's header
lines (``#separator:tab``, ``#html:true``, ``#deck column:3`` …) are honoured;
HTML formatting and sound/image references are stripped so the card text is
clean for speech. A header row (front/back, question/answer, السؤال/الجواب …)
is recognised and skipped. Duplicates of cards already in the deck are not
added twice.

Also builds quick decks from the academy's own data (the periodic table,
Morse code) and exports any deck as UTF-8 TSV that Anki and spreadsheets
open directly.
"""

from __future__ import annotations

import csv
import html
import io
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

_SEPARATORS = {"tab": "\t", "comma": ",", "semicolon": ";", "pipe": "|",
               "space": " ", "colon": ":"}
_HEADER_WORDS = {
    "front", "back", "question", "answer", "term", "definition", "word", "meaning",
    "hint", "deck", "tags", "الوجه", "الظهر", "السؤال", "الجواب", "الإجابة", "الكلمة",
    "المعنى", "التلميح", "المجموعة", "الوجه الأمامي", "الوجه الخلفي",
}
_TAG_RE = re.compile(r"<[^>]+>")
_SOUND_RE = re.compile(r"\[sound:[^\]]*\]")
_CLOZE_RE = re.compile(r"\{\{c\d+::(.*?)(?:::(.*?))?\}\}")


@dataclass
class ParsedDeck:
    cards: List[Tuple[str, str, str]] = field(default_factory=list)   # front, back, hint
    deck_names: List[str] = field(default_factory=list)               # per card, '' if none
    encoding: str = ""
    separator: str = ""
    skipped: int = 0
    header_skipped: bool = False

    def summary(self) -> str:
        sep_names = {"\t": "مسافة جدولة", ",": "فاصلة", ";": "فاصلة منقوطة",
                     "|": "خطّ عمودي", ":": "نقطتان", " ": "مسافة"}
        parts = [f"{len(self.cards)} بطاقة"]
        if self.skipped:
            parts.append(f"وتُجوهل {self.skipped} سطرًا غير صالح")
        return (f"قُرئ الملفّ بترميز {self.encoding} والفاصل {sep_names.get(self.separator, self.separator)}: "
                + "، ".join(parts) + ".")


def decode_bytes(data: bytes) -> Tuple[str, str]:
    """(text, encoding name)."""
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", errors="replace"), "UTF-8"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace"), "UTF-16"
    try:
        return data.decode("utf-8"), "UTF-8"
    except UnicodeDecodeError:
        pass
    try:
        return data.decode("cp1256"), "Windows-1256"
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace"), "Latin-1"


def clean_field(text: str, keep_cloze_answer: bool = True) -> str:
    t = text or ""
    t = _SOUND_RE.sub("", t)
    t = re.sub(r"(?i)<br\s*/?>", " ", t)
    t = re.sub(r"(?i)</(div|p|li)>", " ", t)
    t = _TAG_RE.sub("", t)
    t = html.unescape(t)
    if keep_cloze_answer:
        t = _CLOZE_RE.sub(lambda m: m.group(1), t)
    return " ".join(t.split())


def _anki_headers(lines: List[str]):
    meta = {}
    body = []
    for line in lines:
        if line.startswith("#") and ":" in line and not body:
            k, v = line[1:].split(":", 1)
            meta[k.strip().lower()] = v.strip()
        else:
            body.append(line)
    return meta, body


def detect_separator(lines: Sequence[str]) -> str:
    sample = [l for l in lines if l.strip()][:30]
    if not sample:
        return "\t"
    best, best_score = "\t", -1.0
    for sep in ("\t", ";", "|", ","):
        counts = [l.count(sep) for l in sample]
        hits = [c for c in counts if c >= 1]
        if not hits:
            continue
        # most lines contain it, and the count is consistent
        consistency = len(hits) / len(sample)
        spread = (max(hits) - min(hits)) if hits else 0
        score = consistency * 10 - spread * 0.5 + (0.5 if sep == "\t" else 0)
        if score > best_score:
            best, best_score = sep, score
    if best_score < 0:
        # no separator on any line: "front - back" or "front = back" pairs
        for sep in (" - ", " = ", " : ", " – "):
            if sum(1 for l in sample if sep in l) >= len(sample) * 0.6:
                return sep
    return best


def _looks_like_header(row: Sequence[str]) -> bool:
    cells = [c.strip().lower() for c in row[:3] if c.strip()]
    return bool(cells) and all(c in _HEADER_WORDS for c in cells)


def parse_text(text: str, encoding: str = "UTF-8") -> ParsedDeck:
    lines = text.splitlines()
    meta, body = _anki_headers(lines)
    sep = None
    if "separator" in meta:
        sep = _SEPARATORS.get(meta["separator"].lower(), meta["separator"][:1] or "\t")
    sep = sep or detect_separator(body)
    deck_col = None
    if "deck column" in meta:
        try:
            deck_col = int(meta["deck column"]) - 1
        except ValueError:
            deck_col = None
    out = ParsedDeck(encoding=encoding, separator=sep)
    if len(sep) == 1:
        reader = csv.reader(io.StringIO("\n".join(body)), delimiter=sep,
                            quotechar='"', skipinitialspace=(sep != "\t"))
        rows = list(reader)
    else:
        rows = [l.split(sep, 1) for l in body]
    first = True
    for row in rows:
        if not any(c.strip() for c in row):
            continue
        if first:
            first = False
            if _looks_like_header(row):
                out.header_skipped = True
                continue
        deck = ""
        if deck_col is not None and deck_col < len(row):
            deck = clean_field(row[deck_col])
            row = [c for i, c in enumerate(row) if i != deck_col]
        fields = [clean_field(c) for c in row]
        fields = [f for f in fields]
        if len(fields) < 2 or not fields[0] or not fields[1]:
            out.skipped += 1
            continue
        hint = fields[2] if len(fields) > 2 else ""
        out.cards.append((fields[0], fields[1], hint))
        out.deck_names.append(deck)
    return out


def parse_file(path: str) -> ParsedDeck:
    with open(path, "rb") as f:
        data = f.read()
    text, enc = decode_bytes(data)
    return parse_text(text, enc)


def import_into(store, parsed: ParsedDeck, deck: str = "", swap: bool = False) -> Tuple[int, int]:
    """Add the parsed cards to a FlashcardStore. Returns (added, duplicates)."""
    existing = {(c.get("front", ""), c.get("back", ""), c.get("deck", ""))
                for c in store.all_cards()}
    new_cards = []
    dup = 0
    for (front, back, hint), dname in zip(parsed.cards, parsed.deck_names):
        if swap:
            front, back = back, front
        name = (dname or deck or "مستورد").strip()
        key = (front, back, name)
        if key in existing:
            dup += 1
            continue
        existing.add(key)
        new_cards.append((front, back, name, hint))
    if hasattr(store, "add_many"):
        store.add_many(new_cards)
    else:
        for front, back, name, hint in new_cards:
            store.add(front, back, name, hint)
    return len(new_cards), dup


def export_tsv(cards: Iterable[dict], deck: Optional[str] = None) -> str:
    """UTF-8 TSV with Anki headers; tabs/newlines inside fields become spaces."""
    def esc(s):
        return " ".join(str(s or "").replace("\t", " ").split())
    lines = ["#separator:tab", "#html:false", "#columns:الوجه\tالظهر\tالتلميح"]
    for c in cards:
        if deck and (c.get("deck") or "عام") != deck:
            continue
        lines.append(f"{esc(c.get('front'))}\t{esc(c.get('back'))}\t{esc(c.get('hint'))}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# decks made from the academy's own data
# ---------------------------------------------------------------------------

GENERATED_DECKS = {
    "elements_symbols": "رموز العناصر الكيميائية (أول ٣٦ عنصرًا)",
    "elements_all": "رموز العناصر الكيميائية (كلّ العناصر)",
    "morse_ar": "شيفرة مورس للحروف العربية",
    "morse_en": "شيفرة مورس للحروف اللاتينية والأرقام",
    "arud_metres": "بحور الشعر وتفعيلاتها",
}


def generated_cards(kind: str) -> List[Tuple[str, str, str]]:
    if kind in ("elements_symbols", "elements_all"):
        from .science import periodic
        limit = 36 if kind == "elements_symbols" else 118
        return [(e.symbol, e.name, f"العدد الذري {e.number}")
                for e in periodic.TABLE if e.number <= limit]
    if kind in ("morse_ar", "morse_en"):
        from .tools import morse
        if kind == "morse_ar":
            return [(f"{ch} ({morse.ARABIC_NAMES[ch]})", f"{morse.spoken_code(code)}",
                     morse.rhythm_word(code)) for ch, code in morse.ARABIC.items()]
        items = list(morse.LATIN.items()) + list(morse.DIGITS.items())
        return [(ch, morse.spoken_code(code), morse.rhythm_word(code)) for ch, code in items]
    if kind == "arud_metres":
        from .arabic_lab import arud
        return [(m.name, m.feet, m.miftah) for m in arud.METRES]
    raise ValueError(kind)


def add_generated(store, kind: str) -> Tuple[int, int]:
    deck_name = GENERATED_DECKS[kind]
    parsed = ParsedDeck(cards=generated_cards(kind), encoding="", separator="")
    parsed.deck_names = [deck_name] * len(parsed.cards)
    return import_into(store, parsed)
