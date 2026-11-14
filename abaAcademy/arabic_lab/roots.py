# -*- coding: utf-8 -*-
"""
abaAcademy.arabic_lab.roots
===========================

The root lab (مختبر الجذور): find a word's root, its morphological pattern
(الوزن), and the other words in the dictionary built on the same root.

Roots come from the ISRI stemmer (Taghva, Elkhoury and Coombs, 2005; the
NLTK implementation is vendored in ``isri.py``), which strips prefixes and
suffixes and matches the remaining stem against the common patterns. It
works without a root dictionary, so it is fast and covers the whole 294,000-
word word list, but like every rule-based stemmer it is sometimes wrong
(hollow and defective verbs are the usual cases). The lab therefore:

* reports a root only when the stemmer reaches three or four letters;
* derives the pattern by placing ف ع ل over the root letters, and calls the
  analysis *confident* only when that pattern is one of the well-known
  patterns listed below;
* builds quiz questions from confident analyses only.
"""

from __future__ import annotations

import random
import threading
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .isri import ISRIStemmer

_TASHKEEL = set("ًٌٍَُِّْٰـ")
_FOLD = {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"}

# Well-known patterns (written without vowels, as the dictionary is). An
# analysis whose pattern is here is very likely right.
KNOWN_PATTERNS: Dict[str, str] = {
    "فعل": "فَعَلَ / فِعْل / فَعْل", "فاعل": "اسم الفاعل من الثلاثي", "مفعول": "اسم المفعول من الثلاثي",
    "فعال": "فِعال / فَعال", "فعيل": "فَعِيل (صفة مشبّهة)", "فعول": "فَعُول (صيغة مبالغة)",
    "فعالة": "فِعالة / فَعالة", "فعلة": "فَعْلة / فِعْلة", "مفعل": "مَفْعَل (اسم مكان أو زمان)",
    "مفعلة": "مَفْعَلة (اسم مكان)", "مفعال": "مِفْعال (اسم آلة أو مبالغة)", "مفعيل": "مِفْعيل",
    "تفعيل": "تَفْعِيل (مصدر فعّل)", "تفعلة": "تَفْعِلة (مصدر)", "افتعال": "افْتِعال (مصدر افتعل)",
    "انفعال": "انْفِعال (مصدر انفعل)", "استفعال": "اسْتِفْعال (مصدر استفعل)",
    "تفاعل": "تَفاعُل (مصدر تفاعل)", "تفعل": "تَفَعُّل (مصدر تفعّل)", "مفاعلة": "مُفاعَلة (مصدر فاعل)",
    "يفعل": "يَفْعَلُ (المضارع)", "تفعل": "تَفْعَلُ (المضارع)", "نفعل": "نَفْعَلُ (المضارع)",
    "افعل": "أَفْعَلُ / افْعَلْ", "يفعلون": "يَفْعَلُونَ", "تفعلون": "تَفْعَلُونَ", "فعلوا": "فَعَلُوا",
    "فعلت": "فَعَلْتُ / فَعَلَتْ", "فعلنا": "فَعَلْنا", "فاعلون": "فاعِلُونَ (جمع مذكّر سالم)",
    "فاعلين": "فاعِلِينَ", "فاعلات": "فاعِلات (جمع مؤنّث سالم)", "فاعلة": "فاعِلة",
    "مفعولة": "مَفْعولة", "مفعولات": "مَفْعولات", "فعالون": "فَعّالون", "فعلاء": "فُعَلاء (جمع تكسير)",
    "افعال": "أَفْعال (جمع تكسير) / إفعال (مصدر أفعل)", "فعول": "فُعُول (جمع تكسير)",
    "مفاعل": "مَفاعِل (جمع تكسير)", "مفاعيل": "مَفاعِيل (جمع تكسير)", "فواعل": "فَواعِل (جمع تكسير)",
    "فعائل": "فَعائِل (جمع تكسير)", "مستفعل": "مُسْتَفْعِل (اسم فاعل من استفعل)",
    "مفتعل": "مُفْتَعِل (اسم فاعل من افتعل)", "منفعل": "مُنْفَعِل", "متفاعل": "مُتَفاعِل",
    "متفعل": "مُتَفَعِّل", "مفعلون": "مُفَعِّلُونَ", "فعلان": "فَعْلان / فُعْلان",
    "فعلى": "فُعْلى / فَعْلى", "فعالي": "فَعالِي", "افعل": "أَفْعَل (اسم تفضيل)",
}

PATTERN_LETTERS = ("ف", "ع", "ل")


def strip_tashkeel(word: str) -> str:
    return "".join(ch for ch in word if ch not in _TASHKEEL)


def fold(word: str) -> str:
    return "".join(_FOLD.get(ch, ch) for ch in strip_tashkeel(word.strip()))


_stemmer_lock = threading.Lock()
_stemmer = ISRIStemmer()


def raw_stem(word: str) -> str:
    with _stemmer_lock:
        return _stemmer.stem(strip_tashkeel(word))


@dataclass(frozen=True)
class RootAnalysis:
    word: str
    root: str
    pattern: str          # e.g. مفعول, or '' when it can't be placed
    confident: bool
    source: str = "stemmer"   # "quran" when the Qur'an corpus supplied the root

    @property
    def pattern_note(self) -> str:
        return KNOWN_PATTERNS.get(self.pattern, "")

    def spoken(self) -> str:
        if not self.root:
            return f"لم أستطع تحديد جذر {self.word}. قد تكون الكلمة جامدة أو أعجمية."
        parts = [f"جذر {self.word}: {' '.join(self.root)}"]
        if self.pattern:
            parts.append(f"على وزن {self.pattern}")
            if self.pattern_note:
                parts.append(f"({self.pattern_note})")
        if self.source == "quran":
            parts.append("— الجذر من معجم ألفاظ القرآن الكريم")
        elif not self.confident:
            parts.append("— تحليل تقريبيّ، فتحقّق منه")
        return " ".join(parts) + "."


def derive_pattern(word: str, root: str) -> str:
    """Put ف ع ل (and ل again for a fourth root letter) over the root letters
    as they appear in order inside the word. '' if they don't."""
    w = fold(word)
    r = fold(root)
    if len(r) not in (3, 4):
        return ""
    letters = list(PATTERN_LETTERS) if len(r) == 3 else ["ف", "ع", "ل", "ل"]
    out = []
    j = 0
    for ch in w:
        if j < len(r) and ch == r[j]:
            out.append(letters[j])
            j += 1
        else:
            out.append(ch)
    if j < len(r):
        # a doubled last radical written once (مدّ) or a weak radical that changed
        return ""
    return "".join(out)


_ARTICLES = ("وبال", "فبال", "وال", "فال", "بال", "كال", "لل", "ال")


def strip_article(word: str) -> str:
    w = fold(word)
    for a in _ARTICLES:
        if w.startswith(a) and len(w) - len(a) >= 3:
            return w[len(a):]
    return w


def analyse(word: str, bank: Optional["QuranRootBank"] = None) -> RootAnalysis:
    """Root and pattern of one word. When the Qur'an corpus knows the word
    its scholar-checked root is used; otherwise the ISRI stemmer."""
    w = strip_tashkeel(word.strip())
    if not w:
        return RootAnalysis(word, "", "", False)
    if bank is not None and bank.ready:
        hit = bank.lookup(w)
        if hit:
            root, lemma = hit[0], hit[1]
            base = strip_article(w)
            # spellings that drop a long alif (الرحمن، إله) scan by the lemma
            if lemma and base == strip_article(quran_fold(lemma)):
                base = strip_article(quran_fold(lemma, dagger_as_alif=True))
            pattern = derive_pattern(base, root)
            return RootAnalysis(word, root, pattern, True, source="quran")
    stem = raw_stem(w)
    if len(stem) not in (3, 4) or stem == w and len(w) > 4:
        return RootAnalysis(word, "", "", False)
    pattern = derive_pattern(strip_article(w), stem)
    weak = any(ch in "اىء" for ch in fold(stem))
    confident = bool(pattern) and pattern in KNOWN_PATTERNS and not weak
    return RootAnalysis(word, fold(stem), pattern, confident)


# ---------------------------------------------------------------------------
# the dictionary index
# ---------------------------------------------------------------------------

class RootIndex:
    """root -> words, built once over the dictionary in a background thread
    (about a second and a half for the full list)."""

    def __init__(self, words: Iterable[str]):
        self._words = list(words)
        self._index: Dict[str, List[str]] = {}
        self._confident: Dict[str, List[str]] = {}
        self._ready = threading.Event()
        self._building = False
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    def build(self) -> None:
        with self._lock:
            if self._building or self.ready:
                return
            self._building = True
        index: Dict[str, List[str]] = {}
        confident: Dict[str, List[str]] = {}
        stem = ISRIStemmer().stem
        for w in self._words:
            if not 3 <= len(w) <= 12:
                continue
            r = stem(w)
            if len(r) not in (3, 4):
                continue
            r = fold(r)
            index.setdefault(r, []).append(w)
            p = derive_pattern(w, r)
            if p and p in KNOWN_PATTERNS:
                confident.setdefault(r, []).append(w)
        for lst in index.values():
            lst.sort(key=lambda x: (len(x), x))
        self._index = index
        self._confident = confident
        self._ready.set()

    def build_async(self, on_ready=None) -> None:
        def run():
            try:
                self.build()
            finally:
                if on_ready:
                    on_ready()
        threading.Thread(target=run, daemon=True, name="root-index").start()

    def wait(self, timeout: Optional[float] = None) -> bool:
        return self._ready.wait(timeout)

    @classmethod
    def from_gzip_async(cls, path: str) -> "RootIndex":
        """Read the gzipped word list and build the index, both off the UI
        thread. A missing file leaves an empty (but ready) index."""
        idx = cls([])

        def run():
            import gzip
            try:
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    idx._words = [w.strip() for w in f if w.strip()]
            except Exception:
                idx._words = []
            idx.build()
        threading.Thread(target=run, daemon=True, name="root-index").start()
        return idx

    def family(self, root: str, limit: int = 60, confident_only: bool = False) -> List[str]:
        src = self._confident if confident_only else self._index
        return src.get(fold(root), [])[:limit]

    def roots(self) -> List[str]:
        return sorted(self._index)

    def size(self) -> int:
        return len(self._index)

    def rich_roots(self, minimum: int = 6) -> List[str]:
        """Roots with enough confidently analysed words to quiz on."""
        return [r for r, ws in self._confident.items() if len(set(ws)) >= minimum and len(r) == 3]


# ---------------------------------------------------------------------------
# the Qur'an corpus: scholar-checked roots and lemmas
# ---------------------------------------------------------------------------

_QURAN_MARKS = set(chr(c) for c in list(range(0x0610, 0x061B)) + list(range(0x064B, 0x0660))
                   + list(range(0x06D6, 0x06EE))) | {"\u0670", "\u0640"}


def quran_fold(word: str, dagger_as_alif: bool = False) -> str:
    out = []
    for ch in word:
        if ch == "\u0670":
            if dagger_as_alif:
                out.append("ا")
            continue
        if ch in _QURAN_MARKS:
            continue
        out.append(_FOLD.get(ch, ch))
    return "".join(out)


POS_NAMES = {"اسم": "اسم", "فعل": "فعل", "نعت": "صفة", "علم": "اسم علم"}


class QuranRootBank:
    """Every word form of the Qur'an with its root, lemma and part of speech,
    from the morphology data bundled with the Qur'an reader."""

    def __init__(self, path: str):
        self.path = path
        self._forms: Dict[str, Tuple[str, str, str]] = {}
        self._lemmas: Dict[str, Tuple[str, str, int]] = {}     # lemma -> root, pos, count
        self._by_root: Dict[str, List[str]] = {}
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._started = False
        self.error = ""

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    def load(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
        import json
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            forms, lemmas, by_root = {}, {}, {}
            for words in data.values():
                for item in words:
                    root = item.get("root") or ""
                    lemma = item.get("lemma") or ""
                    if not root or len(root) not in (3, 4):
                        continue
                    root = "".join(_FOLD.get(c, c) for c in root)
                    pos = item.get("pos") or ""
                    for key in {quran_fold(item.get("w", "")),
                                quran_fold(item.get("w", ""), dagger_as_alif=True)}:
                        if key:
                            forms.setdefault(key, (root, lemma, pos))
                    if lemma:
                        r, p, c = lemmas.get(lemma, (root, pos, 0))
                        lemmas[lemma] = (r, p, c + 1)
            for lemma, (r, p, c) in lemmas.items():
                by_root.setdefault(r, []).append(lemma)
            self._forms, self._lemmas, self._by_root = forms, lemmas, by_root
        except Exception as exc:          # missing or damaged data: lab still works
            self.error = str(exc)
        finally:
            self._ready.set()

    def load_async(self, on_ready=None) -> None:
        def run():
            try:
                self.load()
            finally:
                if on_ready:
                    on_ready()
        threading.Thread(target=run, daemon=True, name="quran-roots").start()

    def wait(self, timeout=None) -> bool:
        return self._ready.wait(timeout)

    def lookup(self, word: str) -> Optional[Tuple[str, str, str]]:
        w = quran_fold(word)
        hit = self._forms.get(w)
        if hit is None and not w.startswith("ال"):
            hit = self._forms.get("ال" + w)
        return hit

    def lemmas_of(self, root: str) -> List[str]:
        return sorted(self._by_root.get(fold(root), []),
                      key=lambda l: -self._lemmas[l][2])

    def lemma_info(self, lemma: str) -> Tuple[str, str, int]:
        return self._lemmas[lemma]

    def quiz_lemmas(self, minimum_count: int = 3) -> List[str]:
        return [l for l, (r, p, c) in self._lemmas.items()
                if c >= minimum_count and len(r) == 3 and p in ("اسم", "فعل", "نعت")
                and len(quran_fold(l)) >= 3]

    def roots(self) -> List[str]:
        return list(self._by_root)

    def stats(self) -> Tuple[int, int, int]:
        return len(self._forms), len(self._lemmas), len(self._by_root)


# ---------------------------------------------------------------------------
# practice
# ---------------------------------------------------------------------------

@dataclass
class RootQuestion:
    kind: str
    prompt: str
    answer: str
    options: List[str]
    explanation: str

    def check(self, text: str) -> bool:
        return fold(text).replace(" ", "") == fold(self.answer).replace(" ", "")


QUESTION_KINDS = {
    "root_of": "استخراج الجذر",
    "same_root": "الكلمة من الجذر نفسه",
    "pattern_of": "الوزن الصرفي",
}


def _distractor_roots(root: str, pool: Sequence[str], rng, n: int = 3) -> List[str]:
    """Roots that share two letters with the right one — the kind a learner
    would genuinely confuse — topped up with random roots."""
    close = [r for r in pool if r != root and len(r) == len(root)
             and sum(a == b for a, b in zip(r, root)) >= 2]
    rng.shuffle(close)
    picks = close[:n]
    if len(picks) < n:
        others = [r for r in pool if r != root and r not in picks and len(r) == len(root)]
        rng.shuffle(others)
        picks += others[:n - len(picks)]
    return picks


def _spaced(r: str) -> str:
    return " ".join(r)


def make_question(bank: "QuranRootBank", rng: Optional[random.Random] = None,
                  kind: Optional[str] = None) -> Optional[RootQuestion]:
    """A question drawn from the Qur'an's own vocabulary, whose roots are
    checked by scholars (so the 'right' answer is right)."""
    if not bank.ready:
        return None
    rng = rng or random.Random()
    lemmas = bank.quiz_lemmas()
    if len(lemmas) < 20:
        return None
    roots = [r for r in bank.roots() if len(r) == 3]
    kind = kind or rng.choice(list(QUESTION_KINDS))
    for _ in range(30):
        lemma = rng.choice(lemmas)
        root, pos, count = bank.lemma_info(lemma)
        if kind == "root_of":
            opts = [_spaced(root)] + [_spaced(r) for r in _distractor_roots(root, roots, rng)]
            if len(set(opts)) < 4:
                continue
            rng.shuffle(opts)
            return RootQuestion(kind, f"ما جذر كلمة {lemma}؟", _spaced(root), opts,
                                f"{lemma} من الجذر {_spaced(root)}، ووردت في القرآن الكريم "
                                f"بهذا الأصل {count} مرّة.")
        if kind == "same_root":
            others = []
            for r in _distractor_roots(root, roots, rng, 8):
                cands = [l for l in bank.lemmas_of(r) if l in set(lemmas)] or bank.lemmas_of(r)
                if cands:
                    others.append(cands[0])
                if len(others) == 3:
                    break
            if len(others) < 3:
                continue
            opts = [lemma] + others
            rng.shuffle(opts)
            return RootQuestion(kind, f"أيّ هذه الكلمات من الجذر {_spaced(root)}؟", lemma, opts,
                                f"{lemma} من الجذر {_spaced(root)}، أمّا "
                                + "، ".join(f"{o}" for o in others) + " فمن جذور أخرى.")
        # pattern_of
        bare = strip_article(quran_fold(lemma, dagger_as_alif=True))
        pattern = derive_pattern(bare, root)
        if not pattern or pattern not in KNOWN_PATTERNS:
            continue
        others = [p for p in KNOWN_PATTERNS if p != pattern and abs(len(p) - len(pattern)) <= 1]
        rng.shuffle(others)
        opts = [pattern] + others[:3]
        if len(set(opts)) < 4:
            continue
        rng.shuffle(opts)
        return RootQuestion(kind, f"ما وزن كلمة {lemma}؟", pattern, opts,
                            f"جذرها {_spaced(root)}؛ نضع الفاء والعين واللام مكان حروف الجذر "
                            f"فيكون الوزن {pattern}، وهو {KNOWN_PATTERNS[pattern]}.")
    return None
