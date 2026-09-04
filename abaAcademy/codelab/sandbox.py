# -*- coding: utf-8 -*-
"""
abaAcademy.codelab.sandbox
==========================

Run a beginner's Python code safely and capture what it prints, so the code lab
can show output and (via ``ast_diagnostics``) explain errors in Arabic.

Honest scope of the "sandbox"
-----------------------------
True security sandboxing of Python is famously hard — CPython gives no perfect
in-process jail. What this module provides is a *practical* teaching sandbox for
a single learner running their own code on their own machine:

* code is compiled first (syntax errors are caught and explained before running);
* a curated set of safe builtins is exposed, and obviously dangerous names
  (``open``, ``eval``, ``exec``, ``__import__``, ``input`` blocking, etc.) are
  removed from the default namespace;
* a small allow-list of safe modules (``math``, ``random``, ``statistics``,
  ``datetime``, ``string``) can be imported; anything else is refused with an
  Arabic message;
* execution runs on a worker thread with a wall-clock timeout so an infinite
  loop can't hang the screen reader;
* ``print`` output is captured and returned.

This is a learning aid, not a security boundary against hostile code — and the UI
says so. For a student practising loops and functions, it does exactly what's
needed: run my code, show my output, explain my error.
"""

from __future__ import annotations

import builtins
import io
import threading
import contextlib

from .ast_diagnostics import explain_syntax, explain_traceback


# modules a learner may import for exercises
_ALLOWED_MODULES = {"math", "random", "statistics", "datetime", "string", "re"}

# builtins we deliberately keep (safe, useful for teaching)
_SAFE_BUILTIN_NAMES = [
    "abs", "all", "any", "bool", "chr", "dict", "divmod", "enumerate", "filter",
    "float", "format", "frozenset", "int", "isinstance", "issubclass", "len",
    "list", "map", "max", "min", "ord", "pow", "print", "range", "repr",
    "reversed", "round", "set", "slice", "sorted", "str", "sum", "tuple", "type",
    "zip", "bin", "hex", "oct", "hash", "id", "True", "False", "None",
    "ValueError", "TypeError", "IndexError", "KeyError", "ZeroDivisionError",
    "StopIteration", "Exception",
]


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".")[0]
    if root not in _ALLOWED_MODULES:
        raise ImportError(
            f"استيراد الوحدة «{name}» غير مسموح في المختبر. "
            f"المسموح: {'، '.join(sorted(_ALLOWED_MODULES))}.")
    return builtins.__import__(name, globals, locals, fromlist, level)


def _make_namespace():
    safe_builtins = {n: getattr(builtins, n) for n in _SAFE_BUILTIN_NAMES
                     if hasattr(builtins, n)}
    safe_builtins["__import__"] = _safe_import
    # needed for the `class` statement to execute; teaching classes is core, and
    # this does not widen the file/network surface.
    safe_builtins["__build_class__"] = builtins.__build_class__
    return {"__builtins__": safe_builtins, "__name__": "__main__"}


class RunResult:
    """Outcome of a run: printed output, and an Arabic error message if any."""

    def __init__(self, output="", error=None, timed_out=False, ok=True):
        self.output = output
        self.error = error            # Arabic explanation, or None
        self.timed_out = timed_out
        self.ok = ok


def run_code(source, timeout=5.0, input_lines=None):
    """Compile, then run ``source`` with captured output and a timeout.

    Returns a :class:`RunResult`. Syntax errors are explained without running.
    ``input_lines`` optionally feeds ``input()`` calls (each call consumes one).
    """
    # 1) syntax first — explained in Arabic, no execution
    syn = explain_syntax(source)
    if syn is not None:
        return RunResult(error=syn, ok=False)

    code = compile(source, "<code>", "exec")
    ns = _make_namespace()

    # a controllable input() for exercises that read input
    feed = list(input_lines or [])

    def fake_input(prompt=""):
        if prompt:
            print(prompt, end="")
        if feed:
            return feed.pop(0)
        return ""
    ns["__builtins__"]["input"] = fake_input

    buf = io.StringIO()
    result_box = {}

    def worker():
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                exec(code, ns)
            result_box["ok"] = True
        except SystemExit:
            result_box["ok"] = True
        except BaseException as exc:  # noqa: capture everything the code raises
            import sys
            result_box["ok"] = False
            result_box["exc"] = (type(exc), exc, exc.__traceback__)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout)

    if t.is_alive():
        # can't force-kill a thread; report timeout. The daemon thread will die
        # with the process; for a learner's loop this is the safe message.
        return RunResult(output=buf.getvalue(), timed_out=True, ok=False,
                         error=(f"استغرق تنفيذ الكود وقتاً أطول من المسموح "
                                f"({int(timeout)} ثوانٍ). ربما لديك حلقة لا تنتهي — "
                                f"تأكّد من وجود شرط توقّف."))

    output = buf.getvalue()
    if result_box.get("ok"):
        return RunResult(output=output, ok=True)

    exc = result_box.get("exc")
    if exc:
        etype, evalue, etb = exc
        arabic = explain_traceback(etype, evalue, etb)
        return RunResult(output=output, error=arabic, ok=False)
    return RunResult(output=output, ok=True)
