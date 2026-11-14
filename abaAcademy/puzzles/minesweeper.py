# -*- coding: utf-8 -*-
"""
abaAcademy.puzzles.minesweeper
==============================

Minesweeper played by ear. The first uncovered cell is always safe (mines
are placed after the first click, away from it), an empty cell opens its
whole region, and the board can describe a cell's neighbourhood in words so
the player can reason without seeing the grid.

Pure standard library.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

LEVELS = {
    "tiny": ("صغير جدًّا ٥×٥", 5, 5, 3),
    "beginner": ("مبتدئ ٨×٨", 8, 8, 8),
    "intermediate": ("متوسّط ١٠×١٠", 10, 10, 15),
    "expert": ("خبير ١٢×١٢", 12, 12, 26),
}

_DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
_DIR_WORDS = {(-1, -1): "أعلى اليسار", (-1, 0): "أعلى", (-1, 1): "أعلى اليمين",
              (0, -1): "يسار", (0, 1): "يمين", (1, -1): "أسفل اليسار",
              (1, 0): "أسفل", (1, 1): "أسفل اليمين"}


@dataclass
class Minefield:
    rows: int
    cols: int
    mines: int
    rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self):
        if self.mines >= self.rows * self.cols - 1:
            raise ValueError("too many mines")
        self.mine: Set[Tuple[int, int]] = set()
        self.open: Set[Tuple[int, int]] = set()
        self.flags: Set[Tuple[int, int]] = set()
        self.placed = False
        self.lost = False
        self.exploded: Optional[Tuple[int, int]] = None
        self.moves = 0

    @classmethod
    def level(cls, key: str, rng=None):
        _, r, c, m = LEVELS[key]
        return cls(r, c, m, rng or random.Random())

    def inside(self, r, c) -> bool:
        return 0 <= r < self.rows and 0 <= c < self.cols

    def neighbours(self, r, c):
        for dr, dc in _DIRS:
            if self.inside(r + dr, c + dc):
                yield r + dr, c + dc

    def _place(self, safe: Tuple[int, int]) -> None:
        keep_clear = {safe} | set(self.neighbours(*safe))
        cells = [(r, c) for r in range(self.rows) for c in range(self.cols)
                 if (r, c) not in keep_clear]
        if len(cells) < self.mines:      # tiny boards: only the cell itself
            cells = [(r, c) for r in range(self.rows) for c in range(self.cols)
                     if (r, c) != safe]
        self.mine = set(self.rng.sample(cells, self.mines))
        self.placed = True

    def count(self, r, c) -> int:
        return sum(1 for x in self.neighbours(r, c) if x in self.mine)

    def reveal(self, r, c) -> str:
        """'flagged' | 'already' | 'boom' | 'open' | 'won'."""
        if self.lost or self.won:
            return "already"
        if (r, c) in self.flags:
            return "flagged"
        if (r, c) in self.open:
            return "already"
        if not self.placed:
            self._place((r, c))
        self.moves += 1
        if (r, c) in self.mine:
            self.lost = True
            self.exploded = (r, c)
            return "boom"
        stack = [(r, c)]
        while stack:
            cur = stack.pop()
            if cur in self.open:
                continue
            self.open.add(cur)
            self.flags.discard(cur)
            if self.count(*cur) == 0:
                stack.extend(x for x in self.neighbours(*cur) if x not in self.open)
        return "won" if self.won else "open"

    def chord(self, r, c) -> str:
        """On an open number whose flags are all placed, open the rest of its
        neighbours (a common speed move)."""
        if (r, c) not in self.open:
            return "already"
        n = self.count(r, c)
        nb = list(self.neighbours(r, c))
        if sum(1 for x in nb if x in self.flags) != n:
            return "already"
        result = "open"
        for x in nb:
            if x not in self.flags and x not in self.open:
                result = self.reveal(*x)
                if result == "boom":
                    return result
        return result

    def toggle_flag(self, r, c) -> Optional[bool]:
        if (r, c) in self.open or self.lost:
            return None
        if (r, c) in self.flags:
            self.flags.discard((r, c))
            return False
        self.flags.add((r, c))
        return True

    @property
    def won(self) -> bool:
        return self.placed and not self.lost and \
            len(self.open) == self.rows * self.cols - self.mines

    def remaining(self) -> int:
        return self.mines - len(self.flags)

    def cell_word(self, r, c) -> str:
        x = (r, c)
        if self.lost and x in self.mine:
            return "لغم انفجر" if x == self.exploded else "لغم"
        if x in self.flags:
            return "علم"
        if x not in self.open:
            return "مغلقة"
        n = self.count(r, c)
        return "فارغة" if n == 0 else str(n)

    def describe_neighbourhood(self, r, c) -> str:
        parts = []
        for dr, dc in _DIRS:
            rr, cc = r + dr, c + dc
            if self.inside(rr, cc):
                parts.append(f"{_DIR_WORDS[(dr, dc)]}: {self.cell_word(rr, cc)}")
            else:
                parts.append(f"{_DIR_WORDS[(dr, dc)]}: حافة")
        return "، ".join(parts)

    def safe_hint(self) -> Optional[Tuple[int, int, str]]:
        """A cell logic proves safe or a mine, by the simple rules:
        a number whose flags already match it makes its other neighbours
        safe; a number whose closed neighbours equal it makes them all mines."""
        for (r, c) in sorted(self.open):
            n = self.count(r, c)
            if n == 0:
                continue
            closed = [x for x in self.neighbours(r, c)
                      if x not in self.open and x not in self.flags]
            flagged = [x for x in self.neighbours(r, c) if x in self.flags]
            if closed and len(flagged) == n:
                return closed[0][0], closed[0][1], "safe"
            if closed and len(closed) + len(flagged) == n:
                return closed[0][0], closed[0][1], "mine"
        return None
