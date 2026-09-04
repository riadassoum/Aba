# -*- coding: utf-8 -*-
"""
abaAcademy.codelab.curriculum
=============================

A structured Python learning path in Arabic, from absolute beginner to advanced.
The curriculum is organised into **levels**, each level into **units**, and each
unit carries a short Arabic *lesson* (explanation + a worked example the learner
can run) plus a list of challenge ids (defined in :mod:`challenges`) that drill
that unit.

Design and honesty
-------------------
This module gives the real *structure and teaching text* for the whole ladder,
and points each unit at concrete auto-graded challenges. The lessons are written
to be correct and screen-reader friendly (short paragraphs, no reliance on visual
layout, code read line by line). The ladder is deliberately broad; the units near
the top (advanced) teach real concepts with runnable examples, and every unit
that claims a challenge has that challenge defined and tested. Where an advanced
topic is introduced by explanation and example without a full graded project yet,
the unit says so rather than pretending a grader exists.

Everything is plain data and offline.
"""

from __future__ import annotations


class Lesson:
    """One unit's teaching content."""

    def __init__(self, uid, title, body, example="", example_output="",
                 challenges=None, note=""):
        self.uid = uid
        self.title = title
        self.body = body                 # Arabic explanation
        self.example = example           # runnable example code
        self.example_output = example_output
        self.challenges = challenges or []
        self.note = note                 # honest scope note if any


class Level:
    def __init__(self, key, title, subtitle, units):
        self.key = key
        self.title = title
        self.subtitle = subtitle
        self.units = units


# ===========================================================================
# LEVEL 1 — المبتدئ (Beginner)
# ===========================================================================
_L1 = Level("beginner", "المستوى الأول: المبتدئ",
            "أول خطواتك في البرمجة: الطباعة، المتغيّرات، الأنواع، والإدخال.", [
    Lesson("u101", "ما هي البرمجة والطباعة",
        "البرمجة هي إعطاء الحاسوب سلسلة من الأوامر ينفّذها بالترتيب. أول أمر "
        "نتعلّمه هو الطباعة: أن نطلب من الحاسوب أن يُظهر نصًّا. في بايثون نستخدم "
        "الدالة print، ونضع ما نريد طباعته بين قوسين، والنص بين علامتَي اقتباس.",
        example='print("مرحبا بالعالم")',
        example_output="مرحبا بالعالم",
        challenges=["c01"]),
    Lesson("u102", "المتغيّرات",
        "المتغيّر اسمٌ نخزّن فيه قيمة لنستعملها لاحقًا. نكتب اسم المتغيّر ثم "
        "علامة يساوي واحدة ثم القيمة. علامة يساوي هنا معناها «خزّن»، لا «يساوي» "
        "الرياضية. بعد ذلك يمكننا طباعة المتغيّر دون علامات اقتباس لنطبع قيمته.",
        example='age = 15\nprint(age)',
        example_output="15",
        challenges=["c02"]),
    Lesson("u103", "الأعداد والعمليات الحسابية",
        "يتعامل بايثون مع الأعداد مباشرة. نستعمل + للجمع و- للطرح و* للضرب "
        "و/ للقسمة و** للأس و% لباقي القسمة. يمكن طباعة ناتج العملية مباشرة.",
        example='print(7 + 8)\nprint(2 ** 10)\nprint(17 % 5)',
        example_output="15\n1024\n2",
        challenges=["c03"]),
    Lesson("u104", "النصوص (السلاسل)",
        "النص في بايثون يُسمّى سلسلة (string) ويوضع بين علامتَي اقتباس. يمكن "
        "ضمّ نصّين بعلامة +، وتكرار نصّ بعلامة *. ولكلّ نصّ طول نعرفه بالدالة len.",
        example='name = "سالم"\nprint("أهلا " + name)\nprint(len(name))',
        example_output="أهلا سالم\n4"),
    Lesson("u105", "الإدخال من المستخدم",
        "لجعل البرنامج تفاعليًّا نطلب من المستخدم إدخال قيمة بالدالة input. "
        "ما يُدخله المستخدم يأتي دائمًا كنصّ، فإن أردنا رقمًا حوّلناه بالدالة int.",
        example='name = input("ما اسمك؟ ")\nprint("أهلا", name)',
        example_output="(يعتمد على إدخالك)",
        note="جرّب هذا في «تدريب حر» حيث يمكنك إدخال قيمة."),
])

# ===========================================================================
# LEVEL 2 — التحكّم في المسار (Control flow)
# ===========================================================================
_L2 = Level("control", "المستوى الثاني: التحكّم في المسار",
            "اجعل برنامجك يقرّر ويكرّر: الشروط والحلقات.", [
    Lesson("u201", "الشروط (if / else)",
        "أحيانًا نريد أن ينفّذ البرنامج أمرًا فقط إذا تحقّق شرط. نستخدم if متبوعة "
        "بالشرط ثم نقطتين، ثم كتلة مُزاحة بأربع مسافات. يمكن إضافة else لما يحدث "
        "إذا لم يتحقّق الشرط، و elif لشرط آخر.",
        example='n = 7\nif n % 2 == 0:\n    print("زوجي")\nelse:\n    print("فردي")',
        example_output="فردي",
        challenges=["c04"]),
    Lesson("u202", "المقارنات والمنطق",
        "الشروط تعتمد على المقارنات: == للتساوي، و!= لعدم التساوي، و< و> و<= "
        "و>=. ونربط الشروط بالكلمات and (و) و or (أو) و not (ليس).",
        example='x = 5\nprint(x > 0 and x < 10)\nprint(not (x == 5))',
        example_output="True\nFalse"),
    Lesson("u203", "حلقة for",
        "الحلقة تكرّر أمرًا عدّة مرّات. حلقة for مع range تكرّر عددًا معلومًا من "
        "المرّات. range(1, 6) تعطي الأعداد من ١ إلى ٥.",
        example='for i in range(1, 6):\n    print(i)',
        example_output="1\n2\n3\n4\n5",
        challenges=["c05"]),
    Lesson("u204", "حلقة while",
        "حلقة while تكرّر ما دام الشرط صحيحًا. يجب أن يتغيّر شيء داخل الحلقة "
        "لتتوقّف، وإلّا صارت حلقة لا تنتهي.",
        example='i = 1\nwhile i <= 3:\n    print(i)\n    i = i + 1',
        example_output="1\n2\n3"),
    Lesson("u205", "الجمع بالحلقات",
        "من أكثر استعمالات الحلقة تجميع قيمة. نبدأ بمتغيّر صفر، ثم نضيف إليه في "
        "كلّ دورة.",
        example='total = 0\nfor i in range(1, 6):\n    total = total + i\nprint(total)',
        example_output="15",
        challenges=["c06"]),
])

# ===========================================================================
# LEVEL 3 — البيانات المركّبة (Data structures)
# ===========================================================================
_L3 = Level("data", "المستوى الثالث: هياكل البيانات",
            "القوائم والقواميس والمجموعات: كيف نخزّن بيانات كثيرة ونعالجها.", [
    Lesson("u301", "القوائم",
        "القائمة تخزّن عدّة قيم بترتيب، بين قوسين معقوفين. نصل إلى عنصر برقمه "
        "(الفهرس) بدءًا من صفر. نضيف بالدالة append ونعرف الطول بـ len.",
        example='fruits = ["تفاح", "موز", "تمر"]\nprint(fruits[0])\nfruits.append("عنب")\nprint(len(fruits))',
        example_output="تفاح\n4",
        challenges=["c07"]),
    Lesson("u302", "التكرار على القوائم",
        "يمكن أن تمرّ حلقة for على عناصر القائمة مباشرة، فتأخذ كلّ عنصر بدوره.",
        example='nums = [3, 9, 2]\nfor n in nums:\n    print(n * 2)',
        example_output="6\n18\n4"),
    Lesson("u303", "النصوص كسلاسل من الحروف",
        "النصّ يشبه قائمة من الحروف: له فهارس، ويمكن أخذ شريحة منه، وعكسه "
        "بالشريحة [::-1]، وعدّ حرف فيه بالدالة count.",
        example='s = "مرحبا"\nprint(s[0])\nprint(s[::-1])\nprint(s.count("م"))',
        example_output="م\nابحرم\n1",
        challenges=["c08", "c09"]),
    Lesson("u304", "القواميس",
        "القاموس يربط مفتاحًا بقيمة، بين قوسين معقوفين، كلّ مفتاح ونقطتان "
        "وقيمته. نصل إلى قيمة بمفتاحها، ونمرّ على المفاتيح بحلقة.",
        example='caps = {"مصر": "القاهرة", "لبنان": "بيروت"}\nprint(caps["مصر"])',
        example_output="القاهرة",
        challenges=["c11"]),
    Lesson("u305", "المجموعات",
        "المجموعة (set) تخزّن عناصر فريدة بلا تكرار ولا ترتيب. مفيدة لإزالة "
        "التكرار ولاختبار الانتماء بسرعة.",
        example='nums = [1, 2, 2, 3, 3, 3]\nunique = set(nums)\nprint(len(unique))',
        example_output="3",
        challenges=["c12"]),
])

# ===========================================================================
# LEVEL 4 — الدوال والوحدات (Functions & modules)
# ===========================================================================
_L4 = Level("functions", "المستوى الرابع: الدوال والوحدات",
            "نظّم شيفرتك في دوالّ قابلة لإعادة الاستعمال، واستعن بالوحدات.", [
    Lesson("u401", "تعريف الدوال",
        "الدالة كتلة شيفرة مسمّاة نستدعيها متى شئنا. نعرّفها بـ def ثم الاسم "
        "وقوسين للمعاملات ونقطتين. نُرجع نتيجة بالكلمة return.",
        example='def square(n):\n    return n * n\nprint(square(5))',
        example_output="25",
        challenges=["c10"]),
    Lesson("u402", "المعاملات والقيم الافتراضية",
        "يمكن أن تأخذ الدالة عدّة معاملات، ويمكن إعطاء معامل قيمة افتراضية "
        "تُستعمل إن لم يُمرَّر.",
        example='def greet(name, greeting="أهلا"):\n    return greeting + " " + name\nprint(greet("سالم"))\nprint(greet("ليلى", "مرحبا"))',
        example_output="أهلا سالم\nمرحبا ليلى"),
    Lesson("u403", "الاستيراد من الوحدات",
        "بايثون يأتي بوحدات جاهزة. نستوردها بالكلمة import ثم نستعمل دوالّها. "
        "مثلًا وحدة math فيها الجذر والدوال المثلثية، ووحدة random للعشوائية.",
        example='import math\nprint(math.sqrt(144))\nprint(math.floor(3.7))',
        example_output="12.0\n3",
        note="الوحدات المسموحة في المختبر: math, random, statistics, datetime, string, re."),
    Lesson("u404", "التعاود (recursion)",
        "الدالة قد تستدعي نفسها لحلّ مسألة أصغر منها؛ هذا التعاود. يجب أن تكون "
        "هناك حالة توقّف تمنع اللانهاية. المثال: مضروب العدد.",
        example='def fact(n):\n    if n <= 1:\n        return 1\n    return n * fact(n - 1)\nprint(fact(5))',
        example_output="120",
        challenges=["c13"]),
])

# ===========================================================================
# LEVEL 5 — المتقدّم (Advanced)
# ===========================================================================
_L5 = Level("advanced", "المستوى الخامس: المتقدّم",
            "أفكار أقوى: الاستيعاب، المعالجة الآمنة للأخطاء، والكائنات.", [
    Lesson("u501", "استيعاب القوائم (list comprehension)",
        "طريقة موجزة لبناء قائمة من أخرى في سطر واحد: نكتب التعبير ثم for. "
        "تجعل الشيفرة أقصر وأوضح للمهامّ البسيطة.",
        example='squares = [n * n for n in range(1, 6)]\nprint(squares)',
        example_output="[1, 4, 9, 16, 25]",
        challenges=["c14"]),
    Lesson("u502", "معالجة الأخطاء (try / except)",
        "لتفادي توقّف البرنامج عند خطأ، نحيط الشيفرة الخطرة بـ try، ونعالج "
        "الخطأ في except. هكذا نتحكّم بما يحدث بدل أن ينهار البرنامج.",
        example='try:\n    x = int("ليس رقما")\nexcept ValueError:\n    print("إدخال غير صالح")',
        example_output="إدخال غير صالح",
        challenges=["c15"]),
    Lesson("u503", "الكائنات والأصناف (classes)",
        "الصنف قالب يجمع بيانات ودوالّ معًا. نعرّفه بـ class، وله دالة تهيئة "
        "__init__ تُنشئ الكائن، ودوالّ (methods) تعمل على بياناته.",
        example='class Dog:\n    def __init__(self, name):\n        self.name = name\n    def speak(self):\n        return self.name + " ينبح"\nd = Dog("ركس")\nprint(d.speak())',
        example_output="ركس ينبح",
        challenges=["c16"]),
    Lesson("u504", "المولّدات و yield",
        "المولّد دالة تُنتج القيم واحدة تلو الأخرى بالكلمة yield بدل بنائها كلّها "
        "في الذاكرة. مفيد للسلاسل الطويلة أو اللانهائية.",
        example='def evens(limit):\n    n = 0\n    while n < limit:\n        yield n\n        n = n + 2\nprint(list(evens(10)))',
        example_output="[0, 2, 4, 6, 8]"),
    Lesson("u505", "الدوالّ العُليا و lambda",
        "الدوالّ في بايثون قيمٌ يمكن تمريرها. lambda دالة مصغّرة في سطر. "
        "ودوالّ مثل sorted تقبل مفتاحًا يحدّد كيفية الترتيب.",
        example='words = ["bb", "a", "ccc"]\nprint(sorted(words, key=lambda w: len(w)))',
        example_output="['a', 'bb', 'ccc']",
        challenges=["c17"]),
])

# ===========================================================================
# LEVEL 6 — المتقدّم جدًّا (Very advanced)
# ===========================================================================
_L6 = Level("expert", "المستوى السادس: المتقدّم جدًّا",
            "مفاهيم الخبراء: المُزخرِفات، تعقيد الخوارزميات، والبنى المتقدّمة.", [
    Lesson("u601", "المُزخرِفات (decorators)",
        "المُزخرِف دالة تأخذ دالة وتُعيد دالة مُحسَّنة، فتضيف سلوكًا دون تعديل "
        "الأصل. تُكتب بعلامة @ فوق الدالة. مثال: مُزخرِف يطبع قبل الاستدعاء.",
        example='def announce(fn):\n    def wrapper(*args):\n        print("سأنادي الدالة")\n        return fn(*args)\n    return wrapper\n\n@announce\ndef add(a, b):\n    return a + b\nprint(add(2, 3))',
        example_output="سأنادي الدالة\n5",
        challenges=["c18"]),
    Lesson("u602", "تعقيد الخوارزميات (Big-O)",
        "نقيس كفاءة الخوارزمية بعدد الخطوات مع كِبَر المدخل، ونرمز له بـ O. "
        "البحث الخطّي O(n)، والبحث الثنائي في قائمة مرتّبة O(log n) أسرع بكثير. "
        "فهم هذا يساعدك على اختيار الحلّ الأنسب.",
        example='def binary_search(arr, target):\n    lo, hi = 0, len(arr) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if arr[mid] == target:\n            return mid\n        if arr[mid] < target:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return -1\nprint(binary_search([1,3,5,7,9,11], 7))',
        example_output="3",
        challenges=["c19"]),
    Lesson("u603", "إدارة الموارد (context managers)",
        "الكلمة with تضمن إغلاق مورد (كملفّ) تلقائيًّا بعد الاستعمال حتى لو حدث "
        "خطأ. يمكننا بناء مديري سياق خاصّين بنا.",
        example='class Timer:\n    def __enter__(self):\n        print("بدأ")\n        return self\n    def __exit__(self, *a):\n        print("انتهى")\nwith Timer():\n    print("عمل")',
        example_output="بدأ\nعمل\nانتهى"),
    Lesson("u604", "البرمجة الوظيفية والتجميع",
        "أدوات مثل map و filter و reduce تعالج المجموعات بأسلوب وظيفيّ. "
        "و functools.reduce تطوي القائمة إلى قيمة واحدة.",
        example='from functools import reduce\nnums = [1, 2, 3, 4]\nprint(reduce(lambda a, b: a * b, nums))',
        example_output="24",
        note="functools غير مُدرَجة في وحدات المختبر الافتراضية؛ هذا الدرس للقراءة "
             "والفهم، وجرّبه في بيئتك الخاصّة.",
        challenges=["c20"]),
    Lesson("u605", "هياكل بيانات متقدّمة",
        "لكلّ مسألة الهيكل الأنسب: الطابور (deque) للإضافة والحذف من الطرفين، "
        "والقاموس الافتراضي، والعدّاد. اختيار الهيكل الصحيح يبسّط الخوارزمية.",
        example='counts = {}\nfor ch in "مرحبا مرحبا":\n    counts[ch] = counts.get(ch, 0) + 1\nprint(counts["م"])',
        example_output="2"),
])


LEVELS = [_L1, _L2, _L3, _L4, _L5, _L6]


def all_levels():
    return LEVELS


def get_level(key):
    for lv in LEVELS:
        if lv.key == key:
            return lv
    return None


def get_unit(uid):
    for lv in LEVELS:
        for u in lv.units:
            if u.uid == uid:
                return lv, u
    return None, None


def total_units():
    return sum(len(lv.units) for lv in LEVELS)
