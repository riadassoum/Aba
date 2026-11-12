# -*- coding: utf-8 -*-
"""
abaAcademy.codelab.web_sandbox
==============================

A web-page accessibility checker and screen-reader preview for HTML the
learner writes.

``audit(html)`` reports, in Arabic, the problems a screen-reader user would
actually meet: a missing page title or language, skipped heading levels,
images without alternative text, links and buttons with no name, form
fields with no label, tables without headers, duplicate ids, and ARIA
references to ids that don't exist.

``accessibility_tree(html)`` builds the object tree a screen reader presents
(roles, names, heading levels, states) so the learner can walk their own
page with the arrow keys and hear it as a user would, and ``reading_order``
flattens it into browse-mode lines. ``headings`` / ``landmarks`` / ``links``
give the quick-navigation lists (H, D, K in browse mode).

Built on the standard library's ``html.parser``; nothing is fetched or run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}

# implicit roles (HTML-AAM, simplified to what screen readers announce)
IMPLICIT_ROLES = {
    "a": "link", "article": "article", "aside": "complementary", "button": "button",
    "dialog": "dialog", "fieldset": "group", "figure": "figure", "footer": "contentinfo",
    "form": "form", "h1": "heading", "h2": "heading", "h3": "heading", "h4": "heading",
    "h5": "heading", "h6": "heading", "header": "banner", "hr": "separator",
    "img": "img", "li": "listitem", "main": "main", "nav": "navigation", "ol": "list",
    "option": "option", "progress": "progressbar", "section": "region", "select": "combobox",
    "table": "table", "tbody": "rowgroup", "td": "cell", "textarea": "textbox",
    "th": "columnheader", "thead": "rowgroup", "tr": "row", "ul": "list",
    "details": "group", "summary": "button", "meter": "meter",
}

INPUT_ROLES = {
    "button": "button", "submit": "button", "reset": "button", "image": "button",
    "checkbox": "checkbox", "radio": "radio", "range": "slider", "search": "searchbox",
    "email": "textbox", "tel": "textbox", "text": "textbox", "url": "textbox",
    "password": "textbox", "number": "spinbutton", "hidden": "",
}

ROLE_NAMES = {
    "link": "رابط", "button": "زرّ", "heading": "عنوان", "img": "صورة",
    "list": "قائمة", "listitem": "عنصر قائمة", "navigation": "منطقة تنقّل",
    "main": "المحتوى الرئيسي", "banner": "ترويسة", "contentinfo": "تذييل",
    "complementary": "محتوى جانبي", "form": "نموذج", "region": "منطقة",
    "article": "مقال", "table": "جدول", "row": "صفّ", "cell": "خليّة",
    "columnheader": "رأس عمود", "rowheader": "رأس صفّ", "textbox": "حقل تحرير",
    "searchbox": "حقل بحث", "checkbox": "خانة اختيار", "radio": "زرّ اختيار",
    "combobox": "قائمة منسدلة", "option": "خيار", "slider": "منزلق",
    "spinbutton": "حقل رقمي", "group": "مجموعة", "dialog": "مربّع حوار",
    "separator": "فاصل", "figure": "شكل", "progressbar": "شريط تقدّم",
    "alert": "تنبيه", "status": "حالة", "tab": "تبويب", "tablist": "قائمة تبويبات",
    "tabpanel": "لوحة تبويب", "menu": "قائمة أوامر", "menuitem": "عنصر قائمة أوامر",
    "switch": "مفتاح تبديل", "document": "مستند", "text": "نصّ", "rowgroup": "",
    "meter": "مقياس", "presentation": "", "none": "",
}

LANDMARK_ROLES = {"banner", "navigation", "main", "complementary", "contentinfo",
                  "form", "region", "search"}

NAME_FROM_CONTENT = {"link", "button", "heading", "cell", "columnheader", "rowheader",
                     "listitem", "option", "tab", "menuitem", "checkbox", "radio",
                     "switch", "summary"}


@dataclass
class Node:
    tag: str
    attrs: Dict[str, str]
    line: int
    children: List["Node"] = field(default_factory=list)
    parent: Optional["Node"] = None
    text_parts: List[str] = field(default_factory=list)

    def attr(self, k: str, default: str = "") -> str:
        return self.attrs.get(k, default)

    def text(self) -> str:
        """Visible text content of the subtree (images contribute alt)."""
        out = []
        for part in self._walk_text():
            out.append(part)
        return " ".join(" ".join(out).split())

    def _walk_text(self):
        if self.tag in ("script", "style", "template"):
            return
        if self.attrs.get("aria-hidden") == "true" or "hidden" in self.attrs:
            return
        if self.tag == "img":
            alt = self.attrs.get("alt")
            if alt:
                yield alt
            return
        for item in self.text_parts:
            if isinstance(item, Node):
                yield from item._walk_text()
            else:
                yield item

    def iter(self):
        yield self
        for c in self.children:
            yield from c.iter()


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", {}, 0)
        self.stack = [self.root]
        self.errors: List[Tuple[int, str]] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        parent = self.stack[-1]
        # implicit closes for common unclosed elements
        if tag in ("li", "p", "tr", "td", "th", "option") and parent.tag == tag:
            self.stack.pop()
            parent = self.stack[-1]
        node = Node(tag, a, self.getpos()[0], parent=parent)
        parent.children.append(node)
        parent.text_parts.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID and self.stack[-1].tag == tag.lower():
            self.stack.pop()

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                if i != len(self.stack) - 1:
                    unclosed = self.stack[-1].tag
                    self.errors.append((self.getpos()[0],
                                        f"الوسم <{unclosed}> لم يُغلق قبل </{tag}>."))
                del self.stack[i:]
                return
        self.errors.append((self.getpos()[0], f"وسم إغلاق </{tag}> بلا وسم فتح."))

    def handle_data(self, data):
        if data.strip():
            self.stack[-1].text_parts.append(data)


def parse(html: str) -> Tuple[Node, List[Tuple[int, str]]]:
    b = _TreeBuilder()
    b.feed(html)
    b.close()
    for n in b.stack[1:]:
        if n.tag not in ("html", "body", "head", "p", "li", "td", "tr", "option"):
            b.errors.append((n.line, f"الوسم <{n.tag}> لم يُغلق."))
    return b.root, b.errors


# ---------------------------------------------------------------------------
# roles and names
# ---------------------------------------------------------------------------

def role_of(n: Node) -> str:
    explicit = n.attr("role").split()
    if explicit:
        return explicit[0]
    if n.tag == "input":
        return INPUT_ROLES.get(n.attr("type", "text").lower(), "textbox")
    if n.tag == "a" and "href" not in n.attrs:
        return ""
    if n.tag == "img" and n.attrs.get("alt") == "":
        return "presentation"
    if n.tag in ("section", "form") and not (n.attr("aria-label") or n.attr("aria-labelledby")):
        return "" if n.tag == "section" else "form"
    if n.tag in ("header", "footer") and _inside(n, ("article", "section", "aside", "main", "nav")):
        return ""
    return IMPLICIT_ROLES.get(n.tag, "")


def _inside(n: Node, tags) -> bool:
    p = n.parent
    while p is not None:
        if p.tag in tags:
            return True
        p = p.parent
    return False


def _by_id(root: Node) -> Dict[str, Node]:
    out = {}
    for n in root.iter():
        i = n.attr("id")
        if i and i not in out:
            out[i] = n
    return out


def _labels_for(root: Node) -> Dict[str, Node]:
    return {n.attr("for"): n for n in root.iter() if n.tag == "label" and n.attr("for")}


def accessible_name(n: Node, root: Node, ids=None, labels=None) -> str:
    ids = ids if ids is not None else _by_id(root)
    labels = labels if labels is not None else _labels_for(root)
    lb = n.attr("aria-labelledby")
    if lb:
        parts = [ids[i].text() for i in lb.split() if i in ids]
        if any(parts):
            return " ".join(p for p in parts if p)
    if n.attr("aria-label").strip():
        return n.attr("aria-label").strip()
    role = role_of(n)
    if n.tag == "img" or (n.tag == "input" and n.attr("type") == "image"):
        return n.attrs.get("alt", "").strip()
    if n.tag in ("input", "select", "textarea"):
        if n.attr("id") in labels:
            return labels[n.attr("id")].text()
        p = n.parent
        while p is not None:
            if p.tag == "label":
                return p.text()
            p = p.parent
        if n.tag == "input" and n.attr("type") in ("submit", "button", "reset"):
            return n.attr("value") or {"submit": "إرسال", "reset": "إعادة تعيين"}.get(n.attr("type"), "")
        return n.attr("title") or n.attr("placeholder")
    if n.tag in ("fieldset",):
        for c in n.children:
            if c.tag == "legend":
                return c.text()
    if n.tag == "table":
        for c in n.children:
            if c.tag == "caption":
                return c.text()
    if n.tag == "figure":
        for c in n.iter():
            if c.tag == "figcaption":
                return c.text()
    if role in NAME_FROM_CONTENT or n.tag in ("a", "button", "summary"):
        return n.text() or n.attr("title")
    return n.attr("title")


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    severity: str          # "error" | "warning"
    line: int
    message: str

    def spoken(self) -> str:
        kind = "خطأ" if self.severity == "error" else "تنبيه"
        return f"{kind} في السطر {self.line}: {self.message}"


_GENERIC_LINKS = {"اضغط هنا", "هنا", "المزيد", "اقرأ المزيد", "رابط", "click here",
                  "here", "more", "read more", "link"}


def audit(html: str) -> List[Issue]:
    root, parse_errors = parse(html)
    ids = _by_id(root)
    labels = _labels_for(root)
    issues = [Issue("error", ln, msg) for ln, msg in parse_errors]
    nodes = list(root.iter())
    tags = [n.tag for n in nodes]

    if "html" in tags:
        html_node = next(n for n in nodes if n.tag == "html")
        if not html_node.attr("lang"):
            issues.append(Issue("error", html_node.line,
                                "وسم <html> بلا سمة lang؛ لن يعرف قارئ الشاشة لغة الصفحة "
                                "فقد يقرؤها بنطق خاطئ. أضف lang=\"ar\" مثلًا."))
        elif html_node.attr("lang").lower().startswith("ar") and html_node.attr("dir").lower() != "rtl":
            issues.append(Issue("warning", html_node.line,
                                "الصفحة عربية بلا dir=\"rtl\"؛ سيظهر النصّ معكوس الاتجاه بصريًّا."))
    if "head" in tags or "html" in tags:
        titles = [n for n in nodes if n.tag == "title"]
        if not titles or not titles[0].text():
            issues.append(Issue("error", 1, "لا يوجد عنوان للصفحة <title>؛ وهو أول ما ينطقه "
                                            "قارئ الشاشة عند فتحها."))

    # headings
    last = 0
    h1s = 0
    for n in nodes:
        if n.tag in ("h1", "h2", "h3", "h4", "h5", "h6") or (role_of(n) == "heading"):
            level = int(n.tag[1]) if n.tag[0] == "h" and n.tag[1:].isdigit() else \
                int(n.attr("aria-level") or 2)
            if level == 1:
                h1s += 1
            if not n.text():
                issues.append(Issue("error", n.line, f"عنوان من المستوى {level} فارغ."))
            if last and level > last + 1:
                issues.append(Issue("warning", n.line,
                                    f"قفزة في مستويات العناوين: من {last} إلى {level} "
                                    f"دون المستوى {last + 1}. من يتنقّل بالعناوين سيظنّ أنّ "
                                    f"قسمًا مفقود."))
            last = level
    if any(n.tag == "body" for n in nodes) or len(nodes) > 5:
        if h1s == 0:
            issues.append(Issue("warning", 1, "لا يوجد عنوان رئيسي <h1>."))
        elif h1s > 1:
            issues.append(Issue("warning", 1, f"في الصفحة {h1s} عناوين من المستوى الأول؛ "
                                              f"الأفضل عنوان رئيسي واحد."))

    seen_ids: Dict[str, int] = {}
    for n in nodes:
        i = n.attr("id")
        if i:
            if i in seen_ids:
                issues.append(Issue("error", n.line, f"المعرّف id=\"{i}\" مكرّر "
                                                     f"(ظهر أولًا في السطر {seen_ids[i]})."))
            else:
                seen_ids[i] = n.line
        for ref_attr in ("aria-labelledby", "aria-describedby", "aria-controls"):
            for ref in n.attr(ref_attr).split():
                if ref not in ids:
                    issues.append(Issue("error", n.line,
                                        f"{ref_attr} يشير إلى id=\"{ref}\" غير موجود."))
        role = role_of(n)
        name = accessible_name(n, root, ids, labels)

        if n.tag == "img" and "alt" not in n.attrs and n.attr("role") not in ("presentation", "none"):
            src = n.attr("src") or "بلا مصدر"
            issues.append(Issue("error", n.line,
                                f"صورة ({src}) بلا نصّ بديل alt. إن كانت للزينة فاكتب alt=\"\"، "
                                f"وإلا فصِف محتواها."))
        elif n.tag == "img" and n.attrs.get("alt", "").lower().endswith((".jpg", ".png", ".gif", ".jpeg", ".webp")):
            issues.append(Issue("warning", n.line, "النصّ البديل للصورة اسم ملفّ؛ صِف الصورة بدلًا منه."))

        if n.tag == "a" and "href" in n.attrs:
            if not name:
                issues.append(Issue("error", n.line, "رابط بلا اسم؛ سيُنطق رابط فقط أو عنوانه."))
            elif name.strip().lower() in _GENERIC_LINKS:
                issues.append(Issue("warning", n.line,
                                    f"نصّ الرابط {name} لا يوضّح وجهته عند سماعه وحده في قائمة الروابط."))
        if role == "button" and not name:
            issues.append(Issue("error", n.line, "زرّ بلا اسم؛ أضف نصًّا أو aria-label."))
        if n.tag in ("input", "select", "textarea") and role not in ("", "button") \
                and n.attr("type") != "hidden" and not name:
            issues.append(Issue("error", n.line,
                                f"حقل {ROLE_NAMES.get(role, n.tag)} بلا تسمية؛ اربطه بـ <label for> "
                                f"أو أعطه aria-label. العنصر النائب placeholder لا يكفي وحده."))
        elif n.tag in ("input", "select", "textarea") and name and \
                name == n.attr("placeholder") and not n.attr("aria-label"):
            issues.append(Issue("warning", n.line,
                                "الحقل يعتمد على placeholder وحده للتسمية؛ يختفي عند الكتابة "
                                "ولا تقرؤه كلّ القارئات. أضف label."))
        if n.tag == "table" and role == "table":
            if not any(c.tag == "th" for c in n.iter()):
                issues.append(Issue("warning", n.line, "جدول بلا خلايا رؤوس <th>؛ لن يعلن قارئ "
                                                       "الشاشة رأس العمود عند التنقّل بين الخلايا."))
        if n.attr("tabindex").lstrip("-").isdigit() and int(n.attr("tabindex")) > 0:
            issues.append(Issue("warning", n.line,
                                "tabindex أكبر من صفر يغيّر ترتيب التنقّل بـ Tab؛ استخدم 0 أو -1."))
        if n.attr("onclick") and n.tag in ("div", "span") and role not in ("button", "link"):
            issues.append(Issue("error", n.line,
                                f"<{n.tag}> قابل للنقر بلا دور؛ لا يصل إليه من يستخدم لوحة المفاتيح. "
                                f"استخدم <button>."))
        if n.tag in ("b", "i", "font", "center", "marquee", "blink"):
            issues.append(Issue("warning", n.line,
                                f"الوسم <{n.tag}> شكلي فقط؛ استخدم <strong> أو <em> أو CSS."))
        if n.attr("aria-hidden") == "true" and _focusable(n):
            issues.append(Issue("error", n.line, "عنصر مخفيّ عن قارئ الشاشة لكنه قابل للتركيز."))

    if any(n.tag == "body" for n in nodes) and not any(role_of(n) == "main" for n in nodes):
        issues.append(Issue("warning", 1, "لا توجد منطقة <main>؛ لن يقفز المستخدم إلى المحتوى "
                                          "الرئيسي مباشرة."))
    issues.sort(key=lambda i: (i.line, i.severity != "error"))
    return issues


def _focusable(n: Node) -> bool:
    if n.tag in ("a",) and "href" in n.attrs:
        return True
    if n.tag in ("button", "input", "select", "textarea") and "disabled" not in n.attrs:
        return True
    return n.attr("tabindex") not in ("", "-1")


# ---------------------------------------------------------------------------
# accessibility tree
# ---------------------------------------------------------------------------

@dataclass
class AxNode:
    role: str
    name: str
    states: List[str]
    depth: int
    line: int
    level: int = 0
    children: List["AxNode"] = field(default_factory=list)

    def spoken(self) -> str:
        parts = []
        if self.name:
            parts.append(self.name)
        rn = ROLE_NAMES.get(self.role, self.role)
        if rn:
            parts.append(rn)
        if self.level:
            parts.append(f"المستوى {self.level}")
        parts += self.states
        return "، ".join(parts) or "نصّ"


def _states(n: Node, role: str) -> List[str]:
    out = []
    if n.tag == "input" and n.attr("type") in ("checkbox", "radio"):
        out.append("محدّد" if "checked" in n.attrs else "غير محدّد")
    if n.attr("aria-checked") in ("true", "false"):
        out.append("محدّد" if n.attr("aria-checked") == "true" else "غير محدّد")
    if n.attr("aria-expanded") in ("true", "false"):
        out.append("موسّع" if n.attr("aria-expanded") == "true" else "مطويّ")
    if "required" in n.attrs or n.attr("aria-required") == "true":
        out.append("مطلوب")
    if "disabled" in n.attrs or n.attr("aria-disabled") == "true":
        out.append("غير متاح")
    if n.attr("aria-invalid") == "true":
        out.append("غير صالح")
    if n.attr("aria-current"):
        out.append("الحالي")
    if role in ("textbox", "searchbox") and n.attr("value"):
        out.append(f"القيمة {n.attr('value')}")
    return out


def accessibility_tree(html: str) -> List[AxNode]:
    root, _ = parse(html)
    ids = _by_id(root)
    labels = _labels_for(root)
    out: List[AxNode] = []

    def walk(n: Node, depth: int, into: List[AxNode]):
        if n.tag in ("head", "script", "style", "template", "title", "meta", "link"):
            return
        if n.attr("aria-hidden") == "true" or "hidden" in n.attrs:
            return
        role = role_of(n)
        if role in ("presentation", "none"):
            role = ""
        if role:
            level = 0
            if role == "heading":
                level = int(n.tag[1]) if n.tag[:1] == "h" and n.tag[1:].isdigit() else \
                    int(n.attr("aria-level") or 2)
            ax = AxNode(role, accessible_name(n, root, ids, labels), _states(n, role),
                        depth, n.line, level)
            into.append(ax)
            if role in NAME_FROM_CONTENT or role in ("img", "textbox", "searchbox",
                                                     "combobox", "slider", "spinbutton"):
                return               # content already spoken as the name
            target, d = ax.children, depth + 1
        else:
            target, d = into, depth
        for item in n.text_parts:
            if isinstance(item, Node):
                walk(item, d, target)
            else:
                t = " ".join(item.split())
                if t:
                    target.append(AxNode("text", t, [], d, n.line))

    walk(root, 0, out)
    return out


def flatten(tree: List[AxNode]) -> List[AxNode]:
    out = []
    for n in tree:
        out.append(n)
        out.extend(flatten(n.children))
    return out


def reading_order(html: str) -> List[str]:
    """What browse mode reads, line by line (containers are announced on
    entry, the way NVDA and JAWS say قائمة بها ٣ عناصر)."""
    lines = []
    for n in flatten(accessibility_tree(html)):
        if n.role == "text":
            lines.append(n.name)
        elif n.role == "list":
            items = sum(1 for c in n.children if c.role == "listitem")
            lines.append(f"قائمة بها {items} عناصر")
        elif n.role in LANDMARK_ROLES:
            lines.append(f"{ROLE_NAMES.get(n.role, n.role)}{('، ' + n.name) if n.name else ''}")
        elif n.role in ("row", "rowgroup", "group") and not n.name:
            continue
        else:
            lines.append(n.spoken())
    return lines


def headings(html: str) -> List[str]:
    return [f"{n.name or '(فارغ)'}، المستوى {n.level}"
            for n in flatten(accessibility_tree(html)) if n.role == "heading"]


def landmarks(html: str) -> List[str]:
    return [f"{ROLE_NAMES.get(n.role, n.role)}{('، ' + n.name) if n.name else ''}"
            for n in flatten(accessibility_tree(html)) if n.role in LANDMARK_ROLES]


def links(html: str) -> List[str]:
    return [n.name or "(بلا اسم)" for n in flatten(accessibility_tree(html)) if n.role == "link"]


def form_fields(html: str) -> List[str]:
    roles = {"textbox", "searchbox", "checkbox", "radio", "combobox", "slider",
             "spinbutton", "button", "switch"}
    return [n.spoken() for n in flatten(accessibility_tree(html)) if n.role in roles]


STARTER_PAGE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <title>صفحتي الأولى</title>
</head>
<body>
  <header>
    <h1>مرحبًا بكم</h1>
    <nav aria-label="القائمة الرئيسية">
      <ul>
        <li><a href="#about">من نحن</a></li>
        <li><a href="#contact">اتصل بنا</a></li>
      </ul>
    </nav>
  </header>
  <main>
    <h2 id="about">من نحن</h2>
    <p>نحن طلاب نتعلّم كتابة صفحات يصل إليها الجميع.</p>
    <h2 id="contact">اتصل بنا</h2>
    <form>
      <label for="name">الاسم</label>
      <input id="name" type="text" required>
      <button type="submit">أرسل</button>
    </form>
  </main>
  <footer><p>جميع الحقوق محفوظة</p></footer>
</body>
</html>
"""

LESSONS = (
    ("عنوان الصفحة ولغتها",
     "أول ما يسمعه مستخدم قارئ الشاشة هو عنوان الصفحة <title>. والسمة lang في وسم <html> "
     "تخبر القارئ بأيّ لغة ينطق، وdir=\"rtl\" تجعل اتجاه النصّ العربيّ صحيحًا."),
    ("العناوين المتدرّجة",
     "يتنقّل المكفوفون بين العناوين بالمفتاح H، ومستوياتها (h1 إلى h6) تعطي فهرسًا للصفحة. "
     "لا تقفز من h1 إلى h3، واجعل للصفحة عنوانًا رئيسيًّا واحدًا."),
    ("النصّ البديل للصور",
     "السمة alt تقول ما في الصورة. صورة الزينة تأخذ alt=\"\" فيتجاهلها القارئ، وصورة المحتوى "
     "توصَف وصفًا قصيرًا مفيدًا."),
    ("الروابط والأزرار",
     "الرابط يأخذ المستخدم إلى مكان، والزرّ ينفّذ أمرًا. اجعل نصّ الرابط يدلّ على وجهته، "
     "فعبارة اضغط هنا لا تعني شيئًا في قائمة الروابط."),
    ("تسمية الحقول",
     "كلّ حقل يحتاج <label for=\"المعرّف\"> مرتبطًا بسمة id للحقل. النصّ النائب placeholder "
     "يختفي عند الكتابة فلا يصلح تسمية."),
    ("المعالم",
     "<header> و<nav> و<main> و<footer> تصبح معالم يقفز إليها المستخدم مباشرة (المفتاح D "
     "في NVDA). سمِّ القوائم المتعدّدة بـ aria-label."),
    ("الجداول",
     "الجدول البياني يحتاج رؤوسًا <th> وعنوانًا <caption>، فيعلن القارئ رأس العمود كلّما "
     "انتقلت بين الخلايا."),
)
