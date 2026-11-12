# -*- coding: utf-8 -*-
"""
abaAcademy.puzzles.word_search
==============================

Word search (البحث عن الكلمات), designed for play by ear: the grid is read
row by row or column by column, the cursor moves with the arrow keys, and a
word is claimed by marking its first and last letters. Words are placed
horizontally (right-to-left, as Arabic is read), vertically downwards, and —
at the hard level — diagonally; empty cells are filled with letters drawn
from the hidden words themselves, so the fillers look plausible.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

ARABIC_LETTERS = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"

LEVELS = {
    "easy": ("سهل: ٧×٧ وخمس كلمات أفقية وعمودية", 7, 5, ((0, -1), (1, 0))),
    "medium": ("متوسّط: ٩×٩ وسبع كلمات", 9, 7, ((0, -1), (1, 0))),
    "hard": ("صعب: ١٠×١٠ وتسع كلمات، ومنها مائلة", 10, 9, ((0, -1), (1, 0), (1, -1), (1, 1))),
}

DIRECTION_NAMES = {(0, -1): "أفقيًّا من اليمين إلى اليسار", (1, 0): "عموديًّا من الأعلى إلى الأسفل",
                   (1, -1): "مائلًا إلى الأسفل واليسار", (1, 1): "مائلًا إلى الأسفل واليمين"}

THEMES = {
    "school": ("المدرسة", ["كتاب", "قلم", "دفتر", "معلم", "طالب", "مدرسة", "درس", "صف", "سبورة",
                           "حقيبة", "مكتبة", "امتحان", "واجب", "فصل"]),
    "nature": ("الطبيعة", ["شمس", "قمر", "نجم", "بحر", "نهر", "جبل", "شجرة", "وردة", "مطر", "غيم",
                           "رمل", "صخر", "غابة", "سهل"]),
    "home": ("البيت", ["باب", "نافذة", "غرفة", "سرير", "كرسي", "مطبخ", "سجادة", "مفتاح", "مصباح",
                       "طاولة", "حديقة", "سقف", "جدار"]),
    "body": ("جسم الإنسان", ["رأس", "عين", "أذن", "أنف", "فم", "يد", "رجل", "قلب", "كتف", "إصبع",
                             "ركبة", "ظهر", "لسان"]),
    "food": ("الطعام", ["خبز", "أرز", "لحم", "سمك", "تمر", "عسل", "حليب", "زيت", "ملح", "تفاح",
                        "عنب", "جبن", "بيض", "عدس"]),
}


def _norm(w: str) -> str:
    return w.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")


@dataclass
class Placed:
    word: str
    start: Tuple[int, int]
    direction: Tuple[int, int]
    found: bool = False

    @property
    def cells(self) -> List[Tuple[int, int]]:
        r, c = self.start
        dr, dc = self.direction
        return [(r + i * dr, c + i * dc) for i in range(len(_norm(self.word)))]

    @property
    def end(self) -> Tuple[int, int]:
        return self.cells[-1]


@dataclass
class Puzzle:
    size: int
    grid: List[List[str]]
    words: List[Placed]
    theme: str
    found_cells: Set[Tuple[int, int]] = field(default_factory=set)

    def letter(self, r: int, c: int) -> str:
        return self.grid[r][c]

    def col_no(self, c: int) -> int:
        """Columns are numbered from the right, the way Arabic is read."""
        return self.size - c

    def row_text(self, r: int) -> str:
        """The row read right to left, so horizontal words read correctly."""
        return " ".join(reversed(self.grid[r]))

    def col_text(self, c: int) -> str:
        return " ".join(self.grid[r][c] for r in range(self.size))

    def remaining(self) -> List[str]:
        return [p.word for p in self.words if not p.found]

    def claim(self, a: Tuple[int, int], b: Tuple[int, int]) -> Optional[Placed]:
        """Mark a word by its first and last cells (in either order)."""
        for p in self.words:
            if p.found:
                continue
            if (p.start, p.end) in ((a, b), (b, a)):
                p.found = True
                self.found_cells.update(p.cells)
                return p
        return None

    def letters_between(self, a: Tuple[int, int], b: Tuple[int, int]) -> str:
        (r1, c1), (r2, c2) = a, b
        dr = (r2 > r1) - (r2 < r1)
        dc = (c2 > c1) - (c2 < c1)
        if not (r1 == r2 or c1 == c2 or abs(r2 - r1) == abs(c2 - c1)):
            return ""
        out = []
        r, c = r1, c1
        while True:
            out.append(self.grid[r][c])
            if (r, c) == (r2, c2):
                break
            r += dr
            c += dc
        return "".join(out)

    @property
    def complete(self) -> bool:
        return all(p.found for p in self.words)

    def hint(self) -> Optional[str]:
        for p in self.words:
            if not p.found:
                r, c = p.start
                return (f"الكلمة {p.word} تبدأ في الصفّ {r + 1}، العمود {self.col_no(c)}، "
                        f"وتمتدّ {DIRECTION_NAMES[p.direction]}.")
        return None


def generate(level: str = "easy", theme: str = "school",
             rng: Optional[random.Random] = None, words: Optional[Sequence[str]] = None) -> Puzzle:
    rng = rng or random.Random()
    _, size, n_words, dirs = LEVELS[level]
    tname, pool = THEMES.get(theme, THEMES["school"])
    pool = [w for w in (words or pool) if 2 <= len(_norm(w)) <= size]
    rng.shuffle(pool)
    grid: List[List[Optional[str]]] = [[None] * size for _ in range(size)]
    placed: List[Placed] = []
    for word in sorted(pool, key=lambda w: -len(w)):
        if len(placed) >= n_words:
            break
        letters = _norm(word)
        options = []
        for d in dirs:
            for r in range(size):
                for c in range(size):
                    cells = [(r + i * d[0], c + i * d[1]) for i in range(len(letters))]
                    if not all(0 <= rr < size and 0 <= cc < size for rr, cc in cells):
                        continue
                    if all(grid[rr][cc] in (None, ch) for (rr, cc), ch in zip(cells, letters)):
                        overlap = sum(1 for (rr, cc) in cells if grid[rr][cc] is not None)
                        options.append((overlap, rng.random(), r, c, d))
        if not options:
            continue
        options.sort(reverse=True)
        _, _, r, c, d = options[0] if rng.random() < 0.3 else rng.choice(options)
        for i, ch in enumerate(letters):
            grid[r + i * d[0]][c + i * d[1]] = ch
        placed.append(Placed(word, (r, c), d))
    fill_src = "".join(_norm(p.word) for p in placed) + ARABIC_LETTERS
    for r in range(size):
        for c in range(size):
            if grid[r][c] is None:
                grid[r][c] = rng.choice(fill_src)
    return Puzzle(size, [[ch or "ا" for ch in row] for row in grid], placed, tname)
