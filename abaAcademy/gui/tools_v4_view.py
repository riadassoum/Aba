# -*- coding: utf-8 -*-
"""
abaAcademy.gui.tools_v4_view
============================

Screens added in 4.0 around open-source engines and textbook algorithms:
the word analyser (Qalsadi), the collocations dictionary (Maskouk), the
cryptography lab, the SQL lab, the inheritance calculator, solutions and
gases, and probability distributions.
"""

from __future__ import annotations

import random
import threading

import wx

from .tool_base import ChoiceQuiz, ToolDialog, parse_float


def _bg(dialog, work, done):
    """Run work() off the UI thread and pass (result, error) to done()."""
    def run():
        try:
            res, err = work(), None
        except Exception as e:
            res, err = None, str(e) or type(e).__name__
        wx.CallAfter(lambda: done(res, err) if dialog else None)
    threading.Thread(target=run, daemon=True).start()


# -- المحلّل الصرفي ------------------------------------------------------------

class AnalyzerDialog(ToolDialog):
    TITLE = "المحلّل الصرفي للكلمات"
    SIZE = (820, 640)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        self.add_text("اكتب كلمة عربية فتسمع كل احتمالات تحليلها: الكلمة مشكولة، ونوعها، وجذرها، وأصلها، وسوابقها "
                      "ولواحقها، والزمن والضمير والعدد والجنس والإعراب. واكتب نصًّا لتعرف أصل كل كلماته. التحليل "
                      "بمحلّل القلصادي المفتوح لطه زروقي، وهو المحلّل الذي يعتمد عليه المشكِّل.")
        self.word = self.add_entry("الكلمة (Enter للتحليل)", on_enter=self._analyse)
        self.list = self.add_list("احتمالات التحليل", [], height=170, on_select=self._show,
                                  on_activate=lambda: self._say(self._current()))
        self.out = self.add_output("التحليل المختار", height=80)
        self.text = self.add_entry("نصّ لاستخراج أصول كلماته", multiline=True, height=70)
        self.add_buttons([("حلّل الكلمة", self._analyse), ("استخرج الأصول", self._lemmas)])
        self.readings = []
        self.finish(self.word)
        from ..arabic_lab import diacritizer
        diacritizer.preload()

    def instructions(self) -> str:
        return ("اكتب الكلمة واضغط Enter، ثم تنقّل في الاحتمالات بالأسهم. الاحتمالات مرتّبة من الأشيع إلى الأندر. "
                "يُحمَّل المحلّل في ثوانٍ أوّل مرّة.")

    def _current(self) -> str:
        i = self.list.GetSelection()
        return self.readings[i].text() if 0 <= i < len(self.readings) else ""

    def _show(self):
        self.out.SetValue(self._current())

    def _analyse(self):
        from ..arabic_lab import analyzer
        w = self.word.GetValue().strip()
        if not w:
            self._say("اكتب كلمة أوّلًا.")
            return
        self._say("جارٍ التحليل.")
        _bg(self, lambda: analyzer.analyse(w), self._done)

    def _done(self, res, err):
        if err:
            self._say(err)
            return
        self.readings = res[:60]
        if not self.readings:
            self.list.Set([])
            self._say("لم أجد تحليلًا لهذه الكلمة.")
            return
        self.list.Set([r.text() for r in self.readings])
        self.select_index(self.list, 0)
        self._show()
        self.list.SetFocus()
        self._say(f"{len(self.readings)} احتمالًا. الأوّل: {self.readings[0].text()}")

    def _lemmas(self):
        from ..arabic_lab import analyzer
        t = self.text.GetValue().strip()
        if not t:
            self._say("اكتب نصًّا أوّلًا.")
            return
        _bg(self, lambda: analyzer.lemmas(t),
            lambda res, err: self._say(err) if err else (self.out.SetValue("، ".join(res)),
                                                           self._say("الأصول: " + "، ".join(res))))

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.list:
            self._say(self._current())
            return True
        return False


# -- المتلازمات اللفظية --------------------------------------------------------

class CollocationsDialog(ToolDialog):
    TITLE = "معجم المتلازمات اللفظية"
    SIZE = (800, 640)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        from ..arabic_lab import collocations as co
        self.co = co
        self.rng = random.Random()
        self.add_text(f"المتلازمات كلمات تأتي معًا عادةً، مثل صلاة الجماعة ودار الإسلام. في المعجم {co.count()} "
                      "متلازمة مشكولة من معجم مسكوك المفتوح لطه زروقي. اكتب كلمة لترى ما يلازمها، أو اختبر نفسك.")
        self.word = self.add_entry("الكلمة (Enter للبحث)", on_enter=self._search)
        self.list = self.add_list("المتلازمات", [], height=170,
                                  on_activate=lambda: self._say(self.list.GetStringSelection()))
        self.prompt = self.add_text("")
        self.quizList = self.add_list("الاختبار: أكمل المتلازمة ثم Enter", [], height=90)
        self.quiz = ChoiceQuiz(self, self.quizList, lambda: co.make_question(self.rng), prompt_ctrl=self.prompt)
        self.add_buttons([("ابحث", self._search), ("ابدأ الاختبار", self.quiz.next),
                          ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self.finish(self.word)

    def instructions(self) -> str:
        return "اكتب كلمة مثل صلاة أو علم واضغط Enter، ثم تنقّل في المتلازمات. كل سطر فيه المتلازمة ونوع العلاقة."

    def _search(self):
        rows = self.co.search(self.word.GetValue())
        if not rows:
            self.list.Set([])
            self._say("لا متلازمات لهذه الكلمة في المعجم.")
            return
        self.list.Set([f"{r.vocalized}" + (f" ({r.relation})" if r.relation else "") for r in rows])
        self.select_index(self.list, 0)
        self.list.SetFocus()
        self._say(f"{len(rows)} متلازمة. الأولى {self.list.GetString(0)}")

    def on_enter_key(self) -> bool:
        f = self.FindFocus()
        if f is self.quizList:
            self.quiz.answer()
            return True
        if f is self.list:
            self._say(self.list.GetStringSelection())
            return True
        return False


# -- مختبر التشفير --------------------------------------------------------------

class CipherDialog(ToolDialog):
    TITLE = "مختبر التشفير والترميز"
    SIZE = (800, 640)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        from ..tools import ciphers
        self.c = ciphers
        self.add_text("جرّب الشيفرات التاريخية بالعربية والإنجليزية: قيصر وأتباش وفيجنير والسياج، واكسر شيفرة قيصر "
                      "آليًّا بتحليل تكرار الحروف كما فعل الكندي أوّل من وصف هذه الطريقة، وحوّل النصّ إلى الثنائي "
                      "والست عشري وBase64، واحسب الجُمَّل.")
        self.method = self.add_choice("الطريقة", ciphers.METHODS, 0)
        self.key = self.add_entry("المفتاح (رقم لقيصر والسياج، وكلمة لفيجنير)", "3")
        self.text = self.add_entry("النصّ", multiline=True, height=110)
        self.add_buttons([("نفّذ", self._run), ("استعمل الناتج نصًّا", self._swap)], close=False)
        self.out = self.add_output("الناتج", height=150)
        self.add_buttons([("انسخ الناتج", self._copy)])
        self.finish(self.text)

    def instructions(self) -> str:
        return ("اكتب النصّ واختر الطريقة واضغط نفّذ. الهمزات والتاء المربوطة والألف المقصورة توحَّد قبل التشفير "
                "العربي. زرّ استعمل الناتج نصًّا يضع الناتج في خانة النصّ لتفكّه مثلًا.")

    def _run(self):
        t = self.text.GetValue()
        if not t.strip():
            self._say("اكتب نصًّا أوّلًا.")
            return
        r = self.c.run(self.method.GetSelection(), t, self.key.GetValue())
        self.out.SetValue(r)
        self._say(r[:400])

    def _swap(self):
        self.text.SetValue(self.out.GetValue())
        self.text.SetFocus()
        self._say("وُضع الناتج في خانة النصّ.")

    def _copy(self):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(self.out.GetValue()))
            wx.TheClipboard.Close()
            self._say("نُسخ.")


# -- مختبر SQL -----------------------------------------------------------------

class SqlLabDialog(ToolDialog):
    TITLE = "مختبر قواعد البيانات SQL"
    SIZE = (860, 700)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        from ..codelab import sql_lab
        self.s = sql_lab
        self.con = sql_lab.new_db()
        self.add_text("قاعدة بيانات صغيرة في الذاكرة فيها جداول الطلاب والمواد والدرجات والكتب والإعارات. اكتب "
                      "استعلام SQL واضغط Ctrl+Enter أو زرّ نفّذ، فتُقرأ النتيجة صفًّا صفًّا. وفي التمارين يُصحَّح "
                      "استعلامك بمقارنة نتيجته بالنتيجة الصحيحة، فأيّ استعلام صحيح يُقبل.")
        self.tables = self.add_list("الجداول", sql_lab.describe_tables(self.con), height=80)
        self.exChoice = self.add_choice("التمرين", ["استعلام حرّ"] + [f"{i + 1}. {e.title}" for i, e in
                                                                    enumerate(sql_lab.EXERCISES)], 0,
                                        on_change=self._exercise)
        self.task = self.add_text("")
        self.sql = self.add_entry("الاستعلام", multiline=True, height=80)
        self.sql.Bind(wx.EVT_KEY_DOWN, self._key)
        self.add_buttons([("نفّذ", self._run), ("تلميح", self._hint), ("أعد بناء القاعدة", self._reset)],
                         close=False)
        self.rows = self.add_list("النتيجة صفًّا صفًّا", [], height=150,
                                  on_activate=lambda: self._say(self.rows.GetStringSelection()))
        self.out = self.add_output("النتيجة جدولًا", height=90)
        self.add_buttons([])
        self.finish(self.sql)

    def instructions(self) -> str:
        return ("اكتب الاستعلام ثم Ctrl+Enter. اختر تمرينًا من القائمة لتسمع المطلوب، وزرّ تلميح يذكّرك بالصيغة. "
                "الجداول بالإنجليزية كما في قواعد البيانات الحقيقية، والبيانات بالعربية.")

    def _key(self, evt):
        if evt.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and evt.ControlDown():
            self._safe(self._run)
            return
        evt.Skip()

    def _ex(self):
        i = self.exChoice.GetSelection()
        return self.s.EXERCISES[i - 1] if i > 0 else None

    def _exercise(self):
        ex = self._ex()
        self.task.SetLabel(ex.task if ex else "")
        self._say(ex.task if ex else "استعلام حرّ.")

    def _hint(self):
        ex = self._ex()
        self._say(ex.hint if ex else "ابدأ بـ SELECT * FROM students")

    def _reset(self):
        self.con = self.s.new_db()
        self._say("أُعيد بناء القاعدة ببياناتها الأصلية.")

    def on_enter_key(self) -> bool:
        if self.FindFocus() is self.rows:
            self._say(self.rows.GetStringSelection())
            return True
        return False

    def _run(self):
        q = self.sql.GetValue()
        try:
            ex = self._ex()
            if ex:
                ok, msg = self.s.check(ex, q)
                res = self.s.run(self.s.new_db(), q) if not q.strip().upper().startswith(
                    ("INSERT", "UPDATE", "DELETE")) else None
                if res is not None:
                    self._show(res)
                self._say(msg)
                return
            res = self.s.run(self.con, q)
        except self.s.SQLError as e:
            self._say(str(e))
            return
        self._show(res)
        self.tables.Set(self.s.describe_tables(self.con))
        if res.columns:
            first = res.spoken_rows()[:1]
            self._say(f"{len(res.rows)} صفًّا. " + (first[0] if first else ""))
        else:
            self._say(res.message)

    def _show(self, res):
        self.out.SetValue(res.text())
        self.rows.Set(res.spoken_rows() if res.columns else [res.message])
        if self.rows.GetCount():
            self.select_index(self.rows, 0)


# -- حاسبة المواريث --------------------------------------------------------------

class MawarithDialog(ToolDialog):
    TITLE = "حاسبة المواريث"
    SIZE = (820, 720)

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        from ..tools import mawarith
        self.m = mawarith
        self.add_text("أداة تعليمية لعلم الفرائض: اختر الورثة وعددهم، فتُقسم التركة بالفروض والتعصيب والحجب والعَوْل "
                      "والردّ مع سبب كل نصيب. ما اختلفت فيه المذاهب تذكر الحاسبة القول الذي اتّبعته. لا تشمل ذوي الأرحام "
                      "ولا الوصية والديون ولا الحمل والمفقود، والتركات الحقيقية يقسمها عالم أو محكمة مختصّة.")
        self.counts = {}
        grid = wx.FlexGridSizer(0, 4, 4, 8)
        for key, name, mx in mawarith.HEIRS:
            grid.Add(wx.StaticText(self.panel, label=name + ":"), 0, wx.ALIGN_CENTER_VERTICAL)
            sp = wx.SpinCtrl(self.panel, min=0, max=mx, initial=0)
            sp.SetName(name)
            grid.Add(sp, 0)
            self.counts[key] = sp
        self.sizer.Add(grid, 0, wx.ALL, 6)
        self.estate = self.add_entry("قيمة التركة بعد الديون والوصية (اختياري)")
        self.add_buttons([("احسب", self._run), ("امسح", self._clear)], close=False)
        self.out = self.add_output("القسمة", height=200)
        self.add_buttons([])
        self.finish(self.counts["husband"])

    def instructions(self) -> str:
        return ("انتقل بين الورثة بزرّ Tab واكتب عدد كلّ موجود منهم، ثم اضغط احسب. تُقرأ القسمة سطرًا سطرًا: "
                "نصيب كل وارث من التركة وسببه، ومن حُجب وبمن.")

    def _clear(self):
        for sp in self.counts.values():
            sp.SetValue(0)
        self.out.SetValue("")
        self._say("مُسح.")

    def _run(self):
        heirs = {k: sp.GetValue() for k, sp in self.counts.items() if sp.GetValue()}
        est = self.estate.GetValue().strip()
        value = parse_float(est) if est else 0.0
        res = self.m.compute(heirs)
        lines = self.m.report(res, value)
        head = f"أصل المسألة {res.base}" + (f"، وعالت إلى {res.awl_base}" if res.awl_base else "") + "."
        text = head + "\n" + "\n".join(lines)
        self.out.SetValue(text)
        self.out.SetFocus()
        self._say(text)


# -- المحاليل والغازات -----------------------------------------------------------

class SolutionsDialog(ToolDialog):
    TITLE = "المحاليل والحموض والغازات"
    SIZE = (800, 640)
    CALCS = ["pH حمض قوي (التركيز، عدد البروتونات)", "pH قاعدة قوية (التركيز، عدد الهيدروكسيد)",
             "pH حمض ضعيف (التركيز، Ka)", "pH قاعدة ضعيفة (التركيز، Kb)", "من pH إلى التراكيز (pH)",
             "المولارية (الكتلة بالغرام أو المولات، الصيغة أو الكتلة المولية، الحجم باللتر)",
             "التخفيف M1، V1، M2، V2 (اترك المجهول فارغًا)", "النسبة الكتلية (كتلة المذاب، كتلة المحلول)",
             "الغاز المثالي P، V، n، T (اترك المجهول فارغًا)"]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        from ..science import solutions
        self.s = solutions
        self.add_text("حسابات المحاليل في منهج الكيمياء مع القانون والخطوات. اكتب القيم مفصولة بفواصل بالترتيب المكتوب "
                      "في اسم الحساب. ثوابت تأيّن أحماض وقواعد شائعة في القائمة أدناه.")
        self.calc = self.add_choice("الحساب", self.CALCS, 0)
        self.values = self.add_entry("القيم مفصولة بفواصل (Enter للحساب)", on_enter=self._run)
        self.consts = self.add_list("ثوابت شائعة", [f"{n}: Ka = {k:g}" for n, k in solutions.COMMON_KA] +
                                    [f"{n}: Kb = {k:g}" for n, k in solutions.COMMON_KB], height=90)
        self.add_buttons([("احسب", self._run)], close=False)
        self.out = self.add_output("الحلّ", height=160)
        self.add_buttons([])
        self.finish(self.values)

    def instructions(self) -> str:
        return "اختر الحساب، واكتب القيم بالترتيب مفصولة بفواصل، مثل 0.1، 1.8e-5 لحمض الخلّ، ثم Enter."

    def _vals(self):
        raw = [p.strip() for p in self.values.GetValue().replace("،", ",").split(",")]
        return raw

    def _num(self, s):
        return parse_float(s) if s else 0.0

    def _run(self):
        v = self._vals()
        i = self.calc.GetSelection()
        n = lambda j, d=0.0: self._num(v[j]) if j < len(v) and v[j] else d   # noqa: E731
        s = self.s
        if i == 0:
            r, steps = s.ph_strong_acid(n(0), int(n(1, 1)))
        elif i == 1:
            r, steps = s.ph_strong_base(n(0), int(n(1, 1)))
        elif i == 2:
            r, steps = s.ph_weak_acid(n(0), n(1))
        elif i == 3:
            r, steps = s.ph_weak_base(n(0), n(1))
        elif i == 4:
            steps = s.from_ph(n(0))
        elif i == 5:
            mm_raw = v[1] if len(v) > 1 else ""
            try:
                mm = parse_float(mm_raw)
            except ValueError:
                from ..science import chemistry
                mm, _ = chemistry.molar_mass(mm_raw)
            r, steps = s.molarity(grams=n(0), molar_mass=mm, volume_l=n(2))
        elif i == 6:
            r, steps = s.dilution(n(0), n(1), n(2), n(3))
        elif i == 7:
            r, steps = s.mass_percent(n(0), n(1))
        else:
            r, steps = s.ideal_gas(n(0), n(1), n(2), n(3))
        text = "\n".join(steps)
        self.out.SetValue(text)
        self._say(text)


# -- التوزيعات الاحتمالية --------------------------------------------------------

class DistributionsDialog(ToolDialog):
    TITLE = "التوزيعات الاحتمالية وفترات الثقة"
    SIZE = (800, 660)
    PARAMS = {"ذات الحدّين": "عدد المحاولات ن، واحتمال النجاح ح", "بواسون": "المعدّل لامدا",
              "الهندسي": "احتمال النجاح ح", "المنتظم المتقطّع": "الحدّ الأدنى أ، والحدّ الأعلى ب",
              "الطبيعي": "المتوسّط مو، والانحراف المعياري سيغما", "ستيودنت t": "درجات الحرية د"}

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        from ..math_engine import distributions as d
        self.d = d
        self.add_text("احسب احتمالات التوزيعات المشهورة مع القانون والتوقّع والتباين، وفترة الثقة لمتوسّط عيّنة.")
        self.kind = self.add_choice("التوزيع", d.KINDS, 0, on_change=self._kind)
        self.paramLabel = self.add_text("")
        self.params = self.add_entry("المعاملات مفصولة بفاصلة")
        self.query = self.add_choice("الاحتمال المطلوب", d.QUERIES, 0)
        self.values = self.add_entry("القيمة، أو القيمتان مفصولتين بفاصلة (Enter للحساب)", on_enter=self._run)
        self.add_buttons([("احسب الاحتمال", self._run)], close=False)
        self.ci = self.add_entry("فترة الثقة: المتوسّط، الانحراف، حجم العيّنة، مستوى الثقة (مثل 50، 10، 16، 0.95)",
                                 on_enter=self._ci)
        self.add_buttons([("احسب فترة الثقة", self._ci)], close=False)
        self.out = self.add_output("الحلّ", height=160)
        self.add_buttons([])
        self.finish(self.kind)
        self._kind()

    def instructions(self) -> str:
        return "اختر التوزيع واكتب معاملاته، ثم نوع الاحتمال والقيمة، واضغط Enter."

    def _kind(self):
        k = self.d.KINDS[self.kind.GetSelection()]
        self.paramLabel.SetLabel("المعاملات: " + self.PARAMS[k])

    def _nums(self, ctrl):
        return [parse_float(p) for p in ctrl.GetValue().replace("،", ",").split(",") if p.strip()]

    def _run(self):
        k = self.d.KINDS[self.kind.GetSelection()]
        p = self._nums(self.params) + [0.0, 0.0]
        v = self._nums(self.values) + [0.0, 0.0]
        if not self.params.GetValue().strip():
            raise ValueError("اكتب المعاملات: " + self.PARAMS[k])
        _, steps = self.d.probability(k, p[0], p[1], self.d.QUERIES[self.query.GetSelection()], v[0], v[1])
        text = "\n".join(steps)
        self.out.SetValue(text)
        self._say(text)

    def _ci(self):
        v = self._nums(self.ci)
        if len(v) < 3:
            raise ValueError("اكتب المتوسّط والانحراف وحجم العيّنة على الأقلّ.")
        lo, hi, steps = self.d.confidence_interval(v[0], v[1], int(v[2]), v[3] if len(v) > 3 else 0.95)
        text = "\n".join(steps)
        self.out.SetValue(text)
        self._say(text)


# -- الأعداد في اللغات ----------------------------------------------------------

class NumberWordsDialog(ToolDialog):
    TITLE = "الأعداد في اللغات"
    SIZE = (800, 640)
    LEVELS = ["حتى 20", "حتى 100", "حتى 1000", "حتى 10000", "حتى مليون"]

    def __init__(self, parent, academy, speech):
        super().__init__(parent, academy, speech)
        from ..tools import num_words as nw
        self.nw = nw
        self.langs = list(nw.LANGS)
        self.rng = random.Random()
        self.add_text("اكتب عددًا فتسمعه مكتوبًا بالإنجليزية والفرنسية والإسبانية والألمانية والإيطالية والتركية "
                      "والعربية، ثم تدرّب على فهم الأعداد المكتوبة وكتابتها في اللغة التي تتعلّمها.")
        self.num = self.add_entry("العدد (Enter)", on_enter=self._show)
        self.list = self.add_list("العدد في اللغات", [], height=150,
                                  on_activate=lambda: self._say(self.list.GetStringSelection()))
        self.lang = self.add_choice("لغة التدريب", [nw.LANGS[k] for k in self.langs], 1)
        self.level = self.add_choice("المستوى", self.LEVELS, 1)
        self.direction = self.add_choice("نوع السؤال", ["اقرأ واختر العدد", "اختر الكتابة الصحيحة"], 0)
        self.prompt = self.add_text("")
        self.quizList = self.add_list("الاختبار: اختر ثم Enter", [], height=100)
        self.quiz = ChoiceQuiz(self, self.quizList, self._make, prompt_ctrl=self.prompt)
        self.add_buttons([("اعرض", self._show), ("ابدأ التدريب", self.quiz.next),
                          ("نتيجتي", lambda: self._say(self.quiz.score_text()))])
        self.finish(self.num)

    def instructions(self) -> str:
        return "اكتب العدد واضغط Enter، وتنقّل في القائمة لتسمعه بكل لغة. للتدريب اختر اللغة والمستوى ثم ابدأ."

    def _make(self):
        return self.nw.make_question(self.langs[self.lang.GetSelection()], self.level.GetSelection(), self.rng,
                                     "to_number" if self.direction.GetSelection() == 0 else "to_words")

    def _show(self):
        from .tool_base import parse_int
        try:
            n = parse_int(self.num.GetValue())
        except ValueError:
            raise ValueError("اكتب عددًا صحيحًا.")
        rows = [f"{self.nw.LANGS[k]}: {self.nw.words(n, k)}" for k in self.langs]
        self.list.Set(rows)
        self.select_index(self.list, 0)
        self.list.SetFocus()
        self._say(rows[0])

    def on_enter_key(self) -> bool:
        f = self.FindFocus()
        if f is self.quizList:
            self.quiz.answer()
            return True
        if f is self.list:
            self._say(self.list.GetStringSelection())
            return True
        return False
