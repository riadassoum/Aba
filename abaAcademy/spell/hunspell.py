# -*- coding: utf-8 -*-
"""
abaAcademy.spell.hunspell
=========================

A small pure-Python reader for Hunspell dictionaries (.aff and .dic), enough
to check and suggest words with the Arabic (Ayaspell), English (SCOWL) and
French (Grammalecte) dictionaries that LibreOffice ships. No native library
is needed, so it runs in the portable build as it is.

Supported: FLAG (single, long, num, UTF-8), AF flag aliases, PFX and SFX
with conditions, cross products and continuation classes (two suffixes, or a
prefix and up to two suffixes), NEEDAFFIX, FORBIDDENWORD, CIRCUMFIX, KEEPCASE,
NOSUGGEST, IGNORE, ICONV, REP, MAP, KEY and TRY. Compounding is not
supported; words made only by compounding are reported as unknown.

Suggestions follow Hunspell's order of ideas: REP replacements, MAP related
letters, a neighbouring key, a swapped, missing, doubled or extra letter,
then two edits for short words. Every suggestion is checked against the
dictionary, so nothing is suggested that the dictionary does not accept.
"""

from __future__ import annotations

import io
import re
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Set, Tuple


class Affix:
    __slots__ = ("kind", "flag", "cross", "strip", "add", "cond", "cont")

    def __init__(self, kind, flag, cross, strip, add, cond, cont):
        self.kind = kind
        self.flag = flag
        self.cross = cross
        self.strip = strip
        self.add = add
        self.cond = cond
        self.cont = cont


def _cond_regex(cond: str, kind: str):
    if cond in (".", ""):
        return None
    return re.compile(("^" + cond) if kind == "PFX" else (cond + "$"))


class Dictionary:
    def __init__(self, aff_path: str, dic_path: str):
        self.flag_mode = "single"
        self.aliases: List[str] = []
        self.pfx: Dict[str, List[Affix]] = defaultdict(list)    # by added text
        self.sfx: Dict[str, List[Affix]] = defaultdict(list)
        self.max_pfx = 0
        self.max_sfx = 0
        self.rep: List[Tuple[str, str]] = []
        self.maps: List[str] = []
        self.key: List[str] = []
        self.try_chars = ""
        self.ignore = ""
        self.iconv: List[Tuple[str, str]] = []
        self.needaffix = self.forbidden = self.circumfix = self.keepcase = self.nosuggest = None
        self._read_aff(aff_path)
        self.words: Dict[str, Tuple[str, ...]] = {}
        self._read_dic(dic_path)
        self._ignore_re = re.compile("[" + re.escape(self.ignore) + "]") if self.ignore else None

    # -- loading ---------------------------------------------------------------

    def parse_flags(self, s: str) -> Tuple[str, ...]:
        if not s:
            return ()
        if self.aliases and s.isdigit():
            i = int(s)
            if 0 < i <= len(self.aliases):
                s = self.aliases[i - 1]
        if self.flag_mode == "long":
            return tuple(s[i:i + 2] for i in range(0, len(s) - 1, 2))
        if self.flag_mode == "num":
            return tuple(x for x in s.split(",") if x)
        return tuple(s)

    def _read_aff(self, path: str) -> None:
        with io.open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().split("\n")
        pending = {}
        for raw in lines:
            line = raw.split("#", 1)[0].strip() if not raw.lstrip().startswith(("ICONV", "REP", "MAP", "KEY", "TRY", "IGNORE")) else raw.strip()
            if not line:
                continue
            p = line.split()
            op = p[0]
            if op == "FLAG" and len(p) > 1:
                self.flag_mode = {"long": "long", "num": "num", "UTF-8": "single"}.get(p[1], "single")
            elif op == "AF" and len(p) > 1:
                if p[1].isdigit() and "AF" not in pending:
                    pending["AF"] = int(p[1])          # the count line
                else:
                    self.aliases.append(p[1])
            elif op in ("PFX", "SFX") and len(p) >= 4:
                flag = p[1]
                if len(p) == 4 and p[3].isdigit() and p[2] in ("Y", "N"):
                    pending[(op, flag)] = p[2] == "Y"
                    continue
                cross = pending.get((op, flag), True)
                strip = "" if p[2] == "0" else p[2]
                add, _, cont = p[3].partition("/")
                add = "" if add == "0" else add
                cond = p[4] if len(p) > 4 else "."
                a = Affix(op, flag, cross, strip, add, _cond_regex(cond, op), frozenset(self.parse_flags(cont)))
                if op == "PFX":
                    self.pfx[add].append(a)
                    self.max_pfx = max(self.max_pfx, len(add))
                else:
                    self.sfx[add].append(a)
                    self.max_sfx = max(self.max_sfx, len(add))
            elif op == "REP" and len(p) == 3:
                self.rep.append((p[1].replace("_", " "), p[2].replace("_", " ")))
            elif op == "MAP" and len(p) == 2 and not p[1].isdigit():
                self.maps.append(p[1])
            elif op == "KEY" and len(p) == 2:
                self.key = p[1].split("|") if "|" in p[1] else p[1].split("¦")
            elif op == "TRY" and len(p) == 2:
                self.try_chars = p[1]
            elif op == "IGNORE" and len(p) == 2:
                self.ignore = p[1]
            elif op == "ICONV" and len(p) == 3:
                self.iconv.append((p[1], p[2]))
            elif op in ("NEEDAFFIX", "FORBIDDENWORD", "CIRCUMFIX", "KEEPCASE", "NOSUGGEST") and len(p) == 2:
                setattr(self, {"NEEDAFFIX": "needaffix", "FORBIDDENWORD": "forbidden", "CIRCUMFIX": "circumfix",
                               "KEEPCASE": "keepcase", "NOSUGGEST": "nosuggest"}[op],
                        self.parse_flags(p[1])[0] if self.parse_flags(p[1]) else None)
        # SFX/PFX lines were parsed before FLAG could matter only if FLAG
        # comes first, which every real dictionary does.

    def _read_dic(self, path: str) -> None:
        with io.open(path, encoding="utf-8", errors="replace") as f:
            first = True
            for line in f:
                if first:
                    first = False
                    if line.strip().isdigit():
                        continue
                line = line.rstrip("\n")
                if not line or line.startswith(("#", "\t")):
                    continue
                word, flags = line, ""
                # a slash escaped as \/ belongs to the word
                k = line.find("/")
                while k > 0 and line[k - 1] == "\\":
                    k = line.find("/", k + 1)
                if k > 0:
                    word, flags = line[:k].replace("\\/", "/"), line[k + 1:]
                word = word.split("\t")[0].split(" ")[0] if (" " in word or "\t" in word) else word
                flags = flags.split()[0] if flags.strip() else ""
                fl = self.parse_flags(flags)
                if word in self.words:
                    self.words[word] = tuple(set(self.words[word]) | set(fl))
                else:
                    self.words[word] = fl

    # -- checking ----------------------------------------------------------------

    def _clean(self, word: str) -> str:
        for a, b in self.iconv:
            word = word.replace(a, b)
        if self._ignore_re is not None:
            word = self._ignore_re.sub("", word)
        return word

    def _entry_ok(self, stem: str, need: Iterable[str] = (), plain: bool = False) -> bool:
        fl = self.words.get(stem)
        if fl is None:
            return False
        if self.forbidden and self.forbidden in fl:
            return False
        if plain and self.needaffix and self.needaffix in fl:
            return False
        return all(n in fl for n in need)

    def _suffix_stems(self, word: str):
        n = len(word)
        for k in range(min(self.max_sfx, n - 1), -1, -1):
            add = word[n - k:] if k else ""
            for a in self.sfx.get(add, ()):
                stem = word[:n - k] + a.strip
                if not stem:
                    continue
                if a.cond is not None and not a.cond.search(stem):
                    continue
                yield a, stem

    def _prefix_stems(self, word: str):
        n = len(word)
        for k in range(min(self.max_pfx, n - 1), -1, -1):
            add = word[:k]
            for a in self.pfx.get(add, ()):
                stem = a.strip + word[k:]
                if not stem:
                    continue
                if a.cond is not None and not a.cond.search(stem):
                    continue
                yield a, stem

    def _check_suffixed(self, word: str, pfx: Optional[Affix] = None) -> bool:
        for s1, stem in self._suffix_stems(word):
            if pfx is not None and not (s1.cross and pfx.cross):
                continue
            needs_more = self.needaffix and self.needaffix in s1.cont
            # word = stem + s1
            if not needs_more:
                fl = self.words.get(stem)
                if fl is not None and s1.flag in fl and not (self.forbidden and self.forbidden in fl):
                    if pfx is None or pfx.flag in fl or pfx.flag in s1.cont:
                        if not (self.circumfix and (self.circumfix in s1.cont) != (pfx is not None and self.circumfix in pfx.cont)):
                            return True
            # word = stem + s2 + s1, where s1 continues s2
            for s2, stem2 in self._suffix_stems(stem):
                if s1.flag not in s2.cont:
                    continue
                if pfx is not None and not (s2.cross and pfx.cross):
                    continue
                fl = self.words.get(stem2)
                if fl is not None and s2.flag in fl and not (self.forbidden and self.forbidden in fl):
                    if pfx is None or pfx.flag in fl or pfx.flag in s1.cont or pfx.flag in s2.cont:
                        return True
        return False

    def _check_form(self, word: str) -> bool:
        if self._entry_ok(word, plain=True):
            return True
        if self._check_suffixed(word):
            return True
        for p, stem in self._prefix_stems(word):
            if not p.add and not p.strip:
                continue
            needs_more = self.needaffix and self.needaffix in p.cont
            fl = self.words.get(stem)
            if not needs_more and fl is not None and p.flag in fl and not (self.forbidden and self.forbidden in fl):
                if not (self.circumfix and self.circumfix in p.cont):
                    return True
            if self._check_suffixed(stem, p):
                return True
        return False

    def check(self, word: str) -> bool:
        w = self._clean(word.strip())
        if not w:
            return True
        if any(c.isdigit() for c in w) and not any(c.isalpha() for c in w):
            return True
        if self._check_form(w):
            return True
        if w[:1].isupper():
            low = w.lower()
            if low != w and self._check_form(low):
                fl = self.words.get(low)
                if not (self.keepcase and fl and self.keepcase in fl):
                    return True
            cap = w[:1] + w[1:].lower()
            if cap != w and w.isupper() and self._check_form(cap):
                return True
        return False

    # -- suggestions -------------------------------------------------------------

    def _related(self) -> Dict[str, Set[str]]:
        rel: Dict[str, Set[str]] = defaultdict(set)
        for group in self.maps:
            chars = re.findall(r"\(([^)]*)\)|(.)", group)
            items = [a or b for a, b in chars]
            for x in items:
                for y in items:
                    if x != y:
                        rel[x].add(y)
        return rel

    def _neighbours(self) -> Dict[str, Set[str]]:
        nb: Dict[str, Set[str]] = defaultdict(set)
        for row in self.key:
            for i, c in enumerate(row):
                if i > 0:
                    nb[c].add(row[i - 1])
                if i + 1 < len(row):
                    nb[c].add(row[i + 1])
        return nb

    def _good(self, cand: str) -> bool:
        if not cand or cand.startswith(" ") or cand.endswith(" "):
            return False
        if " " in cand:
            return all(len(p) > 1 and self.check(p) for p in cand.split())
        if not self.check(cand):
            return False
        fl = self.words.get(cand)
        return not (self.nosuggest and fl and self.nosuggest in fl)

    def suggest(self, word: str, limit: int = 8) -> List[str]:
        w = self._clean(word.strip())
        if not w:
            return []
        out: List[str] = []
        tier: Dict[str, int] = {}
        level = [0]

        def add(c):
            if self._ignore_re is not None:
                c = self._ignore_re.sub("", c)
            if any("\ufb50" <= ch <= "\ufeff" for ch in c):
                return
            if c != w and c not in tier and self._good(c):
                out.append(c)
                tier[c] = level[0]

        if any("\u0621" <= ch <= "\u064a" for ch in w):
            # the slips Arabic writers make most: ta marbuta and ha, alif
            # maqsura and ya at the end, and the hamza on an initial alif
            if w.endswith("ه"):
                add(w[:-1] + "ة")
            if w.endswith("ي"):
                add(w[:-1] + "ى")
            if w.endswith("ى"):
                add(w[:-1] + "ي")
            if w.endswith("ة"):
                add(w[:-1] + "ه")
            if w.endswith("و"):
                add(w + "ا")
            if w[:1] == "ا" and w.endswith("ي"):
                add("إ" + w[1:-1] + "ى")
                add("أ" + w[1:-1] + "ى")
            for i in [0] + [k + 1 for k, ch in enumerate(w[:3]) if ch in "وفبل"]:
                if i < len(w) and w[i] == "ا":
                    add(w[:i] + "أ" + w[i + 1:])
                    add(w[:i] + "إ" + w[i + 1:])
                elif i < len(w) and w[i] in "أإ":
                    add(w[:i] + "ا" + w[i + 1:])

        for a, b in self.rep:
            i = w.find(a)
            while i >= 0:
                add(w[:i] + b + w[i + len(a):])
                i = w.find(a, i + 1)
        level[0] = 1
        rel = getattr(self, "_rel", None)
        if rel is None:
            rel = self._rel = self._related()
            self._nb = self._neighbours()
        for i, c in enumerate(w):
            for r in rel.get(c, ()):
                add(w[:i] + r + w[i + 1:])
        level[0] = 2
        for i, c in enumerate(w):
            for r in self._nb.get(c, ()):
                add(w[:i] + r + w[i + 1:])
        if len(out) < limit:
            for cand in self._edits1(w):
                add(cand)
                if len(out) >= limit * 2:
                    break
        if not out and len(w) <= 8:
            seen = 0
            for e1 in self._edits1(w):
                for cand in self._edits1(e1, splits=False):
                    add(cand)
                    seen += 1
                if len(out) >= limit or seen > 60000:
                    break
        if w[:1].isupper() and not out:
            return [s[:1].upper() + s[1:] for s in self.suggest(w.lower(), limit)]
        from difflib import SequenceMatcher
        rel = self._rel

        def norm(x):
            return "".join(min([ch] + sorted(rel.get(ch, ()))) for ch in x.lower())

        nw = norm(w)
        def key(c):
            score = SequenceMatcher(None, nw, norm(c.replace(" ", ""))).ratio()
            if len(c) == len(w) and sorted(c.lower()) == sorted(w.lower()):
                score += 0.15                         # two letters swapped
            return (" " in c, min(tier[c], 1), -score, abs(len(c) - len(w)))

        out.sort(key=key)
        return out[:limit]

    def _edits1(self, w: str, splits: bool = True):
        letters = self.try_chars or "".join(sorted(set(w)))
        n = len(w)
        for i in range(n - 1):                       # swapped neighbours
            if w[i] != w[i + 1]:
                yield w[:i] + w[i + 1] + w[i] + w[i + 2:]
        for i in range(n):                            # extra letter
            yield w[:i] + w[i + 1:]
        for i in range(n + 1):                        # missing letter
            for c in letters:
                yield w[:i] + c + w[i:]
        for i in range(n):                            # wrong letter
            for c in letters:
                if c != w[i]:
                    yield w[:i] + c + w[i + 1:]
        if splits:
            for i in range(1, n):                     # two words run together
                yield w[:i] + " " + w[i:]


_WORD = re.compile(r"[\w؀-ۿ'’-]+", re.UNICODE)


def words_in(text: str) -> List[Tuple[int, int, str]]:
    """(start, end, word) for each word worth checking: letters only, with
    leading and trailing apostrophes and hyphens dropped."""
    out = []
    for m in _WORD.finditer(text):
        s, e = m.start(), m.end()
        while s < e and text[s] in "'’-":
            s += 1
        while e > s and text[e - 1] in "'’-":
            e -= 1
        word = text[s:e]
        if word and any(c.isalpha() for c in word) and not any(c.isdigit() for c in word):
            out.append((s, e, word))
    return out
