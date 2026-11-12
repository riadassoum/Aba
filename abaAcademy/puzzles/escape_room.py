# -*- coding: utf-8 -*-
"""
abaAcademy.puzzles.escape_room
==============================

الغرفة المغلقة — an audio escape-room story played from a menu of
actions, so it needs no typing parser and nothing to see. Every room is
data: objects to examine, items to take, and locks opened by an item or a
code that the clues in the room add up to. The puzzles exercise arithmetic,
attention to detail and reasoning, and every clue is in the text the player
hears.

The engine only knows rooms, actions, conditions and effects, so new
adventures can be added as data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple


@dataclass(frozen=True)
class Action:
    key: str
    label: str
    text: str                                   # what the player hears
    needs: Tuple[str, ...] = ()                 # flags/items required to see it
    hides: Tuple[str, ...] = ()                 # disappears once these are set
    sets: Tuple[str, ...] = ()                  # flags set on success
    gives: Tuple[str, ...] = ()                 # items added to the bag
    code: str = ""                              # a code to type; empty = none
    code_prompt: str = ""
    wrong: str = "لم يحدث شيء. الرمز غير صحيح."
    go: str = ""                                # room to move to
    wins: bool = False


@dataclass(frozen=True)
class Room:
    key: str
    name: str
    intro: str
    actions: Tuple[Action, ...]


@dataclass
class Adventure:
    title: str
    intro: str
    start: str
    rooms: Dict[str, Room]
    items: Dict[str, str]                       # item key -> spoken name


@dataclass
class Game:
    adventure: Adventure
    room: str = ""
    flags: Set[str] = field(default_factory=set)
    bag: List[str] = field(default_factory=list)
    moves: int = 0
    wrong_codes: int = 0
    won: bool = False
    log: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.room:
            self.room = self.adventure.start

    @property
    def current(self) -> Room:
        return self.adventure.rooms[self.room]

    def _has(self, req: str) -> bool:
        if req.startswith("!"):
            return not self._has(req[1:])
        return req in self.flags or req in self.bag

    def available(self) -> List[Action]:
        out = []
        for a in self.current.actions:
            if all(self._has(n) for n in a.needs) and not any(self._has(h) for h in a.hides):
                out.append(a)
        return out

    def describe(self) -> str:
        r = self.current
        return f"{r.name}. {r.intro}"

    def bag_text(self) -> str:
        if not self.bag:
            return "حقيبتك فارغة."
        return "في حقيبتك: " + "، ".join(self.adventure.items[i] for i in self.bag) + "."

    def do(self, key: str, code: Optional[str] = None) -> str:
        """Perform an action. Actions with a code need ``code``; returns the
        text the player hears."""
        if self.won:
            return "لقد خرجت بالفعل!"
        act = next((a for a in self.available() if a.key == key), None)
        if act is None:
            return "هذا غير متاح الآن."
        self.moves += 1
        if act.code:
            entered = "".join(ch for ch in (code or "").translate(
                str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")) if not ch.isspace())
            if entered != act.code:
                self.wrong_codes += 1
                return act.wrong
        for f in act.sets:
            self.flags.add(f)
        for i in act.gives:
            if i not in self.bag:
                self.bag.append(i)
        text = act.text
        if act.gives:
            text += " أُضيف إلى حقيبتك: " + "، ".join(self.adventure.items[i] for i in act.gives) + "."
        if act.go:
            self.room = act.go
            text += " " + self.describe()
        if act.wins:
            self.won = True
        self.log.append(text)
        return text

    def hint(self) -> str:
        """Point at the first action that moves the story forward."""
        for a in self.available():
            if a.code or a.go or a.gives or a.wins:
                return f"جرّب: {a.label}."
        acts = self.available()
        return f"جرّب: {acts[0].label}." if acts else "لا أفعال متاحة."


def _a(key, label, text, **kw) -> Action:
    return Action(key, label, text, **{k: tuple(v) if isinstance(v, list) else v for k, v in kw.items()})


# ---------------------------------------------------------------------------
# المكتبة المنسيّة — the bundled adventure
# ---------------------------------------------------------------------------

LIBRARY = Adventure(
    title="المكتبة المنسيّة",
    intro=("دخلت مكتبة قديمة لتعيد كتابًا، فأُغلق الباب خلفك. أمامك ثلاث غرف، "
           "وعليك أن تجد طريق الخروج قبل أن يحلّ الليل. استمع جيّدًا: كلّ دليل في الكلام."),
    start="hall",
    items={"brass_key": "مفتاح نحاسي", "note": "ورقة مطوية", "lamp": "مصباح يدوي",
           "gear": "ترس معدني", "silver_key": "مفتاح فضّي"},
    rooms={
        "hall": Room("hall", "قاعة المطالعة",
                     "قاعة واسعة فيها طاولة طويلة، ورفّ كتب، وساعة حائط، وباب خشبي على يمينك مغلق "
                     "بقفل ذي ثلاثة أرقام، وباب الخروج الكبير أمامك.",
                     (
                         _a("table", "افحص الطاولة",
                            "على الطاولة كتاب مفتوح على الصفحة ١٢، وتحته ورقة مطوية.",
                            hides=["note"], gives=["note"]),
                         _a("read_note", "اقرأ الورقة المطوية",
                            "كُتب فيها: رقم القفل: عدد كتب الرفّ الأوسط، ثم الساعة التي تشير "
                            "إليها ساعة الحائط، ثم آخر رقم في الصفحة المفتوحة.",
                            needs=["note"]),
                         _a("shelf", "افحص رفّ الكتب",
                            "للرفّ ثلاث طبقات: العليا فيها خمسة كتب، والوسطى فيها أربعة كتب، "
                            "والسفلى فيها سبعة كتب."),
                         _a("clock", "استمع إلى ساعة الحائط",
                            "تدقّ الساعة ثلاث دقّات ثم تسكت. عقرباها متوقّفان عند الثالثة تمامًا."),
                         _a("book", "اقرأ الكتاب المفتوح",
                            "الصفحة رقم ١٢ تتحدّث عن الصبر. الرقمان في رقم الصفحة هما ١ ثم ٢، "
                            "فآخرهما ٢."),
                         _a("side_door", "أدخل رقمًا في قفل الباب الجانبي",
                            "دار القفل وانفتح الباب الجانبي على غرفة صغيرة.",
                            hides=["side_open"], sets=["side_open"], code="432",
                            code_prompt="اكتب الأرقام الثلاثة للقفل",
                            wrong="لم ينفتح القفل. راجع الورقة المطوية: الرفّ الأوسط، ثم الساعة، ثم الصفحة."),
                         _a("to_archive", "ادخل الغرفة الجانبية", "تدخل الغرفة الجانبية.",
                            needs=["side_open"], go="archive"),
                         _a("exit_door", "افحص باب الخروج",
                            "باب حديدي كبير، فيه قفل بمفتاح فضّي، وبجانبه لوحة أرقام صغيرة."),
                         _a("exit_unlock", "افتح باب الخروج بالمفتاح الفضّي",
                            "دار المفتاح في القفل، لكنّ الباب ما زال مشدودًا؛ تطلب لوحة الأرقام رمزًا.",
                            needs=["silver_key"], hides=["exit_unlocked"], sets=["exit_unlocked"]),
                         _a("exit_code", "أدخل الرمز في لوحة باب الخروج",
                            "صدر صوت نقرة، وانفتح الباب الكبير على هواء الليل البارد. خرجت! أحسنت.",
                            needs=["exit_unlocked"], code="1446",
                            code_prompt="اكتب رمز باب الخروج",
                            wrong="أصدرت اللوحة صفيرًا قصيرًا. الرمز خطأ.", wins=True),
                     )),
        "archive": Room("archive", "غرفة الأرشيف",
                        "غرفة ضيّقة مظلمة تفوح منها رائحة الورق. تسمع أزيز آلة متوقّفة في الزاوية، "
                        "وأمامك خزانة صغيرة.",
                        (
                            _a("dark", "تحسّس الجدار قرب الباب",
                               "وجدت على الجدار مصباحًا يدويًّا معلّقًا.", hides=["lamp"], gives=["lamp"]),
                            _a("light", "أضئ المصباح",
                               "أضاء المصباح الغرفة. على الخزانة صندوق صغير، وفي الزاوية آلة تروس "
                               "ينقصها ترس، وعلى الجدار لوحة كُتب فيها جدول ضرب ناقص.",
                               needs=["lamp"], hides=["lit"], sets=["lit"]),
                            _a("board", "اقرأ لوحة الجدار",
                               "اللوحة: ٦ × ٧ = ؟ — اكتب الناتج على قفل الصندوق.",
                               needs=["lit"]),
                            _a("box", "افتح الصندوق الصغير",
                               "انفتح الصندوق، وفيه ترس معدني ومفتاح نحاسي.",
                               needs=["lit"], hides=["box_open"], sets=["box_open"],
                               gives=["gear", "brass_key"], code="42",
                               code_prompt="اكتب رمز الصندوق",
                               wrong="لم ينفتح الصندوق. اقرأ لوحة الجدار."),
                            _a("machine", "ركّب الترس في الآلة",
                               "دار الترس، وتحرّكت الآلة فانزاح جزء من الجدار عن باب ثالث صغير "
                               "عليه قفل نحاسي.",
                               needs=["gear", "lit"], hides=["machine_on"], sets=["machine_on"]),
                            _a("to_study", "افتح الباب الصغير بالمفتاح النحاسي وادخل",
                               "انفتح القفل النحاسي، فدخلت.", needs=["machine_on", "brass_key"],
                               go="study"),
                            _a("back_hall", "ارجع إلى قاعة المطالعة", "ترجع إلى القاعة.", go="hall"),
                        )),
        "study": Room("study", "مكتب أمين المكتبة",
                      "مكتب صغير فيه كرسي ومكتب خشبي ذو درج، وتقويم معلّق على الجدار.",
                      (
                          _a("calendar", "اقرأ التقويم",
                             "تقويم هجري، كُتب عليه بخطّ اليد: سنة افتتاح القاعة الجديدة هي رمز "
                             "الباب الكبير. السنة المطبوعة على التقويم ١٤٤٧، وتحتها: افتُتحت القاعة "
                             "قبل سنة من هذا التقويم."),
                          _a("drawer", "افتح درج المكتب",
                             "في الدرج مفتاح فضّي وورقة كُتب فيها: احسب جيّدًا: قبل سنة.",
                             hides=["silver_key"], gives=["silver_key"]),
                          _a("chair", "اجلس على الكرسي وفكّر",
                             "تتذكّر: الرمز سنة افتتاح القاعة، وهي سنة واحدة قبل ١٤٤٧."),
                          _a("back_archive", "ارجع إلى غرفة الأرشيف", "ترجع إلى الأرشيف.",
                             go="archive"),
                      )),
    },
)

ADVENTURES = {"library": LIBRARY}


def new_game(key: str = "library") -> Game:
    return Game(ADVENTURES[key])


def solution_path() -> List[Tuple[str, str]]:
    """The intended solution (used by the tests to prove it is winnable)."""
    return [("table", ""), ("read_note", ""), ("side_door", "432"), ("to_archive", ""),
            ("dark", ""), ("light", ""), ("board", ""), ("box", "42"), ("machine", ""),
            ("to_study", ""), ("drawer", ""), ("calendar", ""), ("back_archive", ""),
            ("back_hall", ""), ("exit_unlock", ""), ("exit_code", "1446")]
