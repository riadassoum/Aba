# -*- coding: utf-8 -*-
"""
abaAcademy.gui.millionaire
==========================

من سيربح المليون — a full, accessible "Who Wants to Be a Millionaire" game built
on a large Arabic general-knowledge question bank (thousands of questions, each
with four options), assembled from the bundled competition question banks.

It plays like the real show:
  * a 15-rung money ladder with two guaranteed "safe havens" (questions 5 and 10),
  * questions chosen by difficulty tier so they get harder as you climb,
  * four options A/B/C/D, navigated with the arrow keys and locked in with Enter,
  * the four classic lifelines, each usable once:
      - الخمسون خمسون (50:50): removes two wrong options,
      - اتصال بصديق (phone a friend): a friend suggests an answer (usually right),
      - مساعدة الجمهور (ask the audience): a voting breakdown across the options,
      - تغيير السؤال (switch the question): swap for another of the same tier,
  * walk away at any time and keep your banked winnings,
  * a wrong answer drops you to the last safe haven.

Everything is spoken; nothing depends on sight or a mouse.
"""

from __future__ import annotations

import gzip
import json
import os
import random

from .accessible import AccessibleDialog

try:
    import wx
except Exception:
    wx = None

AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def ar(n):
    return str(n).translate(AR)


# the classic 15-rung prize ladder (in a generic "point" currency); questions 5
# and 10 are safe havens the player never drops below
LADDER = [
    100, 200, 300, 500, 1000,          # 5 -> safe haven
    2000, 4000, 8000, 16000, 32000,    # 10 -> safe haven
    64000, 125000, 250000, 500000, 1000000,
]
SAFE_HAVENS = {4, 9}   # zero-based indices of rungs 5 and 10
OPTION_LETTERS = ["أ", "ب", "ج", "د"]


class _Bank:
    """Loads and serves the question bank once, grouped by difficulty tier and
    by category."""
    _instance = None

    def __init__(self, resource_dir):
        self.by_level = {}
        self.by_cat = {}
        self.all = []
        path = os.path.join(resource_dir, "millionaire", "questions.json.gz")
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                data = json.load(f)
            self.all = data.get("questions", [])
            for q in self.all:
                self.by_level.setdefault(q.get("level", 2), []).append(q)
                self.by_cat.setdefault(q.get("cat", "معلومات عامة"), []).append(q)
        except Exception:
            pass

    @classmethod
    def get(cls, resource_dir):
        if cls._instance is None:
            cls._instance = _Bank(resource_dir)
        return cls._instance

    def categories(self):
        """Category names sorted by how many questions they have (largest
        first) — for the training ground's category picker."""
        return sorted(self.by_cat, key=lambda c: -len(self.by_cat[c]))

    def pick(self, rung, used):
        """Pick an unused question whose difficulty suits the rung (1-15)."""
        # map the 15 rungs onto difficulty tiers 1..5
        if rung <= 4:
            tiers = [1, 2]
        elif rung <= 9:
            tiers = [2, 3]
        elif rung <= 12:
            tiers = [3, 4]
        else:
            tiers = [4, 3, 5]
        pool = []
        for t in tiers:
            pool.extend(self.by_level.get(t, []))
        random.shuffle(pool)
        for q in pool:
            if q.get("id") not in used:
                return q
        # fallback: any unused question
        for q in self.all:
            if q.get("id") not in used:
                return q
        return None


class MillionaireGame(AccessibleDialog):
    TITLE = "من سيربح المليون"
    GAME_KEY = "millionaire"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(680, 620))
        self.academy = academy
        self.bank = _Bank.get(academy.resource_dir)
        panel = wx.Panel(self)
        self._panel = panel
        s = wx.BoxSizer(wx.VERTICAL)
        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(640)
        s.Add(self.status, 0, wx.ALL, 8)

        # the question + options grid (arrow-navigable)
        self.qLabel = wx.StaticText(panel, label="")
        self.qLabel.Wrap(640)
        s.Add(self.qLabel, 0, wx.ALL, 8)
        self.options = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.options.SetName("الخيارات، تنقّل بالأسهم واضغط Enter للتثبيت")
        self.options.Bind(wx.EVT_KEY_DOWN, self._on_opt_key)
        s.Add(self.options, 1, wx.EXPAND | wx.ALL, 6)

        # lifeline buttons
        ll = wx.BoxSizer(wx.HORIZONTAL)
        self.btn5050 = self.button(panel, "٥٠:٥٠", lambda e: self._use_5050())
        self.btnPhone = self.button(panel, "اتصال بصديق", lambda e: self._use_phone())
        self.btnAudience = self.button(panel, "مساعدة الجمهور", lambda e: self._use_audience())
        self.btnSwitch = self.button(panel, "تغيير السؤال", lambda e: self._use_switch())
        for b in (self.btn5050, self.btnPhone, self.btnAudience, self.btnSwitch):
            ll.Add(b, 0, wx.ALL, 3)
        s.Add(ll, 0, wx.ALIGN_RIGHT)

        # action buttons
        act = wx.BoxSizer(wx.HORIZONTAL)
        act.Add(self.button(panel, "ثبّت الإجابة (Enter)", lambda e: self._lock_in()), 0, wx.ALL, 3)
        act.Add(self.button(panel, "أعد قراءة السؤال (Ctrl+R)", lambda e: self.on_repeat()), 0, wx.ALL, 3)
        act.Add(self.button(panel, "السلّم والجائزة", lambda e: self._read_ladder()), 0, wx.ALL, 3)
        act.Add(self.button(panel, "انسحب واحتفظ بالجائزة", lambda e: self._walk_away()), 0, wx.ALL, 3)
        act.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(act, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        self.set_first_control(self.options)
        self.call_after(self.start)

    def say(self, text):
        self.status.SetLabel(text)
        self.announce(text)

    # -- game flow --------------------------------------------------------
    def start(self):
        if not self.bank.all:
            self.say("تعذّر تحميل بنك الأسئلة.")
            return
        self._rung = 0                 # 0-based index into LADDER
        self._used = set()
        self._answered = False
        self._lifelines = {"5050": True, "phone": True, "audience": True, "switch": True}
        self.btn5050.Enable(); self.btnPhone.Enable()
        self.btnAudience.Enable(); self.btnSwitch.Enable()
        self._load_question()
        self.say("أهلاً بك في من سيربح المليون! خمسة عشر سؤالاً تفصلك عن المليون. "
                 "لديك أربع وسائل مساعدة، كلٌّ مرة واحدة. بالتوفيق!")

    def _load_question(self, keep_lifelines=True):
        self._answered = False
        self._removed = set()          # options hidden by 50:50
        self._last_lifeline = ""       # reset per question
        q = self.bank.pick(self._rung + 1, self._used)
        if q is None:
            self.say("نفدت الأسئلة! لقد أبليت بلاءً حسناً.")
            return
        self._q = q
        self._used.add(q.get("id"))
        self._present_question(first=True)

    def _present_question(self, first=False):
        self.qLabel.SetLabel(self._q["q"])
        items = []
        for i, opt in enumerate(self._q["options"]):
            if i in self._removed:
                items.append(f"{OPTION_LETTERS[i]}: —")
            else:
                items.append(f"{OPTION_LETTERS[i]}: {opt}")
        self.options.Set(items)
        # focus first non-removed option
        for i in range(4):
            if i not in self._removed:
                self.select_index(self.options, i)
                break
        prize = ar(LADDER[self._rung])
        lead = f"السؤال رقم {ar(self._rung + 1)} من أجل {prize} نقطة: "
        self.say(lead + self._q["q"] + " — " + self._options_speech())
        if first:
            self.options.SetFocus()

    def _options_speech(self):
        parts = []
        for i, opt in enumerate(self._q["options"]):
            if i not in self._removed:
                parts.append(f"{OPTION_LETTERS[i]}: {opt}")
        return "؛ ".join(parts)

    def _on_opt_key(self, evt):
        # arrow keys move the selection; Enter is handled by on_enter_key (the
        # base dialog routes it there), so here we just let other keys through
        evt.Skip()

    def on_enter_key(self):
        """Enter locks in the selected option when the options list (or nothing
        specific) has focus. When a button has focus, return False so the base
        dialog lets wx deliver Enter to that button natively — this is more
        robust than synthesizing a click and is why the lifeline/action buttons
        now fire."""
        focus = self.FindFocus()
        if isinstance(focus, wx.Button):
            return False        # let wx activate the focused button
        if getattr(self, "_game_over", False):
            return True
        self._lock_in()
        return True

    def _lock_in(self):
        if self._answered:
            return
        i = self.options.GetSelection()
        if i == wx.NOT_FOUND or i in self._removed:
            self.say("اختر إجابة صالحة بالأسهم أولاً.")
            return
        self._answered = True
        correct = self._q["answer"]
        chosen_text = self._q["options"][i]
        if i == correct:
            prize = LADDER[self._rung]
            if self._rung == len(LADDER) - 1:
                self.say(f"إجابة صحيحة! {chosen_text}. لقد ربحت المليون! "
                         f"{ar(prize)} نقطة! أنت بطل! اضغط إغلاق أو ابدأ من جديد بـالسلّم.")
                self._record(prize)
                return
            self.say(f"إجابة صحيحة! {chosen_text}. ربحت {ar(prize)} نقطة. "
                     f"إلى السؤال التالي.")
            self._record(prize)
            self._rung += 1
            self.call_later(1500, self._load_question)
        else:
            correct_text = self._q["options"][correct]
            banked = self._banked_prize()
            self.say(f"للأسف، إجابة خاطئة. الصحيحة كانت {correct_text}. "
                     f"تحتفظ بـ {ar(banked)} نقطة. انتهت اللعبة — اضغط السلّم للعب من جديد.")
            self._record(banked)
            self._game_over = True

    def _banked_prize(self):
        """Winnings the player keeps on a wrong answer: the last safe haven
        passed, otherwise zero."""
        banked = 0
        for idx in sorted(SAFE_HAVENS):
            if self._rung > idx:
                banked = LADDER[idx]
        return banked

    def _walk_away(self):
        if getattr(self, "_game_over", False):
            return
        prize = LADDER[self._rung - 1] if self._rung > 0 else 0
        self.say(f"انسحبت وأنت رابح. تحتفظ بـ {ar(prize)} نقطة. قرار حكيم! "
                 f"اضغط السلّم للعب من جديد.")
        self._record(prize)
        self._game_over = True

    def _record(self, prize):
        try:
            from .games import save_score
            save_score(self.academy, self.GAME_KEY, prize, True)
        except Exception:
            pass

    # -- lifelines --------------------------------------------------------
    def _use_5050(self):
        if not self._lifelines["5050"]:
            self.announce("استُخدمت الخمسون خمسون من قبل.")
            return
        if self._answered:
            return
        self._lifelines["5050"] = False
        self.btn5050.Disable()
        correct = self._q["answer"]
        wrong = [i for i in range(4) if i != correct and i not in self._removed]
        random.shuffle(wrong)
        for i in wrong[:2]:
            self._removed.add(i)
        self._present_question()
        self._last_lifeline = "الخمسون خمسون: حُذف خياران خاطئان. بقي: " + self._options_speech()
        self.say(self._last_lifeline)
        self.options.SetFocus()

    def _use_phone(self):
        if not self._lifelines["phone"]:
            self.announce("استُخدم الاتصال بصديق من قبل.")
            return
        if self._answered:
            return
        self._lifelines["phone"] = False
        self.btnPhone.Disable()
        correct = self._q["answer"]
        avail = [i for i in range(4) if i not in self._removed]
        certainty = 0.9 if self._rung < 5 else 0.75 if self._rung < 10 else 0.6
        if random.random() < certainty:
            guess = correct
            tone = "أنا شبه متأكد،"
        else:
            guess = random.choice([i for i in avail if i != correct] or [correct])
            tone = "لست متأكداً تماماً، لكن أظنّ"
        self._last_lifeline = (f"صديقك يقول: {tone} الإجابة هي "
                               f"{OPTION_LETTERS[guess]}: {self._q['options'][guess]}.")
        self.say(self._last_lifeline)
        self.options.SetFocus()

    def _use_audience(self):
        if not self._lifelines["audience"]:
            self.announce("استُخدمت مساعدة الجمهور من قبل.")
            return
        if self._answered:
            return
        self._lifelines["audience"] = False
        self.btnAudience.Disable()
        correct = self._q["answer"]
        avail = [i for i in range(4) if i not in self._removed]
        weight_correct = 65 if self._rung < 5 else 50 if self._rung < 10 else 40
        votes = {}
        remaining = 100 - weight_correct
        others = [i for i in avail if i != correct]
        for i in others:
            votes[i] = 0
        for _ in range(remaining):
            votes[random.choice(others)] = votes.get(random.choice(others), 0) + 1
        votes[correct] = weight_correct
        total = sum(votes.get(i, 0) for i in avail)
        parts = []
        for i in avail:
            pct = round(votes.get(i, 0) * 100 / total) if total else 0
            parts.append(f"{OPTION_LETTERS[i]}: {ar(pct)}٪")
        self._last_lifeline = "صوّت الجمهور — " + "، ".join(parts) + "."
        self.say(self._last_lifeline)
        self.options.SetFocus()

    def _use_switch(self):
        if not self._lifelines["switch"]:
            self.announce("استُخدم تغيير السؤال من قبل.")
            return
        if self._answered:
            return
        self._lifelines["switch"] = False
        self.btnSwitch.Disable()
        newq = self.bank.pick(self._rung + 1, self._used)
        if newq is None:
            self.say("لا يوجد سؤال بديل متاح.")
            return
        self._q = newq
        self._used.add(newq.get("id"))
        self._removed = set()
        self._present_question()
        self._last_lifeline = ("تم تغيير السؤال. السؤال الجديد: " + self._q["q"] + " — "
                               + self._options_speech())
        self.say(self._last_lifeline)
        self.options.SetFocus()

    # -- info -------------------------------------------------------------
    def _read_ladder(self):
        if getattr(self, "_game_over", False):
            # offer to restart
            self.start()
            return
        lines = []
        for i in range(len(LADDER) - 1, -1, -1):
            marker = " ← أنت هنا" if i == self._rung else ""
            safe = " (محطة أمان)" if i in SAFE_HAVENS else ""
            lines.append(f"{ar(i + 1)}: {ar(LADDER[i])}{safe}{marker}")
        self.say("سلّم الجوائز من الأعلى للأسفل: " + "؛ ".join(lines))

    def on_repeat(self):
        if getattr(self, "_q", None):
            msg = (f"السؤال رقم {ar(self._rung + 1)}: " + self._q["q"] +
                   " — " + self._options_speech())
            # remind the player what their last lifeline told them, so it isn't
            # lost if speech was interrupted
            if getattr(self, "_last_lifeline", ""):
                msg += " — آخر مساعدة: " + self._last_lifeline
            self.say(msg)

    def instructions(self):
        return ("من سيربح المليون: أجب عن ١٥ سؤالاً متدرّج الصعوبة للوصول إلى المليون. "
                "تنقّل بين الخيارات بالأسهم واضغط Enter للتثبيت. المحطتان ٥ و١٠ محطتا أمان "
                "تحتفظ بجائزتهما. لديك أربع وسائل مساعدة مرة واحدة لكلٍّ: الخمسون خمسون، "
                "الاتصال بصديق، مساعدة الجمهور، وتغيير السؤال. يمكنك الانسحاب والاحتفاظ "
                "بجائزتك في أي وقت. Ctrl+R لإعادة السؤال. Escape للإغلاق.")


class TrainingGround(AccessibleDialog):
    """A relaxed practice mode: the player picks a category and answers questions
    from it with no money, no losing, and no game over. Every question shows
    whether the answer was right and, if wrong, what the correct answer was, so
    it's pure learning. A running tally of correct/attempted is kept, and the
    player can change category or leave any time. This is the safe place to build
    knowledge before risking the real من سيربح المليون."""

    TITLE = "ساحة التدريب"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, self.TITLE, speech, size=(680, 600))
        self.academy = academy
        self.bank = _Bank.get(academy.resource_dir)
        panel = wx.Panel(self)
        self._panel = panel
        s = wx.BoxSizer(wx.VERTICAL)
        self.status = wx.StaticText(panel, label="")
        self.status.Wrap(640)
        s.Add(self.status, 0, wx.ALL, 8)

        # category chooser
        crow = wx.BoxSizer(wx.HORIZONTAL)
        crow.Add(wx.StaticText(panel, label="التصنيف:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        cats = ["كل التصنيفات"] + self.bank.categories()
        self._cats = cats
        self.catChoice = wx.Choice(panel, choices=[
            f"{c} ({ar(len(self.bank.by_cat.get(c, [])) or len(self.bank.all))})"
            if c != "كل التصنيفات" else f"{c} ({ar(len(self.bank.all))})"
            for c in cats])
        self.catChoice.SetSelection(0)
        self.bind_choice(self.catChoice, lambda e: self._change_cat())
        crow.Add(self.catChoice, 0)
        s.Add(crow, 0, wx.ALL, 6)

        self.qLabel = wx.StaticText(panel, label="")
        self.qLabel.Wrap(640)
        s.Add(self.qLabel, 0, wx.ALL, 8)
        self.options = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.options.SetName("الخيارات، تنقّل بالأسهم واضغط Enter للإجابة")
        s.Add(self.options, 1, wx.EXPAND | wx.ALL, 6)

        act = wx.BoxSizer(wx.HORIZONTAL)
        act.Add(self.button(panel, "أجب (Enter)", lambda e: self._answer()), 0, wx.ALL, 3)
        act.Add(self.button(panel, "سؤال جديد", lambda e: self._next()), 0, wx.ALL, 3)
        act.Add(self.button(panel, "أعد قراءة السؤال (Ctrl+R)", lambda e: self.on_repeat()), 0, wx.ALL, 3)
        act.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(act, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        self.set_first_control(self.options)
        self._correct = 0
        self._attempted = 0
        self._used = set()
        self.call_after(self._start)

    def say(self, text):
        self.status.SetLabel(text)
        self.announce(text)

    def _cat_pool(self):
        i = self.choice_index(self.catChoice)
        cat = self._cats[i]
        if cat == "كل التصنيفات":
            return self.bank.all
        return self.bank.by_cat.get(cat, self.bank.all)

    def _start(self):
        self.say("ساحة التدريب: اختر تصنيفاً وتدرّب بلا خسارة. سيُخبرك بالإجابة الصحيحة "
                 "بعد كل محاولة. بالتوفيق!")
        self._next()

    def _change_cat(self):
        self._used = set()
        self._correct = self._attempted = 0
        cat = self._cats[self.choice_index(self.catChoice)]
        self.announce(f"التصنيف الآن: {cat}.")
        self._next()

    def _next(self):
        pool = self._cat_pool()
        avail = [q for q in pool if q.get("id") not in self._used]
        if not avail:
            self._used = set()
            avail = pool
        self._q = random.choice(avail)
        self._used.add(self._q.get("id"))
        self._answered = False
        self.qLabel.SetLabel(self._q["q"])
        self.options.Set([f"{OPTION_LETTERS[i]}: {o}"
                          for i, o in enumerate(self._q["options"])])
        self.select_index(self.options, 0)
        self.say(self._q["q"] + " — " + "؛ ".join(
            f"{OPTION_LETTERS[i]}: {o}" for i, o in enumerate(self._q["options"])))
        self.options.SetFocus()

    def _answer(self):
        if getattr(self, "_answered", False):
            self._next()
            return
        i = self.options.GetSelection()
        if i == wx.NOT_FOUND:
            return
        self._answered = True
        self._attempted += 1
        correct = self._q["answer"]
        if i == correct:
            self._correct += 1
            self.say(f"إجابة صحيحة! {self._q['options'][correct]}. "
                     f"نتيجتك {ar(self._correct)} من {ar(self._attempted)}. "
                     f"اضغط Enter أو سؤال جديد للتالي.")
        else:
            self.say(f"إجابة خاطئة. الصحيحة: {self._q['options'][correct]}. "
                     f"لا بأس، هذا تدريب! نتيجتك {ar(self._correct)} من {ar(self._attempted)}. "
                     f"اضغط Enter للسؤال التالي.")

    def on_enter_key(self):
        focus = self.FindFocus()
        if isinstance(focus, wx.Button):
            return False
        self._answer()
        return True

    def on_repeat(self):
        if getattr(self, "_q", None):
            self.say(self._q["q"] + " — " + "؛ ".join(
                f"{OPTION_LETTERS[i]}: {o}" for i, o in enumerate(self._q["options"])))

    def instructions(self):
        return ("ساحة التدريب: اختر تصنيفاً من القائمة وتدرّب على أسئلته بلا خسارة ولا نهاية. "
                "تنقّل بالأسهم واضغط Enter للإجابة، وسيُخبرك بالصحيح بعد كل سؤال. Enter مرة "
                "أخرى للسؤال التالي. Ctrl+R لإعادة السؤال. Escape للإغلاق.")
