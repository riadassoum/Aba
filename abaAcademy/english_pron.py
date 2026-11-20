# -*- coding: utf-8 -*-
"""
abaAcademy.english_pron
=======================

دليل النطق الإنجليزي — how about 20,000 English words are pronounced, from
the CMU Pronouncing Dictionary (Carnegie Mellon University, BSD-style
licence): the sounds in the International Phonetic Alphabet, an Arabic-
letter approximation a speech synthesizer can read, the syllable count and
which syllable carries the stress, words that rhyme, and silent letters
made obvious by comparing spelling and sound. English spelling is the
hardest part of the language for a learner who cannot see words often;
this hears it.
"""

from __future__ import annotations

import gzip
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "resources", "english", "cmudict.txt.gz")

IPA = {"AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ", "B": "b", "CH": "tʃ", "D": "d", "DH": "ð",
       "EH": "ɛ", "ER": "ɝ", "EY": "eɪ", "F": "f", "G": "ɡ", "HH": "h", "IH": "ɪ", "IY": "i", "JH": "dʒ", "K": "k",
       "L": "l", "M": "m", "N": "n", "NG": "ŋ", "OW": "oʊ", "OY": "ɔɪ", "P": "p", "R": "r", "S": "s", "SH": "ʃ",
       "T": "t", "TH": "θ", "UH": "ʊ", "UW": "u", "V": "v", "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ"}
# an approximation in Arabic letters, chosen so that Arabic voices read it
CONS = {"B": "ب", "CH": "تش", "D": "د", "DH": "ذ", "F": "ف", "G": "غ", "HH": "ه", "JH": "ج", "K": "ك", "L": "ل",
        "M": "م", "N": "ن", "NG": "نغ", "P": "ب", "R": "ر", "S": "س", "SH": "ش", "T": "ت", "TH": "ث", "V": "ف",
        "W": "و", "Y": "ي", "Z": "ز", "ZH": "ج"}
# vowel: (mark after a consonant, form at the start of the word)
VOW = {"AA": ("ا", "آ"), "AE": ("َا", "أَ"), "AH": ("َ", "أَ"), "AO": ("و", "أو"), "AW": ("َاو", "آو"),
       "AY": ("َاي", "آي"), "EH": ("َ", "إِ"), "ER": ("ِر", "أِر"), "EY": ("ِي", "إي"), "IH": ("ِ", "إِ"),
       "IY": ("ِي", "إي"), "OW": ("ُو", "أو"), "OY": ("ُوي", "أوي"), "UH": ("ُ", "أُ"), "UW": ("ُو", "أو")}
ORDINAL = ["الأول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس", "السابع", "الثامن"]
SOUND_NAMES = {"TH": "ث كما في think", "DH": "ذ كما في this", "P": "پ، الباء المهموسة، كما في pen",
               "V": "ڤ، الفاء المجهورة، كما في very", "G": "الجيم القاهرية كما في go", "NG": "النون الأنفية كما في sing",
               "ZH": "الجيم الشامية كما في vision", "CH": "تش كما في church"}

_words: Dict[str, Tuple[List[str], int]] = {}


def load() -> Dict[str, Tuple[List[str], int]]:
    if not _words and os.path.exists(PATH):
        with gzip.open(PATH, "rt", encoding="utf-8") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                if len(p) == 3:
                    _words[p[0]] = (p[1].split(), int(p[2]))
    return _words


def available() -> bool:
    return bool(load())


@dataclass
class Pron:
    word: str
    phones: List[str]
    freq: int

    @property
    def vowels(self) -> List[str]:
        return [p for p in self.phones if p[-1].isdigit()]

    @property
    def syllables(self) -> int:
        return len(self.vowels)

    @property
    def stress(self) -> int:
        """Index (from 0) of the syllable with primary stress."""
        for i, v in enumerate(self.vowels):
            if v.endswith("1"):
                return i
        return 0

    def ipa(self) -> str:
        out = []
        for p in self.phones:
            base, mark = (p[:-1], p[-1]) if p[-1].isdigit() else (p, "")
            sym = IPA.get(base, base.lower())
            if base == "AH" and mark == "0":
                sym = "ə"
            if base == "ER" and mark == "0":
                sym = "ɚ"
            out.append(("ˈ" if mark == "1" else "ˌ" if mark == "2" else "") + sym)
        return "/" + "".join(out) + "/"

    def arabic(self) -> str:
        out = []
        for i, p in enumerate(self.phones):
            base = p[:-1] if p[-1].isdigit() else p
            if base in VOW:
                mid, start = VOW[base]
                out.append(start if not out else mid)
            else:
                out.append(CONS.get(base, ""))
        return "".join(out)

    def rhyme_key(self) -> Tuple[str, ...]:
        """Phones from the last stressed vowel to the end."""
        idx = 0
        for i, p in enumerate(self.phones):
            if p[-1] in "12":
                idx = i
        return tuple(p.rstrip("012") for p in self.phones[idx:])

    def describe(self) -> str:
        n = self.syllables
        syl = "مقطع واحد" if n == 1 else ("مقطعان" if n == 2 else f"{n} مقاطع")
        parts = [f"{self.word}: تُنطق تقريبًا {self.arabic()}", f"وبالرموز الصوتية {self.ipa()}", syl]
        if n > 1:
            parts.append(f"النبر على المقطع {ORDINAL[self.stress] if self.stress < len(ORDINAL) else self.stress + 1}")
        special = [SOUND_NAMES[b] for b in dict.fromkeys(p.rstrip("012") for p in self.phones) if b in SOUND_NAMES]
        if special:
            parts.append("أصوات ليست في العربية: " + "، ".join(special))
        silent = silent_letters(self.word, self.phones)
        if silent:
            parts.append("حروف لا تُنطق: " + "، ".join(silent))
        return "، ".join(parts) + "."


def lookup(word: str) -> Optional[Pron]:
    w = word.strip().lower()
    v = load().get(w)
    return Pron(w, v[0], v[1]) if v else None


def rhymes(word: str, limit: int = 40) -> List[str]:
    p = lookup(word)
    if not p:
        return []
    key = p.rhyme_key()
    out = [(f, w) for w, (ph, f) in load().items() if w != p.word and Pron(w, ph, f).rhyme_key() == key]
    out.sort(key=lambda x: -x[0])
    return [w for _, w in out[:limit]]


SILENT_PATTERNS = [("kn", 0, "K"), ("wr", 0, "W"), ("gn", 0, "G"), ("ps", 0, "P"), ("mb", 1, "B"), ("mn", 1, "N"),
                   ("gh", 0, "G"), ("wh", 1, "HH"), ("lk", 0, "L"), ("lm", 0, "L"), ("bt", 0, "B"), ("st", 1, "T")]


def silent_letters(word: str, phones: List[str]) -> List[str]:
    bases = [p.rstrip("012") for p in phones]
    out = []
    for pat, which, sound in SILENT_PATTERNS:
        i = word.find(pat)
        if i < 0:
            continue
        letter = pat[which]
        if sound not in bases and (pat != "st" or word.endswith("stle") or word.endswith("sten")):
            if pat == "gh" and ("F" in bases and word.endswith("gh")):
                continue
            if pat == "wh" and "HH" in bases:
                continue
            out.append(f"{letter} في {pat}")
    if word.startswith("h") and bases and bases[0] != "HH" and word[:4] in ("hour", "hone", "heir"):
        out.append("h في أوّل الكلمة")
    return out


def common(n: int = 3000) -> List[Pron]:
    ws = sorted(load().items(), key=lambda kv: -kv[1][1])[:n]
    return [Pron(w, ph, f) for w, (ph, f) in ws if f > 0]


@dataclass
class Question:
    prompt: str
    options: List[str]
    answer: str
    explanation: str


def make_question(kind: str = "rhyme", rng: Optional[random.Random] = None) -> Optional[Question]:
    rng = rng or random.Random()
    pool = common(2500)
    if len(pool) < 20:
        return None
    for _ in range(40):
        p = rng.choice(pool)
        if kind == "rhyme":
            rs = [r for r in rhymes(p.word, 15) if lookup(r).freq > 0 and r[-2:] != p.word[-2:]] or \
                 [r for r in rhymes(p.word, 15) if lookup(r).freq > 0]
            if not rs:
                continue
            right = rng.choice(rs)
            wrong = []
            key = p.rhyme_key()
            for q in rng.sample(pool, 30):
                if q.word not in (p.word, right) and q.rhyme_key() != key and q.syllables == lookup(right).syllables:
                    wrong.append(q.word)
                if len(wrong) == 3:
                    break
            if len(wrong) < 3:
                continue
            opts = wrong + [right]
            rng.shuffle(opts)
            return Question(f"أيّ كلمة تقافي {p.word}؟", opts, right,
                            f"{p.word} {p.ipa()} و{right} {lookup(right).ipa()} تنتهيان بالصوت نفسه.")
        if kind == "stress":
            if p.syllables < 2 or p.syllables > 4:
                continue
            opts = [f"المقطع {ORDINAL[i]}" for i in range(p.syllables)]
            right = opts[p.stress]
            return Question(f"على أيّ مقطع يقع النبر في {p.word}؟", opts, right, p.describe())
        if kind == "syllables":
            n = p.syllables
            opts = [str(k) for k in sorted({n, max(1, n - 1), n + 1, n + 2 if n > 1 else 3})][:4]
            if str(n) not in opts:
                continue
            return Question(f"كم مقطعًا في {p.word}؟", opts, str(n), p.describe())
    return None


QUIZ_KINDS = [("القافية", "rhyme"), ("موضع النبر", "stress"), ("عدد المقاطع", "syllables")]
