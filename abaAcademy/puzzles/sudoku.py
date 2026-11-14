# -*- coding: utf-8 -*-
"""
abaAcademy.puzzles.sudoku
=========================

Sudoku generation, solving, hints and checking, built for play by ear.

* Puzzles are generated from a random full grid by removing clues while the
  solution stays unique (checked with a counting solver), so every puzzle
  can be solved by logic.
* Difficulty is set by how many clues remain and confirmed by grading: the
  grader solves the puzzle with human techniques (naked single, hidden
  single, naked pair, pointing pairs) and reports which ones were needed.
* Hints explain *why* a digit goes in a cell, in Arabic, using the same
  techniques, so a hint teaches instead of just filling the square.

Supports the classic 9x9 and a 4x4 board for beginners and young learners.
Pure standard library.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

Grid = List[List[int]]

DIFFICULTIES = {
    "beginner": ("مبتدئ", 40),
    "easy": ("سهل", 36),
    "medium": ("متوسّط", 31),
    "hard": ("صعب", 26),
}

TECHNIQUE_NAMES = {
    "naked_single": "الخانة الوحيدة (لا يصلح فيها إلا رقم واحد)",
    "hidden_single": "المكان الوحيد (لا مكان للرقم في الوحدة إلا هنا)",
    "naked_pair": "الزوج المكشوف",
    "pointing": "الإشارة من المربّع إلى الصفّ أو العمود",
}


class Board:
    def __init__(self, size: int = 9):
        if size not in (4, 9):
            raise ValueError("size must be 4 or 9")
        self.size = size
        self.box = 2 if size == 4 else 3

    # -- geometry --------------------------------------------------------
    def box_of(self, r: int, c: int) -> int:
        return (r // self.box) * self.box + c // self.box

    def box_cells(self, b: int) -> List[Tuple[int, int]]:
        r0, c0 = (b // self.box) * self.box, (b % self.box) * self.box
        return [(r0 + i, c0 + j) for i in range(self.box) for j in range(self.box)]

    def units(self) -> List[Tuple[str, int, List[Tuple[int, int]]]]:
        n = self.size
        out = []
        for r in range(n):
            out.append(("row", r, [(r, c) for c in range(n)]))
        for c in range(n):
            out.append(("col", c, [(r, c) for r in range(n)]))
        for b in range(n):
            out.append(("box", b, self.box_cells(b)))
        return out

    def peers(self, r: int, c: int) -> Set[Tuple[int, int]]:
        n = self.size
        s = {(r, j) for j in range(n)} | {(i, c) for i in range(n)}
        s |= set(self.box_cells(self.box_of(r, c)))
        s.discard((r, c))
        return s

    # -- rules -----------------------------------------------------------
    def candidates(self, g: Grid, r: int, c: int) -> Set[int]:
        if g[r][c]:
            return set()
        used = {g[i][j] for i, j in self.peers(r, c)}
        return set(range(1, self.size + 1)) - used

    def conflicts(self, g: Grid) -> List[Tuple[int, int]]:
        bad = set()
        for _, _, cells in self.units():
            seen: Dict[int, Tuple[int, int]] = {}
            for (r, c) in cells:
                v = g[r][c]
                if not v:
                    continue
                if v in seen:
                    bad.add((r, c))
                    bad.add(seen[v])
                else:
                    seen[v] = (r, c)
        return sorted(bad)

    def is_complete(self, g: Grid) -> bool:
        return all(all(row) for row in g) and not self.conflicts(g)

    # -- solving ---------------------------------------------------------
    def count_solutions(self, g: Grid, limit: int = 2) -> int:
        g = [row[:] for row in g]
        count = 0

        def best_cell():
            best, best_c = None, None
            for r in range(self.size):
                for c in range(self.size):
                    if not g[r][c]:
                        cand = self.candidates(g, r, c)
                        if best is None or len(cand) < len(best_c):
                            best, best_c = (r, c), cand
                            if len(cand) <= 1:
                                return best, best_c
            return best, best_c

        def go():
            nonlocal count
            if count >= limit:
                return
            cell, cand = best_cell()
            if cell is None:
                count += 1
                return
            r, c = cell
            for v in cand:
                g[r][c] = v
                go()
                if count >= limit:
                    break
            g[r][c] = 0

        go()
        return count

    def solve(self, g: Grid, rng: Optional[random.Random] = None) -> Optional[Grid]:
        g = [row[:] for row in g]
        digits = list(range(1, self.size + 1))

        def go():
            best, best_c = None, None
            for r in range(self.size):
                for c in range(self.size):
                    if not g[r][c]:
                        cand = self.candidates(g, r, c)
                        if not cand:
                            return False
                        if best is None or len(cand) < len(best_c):
                            best, best_c = (r, c), cand
            if best is None:
                return True
            r, c = best
            order = [d for d in digits if d in best_c]
            if rng:
                rng.shuffle(order)
            for v in order:
                g[r][c] = v
                if go():
                    return True
            g[r][c] = 0
            return False

        return g if go() else None

    # -- generation ------------------------------------------------------
    def generate(self, difficulty: str = "easy", rng: Optional[random.Random] = None,
                 symmetric: bool = True) -> Tuple[Grid, Grid]:
        """(puzzle, solution)."""
        rng = rng or random.Random()
        n = self.size
        full = self.solve([[0] * n for _ in range(n)], rng)
        assert full is not None
        if n == 4:
            target = {"beginner": 10, "easy": 8, "medium": 6, "hard": 5}.get(difficulty, 8)
        else:
            target = DIFFICULTIES.get(difficulty, DIFFICULTIES["easy"])[1]
        puzzle = [row[:] for row in full]
        cells = [(r, c) for r in range(n) for c in range(n)]
        rng.shuffle(cells)
        clues = n * n
        for (r, c) in cells:
            if clues <= target:
                break
            if not puzzle[r][c]:
                continue
            pair = [(r, c)]
            if symmetric and (n - 1 - r, n - 1 - c) != (r, c):
                pair.append((n - 1 - r, n - 1 - c))
            saved = [puzzle[i][j] for i, j in pair]
            for i, j in pair:
                puzzle[i][j] = 0
            if self.count_solutions(puzzle) != 1:
                for (i, j), v in zip(pair, saved):
                    puzzle[i][j] = v
            else:
                clues -= sum(1 for v in saved if v)
        return puzzle, full

    # -- human-style reasoning ------------------------------------------
    def _candidate_map(self, g: Grid) -> Dict[Tuple[int, int], Set[int]]:
        return {(r, c): self.candidates(g, r, c)
                for r in range(self.size) for c in range(self.size) if not g[r][c]}

    def _eliminate(self, cand: Dict[Tuple[int, int], Set[int]]) -> Optional[str]:
        """Apply one round of naked pairs / pointing to the candidate map.
        Returns the technique used, or None."""
        used = None
        for _, _, cells in self.units():
            empty = [x for x in cells if x in cand]
            pairs = [x for x in empty if len(cand[x]) == 2]
            for i in range(len(pairs)):
                for j in range(i + 1, len(pairs)):
                    a, b = pairs[i], pairs[j]
                    if cand[a] == cand[b]:
                        for x in empty:
                            if x not in (a, b) and cand[x] & cand[a]:
                                cand[x] -= cand[a]
                                used = "naked_pair"
        for b in range(self.size):
            cells = [x for x in self.box_cells(b) if x in cand]
            for d in range(1, self.size + 1):
                where = [x for x in cells if d in cand[x]]
                if len(where) < 2:
                    continue
                rows = {r for r, _ in where}
                cols = {c for _, c in where}
                if len(rows) == 1:
                    r = rows.pop()
                    for c in range(self.size):
                        x = (r, c)
                        if x in cand and self.box_of(r, c) != b and d in cand[x]:
                            cand[x].discard(d)
                            used = "pointing"
                if len(cols) == 1:
                    c = cols.pop()
                    for r in range(self.size):
                        x = (r, c)
                        if x in cand and self.box_of(r, c) != b and d in cand[x]:
                            cand[x].discard(d)
                            used = "pointing"
        return used

    def next_step(self, g: Grid) -> Optional["Step"]:
        """The next logical placement a person could make, with the reason."""
        cand = self._candidate_map(g)
        if not cand:
            return None
        helper = None
        for _ in range(4):
            step = self._find_single(cand)
            if step:
                if helper:
                    step.techniques.insert(0, helper)
                return step
            used = self._eliminate(cand)
            if not used:
                break
            helper = helper or used
        return None

    def _find_single(self, cand) -> Optional["Step"]:
        for (r, c), s in sorted(cand.items()):
            if len(s) == 1:
                v = next(iter(s))
                return Step(r, c, v, ["naked_single"],
                            f"الخانة {cell_name(r, c)} لا يصلح فيها إلا الرقم {v}، "
                            f"لأنّ بقية الأرقام موجودة في صفّها أو عمودها أو مربّعها.")
        unit_names = {"row": "الصفّ", "col": "العمود", "box": "المربّع"}
        for kind, idx, cells in self.units():
            empty = [x for x in cells if x in cand]
            for d in range(1, self.size + 1):
                where = [x for x in empty if d in cand[x]]
                if len(where) == 1:
                    r, c = where[0]
                    return Step(r, c, d, ["hidden_single"],
                                f"في {unit_names[kind]} {idx + 1} لا يوجد مكان للرقم {d} "
                                f"إلا الخانة {cell_name(r, c)}.")
        return None

    def grade(self, puzzle: Grid) -> Tuple[bool, List[str]]:
        """(solvable by the techniques above, techniques used)."""
        g = [row[:] for row in puzzle]
        used: List[str] = []
        while True:
            if all(all(row) for row in g):
                return True, used
            step = self.next_step(g)
            if not step:
                return False, used
            for t in step.techniques:
                if t not in used:
                    used.append(t)
            g[step.row][step.col] = step.value


@dataclass
class Step:
    row: int
    col: int
    value: int
    techniques: List[str] = field(default_factory=list)
    reason: str = ""


COL_LETTERS = "أبجدهوزحط"


def cell_name(r: int, c: int) -> str:
    """Rows are numbered, columns lettered (أ ب ج …) so a cell has a short
    spoken name like ج٥."""
    return f"{COL_LETTERS[c]}{r + 1}"


@dataclass
class Game:
    """A sudoku in progress: givens are locked, the player's digits and
    pencil marks are tracked, with undo."""
    size: int
    puzzle: Grid
    solution: Grid
    grid: Grid = field(default_factory=list)
    notes: Dict[Tuple[int, int], Set[int]] = field(default_factory=dict)
    history: List[Tuple[int, int, int, frozenset]] = field(default_factory=list)
    hints_used: int = 0
    mistakes: int = 0

    def __post_init__(self):
        if not self.grid:
            self.grid = [row[:] for row in self.puzzle]
        self.board = Board(self.size)

    @classmethod
    def new(cls, size=9, difficulty="easy", rng=None, attempts: int = 12):
        """A fresh puzzle that a person can finish with the techniques the
        hints teach (several candidates are tried; the last is kept if none
        qualifies, and its hints then fall back to the solution)."""
        b = Board(size)
        rng = rng or random.Random()
        p = s = None
        for _ in range(max(1, attempts)):
            p, s = b.generate(difficulty, rng)
            if b.grade(p)[0]:
                break
        return cls(size, p, s)

    def is_given(self, r, c) -> bool:
        return bool(self.puzzle[r][c])

    def place(self, r, c, v) -> str:
        """Put (or clear with 0) a digit. Returns 'given', 'ok', 'conflict'
        or 'solved'."""
        if self.is_given(r, c):
            return "given"
        if not 0 <= v <= self.size:
            raise ValueError(v)
        self.history.append((r, c, self.grid[r][c], frozenset(self.notes.get((r, c), set()))))
        self.grid[r][c] = v
        if v:
            self.notes.pop((r, c), None)
            for pr, pc in self.board.peers(r, c):
                self.notes.get((pr, pc), set()).discard(v)
        if v and (r, c) in self.board.conflicts(self.grid):
            self.mistakes += 1
            return "conflict"
        if self.board.is_complete(self.grid):
            return "solved"
        return "ok"

    def toggle_note(self, r, c, v) -> bool:
        if self.grid[r][c]:
            return False
        s = self.notes.setdefault((r, c), set())
        if v in s:
            s.discard(v)
            return False
        s.add(v)
        return True

    def undo(self) -> bool:
        if not self.history:
            return False
        r, c, v, notes = self.history.pop()
        self.grid[r][c] = v
        if notes:
            self.notes[(r, c)] = set(notes)
        else:
            self.notes.pop((r, c), None)
        return True

    def hint(self) -> Optional[Step]:
        # wrong digits first: a hint on a broken grid would mislead
        for r in range(self.size):
            for c in range(self.size):
                v = self.grid[r][c]
                if v and v != self.solution[r][c]:
                    return Step(r, c, 0, [], f"الرقم {v} في الخانة {cell_name(r, c)} غير صحيح؛ امسحه.")
        step = self.board.next_step(self.grid)
        if step is None:
            # fall back to the solution, honestly labelled
            for r in range(self.size):
                for c in range(self.size):
                    if not self.grid[r][c]:
                        step = Step(r, c, self.solution[r][c], [],
                                    f"الخانة {cell_name(r, c)} رقمها {self.solution[r][c]} "
                                    f"(تحتاج هنا إلى تقنية متقدّمة).")
                        break
                if step:
                    break
        if step:
            self.hints_used += 1
        return step

    def describe_cell(self, r, c) -> str:
        v = self.grid[r][c]
        name = cell_name(r, c)
        if v:
            kind = "معطاة" if self.is_given(r, c) else "رقمك"
            return f"{name}: {v} ({kind})"
        notes = self.notes.get((r, c))
        if notes:
            return f"{name}: فارغة، ملاحظاتك {' '.join(str(x) for x in sorted(notes))}"
        return f"{name}: فارغة"

    def describe_unit(self, kind: str, r: int, c: int) -> str:
        n = self.size
        if kind == "row":
            vals = [self.grid[r][j] for j in range(n)]
            title = f"الصفّ {r + 1}"
        elif kind == "col":
            vals = [self.grid[i][c] for i in range(n)]
            title = f"العمود {COL_LETTERS[c]}"
        else:
            b = self.board.box_of(r, c)
            vals = [self.grid[i][j] for i, j in self.board.box_cells(b)]
            title = f"المربّع {b + 1}"
        spoken = " ".join(str(v) if v else "فراغ" for v in vals)
        missing = sorted(set(range(1, n + 1)) - set(vals))
        return f"{title}: {spoken}. الناقص: {' '.join(map(str, missing)) or 'لا شيء'}."

    def empty_count(self) -> int:
        return sum(1 for row in self.grid for v in row if not v)
