# -*- coding: utf-8 -*-
"""
abaAcademy.tools.morse
======================

Morse code for Arabic and Latin text: encoding, decoding, tone rendering and a
graded lesson order for the listening trainer.

The Arabic table is the standard Arabic Morse alphabet (each Arabic letter
shares its code with a Latin letter or extended character, e.g. ا = A,
ت = T, ع = Ä). Latin letters, digits and common punctuation follow the ITU
recommendation M.1677.

Morse is a natural skill for blind learners: it is entirely auditory or
tactile (it can be tapped on one key), and practising it trains rhythm
recognition and short-term auditory memory.

Timing follows the PARIS standard: one dot = 1.2 / WPM seconds; a dash is
three dots; one dot of silence between symbols, three between letters and
seven between words. "Farnsworth" spacing stretches only the gaps, so letters
keep their real speed while the learner gets time to think.
"""

from __future__ import annotations

import math
import random
import struct
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

ARABIC: Dict[str, str] = {
    "ا": ".-", "ب": "-...", "ت": "-", "ث": "-.-.", "ج": ".---", "ح": "....",
    "خ": "---", "د": "-..", "ذ": "--..", "ر": ".-.", "ز": "---.", "س": "...",
    "ش": "----", "ص": "-..-", "ض": "...-", "ط": "..-", "ظ": "-.--", "ع": ".-.-",
    "غ": "--.", "ف": "..-.", "ق": "--.-", "ك": "-.-", "ل": ".-..", "م": "--",
    "ن": "-.", "ه": "..-..", "و": ".--", "ي": "..", "ء": ".",
}

LATIN: Dict[str, str] = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
}

DIGITS: Dict[str, str] = {
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
}

PUNCTUATION: Dict[str, str] = {
    ".": ".-.-.-", ",": "--..--", "?": "..--..", "'": ".----.", "!": "-.-.--",
    "/": "-..-.", "(": "-.--.", ")": "-.--.-", ":": "---...", "=": "-...-",
    "+": ".-.-.", "-": "-....-", '"': ".-..-.", "@": ".--.-.",
}

# Arabic letter forms folded onto the base letter the table carries
_ARABIC_FOLD = {
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ئ": "ي", "ؤ": "و",
    "ة": "ه", "،": ",", "؟": "?", "؛": ";",
}
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_TASHKEEL = set("ًٌٍَُِّْٰـ")

ARABIC_NAMES = {
    "ا": "ألف", "ب": "باء", "ت": "تاء", "ث": "ثاء", "ج": "جيم", "ح": "حاء",
    "خ": "خاء", "د": "دال", "ذ": "ذال", "ر": "راء", "ز": "زاي", "س": "سين",
    "ش": "شين", "ص": "صاد", "ض": "ضاد", "ط": "طاء", "ظ": "ظاء", "ع": "عين",
    "غ": "غين", "ف": "فاء", "ق": "قاف", "ك": "كاف", "ل": "لام", "م": "ميم",
    "ن": "نون", "ه": "هاء", "و": "واو", "ي": "ياء", "ء": "همزة",
}

ALPHABETS = {"ar": "العربية", "en": "اللاتينية"}


def table(alphabet: str = "ar") -> Dict[str, str]:
    base = dict(ARABIC if alphabet == "ar" else LATIN)
    base.update(DIGITS)
    base.update(PUNCTUATION)
    return base


def reverse_table(alphabet: str = "ar") -> Dict[str, str]:
    out = {}
    # letters win over punctuation when two share a code
    for ch, code in list(PUNCTUATION.items()) + list(DIGITS.items()) + \
            list((ARABIC if alphabet == "ar" else LATIN).items()):
        out[code] = ch
    return out


def normalise(text: str, alphabet: str = "ar") -> str:
    t = "".join(ch for ch in text if ch not in _TASHKEEL)
    t = t.translate(_ARABIC_DIGITS)
    if alphabet == "ar":
        t = "".join(_ARABIC_FOLD.get(ch, ch) for ch in t)
    else:
        t = t.upper()
    return t


def encode(text: str, alphabet: str = "ar") -> str:
    """Text -> Morse with one space between letters and ' / ' between words.
    Characters with no Morse code are skipped."""
    tab = table(alphabet)
    words = []
    for word in normalise(text, alphabet).split():
        codes = [tab[ch] for ch in word if ch in tab]
        if codes:
            words.append(" ".join(codes))
    return " / ".join(words)


def decode(morse: str, alphabet: str = "ar") -> str:
    """Morse (letters separated by spaces, words by '/' or three spaces) ->
    text. Unknown codes become '؟'."""
    rev = reverse_table(alphabet)
    m = morse.replace("•", ".").replace("_", "-").replace("–", "-")
    m = m.replace("   ", " / ")
    out_words = []
    for chunk in m.split("/"):
        letters = [rev.get(code, "؟") for code in chunk.split() if code]
        if letters:
            out_words.append("".join(letters))
    return " ".join(out_words)


def spoken_code(code: str) -> str:
    """'.-' -> 'نقطة شرطة' for the screen reader."""
    names = {".": "نقطة", "-": "شرطة"}
    return " ".join(names[c] for c in code if c in names)


def rhythm_word(code: str) -> str:
    """'.-' -> 'دي داه', the way radio operators learn to *hear* letters."""
    names = {".": "دي", "-": "داه"}
    return " ".join(names[c] for c in code if c in names)


def letter_name(ch: str, alphabet: str = "ar") -> str:
    if alphabet == "ar":
        return ARABIC_NAMES.get(ch, ch)
    return ch


# ---------------------------------------------------------------------------
# timing and tones
# ---------------------------------------------------------------------------

@dataclass
class Timing:
    wpm: float = 15.0                 # character speed
    farnsworth_wpm: float = 0.0       # effective speed for gaps (0 = same)

    @property
    def dot(self) -> float:
        return 1.2 / max(1.0, self.wpm)

    @property
    def gap_unit(self) -> float:
        """Length of one unit of *inter-letter/word* silence. With Farnsworth
        spacing the letters stay fast and only these gaps grow."""
        f = self.farnsworth_wpm
        if not f or f >= self.wpm:
            return self.dot
        # ARRL formula: total delay spread over the 19 gap units in PARIS
        ta = (60 * self.wpm - 37.2 * f) / (self.wpm * f)
        return ta / 19.0

    def letter_gap(self) -> float:
        return 3 * self.gap_unit

    def word_gap(self) -> float:
        return 7 * self.gap_unit


def events(morse: str, timing: Optional[Timing] = None) -> List[Tuple[bool, float]]:
    """(tone_on, seconds) pairs for a Morse string produced by ``encode``."""
    timing = timing or Timing()
    dot = timing.dot
    out: List[Tuple[bool, float]] = []
    words = [w.strip() for w in morse.split("/")]
    for wi, word in enumerate(words):
        letters = word.split()
        for li, code in enumerate(letters):
            for si, sym in enumerate(code):
                out.append((True, dot if sym == "." else 3 * dot))
                if si < len(code) - 1:
                    out.append((False, dot))
            if li < len(letters) - 1:
                out.append((False, timing.letter_gap()))
        if wi < len(words) - 1:
            out.append((False, timing.word_gap()))
    return out


def duration(morse: str, timing: Optional[Timing] = None) -> float:
    return sum(d for _, d in events(morse, timing))


def render_pcm(morse: str, timing: Optional[Timing] = None, freq: float = 650.0,
               sample_rate: int = 22050, amp: float = 0.4,
               lead_in: float = 0.08) -> bytes:
    """Stereo 16-bit PCM for the Morse string. Each tone has a 5 ms raised-
    cosine ramp so it doesn't click."""
    timing = timing or Timing()
    frames = bytearray()
    silence = struct.pack("<hh", 0, 0)
    frames += silence * int(lead_in * sample_rate)
    ramp = max(1, int(0.005 * sample_rate))
    step = 2 * math.pi * freq / sample_rate
    for on, secs in events(morse, timing):
        n = max(1, int(secs * sample_rate))
        if not on:
            frames += silence * n
            continue
        for i in range(n):
            env = 1.0
            if i < ramp:
                env = 0.5 - 0.5 * math.cos(math.pi * i / ramp)
            elif i >= n - ramp:
                env = 0.5 - 0.5 * math.cos(math.pi * (n - i) / ramp)
            v = int(amp * env * math.sin(step * i) * 32767)
            frames += struct.pack("<hh", v, v)
    frames += silence * int(0.05 * sample_rate)
    return bytes(frames)


# ---------------------------------------------------------------------------
# keyed input: turning key-down durations back into dots and dashes
# ---------------------------------------------------------------------------

class KeyDecoder:
    """Turns presses of a single key (Space) into Morse. Feed it press and
    release times in seconds; a press shorter than two dots is a dot, longer
    is a dash; a silence longer than two dots ends the letter, longer than
    five dots ends the word. The dot length adapts to the learner's own
    rhythm as they key."""

    def __init__(self, wpm: float = 12.0, alphabet: str = "ar"):
        self.dot = 1.2 / wpm
        self.alphabet = alphabet
        self._rev = reverse_table(alphabet)
        self._symbols = ""
        self._letters: List[str] = []
        self._words: List[str] = []
        self._down_at: Optional[float] = None
        self._up_at: Optional[float] = None

    def press(self, t: float) -> None:
        if self._up_at is not None:
            self._gap(t - self._up_at)
        self._down_at = t

    def release(self, t: float) -> str:
        if self._down_at is None:
            return ""
        held = t - self._down_at
        sym = "." if held < 2 * self.dot else "-"
        # adapt: a dot is about one unit, a dash about three
        unit = held if sym == "." else held / 3.0
        self.dot = 0.8 * self.dot + 0.2 * max(0.03, min(0.4, unit))
        self._symbols += sym
        self._down_at = None
        self._up_at = t
        return sym

    def idle(self, t: float) -> None:
        """Call periodically; closes a letter/word after enough silence."""
        if self._up_at is not None and self._down_at is None:
            self._gap(t - self._up_at, final=True)

    def _gap(self, secs: float, final: bool = False) -> None:
        if secs >= 2 * self.dot and self._symbols:
            self._letters.append(self._rev.get(self._symbols, "؟"))
            self._symbols = ""
        if secs >= 5 * self.dot and self._letters:
            self._words.append("".join(self._letters))
            self._letters = []
            if final:
                self._up_at = None

    @property
    def pending(self) -> str:
        return self._symbols

    def text(self) -> str:
        parts = list(self._words)
        if self._letters:
            parts.append("".join(self._letters))
        return " ".join(parts)

    def clear(self) -> None:
        self._symbols = ""
        self._letters = []
        self._words = []
        self._down_at = self._up_at = None


# ---------------------------------------------------------------------------
# lessons (Koch method)
# ---------------------------------------------------------------------------

# The Koch method starts with two letters at full speed and adds one letter
# each time the learner reaches 90% accuracy. Orders chosen so early letters
# sound very different from each other.
KOCH_ORDER = {
    "ar": list("مكرسنتايلعوبدجحشفقصطضزغخذثظهء"),
    "en": list("KMRSUAPTLOWI.NJEF0YVG5/Q9ZH38B?427C1D6X"),
}


def lesson_letters(alphabet: str, lesson: int) -> List[str]:
    """Letters available at a lesson (lesson 1 = first two letters)."""
    order = KOCH_ORDER.get(alphabet, KOCH_ORDER["ar"])
    n = max(2, min(len(order), lesson + 1))
    return order[:n]


def lesson_count(alphabet: str) -> int:
    return len(KOCH_ORDER.get(alphabet, KOCH_ORDER["ar"])) - 1


def practice_group(alphabet: str, lesson: int, rng: Optional[random.Random] = None,
                   size: int = 5, favour_new: bool = True) -> str:
    """A random group of letters for listening practice, weighted towards the
    newest letter so it gets the attention it needs."""
    rng = rng or random.Random()
    letters = lesson_letters(alphabet, lesson)
    newest = letters[-1]
    out = []
    for _ in range(size):
        if favour_new and rng.random() < 0.35:
            out.append(newest)
        else:
            out.append(rng.choice(letters))
    return "".join(out)


def score(expected: str, answer: str, alphabet: str = "ar") -> Tuple[int, int]:
    """(correct letters, total) comparing position by position after
    normalisation; spaces are ignored."""
    e = [c for c in normalise(expected, alphabet) if not c.isspace()]
    a = [c for c in normalise(answer, alphabet) if not c.isspace()]
    correct = sum(1 for x, y in zip(e, a) if x == y)
    return correct, len(e)


def confusable(code: str, alphabet: str = "ar", limit: int = 3) -> List[str]:
    """Letters whose code is one symbol away — the ones a learner mixes up."""
    tab = ARABIC if alphabet == "ar" else LATIN
    out = []
    for ch, c in tab.items():
        if c == code:
            continue
        if len(c) == len(code) and sum(x != y for x, y in zip(c, code)) == 1:
            out.append(ch)
        elif abs(len(c) - len(code)) == 1 and (c.startswith(code) or code.startswith(c)):
            out.append(ch)
    return out[:limit]


def multiple_choice(alphabet: str, lesson: int, rng: Optional[random.Random] = None,
                    options: int = 4) -> Tuple[str, List[str]]:
    """A letter to recognise by ear and plausible options (confusable codes
    first)."""
    rng = rng or random.Random()
    letters = lesson_letters(alphabet, lesson)
    target = rng.choice(letters)
    tab = table(alphabet)
    pool = [c for c in confusable(tab[target], alphabet) if c in letters]
    others = [c for c in letters if c != target and c not in pool]
    rng.shuffle(others)
    choices = [target] + (pool + others)[:options - 1]
    rng.shuffle(choices)
    return target, choices
