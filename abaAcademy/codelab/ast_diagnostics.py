# -*- coding: utf-8 -*-
"""
abaAcademy.codelab.ast_diagnostics
==================================

Translate Python errors into plain Arabic for a beginning blind programmer. When
a learner's code fails, a raw English ``SyntaxError: invalid syntax`` on line 12
is doubly opaque with a screen reader. This module turns the common beginner
errors into clear Arabic guidance that says *what* went wrong, *where*, and *what
to try* — e.g. a missing colon becomes نسيت وضع النقطتين الرأسيتين (:) في نهاية
السطر ١٢.

It works in two layers:

* **compile-time** (``explain_syntax``): before running, we ``compile`` the code;
  if it raises ``SyntaxError``/``IndentationError``/``TabError`` we map it to
  Arabic using the exception's own line/offset and a set of pattern rules.
* **run-time** (``explain_exception``): after running, if an exception is raised,
  we map the exception *type* (and message where useful) to an Arabic
  explanation, and report the line number from the traceback.

Everything is deterministic and offline — just ``ast``/``compile`` and rules.
Nothing here executes the user's code; running is the sandbox's job.
"""

from __future__ import annotations

import re


def _ar_num(n):
    if n is None:
        return "غير معروف"
    return str(n).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


# ---------------------------------------------------------------------------
# compile-time syntax errors
# ---------------------------------------------------------------------------

def explain_syntax(source):
    """Compile ``source`` without running it. Return None if it compiles, else an
    Arabic explanation string for the syntax/indentation error."""
    try:
        compile(source, "<code>", "exec")
        return None
    except (SyntaxError, IndentationError, TabError) as exc:
        return _explain_syntax_exc(exc, source)


def _explain_syntax_exc(exc, source):
    line = getattr(exc, "lineno", None)
    msg = (exc.msg or "").lower() if hasattr(exc, "msg") else str(exc).lower()
    where = f" في السطر {_ar_num(line)}" if line else ""
    lines = source.splitlines()
    cur = lines[line - 1] if line and 0 < line <= len(lines) else ""

    # TabError / IndentationError
    if isinstance(exc, TabError) or "inconsistent use of tabs" in msg:
        return (f"خطأ في المسافات البادئة{where}: خلطت بين المسافات وعلامات الجدولة "
                f"(Tab). استخدم مسافاتٍ فقط، وأربع مسافات لكل مستوى.")
    if isinstance(exc, IndentationError) or "indent" in msg:
        if "unexpected indent" in msg:
            return (f"خطأ في المسافة البادئة{where}: هذا السطر يبدأ بمسافة زائدة غير "
                    f"متوقّعة. تأكّد من محاذاته مع الأسطر المجاورة.")
        if "expected an indented block" in msg:
            return (f"خطأ في المسافة البادئة{where}: بعد النقطتين (:) يجب أن يأتي سطر "
                    f"مُزاح إلى الداخل بأربع مسافات ليكوّن الكتلة.")
        return (f"خطأ في المسافة البادئة{where}: تأكّد من محاذاة الأسطر، "
                f"وأربع مسافات لكل مستوى داخل الكتل.")

    # missing colon: a compound statement without its trailing ':'
    if re.match(r"\s*(if|elif|else|for|while|def|class|try|except|finally|with|"
                r"إذا|لكل|طالما)\b", cur) and ":" not in cur:
        return (f"نسيت وضع النقطتين الرأسيتين (:) في نهاية السطر {_ar_num(line)}. "
                f"جُمَل مثل if و for و while و def تنتهي بنقطتين.")

    # unmatched / unclosed brackets or quotes
    if "unterminated string" in msg or "EOL while scanning" in msg:
        return (f"سلسلة نصية غير مُغلقة{where}: نسيت علامة الاقتباس في نهاية النص. "
                f"تأكّد من إغلاق كل \" أو '.")
    if "was never closed" in msg or "unexpected EOF" in msg:
        return (f"قوس غير مُغلق{where}: فتحت قوساً ( أو [ أو {{ ولم تُغلقه. "
                f"تأكّد من إغلاق كل قوس فتحته.")
    if "unmatched" in msg or "closing parenthesis" in msg:
        return (f"قوس زائد أو غير متطابق{where}: يوجد قوس إغلاق بلا قوس فتح مقابل، "
                f"أو الأقواس غير متوازنة.")

    # assignment vs comparison
    if "cannot assign" in msg or ("invalid syntax" in msg and "==" not in cur and "=" in cur
                                  and re.search(r"(if|while|إذا|طالما)\b", cur)):
        return (f"ربما استخدمت = بدل =={where}: للمقارنة استعمل == (علامتَي يساوي)، "
                f"أمّا = فهي لإسناد قيمة.")

    # print as a statement (Python 2 habit)
    if "Missing parentheses in call to 'print'" in (exc.msg or ""):
        return (f"في بايثون ٣ يجب وضع قوسين حول ما تطبعه{where}: "
                f"اكتب print(\"مرحبا\") مع القوسين.")

    # generic fallback with the offending line quoted
    hint = f" السطر: {cur.strip()}" if cur.strip() else ""
    return (f"خطأ في الصياغة{where}: راجع هذا السطر بحثاً عن رمز ناقص أو زائد "
            f"(نقطتان، قوس، فاصلة، أو علامة اقتباس).{hint}")


# ---------------------------------------------------------------------------
# run-time exceptions
# ---------------------------------------------------------------------------

_RUNTIME = {
    "ZeroDivisionError": "قسمة على صفر: لا يمكن القسمة على صفر. تحقّق من المقسوم عليه.",
    "NameError": "اسم غير معرّف: استخدمت اسم متغيّر أو دالة لم تُعرّفه بعد، أو أخطأت في كتابته.",
    "TypeError": "خطأ في النوع: أجريت عملية على نوع بيانات غير مناسب "
                 "(مثل جمع نص مع رقم). حوّل الأنواع أولاً.",
    "ValueError": "قيمة غير صالحة: القيمة من النوع الصحيح لكنها غير مقبولة "
                  "(مثل تحويل نص ليس رقماً إلى عدد).",
    "IndexError": "فهرس خارج النطاق: طلبت عنصراً برقم أكبر من حجم القائمة. "
                  "تذكّر أن الترقيم يبدأ من صفر.",
    "KeyError": "مفتاح غير موجود: طلبت مفتاحاً غير موجود في القاموس.",
    "AttributeError": "خاصية غير موجودة: طلبت خاصية أو دالة لا يملكها هذا الكائن.",
    "ImportError": "تعذّر الاستيراد: لم يُعثر على الوحدة التي حاولت استيرادها.",
    "ModuleNotFoundError": "وحدة غير موجودة: اسم الوحدة في import غير صحيح أو غير مثبّتة.",
    "RecursionError": "تكرار عميق جداً: دالة تستدعي نفسها بلا نهاية. "
                      "تأكّد من وجود حالة توقّف.",
    "OverflowError": "تجاوز في الحساب: الناتج كبير جداً على التمثيل.",
    "StopIteration": "انتهى المكرّر: لم تبقَ عناصر.",
    "KeyboardInterrupt": "تم إيقاف التنفيذ.",
}


def explain_exception(exc_type, exc_value, line=None):
    """Return an Arabic explanation for a runtime exception. ``exc_type`` may be a
    type or its name; ``line`` (if known from the traceback) is included."""
    name = exc_type.__name__ if isinstance(exc_type, type) else str(exc_type)
    where = f" (السطر {_ar_num(line)})" if line else ""
    base = _RUNTIME.get(name)
    detail = str(exc_value).strip()
    if base:
        text = base + where
        # add the specific undefined name for NameError, key for KeyError, etc.
        if name == "NameError" and detail:
            m = re.search(r"name '([^']+)'", detail)
            if m:
                text += f" الاسم غير المعرّف: {m.group(1)}."
        return text
    # unknown exception: give the type and message plainly
    return f"حدث خطأ من النوع {name}{where}: {detail}"


def explain_traceback(tb_exc_type, tb_exc_value, tb):
    """Extract the deepest line number in the *user* code from a traceback object
    and produce an Arabic explanation. The sandbox passes the tb from its run."""
    line = None
    t = tb
    while t is not None:
        frame = t.tb_frame
        if frame.f_code.co_filename == "<code>":
            line = t.tb_lineno
        t = t.tb_next
    return explain_exception(tb_exc_type, tb_exc_value, line)
