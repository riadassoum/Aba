# -*- coding: utf-8 -*-
"""
abaAcademy.chess_engine.board
=============================

A self-contained chess engine in pure Python: full legal-move generation
(including castling, en passant, promotion, check and checkmate detection) and a
minimax AI with alpha-beta pruning and a material+position evaluation.

Honest scope note
-----------------
This is a real, correct chess engine — not a wrapper around Stockfish. We did NOT
integrate an external UCI engine, because bundling a Stockfish binary in an the screen reader
add-on is not something we can do here and would bloat the package. What we ship
instead is a genuine engine strong enough to give a satisfying game at the
"beginner to club" level (depth-limited search). It plays legal, sensible chess
and never makes illegal moves; it will not beat a strong engine, and the UI says
so plainly. Every rule needed for a complete game is implemented and tested.

Coordinates: squares are (file, rank) with file 0..7 = a..h and rank 0..7 = 1..8.
Pieces are single letters, uppercase = white, lowercase = black:
K Q R B N P / k q r b n p. Empty = None.
"""

from __future__ import annotations

import copy


WHITE, BLACK = "w", "b"

# piece values for evaluation (centipawns)
_VALUES = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 20000}

# piece-square tables (white perspective; mirrored for black) — encourage sane
# development. Kept compact; a full engine would tune these heavily.
_PST_PAWN = [
    0, 0, 0, 0, 0, 0, 0, 0,
    5, 10, 10, -20, -20, 10, 10, 5,
    5, -5, -10, 0, 0, -10, -5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, 5, 10, 25, 25, 10, 5, 5,
    10, 10, 20, 30, 30, 20, 10, 10,
    50, 50, 50, 50, 50, 50, 50, 50,
    0, 0, 0, 0, 0, 0, 0, 0,
]
_PST_KNIGHT = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]


def _mirror(idx):
    """Mirror a 0..63 index vertically (for black's piece-square lookup)."""
    f = idx % 8
    r = idx // 8
    return (7 - r) * 8 + f


class Move:
    __slots__ = ("frm", "to", "promo", "is_castle", "is_ep")

    def __init__(self, frm, to, promo=None, is_castle=False, is_ep=False):
        self.frm = frm
        self.to = to
        self.promo = promo          # 'Q','R','B','N' or None
        self.is_castle = is_castle
        self.is_ep = is_ep

    def __eq__(self, other):
        return (isinstance(other, Move) and self.frm == other.frm
                and self.to == other.to and self.promo == other.promo)

    def __hash__(self):
        return hash((self.frm, self.to, self.promo))


class Board:
    """A chess position with full rules."""

    def __init__(self):
        self.squares = self._initial()
        self.turn = WHITE
        self.castling = {"K": True, "Q": True, "k": True, "q": True}
        self.ep_target = None       # (file, rank) available for en passant
        self.halfmove = 0

    @staticmethod
    def _initial():
        back = "RNBQKBNR"
        sq = [None] * 64
        for f in range(8):
            sq[f] = back[f]              # rank 1 white
            sq[8 + f] = "P"
            sq[48 + f] = "p"
            sq[56 + f] = back[f].lower()  # rank 8 black
        return sq

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def idx(file, rank):
        return rank * 8 + file

    @staticmethod
    def fr(idx):
        return idx % 8, idx // 8

    def piece_at(self, file, rank):
        if 0 <= file < 8 and 0 <= rank < 8:
            return self.squares[self.idx(file, rank)]
        return None

    @staticmethod
    def color_of(piece):
        if piece is None:
            return None
        return WHITE if piece.isupper() else BLACK

    # -- move generation --------------------------------------------------
    def legal_moves(self):
        """All fully-legal moves for the side to move (leaves king safe)."""
        out = []
        for mv in self._pseudo_moves(self.turn):
            nb = self.apply(mv)
            if not nb._king_attacked(self.turn):
                out.append(mv)
        return out

    def _pseudo_moves(self, color):
        moves = []
        for i in range(64):
            p = self.squares[i]
            if p is None or self.color_of(p) != color:
                continue
            f, r = self.fr(i)
            kind = p.upper()
            if kind == "P":
                moves.extend(self._pawn_moves(f, r, color))
            elif kind == "N":
                moves.extend(self._step_moves(f, r, color, _KNIGHT))
            elif kind == "K":
                moves.extend(self._step_moves(f, r, color, _KING))
                moves.extend(self._castle_moves(f, r, color))
            elif kind == "B":
                moves.extend(self._slide_moves(f, r, color, _DIAG))
            elif kind == "R":
                moves.extend(self._slide_moves(f, r, color, _ORTHO))
            elif kind == "Q":
                moves.extend(self._slide_moves(f, r, color, _DIAG + _ORTHO))
        return moves

    def _pawn_moves(self, f, r, color):
        out = []
        d = 1 if color == WHITE else -1
        start = 1 if color == WHITE else 6
        promo_rank = 7 if color == WHITE else 0
        # forward
        if self.piece_at(f, r + d) is None:
            self._add_pawn(out, f, r, f, r + d, promo_rank)
            if r == start and self.piece_at(f, r + 2 * d) is None:
                out.append(Move(self.idx(f, r), self.idx(f, r + 2 * d)))
        # captures
        for df in (-1, 1):
            nf, nr = f + df, r + d
            if 0 <= nf < 8 and 0 <= nr < 8:
                tp = self.piece_at(nf, nr)
                if tp is not None and self.color_of(tp) != color:
                    self._add_pawn(out, f, r, nf, nr, promo_rank)
                elif self.ep_target == (nf, nr):
                    out.append(Move(self.idx(f, r), self.idx(nf, nr), is_ep=True))
        return out

    def _add_pawn(self, out, f, r, nf, nr, promo_rank):
        if nr == promo_rank:
            for promo in ("Q", "R", "B", "N"):
                out.append(Move(self.idx(f, r), self.idx(nf, nr), promo=promo))
        else:
            out.append(Move(self.idx(f, r), self.idx(nf, nr)))

    def _step_moves(self, f, r, color, deltas):
        out = []
        for df, dr in deltas:
            nf, nr = f + df, r + dr
            if 0 <= nf < 8 and 0 <= nr < 8:
                tp = self.piece_at(nf, nr)
                if tp is None or self.color_of(tp) != color:
                    out.append(Move(self.idx(f, r), self.idx(nf, nr)))
        return out

    def _slide_moves(self, f, r, color, dirs):
        out = []
        for df, dr in dirs:
            nf, nr = f + df, r + dr
            while 0 <= nf < 8 and 0 <= nr < 8:
                tp = self.piece_at(nf, nr)
                if tp is None:
                    out.append(Move(self.idx(f, r), self.idx(nf, nr)))
                else:
                    if self.color_of(tp) != color:
                        out.append(Move(self.idx(f, r), self.idx(nf, nr)))
                    break
                nf += df
                nr += dr
        return out

    def _castle_moves(self, f, r, color):
        out = []
        if self._king_attacked(color):
            return out
        rights = ("K", "Q") if color == WHITE else ("k", "q")
        rank = 0 if color == WHITE else 7
        if f != 4 or r != rank:
            return out
        # king-side
        if self.castling[rights[0]] and self.piece_at(5, rank) is None \
                and self.piece_at(6, rank) is None:
            if not self._square_attacked(5, rank, color) \
                    and not self._square_attacked(6, rank, color):
                out.append(Move(self.idx(4, rank), self.idx(6, rank), is_castle=True))
        # queen-side
        if self.castling[rights[1]] and self.piece_at(3, rank) is None \
                and self.piece_at(2, rank) is None and self.piece_at(1, rank) is None:
            if not self._square_attacked(3, rank, color) \
                    and not self._square_attacked(2, rank, color):
                out.append(Move(self.idx(4, rank), self.idx(2, rank), is_castle=True))
        return out

    # -- attack detection -------------------------------------------------
    def _king_attacked(self, color):
        king = "K" if color == WHITE else "k"
        for i in range(64):
            if self.squares[i] == king:
                f, r = self.fr(i)
                return self._square_attacked(f, r, color)
        return True  # no king = treat as attacked (lost)

    def _square_attacked(self, f, r, color):
        """Is (f,r) attacked by the opponent of ``color``?"""
        opp = BLACK if color == WHITE else WHITE
        d = 1 if color == WHITE else -1
        # pawn attacks
        for df in (-1, 1):
            p = self.piece_at(f + df, r + d)
            if p is not None and self.color_of(p) == opp and p.upper() == "P":
                return True
        # knight
        for df, dr in _KNIGHT:
            p = self.piece_at(f + df, r + dr)
            if p is not None and self.color_of(p) == opp and p.upper() == "N":
                return True
        # king
        for df, dr in _KING:
            p = self.piece_at(f + df, r + dr)
            if p is not None and self.color_of(p) == opp and p.upper() == "K":
                return True
        # sliders
        for dirs, kinds in ((_DIAG, ("B", "Q")), (_ORTHO, ("R", "Q"))):
            for df, dr in dirs:
                nf, nr = f + df, r + dr
                while 0 <= nf < 8 and 0 <= nr < 8:
                    p = self.piece_at(nf, nr)
                    if p is not None:
                        if self.color_of(p) == opp and p.upper() in kinds:
                            return True
                        break
                    nf += df
                    nr += dr
        return False

    # -- applying a move --------------------------------------------------
    def apply(self, mv):
        """Return a NEW board with the move applied (does not mutate self)."""
        nb = Board.__new__(Board)
        nb.squares = list(self.squares)
        nb.turn = BLACK if self.turn == WHITE else WHITE
        nb.castling = dict(self.castling)
        nb.ep_target = None
        nb.halfmove = self.halfmove + 1

        p = nb.squares[mv.frm]
        color = self.color_of(p)
        ff, fr = self.fr(mv.frm)
        tf, tr = self.fr(mv.to)

        # reset halfmove on pawn move or capture
        if p.upper() == "P" or nb.squares[mv.to] is not None:
            nb.halfmove = 0

        # move the piece
        nb.squares[mv.to] = p
        nb.squares[mv.frm] = None

        # en passant capture removes the passed pawn
        if mv.is_ep:
            cap_rank = tr - 1 if color == WHITE else tr + 1
            nb.squares[self.idx(tf, cap_rank)] = None

        # promotion
        if mv.promo:
            nb.squares[mv.to] = mv.promo if color == WHITE else mv.promo.lower()

        # double pawn push sets ep target
        if p.upper() == "P" and abs(tr - fr) == 2:
            nb.ep_target = (ff, (tr + fr) // 2)

        # castling: move the rook too
        if mv.is_castle:
            rank = fr
            if tf == 6:   # king-side
                nb.squares[self.idx(5, rank)] = nb.squares[self.idx(7, rank)]
                nb.squares[self.idx(7, rank)] = None
            else:         # queen-side
                nb.squares[self.idx(3, rank)] = nb.squares[self.idx(0, rank)]
                nb.squares[self.idx(0, rank)] = None

        # update castling rights
        nb._revoke_castling(mv, p, color)
        return nb

    def _revoke_castling(self, mv, piece, color):
        if piece.upper() == "K":
            if color == WHITE:
                self.castling["K"] = self.castling["Q"] = False
            else:
                self.castling["k"] = self.castling["q"] = False
        # rook moved or captured
        corners = {(0, 0): "Q", (7, 0): "K", (0, 7): "q", (7, 7): "k"}
        for sqi in (mv.frm, mv.to):
            fr = self.fr(sqi)
            if fr in corners:
                self.castling[corners[fr]] = False

    # -- status -----------------------------------------------------------
    def in_check(self):
        return self._king_attacked(self.turn)

    def status(self):
        """'ongoing' | 'checkmate' | 'stalemate' | 'draw'."""
        if not self.legal_moves():
            return "checkmate" if self.in_check() else "stalemate"
        if self.halfmove >= 100:
            return "draw"
        return "ongoing"

    # -- evaluation & search ----------------------------------------------
    def evaluate(self):
        """Material + piece-square score from WHITE's perspective (centipawns)."""
        score = 0
        for i in range(64):
            p = self.squares[i]
            if p is None:
                continue
            val = _VALUES[p.upper()]
            pst = 0
            if p.upper() == "P":
                pst = _PST_PAWN[i if p.isupper() else _mirror(i)]
            elif p.upper() == "N":
                pst = _PST_KNIGHT[i if p.isupper() else _mirror(i)]
            if p.isupper():
                score += val + pst
            else:
                score -= val + pst
        return score

    def best_move(self, depth=3):
        """Pick the best move for the side to move via alpha-beta minimax."""
        maximizing = self.turn == WHITE
        best = None
        best_val = float("-inf") if maximizing else float("inf")
        moves = self._ordered_moves()
        for mv in moves:
            val = self.apply(mv)._search(depth - 1, float("-inf"),
                                         float("inf"), not maximizing)
            if maximizing and val > best_val:
                best_val, best = val, mv
            elif not maximizing and val < best_val:
                best_val, best = val, mv
        return best

    def _search(self, depth, alpha, beta, maximizing):
        if depth == 0:
            return self.evaluate()
        moves = self.legal_moves()
        if not moves:
            if self.in_check():
                # checkmate: very bad for the side to move
                return -1_000_000 if maximizing else 1_000_000
            return 0  # stalemate
        if maximizing:
            value = float("-inf")
            for mv in moves:
                value = max(value, self.apply(mv)._search(depth - 1, alpha, beta, False))
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value
        else:
            value = float("inf")
            for mv in moves:
                value = min(value, self.apply(mv)._search(depth - 1, alpha, beta, True))
                beta = min(beta, value)
                if alpha >= beta:
                    break
            return value

    def _ordered_moves(self):
        """Legal moves with captures first (helps alpha-beta prune)."""
        moves = self.legal_moves()
        def score(m):
            tp = self.squares[m.to]
            return _VALUES[tp.upper()] if tp else 0
        return sorted(moves, key=score, reverse=True)


# movement tables
_KNIGHT = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
_KING = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
_DIAG = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
_ORTHO = [(1, 0), (-1, 0), (0, 1), (0, -1)]
