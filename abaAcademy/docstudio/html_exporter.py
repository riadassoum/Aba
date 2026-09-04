# -*- coding: utf-8 -*-
"""
abaAcademy.docstudio.html_exporter
==================================

Export the same small Markdown subset as :mod:`docx_exporter`, but to a
self-contained, right-to-left HTML file with clean Arabic typography. Pure
standard library; the styling is inline so the file is portable.
"""

from __future__ import annotations

import re
from xml.sax.saxutils import escape


def _inline(text):
    text = escape(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    return text


def _markdown_to_html_body(md):
    lines = md.replace("\r\n", "\n").split("\n")
    out = []
    i = 0
    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            close_list()
            i += 1
            continue
        # table
        if line.lstrip().startswith("|") and i + 1 < len(lines) and \
                re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            close_list()
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            out.append("<table><thead><tr>"
                       + "".join(f"<th>{_inline(h)}</th>" for h in header)
                       + "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            close_list()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if line.lstrip().startswith(">"):
            close_list()
            out.append(f"<blockquote>{_inline(line.lstrip()[1:].strip())}</blockquote>")
            i += 1
            continue
        if re.match(r"^\s*[-*]\s+", line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(re.sub(r'^\s*[-*]\s+', '', line))}</li>")
            i += 1
            continue
        close_list()
        out.append(f"<p>{_inline(line)}</p>")
        i += 1
    close_list()
    return "\n".join(out)


_TEMPLATE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>
body {{ font-family: "Amiri", "Traditional Arabic", serif; direction: rtl;
        text-align: right; line-height: 1.8; max-width: 46rem; margin: 2rem auto;
        padding: 0 1rem; color: #222; }}
h1 {{ color: #1F4E79; }} h2 {{ color: #2E75B6; }} h3 {{ color: #5B9BD5; }}
blockquote {{ border-right: 4px solid #B0C4DE; margin: 1rem 0; padding: .3rem 1rem;
        color: #555; font-style: italic; background: #F5F8FC; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
th, td {{ border: 1px solid #A0A0A0; padding: .4rem .6rem; text-align: right; }}
th {{ background: #D9E2F3; }}
.author {{ margin-top: 2rem; color: #666; font-size: .9rem; }}
</style>
</head>
<body>
{body}
{footer}
</body>
</html>"""


def export_markdown_to_html(md, out_path, title=None, author=None):
    body = _markdown_to_html_body(md)
    if title:
        body = f"<h1>{escape(title)}</h1>\n" + body
    footer = f'<p class="author">إعداد: {escape(author)}</p>' if author else ""
    html = _TEMPLATE.format(title=escape(title or "مستند"), body=body, footer=footer)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path
