# -*- coding: utf-8 -*-
"""Static integrity checks across every screen.

A packaged application cannot afford an AttributeError that only appears when a
learner opens a particular screen. These checks parse every GUI module and
verify that each ``self._method()`` a screen calls actually exists somewhere in
its class hierarchy — the exact failure that shipped when a refactor removed a
method that was still being called.
"""

import ast
import os
import unittest

_GUI = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "gui"))

# helpers provided by AccessibleDialog / wx that screens legitimately call
_BASE_HELPERS = {
    "announce", "button", "bind_choice", "close_screen", "set_first_control",
    "on_enter_key", "on_closing", "show_child", "instructions", "on_help",
    "can_close", "call_later", "choice_index", "on_raw_key_down",
    "_say", "_announce_screen", "_restore_geometry", "_save_geometry",
    "_geometry_key", "_store", "_is_text_focus", "_on_show", "_on_char_hook",
    "_progress_text", "_refresh_progress", "_run_session", "_run",
    "set_first_control_name", "add_accelerator", "speak_line", "interrupt",
}


def _class_methods(node):
    return {n.name for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _self_calls(node):
    out = set()
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                and isinstance(sub.func.value, ast.Name)
                and sub.func.value.id == "self"):
            out.add(sub.func.attr)
    return out


def _assigned_attrs(node):
    """Attributes assigned on self, so ``self._cap = ...`` counts as defined."""
    out = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) \
                and sub.value.id == "self" and isinstance(sub.ctx, ast.Store):
            out.add(sub.attr)
    return out


def _wx_window_methods():
    """Methods inherited from wx windows/dialogs, which we can't see by parsing."""
    try:
        import wx
        names = set(dir(wx.Dialog)) | set(dir(wx.Frame)) | set(dir(wx.Window))
        return names
    except Exception:
        # wx isn't installed in the test environment; use the ones screens use
        return {
            "Bind", "FindFocus", "Raise", "Destroy", "Close", "Show", "Hide",
            "SetTitle", "GetTitle", "ShowModal", "EndModal", "SetSizer",
            "Layout", "Fit", "Centre", "Center", "SetSize", "GetSize",
            "SetMinSize", "GetMinSize", "IsShown", "IsMaximized", "IsIconized",
            "IsDescendant", "GetChildren", "SetFocus", "Refresh", "Update",
            "SetAcceleratorTable", "GetParent", "SetLabel", "GetId",
            "TransferDataToWindow", "TransferDataFromWindow", "SetName",
            "IsModal", "SetEscapeId", "GetSizer", "SetAffirmativeId",
        }


def _package_class_methods():
    """Every class in the gui package -> its methods, so a base class defined in
    another module of the package can still be resolved."""
    out = {}
    for fname in os.listdir(_GUI):
        if not fname.endswith(".py"):
            continue
        try:
            tree = ast.parse(open(os.path.join(_GUI, fname),
                                  encoding="utf-8").read())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                names = _class_methods(node) | _assigned_attrs(node)
                out.setdefault(node.name, set()).update(names)
    return out


class TestScreenIntegrity(unittest.TestCase):
    def test_every_self_call_resolves(self):
        problems = []
        wx_methods = _wx_window_methods()
        pkg_classes = _package_class_methods()
        for fname in sorted(os.listdir(_GUI)):
            if not fname.endswith(".py"):
                continue
            path = os.path.join(_GUI, fname)
            try:
                tree = ast.parse(open(path, encoding="utf-8").read())
            except SyntaxError as exc:
                problems.append(f"{fname}: syntax error {exc}")
                continue
            module_funcs = {n.name for n in tree.body
                            if isinstance(n, ast.FunctionDef)}
            classes = {n.name: n for n in ast.walk(tree)
                       if isinstance(n, ast.ClassDef)}
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                defined = _class_methods(node) | _assigned_attrs(node)
                # pull in anything defined by base classes in this module; a
                # base from another module is assumed to provide what it needs
                for base in node.bases:
                    name = getattr(base, "id", None) or getattr(base, "attr", None)
                    if not name:
                        continue
                    if name in classes:
                        defined |= _class_methods(classes[name])
                        defined |= _assigned_attrs(classes[name])
                    elif name in pkg_classes:
                        # base lives in another module of the gui package
                        defined |= pkg_classes[name]
                defined |= _BASE_HELPERS | module_funcs | wx_methods
                for called in _self_calls(node):
                    if called.startswith("__"):
                        continue
                    if called not in defined:
                        problems.append(
                            f"{fname}::{node.name} calls self.{called}() "
                            f"which is not defined")
        self.assertEqual(problems, [], "\n".join(problems))


if __name__ == "__main__":
    unittest.main(verbosity=2)
