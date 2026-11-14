# -*- coding: utf-8 -*-
"""Every hub button must open something real.

The hub imports most screens lazily inside its ``_open_*`` handlers, so a
renamed module or class would only fail when a learner pressed that button.
This test reads the hub and the games arcade, and checks that every lazy
``from .module import Name`` resolves to a class defined in that module, that
every button's handler exists, and that no two buttons share a label."""

import ast
import os
import unittest

_GUI = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "gui"))


def _tree(name):
    with open(os.path.join(_GUI, name), encoding="utf-8") as f:
        return ast.parse(f.read())


def _defined_names(module_file):
    path = os.path.join(_GUI, module_file + ".py")
    if not os.path.exists(path):
        return None
    t = _tree(module_file + ".py")
    return {n.name for n in ast.walk(t) if isinstance(n, (ast.ClassDef, ast.FunctionDef))} | \
           {tg.id for n in ast.walk(t) if isinstance(n, ast.Assign) for tg in n.targets if isinstance(tg, ast.Name)}


class TestHubWiring(unittest.TestCase):
    def test_lazy_imports_resolve(self):
        problems = []
        for fname in ("hub.py", "games.py"):
            for node in ast.walk(_tree(fname)):
                if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                    names = _defined_names(node.module)
                    if names is None:
                        problems.append(f"{fname}: module .{node.module} not found")
                        continue
                    for alias in node.names:
                        if alias.name not in names:
                            problems.append(f"{fname}: {node.module}.{alias.name} not defined")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_catalog_handlers_exist_and_labels_unique(self):
        import sys
        sys.path.insert(0, os.path.abspath(os.path.join(_GUI, "..", "..")))
        from abaAcademy.gui.hub_catalog import CATALOG, all_features, handler_names, course_ids
        t = _tree("hub.py")
        hub = next(n for n in ast.walk(t) if isinstance(n, ast.ClassDef) and n.name == "HubDialog")
        methods = {n.name for n in hub.body if isinstance(n, ast.FunctionDef)}
        missing = [h for h in handler_names() if h not in methods]
        self.assertEqual(missing, [])
        labels = [f.label for f in all_features()]
        self.assertGreater(len(labels), 80)
        self.assertEqual(len(labels), len(set(labels)), [l for l in labels if labels.count(l) > 1])
        courses = os.path.abspath(os.path.join(_GUI, "..", "courses"))
        for cid in course_ids():
            self.assertTrue(os.path.isfile(os.path.join(courses, cid, "course.json")), cid)
        for tab in CATALOG:
            self.assertLessEqual(len(tab.features), 12, tab.title)
            for f in tab.features:
                self.assertTrue(f.description.endswith("."), f.label)
                self.assertLessEqual(len(f.label), 30, f.label)

    def test_puzzle_lookups_exist(self):
        t = _tree("games.py")
        wanted = [n.args[0].value for n in ast.walk(t) if isinstance(n, ast.Call)
                  and getattr(n.func, "id", "") == "_puzzle_cls" and n.args and isinstance(n.args[0], ast.Constant)]
        names = _defined_names("puzzles_view")
        self.assertTrue(wanted)
        for w in wanted:
            self.assertIn(w, names)


if __name__ == "__main__":
    unittest.main()
