# -*- coding: utf-8 -*-
"""
abaAcademy.codelab.tracer
=========================

The execution tracer (متتبّع التنفيذ): run a learner's program one line at a
time and record, for every step, which line ran, which variables changed and
to what, what was printed, and when a function was entered or returned.

A sighted programmer watches variables change in a debugger's panes; this
gives a screen-reader user the same view as a list of spoken steps
(السطر ٣: total = total + n — صار total = 6). It reuses the code lab's
sandbox namespace (safe builtins and the module allow-list) and stops after
a step budget so an endless loop ends with an explanation, not a hang.
"""

from __future__ import annotations

import contextlib
import io
import sys
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .sandbox import _make_namespace
from .ast_diagnostics import explain_syntax, explain_traceback

FILENAME = "<برنامجي>"
MAX_REPR = 60


class _StepLimit(Exception):
    pass


def _short(v) -> str:
    try:
        r = repr(v)
    except Exception:
        r = f"<{type(v).__name__}>"
    return r if len(r) <= MAX_REPR else r[:MAX_REPR - 1] + "…"


def _type_ar(v) -> str:
    return {int: "عدد صحيح", float: "عدد عشري", str: "نصّ", bool: "منطقي", list: "قائمة",
            dict: "قاموس", tuple: "صفّ ثابت", set: "مجموعة", type(None): "لا شيء"}.get(type(v), type(v).__name__)


@dataclass
class Step:
    index: int
    kind: str                 # "line" | "call" | "return" | "exception"
    line: int
    code: str
    function: str
    changes: List[str] = field(default_factory=list)
    output: str = ""
    depth: int = 0

    def spoken(self) -> str:
        where = f"السطر {self.line}"
        if self.function != "<module>":
            where += f" داخل {self.function}"
        if self.kind == "call":
            text = f"دخول الدالّة {self.function}"
            if self.changes:
                text += ": " + "، ".join(self.changes)
            return text
        if self.kind == "return":
            return f"خروج من {self.function} " + ("، ".join(self.changes) if self.changes else "")
        if self.kind == "exception":
            return f"{where}: حدث خطأ — " + "، ".join(self.changes)
        text = f"{where}: {self.code.strip()}"
        if self.changes:
            text += " — " + "، ".join(self.changes)
        if self.output:
            text += f" — طُبع: {self.output.strip()}"
        return text


@dataclass
class Trace:
    steps: List[Step]
    output: str
    error: Optional[str]
    stopped: bool
    final_vars: Dict[str, str]

    def summary(self) -> str:
        from ..tools.ar_count import count
        parts = [f"نُفّذت {count(len(self.steps), 'step')}."]
        if self.stopped:
            parts.append("توقّف التتبّع عند حدّ الخطوات؛ ربما فيه حلقة لا تنتهي.")
        if self.error:
            parts.append(self.error)
        if self.final_vars:
            parts.append("القيم الأخيرة: " + "، ".join(f"{k} = {v}" for k, v in self.final_vars.items()))
        return " ".join(parts)

    def line_counts(self) -> Dict[int, int]:
        out: Dict[int, int] = {}
        for s in self.steps:
            if s.kind == "line":
                out[s.line] = out.get(s.line, 0) + 1
        return dict(sorted(out.items()))


def _visible(namespace: dict) -> Dict[str, object]:
    out = {}
    for k, v in namespace.items():
        if k.startswith("__") or callable(v) and not isinstance(v, (list, dict)) and type(v).__name__ in (
                "function", "builtin_function_or_method", "type", "module"):
            continue
        if type(v).__name__ == "module":
            continue
        out[k] = v
    return out


def trace(source: str, max_steps: int = 500, timeout: float = 5.0,
          input_lines: Optional[List[str]] = None) -> Trace:
    syn = explain_syntax(source)
    if syn is not None:
        return Trace([], "", syn, False, {})
    lines = source.splitlines()
    code = compile(source, FILENAME, "exec")
    ns = _make_namespace()
    feed = list(input_lines or [])

    def fake_input(prompt=""):
        if prompt:
            print(prompt, end="")
        return feed.pop(0) if feed else ""
    ns["__builtins__"]["input"] = fake_input

    buf = io.StringIO()
    steps: List[Step] = []
    snapshots: Dict[int, Dict[str, str]] = {}      # frame id -> last reprs
    state = {"printed": 0, "depth": 0}
    pending: Dict[int, Step] = {}                  # frame id -> step whose line is running
    box = {}

    def text_of(n: int) -> str:
        return lines[n - 1] if 0 < n <= len(lines) else ""

    def diff(frame) -> List[str]:
        local = frame.f_locals if frame.f_code.co_name != "<module>" else frame.f_globals
        cur = {k: _short(v) for k, v in _visible(local).items()}
        prev = snapshots.get(id(frame), {})
        changes = []
        for k, v in cur.items():
            if prev.get(k) != v:
                changes.append(f"صار {k} = {v}" if k in prev else f"أُنشئ {k} = {v}")
        for k in prev:
            if k not in cur:
                changes.append(f"حُذف {k}")
        snapshots[id(frame)] = cur
        return changes

    def flush_pending(frame):
        """Attach the effects of this frame's previous line (now finished)."""
        st = pending.pop(id(frame), None)
        if st is None:
            return
        st.changes = diff(frame)
        out = buf.getvalue()
        st.output = out[state["printed"]:]
        state["printed"] = len(out)

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != FILENAME:
            return None
        if len(steps) >= max_steps:
            raise _StepLimit()
        fname = frame.f_code.co_name
        if event == "call":
            if fname == "<module>":
                snapshots[id(frame)] = {}
                return tracer
            state["depth"] += 1
            args = [f"{k} = {_short(frame.f_locals.get(k))}"
                    for k in frame.f_code.co_varnames[:frame.f_code.co_argcount]]
            snapshots[id(frame)] = {k: _short(v) for k, v in _visible(frame.f_locals).items()}
            steps.append(Step(len(steps) + 1, "call", frame.f_lineno, text_of(frame.f_lineno),
                              fname, args, depth=state["depth"]))
            return tracer
        if event == "line":
            # the previous line in this frame has now completed
            flush_pending(frame)
            st = Step(len(steps) + 1, "line", frame.f_lineno, text_of(frame.f_lineno), fname,
                      depth=state["depth"])
            steps.append(st)
            pending[id(frame)] = st
            return tracer
        if event == "return":
            flush_pending(frame)
            if fname != "<module>":
                steps.append(Step(len(steps) + 1, "return", frame.f_lineno, text_of(frame.f_lineno),
                                  fname, [f"وأعادت {_short(arg)}"], depth=state["depth"]))
                state["depth"] = max(0, state["depth"] - 1)
            snapshots.pop(id(frame), None)
            return tracer
        if event == "exception":
            exc_type, exc, _ = arg
            if exc_type is _StepLimit:
                return tracer
            flush_pending(frame)
            steps.append(Step(len(steps) + 1, "exception", frame.f_lineno, text_of(frame.f_lineno),
                              fname, [f"{exc_type.__name__}: {exc}"], depth=state["depth"]))
            return tracer
        return tracer

    def worker():
        sys.settrace(tracer)
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                exec(code, ns)
            box["ok"] = True
        except _StepLimit:
            box["stopped"] = True
        except BaseException as exc:          # noqa: learner code may raise anything
            box["exc"] = (type(exc), exc, exc.__traceback__)
        finally:
            sys.settrace(None)

    t = threading.Thread(target=worker, daemon=True, name="code-tracer")
    t.start()
    t.join(timeout)
    stopped = bool(box.get("stopped")) or t.is_alive()
    error = None
    if "exc" in box:
        error = explain_traceback(*box["exc"])
    final = {k: _short(v) for k, v in _visible(ns).items() if k != "__builtins__"}
    return Trace(steps, buf.getvalue(), error, stopped, final)


SAMPLES = [
    ("مجموع الأعداد من ١ إلى ٥", "total = 0\nfor n in range(1, 6):\n    total = total + n\nprint(total)\n"),
    ("دالّة المضروب", "def factorial(n):\n    result = 1\n    for k in range(2, n + 1):\n"
                     "        result = result * k\n    return result\n\nprint(factorial(4))\n"),
    ("أكبر عنصر في قائمة", "numbers = [7, 3, 12, 5]\nbiggest = numbers[0]\nfor x in numbers:\n"
                          "    if x > biggest:\n        biggest = x\nprint(biggest)\n"),
    ("حلقة while", "n = 10\nsteps = 0\nwhile n != 1:\n    if n % 2 == 0:\n        n = n // 2\n"
                   "    else:\n        n = 3 * n + 1\n    steps = steps + 1\nprint(steps)\n"),
    ("دالّة ذاتية الاستدعاء", "def countdown(n):\n    if n == 0:\n        return 'انطلق'\n"
                             "    return countdown(n - 1)\n\nprint(countdown(3))\n"),
]
