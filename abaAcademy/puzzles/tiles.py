# -*- coding: utf-8 -*-
"""
abaAcademy.puzzles.tiles
========================

Two tile puzzles that suit play by ear:

* **2048** — slide the tiles with the arrow keys; equal tiles merge. After
  every move the game reports what merged and where the new tile appeared,
  and the board can be read row by row or column by column.
* **Sliding puzzle (15-puzzle)** — order the numbered tiles by sliding them
  into the gap. Shuffles are made by random legal moves from the solved
  position, so every puzzle is solvable; the solver can suggest the next
  move for small boards.

Pure standard library.
"""

from __future__ import annotations

import heapq
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

DIRECTIONS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
ARROW_WORDS = {"up": "الأعلى", "down": "الأسفل", "left": "الأيسر", "right": "الأيمن"}
DIRECTION_WORDS = {"up": "الأعلى", "down": "الأسفل", "left": "اليسار", "right": "اليمين"}


# ---------------------------------------------------------------------------
# 2048
# ---------------------------------------------------------------------------

@dataclass
class MoveResult:
    moved: bool
    merges: List[int] = field(default_factory=list)
    gained: int = 0
    spawned: Optional[Tuple[int, int, int]] = None


class Game2048:
    def __init__(self, size: int = 4, rng: Optional[random.Random] = None,
                 target: int = 2048):
        self.size = size
        self.rng = rng or random.Random()
        self.target = target
        self.board = [[0] * size for _ in range(size)]
        self.score = 0
        self.best_tile = 0
        self.reached_target = False
        self._history: List[Tuple[List[List[int]], int]] = []
        self._spawn()
        self._spawn()

    def _empty(self):
        return [(r, c) for r in range(self.size) for c in range(self.size)
                if not self.board[r][c]]

    def _spawn(self):
        empty = self._empty()
        if not empty:
            return None
        r, c = self.rng.choice(empty)
        v = 4 if self.rng.random() < 0.1 else 2
        self.board[r][c] = v
        self.best_tile = max(self.best_tile, v)
        return r, c, v

    @staticmethod
    def _slide_line(line: List[int]) -> Tuple[List[int], List[int]]:
        tiles = [v for v in line if v]
        out, merges = [], []
        i = 0
        while i < len(tiles):
            if i + 1 < len(tiles) and tiles[i] == tiles[i + 1]:
                out.append(tiles[i] * 2)
                merges.append(tiles[i] * 2)
                i += 2
            else:
                out.append(tiles[i])
                i += 1
        out += [0] * (len(line) - len(out))
        return out, merges

    def _lines(self, direction):
        n = self.size
        if direction == "left":
            return [[(r, c) for c in range(n)] for r in range(n)]
        if direction == "right":
            return [[(r, c) for c in reversed(range(n))] for r in range(n)]
        if direction == "up":
            return [[(r, c) for r in range(n)] for c in range(n)]
        return [[(r, c) for r in reversed(range(n))] for c in range(n)]

    def move(self, direction: str) -> MoveResult:
        if direction not in DIRECTIONS:
            raise ValueError(direction)
        before = [row[:] for row in self.board]
        merges_all: List[int] = []
        for cells in self._lines(direction):
            vals = [self.board[r][c] for r, c in cells]
            new, merges = self._slide_line(vals)
            for (r, c), v in zip(cells, new):
                self.board[r][c] = v
            merges_all += merges
        if self.board == before:
            return MoveResult(False)
        self._history.append((before, self.score))
        if len(self._history) > 20:
            self._history.pop(0)
        gained = sum(merges_all)
        self.score += gained
        for v in merges_all:
            self.best_tile = max(self.best_tile, v)
            if v >= self.target:
                self.reached_target = True
        spawned = self._spawn()
        return MoveResult(True, merges_all, gained, spawned)

    def undo(self) -> bool:
        if not self._history:
            return False
        self.board, self.score = self._history.pop()
        return True

    def can_move(self) -> bool:
        if self._empty():
            return True
        n = self.size
        for r in range(n):
            for c in range(n):
                v = self.board[r][c]
                if c + 1 < n and self.board[r][c + 1] == v:
                    return True
                if r + 1 < n and self.board[r + 1][c] == v:
                    return True
        return False

    def row_text(self, r: int) -> str:
        return " ".join(str(v) if v else "فراغ" for v in self.board[r])

    def col_text(self, c: int) -> str:
        return " ".join(str(self.board[r][c]) if self.board[r][c] else "فراغ"
                        for r in range(self.size))

    def board_text(self) -> str:
        return "\n".join(f"الصفّ {r + 1}: {self.row_text(r)}" for r in range(self.size))

    def describe_move(self, direction: str, res: MoveResult) -> str:
        if not res.moved:
            return f"لا يمكن التحريك نحو {DIRECTION_WORDS[direction]}."
        parts = [f"نحو {DIRECTION_WORDS[direction]}."]
        if res.merges:
            parts.append("دمج: " + "، ".join(str(m) for m in res.merges) +
                         f"، +{res.gained} نقطة.")
        if res.spawned:
            r, c, v = res.spawned
            parts.append(f"ظهر {v} في الصفّ {r + 1} العمود {c + 1}.")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# sliding puzzle
# ---------------------------------------------------------------------------

class SlidingPuzzle:
    """Tiles 1..n²-1 with the gap (0) at the end when solved. Arrow keys move
    the *tile* into the gap in that direction (pressing up slides the tile
    below the gap upwards), which is how most players think of it."""

    def __init__(self, size: int = 3, rng: Optional[random.Random] = None,
                 shuffle_moves: int = 0):
        if size < 2:
            raise ValueError(size)
        self.size = size
        self.rng = rng or random.Random()
        self.tiles = list(range(1, size * size)) + [0]
        self.moves = 0
        if shuffle_moves is not None:
            self.shuffle(shuffle_moves or size * size * 20)

    @property
    def gap(self) -> int:
        return self.tiles.index(0)

    def _rc(self, i):
        return divmod(i, self.size)

    def _tile_from(self, direction: str) -> Optional[int]:
        """Index of the tile that would move into the gap."""
        gr, gc = self._rc(self.gap)
        dr, dc = DIRECTIONS[direction]
        tr, tc = gr - dr, gc - dc            # tile is opposite to the motion
        if 0 <= tr < self.size and 0 <= tc < self.size:
            return tr * self.size + tc
        return None

    def legal(self) -> List[str]:
        return [d for d in DIRECTIONS if self._tile_from(d) is not None]

    def move(self, direction: str) -> Optional[int]:
        i = self._tile_from(direction)
        if i is None:
            return None
        g = self.gap
        tile = self.tiles[i]
        self.tiles[g], self.tiles[i] = tile, 0
        self.moves += 1
        return tile

    def shuffle(self, steps: int) -> None:
        last = None
        opposite = {"up": "down", "down": "up", "left": "right", "right": "left"}
        for _ in range(steps):
            options = [d for d in self.legal() if d != opposite.get(last)]
            d = self.rng.choice(options)
            self.move(d)
            last = d
        if self.solved():
            self.shuffle(max(2, steps // 2 or 2))
        self.moves = 0

    def solved(self) -> bool:
        return self.tiles == list(range(1, self.size * self.size)) + [0]

    def misplaced(self) -> int:
        return sum(1 for i, v in enumerate(self.tiles) if v and v != i + 1)

    def manhattan(self, tiles=None) -> int:
        tiles = tiles or self.tiles
        n = self.size
        d = 0
        for i, v in enumerate(tiles):
            if v:
                r, c = divmod(i, n)
                tr, tc = divmod(v - 1, n)
                d += abs(r - tr) + abs(c - tc)
        return d

    def row_text(self, r: int) -> str:
        n = self.size
        return " ".join(str(v) if v else "فراغ" for v in self.tiles[r * n:(r + 1) * n])

    def board_text(self) -> str:
        return "\n".join(f"الصفّ {r + 1}: {self.row_text(r)}" for r in range(self.size))

    def gap_text(self) -> str:
        r, c = self._rc(self.gap)
        around = []
        for d in DIRECTIONS:
            i = self._tile_from(d)
            if i is not None:
                around.append(f"السهم {ARROW_WORDS[d]} يحرّك {self.tiles[i]}")
        return f"الفراغ في الصفّ {r + 1} العمود {c + 1}. " + "، ".join(around) + "."

    def suggest(self, limit_nodes: int = 60000) -> Optional[str]:
        """Next move on an optimal path (A* with Manhattan distance). Only for
        3x3 and smaller, where it is instant."""
        if self.size > 3 or self.solved():
            return None
        start = tuple(self.tiles)
        goal = tuple(list(range(1, self.size * self.size)) + [0])
        n = self.size
        frontier = [(self.manhattan(list(start)), 0, start, None)]
        seen = {start: 0}
        first_move = {start: None}
        nodes = 0
        while frontier and nodes < limit_nodes:
            _, g, state, _ = heapq.heappop(frontier)
            nodes += 1
            if state == goal:
                return first_move[state]
            gap = state.index(0)
            gr, gc = divmod(gap, n)
            for d, (dr, dc) in DIRECTIONS.items():
                tr, tc = gr - dr, gc - dc
                if not (0 <= tr < n and 0 <= tc < n):
                    continue
                t = tr * n + tc
                lst = list(state)
                lst[gap], lst[t] = lst[t], 0
                nxt = tuple(lst)
                if nxt not in seen or seen[nxt] > g + 1:
                    seen[nxt] = g + 1
                    first_move[nxt] = first_move[state] or d
                    heapq.heappush(frontier, (g + 1 + self.manhattan(lst), g + 1, nxt, d))
        return None
