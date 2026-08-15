# -*- coding: utf-8 -*-
"""
abaAcademy.gui.games_more
=========================

The second batch of brain-training games for the Games section (see
``games.py`` for the hub and the first batch). All are original implementations
of public-domain game concepts, Arabic/RTL, keyboard-and-speech driven; some
solo, some against a simple built-in AI. Scores persist via ``games.save_score``.
"""

from __future__ import annotations

import random

from .games import _GameBase, GridGameDialog, ar, save_score

try:
    import wx
except Exception:
    wx = None


# --------------------------------------------------------------------------
# MEMORY
# --------------------------------------------------------------------------

class PairsMemory(_GameBase):
    """Concentration/pairs: a set of hidden pairs on numbered cards; find them
    all in the fewest flips. Announced entirely by speech."""
    TITLE = "أزواج متطابقة"
    GAME_KEY = "pairs"
    HIGHER_BETTER = False   # fewer flips is better
    SYMBOLS = ["نجمة", "قلب", "قمر", "شمس", "وردة", "سمكة", "طائر", "شجرة"]

    def start(self):
        n = 6                      # 6 pairs = 12 cards
        syms = self.SYMBOLS[:n] * 2
        random.shuffle(syms)
        self._cards = syms
        self._found = [False] * len(syms)
        self._first = None
        self._flips = 0
        self.say(f"اثنتا عشرة بطاقة مرقّمة ١ إلى ١٢، خلفها {ar(n)} أزواج. اكتب رقم بطاقة "
                 f"لقلبها، ثم رقم بطاقة أخرى؛ إن تطابقتا بقيتا مكشوفتين. جد كل الأزواج "
                 f"بأقل عدد قلبات.")

    def handle(self, text):
        try:
            i = int(text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))) - 1
        except ValueError:
            self.say("اكتب رقم بطاقة من ١ إلى ١٢.")
            return
        if i < 0 or i >= len(self._cards) or self._found[i]:
            self.say("بطاقة غير صالحة أو مكشوفة.")
            return
        if self._first is None:
            self._first = i
            self.say(f"البطاقة {ar(i + 1)}: {self._cards[i]}. اكتب بطاقة ثانية.")
            return
        if i == self._first:
            self.say("نفس البطاقة. اختر أخرى.")
            return
        self._flips += 1
        a, b = self._first, i
        self._first = None
        if self._cards[a] == self._cards[b]:
            self._found[a] = self._found[b] = True
            if all(self._found):
                self.say(f"أحسنت! وجدت كل الأزواج في {ar(self._flips)} قلبة. «لعبة جديدة».")
                self.record(self._flips)
            else:
                self.say(f"تطابق! {self._cards[a]}. تبقّى {ar(self._found.count(False) // 2)} أزواج.")
        else:
            self.say(f"البطاقة {ar(b + 1)}: {self._cards[b]}. لا تطابق. "
                     f"عدد القلبات {ar(self._flips)}.")

    def instructions(self):
        return ("لعبة ذاكرة: اقلب بطاقتين في كل مرة بكتابة رقميهما؛ الزوجان المتطابقان "
                "يبقيان مكشوفين. جد كل الأزواج بأقل قلبات. Escape للإغلاق.")


# --------------------------------------------------------------------------
# MATH / NUMBER
# --------------------------------------------------------------------------

class SequenceGame(_GameBase):
    """Find the next number in an arithmetic or geometric sequence."""
    TITLE = "أكمل المتتالية"
    GAME_KEY = "sequence"

    def start(self):
        self._score = 0
        self._ask()

    def _ask(self):
        kind = random.choice(["add", "mul", "square"])
        if kind == "add":
            start = random.randint(1, 9)
            step = random.randint(2, 6)
            seq = [start + step * i for i in range(4)]
            self._answer = start + step * 4
        elif kind == "mul":
            start = random.randint(1, 4)
            r = random.randint(2, 3)
            seq = [start * (r ** i) for i in range(4)]
            self._answer = start * (r ** 4)
        else:
            seq = [(i + 1) ** 2 for i in range(4)]
            self._answer = 25
        self._seq = seq
        self.say("ما العدد التالي؟ " + "، ".join(ar(x) for x in seq) +
                 f" (النتيجة {ar(self._score)})")

    def handle(self, text):
        try:
            v = int(text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
        except ValueError:
            self.say("اكتب رقماً.")
            return
        if v == self._answer:
            self._score += 1
            self.record(self._score)
            self._ask()
        else:
            self.say(f"خطأ، الصواب {ar(self._answer)}. نتيجتك {ar(self._score)}. «لعبة جديدة».")
            self._score = 0

    def instructions(self):
        return "تُعرض أربعة أعداد على نمط معيّن؛ اكتب العدد الخامس. Escape للإغلاق."


class MakeTarget(_GameBase):
    """Reach a target by choosing which of the given numbers to add."""
    TITLE = "اجمع للوصول"
    GAME_KEY = "make_target"

    def start(self):
        self._nums = [random.randint(2, 15) for _ in range(5)]
        # ensure a solvable target from a subset
        k = random.randint(2, 4)
        self._target = sum(random.sample(self._nums, k))
        self.say(f"الأعداد المتاحة: {'، '.join(ar(n) for n in self._nums)}. "
                 f"اختر بعضها ليكون مجموعها {ar(self._target)}؛ اكتبها مفصولة بمسافات.")

    def handle(self, text):
        picks = []
        for tok in text.replace("،", " ").split():
            try:
                picks.append(int(tok.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))))
            except ValueError:
                pass
        # verify picks are available (with multiplicity) and sum to target
        avail = list(self._nums)
        ok = True
        for p in picks:
            if p in avail:
                avail.remove(p)
            else:
                ok = False
                break
        if ok and picks and sum(picks) == self._target:
            self.say(f"أحسنت! {' + '.join(ar(p) for p in picks)} = {ar(self._target)}. «لعبة جديدة».")
            self.record(1)
        else:
            self.say(f"المجموع {ar(sum(picks))} لا يساوي {ar(self._target)} أو أعداد غير متاحة. حاول ثانية.")

    def instructions(self):
        return ("اختر من الأعداد المعطاة ما مجموعه العدد المطلوب، واكتبها مفصولة بمسافات. "
                "Escape للإغلاق.")


class OddEven(_GameBase):
    """Fast odd/even classification against a 45-second clock; how many can you
    get right before time runs out?"""
    TITLE = "زوجيّ أم فرديّ"
    GAME_KEY = "odd_even"
    TIME_LIMIT = 45

    def start(self):
        self._score = 0
        self._begin_timer()
        self.say("لديك ٤٥ ثانية. صنّف أكبر عددٍ من الأرقام.")
        self._ask()

    def _ask(self):
        self._n = random.randint(2, 999)
        self.say(f"هل {ar(self._n)} زوجيّ أم فرديّ؟ اكتب «زوجي» أو «فردي». "
                 f"(النتيجة {ar(self._score)})")

    def handle(self, text):
        t = text.strip()
        is_even = self._n % 2 == 0
        said_even = "زوج" in t
        said_odd = "فرد" in t
        if not (said_even or said_odd):
            self.say("اكتب «زوجي» أو «فردي».")
            return
        if (said_even and is_even) or (said_odd and not is_even):
            self._score += 1
            self.record(self._score)
            self._ask()
        else:
            self.say(f"خطأ. {ar(self._n)} {'زوجيّ' if is_even else 'فرديّ'}. "
                     f"تابع! (النتيجة {ar(self._score)})")
            self._ask()

    def instructions(self):
        return "صنّف الأعداد بسرعة: زوجيّ أم فرديّ؛ كل إجابة صحيحة تزيد نتيجتك. Escape للإغلاق."


# --------------------------------------------------------------------------
# LOGIC / STRATEGY (vs computer)
# --------------------------------------------------------------------------

class NimGame(_GameBase):
    """Nim (نيم): a pile of sticks; each turn take 1, 2 or 3. Two rules, chosen by
    the player: either whoever takes the LAST stick WINS (normal play), or whoever
    takes the last stick LOSES (misère play). The computer plays the correct
    optimal strategy for whichever rule is set, at three strengths:

      * سهل: usually random — easy to beat.
      * متوسّط: plays well most of the time but slips occasionally.
      * صعب: always optimal — only beatable if you know the trick and it starts
        from a losing position for it.

    Normal play: leave a multiple of 4. Misère play: same, until only small piles
    remain, then leave your opponent exactly one stick.
    """
    TITLE = "نيم"
    GAME_KEY = "nim"

    def __init__(self, parent, academy, speech):
        # build our own controls (rule + level choosers) on top of the base
        super().__init__(parent, academy, speech, size=(600, 460))

    def _extra_controls(self, panel, sizer):
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(panel, label="القاعدة:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.ruleChoice = wx.Choice(panel, choices=["من يأخذ الأخير يفوز", "من يأخذ الأخير يخسر"])
        self.ruleChoice.SetSelection(0)
        self.bind_choice(self.ruleChoice, lambda e: self.start())
        row.Add(self.ruleChoice, 0, wx.RIGHT, 8)
        row.Add(wx.StaticText(panel, label="المستوى:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.levelChoice = wx.Choice(panel, choices=["سهل", "متوسّط", "صعب"])
        self.levelChoice.SetSelection(1)
        self.bind_choice(self.levelChoice, lambda e: self.start())
        row.Add(self.levelChoice, 0)
        sizer.Insert(1, row, 0, wx.ALL, 6)

    def start(self):
        self._n = random.randint(12, 21)
        self._misere = self.ruleChoice.GetSelection() == 1 if hasattr(self, "ruleChoice") else False
        rule = "من يأخذ العود الأخير يخسر" if self._misere else "من يأخذ العود الأخير يفوز"
        self.say(f"أمامنا {ar(self._n)} عوداً. في دورك خذ ١ أو ٢ أو ٣. القاعدة: {rule}. "
                 f"ابدأ: كم تأخذ؟")

    def _optimal_take(self, n, misere):
        """Best move for the mover facing ``n`` sticks under the chosen rule.
        Returns a take in 1..3, or None when the position is lost (no winning
        move — then any legal move is returned by the caller)."""
        if misere:
            # misère Nim with max-take 3: play to leave a multiple of 4 EXCEPT
            # when the only sticks left are few — then leave exactly 1 for the
            # opponent. Concretely: if n>4, mirror to a multiple of 4; if n<=4,
            # leave 1 (take n-1), forcing the opponent to take the last.
            if n == 1:
                return 1          # forced to take the last (and lose) — no escape
            if n <= 4:
                return n - 1      # leave exactly 1 for the opponent
            t = (n - 1) % 4
            return t if t != 0 else None
        else:
            t = n % 4
            return t if t != 0 else None

    def handle(self, text):
        try:
            take = int(text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
        except ValueError:
            self.say("اكتب ١ أو ٢ أو ٣.")
            return
        if take < 1 or take > 3 or take > self._n:
            self.say("عدد غير صالح. خذ ١ أو ٢ أو ٣ (وليس أكثر من المتبقّي).")
            return
        self._n -= take
        if self._n == 0:
            # player took the last stick
            if self._misere:
                self.say("أخذتَ العود الأخير، وبالقاعدة الحالية خسرت. «لعبة جديدة».")
            else:
                self.say("أخذت العود الأخير ففزت! أحسنت. «لعبة جديدة».")
                self.record(1)
            return
        # AI move by difficulty
        level = self.levelChoice.GetSelection() if hasattr(self, "levelChoice") else 2
        if level == 0:
            ai_take = random.randint(1, min(3, self._n))
        elif level == 1 and random.random() < 0.3:
            ai_take = random.randint(1, min(3, self._n))
        else:
            opt = self._optimal_take(self._n, self._misere)
            ai_take = opt if opt else random.randint(1, min(3, self._n))
        ai_take = max(1, min(ai_take, min(3, self._n)))
        self._n -= ai_take
        if self._n == 0:
            if self._misere:
                self.say(f"أخذ الحاسوب {ar(ai_take)}، فأخذ العود الأخير وبالقاعدة الحالية "
                         f"خسر، ففزت! «لعبة جديدة».")
                self.record(1)
            else:
                self.say(f"أخذ الحاسوب {ar(ai_take)} فأخذ العود الأخير وفاز. «لعبة جديدة».")
            return
        self.say(f"أخذ الحاسوب {ar(ai_take)}. تبقّى {ar(self._n)} عوداً. كم تأخذ؟")

    def instructions(self):
        return ("نيم: بالتناوب تأخذان من الكومة ١ إلى ٣ أعواد. اختر القاعدة (من يأخذ الأخير "
                "يفوز أو يخسر) والمستوى (سهل، متوسّط، صعب). الحاسوب يلعب بالاستراتيجية المثلى "
                "للقاعدة المختارة. Escape للإغلاق.")
        return ("لعبة نيم: بالتناوب تأخذان من الكومة ١ إلى ٣ أعواد، ومن يأخذ الأخير يفوز. "
                "الحاسوب يلعب بذكاء — هل تجد الحيلة؟ Escape للإغلاق.")


class MiniBattleship(GridGameDialog):
    """Mini-battleship on a navigable 5x5 grid: find the computer's hidden 3-cell
    ship in the fewest shots. Move the cursor with the arrow keys (no wrapping)
    and press Enter to fire at the current cell; each cell announces its address
    and whether you've already fired there and hit or missed."""
    GAME_KEY = "battleship"
    HIGHER_BETTER = False
    ROWS = 5
    COLS = 5
    COL_LABELS = "أبجده"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech, "بحر السفن الصغير", size=(600, 560))
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        self.build_grid(panel, s)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "أطلق هنا (Enter)", lambda e: self.activate(self._row, self._col)), 0, wx.ALL, 4)
        row.Add(self.button(panel, "لعبة جديدة", lambda e: self.start()), 0, wx.ALL, 4)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        s.Add(row, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        self.set_first_control(self.grid)
        wx.CallAfter(self.start)

    def start(self):
        horiz = random.choice([True, False])
        if horiz:
            r = random.randint(0, 4); c = random.randint(0, 2)
            self._ship = {(r, c + i) for i in range(3)}
        else:
            r = random.randint(0, 2); c = random.randint(0, 4)
            self._ship = {(r + i, c) for i in range(3)}
        self._hits = set()
        self._missed = set()
        self._shots = 0
        self._over = False
        self.set_cursor(0, 0)
        self.refresh_grid()
        self.say("سفينة من ٣ خانات مخبّأة في شبكة ٥×٥. تنقّل بالأسهم واضغط Enter "
                 "للإطلاق على الخانة. جدها بأقل عدد من الطلقات.")
        wx.CallAfter(self.grid.SetFocus)

    def cell_word(self, r, c):
        cell = (r, c)
        if cell in self._hits:
            return "إصابة"
        if cell in self._missed:
            return "ماء"
        return "لم تُطلق"

    def activate(self, r, c):
        if self._over:
            self.say("انتهت اللعبة. «لعبة جديدة».")
            return
        cell = (r, c)
        if cell in self._hits or cell in self._missed:
            self.say(f"{self.addr(r, c)} أطلقت عليها من قبل.")
            return
        self._shots += 1
        if cell in self._ship:
            self._hits.add(cell)
            self.refresh_grid()
            if self._hits == self._ship:
                self._over = True
                self.say(f"أغرقت السفينة في {ar(self._shots)} طلقة! «لعبة جديدة».")
                if save_score(self.academy, self.GAME_KEY, self._shots, False):
                    self.announce("رقم قياسي جديد بأقل الطلقات!")
            else:
                self.say(f"إصابة في {self.addr(r, c)}! ({ar(len(self._hits))} من ٣). "
                         f"الطلقات {ar(self._shots)}.")
        else:
            self._missed.add(cell)
            self.refresh_grid()
            self.say(f"ماء في {self.addr(r, c)}. الطلقات {ar(self._shots)}.")

    def instructions(self):
        return ("جد سفينةً من ٣ خانات في شبكة ٥×٥ بأقل طلقات. تنقّل بأسهم الاتجاهات الأربعة "
                "(بلا التفاف) واضغط Enter للإطلاق. كل خانة تنطق عنوانها وحالتها. Escape للإغلاق.")


class Mastermind(_GameBase):
    """Guess a 4-digit secret code (digits 1-6). Feedback: how many are correct
    and in place, and how many are correct but misplaced."""
    TITLE = "ماستر مايند بالأرقام"
    GAME_KEY = "mastermind"
    HIGHER_BETTER = False

    def start(self):
        self._code = [random.randint(1, 6) for _ in range(4)]
        self._tries = 0
        self.say("خمّنتُ رمزاً من ٤ أرقام، كل رقم بين ١ و٦ (قد يتكرر). اكتب أربعة أرقام "
                 "متتابعة. سأخبرك كم رقماً في مكانه الصحيح وكم رقماً صحيح بمكان خاطئ.")

    def handle(self, text):
        digits = [int(c) for c in text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
                  if c.isdigit()]
        if len(digits) != 4 or any(d < 1 or d > 6 for d in digits):
            self.say("اكتب أربعة أرقام، كلٌّ بين ١ و٦.")
            return
        self._tries += 1
        exact = sum(1 for i in range(4) if digits[i] == self._code[i])
        # count colour matches
        from collections import Counter
        cc, gc = Counter(self._code), Counter(digits)
        total = sum(min(cc[k], gc[k]) for k in cc)
        misplaced = total - exact
        if exact == 4:
            self.say(f"أصبت الرمز في {ar(self._tries)} محاولة! «لعبة جديدة».")
            self.record(self._tries)
        else:
            self.say(f"{ar(exact)} في مكانه الصحيح، و{ar(misplaced)} صحيح بمكان خاطئ. "
                     f"المحاولات {ar(self._tries)}.")

    def instructions(self):
        return ("خمّن الرمز السرّي (٤ أرقام من ١ إلى ٦) بأقل محاولات. بعد كل تخمين تعرف "
                "كم رقماً في مكانه وكم رقماً صحيحاً بمكان خاطئ. Escape للإغلاق.")


class TrueFalseBlitz(_GameBase):
    """Rapid true/false on arithmetic facts against a 45-second clock."""
    TITLE = "صح أم خطأ سريع"
    GAME_KEY = "tf_blitz"
    TIME_LIMIT = 45

    def start(self):
        self._score = 0
        self._begin_timer()
        self.say("لديك ٤٥ ثانية. احكم على أكبر عددٍ من العبارات.")
        self._ask()

    def _ask(self):
        a, b = random.randint(2, 12), random.randint(2, 12)
        op = random.choice(["+", "-", "×"])
        real = a + b if op == "+" else a - b if op == "-" else a * b
        # half the time show a wrong result
        if random.random() < 0.5:
            shown = real
            self._truth = True
        else:
            shown = real + random.choice([-3, -2, -1, 1, 2, 3])
            self._truth = (shown == real)
        self.say(f"هل {ar(a)} {op} {ar(b)} = {ar(shown)}؟ اكتب «صح» أو «خطأ». "
                 f"(النتيجة {ar(self._score)})")

    def handle(self, text):
        t = text.strip()
        said = True if ("صح" in t or "نعم" in t) else False if ("خطأ" in t or "لا" in t) else None
        if said is None:
            self.say("اكتب «صح» أو «خطأ».")
            return
        if said == self._truth:
            self._score += 1
            self.record(self._score)
            self._ask()
        else:
            self.say(f"غير صحيح. تابع! (النتيجة {ar(self._score)})")
            self._ask()

    def instructions(self):
        return ("عبارات حسابية سريعة؛ احكم هل هي صحيحة أم خاطئة بأسرع ما يمكن. Escape للإغلاق.")


# --------------------------------------------------------------------------
# WORD / LANGUAGE
# --------------------------------------------------------------------------

class WordScramble(_GameBase):
    """Unscramble the shuffled letters of an Arabic word."""
    TITLE = "كوّن الكلمة"
    GAME_KEY = "scramble"
    WORDS = ["مدرسة", "معلم", "طالب", "كتاب", "قلم", "حديقة", "شجرة", "زهرة",
             "مفتاح", "نافذة", "سيارة", "طريق", "مدينة", "قرية", "بحر", "جبل"]

    def start(self):
        self._score = 0
        self._ask()

    def _ask(self):
        self._word = random.choice(self.WORDS)
        letters = list(self._word)
        random.shuffle(letters)
        # ensure it's actually shuffled
        if "".join(letters) == self._word and len(set(letters)) > 1:
            letters.reverse()
        self.say("رتّب هذه الحروف لتكوّن كلمة: " + " ، ".join(letters) +
                 f" (النتيجة {ar(self._score)})")

    def handle(self, text):
        if text.strip() == self._word:
            self._score += 1
            self.record(self._score)
            self.say("أحسنت!")
            wx.CallLater(700, self._ask)
        else:
            self.say(f"ليست صحيحة. الكلمة كانت «{self._word}». نتيجتك {ar(self._score)}. «لعبة جديدة».")
            self._score = 0

    def on_repeat(self):
        letters = list(self._word)
        random.shuffle(letters)
        self.say("الحروف: " + " ، ".join(letters))

    def instructions(self):
        return "تُعطى حروفاً مبعثرة؛ اكتب الكلمة الصحيحة منها. Escape للإغلاق."


class ReverseWord(_GameBase):
    """Say/spell a word backwards — a working-memory challenge."""
    TITLE = "عكس الكلمة"
    GAME_KEY = "reverse"
    WORDS = ["شمس", "قمر", "نجم", "بحر", "ورد", "علم", "قلم", "باب",
             "نور", "فجر", "غيم", "زهر", "سحر", "بدر", "رمل"]

    def start(self):
        self._score = 0
        self._ask()

    def _ask(self):
        self._word = random.choice(self.WORDS)
        self._rev = self._word[::-1]
        self.say(f"اكتب حروف كلمة «{self._word}» بالعكس. (النتيجة {ar(self._score)})")

    def handle(self, text):
        if text.strip() == self._rev:
            self._score += 1
            self.record(self._score)
            self.say("صحيح!")
            wx.CallLater(700, self._ask)
        else:
            self.say(f"خطأ. عكس «{self._word}» هو «{self._rev}». نتيجتك {ar(self._score)}. «لعبة جديدة».")
            self._score = 0

    def instructions(self):
        return "تُعطى كلمة؛ اكتب حروفها بترتيب معكوس. تمرين ممتاز للذاكرة العاملة. Escape للإغلاق."


class WordChain(_GameBase):
    """Word chain (سلسلة الكلمات): you and the computer take turns giving a word
    that starts with the last letter of the previous word. The player's word must
    be a real Arabic word — checked against the offline dictionary — so an
    invalid word is rejected and the turn stays with the player until they give a
    genuine one. The computer answers from the whole dictionary, so it's a real
    challenge, not a 30-word list."""
    TITLE = "أول حرف آخر حرف"
    GAME_KEY = "chain"
    SEEDS = ["باب", "برتقال", "لبن", "نمر", "رمان", "نهر", "وردة", "تفاح",
             "حصان", "نجمة", "أسد", "دار", "رمل", "ليمون", "بحر", "سماء"]

    def start(self):
        from ..dictionary_ar import ArabicDictionary, normalize
        self._dict = ArabicDictionary.get(self.academy.resource_dir)
        self._normalize = normalize
        self._used = set()
        self._score = 0
        first = random.choice(self.SEEDS)
        self._used.add(self._normalize(first))
        self._last_letter = first[-1]
        self.say(f"بدأتُ بكلمة «{first}». اكتب كلمة عربية حقيقية تبدأ بحرف "
                 f"«{self._last_letter}». لا تكرّر كلمة. (النتيجة {ar(self._score)})")

    def _norm_first(self, w):
        # first letter after normalizing leading hamza forms to bare alef would
        # lose information, so match on the raw first character the learner sees
        return w[0]

    def handle(self, text):
        w = text.strip()
        if not w:
            return
        if len(w) < 2:
            self.say("الكلمة قصيرة جداً. اكتب كلمة حقيقية.")
            return
        if self._norm_first(w) != self._last_letter:
            self.say(f"يجب أن تبدأ بحرف «{self._last_letter}». حاول ثانية.")
            return
        if self._normalize(w) in self._used:
            self.say("استُخدمت من قبل. جرّب كلمة أخرى.")
            return
        # must be a real word — otherwise it's wrong and the turn stays with the
        # player until they produce a genuine dictionary word
        if not self._dict.is_word(w):
            self.say(f"«{w}» ليست في القاموس. اكتب كلمة عربية صحيحة تبدأ بحرف "
                     f"«{self._last_letter}».")
            return
        self._used.add(self._normalize(w))
        self._score += 1
        self.record(self._score)
        need = w[-1]
        reply = self._computer_word(need)
        if reply is None:
            self.say(f"أحسنت! لم أجد كلمة تبدأ بحرف «{need}»، ففزت! "
                     f"نتيجتك {ar(self._score)}. «لعبة جديدة».")
            return
        self._used.add(self._normalize(reply))
        self._last_letter = reply[-1]
        self.say(f"كلمتي «{reply}». الآن اكتب كلمة تبدأ بحرف «{self._last_letter}».")

    def _computer_word(self, letter):
        """Find an unused dictionary word starting with ``letter``. Prefers short,
        common-length words so its replies stay natural."""
        candidates = []
        for w in self._dict._words:
            if w and w[0] == letter and 3 <= len(w) <= 6 \
                    and self._normalize(w) not in self._used:
                candidates.append(w)
                if len(candidates) >= 400:
                    break
        return random.choice(candidates) if candidates else None

    def instructions(self):
        return ("سلسلة كلمات مع الحاسوب: كل كلمة تبدأ بآخر حرف من الكلمة السابقة، بلا تكرار. "
                "يجب أن تكون كلمتك عربية حقيقية (تُدقَّق في القاموس)، وإلا بقي الدور لك. "
                "Escape للإغلاق.")


# --------------------------------------------------------------------------
# more number / logic games (added batch)
# --------------------------------------------------------------------------

class BullsAndCows(_GameBase):
    """Bulls & Cows: guess a secret number of distinct digits. After each guess
    you learn how many digits are correct and in place ("ثيران/bulls") and how
    many are correct but misplaced ("أبقار/cows"). A classic deduction game and
    the numeric ancestor of Mastermind."""
    TITLE = "ثيران وأبقار"
    GAME_KEY = "bulls_cows"
    HIGHER_BETTER = False

    def start(self):
        digits = list("0123456789")
        random.shuffle(digits)
        self._code = digits[:4]           # 4 distinct digits
        self._tries = 0
        self.say("خمّنتُ عدداً من ٤ أرقام مختلفة (بلا تكرار). اكتب أربعة أرقام؛ "
                 "سأخبرك كم رقماً في مكانه الصحيح (ثيران) وكم رقماً صحيح بمكان خاطئ (أبقار).")

    def handle(self, text):
        s = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        guess = [c for c in s if c.isdigit()]
        if len(guess) != 4 or len(set(guess)) != 4:
            self.say("اكتب أربعة أرقام مختلفة.")
            return
        self._tries += 1
        bulls = sum(1 for i in range(4) if guess[i] == self._code[i])
        cows = sum(1 for d in guess if d in self._code) - bulls
        if bulls == 4:
            self.say(f"أصبت العدد في {ar(self._tries)} محاولة! «لعبة جديدة».")
            self.record(self._tries)
        else:
            self.say(f"{ar(bulls)} ثيران، {ar(cows)} أبقار. المحاولات {ar(self._tries)}.")

    def instructions(self):
        return ("خمّن عدداً من ٤ أرقام مختلفة. بعد كل محاولة تعرف كم رقماً في مكانه الصحيح "
                "(ثيران) وكم رقماً صحيحاً في مكان خاطئ (أبقار). حاول بأقل محاولات. Escape للإغلاق.")


class TwentyOne(_GameBase):
    """Twenty-one (a simple Blackjack): draw cards to get as close to 21 as you
    can without going over, then the dealer draws to 17. Solo vs a dealer AI."""
    TITLE = "الواحد والعشرون"
    GAME_KEY = "twenty_one"

    def _draw(self):
        # cards 1..11 (face cards counted simply as 10, ace as 11 then 1)
        return random.choice([2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11])

    def start(self):
        self._you = [self._draw(), self._draw()]
        self._dealer = [self._draw()]
        self._done = False
        self.say(f"لديك {self._hand_str(self._you)}، المجموع {ar(self._total(self._you))}. "
                 f"ورقة البائع الظاهرة {ar(self._dealer[0])}. اكتب «سحب» لورقة أخرى "
                 f"أو «قف» للتوقّف.")

    def _total(self, hand):
        total = sum(hand)
        # soften aces (11 -> 1) while busting
        aces = hand.count(11)
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

    def _hand_str(self, hand):
        return "، ".join(ar(c) for c in hand)

    def handle(self, text):
        t = text.strip()
        if self._done:
            self.say("انتهت الجولة. «لعبة جديدة».")
            return
        if "سحب" in t or "ورقة" in t:
            self._you.append(self._draw())
            tot = self._total(self._you)
            if tot > 21:
                self._done = True
                self.say(f"سحبت {ar(self._you[-1])}، المجموع {ar(tot)} — تجاوزت ٢١، خسرت. «لعبة جديدة».")
            else:
                self.say(f"سحبت {ar(self._you[-1])}، المجموع {ar(tot)}. «سحب» أو «قف»؟")
        elif "قف" in t or "توقف" in t or "وقف" in t:
            self._settle()
        else:
            self.say("اكتب «سحب» أو «قف».")

    def _settle(self):
        self._done = True
        while self._total(self._dealer) < 17:
            self._dealer.append(self._draw())
        you, deal = self._total(self._you), self._total(self._dealer)
        msg = f"مجموعك {ar(you)}، مجموع البائع {ar(deal)}. "
        if deal > 21 or you > deal:
            msg += "فزت! أحسنت. «لعبة جديدة»."
            self.record(1)
        elif you == deal:
            msg += "تعادل. «لعبة جديدة»."
        else:
            msg += "فاز البائع. «لعبة جديدة»."
        self.say(msg)

    def instructions(self):
        return ("اقترب من ٢١ دون تجاوزها. اكتب «سحب» لورقة جديدة أو «قف» للتوقّف، ثم يسحب "
                "البائع حتى ١٧. من يقترب أكثر دون تجاوز يفوز. Escape للإغلاق.")


class CountingGame(_GameBase):
    """Count-and-recall: a quick 'how many' mental tally. The game names a run
    of items and asks how many matched a rule — trains focus and working memory."""
    TITLE = "عُدّ وركّز"
    GAME_KEY = "counting"

    def start(self):
        self._score = 0
        self._ask()

    def _ask(self):
        n = random.randint(6, 10)
        self._items = [random.choice(["تفاحة", "برتقالة", "موزة"]) for _ in range(n)]
        self._target = random.choice(["تفاحة", "برتقالة", "موزة"])
        self._answer = self._items.count(self._target)
        self.say("سأذكر لك قائمة، عُدّ كم مرة تكرّرت كلمة «" + self._target + "»: " +
                 "، ".join(self._items) + f". كم مرة؟ (النتيجة {ar(self._score)})")

    def handle(self, text):
        try:
            v = int(text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
        except ValueError:
            self.say("اكتب رقماً.")
            return
        if v == self._answer:
            self._score += 1
            self.record(self._score)
            self._ask()
        else:
            self.say(f"العدد الصحيح {ar(self._answer)}. نتيجتك {ar(self._score)}. «لعبة جديدة».")
            self._score = 0

    def on_repeat(self):
        self.say("القائمة: " + "، ".join(self._items) + f" — عُدّ «{self._target}».")

    def instructions(self):
        return ("تُذكر لك قائمة أشياء؛ عُدّ كم مرة تكرّر شيء معيّن واكتب العدد. تمرين للتركيز "
                "والذاكرة العاملة. Ctrl+R لإعادة القائمة. Escape للإغلاق.")


class MissingNumber(_GameBase):
    """A set of consecutive numbers is read with one missing; name it. Trains
    attention and number sense."""
    TITLE = "الرقم الناقص"
    GAME_KEY = "missing_number"

    def start(self):
        self._score = 0
        self._ask()

    def _ask(self):
        start = random.randint(1, 20)
        count = random.randint(6, 9)
        seq = list(range(start, start + count))
        self._missing = random.choice(seq[1:-1])
        shown = [x for x in seq if x != self._missing]
        self.say("رقمٌ ناقص من هذه المتتالية المرتّبة، ما هو؟ " +
                 "، ".join(ar(x) for x in shown) + f" (النتيجة {ar(self._score)})")

    def handle(self, text):
        try:
            v = int(text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
        except ValueError:
            self.say("اكتب رقماً.")
            return
        if v == self._missing:
            self._score += 1
            self.record(self._score)
            self._ask()
        else:
            self.say(f"الناقص كان {ar(self._missing)}. نتيجتك {ar(self._score)}. «لعبة جديدة».")
            self._score = 0

    def instructions(self):
        return ("تُقرأ متتالية أعداد مرتّبة ينقصها رقم واحد؛ اكتب الرقم الناقص. Escape للإغلاق.")


class RhymeOrStart(_GameBase):
    """Letter fluency (كلمات بحرف): in 60 seconds, name as many real Arabic words
    as you can that begin with a given letter. Every word is checked against the
    offline dictionary, so any genuine word counts — not just a short fixed list.
    Trains lexical retrieval."""
    TITLE = "كلمات بحرف"
    GAME_KEY = "letter_words"
    TIME_LIMIT = 60
    LETTERS = "بتثجحخدذرزسشصضطظعغفقكلمنهو"

    def start(self):
        from ..dictionary_ar import ArabicDictionary, normalize
        self._dict = ArabicDictionary.get(self.academy.resource_dir)
        self._normalize = normalize
        self._letter = random.choice(self.LETTERS)
        self._found = set()
        self._score = 0
        self._begin_timer()
        self.say(f"لديك ٦٠ ثانية. اذكر أكبر عددٍ من الكلمات العربية الحقيقية التي تبدأ "
                 f"بحرف «{self._letter}»، واحدة في كل مرة.")

    def handle(self, text):
        w = text.strip()
        if not w:
            return
        if w[0] != self._letter:
            self.say(f"يجب أن تبدأ بحرف «{self._letter}».")
            return
        nw = self._normalize(w)
        if nw in self._found:
            self.say("ذكرتها من قبل. جرّب غيرها.")
            return
        if len(w) < 2 or not self._dict.is_word(w):
            self.say(f"«{w}» ليست في القاموس. جرّب كلمة أخرى.")
            return
        self._found.add(nw)
        self._score += 1
        self.say(f"أحسنت! «{w}» صحيحة. عندك {ar(self._score)} كلمة.")

    def instructions(self):
        return ("اذكر أكبر عددٍ من الكلمات الحقيقية التي تبدأ بالحرف المطلوب في ٦٠ ثانية؛ "
                "تُدقَّق كل كلمة في القاموس. تمرين لطلاقة الكلمات. Escape للإغلاق.")


# --------------------------------------------------------------------------
# ANAGRAMS (timed, judged by the offline Arabic dictionary)
# --------------------------------------------------------------------------

class Anagrams(_GameBase):
    """Anagrams against the clock: you are given the shuffled letters of a word,
    and in 90 seconds you type as many real Arabic words as you can make from
    those letters. Each word is checked against a bundled offline Arabic
    dictionary (no internet needed), so only genuine words score. Longer words
    score more. Finding the original full-length word gives a bonus."""

    TITLE = "الكلمات المبعثرة (أناغرام)"
    GAME_KEY = "anagrams"
    TIME_LIMIT = 90

    def start(self):
        from ..dictionary_ar import ArabicDictionary, normalize
        self._dict = ArabicDictionary.get(self.academy.resource_dir)
        self._normalize = normalize
        self._pool = self._dict.anagram_pool() or ["مدرسة", "كتاب", "حديقة"]
        self._score = 0
        self._begin_timer()
        self.say("لديك ٩٠ ثانية. كوّن كلمات عربية حقيقية من الحروف المعطاة. "
                 "كلّما وجدت كل كلمات الحروف الحالية انتقلنا إلى حروفٍ جديدة. "
                 "اكتب «حروف» لسماع الحروف من جديد.")
        self._new_word(first=True)

    def _new_word(self, first=False):
        # pick a source with at least a few findable sub-words
        for _ in range(40):
            src = random.choice([w for w in self._pool if len(w) >= 5] or self._pool)
            findable = self._dict.findable_from(src)
            if len(findable) >= 2:
                break
        self._source = src
        self._findable = findable          # normalized set of all valid answers
        self._letters = list(self._source)
        random.shuffle(self._letters)
        self._found = set()
        lead = "" if first else "أحسنت! وجدت كل الكلمات. حروف جديدة: "
        self.say(lead + "الحروف: " + " ، ".join(self._letters) +
                 f" (يمكن تكوين {ar(len(self._findable))} كلمة).")

    def _can_make(self, word):
        from collections import Counter
        need = Counter(self._normalize(word))
        have = Counter(self._normalize(self._source))
        return all(have.get(ch, 0) >= n for ch, n in need.items())

    def handle(self, text):
        w = text.strip()
        if not w:
            return
        if w in ("حروف", "الحروف"):
            self.say("الحروف: " + " ، ".join(self._letters))
            return
        if len(w) < 2:
            self.say("الكلمة قصيرة جداً. حرفان على الأقل.")
            return
        nw = self._normalize(w)
        if nw in self._found:
            self.say("وجدتها من قبل. جرّب كلمة أخرى.")
            return
        if not self._can_make(w):
            self.say("لا يمكن تكوين هذه الكلمة من الحروف المتاحة.")
            return
        if not self._dict.is_word(w):
            self.say(f"«{w}» ليست في القاموس. جرّب كلمة أخرى.")
            return
        # valid! score by length, with a bonus for using all the letters
        self._found.add(nw)
        pts = len(nw)
        if nw == self._normalize(self._source):
            pts += 5
            bonus = " (الكلمة الكاملة! مكافأة)"
        else:
            bonus = ""
        self._score += pts
        # advance to a fresh word once every findable word here is found
        if self._found >= self._findable:
            self.say(f"صحيحة! «{w}» +{ar(pts)}{bonus}. مجموعك {ar(self._score)}.")
            self._new_word()
            return
        left = len(self._findable) - len(self._found)
        self.say(f"صحيحة! «{w}» +{ar(pts)}{bonus}. مجموعك {ar(self._score)}، "
                 f"تبقّى {ar(left)} كلمة من حروف هذه الجولة.")

    def _time_up(self):
        self.record(self._score)
        self.say(f"انتهى الوقت! مجموعك النهائي {ar(self._score)}. "
                 f"الكلمة الحالية كانت «{self._source}». «لعبة جديدة» لجولة أخرى.")

    def on_repeat(self):
        self.say("الحروف: " + " ، ".join(self._letters))

    def instructions(self):
        return ("لعبة الأناغرام: من الحروف المبعثرة، كوّن أكبر عددٍ من الكلمات العربية "
                "الحقيقية في ٩٠ ثانية. تُدقَّق كل كلمة في قاموس عربيٍّ داخل البرنامج بلا إنترنت. "
                "متى وجدت كل كلمات الحروف الحالية انتقلت تلقائياً إلى حروفٍ جديدة. الكلمة "
                "الأطول نقاطها أكثر، والكلمة الكاملة تمنح مكافأة. اكتب «حروف» أو Ctrl+R "
                "لسماع الحروف، Ctrl+R كذلك، «الوقت المتبقّي» لمعرفة الوقت. Escape للإغلاق.")


# --------------------------------------------------------------------------
# BOARD GAMES vs AI (navigable 2-D grids, difficulty levels)
# --------------------------------------------------------------------------

class ConnectFour(GridGameDialog):
    """Connect Four (أربعة على التوالي) on a navigable 6x7 grid against an AI with
    three strength levels. You move the cursor along the columns with Left/Right
    (Up/Down move by row to inspect the board), and Enter drops your piece into
    the current column. First to line up four — horizontally, vertically or
    diagonally — wins.

    Difficulty:
      * سهل: mostly random, takes an immediate win.
      * متوسّط: takes a win, blocks your win, else prefers the centre — a
        human-like club player, beatable with a set-up.
      * صعب: minimax look-ahead, a tough opponent.
    """
    GAME_KEY = "connect_four"
    ROWS = 6
    COLS = 7
    COL_LABELS = "ABCDEFG"
    LEVELS = ["سهل", "متوسّط", "صعب"]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech, "أربعة على التوالي", size=(640, 580))
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        lvlrow = wx.BoxSizer(wx.HORIZONTAL)
        lvlrow.Add(wx.StaticText(panel, label="المستوى:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.levelChoice = wx.Choice(panel, choices=self.LEVELS)
        self.levelChoice.SetSelection(1)
        self.bind_choice(self.levelChoice, lambda e: self.start())
        lvlrow.Add(self.levelChoice, 0)
        s.Add(lvlrow, 0, wx.ALL, 6)
        self.build_grid(panel, s)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "أسقط هنا (Enter)", lambda e: self.activate(self._row, self._col)), 0, wx.ALL, 4)
        row.Add(self.button(panel, "قراءة العمود", lambda e: self._read_column()), 0, wx.ALL, 4)
        row.Add(self.button(panel, "لعبة جديدة", lambda e: self.start()), 0, wx.ALL, 4)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 4)
        s.Add(row, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        self.set_first_control(self.grid)
        wx.CallAfter(self.start)

    def start(self):
        self._b = [[" "] * self.COLS for _ in range(self.ROWS)]
        self._me, self._ai = "أنت", "الحاسوب"
        self._over = False
        self.set_cursor(0, 0)
        self.refresh_grid()
        lvl = self.LEVELS[self.levelChoice.GetSelection()]
        self.say(f"لوح جديد ٦×٧. المستوى {lvl}. حرّك بالأسهم يميناً ويساراً لاختيار العمود، "
                 f"واضغط Enter لإسقاط قطعتك. اجمع أربعاً على التوالي لتفوز.")
        wx.CallAfter(self.grid.SetFocus)

    def cell_word(self, r, c):
        v = self._b[r][c]
        return "لك" if v == "X" else "للحاسوب" if v == "O" else "فارغة"

    def _read_column(self):
        c = self._col
        cells = [self.cell_word(r, c) for r in range(self.ROWS)]
        self.announce(f"العمود {self._labels[c]} من الأعلى للأسفل: " + "، ".join(cells))

    def _drop_row(self, board, c):
        for r in range(self.ROWS - 1, -1, -1):
            if board[r][c] == " ":
                return r
        return None

    def activate(self, r, c):
        if self._over:
            self.say("انتهت اللعبة. «لعبة جديدة».")
            return
        rr = self._drop_row(self._b, c)
        if rr is None:
            self.say(f"العمود {self._labels[c]} ممتلئ. اختر آخر.")
            return
        self._b[rr][c] = "X"
        self.refresh_grid()
        if self._wins(self._b, "X"):
            self._over = True
            self.say(f"أسقطت في {self.addr(rr, c)}. أربعة على التوالي — فزت! «لعبة جديدة».")
            if save_score(self.academy, self.GAME_KEY, 1, True):
                self.announce("فوز جديد مسجّل!")
            return
        if self._full(self._b):
            self._over = True
            self.say("امتلأ اللوح. تعادل! «لعبة جديدة».")
            return
        ai_c = self._ai_move()
        ai_r = self._drop_row(self._b, ai_c)
        self._b[ai_r][ai_c] = "O"
        self.set_cursor(0, ai_c)
        self.refresh_grid()
        if self._wins(self._b, "O"):
            self._over = True
            self.say(f"لعب الحاسوب في العمود {self._labels[ai_c]} وجمع أربعاً ففاز. «لعبة جديدة».")
            return
        if self._full(self._b):
            self._over = True
            self.say("امتلأ اللوح. تعادل! «لعبة جديدة».")
            return
        self.say(f"لعبتَ في {self.addr(rr, c)}. لعب الحاسوب في العمود {self._labels[ai_c]}. "
                 f"دورك؛ اختر عموداً بالأسهم.")

    # -- win detection ----------------------------------------------------
    def _wins(self, b, p):
        R, C = self.ROWS, self.COLS
        for r in range(R):
            for c in range(C):
                if c + 3 < C and all(b[r][c + i] == p for i in range(4)):
                    return True
                if r + 3 < R and all(b[r + i][c] == p for i in range(4)):
                    return True
                if r + 3 < R and c + 3 < C and all(b[r + i][c + i] == p for i in range(4)):
                    return True
                if r + 3 < R and c - 3 >= 0 and all(b[r + i][c - i] == p for i in range(4)):
                    return True
        return False

    def _full(self, b):
        return all(b[0][c] != " " for c in range(self.COLS))

    def _valid_cols(self, b):
        return [c for c in range(self.COLS) if b[0][c] == " "]

    def _wins_with(self, b, c, p):
        r = self._drop_row(b, c)
        if r is None:
            return False
        b[r][c] = p
        won = self._wins(b, p)
        b[r][c] = " "
        return won

    def _ai_move(self):
        level = self.levelChoice.GetSelection()
        cols = self._valid_cols(self._b)
        # always take an immediate win
        for c in cols:
            if self._wins_with(self._b, c, "O"):
                return c
        if level == 0:
            return random.choice(cols)
        # block the player's immediate win
        for c in cols:
            if self._wins_with(self._b, c, "X"):
                return c
        if level == 1:
            # human-like: prefer centre, a bit of randomness
            if random.random() < 0.15:
                return random.choice(cols)
            order = sorted(cols, key=lambda c: -(3 - abs(c - 3)))
            return order[0]
        # hard: shallow minimax
        best, mv = -10 ** 9, random.choice(cols)
        for c in cols:
            r = self._drop_row(self._b, c)
            self._b[r][c] = "O"
            sc = self._minimax(4, False, -10 ** 9, 10 ** 9)
            self._b[r][c] = " "
            if sc > best:
                best, mv = sc, c
        return mv

    def _minimax(self, depth, maximizing, alpha, beta):
        if self._wins(self._b, "O"):
            return 1000 + depth
        if self._wins(self._b, "X"):
            return -1000 - depth
        cols = self._valid_cols(self._b)
        if depth == 0 or not cols:
            return self._heuristic()
        if maximizing:
            val = -10 ** 9
            for c in cols:
                r = self._drop_row(self._b, c)
                self._b[r][c] = "O"
                val = max(val, self._minimax(depth - 1, False, alpha, beta))
                self._b[r][c] = " "
                alpha = max(alpha, val)
                if alpha >= beta:
                    break
            return val
        val = 10 ** 9
        for c in cols:
            r = self._drop_row(self._b, c)
            self._b[r][c] = "X"
            val = min(val, self._minimax(depth - 1, True, alpha, beta))
            self._b[r][c] = " "
            beta = min(beta, val)
            if alpha >= beta:
                break
        return val

    def _heuristic(self):
        # prefer having pieces near the centre column
        score = 0
        for r in range(self.ROWS):
            for c in range(self.COLS):
                if self._b[r][c] == "O":
                    score += 3 - abs(c - 3)
                elif self._b[r][c] == "X":
                    score -= 3 - abs(c - 3)
        return score

    def instructions(self):
        return ("أربعة على التوالي على لوح ٦×٧ ضد الحاسوب. تنقّل بالأسهم يميناً ويساراً "
                "لاختيار العمود (وأعلى/أسفل لتفحّص الصفوف، بلا التفاف)، واضغط Enter لإسقاط "
                "قطعتك. «قراءة العمود» يقرأ العمود الحالي. اختر المستوى: سهل، متوسّط، صعب. "
                "اجمع أربع قطع متتالية أفقياً أو رأسياً أو قطرياً. Escape للإغلاق.")


# --------------------------------------------------------------------------
# REVERSI / OTHELLO — navigable 8x8 board vs a positional AI
# --------------------------------------------------------------------------

class Reversi(GridGameDialog):
    """Reversi (عكس/أوثيلو) on a navigable 8x8 grid against an AI with three
    strength levels. You are the dark discs; place a disc to trap the computer's
    light discs in a straight line between two of yours, flipping them. When
    neither side can move, the most discs wins.

    Difficulty:
      * سهل: plays a random legal move.
      * متوسّط: greedy — grabs the move that flips the most discs now.
      * صعب: positional — values corners and edges and avoids the squares next to
        corners, a genuinely strong club-level opponent.
    """
    GAME_KEY = "reversi"
    ROWS = 8
    COLS = 8
    COL_LABELS = "ABCDEFGH"
    LEVELS = ["سهل", "متوسّط", "صعب"]
    DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    # positional weights (corners best; squares diagonal to corners worst)
    WEIGHTS = [
        [120, -20, 20, 5, 5, 20, -20, 120],
        [-20, -40, -5, -5, -5, -5, -40, -20],
        [20, -5, 15, 3, 3, 15, -5, 20],
        [5, -5, 3, 3, 3, 3, -5, 5],
        [5, -5, 3, 3, 3, 3, -5, 5],
        [20, -5, 15, 3, 3, 15, -5, 20],
        [-20, -40, -5, -5, -5, -5, -40, -20],
        [120, -20, 20, 5, 5, 20, -20, 120],
    ]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech, "عكس (أوثيلو)", size=(680, 620))
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        lvlrow = wx.BoxSizer(wx.HORIZONTAL)
        lvlrow.Add(wx.StaticText(panel, label="المستوى:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.levelChoice = wx.Choice(panel, choices=self.LEVELS)
        self.levelChoice.SetSelection(1)
        self.bind_choice(self.levelChoice, lambda e: self.start())
        lvlrow.Add(self.levelChoice, 0)
        s.Add(lvlrow, 0, wx.ALL, 6)
        self.build_grid(panel, s)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.button(panel, "ضع قطعة (Enter)", lambda e: self.activate(self._row, self._col)), 0, wx.ALL, 3)
        row.Add(self.button(panel, "النتيجة الحالية", lambda e: self._say_score()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "حركاتي الممكنة", lambda e: self._say_moves()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "لعبة جديدة", lambda e: self.start()), 0, wx.ALL, 3)
        row.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()), 0, wx.ALL, 3)
        s.Add(row, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(s)
        self.set_first_control(self.grid)
        wx.CallAfter(self.start)

    def start(self):
        self._b = [[" "] * 8 for _ in range(8)]
        self._b[3][3] = "L"; self._b[3][4] = "D"
        self._b[4][3] = "D"; self._b[4][4] = "L"
        self._me, self._ai = "D", "L"      # dark = human
        self._over = False
        self.set_cursor(2, 3)
        self.refresh_grid()
        lvl = self.LEVELS[self.levelChoice.GetSelection()]
        self.say(f"لوح جديد ٨×٨. أنت القطع الداكنة. المستوى {lvl}. ضع قطعة لتحصر قطع الحاسوب "
                 f"بين قطعتين لك فتنقلب لك. تنقّل بالأسهم وEnter للوضع. «حركاتي الممكنة» "
                 f"لسماع الخانات المتاحة.")
        wx.CallAfter(self.grid.SetFocus)

    def cell_word(self, r, c):
        v = self._b[r][c]
        if v == "D":
            return "لك"
        if v == "L":
            return "للحاسوب"
        return "قابلة للّعب" if self._flips(self._b, r, c, self._me) else "فارغة"

    def _flips(self, b, r, c, who):
        if b[r][c] != " ":
            return []
        opp = "L" if who == "D" else "D"
        out = []
        for dr, dc in self.DIRS:
            line = []
            rr, cc = r + dr, c + dc
            while 0 <= rr < 8 and 0 <= cc < 8 and b[rr][cc] == opp:
                line.append((rr, cc)); rr += dr; cc += dc
            if line and 0 <= rr < 8 and 0 <= cc < 8 and b[rr][cc] == who:
                out.extend(line)
        return out

    def _legal(self, b, who):
        return [(r, c) for r in range(8) for c in range(8) if self._flips(b, r, c, who)]

    def activate(self, r, c):
        if self._over:
            self.say("انتهت اللعبة. «لعبة جديدة».")
            return
        flips = self._flips(self._b, r, c, self._me)
        if not flips:
            self.say(f"{self.addr(r, c)} ليست حركة صالحة. اضغط «حركاتي الممكنة».")
            return
        self._place(self._b, r, c, self._me, flips)
        self.refresh_grid()
        self.say(f"وضعت في {self.addr(r, c)}، قلبت {ar(len(flips))}. ")
        wx.CallLater(600, self._ai_turn)

    def _place(self, b, r, c, who, flips):
        b[r][c] = who
        for (rr, cc) in flips:
            b[rr][cc] = who

    def _ai_turn(self):
        if self._over:
            return
        # AI may need to pass if it has no move
        moves = self._legal(self._b, self._ai)
        if not moves:
            if not self._legal(self._b, self._me):
                return self._finish()
            self.say("لا حركة للحاسوب، دورك مجدداً.")
            return
        mv = self._choose_ai_move(moves)
        flips = self._flips(self._b, mv[0], mv[1], self._ai)
        self._place(self._b, mv[0], mv[1], self._ai, flips)
        self.set_cursor(mv[0], mv[1])
        self.refresh_grid()
        # does the human have a move?
        if not self._legal(self._b, self._me):
            if not self._legal(self._b, self._ai):
                return self._finish()
            self.say(f"لعب الحاسوب في {self.addr(*mv)} وقلب {ar(len(flips))}. "
                     f"لا حركة لك، دور الحاسوب مجدداً.")
            wx.CallLater(600, self._ai_turn)
            return
        self.say(f"لعب الحاسوب في {self.addr(*mv)} وقلب {ar(len(flips))}. دورك.")

    def _choose_ai_move(self, moves):
        level = self.levelChoice.GetSelection()
        if level == 0:
            return random.choice(moves)
        if level == 1:
            # greedy: most flips now
            return max(moves, key=lambda m: len(self._flips(self._b, m[0], m[1], self._ai)))
        # positional: pick the highest board-weight square, breaking ties by the
        # number of flips, and randomising among genuinely equal choices so the
        # AI doesn't play an identical game every time
        scored = [((self.WEIGHTS[m[0]][m[1]],
                    len(self._flips(self._b, m[0], m[1], self._ai))), m)
                  for m in moves]
        best = max(sc for sc, _ in scored)
        top = [m for sc, m in scored if sc == best]
        return random.choice(top)

    def _count(self):
        d = sum(row.count("D") for row in self._b)
        l = sum(row.count("L") for row in self._b)
        return d, l

    def _say_score(self):
        d, l = self._count()
        self.say(f"لك {ar(d)} قطعة، للحاسوب {ar(l)} قطعة.")

    def _say_moves(self):
        moves = self._legal(self._b, self._me)
        if not moves:
            self.say("لا توجد حركة متاحة لك الآن.")
            return
        self.say("حركاتك الممكنة: " + "، ".join(self.addr(r, c) for r, c in moves))

    def _finish(self):
        self._over = True
        d, l = self._count()
        if d > l:
            self.say(f"انتهت اللعبة! لك {ar(d)} وللحاسوب {ar(l)}. فزت! أحسنت. «لعبة جديدة».")
            if save_score(self.academy, self.GAME_KEY, d, True):
                self.announce("رقم قياسي جديد!")
        elif l > d:
            self.say(f"انتهت اللعبة! لك {ar(d)} وللحاسوب {ar(l)}. فاز الحاسوب. «لعبة جديدة».")
        else:
            self.say(f"انتهت اللعبة بالتعادل {ar(d)} لكلٍّ. «لعبة جديدة».")

    def instructions(self):
        return ("عكس (أوثيلو) على لوح ٨×٨ ضد الحاسوب. أنت القطع الداكنة. ضع قطعةً بحيث "
                "تحصر قطع الحاسوب بين قطعتين لك في خطٍّ مستقيم فتنقلب إليك. تنقّل بأسهم "
                "الاتجاهات الأربعة (بلا التفاف) وEnter للوضع. «حركاتي الممكنة» لسماع الخانات "
                "المتاحة، و«النتيجة الحالية» للعدّ. اختر المستوى: سهل، متوسّط، صعب. من يملك "
                "أكثر القطع في النهاية يفوز. Escape للإغلاق.")


# --------------------------------------------------------------------------
# DOTS AND BOXES — vs an AI that avoids giving away boxes
# --------------------------------------------------------------------------

class DotsAndBoxes(_GameBase):
    """Dots and boxes (النقاط والصناديق) on a small 3x3-box grid against the
    computer. On your turn you draw one line between two adjacent dots; whoever
    completes the fourth side of a box claims it and goes again. Most boxes wins.

    You address lines simply: type H then a row (1-4) and column (1-3) for a
    horizontal line, or V then row (1-3) column (1-4) for a vertical line — the
    game reads back the available lines so you never have to guess.

    The AI plays a sound strategy: it completes any box it can, otherwise it
    avoids drawing the third side of a box (which would hand you a box), and only
    when forced gives away the smallest chain — a real, thoughtful opponent
    rather than a random one.
    """
    TITLE = "النقاط والصناديق"
    GAME_KEY = "dots_boxes"
    N = 3   # 3x3 boxes -> 4x4 dots

    def start(self):
        n = self.N
        # horizontal lines: (n+1) rows x n cols ; vertical: n rows x (n+1) cols
        self._h = [[False] * n for _ in range(n + 1)]
        self._v = [[False] * (n + 1) for _ in range(n)]
        self._owner = [[" "] * n for _ in range(n)]
        self._my_score = 0
        self._ai_score = 0
        self._over = False
        self.say(f"شبكة {ar(n)}×{ar(n)} صناديق. ارسم خطاً بين نقطتين: اكتب «أفقي صف عمود» "
                 f"أو «عمودي صف عمود». مثال: «أفقي ١ ١». من يكمل الضلع الرابع لصندوق يملكه "
                 f"ويلعب مرة أخرى. اكتب «خطوط» لسماع الخطوط المتاحة.")

    def _avail(self):
        """List available lines as tuples ('h'|'v', r, c)."""
        out = []
        for r in range(self.N + 1):
            for c in range(self.N):
                if not self._h[r][c]:
                    out.append(("h", r, c))
        for r in range(self.N):
            for c in range(self.N + 1):
                if not self._v[r][c]:
                    out.append(("v", r, c))
        return out

    def _line_label(self, kind, r, c):
        k = "أفقي" if kind == "h" else "عمودي"
        return f"{k} {ar(r + 1)} {ar(c + 1)}"

    def _box_sides(self, r, c):
        return (self._h[r][c], self._h[r + 1][c], self._v[r][c], self._v[r][c + 1])

    def _draw(self, kind, r, c, who):
        """Draw a line; return the number of boxes completed by it."""
        if kind == "h":
            self._h[r][c] = True
        else:
            self._v[r][c] = True
        completed = 0
        # check the up-to-two boxes touching this line
        boxes = []
        if kind == "h":
            if r > 0:
                boxes.append((r - 1, c))
            if r < self.N:
                boxes.append((r, c))
        else:
            if c > 0:
                boxes.append((r, c - 1))
            if c < self.N:
                boxes.append((r, c))
        for (br, bc) in boxes:
            if self._owner[br][bc] == " " and all(self._box_sides(br, bc)):
                self._owner[br][bc] = who
                completed += 1
        return completed

    def handle(self, text):
        if self._over:
            self.say("انتهت اللعبة. «لعبة جديدة».")
            return
        t = text.strip()
        if "خطوط" in t:
            self._say_avail()
            return
        parsed = self._parse(t)
        if not parsed:
            self.say("اكتب مثل «أفقي ١ ١» أو «عمودي ٢ ٣». «خطوط» لسماع المتاح.")
            return
        kind, r, c = parsed
        # validate bounds + not taken
        if not self._valid_line(kind, r, c):
            self.say("خط غير صالح أو مرسوم. اكتب «خطوط» لسماع المتاح.")
            return
        got = self._draw(kind, r, c, "أنت")
        self._my_score += got
        if self._all_done():
            return self._finish()
        if got:
            self.say(f"أكملت صندوقاً! لك دور آخر. نتيجتك {ar(self._my_score)}. اكتب خطاً.")
            return
        # AI turn (it may chain several boxes)
        self._ai_play()

    def _parse(self, t):
        kind = "h" if ("أفقي" in t or t.lower().startswith("h")) else \
               "v" if ("عمودي" in t or t.lower().startswith("v")) else None
        if kind is None:
            return None
        nums = []
        tt = t.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        for tok in tt.replace("،", " ").split():
            if tok.isdigit():
                nums.append(int(tok))
        if len(nums) < 2:
            return None
        return kind, nums[0] - 1, nums[1] - 1

    def _valid_line(self, kind, r, c):
        if kind == "h":
            return 0 <= r <= self.N and 0 <= c < self.N and not self._h[r][c]
        return 0 <= r < self.N and 0 <= c <= self.N and not self._v[r][c]

    def _say_avail(self):
        av = self._avail()
        self.say("الخطوط المتاحة: " + "، ".join(self._line_label(*l) for l in av[:16]) +
                 ("، وغيرها" if len(av) > 16 else ""))

    def _all_done(self):
        return all(self._owner[r][c] != " " for r in range(self.N) for c in range(self.N))

    def _would_complete(self, kind, r, c):
        """How many boxes drawing this line would complete right now."""
        saved_h = [row[:] for row in self._h]
        saved_v = [row[:] for row in self._v]
        saved_o = [row[:] for row in self._owner]
        n = self._draw(kind, r, c, "test")
        self._h = saved_h; self._v = saved_v; self._owner = saved_o
        return n

    def _makes_third_side(self, kind, r, c):
        """Would drawing this line make some box have exactly 3 sides (handing it
        to the opponent next turn)?"""
        saved_h = [row[:] for row in self._h]
        saved_v = [row[:] for row in self._v]
        if kind == "h":
            self._h[r][c] = True
            boxes = ([(r - 1, c)] if r > 0 else []) + ([(r, c)] if r < self.N else [])
        else:
            self._v[r][c] = True
            boxes = ([(r, c - 1)] if c > 0 else []) + ([(r, c)] if c < self.N else [])
        bad = any(sum(self._box_sides(br, bc)) == 3 and self._owner[br][bc] == " "
                  for br, bc in boxes)
        self._h = saved_h; self._v = saved_v
        return bad

    def _ai_play(self):
        # AI keeps going while it completes boxes
        while True:
            av = self._avail()
            if not av:
                return self._finish()
            # 1) complete a box if possible
            completing = [l for l in av if self._would_complete(*l)]
            if completing:
                l = completing[0]
                got = self._draw(l[0], l[1], l[2], "الحاسوب")
                self._ai_score += got
                if self._all_done():
                    return self._finish()
                continue   # completed a box -> go again
            # 2) otherwise a "safe" line that doesn't make a third side
            safe = [l for l in av if not self._makes_third_side(*l)]
            pick = random.choice(safe) if safe else random.choice(av)
            self._draw(pick[0], pick[1], pick[2], "الحاسوب")
            self.say(f"لعب الحاسوب: {self._line_label(*pick)}. "
                     f"النتيجة — لك {ar(self._my_score)}، للحاسوب {ar(self._ai_score)}. دورك.")
            return

    def _finish(self):
        self._over = True
        if self._my_score > self._ai_score:
            self.say(f"انتهت! لك {ar(self._my_score)} صندوقاً وللحاسوب {ar(self._ai_score)}. "
                     f"فزت! «لعبة جديدة».")
            if save_score(self.academy, self.GAME_KEY, self._my_score, True):
                self.announce("رقم قياسي جديد!")
        elif self._ai_score > self._my_score:
            self.say(f"انتهت! لك {ar(self._my_score)} وللحاسوب {ar(self._ai_score)}. "
                     f"فاز الحاسوب. «لعبة جديدة».")
        else:
            self.say(f"تعادل {ar(self._my_score)} لكلٍّ! «لعبة جديدة».")

    def on_repeat(self):
        self._say_avail()

    def instructions(self):
        return ("النقاط والصناديق: ارسم خطوطاً بين النقاط؛ من يكمل الضلع الرابع لصندوق "
                "يملكه ويلعب مرة أخرى. اكتب «أفقي صف عمود» أو «عمودي صف عمود» (مثل «أفقي ١ ١»)، "
                "و«خطوط» لسماع المتاح. الحاسوب يتجنّب إهداءك الصناديق. من يملك أكثر صناديق "
                "يفوز. Escape للإغلاق.")
