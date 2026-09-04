# -*- coding: utf-8 -*-
"""
abaAcademy.codelab.challenges
=============================

A curated, ordered track of beginner Python challenges in Arabic. Each challenge
gives an Arabic task, an optional starter, and a deterministic way to check the
learner's solution — either by matching the printed output, or by calling a named
function they defined and comparing return values on several test cases.

All checking is offline and deterministic (no network, no model). Challenges are
plain data, so the set is easy to extend or ship in a course pack.
"""

from __future__ import annotations

from .sandbox import run_code, _make_namespace
import io
import contextlib


class Challenge:
    def __init__(self, cid, title, prompt, check, starter="", hint="",
                 topic="basics"):
        self.cid = cid
        self.title = title
        self.prompt = prompt
        self.check = check            # dict describing how to validate
        self.starter = starter
        self.hint = hint
        self.topic = topic


# check kinds:
#   {"kind": "output", "expect": "..."}          -> printed output must match
#   {"kind": "func", "name": "f", "cases": [([args], expected), ...]}
CHALLENGES = [
    Challenge("c01", "الطباعة الأولى",
              "اطبع الجملة: مرحبا بالعالم",
              {"kind": "output", "expect": "مرحبا بالعالم"},
              starter="# اكتب أمر الطباعة هنا\n",
              hint="استخدم print(\"...\") مع النص بين علامتَي اقتباس.",
              topic="basics"),
    Challenge("c02", "المتغيّرات",
              "أنشئ متغيّراً اسمه العمر قيمته ١٥، ثم اطبع قيمته.",
              {"kind": "output", "expect": "15"},
              hint="اكتب age = 15 ثم print(age).",
              topic="variables"),
    Challenge("c03", "الجمع",
              "اطبع ناتج جمع ٧ و ٨.",
              {"kind": "output", "expect": "15"},
              hint="print(7 + 8).",
              topic="arithmetic"),
    Challenge("c04", "الشرط",
              "اكتب دالة اسمها is_even تُعيد True إذا كان العدد زوجياً وإلا False.",
              {"kind": "func", "name": "is_even",
               "cases": [([4], True), ([7], False), ([0], True), ([-2], True)]},
              starter="def is_even(n):\n    # أكمل هنا\n    pass\n",
              hint="استخدم باقي القسمة: n % 2 == 0.",
              topic="conditionals"),
    Challenge("c05", "الحلقة",
              "اطبع الأعداد من ١ إلى ٥ كلٌّ في سطر.",
              {"kind": "output", "expect": "1\n2\n3\n4\n5"},
              hint="for i in range(1, 6): print(i).",
              topic="loops"),
    Challenge("c06", "المجموع",
              "اكتب دالة sum_to تُعيد مجموع الأعداد من ١ إلى n.",
              {"kind": "func", "name": "sum_to",
               "cases": [([5], 15), ([1], 1), ([10], 55), ([0], 0)]},
              hint="اجمع في حلقة، أو استخدم n*(n+1)//2.",
              topic="loops"),
    Challenge("c07", "أكبر عدد",
              "اكتب دالة biggest تُعيد أكبر عدد في قائمة.",
              {"kind": "func", "name": "biggest",
               "cases": [([[3, 9, 2]], 9), ([[-1, -5]], -1), ([[7]], 7)]},
              hint="يمكنك استخدام max(lst) أو حلقة تقارن.",
              topic="lists"),
    Challenge("c08", "عدّ الحروف",
              "اكتب دالة count_char تُعيد عدد مرّات ظهور حرف في نص.",
              {"kind": "func", "name": "count_char",
               "cases": [(["مرحبا", "م"], 1), (["ababa", "a"], 3),
                         (["xyz", "q"], 0)]},
              hint="استخدم text.count(ch) أو حلقة.",
              topic="strings"),
    Challenge("c09", "عكس النص",
              "اكتب دالة reverse_text تُعيد النص معكوساً.",
              {"kind": "func", "name": "reverse_text",
               "cases": [(["abc"], "cba"), (["ما"], "ام"), ([""], "")]},
              hint="الشريحة text[::-1] تعكس النص.",
              topic="strings"),
    Challenge("c10", "الأعداد الأولية",
              "اكتب دالة is_prime تُعيد True إذا كان العدد أوّلياً.",
              {"kind": "func", "name": "is_prime",
               "cases": [([7], True), ([1], False), ([9], False), ([2], True),
                         ([13], True)]},
              hint="العدد الأوّلي أكبر من ١ ولا يقبل القسمة إلا على ١ ونفسه.",
              topic="functions"),

    # -- level 3: data structures ---------------------------------------
    Challenge("c11", "بحث في قاموس",
              "اكتب دالة capital_of تأخذ قاموساً واسم دولة وتُعيد عاصمتها، أو "
              "\"غير معروف\" إن لم توجد.",
              {"kind": "func", "name": "capital_of",
               "cases": [([{"مصر": "القاهرة"}, "مصر"], "القاهرة"),
                         ([{"مصر": "القاهرة"}, "لبنان"], "غير معروف")]},
              hint="استخدم dict.get(key, \"غير معروف\").",
              topic="dictionaries"),
    Challenge("c12", "إزالة التكرار",
              "اكتب دالة unique_count تُعيد عدد العناصر الفريدة في قائمة.",
              {"kind": "func", "name": "unique_count",
               "cases": [([[1, 2, 2, 3]], 3), ([[5, 5, 5]], 1), ([[]], 0)]},
              hint="حوّل القائمة إلى set ثم خذ طولها.",
              topic="sets"),

    # -- level 4: functions & recursion ---------------------------------
    Challenge("c13", "المضروب",
              "اكتب دالة factorial تُعيد مضروب العدد (n!). مضروب صفر هو ١.",
              {"kind": "func", "name": "factorial",
               "cases": [([5], 120), ([0], 1), ([1], 1), ([4], 24)]},
              hint="يمكنك استخدام التعاود: n * factorial(n-1) مع حالة توقّف.",
              topic="recursion"),

    # -- level 5: advanced ----------------------------------------------
    Challenge("c14", "استيعاب القوائم",
              "اكتب دالة squares تُعيد قائمة مربّعات الأعداد من ١ إلى n.",
              {"kind": "func", "name": "squares",
               "cases": [([3], [1, 4, 9]), ([1], [1]), ([5], [1, 4, 9, 16, 25])]},
              hint="استعمل [i*i for i in range(1, n+1)].",
              topic="comprehension"),
    Challenge("c15", "قسمة آمنة",
              "اكتب دالة safe_div تُعيد ناتج قسمة a على b، أو \"خطأ\" عند "
              "القسمة على صفر (استخدم try/except).",
              {"kind": "func", "name": "safe_div",
               "cases": [([10, 2], 5.0), ([5, 0], "خطأ"), ([9, 3], 3.0)]},
              hint="أحِط القسمة بـ try، والتقط ZeroDivisionError في except.",
              topic="exceptions"),
    Challenge("c16", "صنف الحساب",
              "اكتب صنفاً Counter فيه دالة add تزيد العدّاد، ودالة value تُعيد "
              "قيمته. ثم أنشئ دالة test_counter تُنشئ عدّاداً وتزيده مرّتين "
              "وتُعيد قيمته.",
              {"kind": "func", "name": "test_counter",
               "cases": [([], 2)]},
              starter="class Counter:\n    def __init__(self):\n        self.n = 0\n    # أكمل add و value\n\ndef test_counter():\n    c = Counter()\n    # زد مرّتين وأعد القيمة\n    pass\n",
              hint="في __init__ اجعل self.n=0، وفي add زد self.n، وفي value أعِدها.",
              topic="classes"),
    Challenge("c17", "الترتيب بمفتاح",
              "اكتب دالة by_length تُرتّب قائمة كلمات حسب الطول تصاعدياً.",
              {"kind": "func", "name": "by_length",
               "cases": [([["bb", "a", "ccc"]], ["a", "bb", "ccc"]),
                         ([["xy", "z"]], ["z", "xy"])]},
              hint="استعمل sorted(words, key=len) أو key=lambda w: len(w).",
              topic="higher_order"),

    # -- level 6: very advanced -----------------------------------------
    Challenge("c18", "مُزخرِف بسيط",
              "اكتب مُزخرِفاً double_result يضاعف ناتج أيّ دالة يزخرفها، ثم "
              "استعمله على دالة add(a,b). عرّف دالة add مزخرفة تُعيد ضعف المجموع.",
              {"kind": "func", "name": "add",
               "cases": [([2, 3], 10), ([0, 0], 0), ([5, 5], 20)]},
              starter="def double_result(fn):\n    # أعد دالة تضاعف ناتج fn\n    pass\n\n@double_result\ndef add(a, b):\n    return a + b\n",
              hint="داخل المُزخرِف عرّف wrapper يستدعي fn ويضرب الناتج في ٢.",
              topic="decorators"),
    Challenge("c19", "البحث الثنائي",
              "اكتب دالة binary_search تُعيد فهرس القيمة في قائمة مرتّبة، أو -1 "
              "إن لم توجد.",
              {"kind": "func", "name": "binary_search",
               "cases": [([[1, 3, 5, 7, 9], 7], 3), ([[1, 3, 5], 4], -1),
                         ([[2, 4, 6, 8], 2], 0)]},
              hint="حرّك مؤشّرين lo و hi، وقارن بالعنصر الأوسط mid كلّ مرّة.",
              topic="algorithms"),
    Challenge("c20", "طيّ القائمة",
              "اكتب دالة product تُعيد حاصل ضرب كلّ عناصر القائمة (بلا استيراد).",
              {"kind": "func", "name": "product",
               "cases": [([[1, 2, 3, 4]], 24), ([[5]], 5), ([[2, 2, 2]], 8)]},
              hint="ابدأ بـ result=1 واضرب فيه كلّ عنصر بحلقة.",
              topic="functional"),
]


def get_challenge(cid):
    for c in CHALLENGES:
        if c.cid == cid:
            return c
    return None


def check_solution(challenge, source):
    """Validate the learner's ``source`` against the challenge. Returns
    (passed: bool, arabic_message: str)."""
    check = challenge.check
    if check["kind"] == "output":
        result = run_code(source, timeout=5.0)
        if result.error:
            return False, result.error
        got = result.output.strip().replace("\r\n", "\n")
        want = check["expect"].strip()
        if got == want:
            return True, "أحسنت! الناتج صحيح."
        return False, (f"الناتج غير مطابق. توقّعت: «{want}» "
                       f"وحصلت على: «{got}».")
    if check["kind"] == "func":
        return _check_func(challenge, source, check)
    return False, "نوع تحقّق غير معروف."


def _check_func(challenge, source, check):
    # syntax first
    from .ast_diagnostics import explain_syntax, explain_traceback
    syn = explain_syntax(source)
    if syn:
        return False, syn
    ns = _make_namespace()
    try:
        code = compile(source, "<code>", "exec")
        with contextlib.redirect_stdout(io.StringIO()):
            exec(code, ns)
    except BaseException as exc:
        return False, explain_traceback(type(exc), exc, exc.__traceback__)
    fn = ns.get(check["name"])
    if not callable(fn):
        return False, (f"لم أجد دالة اسمها «{check['name']}». "
                       f"تأكّد من كتابة def {check['name']}(...).")
    for args, expected in check["cases"]:
        try:
            got = fn(*args)
        except BaseException as exc:
            return False, (f"حدث خطأ عند تجربة الدالة بالمدخلات {args}: "
                           + explain_traceback(type(exc), exc, exc.__traceback__))
        if got != expected:
            return False, (f"نتيجة خاطئة: للمدخلات {args} توقّعت {expected} "
                           f"لكن الدالة أعادت {got}.")
    return True, "ممتاز! نجحت الدالة في كل الحالات."
