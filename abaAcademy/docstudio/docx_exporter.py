# -*- coding: utf-8 -*-
"""
abaAcademy.docstudio.docx_exporter
==================================

Export a student's notes (written in a small subset of Markdown) to a proper
Right-to-Left Word ``.docx`` — with no external libraries. A ``.docx`` is just a
ZIP of XML parts, so we assemble the handful of parts Word needs, writing the
document body with RTL paragraph direction and Arabic-appropriate defaults.

Why pure XML (not python-docx / docx-js)
----------------------------------------
This runs in the application, where only Python's standard library and wxPython are
guaranteed. So we build the ``.docx`` from ``zipfile`` + string XML templates —
no third-party dependency. The trade-off is that we support a deliberately small,
well-tested feature set (headings, paragraphs, bold/italic runs, bullet lists,
and simple tables) rather than the whole Word format. That subset covers a
student's homework and notes, and every part we emit is minimal, valid
OOXML with the RTL and language settings Arabic needs.

Supported Markdown subset
-------------------------
* ``# / ## ###`` headings (levels 1-3)
* paragraphs (blank-line separated)
* ``- `` or ``* `` bullet list items
* ``**bold**`` and ``*italic*`` inline runs
* ``> `` blockquote
* simple pipe tables:  ``| a | b |`` with a ``|---|---|`` separator row

Anything else is emitted as plain paragraph text.
"""

from __future__ import annotations

import os
import re
import zipfile
from xml.sax.saxutils import escape


# ---------------------------------------------------------------------------
# static parts
# ---------------------------------------------------------------------------

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

_DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

# styles: RTL defaults, Arabic font, heading styles with colour
_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr>
<w:rFonts w:ascii="Amiri" w:hAnsi="Amiri" w:cs="Amiri"/>
<w:sz w:val="28"/><w:szCs w:val="28"/><w:rtl/>
</w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:bidi/>
<w:spacing w:line="360" w:lineRule="auto"/>
<w:jc w:val="right"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>
<w:pPr><w:bidi/><w:jc w:val="right"/><w:outlineLvl w:val="0"/><w:spacing w:before="240" w:after="120"/></w:pPr>
<w:rPr><w:b/><w:bCs/><w:color w:val="1F4E79"/><w:sz w:val="40"/><w:szCs w:val="40"/><w:rtl/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>
<w:pPr><w:bidi/><w:jc w:val="right"/><w:outlineLvl w:val="1"/><w:spacing w:before="200" w:after="100"/></w:pPr>
<w:rPr><w:b/><w:bCs/><w:color w:val="2E75B6"/><w:sz w:val="34"/><w:szCs w:val="34"/><w:rtl/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/>
<w:pPr><w:bidi/><w:jc w:val="right"/><w:outlineLvl w:val="2"/><w:spacing w:before="160" w:after="80"/></w:pPr>
<w:rPr><w:b/><w:bCs/><w:color w:val="5B9BD5"/><w:sz w:val="30"/><w:szCs w:val="30"/><w:rtl/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/>
<w:pPr><w:bidi/><w:jc w:val="right"/><w:ind w:right="720"/></w:pPr>
<w:rPr><w:i/><w:iCs/><w:color w:val="595959"/><w:rtl/></w:rPr></w:style>
</w:styles>"""


# ---------------------------------------------------------------------------
# inline run parsing (bold / italic)
# ---------------------------------------------------------------------------

def _runs_xml(text):
    """Turn inline **bold** / *italic* into a sequence of <w:r> runs."""
    parts = re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", text)
    runs = []
    for p in parts:
        if not p:
            continue
        bold = italic = False
        if p.startswith("**") and p.endswith("**"):
            bold = True
            p = p[2:-2]
        elif p.startswith("*") and p.endswith("*"):
            italic = True
            p = p[1:-1]
        rpr = "<w:rPr>"
        if bold:
            rpr += "<w:b/><w:bCs/>"
        if italic:
            rpr += "<w:i/><w:iCs/>"
        rpr += "<w:rtl/></w:rPr>"
        runs.append(f'<w:r>{rpr}<w:t xml:space="preserve">{escape(p)}</w:t></w:r>')
    return "".join(runs) or '<w:r><w:rPr><w:rtl/></w:rPr><w:t/></w:r>'


def _para(text, style=None):
    ppr = "<w:pPr><w:bidi/><w:jc w:val=\"right\"/>"
    if style:
        ppr += f'<w:pStyle w:val="{style}"/>'
    ppr += "</w:pPr>"
    return f"<w:p>{ppr}{_runs_xml(text)}</w:p>"


def _bullet(text):
    ppr = ('<w:pPr><w:bidi/><w:jc w:val="right"/>'
           '<w:ind w:right="360" w:hanging="360"/></w:pPr>')
    # a simple bullet glyph run then the text (kept RTL)
    bullet_run = '<w:r><w:rPr><w:rtl/></w:rPr><w:t xml:space="preserve">•  </w:t></w:r>'
    return f"<w:p>{ppr}{bullet_run}{_runs_xml(text)}</w:p>"


def _table(rows):
    """rows: list of list of cell strings. Emit a simple bordered RTL table."""
    borders = ("<w:tblBorders>"
               + "".join(f'<w:{e} w:val="single" w:sz="6" w:space="0" w:color="A0A0A0"/>'
                         for e in ("top", "left", "bottom", "right", "insideH", "insideV"))
               + "</w:tblBorders>")
    tbl = ('<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/>'
           '<w:bidiVisual/><w:tblW w:w="0" w:type="auto"/>' + borders + "</w:tblPr>")
    for r_i, row in enumerate(rows):
        tbl += "<w:tr>"
        for cell in row:
            shade = ('<w:shd w:val="clear" w:fill="D9E2F3"/>' if r_i == 0 else "")
            cell_runs = _runs_xml(f"**{cell}**" if r_i == 0 else cell)
            tbl += (f'<w:tc><w:tcPr>{shade}</w:tcPr>'
                    f'<w:p><w:pPr><w:bidi/><w:jc w:val="right"/></w:pPr>{cell_runs}</w:p></w:tc>')
        tbl += "</w:tr>"
    tbl += "</w:tbl>"
    return tbl


# ---------------------------------------------------------------------------
# markdown -> body
# ---------------------------------------------------------------------------

def _markdown_to_body(md):
    lines = md.replace("\r\n", "\n").split("\n")
    body = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        # table: a line with pipes followed by a |---| separator
        if line.lstrip().startswith("|") and i + 1 < len(lines) and \
                re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            rows = []
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            rows.append(header)
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            body.append(_table(rows))
            continue
        # headings
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            body.append(_para(m.group(2), style=f"Heading{level}"))
            i += 1
            continue
        # blockquote
        if line.lstrip().startswith(">"):
            body.append(_para(line.lstrip()[1:].strip(), style="Quote"))
            i += 1
            continue
        # bullet
        if re.match(r"^\s*[-*]\s+", line):
            text = re.sub(r"^\s*[-*]\s+", "", line)
            body.append(_bullet(text))
            i += 1
            continue
        # plain paragraph
        body.append(_para(line))
        i += 1
    return "".join(body)


def _document_xml(md, title=None, author=None):
    body = ""
    if title:
        body += _para(title, style="Heading1")
    body += _markdown_to_body(md)
    # section properties: A4, RTL
    sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>'
            '<w:bidi/></w:sectPr>')
    footer = ""
    if author:
        footer = _para(f"إعداد: {author}")
    return ("""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>""" + body + footer + sect + "</w:body></w:document>")


def export_markdown_to_docx(md, out_path, title=None, author=None):
    """Write ``md`` (Markdown subset) to a valid RTL ``.docx`` at ``out_path``."""
    doc = _document_xml(md, title=title, author=author)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _ROOT_RELS)
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", _STYLES)
        z.writestr("word/_rels/document.xml.rels", _DOC_RELS)
    return out_path
