# -*- coding: utf-8 -*-
"""
abaAcademy.arabic_lab.arud
==========================

Arabic prosody (علم العروض) for a fully vowelled line of poetry:

1. **Prosodic writing** (الكتابة العروضية): what is pronounced is written and
   what is silent is dropped — shadda becomes two letters, tanween becomes a
   nun, hamzat al-wasl and the lam of the definite article fall away where
   they are not pronounced, the hidden alif of هذا / ذلك / لكن / الله is
   restored, and the last vowel of the line is lengthened (الإشباع).
2. **Scansion** (التقطيع): every pronounced letter becomes ``/`` (متحرّك)
   or ``0`` (ساكن).
3. **Metre identification** (البحر): the pattern is matched against the
   sixteen metres of al-Khalil and al-Akhfash with their common permitted
   variations (الزحافات والعلل الشائعة), full (تامّ) and shortened (مجزوء)
   forms, and the matching feet (التفعيلات) are reported.

The analyser works on the vowels the learner writes. Unvowelled letters are
treated as voweled (متحرّكة), except long-vowel letters, so the screen asks
for full vowelling and says which letters it had to guess.

Internally a voweled letter is ``1`` and a quiescent one ``0``; the display
uses the traditional ``/`` and ``0``. Pure standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# characters
# ---------------------------------------------------------------------------

FATHA, DAMMA, KASRA = "َ", "ُ", "ِ"
SUKUN, SHADDA = "ْ", "ّ"
FATHATAN, DAMMATAN, KASRATAN = "ً", "ٌ", "ٍ"
DAGGER_ALIF = "ٰ"
TATWEEL = "ـ"
WASLA_ALIF = "ٱ"

_VOWELS = {FATHA: "a", DAMMA: "u", KASRA: "i"}
_TANWEEN = {FATHATAN: "a", DAMMATAN: "u", KASRATAN: "i"}
_MARKS = set(_VOWELS) | set(_TANWEEN) | {SUKUN, SHADDA, DAGGER_ALIF}

ARABIC_LETTERS = set("ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهوىي" + WASLA_ALIF)
SUN_LETTERS = set("تثدذرزسشصضطظلن")
_LONG_FOR = {"a": "ا", "u": "و", "i": "ي"}

# words whose pronunciation has a long vowel the spelling omits, or drops a
# letter the spelling keeps. skeleton -> ("insert", index) puts a silent-free
# alif after that letter; ("drop", index) removes that letter.
_LEXICAL = {
    "هذا": ("insert", 0), "هذه": ("insert", 0), "هذان": ("insert", 0),
    "هذين": ("insert", 0), "هؤلاء": ("insert", 0), "وهذا": ("insert", 1),
    "فهذا": ("insert", 1), "وهذه": ("insert", 1), "ذلك": ("insert", 0),
    "ذلكم": ("insert", 0), "ذلكما": ("insert", 0), "كذلك": ("insert", 1),
    "وذلك": ("insert", 1), "فذلك": ("insert", 1), "لذلك": ("insert", 1),
    "لكن": ("insert", 0), "ولكن": ("insert", 1), "لكنه": ("insert", 0),
    "لكنها": ("insert", 0), "الله": ("insert", 2), "لله": ("insert", 1),
    "والله": ("insert", 3), "بالله": ("insert", 3), "تالله": ("insert", 3),
    "فالله": ("insert", 3), "اللهم": ("insert", 2), "الرحمن": ("insert", 4),
    "إله": ("insert", 1), "إلهي": ("insert", 1), "إلها": ("insert", 1),
    "طه": ("insert", 0), "أولئك": ("drop", 1), "أولو": ("drop", 1),
    "أولي": ("drop", 1), "أولات": ("drop", 1), "عمرو": ("drop", 3),
}

BINARY_DISPLAY = {"1": "/", "0": "0"}


def strip_tashkeel(text: str) -> str:
    return "".join(ch for ch in text if ch not in _MARKS and ch != TATWEEL)


def to_display(pattern: str) -> str:
    """'11010' -> '//0/0' (traditional notation)."""
    return "".join(BINARY_DISPLAY.get(c, c) for c in pattern)


def from_display(text: str) -> str:
    """Accept '/' and '0' (or 'ه' / 'o' for sukun) and return the 1/0 form."""
    out = []
    for ch in text:
        if ch in "/|1":
            out.append("1")
        elif ch in "0oOهْ":
            out.append("0")
    return "".join(out)


# ---------------------------------------------------------------------------
# scansion
# ---------------------------------------------------------------------------

@dataclass
class Unit:
    """One written letter and the marks on it."""
    letter: str
    vowel: str = ""          # 'a' | 'u' | 'i' | '' (none)
    sukun: bool = False
    shadda: bool = False
    tanween: bool = False
    dagger: bool = False

    @property
    def marked(self) -> bool:
        return bool(self.vowel or self.sukun or self.shadda)


@dataclass
class Phone:
    """One pronounced sound: a letter that is either voweled or quiescent."""
    letter: str
    moving: bool
    vowel: str = ""
    word: int = 0
    guessed: bool = False

    @property
    def bit(self) -> str:
        return "1" if self.moving else "0"


@dataclass
class Scansion:
    text: str
    phones: List[Phone]
    guessed_letters: List[str] = field(default_factory=list)

    @property
    def pattern(self) -> str:
        return "".join(p.bit for p in self.phones)

    @property
    def display(self) -> str:
        return to_display(self.pattern)

    @property
    def prosodic_writing(self) -> str:
        return "".join(p.letter for p in self.phones)


def _parse_word(word: str) -> List[Unit]:
    units: List[Unit] = []
    for ch in word:
        if ch == TATWEEL:
            continue
        if ch in ARABIC_LETTERS:
            units.append(Unit(ch))
            continue
        if not units:
            continue
        u = units[-1]
        if ch in _VOWELS:
            u.vowel = _VOWELS[ch]
        elif ch in _TANWEEN:
            u.vowel = _TANWEEN[ch]
            u.tanween = True
        elif ch == SUKUN:
            u.sukun = True
        elif ch == SHADDA:
            u.shadda = True
        elif ch == DAGGER_ALIF:
            u.dagger = True
    return units


def _apply_lexical(units: List[Unit]) -> List[Unit]:
    skeleton = "".join(u.letter for u in units)
    rule = _LEXICAL.get(skeleton)
    if not rule:
        return units
    kind, idx = rule
    units = list(units)
    if kind == "insert" and idx < len(units):
        # don't double an alif the writer already restored (هاذا)
        if idx + 1 < len(units) and units[idx + 1].letter == "ا":
            return units
        if not units[idx].vowel:
            units[idx].vowel = "a"
        units.insert(idx + 1, Unit("ا", sukun=True))
    elif kind == "drop" and idx < len(units):
        del units[idx]
    return units


def _is_wasl_start(units: List[Unit]) -> bool:
    """Bare alif at the start of a word = hamzat al-wasl (اكتب، استخرج، ال)."""
    return bool(units) and units[0].letter in ("ا", WASLA_ALIF) and not units[0].vowel


def _word_phones(units: List[Unit], word_index: int, line_start: bool,
                 guessed: List[str]) -> List[Phone]:
    units = _apply_lexical(units)
    out: List[Phone] = []
    n = len(units)
    i = 0
    # -- hamzat al-wasl --------------------------------------------------
    article_at = -1                 # index of the alif of ال, if any
    if _is_wasl_start(units):
        if n >= 2 and units[1].letter == "ل":
            article_at = 0
        if line_start:
            vowel = "a" if article_at == 0 else "i"
            out.append(Phone("ا", True, vowel, word_index))
        i = 1
    elif (n >= 3 and units[0].letter in "وفبكل" and units[0].vowel
          and units[1].letter == "ا" and not units[1].vowel
          and units[2].letter == "ل"):
        # و/ف/ب/ك/ل + ال : the alif is silent
        out.append(Phone(units[0].letter, True, units[0].vowel, word_index))
        article_at = 1
        i = 2

    while i < n:
        u = units[i]
        nxt = units[i + 1] if i + 1 < n else None
        prev = units[i - 1] if i > 0 else None

        # lam of the definite article
        if article_at >= 0 and i == article_at + 1 and u.letter == "ل" and not u.vowel:
            if nxt is not None and (nxt.shadda or (nxt.letter in SUN_LETTERS
                                                   and not nxt.sukun)):
                if nxt.letter == "ل" and nxt.sukun:
                    pass
                if not nxt.shadda and nxt.letter in SUN_LETTERS:
                    nxt.shadda = True        # assimilation the writer left out
                i += 1
                continue
            out.append(Phone("ل", False, "", word_index))
            i += 1
            continue

        # silent alif / alif maqsura after tanween al-fath (كتاباً، هدًى)
        if u.letter in ("ا", "ى") and prev is not None and prev.tanween and not u.marked:
            i += 1
            continue

        # alif after waw al-jama'a at the end of a word (كتبوا)
        if (u.letter == "ا" and i == n - 1 and prev is not None
                and prev.letter == "و" and not u.marked
                and (prev.sukun or not prev.vowel)):
            i += 1
            continue

        # آ = hamza + long alif
        if u.letter == "آ":
            out.append(Phone("ء", True, "a", word_index))
            out.append(Phone("ا", False, "", word_index))
            i += 1
            continue

        if u.shadda:
            out.append(Phone(u.letter, False, "", word_index))
            if u.vowel:
                out.append(Phone(u.letter, True, u.vowel, word_index))
            else:
                out.append(Phone(u.letter, True, "a", word_index, guessed=True))
                guessed.append(u.letter)
            if u.tanween:
                out.append(Phone("ن", False, "", word_index))
            if u.dagger:
                out.append(Phone("ا", False, "", word_index))
            i += 1
            continue

        if u.vowel:
            letter = "ت" if u.letter == "ة" else u.letter
            out.append(Phone(letter, True, u.vowel, word_index))
            if u.tanween:
                out.append(Phone("ن", False, "", word_index))
            if u.dagger:
                out.append(Phone("ا", False, "", word_index))
            i += 1
            continue

        if u.sukun:
            letter = "ه" if u.letter == "ة" else u.letter
            out.append(Phone(letter, False, "", word_index))
            i += 1
            continue

        # unmarked letter
        if u.letter in ("ا", "ى"):
            out.append(Phone("ا", False, "", word_index))
        elif u.letter == "و" and prev is not None and prev.vowel == "u":
            out.append(Phone("و", False, "", word_index))
        elif u.letter == "ي" and prev is not None and prev.vowel == "i":
            out.append(Phone("ي", False, "", word_index))
        elif u.dagger:
            out.append(Phone(u.letter, True, "a", word_index))
            out.append(Phone("ا", False, "", word_index))
        else:
            out.append(Phone(u.letter, True, "", word_index, guessed=True))
            guessed.append(u.letter)
        i += 1
    return out


def scan(text: str) -> Scansion:
    """Scan one line (a hemistich or a whole verse)."""
    words = [w for w in text.replace("،", " ").replace(",", " ").split() if w]
    phones: List[Phone] = []
    guessed: List[str] = []
    for wi, word in enumerate(words):
        units = _parse_word(word)
        if not units:
            continue
        phones.extend(_word_phones(units, wi, line_start=(wi == 0), guessed=guessed))

    # two quiescents meeting: a long vowel before another sakin is dropped
    # (التقاء الساكنين: فِي الدَّار -> فِدْدَار)
    cleaned: List[Phone] = []
    for p in phones:
        if (cleaned and not p.moving and not cleaned[-1].moving
                and cleaned[-1].letter in "اوي" and p.word != cleaned[-1].word):
            cleaned.pop()
        cleaned.append(p)
    phones = cleaned

    # a line never starts with a quiescent letter
    while phones and not phones[0].moving:
        phones.pop(0)

    # lengthen the final vowel (الإشباع)
    if phones and phones[-1].moving:
        v = phones[-1].vowel or "i"
        phones.append(Phone(_LONG_FOR[v], False, "", phones[-1].word))
    return Scansion(text, phones, guessed)


# ---------------------------------------------------------------------------
# feet and metres
# ---------------------------------------------------------------------------

# foot name -> 1/0 pattern
FEET: Dict[str, str] = {
    # فعولن and its variants
    "فَعُولُنْ": "11010", "فَعُولُ": "1101", "فَعُو": "110", "فَعُولْ": "1100",
    # مفاعيلن
    "مَفَاعِيلُنْ": "1101010", "مَفَاعِلُنْ": "110110", "مَفَاعِيلُ": "110101",
    # فاعلن
    "فَاعِلُنْ": "10110", "فَعِلُنْ": "1110", "فِعْلُنْ": "1010", "فَاعِلَانْ": "101100",
    # مستفعلن
    "مُسْتَفْعِلُنْ": "1010110", "مُتَفْعِلُنْ": "110110", "مُفْتَعِلُنْ": "101110",
    "فَعِلَتُنْ": "11110", "مَفْعُولُنْ": "101010",
    # فاعلاتن
    "فَاعِلَاتُنْ": "1011010", "فَعِلَاتُنْ": "111010", "فَاعِلَاتُ": "101101",
    "فَعِلَاتُ": "11101", "فَاعِلَاتْ": "101100",
    # متفاعلن
    "مُتَفَاعِلُنْ": "1110110", "مُتْفَاعِلُنْ": "1010110", "مُتَفَاعِلْ": "111010",
    "مُتْفَاعِلْ": "101010", "مُتَفَا": "1110", "مُتْفَا": "1010",
    "مُتَفَاعِلَانْ": "11101100",
    # مفاعلتن
    "مُفَاعَلَتُنْ": "1101110", "مُفَاعَلْتُنْ": "1101010",
    # مفعولات
    "مَفْعُولَاتُ": "1010101", "مَعُولَاتُ": "110101", "مَفْعُلَاتُ": "101101",
    "مَفْعُلَا": "10110",
}

# a slot is a tuple of allowed foot names; the canonical foot comes first
Slot = Tuple[str, ...]

F_FAULUN = ("فَعُولُنْ", "فَعُولُ")
F_FAULUN_END = ("فَعُولُنْ", "فَعُو", "فَعُولْ")
F_MAFAEELUN = ("مَفَاعِيلُنْ", "مَفَاعِيلُ", "مَفَاعِلُنْ")
F_FAILUN = ("فَاعِلُنْ", "فَعِلُنْ")
F_FAILUN_ANY = ("فَاعِلُنْ", "فَعِلُنْ", "فِعْلُنْ")
F_MUSTAF = ("مُسْتَفْعِلُنْ", "مُتَفْعِلُنْ", "مُفْتَعِلُنْ")
F_MUSTAF_RAJAZ = ("مُسْتَفْعِلُنْ", "مُتَفْعِلُنْ", "مُفْتَعِلُنْ", "فَعِلَتُنْ")
F_FAILATUN = ("فَاعِلَاتُنْ", "فَعِلَاتُنْ", "فَاعِلَاتُ", "فَعِلَاتُ")
F_FAILATUN_END = ("فَاعِلَاتُنْ", "فَعِلَاتُنْ", "فَاعِلَاتْ", "مَفْعُولُنْ")
F_MUTAFA = ("مُتَفَاعِلُنْ", "مُتْفَاعِلُنْ")
F_MUFAALA = ("مُفَاعَلَتُنْ", "مُفَاعَلْتُنْ")


@dataclass(frozen=True)
class MetreForm:
    label: str                       # "تامّ" / "مجزوء" / "مشطور"
    slots: Tuple[Slot, ...]


@dataclass(frozen=True)
class Metre:
    key: str
    name: str
    feet: str                        # the canonical feet, as a line of text
    miftah: str                      # Safi al-Din al-Hilli's mnemonic line
    forms: Tuple[MetreForm, ...]

    @property
    def canonical_pattern(self) -> str:
        return "".join(FEET[s[0]] for s in self.forms[0].slots)


METRES: Tuple[Metre, ...] = (
    Metre("tawil", "الطويل", "فَعُولُنْ مَفَاعِيلُنْ فَعُولُنْ مَفَاعِيلُنْ",
          "طَوِيلٌ لَهُ دُونَ البُحُورِ فَضَائِلُ — فَعُولُنْ مَفَاعِيلُنْ فَعُولُنْ مَفَاعِلُ",
          (MetreForm("تامّ", (F_FAULUN, F_MAFAEELUN, F_FAULUN,
                              ("مَفَاعِلُنْ", "مَفَاعِيلُنْ", "فَعُولُنْ"))),)),
    Metre("madid", "المديد", "فَاعِلَاتُنْ فَاعِلُنْ فَاعِلَاتُنْ",
          "لِمَدِيدِ الشِّعْرِ عِنْدِي صِفَاتُ — فَاعِلَاتُنْ فَاعِلُنْ فَاعِلَاتُ",
          (MetreForm("مجزوء", (("فَاعِلَاتُنْ", "فَعِلَاتُنْ"), F_FAILUN,
                               ("فَاعِلَاتُنْ", "فَعِلَاتُنْ", "فَاعِلُنْ", "فَعِلُنْ",
                                "فَاعِلَاتْ", "فِعْلُنْ"))),)),
    Metre("basit", "البسيط", "مُسْتَفْعِلُنْ فَاعِلُنْ مُسْتَفْعِلُنْ فَاعِلُنْ",
          "إِنَّ البَسِيطَ لَدَيْهِ يُبْسَطُ الأَمَلُ — مُسْتَفْعِلُنْ فَعِلُنْ مُسْتَفْعِلُنْ فَعِلُ",
          (MetreForm("تامّ", (F_MUSTAF, F_FAILUN, F_MUSTAF, ("فَعِلُنْ", "فِعْلُنْ"))),
           MetreForm("مجزوء", (F_MUSTAF, F_FAILUN,
                               ("مُسْتَفْعِلُنْ", "مُتَفْعِلُنْ", "مَفْعُولُنْ"))))),
    Metre("wafir", "الوافر", "مُفَاعَلَتُنْ مُفَاعَلَتُنْ فَعُولُنْ",
          "بُحُورُ الشِّعْرِ وَافِرُهَا جَمِيلُ — مُفَاعَلَتُنْ مُفَاعَلَتُنْ فَعُولُ",
          (MetreForm("تامّ", (F_MUFAALA, F_MUFAALA, ("فَعُولُنْ",))),
           MetreForm("مجزوء", (F_MUFAALA, F_MUFAALA)))),
    Metre("kamil", "الكامل", "مُتَفَاعِلُنْ مُتَفَاعِلُنْ مُتَفَاعِلُنْ",
          "كَمَلَ الجَمَالُ مِنَ البُحُورِ الكَامِلُ — مُتَفَاعِلُنْ مُتَفَاعِلُنْ مُتَفَاعِلُ",
          (MetreForm("تامّ", (F_MUTAFA, F_MUTAFA,
                              ("مُتَفَاعِلُنْ", "مُتْفَاعِلُنْ", "مُتَفَاعِلْ", "مُتْفَاعِلْ",
                               "مُتَفَا", "مُتْفَا"))),
           MetreForm("مجزوء", (F_MUTAFA,
                               ("مُتَفَاعِلُنْ", "مُتْفَاعِلُنْ", "مُتَفَاعِلْ",
                                "مُتْفَاعِلْ", "مُتَفَاعِلَانْ"))))),
    Metre("hazaj", "الهزج", "مَفَاعِيلُنْ مَفَاعِيلُنْ",
          "عَلَى الأَهْزَاجِ تَسْهِيلُ — مَفَاعِيلُنْ مَفَاعِيلُ",
          (MetreForm("مجزوء", (("مَفَاعِيلُنْ", "مَفَاعِيلُ"),
                               ("مَفَاعِيلُنْ", "فَعُولُنْ"))),)),
    Metre("rajaz", "الرجز", "مُسْتَفْعِلُنْ مُسْتَفْعِلُنْ مُسْتَفْعِلُنْ",
          "فِي أَبْحُرِ الأَرْجَازِ بَحْرٌ يَسْهُلُ — مُسْتَفْعِلُنْ مُسْتَفْعِلُنْ مُسْتَفْعِلُ",
          (MetreForm("تامّ", (F_MUSTAF_RAJAZ, F_MUSTAF_RAJAZ,
                              F_MUSTAF_RAJAZ + ("مَفْعُولُنْ",))),
           MetreForm("مجزوء", (F_MUSTAF_RAJAZ, F_MUSTAF_RAJAZ + ("مَفْعُولُنْ",))))),
    Metre("ramal", "الرمل", "فَاعِلَاتُنْ فَاعِلَاتُنْ فَاعِلَاتُنْ",
          "رَمَلُ الأَبْحُرِ تَرْوِيهِ الثِّقَاتُ — فَاعِلَاتُنْ فَاعِلَاتُنْ فَاعِلَاتُ",
          (MetreForm("تامّ", (F_FAILATUN, F_FAILATUN,
                              ("فَاعِلُنْ", "فَعِلُنْ", "فَاعِلَاتُنْ", "فَعِلَاتُنْ",
                               "فَاعِلَانْ"))),
           MetreForm("مجزوء", (F_FAILATUN, F_FAILATUN_END)))),
    Metre("sari", "السريع", "مُسْتَفْعِلُنْ مُسْتَفْعِلُنْ مَفْعُولَاتُ",
          "بَحْرٌ سَرِيعٌ مَا لَهُ سَاحِلُ — مُسْتَفْعِلُنْ مُسْتَفْعِلُنْ فَاعِلُ",
          (MetreForm("تامّ", (F_MUSTAF, F_MUSTAF,
                              ("مَفْعُلَا", "فَعِلُنْ", "فَاعِلَانْ", "فِعْلُنْ"))),)),
    Metre("munsarih", "المنسرح", "مُسْتَفْعِلُنْ مَفْعُولَاتُ مُسْتَفْعِلُنْ",
          "مُنْسَرِحٌ فِيهِ يُضْرَبُ المَثَلُ — مُسْتَفْعِلُنْ فَاعِلَاتُ مُفْتَعِلُ",
          (MetreForm("تامّ", (F_MUSTAF,
                              ("مَفْعُولَاتُ", "مَعُولَاتُ", "مَفْعُلَاتُ"),
                              ("مُفْتَعِلُنْ", "مُسْتَفْعِلُنْ", "مَفْعُولُنْ"))),)),
    Metre("khafif", "الخفيف", "فَاعِلَاتُنْ مُسْتَفْعِ لُنْ فَاعِلَاتُنْ",
          "يَا خَفِيفًا خَفَّتْ بِهِ الحَرَكَاتُ — فَاعِلَاتُنْ مُسْتَفْعِ لُنْ فَاعِلَاتُ",
          (MetreForm("تامّ", (("فَاعِلَاتُنْ", "فَعِلَاتُنْ"),
                              ("مُسْتَفْعِلُنْ", "مُتَفْعِلُنْ"),
                              ("فَاعِلَاتُنْ", "فَعِلَاتُنْ", "فَاعِلُنْ", "فَعِلُنْ",
                               "مَفْعُولُنْ"))),
           MetreForm("مجزوء", (("فَاعِلَاتُنْ", "فَعِلَاتُنْ"),
                               ("مُسْتَفْعِلُنْ", "مُتَفْعِلُنْ", "فَعُولُنْ"))))),
    Metre("mudari", "المضارع", "مَفَاعِيلُنْ فَاعِلَاتُنْ",
          "تُعَدُّ المُضَارِعَاتُ — مَفَاعِيلُ فَاعِلَاتُنْ",
          (MetreForm("مجزوء", (("مَفَاعِيلُ", "مَفَاعِلُنْ"), ("فَاعِلَاتُنْ",))),)),
    Metre("muqtadab", "المقتضب", "مَفْعُولَاتُ مُسْتَفْعِلُنْ",
          "اقْتَضِبْ كَمَا سَأَلُوا — مَفْعُلَاتُ مُفْتَعِلُ",
          (MetreForm("مجزوء", (("مَفْعُلَاتُ", "مَعُولَاتُ"), ("مُفْتَعِلُنْ",))),)),
    Metre("mujtathth", "المجتث", "مُسْتَفْعِ لُنْ فَاعِلَاتُنْ",
          "إِنْ جُثَّتِ الحَرَكَاتُ — مُسْتَفْعِ لُنْ فَاعِلَاتُ",
          (MetreForm("مجزوء", (("مُسْتَفْعِلُنْ", "مُتَفْعِلُنْ"),
                               ("فَاعِلَاتُنْ", "فَعِلَاتُنْ", "مَفْعُولُنْ"))),)),
    Metre("mutaqarib", "المتقارب", "فَعُولُنْ فَعُولُنْ فَعُولُنْ فَعُولُنْ",
          "عَنِ المُتَقَارِبِ قَالَ الخَلِيلُ — فَعُولُنْ فَعُولُنْ فَعُولُنْ فَعُولُ",
          (MetreForm("تامّ", (F_FAULUN, F_FAULUN, F_FAULUN, F_FAULUN_END)),
           MetreForm("مجزوء", (F_FAULUN, F_FAULUN, F_FAULUN_END)))),
    Metre("mutadarik", "المتدارك", "فَاعِلُنْ فَاعِلُنْ فَاعِلُنْ فَاعِلُنْ",
          "حَرَكَاتُ المُحْدَثِ تَنْتَقِلُ — فَعِلُنْ فَعِلُنْ فَعِلُنْ فَعِلُ",
          (MetreForm("تامّ", (F_FAILUN_ANY, F_FAILUN_ANY, F_FAILUN_ANY,
                              F_FAILUN_ANY + ("فَاعِلَانْ",))),
           MetreForm("مجزوء", (F_FAILUN_ANY, F_FAILUN_ANY,
                               F_FAILUN_ANY + ("فَاعِلَانْ",))))),
)

METRE_BY_KEY = {m.key: m for m in METRES}


@dataclass
class FootMatch:
    name: str
    pattern: str
    letters: str
    canonical: bool


@dataclass
class MetreMatch:
    metre: Metre
    form: MetreForm
    feet: List[FootMatch]
    variations: int                  # feet that are not the canonical one

    @property
    def summary(self) -> str:
        return " ".join(f.name for f in self.feet)


def _match_form(pattern: str, form: MetreForm):
    """All ways to split ``pattern`` into the form's slots, as lists of
    (foot_name, canonical) tuples."""
    slots = form.slots

    @lru_cache(maxsize=None)
    def go(pos: int, slot: int):
        if slot == len(slots):
            return [[]] if pos == len(pattern) else []
        results = []
        for k, name in enumerate(slots[slot]):
            fp = FEET[name]
            if pattern.startswith(fp, pos):
                for rest in go(pos + len(fp), slot + 1):
                    results.append([(name, k == 0)] + rest)
        return results

    return go(0, 0)


def identify(pattern: str, phones: Optional[Sequence[Phone]] = None) -> List[MetreMatch]:
    """Every metre form the pattern fits, best (fewest variations) first."""
    out: List[MetreMatch] = []
    for metre in METRES:
        for form in metre.forms:
            for split in _match_form(pattern, form):
                feet, pos = [], 0
                for name, canonical in split:
                    fp = FEET[name]
                    letters = ""
                    if phones is not None:
                        letters = "".join(p.letter for p in phones[pos:pos + len(fp)])
                    feet.append(FootMatch(name, fp, letters, canonical))
                    pos += len(fp)
                out.append(MetreMatch(metre, form, feet,
                                      sum(1 for f in feet if not f.canonical)))
    out.sort(key=lambda m: (m.variations, METRES.index(m.metre)))
    # keep one best split per metre form
    seen, unique = set(), []
    for m in out:
        k = (m.metre.key, m.form.label)
        if k not in seen:
            seen.add(k)
            unique.append(m)
    return unique


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def nearest(pattern: str, limit: int = 3) -> List[Tuple[int, Metre, MetreForm]]:
    """Closest metres by edit distance to their canonical pattern, for a line
    that matches none exactly (usually a vowelling slip)."""
    scored = []
    for metre in METRES:
        for form in metre.forms:
            canon = "".join(FEET[s[0]] for s in form.slots)
            scored.append((_edit_distance(pattern, canon), metre, form))
    scored.sort(key=lambda t: (t[0], METRES.index(t[1])))
    return scored[:limit]


@dataclass
class Analysis:
    scansion: Scansion
    matches: List[MetreMatch]
    near: List[Tuple[int, Metre, MetreForm]]

    @property
    def best(self) -> Optional[MetreMatch]:
        return self.matches[0] if self.matches else None

    def report(self) -> str:
        sc = self.scansion
        lines = [f"الكتابة العروضية: {sc.prosodic_writing}",
                 f"الرموز: {sc.display}",
                 f"عدد المتحرّكات {sc.pattern.count('1')}، "
                 f"وعدد السواكن {sc.pattern.count('0')}."]
        if self.best:
            b = self.best
            lines.append(f"البحر: {b.metre.name} ({b.form.label}).")
            lines.append("التفعيلات: " + " | ".join(
                f"{f.letters} = {f.name}" if f.letters else f.name for f in b.feet))
            if b.variations:
                lines.append(f"فيه {b.variations} تفعيلة دخلها زحاف أو علّة.")
            if len(self.matches) > 1:
                others = "، ".join(f"{m.metre.name} ({m.form.label})" for m in self.matches[1:4])
                lines.append(f"يحتمل أيضًا: {others}.")
            lines.append(f"مفتاح البحر: {b.metre.miftah}")
        else:
            lines.append("لم يطابق النمط أيّ بحر بصورته المعروفة.")
            if self.near:
                lines.append("أقرب البحور: " + "، ".join(
                    f"{m.name} ({f.label})" for _, m, f in self.near) + ".")
            lines.append("تأكّد من ضبط الحركات والسكون والشدّة والتنوين.")
        if sc.guessed_letters:
            uniq = "، ".join(dict.fromkeys(sc.guessed_letters))
            lines.append(f"حروف بلا حركة افترضتُها متحرّكة: {uniq}.")
        return "\n".join(lines)


def analyse(text: str) -> Analysis:
    sc = scan(text)
    matches = identify(sc.pattern, sc.phones)
    near = [] if matches else nearest(sc.pattern)
    return Analysis(sc, matches, near)


def split_hemistichs(text: str) -> List[str]:
    """A verse is often written with its two halves separated by '*', '...',
    a tab or a run of spaces."""
    t = text.strip()
    for sep in ("***", "**", "*", "…", "...", "\t", "    ", "   "):
        if sep in t:
            parts = [p.strip() for p in t.split(sep) if p.strip()]
            if len(parts) == 2:
                return parts
    return [t] if t else []


# ---------------------------------------------------------------------------
# rhythm sonification
# ---------------------------------------------------------------------------

def rhythm_events(pattern: str, foot_lengths: Optional[Sequence[int]] = None,
                  short=0.11, long=0.26, gap=0.05, foot_gap=0.18):
    """(frequency, duration, pause_after) for each symbol: a short high beep for
    a voweled letter, a longer lower tone for a quiescent one, with a slightly
    longer rest between feet so the ear hears the foot boundaries."""
    boundaries = set()
    if foot_lengths:
        acc = 0
        for n in foot_lengths:
            acc += n
            boundaries.add(acc)
    events = []
    for i, c in enumerate(pattern, 1):
        if c == "1":
            freq, dur = 880.0, short
        else:
            freq, dur = 523.25, long
        events.append((freq, dur, foot_gap if i in boundaries else gap))
    return events


def metre_quiz(rng, count: int = 4):
    """A listening question: (correct_metre, options) drawn from the table."""
    pool = list(METRES)
    correct = rng.choice(pool)
    others = [m for m in pool if m is not correct]
    rng.shuffle(others)
    options = [correct] + others[:max(1, count - 1)]
    rng.shuffle(options)
    return correct, options
