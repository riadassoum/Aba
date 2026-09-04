# -*- coding: utf-8 -*-
"""
abaAcademy.gui.spatial_maze
===========================

An accessible acoustic maze. The player is placed in a grid maze and must reach
a goal by listening: the goal emits a beacon whose stereo position and loudness
tell direction and distance, walls give a low thud when you bump them, and each
step gives a soft footstep. The player moves with the arrow keys; at any time a
spoken bearing to the goal is available.

The maze is generated with a guaranteed solution (randomised depth-first
carving), so every game is winnable. It's fully offline — the audio is
synthesised by ``spatial.audio3d`` — and equally playable by ear or by the
spoken bearings, so it never depends on perfect hearing of the panning.
"""

from __future__ import annotations

import random

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..spatial.audio3d import SpatialScene
from ..math_engine.sonification import TonePlayer   # reuse the PCM player


def generate_maze(w, h, rng):
    """Randomised DFS maze on a (w x h) grid of cells. Returns a grid where
    grid[y][x] is a set of open directions ('N','S','E','W'). Guarantees the
    whole maze is connected, so any two cells are reachable."""
    grid = [[set() for _ in range(w)] for _ in range(h)]
    visited = [[False] * w for _ in range(h)]
    stack = [(0, 0)]
    visited[0][0] = True
    dirs = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
    opp = {"N": "S", "S": "N", "E": "W", "W": "E"}
    while stack:
        x, y = stack[-1]
        nbrs = []
        for d, (dx, dy) in dirs.items():
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx]:
                nbrs.append((d, nx, ny))
        if not nbrs:
            stack.pop()
            continue
        d, nx, ny = rng.choice(nbrs)
        grid[y][x].add(d)
        grid[ny][nx].add(opp[d])
        visited[ny][nx] = True
        stack.append((nx, ny))
    return grid


class SpatialMazeDialog(AccessibleDialog):
    TITLE = "المتاهة الصوتية"

    # difficulty -> grid size; randomised each game so it's never the same maze
    SIZES = [("سهلة 5×5", 5), ("متوسطة 8×8", 8), ("صعبة 12×12", 12),
             ("صعبة جدًا 16×16", 16)]
    # timed-challenge durations
    TIMES = [("بلا وقت", 0), ("٣٠ ثانية", 30), ("دقيقة", 60),
             ("دقيقتان", 120), ("٥ دقائق", 300)]

    # arrow -> (compass, dx, dy, egocentric Arabic word)
    def _move_map(self):
        return {
            wx.WXK_UP:    ("N", 0, -1, "أمامك"),
            wx.WXK_DOWN:  ("S", 0, 1, "خلفك"),
            wx.WXK_RIGHT: ("E", 1, 0, "يمينك"),
            wx.WXK_LEFT:  ("W", -1, 0, "يسارك"),
        }

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(720, 560))
        self.academy = academy
        self._player = TonePlayer()
        self._rng = random.Random()
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_tick, self._timer)
        self._time_left = 0
        self._cleared = 0
        self._active = False      # no movement until a game is started

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "استمع إلى نغمة الهدف: موضعها بين الأذنين يدلّ على الاتجاه وعلوّها على القرب. "
            "تحرّك بالأسهم: السهم الأعلى للأمام، والأسفل للخلف، والأيمن لليمين، والأيسر "
            "لليسار. زر «أين الهدف؟» ينطق الاتجاه والمسافة.")),
            0, wx.ALL, 6)

        srow = wx.BoxSizer(wx.HORIZONTAL)
        srow.Add(wx.StaticText(panel, label="الصعوبة:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.sizeChoice = wx.Choice(panel, choices=[n for n, _ in self.SIZES])
        self.sizeChoice.SetName("صعوبة المتاهة")
        self.sizeChoice.SetSelection(0)
        srow.Add(self.sizeChoice, 0, wx.RIGHT, 12)
        srow.Add(wx.StaticText(panel, label="تحدّي الوقت:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.timeChoice = wx.Choice(panel, choices=[n for n, _ in self.TIMES])
        self.timeChoice.SetName("مدة تحدّي الوقت")
        self.timeChoice.SetSelection(0)
        srow.Add(self.timeChoice, 0)
        s.Add(srow, 0, wx.ALL, 6)

        self.pad = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE, size=(-1, 70))
        self.pad.SetName("لوح التحكم بالمتاهة")
        s.Add(self.pad, 0, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(680)
        s.Add(self.status, 0, wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "ابدأ", lambda e: self._start()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "أين الهدف؟ (B)", lambda e: self._bearing()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "أعد نغمة الهدف (Ctrl+R)", lambda e: self._beacon()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "أفضل نتيجة", lambda e: self._say_record()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.pad.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.set_first_control(self.sizeChoice)

    def _start(self):
        secs = self.TIMES[self.choice_index(self.timeChoice)][1]
        self._cleared = 0
        self._active = True
        if secs > 0:
            self._time_left = secs
            self._timer.Start(1000)
            self._say(f"بدأ تحدّي الوقت! اجتَز أكبر عدد من المتاهات خلال {secs} ثانية.")
        else:
            self._time_left = 0
        self._new_game()
        wx.CallAfter(self.pad.SetFocus)

    def _on_tick(self, evt):
        if not self._active:
            self._timer.Stop()
            return
        self._time_left -= 1
        if self._time_left <= 0:
            self._timer.Stop()
            self._finish_timed()
        elif self._time_left in (10, 30, 60):
            self.announce(f"بقي {self._time_left} ثانية.")

    def _finish_timed(self):
        self._active = False
        best = self._save_record(self._cleared)
        extra = " رقم قياسي جديد!" if best else ""
        self._say(f"انتهى الوقت! اجتزت {self._cleared} متاهة.{extra} "
                  f"اضغط «ابدأ» لمحاولة أخرى.")

    def _record_key(self):
        diff = self.SIZES[self.choice_index(self.sizeChoice)][1]
        secs = self.TIMES[self.choice_index(self.timeChoice)][1]
        return f"maze_record_{diff}_{secs}"

    def _save_record(self, cleared):
        try:
            key = self._record_key()
            prev = int(self.academy.store.get_setting(key, "0") or "0")
            if cleared > prev:
                self.academy.store.set_setting(key, str(cleared))
                return True
        except Exception:
            pass
        return False

    def _say_record(self):
        try:
            best = int(self.academy.store.get_setting(self._record_key(), "0") or "0")
        except Exception:
            best = 0
        self._say(f"أفضل نتيجة لهذه الصعوبة والمدّة: {best} متاهة.")

    # -- game -------------------------------------------------------------
    def _new_game(self):
        n = self.SIZES[self.choice_index(self.sizeChoice)][1]
        self._n = n
        # reseed so each maze differs
        self._maze = generate_maze(n, n, random.Random(self._rng.randrange(1 << 30)))
        self._scene = SpatialScene(n, n)
        # Start at the bottom-left and put the goal at the top-right. Since the
        # up arrow moves to a smaller y, this makes the goal genuinely "ahead":
        # walking forward carries you toward it instead of away from it.
        self._px, self._py = 0, n - 1
        self._gx, self._gy = n - 1, 0
        self._steps = 0
        self._say(f"متاهة {n} في {n}. أنت في الزاوية، والهدف أمامك في الزاوية "
                  f"المقابلة. تحرّك بالأسهم واتبع نغمة الهدف. بالتوفيق!")
        self._beacon()
        wx.CallAfter(self.pad.SetFocus)

    def _on_key(self, evt):
        code = evt.GetKeyCode()
        moves = self._move_map()
        if code in moves:
            compass, dx, dy, word = moves[code]
            self._try_move(compass, dx, dy, word)
            return
        if code in (ord("B"), ord("b")):
            self._bearing()
            return
        if code == ord("R") and evt.ControlDown():
            self._beacon()
            return
        evt.Skip()

    def _try_move(self, direction, dx, dy, word=""):
        if not self._active:
            self._say("انتهت الجولة. اضغط «ابدأ» لجولة جديدة.")
            return
        cell = self._maze[self._py][self._px]
        if direction in cell:
            self._px += dx
            self._py += dy
            self._steps += 1
            if (self._px, self._py) == (self._gx, self._gy):
                self._win()
                return
            if self._player.available:
                self._player.play(self._scene.cue((self._px, self._py),
                                                   (self._gx, self._gy), kind="step"))
            self.call_later(120, self._beacon)
        else:
            if self._player.available:
                self._player.play(self._scene.cue(
                    (self._px, self._py),
                    (self._px + dx, self._py + dy), kind="wall"))
            self.announce(f"جدار {word}." if word else "جدار.")

    def _beacon(self):
        if self._player.available:
            self._player.play(self._scene.cue((self._px, self._py),
                                              (self._gx, self._gy), kind="goal"))
        else:
            # no audio device: give the bearing so it's still playable
            self._bearing()

    def _bearing(self):
        self._say(self._scene.direction_word((self._px, self._py),
                                             (self._gx, self._gy)))

    def _win(self):
        if self._time_left > 0 and self._active:
            # timed challenge: count it and immediately serve a fresh maze
            self._cleared += 1
            self._say(f"أحسنت! اجتزت {self._cleared}. متاهة جديدة…")
            self.call_later(400, self._new_maze_if_active)
        else:
            # single maze finished: the round is over until «ابدأ» is pressed
            self._active = False
            self._say(f"وصلت إلى الهدف! أنهيت المتاهة في {self._steps} خطوة. "
                      f"أحسنت! «ابدأ» للعب مرة أخرى.")

    def _new_maze_if_active(self):
        """Serve the next maze only if the timed round is still running — the
        clock may have expired during the short pause after a win."""
        if self._active and self._time_left > 0:
            self._new_game()

    def on_closing(self):
        try:
            self._timer.Stop()
        except Exception:
            pass
        try:
            self._player.stop()
        except Exception:
            pass

    def _say(self, text):
        self.status.SetLabel(text)
        self.announce(text)

    def on_repeat(self):
        self._beacon()

    def instructions(self):
        return ("المتاهة الصوتية: تحرّك بالأسهم الأربعة لتصل إلى الهدف. نغمة الهدف تُسمع "
                "من جهته: يمين أو يسار حسب موضعها بين الأذنين، وأعلى صوتاً كلما اقتربت. "
                "عند الاصطدام بجدار تسمع صوتاً منخفضاً وكلمة «جدار». زر «أين الهدف؟» أو "
                "حرف B ينطق الاتجاه والمسافة، فالمتاهة قابلة للّعب بالسمع أو بالكلام. "
                "كل متاهة لها حلّ مضمون. Escape للإغلاق.")
