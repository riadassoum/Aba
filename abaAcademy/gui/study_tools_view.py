# -*- coding: utf-8 -*-
"""
abaAcademy.gui.study_tools_view
===============================

Screens for the talking spreadsheet, the Python execution tracer, the Arabic
number and sun/moon-letter drills, the escape-room story and the school
calculators.
"""

from __future__ import annotations

import datetime
import io
import os
import random

try:
    import wx
except Exception:
    wx = None

from .tool_base import ToolDialog, ChoiceQuiz, parse_float
from ..tools import sheet as sh
from ..tools import school_calc as sc
from ..tools.ar_count import count
from ..codelab import tracer
from ..arabic_lab import number_rules as nr
from ..puzzles import escape_room as er


# ---------------------------------------------------------------------------
# talking spreadsheet
# ---------------------------------------------------------------------------

class SheetDialog(ToolDialog):
    TITLE = "الجدول الناطق (جدول بيانات)"
    SIZE = (800, 660)
    SETTINGS_PREFIX = "sheet_"

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.sheet = sh.Sheet(50, 10)
        self._r = self._c = 0
        saved = self.setting("data", "")
        if saved:
            try:
                self.sheet.load_csv(saved)
            except Exception:
                pass
        self.add_text("الأسهم للتنقّل بين الخانات، Enter أو F2 للتحرير، Delete للمسح، R لقراءة الصفّ، "
                      "C لقراءة العمود، D لمعرفة الخانات المعتمدة عليها، Ctrl+Z للتراجع، "
                      "Ctrl+D لنسخ الصيغة إلى الخانات تحتها.")
        self.cell = self.add_list("الخانة الحالية", height=50)
        self.cell.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.editor = self.add_entry("محتوى الخانة (رقم أو نصّ أو صيغة تبدأ بـ =)",
                                     on_enter=self._commit)
        self.gotoEntry = self.add_entry("انتقل إلى خانة (مثل C7)", on_enter=self._goto)
        self.add_buttons([("احفظ الخانة", self._commit), ("الدوالّ المتاحة", self._functions),
                          ("افتح CSV", self._open), ("احفظ CSV", self._save_file),
                          ("جدول جديد", self._new)])
        self.add_output("تفاصيل", height=110)
        self.finish(self.cell)
        self._refresh(speak=False)

    def _persist(self) -> None:
        self.set_setting("data", self.sheet.to_csv())

    def _refresh(self, speak: bool = True) -> None:
        text = self.sheet.describe(self._r, self._c)
        self.cell.Set([text])
        self.select_index(self.cell, 0)
        self.editor.SetValue(self.sheet.raw(self._r, self._c))
        if speak:
            self.announce(text)

    def _move(self, dr: int, dc: int) -> None:
        r, c = self._r + dr, self._c + dc
        if not (0 <= r < self.sheet.rows and 0 <= c < self.sheet.cols):
            self.announce("حافة الجدول. " + self.sheet.describe(self._r, self._c))
            return
        self._r, self._c = r, c
        self._refresh()

    def _on_key(self, evt) -> None:
        code = evt.GetKeyCode()
        ctrl = evt.ControlDown()
        moves = {wx.WXK_UP: (-1, 0), wx.WXK_DOWN: (1, 0), wx.WXK_LEFT: (0, -1), wx.WXK_RIGHT: (0, 1)}
        if code in moves:
            self._move(*moves[code])
        elif code == wx.WXK_HOME:
            self._c = 0 if not ctrl else self._c
            if ctrl:
                self._r = 0
            self._refresh()
        elif code == wx.WXK_F2:
            self._edit()
        elif code == wx.WXK_DELETE:
            self.sheet.set(self._r, self._c, "")
            self._persist()
            self._refresh(speak=False)
            self.announce(f"مُسحت {sh.addr(self._r, self._c)}.")
        elif ctrl and code in (ord("Z"), ord("z")):
            if self.sheet.undo():
                self._persist()
                self._refresh(speak=False)
                self.announce("تراجعت. " + self.sheet.describe(self._r, self._c))
            else:
                self.announce("لا شيء للتراجع.")
        elif ctrl and code in (ord("D"), ord("d")):
            n = self.sheet.fill_down(self._r, self._c, 9)
            self._persist()
            self.announce(f"نُسخت الصيغة إلى {count(n, 'cell')} تحتها." if n else "الخانة فارغة.")
        elif not ctrl and code in (ord("R"), ord("r")):
            self.announce(self.sheet.row_text(self._r))
        elif not ctrl and code in (ord("C"), ord("c")):
            self.announce(self.sheet.column_text(self._c))
        elif not ctrl and code in (ord("D"), ord("d")):
            deps = self.sheet.dependents(self._r, self._c)
            self.announce("تعتمد عليها: " + "، ".join(deps) if deps else "لا تعتمد عليها أيّ خانة.")
        else:
            evt.Skip()

    def _edit(self) -> None:
        self.editor.SetFocus()
        self.editor.SetInsertionPointEnd()
        self.announce(f"تحرير {sh.addr(self._r, self._c)}: {self.sheet.raw(self._r, self._c) or 'فارغة'}")

    def _commit(self) -> None:
        self.sheet.set(self._r, self._c, self.editor.GetValue())
        self._persist()
        here = self.sheet.describe(self._r, self._c)
        deps = self.sheet.dependents(self._r, self._c)
        if self._r + 1 < self.sheet.rows:
            self._r += 1
        self._refresh(speak=False)
        self.cell.SetFocus()
        extra = f" وتغيّرت: {'، '.join(deps)}." if deps else ""
        self.announce(f"{here}.{extra} الآن {self.sheet.describe(self._r, self._c)}")

    def _goto(self) -> None:
        r, c = sh.parse_addr(self.gotoEntry.GetValue())
        if r >= self.sheet.rows or c >= self.sheet.cols:
            raise ValueError("الخانة خارج الجدول.")
        self._r, self._c = r, c
        self.gotoEntry.SetValue("")
        self.cell.SetFocus()
        self._refresh()

    def _functions(self) -> None:
        lines = [f"{a}: {b}" for a, b in sh.FUNCTION_HELP]
        lines.append("الأخطاء: " + "، ".join(f"{k} {v}" for k, v in sh.ERROR_TEXT.items()))
        self.show_output("\n".join(lines), speak="الدوالّ في مربّع التفاصيل.", focus=True)

    def _new(self) -> None:
        if self.sheet.cells and wx.MessageBox("مسح الجدول كلّه؟", "تأكيد",
                                              wx.YES_NO | wx.NO_DEFAULT, self) != wx.YES:
            return
        self.sheet.clear()
        self._r = self._c = 0
        self._persist()
        self._refresh()

    def _open(self) -> None:
        with wx.FileDialog(self, "افتح ملفّ CSV", wildcard="CSV (*.csv)|*.csv|كلّ الملفات|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        from ..deck_import import decode_bytes
        with open(path, "rb") as f:
            text, _enc = decode_bytes(f.read())
        n = self.sheet.load_csv(text)
        self._r = self._c = 0
        self._persist()
        self._refresh(speak=False)
        self.announce(f"فُتح الملفّ: {count(n, 'cell')} فيها بيانات.")

    def _save_file(self) -> None:
        with wx.FileDialog(self, "احفظ الجدول", wildcard="CSV (*.csv)|*.csv", defaultFile="جدول.csv",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        values = wx.MessageBox("هل تحفظ النتائج بدل الصيغ؟ (نعم للنتائج، لا للصيغ)", "طريقة الحفظ",
                               wx.YES_NO, self) == wx.YES
        with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(self.sheet.to_csv(values=values))
        self._say(f"حُفظ في {os.path.basename(path)}.")

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.cell:
            self._edit()
            return True
        return False

    def instructions(self) -> str:
        return ("جدول بيانات ناطق: الأعمدة بالحروف والصفوف بالأرقام. اكتب في الخانة رقمًا أو نصًّا "
                "أو صيغة مثل =مجموع(A1:A5)، وتُعاد الحسابات تلقائيًّا. يُحفظ الجدول بين الجلسات.")


# ---------------------------------------------------------------------------
# execution tracer
# ---------------------------------------------------------------------------

class TracerDialog(ToolDialog):
    TITLE = "متتبّع تنفيذ البرامج (بايثون)"
    SIZE = (800, 680)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.sampleChoice = self.add_choice("أمثلة", [n for n, _ in tracer.SAMPLES],
                                            on_change=self._load_sample)
        self.code = self.add_entry("البرنامج", tracer.SAMPLES[0][1], multiline=True, height=150)
        self.inputs = self.add_entry("مدخلات input (كلّ قيمة في سطر، اختياري)", multiline=True, height=40)
        self.add_buttons([("تتبّع التنفيذ", self._run), ("كم مرّة نُفّذ كلّ سطر", self._counts)],
                         close=False)
        self.steps = self.add_list("الخطوات (تنقّل بالأسهم)", height=180)
        self.add_output("الملخّص والمخرجات", height=90)
        self.add_buttons([])
        self.finish(self.code)
        self._trace = None

    def _load_sample(self) -> None:
        self.code.SetValue(tracer.SAMPLES[self.choice_index(self.sampleChoice)][1])

    def _run(self) -> None:
        src = self.code.GetValue()
        if not src.strip():
            raise ValueError("اكتب برنامجًا أولًا.")
        feed = [l for l in self.inputs.GetValue().splitlines()]
        t = tracer.trace(src, input_lines=feed)
        self._trace = t
        lines = ["  " * min(s.depth, 4) + s.spoken() for s in t.steps] or ["(لم تُنفّذ أيّ خطوة)"]
        self.steps.Set(lines)
        self.select_index(self.steps, 0)
        out = t.output.strip()
        self.show_output(t.summary() + (f"\nالمخرجات:\n{out}" if out else ""), speak=t.summary())
        if t.steps:
            self.steps.SetFocus()

    def _counts(self) -> None:
        if self._trace is None:
            self._run()
        t = self._trace
        lines = [f"السطر {ln}: {count(n, 'time')}" for ln, n in t.line_counts().items()]
        self.show_output("عدد مرّات تنفيذ كلّ سطر:\n" + "\n".join(lines))

    def instructions(self) -> str:
        return ("اكتب برنامج بايثون أو اختر مثالًا، ثم تتبّع التنفيذ. تُعرض كلّ خطوة: السطر الذي "
                "نُفّذ، والمتغيّرات التي تغيّرت وقيمها الجديدة، وما طُبع، ودخول الدوالّ والخروج منها.")


# ---------------------------------------------------------------------------
# number / lam drills
# ---------------------------------------------------------------------------

class NumberRulesDialog(ToolDialog):
    TITLE = "العدد والمعدود واللام الشمسية والقمرية"
    SIZE = (760, 620)
    _MODES = [("number", "العدد والمعدود"), ("lam", "اللام الشمسية والقمرية")]
    _BANDS = [("all", "كلّ الأعداد"), ("1-10", "من ١ إلى ١٠"), ("11-19", "من ١١ إلى ١٩"),
              ("20-99", "من ٢٠ إلى ٩٩"), ("100+", "المئات والألف")]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self._rng = random.Random()
        self.modeChoice = self.add_choice("التدريب", [l for _, l in self._MODES])
        self.bandChoice = self.add_choice("مجال الأعداد", [l for _, l in self._BANDS])
        self.prompt = self.add_text("اضغط سؤال جديد.")
        self.options = self.add_list("الخيارات", height=130)
        self.quiz = ChoiceQuiz(self, self.options, self._make, prompt_ctrl=self.prompt)
        self.add_buttons([("سؤال جديد", self.quiz.next), ("نتيجتي", lambda: self._say(self.quiz.score_text())),
                          ("القاعدة", self._rules)], close=False)
        self.add_text("اكتب عددًا ومعدودًا لترى كتابتهما الصحيحة:")
        self.numEntry = self.add_entry("العدد")
        self._nouns = list(nr.NOUNS)
        self.nounChoice = self.add_choice("المعدود", [f"{n.singular} ({'مؤنّث' if n.feminine else 'مذكّر'})"
                                                      for n in self._nouns])
        self.add_buttons([("اكتب", self._write)])
        self.add_output("الشرح", height=110)
        self.finish(self.modeChoice)

    def _make(self):
        mode = self._MODES[self.choice_index(self.modeChoice)][0]
        if mode == "lam":
            return nr.lam_question(self._rng)
        return nr.number_question(self._rng, self._BANDS[self.choice_index(self.bandChoice)][0])

    def _write(self) -> None:
        try:
            n = int(parse_float(self.numEntry.GetValue()))
        except ValueError:
            raise ValueError("اكتب عددًا.")
        if n not in nr.SUPPORTED:
            raise ValueError("اكتب عددًا من ١ إلى ٩٩، أو من المئات (١٠٠، ٢٠٠ … ٩٠٠) أو ١٠٠٠.")
        noun = self._nouns[self.choice_index(self.nounChoice)]
        self.show_output(f"عندي {nr.number_phrase(n, noun)}.\n{nr.rule_for(n, noun)}")

    def _rules(self) -> None:
        doc = nr.__doc__.split("**العدد والمعدود**", 1)[1]
        self.show_output("العدد والمعدود" + doc.replace("**", ""), speak="القواعد في مربّع الشرح.",
                         focus=True)

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.options:
            self.quiz.answer()
            return True
        return False

    def instructions(self) -> str:
        return ("تدرّب على كتابة العدد مع المعدود تذكيرًا وتأنيثًا وإعرابًا، وعلى التمييز بين اللام "
                "الشمسية والقمرية. اختر الإجابة بالأسهم وEnter، وكلّ إجابة تشرح قاعدتها.")


# ---------------------------------------------------------------------------
# escape room
# ---------------------------------------------------------------------------

class EscapeRoomDialog(ToolDialog):
    TITLE = "الغرفة المغلقة (لغز صوتي)"
    SIZE = (760, 620)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.game = er.new_game()
        self.where = self.add_text("")
        self.actions = self.add_list("ماذا تفعل؟ (Enter للتنفيذ)", height=190)
        self.codeEntry = self.add_entry("الرمز (للأقفال)", on_enter=self._do)
        self.add_buttons([("نفّذ", self._do), ("أين أنا؟", self._where), ("حقيبتي", self._bag),
                          ("تلميح", self._hint), ("ابدأ من جديد", self._restart)])
        self.add_output("ما يحدث", height=150)
        self.finish(self.actions)
        self._refresh()
        self.output.SetValue(self.game.adventure.intro + "\n" + self.game.describe())

    def _refresh(self) -> None:
        self._acts = self.game.available()
        self.where.SetLabel(self.game.current.name)
        self.actions.Set([a.label + (" (يحتاج رمزًا)" if a.code else "") for a in self._acts])
        self.select_index(self.actions, 0)

    def _do(self) -> None:
        i = self.actions.GetSelection()
        if i < 0 or i >= len(self._acts):
            raise ValueError("اختر فعلًا من القائمة.")
        act = self._acts[i]
        if act.code and not self.codeEntry.GetValue().strip():
            self.codeEntry.SetFocus()
            self._say(act.code_prompt + " في حقل الرمز، ثم ارجع إلى القائمة واضغط Enter.")
            return
        key = act.key
        text = self.game.do(key, self.codeEntry.GetValue())
        self.codeEntry.SetValue("")
        self._refresh()
        if self.game.won:
            text += f" أنهيت اللغز في {count(self.game.moves, 'move')}."
            try:
                from .games import save_score
                save_score(self.academy, "escape_library", self.game.moves, higher_is_better=False)
            except Exception:
                pass
        self.show_output(text)
        self.actions.SetFocus()

    def _where(self) -> None:
        self._say(self.game.describe())

    def _bag(self) -> None:
        self._say(self.game.bag_text())

    def _hint(self) -> None:
        self._say(self.game.hint())

    def _restart(self) -> None:
        self.game = er.new_game()
        self._refresh()
        self.show_output(self.game.adventure.intro + " " + self.game.describe())

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.actions:
            self._safe(self._do)
            return True
        return False

    def instructions(self) -> str:
        return ("لغز صوتي: أنت محبوس في مكتبة قديمة. اختر من القائمة ما تفعل، واستمع إلى الأدلّة. "
                "الأقفال تحتاج رمزًا تكتبه في حقل الرمز. تلميح يدلّك على خطوتك التالية.")


# ---------------------------------------------------------------------------
# school calculators
# ---------------------------------------------------------------------------

class SchoolCalcDialog(ToolDialog):
    TITLE = "حاسبات الطالب (المعدّل والتواريخ)"
    SIZE = (760, 680)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.subjects = self.add_entry("المواد: كلّ مادّة في سطر الاسم، العلامة، من، الوزن",
                                       "رياضيات، 85\nعلوم، 17، 20، 2\nلغة عربية، 72", multiline=True,
                                       height=100)
        self.scaleChoice = self.add_choice("نظام العلامات", ["النسبة المئوية والتقدير الحرفي",
                                                             "على ٢٠ مع المعاملات (لبنان والمغرب العربي)"])
        self.add_buttons([("احسب المعدّل", self._average)], close=False)
        self.curEntry = self.add_entry("علامتك حتى الآن (٪)")
        self.weightEntry = self.add_entry("وزن ما أنجزته من المادّة (٪)", "60")
        self.targetEntry = self.add_entry("المعدّل الذي تريده (٪)", "80")
        self.add_buttons([("كم أحتاج؟", self._needed)], close=False)
        self.fromEntry = self.add_entry("من تاريخ (مثل 2010-05-20)")
        self.toEntry = self.add_entry("إلى تاريخ (فارغ = اليوم)")
        self.add_buttons([("الفرق بين التاريخين", self._diff), ("احسب العمر", self._age)])
        self.add_output("النتيجة", height=150)
        self.finish(self.subjects)

    def _average(self) -> None:
        subs = sc.parse_subjects(self.subjects.GetValue())
        if self.choice_index(self.scaleChoice) == 1:
            _, lines = sc.report_20(subs)
            self.show_output("\n".join(lines), speak=lines[-1] if "ينقصك" not in lines[-1] else " ".join(lines[-2:]))
            return
        _, _, lines = sc.average_report(subs)
        self.show_output("\n".join(lines), speak=lines[-2] if len(subs) > 1 else lines[-1])

    def _needed(self) -> None:
        try:
            cur = parse_float(self.curEntry.GetValue())
            w = parse_float(self.weightEntry.GetValue())
            t = parse_float(self.targetEntry.GetValue())
        except ValueError:
            raise ValueError("اكتب الأرقام الثلاثة.")
        _, msg = sc.needed_mark(cur, w, t)
        self.show_output(msg)

    def _dates(self):
        from ..study_hub.planner import parse_date
        a = parse_date(self.fromEntry.GetValue())
        b = parse_date(self.toEntry.GetValue()) if self.toEntry.GetValue().strip() else datetime.date.today()
        return a, b

    def _diff(self) -> None:
        a, b = self._dates()
        self.show_output(sc.date_difference(a, b))

    def _age(self) -> None:
        a, b = self._dates()
        self.show_output(sc.age_text(a, b))

    def instructions(self) -> str:
        return ("احسب معدّلك الموزون وتقديراتك، والعلامة التي تحتاجها لبلوغ هدفك، والفرق بين "
                "تاريخين أو عمرك. سلّم التقديرات المستخدم شائع (٩٠ فما فوق ممتاز) وقد يختلف في مدرستك.")
