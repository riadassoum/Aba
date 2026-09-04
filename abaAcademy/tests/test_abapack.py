# -*- coding: utf-8 -*-
"""Tests for the .abapack course-pack format: build, read, install, and the
path-safety guarantees that protect a student's machine."""

import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.packformat.abapack import (
    PackBuilder, PackReader, PackError, _join_safe, make_manifest,
)


class TestAbapack(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _sample_pack(self):
        b = PackBuilder("t.geo.rivers", "أنهار", author="معلّم")
        course = {"course_id": "t.geo.rivers", "title": "أنهار", "order": 99,
                  "version": 1, "levels": []}
        b.add_course(course, lessons={"levels/l1/quiz.json": {"blocks": []}})
        b.add_flashcard_deck("rivers", {"name": "أنهار", "cards": []})
        path = os.path.join(self.tmp, "p.abapack")
        b.write(path)
        return path

    def test_build_and_read(self):
        path = self._sample_pack()
        self.assertTrue(os.path.getsize(path) > 0)
        r = PackReader(path)
        self.assertEqual(r.manifest["id"], "t.geo.rivers")
        self.assertIn("course", r.manifest["contains"])
        self.assertIn("flashcards", r.manifest["contains"])

    def test_install(self):
        path = self._sample_pack()
        udir = os.path.join(self.tmp, "ud")
        os.makedirs(udir)
        report = PackReader(path).install(udir)
        self.assertIn("تم التثبيت", report)
        self.assertTrue(os.path.exists(
            os.path.join(udir, "courses", "t.geo.rivers", "course.json")))
        self.assertTrue(os.path.exists(
            os.path.join(udir, "flashcards", "rivers.json")))

    def test_no_overwrite_by_default(self):
        path = self._sample_pack()
        udir = os.path.join(self.tmp, "ud")
        os.makedirs(udir)
        PackReader(path).install(udir)
        with self.assertRaises(PackError):
            PackReader(path).install(udir)          # course already exists

    def test_overwrite_allowed(self):
        path = self._sample_pack()
        udir = os.path.join(self.tmp, "ud")
        os.makedirs(udir)
        PackReader(path).install(udir)
        # should not raise with overwrite=True
        PackReader(path).install(udir, overwrite=True)

    def test_invalid_manifest_rejected(self):
        with self.assertRaises(PackError):
            make_manifest("!!bad id!!", "x")

    def test_not_a_zip(self):
        bad = os.path.join(self.tmp, "bad.abapack")
        with open(bad, "w") as f:
            f.write("not a zip")
        with self.assertRaises(PackError):
            PackReader(bad)

    def test_path_traversal_contained(self):
        base = os.path.join(self.tmp, "base")
        for rel in ["../../etc/passwd", "/etc/passwd", "a/../../b"]:
            result = _join_safe(base, rel)
            norm = os.path.normpath(base)
            self.assertTrue(result == norm or result.startswith(norm + os.sep),
                            f"{rel} escaped containment")


if __name__ == "__main__":
    unittest.main(verbosity=2)
