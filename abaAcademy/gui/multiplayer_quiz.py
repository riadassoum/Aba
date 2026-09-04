# -*- coding: utf-8 -*-
"""
abaAcademy.gui.multiplayer_quiz
===============================

The screen for local-network trivia matches. A student either **hosts** a room
(others are told the host's IP and port to type in) or **joins** one. The host
draws questions from the Millionaire bank, sends them to everyone at once, scores
by correctness and speed, and announces standings between questions.

Because real cross-machine networking cannot be verified in the build
environment, the screen says so up front. The match logic and messaging are
tested over loopback, but you should try a real two-device game before relying on
it in class.
"""

from __future__ import annotations

import gzip
import json
import os
import random
import time

try:
    import wx
except Exception:
    wx = None

from .accessible import AccessibleDialog
from ..multiplayer.lan import Host, Client, DEFAULT_PORT, local_ip

_LETTERS = ["أ", "ب", "ج", "د"]


class MultiplayerQuizDialog(AccessibleDialog):
    TITLE = "مسابقة عبر الشبكة المحلية"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(720, 560))
        self.academy = academy
        self._host = None
        self._client = None
        self._role = None
        self._bank = self._load_bank()
        self._scores = {}
        self._qid = None
        self._q_correct = None
        self._q_start = 0
        self._answered = False
        self._round = 0
        self._max_rounds = 10

        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(panel, label=(
            "العب مع زملائك على الشبكة نفسها. أنشئ غرفة ودع الآخرين ينضمّون، "
            "أو انضمّ إلى غرفة بعنوانها. ملاحظة: الاتصال الشبكي لم يُختبر بين "
            "جهازين حقيقيين، فجرّبه قبل الاعتماد عليه في الصف.")),
            0, wx.ALL, 6)

        nrow = wx.BoxSizer(wx.HORIZONTAL)
        nrow.Add(wx.StaticText(panel, label="اسمك:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.nameEntry = wx.TextCtrl(panel)
        self.nameEntry.SetName("اسمك")
        self.nameEntry.SetValue("لاعب")
        nrow.Add(self.nameEntry, 1)
        s.Add(nrow, 0, wx.EXPAND | wx.ALL, 6)

        hrow = wx.BoxSizer(wx.HORIZONTAL)
        hrow.Add(self.button(panel, "أنشئ غرفة (استضافة)", lambda e: self._host_room()), 0, wx.ALL, 3)
        hrow.Add(self.button(panel, "ابدأ المسابقة", lambda e: self._start_match()), 0, wx.ALL, 3)
        s.Add(hrow, 0, wx.ALL, 3)

        jrow = wx.BoxSizer(wx.HORIZONTAL)
        jrow.Add(wx.StaticText(panel, label="عنوان الغرفة:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.ipEntry = wx.TextCtrl(panel)
        self.ipEntry.SetName("عنوان الغرفة")
        jrow.Add(self.ipEntry, 1)
        jrow.Add(self.button(panel, "انضمّ", lambda e: self._join_room()), 0, wx.LEFT, 4)
        s.Add(jrow, 0, wx.EXPAND | wx.ALL, 6)

        self.options = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.options.SetName("الخيارات")
        s.Add(self.options, 1, wx.EXPAND | wx.ALL, 6)

        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(680)
        s.Add(self.status, 0, wx.ALL, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "أجب (Enter)", lambda e: self._answer()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "النتائج", lambda e: self._say_scores()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)

        panel.SetSizer(s)
        self.set_first_control(self.nameEntry)

    # -- bank -------------------------------------------------------------
    def _load_bank(self):
        try:
            path = os.path.join(self.academy.resource_dir, "millionaire",
                                "questions.json.gz")
            with gzip.open(path, "rt", encoding="utf-8") as f:
                return json.load(f).get("questions", [])
        except Exception:
            return []

    # -- hosting ----------------------------------------------------------
    def _host_room(self):
        if self._host or self._client:
            self._say("أنت في غرفة بالفعل.")
            return
        self._role = "host"
        self._scores = {self._me(): 0}
        self._host = Host(port=DEFAULT_PORT,
                          on_join=lambda n: wx.CallAfter(self._on_join, n),
                          on_answer=lambda n, i, ms: wx.CallAfter(self._on_answer, n, i, ms),
                          on_error=lambda m: wx.CallAfter(self._say, m))
        self._host.start()
        ip = local_ip()
        self._say(f"أنشأت غرفة. اطلب من زملائك الانضمام إلى العنوان {ip} "
                  f"منفذ {DEFAULT_PORT}. عندما يجتمع اللاعبون اضغط «ابدأ المسابقة».")

    def _on_join(self, name):
        self._scores.setdefault(name, 0)
        self.announce(f"انضمّ {name}. عدد اللاعبين {len(self._scores)}.")

    # -- joining ----------------------------------------------------------
    def _join_room(self):
        if self._host or self._client:
            self._say("أنت في غرفة بالفعل.")
            return
        ip = self.ipEntry.GetValue().strip()
        if not ip:
            self._say("اكتب عنوان الغرفة الذي أعطاك إياه المُضيف.")
            return
        self._role = "client"
        self._client = Client(ip, DEFAULT_PORT, name=self._me(),
                              on_question=lambda m: wx.CallAfter(self._show_question, m),
                              on_reveal=lambda m: wx.CallAfter(self._on_reveal, m),
                              on_scores=lambda sc: wx.CallAfter(self._update_scores, sc),
                              on_gameover=lambda r: wx.CallAfter(self._on_gameover, r),
                              on_error=lambda m: wx.CallAfter(self._say, m))
        self._client.connect()
        self._say(f"محاولة الانضمام إلى {ip}…")

    # -- match flow (host drives) ----------------------------------------
    def _start_match(self):
        if self._role != "host":
            self._say("يبدأ المضيف المسابقة فقط.")
            return
        if not self._bank:
            self._say("تعذّر تحميل بنك الأسئلة.")
            return
        self._round = 0
        self._next_question()

    def _next_question(self):
        if self._round >= self._max_rounds:
            self._finish_match()
            return
        self._round += 1
        q = random.choice(self._bank)
        self._qid = f"q{self._round}"
        self._q_correct = q["answer"]
        self._pending_answers = {}
        deadline = 15000
        self._host.send_question(self._qid, q["q"], q["options"], deadline)
        # host plays too
        self._show_question({"qid": self._qid, "text": q["q"],
                             "options": q["options"], "deadline_ms": deadline})
        # schedule reveal
        wx.CallLater(deadline + 500, self._reveal_question)

    def _reveal_question(self):
        if self._role != "host" or self._qid is None:
            return
        self._host.reveal(self._qid, self._q_correct)
        self._on_reveal({"qid": self._qid, "correct": self._q_correct})
        self._host.send_scores(self._scores)
        self.call_later(3000, self._next_question)

    def _on_answer(self, name, index, ms):
        # host tallies a client's answer
        if self._qid is None:
            return
        if getattr(self, "_pending_answers", None) is None:
            self._pending_answers = {}
        if name in self._pending_answers:
            return          # only first answer counts
        self._pending_answers[name] = index
        if index == self._q_correct:
            # speed bonus: faster = more, base 100
            bonus = max(0, 50 - int((ms or 15000) / 400))
            self._scores[name] = self._scores.get(name, 0) + 100 + bonus

    # -- shared display ---------------------------------------------------
    def _show_question(self, m):
        self._qid = m["qid"]
        self._answered = False
        self._q_start = time.time()
        self.options.Set([f"{_LETTERS[i]}: {o}" for i, o in enumerate(m["options"])])
        self.select_index(self.options, 0)
        self._say(f"السؤال {self._round if self._role=='host' else ''}: {m['text']} — "
                  + "؛ ".join(f"{_LETTERS[i]}: {o}" for i, o in enumerate(m["options"]))
                  + ". اختر بالأسهم واضغط Enter.")
        self.options.SetFocus()

    def _answer(self):
        if self._answered or self._qid is None:
            return
        i = self.options.GetSelection()
        if i < 0:
            return
        self._answered = True
        ms = int((time.time() - self._q_start) * 1000)
        if self._role == "client" and self._client:
            self._client.answer(self._qid, i, ms)
            self._say("أُرسلت إجابتك. انتظر النتيجة.")
        elif self._role == "host":
            self._on_answer(self._me(), i, ms)
            self._say("سُجّلت إجابتك.")

    def _on_reveal(self, m):
        correct = m.get("correct")
        self._say(f"الإجابة الصحيحة: {_LETTERS[correct]}.")

    def _update_scores(self, scores):
        self._scores = scores
        self._say(self._scores_text())

    def _say_scores(self):
        self._say(self._scores_text())

    def _scores_text(self):
        if not self._scores:
            return "لا نتائج بعد."
        ordered = sorted(self._scores.items(), key=lambda kv: -kv[1])
        return "النتائج: " + "، ".join(f"{n} {sc}" for n, sc in ordered) + "."

    def _finish_match(self):
        ranking = sorted(self._scores.items(), key=lambda kv: -kv[1])
        if self._role == "host" and self._host:
            self._host.game_over(ranking)
        self._on_gameover(ranking)

    def _on_gameover(self, ranking):
        if ranking:
            winner = ranking[0][0]
            self._say(f"انتهت المسابقة! الفائز: {winner}. " + self._scores_text())
        else:
            self._say("انتهت المسابقة.")

    # -- helpers ----------------------------------------------------------
    def _me(self):
        return (self.nameEntry.GetValue().strip() or "لاعب")[:24]

    def on_enter_key(self):
        focus = self.FindFocus()
        if isinstance(focus, wx.Button):
            return False
        self._answer()
        return True

    def on_closing(self):
        if self._host:
            self._host.stop()
        if self._client:
            self._client.close()

    def _say(self, text):
        self.status.SetLabel(text[:200])
        self.announce(text)

    def instructions(self):
        return ("مسابقة عبر الشبكة المحلية: اكتب اسمك، ثم إمّا «أنشئ غرفة» لتستضيف "
                "(ويظهر لك عنوان تعطيه لزملائك)، أو اكتب عنوان غرفة و«انضمّ». المضيف يضغط "
                "«ابدأ المسابقة»، فتصل الأسئلة للجميع معاً؛ اختر بالأسهم واضغط Enter بسرعة، "
                "فالأسرع ينال نقاطاً أكثر. ملاحظة: لم يُختبر الاتصال بين جهازين حقيقيين بعد. "
                "Escape للإغلاق.")
