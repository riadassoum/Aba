# -*- coding: utf-8 -*-
"""Tests for the invented batch: docx/HTML export, tafqit (number-to-words), and
the Hijri-Gregorian converter."""

import os
import sys
import tempfile
import unittest
import zipfile
import xml.dom.minidom

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.docstudio.docx_exporter import export_markdown_to_docx
from abaAcademy.docstudio.html_exporter import export_markdown_to_html
from abaAcademy.tools.tafqit import number_to_arabic_words as n2w
from abaAcademy.tools import hijri


class TestDocx(unittest.TestCase):
    def test_produces_valid_zip_with_parts(self):
        p = os.path.join(tempfile.mkdtemp(), "t.docx")
        export_markdown_to_docx("# عنوان\n\nنص **عريض**\n\n- نقطة", p,
                                title="ملف", author="سالم")
        z = zipfile.ZipFile(p)
        self.assertIsNone(z.testzip())
        for part in ("[Content_Types].xml", "word/document.xml",
                     "word/styles.xml", "word/_rels/document.xml.rels"):
            self.assertIn(part, z.namelist())

    def test_document_xml_wellformed(self):
        p = os.path.join(tempfile.mkdtemp(), "t.docx")
        export_markdown_to_docx("## عنوان\n\n| أ | ب |\n|---|---|\n| ١ | ٢ |", p)
        z = zipfile.ZipFile(p)
        # must parse as XML
        xml.dom.minidom.parseString(z.read("word/document.xml"))
        xml.dom.minidom.parseString(z.read("word/styles.xml"))

    def test_rtl_present(self):
        p = os.path.join(tempfile.mkdtemp(), "t.docx")
        export_markdown_to_docx("نص", p)
        doc = zipfile.ZipFile(p).read("word/document.xml").decode("utf-8")
        self.assertIn("<w:bidi/>", doc)


class TestHtml(unittest.TestCase):
    def test_rtl_and_elements(self):
        p = os.path.join(tempfile.mkdtemp(), "t.html")
        export_markdown_to_html("# ع\n\n- ن\n\n> اقتباس", p, title="ت")
        html = open(p, encoding="utf-8").read()
        self.assertIn('dir="rtl"', html)
        self.assertIn("<ul>", html)
        self.assertIn("<blockquote>", html)


class TestTafqit(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(n2w(0), "صفر")
        self.assertEqual(n2w(1), "واحد")
        self.assertEqual(n2w(100), "مئة")
        self.assertEqual(n2w(200), "مئتان")

    def test_compound(self):
        self.assertEqual(n2w(23), "ثلاثة وعشرون")
        self.assertIn("مئة", n2w(123))

    def test_scales_standalone(self):
        self.assertEqual(n2w(1000), "ألف")
        self.assertEqual(n2w(1000000), "مليون")
        self.assertEqual(n2w(2000), "ألفان")

    def test_teens(self):
        self.assertEqual(n2w(11), "أحد عشر")
        self.assertEqual(n2w(15), "خمسة عشر")


class TestHijri(unittest.TestCase):
    def test_known_date(self):
        # 1 Muharram 1445 = 19 July 2023
        self.assertEqual(hijri.hijri_to_gregorian(1445, 1, 1), (2023, 7, 19))
        self.assertEqual(hijri.gregorian_to_hijri(2023, 7, 19), (1445, 1, 1))

    def test_round_trip(self):
        for g in [(2024, 3, 15), (2020, 1, 1), (2025, 12, 31), (2000, 6, 15)]:
            h = hijri.gregorian_to_hijri(*g)
            self.assertEqual(hijri.hijri_to_gregorian(*h), g)

    def test_today_both_returns_two_strings(self):
        g, h = hijri.today_both()
        self.assertIn("م", g)
        self.assertIn("هـ", h)


if __name__ == "__main__":
    unittest.main(verbosity=2)
