# -*- coding: utf-8 -*-
"""
abaAcademy.gui.mistakes_view
============================

A "mistake notebook" (دفتر الأخطاء): the topics the learner gets wrong most,
listed with how often, so they can see their weak spots and drill them straight
away. Reviewing one's own errors is one of the most effective study habits, and
until now the data was tracked but never shown. The "تدرّب على هذا" button turns
the selected weak topic into a fresh practice session on the spot.
"""

from __future__ import annotations

from .accessible import AccessibleDialog

try:
    import wx
except Exception:
    wx = None

AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def _ar(n):
    return str(n).translate(AR)


def _topic_label_ar(topic):
    """Make a stored topic id human-readable in Arabic, independent of any
    instance. Handles ``area:kind`` and dotted ``course.subtopic`` ids; keeps
    already-Arabic sub-parts, maps latin keys to Arabic, and never shows a raw
    English id (falls back to the course name)."""
    if not topic:
        return "غير محدّد"
    course_names = MistakesView._COURSE_NAMES
    sub_names = MistakesView._SUB_NAMES

    def ar_sub(key):
        if not key:
            return ""
        if not key.isascii():
            return key
        k = key.rstrip("0123456789")
        return sub_names.get(key) or sub_names.get(k) or ""

    sep = ":" if ":" in topic else ("." if "." in topic else None)
    if sep is None:
        return course_names.get(topic, ar_sub(topic) or topic)
    parts = topic.split(sep)
    head = course_names.get(parts[0], "" if parts[0].isascii() else parts[0])
    tail = ar_sub(parts[1]) if len(parts) > 1 else ""
    if head and tail and tail != head:
        return f"{head} — {tail}"
    if head:
        return head
    if tail:
        return tail
    return course_names.get(parts[0], parts[0])


class MistakesView(AccessibleDialog):
    def __init__(self, parent, academy, speech):
        super().__init__(parent, "دفتر الأخطاء", speech, size=(600, 520))
        self.academy = academy
        panel = wx.Panel(self)
        s = wx.BoxSizer(wx.VERTICAL)
        try:
            self._weak = academy.store.weakest_topics(limit=40)
        except Exception:
            self._weak = []

        if not self._weak:
            s.Add(wx.StaticText(panel, label=(
                "لا أخطاء مسجّلة بعد. عندما تخطئ في أسئلة، ستُجمع مواضيعها هنا "
                "لتتدرّب عليها. تدرّب قليلاً ثم عُد.")), 0, wx.ALL, 10)
        else:
            s.Add(wx.StaticText(panel, label=(
                "أكثر المواضيع التي تخطئ فيها. اختر موضوعاً ثم تدرّب على هذا "
                "لجلسة تركّز عليه:")), 0, wx.ALL, 8)
            self.listbox = wx.ListBox(panel, style=wx.LB_SINGLE)
            items = []
            for topic, wrong, right in self._weak:
                total = wrong + right
                rate = round(wrong * 100 / total) if total else 0
                items.append(f"{self._topic_label(topic)} — أخطأت {_ar(wrong)} من {_ar(total)} "
                             f"({_ar(rate)}٪)")
            self.listbox.Set(items)
            self.select_index(self.listbox, 0)
            self.listbox.SetName("قائمة المواضيع الأكثر خطأً")
            s.Add(self.listbox, 1, wx.EXPAND | wx.ALL, 6)
            s.Add(self.button(panel, "تدرّب على هذا الموضوع", lambda e: self._drill()),
                  0, wx.EXPAND | wx.ALL, 4)
            s.Add(self.button(panel, "تدرّب على كل نقاط ضعفي", lambda e: self._drill_all()),
                  0, wx.EXPAND | wx.ALL, 4)
        s.Add(self.button(panel, "إغلاق", lambda e: self.close_screen()),
              0, wx.ALIGN_RIGHT | wx.ALL, 6)
        panel.SetSizer(s)
        first = getattr(self, "listbox", None) or panel.GetChildren()[0]
        self.set_first_control(first)

    # comprehensive Arabic names for every course prefix and sub-topic key the
    # generators emit, so progress/mistakes displays never show a raw English id
    _COURSE_NAMES = {
        "geo": "الجغرافيا", "hist": "التاريخ", "sci": "العلوم",
        "math": "الرياضيات", "en": "الإنجليزية", "fr": "الفرنسية",
        "quran": "القرآن", "ar": "العربية", "gen": "معلومات عامة",
        "comp": "الحاسوب", "braille": "برايل", "gram": "القواعد",
        "lang": "اللغة", "es": "الإسبانية", "tr": "التركية", "de": "الألمانية", "it": "الإيطالية",
    }
    _SUB_NAMES = {
        # graded language courses (lang:kind)
        "sentence": "فهم الجمل", "word_order": "ترتيب الكلمات", "cloze": "إكمال الفراغ",
        "dictation": "الإملاء بالسمع", "writing": "الكتابة", "conjugation": "تصريف الأفعال",
        # geography
        "arab": "الدول العربية", "world": "دول العالم", "continents": "القارات",
        "capitals": "العواصم", "rivers": "الأنهار", "nations": "دول العالم",
        # science
        "body": "جسم الإنسان", "cell": "الخلية", "elem": "العناصر",
        "planets": "الكواكب", "civ": "الحضارات", "sun_moon": "الشمس والقمر",
        # history
        "states": "الدول الإسلامية", "caliphs": "الخلفاء", "scholars": "العلماء",
        "inventions": "الاختراعات",
        # math
        "add_sub": "الجمع والطرح", "mul_div": "الضرب والقسمة", "add": "الجمع",
        "sub": "الطرح", "mul": "الضرب", "div": "القسمة", "algebra": "الجبر",
        "geometry": "الهندسة", "fraction": "الكسور", "factors": "العوامل",
        "percent": "النسبة المئوية", "power": "الأُسّ", "rounding": "التقريب",
        "sequence": "المتتاليات", "digits": "الأرقام", "numbers": "الأعداد",
        "comparison": "المقارنة", "compare": "المقارنة", "classify": "التصنيف",
        # English grammar
        "be": "الفعل be", "to_be": "الفعل be", "avoir": "الفعل avoir",
        "etre": "الفعل être", "articles": "أدوات التعريف والتنكير",
        "articles_def": "أداة التعريف", "articles_indef": "أداة التنكير",
        "adjectives": "الصفات", "adverbs": "الظروف", "comparatives": "المقارنة",
        "superlatives": "التفضيل", "modals": "الأفعال الناقصة",
        "negation": "النفي", "negative": "النفي", "plural": "الجمع",
        "plurals": "الجموع", "possessives": "الملكية", "prepositions": "حروف الجر",
        "questions": "الأسئلة", "questions_wh": "أسئلة wh", "pronouns": "الضمائر",
        "past_simple": "الماضي البسيط", "past_cont": "الماضي المستمر",
        "past_continuous": "الماضي المستمر", "present_simple": "المضارع البسيط",
        "pres_simple": "المضارع البسيط", "pres_cont": "المضارع المستمر",
        "present_continuous": "المضارع المستمر", "pres_perfect": "المضارع التام",
        "present_perfect": "المضارع التام", "future": "المستقبل",
        "future_will": "المستقبل بـ will", "going_to": "المستقبل بـ going to",
        "conditionals": "الجمل الشرطية", "passive": "المبني للمجهول",
        "there_is": "there is / there are", "what_is": "what is",
        "countable": "المعدود وغير المعدود", "modes": "الأنماط",
        # French
        "er_verbs": "أفعال er", "present_er": "مضارع er", "present_ir": "مضارع ir",
        "futur_simple": "المستقبل البسيط", "future_simple": "المستقبل البسيط",
        "passe_compose": "الماضي المركّب", "passe_compose_avoir": "الماضي المركّب مع avoir",
        "passe_compose_etre": "الماضي المركّب مع être", "imparfait": "الماضي الناقص",
        "conditionnel": "الشرطي", "comparatif_fr": "المقارنة",
        "possessifs": "الملكية", "pronoms": "الضمائر", "prepositions_fr": "حروف الجر",
        "questions_fr": "الأسئلة", "aller_futur": "المستقبل بـ aller",
        "journee": "اليوم", "week_end": "عطلة الأسبوع",
        # Arabic grammar
        "mubtada": "المبتدأ والخبر", "naat": "النعت", "idafa": "الإضافة",
        "inna": "إنّ وأخواتها", "kana": "كان وأخواتها", "maful": "المفعول به",
        "af3al_khamsa": "الأفعال الخمسة", "sun_moon_l": "الحروف الشمسية والقمرية",
        "taa": "التاء المربوطة والمفتوحة", "hamza_pos": "مواضع الهمزة",
        "hamza_mid": "الهمزة المتوسطة", "hamza_end": "الهمزة المتطرفة",
        "alif": "الألف", "conjugate": "التصريف", "conjugation": "التصريف",
        "arabic_extra": "إثراء لغوي",
        # computer / the screen reader
        "browseelem": "تصفّح العناصر", "find": "البحث", "readtext": "قراءة النص",
        "tables": "الجداول", "objnav": "التنقّل بالكائنات", "wordnav": "التنقّل في وورد",
        "webnav": "تصفّح الويب", "excelnav": "التنقّل في إكسل", "excelsplit": "تقسيم إكسل",
        "keys": "المفاتيح", "files": "الملفّات", "headings": "العناوين",
        "synthring": "حلقة النطق", "pptbuild": "بناء العروض", "pptpresent": "تقديم العروض",
        "features": "الميزات", "start": "البدء",
        # general
        "units": "وحدات القياس", "time": "الوقت", "measures": "المقاييس",
        "money": "النقود", "market": "السوق", "hobby": "الهوايات",
        "morning": "الصباح", "discoveries": "الاكتشافات", "senses": "الحواسّ",
        # language-drill kinds
        "confusable": "كلمات متشابهة", "matching": "مطابقة", "listen": "استماع",
        "dictation": "إملاء", "translate": "ترجمة", "words": "مفردات",
        "vocab": "مفردات", "punctuation": "الترقيم", "punct": "الترقيم",
        "marks": "علامات", "mastery": "إتقان",
    }

    def _topic_label(self, topic):
        """Instance wrapper around the module-level topic labeller."""
        return _topic_label_ar(topic)

    def _drill(self):
        if not getattr(self, "listbox", None):
            return
        i = self.listbox.GetSelection()
        if i == wx.NOT_FOUND:
            return
        topic = self._weak[i][0]
        session = None
        # regenerate questions for this one topic via the academy's refill path
        for course in self.academy.courses():
            refill = self.academy._make_refill(
                course.course_id, self.academy._lessons_for_course(course.course_id))
            qs = refill(topic, 12)
            if qs:
                from ..engine.session import QuestionSession
                sid = self.academy.store.start_session("", "", [], "mistakes")
                session = QuestionSession(qs, keep_diacritics=self.academy.settings.strict_tashkeel,
                                          store=self.academy.store, session_id=sid)
                break
        if session is None:
            self.announce("تعذّر توليد أسئلة لهذا الموضوع الآن.")
            return
        self._run(session, "تدريب على " + self._topic_label(topic))

    def _drill_all(self):
        import threading
        self.announce("يُجهّز التدريب، لحظة من فضلك…")

        def work():
            try:
                session = self.academy.build_weak_topics_session(limit=15)
            except Exception:
                session = None
            wx.CallAfter(finish, session)

        def finish(session):
            if session is None:
                self.announce("لا توجد نقاط ضعف كافية بعد.")
                return
            self._run(session, "تدريب نقاط الضعف")

        threading.Thread(target=work, daemon=True).start()

    def _run(self, session, title):
        from .exercise_runner import ExerciseRunner
        self.show_child(ExerciseRunner(self, self.academy, session, title, self.speech))

    def instructions(self):
        return ("دفتر أخطائك: المواضيع التي تخطئ فيها أكثر مع نسبة الخطأ. اختر موضوعاً "
                "وتدرّب على هذا لجلسة تركّز عليه، أو تدرّب على كل نقاط ضعفك. Escape للإغلاق.")
