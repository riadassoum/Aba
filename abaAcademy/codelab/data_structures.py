# -*- coding: utf-8 -*-
"""
abaAcademy.codelab.data_structures
==================================

A data-structures lab described in words. A sighted student sees boxes and
arrows on a whiteboard; here every operation on a stack, a queue, a linked
list or a binary search tree is narrated, and the structure can be read
back at any time (القمّة ٧، تحتها ٣، ثم ١). Each operation also reports
its cost in big-O terms, so the reason to choose one structure over another
is heard, not just stated.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Tuple

KINDS = {"stack": "المكدّس (Stack)", "queue": "الطابور (Queue)",
         "list": "القائمة المترابطة (Linked list)", "bst": "شجرة البحث الثنائية (BST)"}

OPERATIONS = {
    "stack": [("push", "ادفع عنصرًا (push)"), ("pop", "اسحب من القمّة (pop)"), ("peek", "انظر إلى القمّة")],
    "queue": [("enqueue", "أضف إلى الآخر (enqueue)"), ("dequeue", "أخرج من الأوّل (dequeue)"),
              ("peek", "انظر إلى الأوّل")],
    "list": [("append", "أضف في الآخر"), ("prepend", "أضف في البداية"), ("insert", "أدرج بعد موضع"),
             ("remove", "احذف قيمة"), ("find", "ابحث عن قيمة"), ("reverse", "اعكس القائمة")],
    "bst": [("insert", "أدرج قيمة"), ("find", "ابحث عن قيمة"), ("remove", "احذف قيمة"),
            ("inorder", "اعرض بالترتيب (in-order)"), ("preorder", "اعرض قبليًّا (pre-order)"),
            ("height", "ارتفاع الشجرة"), ("minmax", "أصغر قيمة وأكبرها")],
}


class Stack:
    def __init__(self):
        self.items: List[str] = []

    def do(self, op: str, value: str = "", pos: int = 0) -> str:
        if op == "push":
            self.items.append(value)
            return f"دُفع {value} إلى القمّة. الكلفة O(1)."
        if op == "pop":
            if not self.items:
                return "المكدّس فارغ؛ لا شيء يُسحب."
            v = self.items.pop()
            return f"سُحب {v} من القمّة. الكلفة O(1)."
        if op == "peek":
            return f"القمّة: {self.items[-1]}." if self.items else "المكدّس فارغ."
        raise ValueError(op)

    def read(self) -> str:
        if not self.items:
            return "المكدّس فارغ."
        parts = [f"القمّة {self.items[-1]}"] + [f"تحتها {x}" for x in reversed(self.items[:-1])]
        return "، ".join(parts) + f". عدد العناصر {len(self.items)}."


class Queue:
    def __init__(self):
        self.items = deque()

    def do(self, op: str, value: str = "", pos: int = 0) -> str:
        if op == "enqueue":
            self.items.append(value)
            return f"انضمّ {value} إلى آخر الطابور. الكلفة O(1)."
        if op == "dequeue":
            if not self.items:
                return "الطابور فارغ."
            v = self.items.popleft()
            return f"خرج {v} من أوّل الطابور. الكلفة O(1)."
        if op == "peek":
            return f"الأوّل: {self.items[0]}." if self.items else "الطابور فارغ."
        raise ValueError(op)

    def read(self) -> str:
        if not self.items:
            return "الطابور فارغ."
        return "من الأوّل إلى الآخر: " + "، ".join(self.items) + f". عدد العناصر {len(self.items)}."


@dataclass
class _Node:
    value: str
    next: Optional["_Node"] = None


class LinkedList:
    def __init__(self):
        self.head: Optional[_Node] = None

    def values(self) -> List[str]:
        out, n = [], self.head
        while n:
            out.append(n.value)
            n = n.next
        return out

    def do(self, op: str, value: str = "", pos: int = 0) -> str:
        if op == "prepend":
            self.head = _Node(value, self.head)
            return f"أُضيف {value} في البداية وصار الرأس. الكلفة O(1)."
        if op == "append":
            node = _Node(value)
            if not self.head:
                self.head = node
                return f"أُضيف {value} وصار الرأس. الكلفة O(1)."
            n, steps = self.head, 1
            while n.next:
                n = n.next
                steps += 1
            n.next = node
            return f"مشينا في القائمة حتى آخرها (عدد العقد {steps})، ثم ربطنا {value} بعدها. الكلفة O(n)."
        if op == "insert":
            if pos <= 0 or not self.head:
                return self.do("prepend", value)
            n, i = self.head, 1
            while n.next and i < pos:
                n = n.next
                i += 1
            n.next = _Node(value, n.next)
            return f"أُدرج {value} بعد العقدة {i} ({n.value}). الكلفة O(n) للوصول، وO(1) للربط."
        if op == "remove":
            prev, n, i = None, self.head, 1
            while n and n.value != value:
                prev, n, i = n, n.next, i + 1
            if not n:
                return f"لم أجد {value} في القائمة."
            if prev is None:
                self.head = n.next
            else:
                prev.next = n.next
            return f"حُذف {value} من الموضع {i}، ورُبط ما قبله بما بعده. الكلفة O(n)."
        if op == "find":
            n, i = self.head, 1
            while n:
                if n.value == value:
                    return f"وجدت {value} في الموضع {i}، وعدد العقد المفحوصة {i}. الكلفة O(n)."
                n, i = n.next, i + 1
            return f"لم أجد {value}، وعدد العقد المفحوصة {i - 1}. الكلفة O(n)."
        if op == "reverse":
            prev, n = None, self.head
            while n:
                n.next, prev, n = prev, n, n.next
            self.head = prev
            return "عُكست القائمة بتغيير اتجاه كلّ رابط. الكلفة O(n)."
        raise ValueError(op)

    def read(self) -> str:
        vals = self.values()
        if not vals:
            return "القائمة فارغة."
        return "الرأس " + " ← ".join(vals) + " ← لا شيء."


@dataclass
class _TNode:
    key: float
    label: str
    left: Optional["_TNode"] = None
    right: Optional["_TNode"] = None


def _num(value: str) -> float:
    try:
        return float(value.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
    except ValueError:
        raise ValueError("شجرة البحث هنا تأخذ أرقامًا.")


class BST:
    def __init__(self):
        self.root: Optional[_TNode] = None

    def do(self, op: str, value: str = "", pos: int = 0) -> str:
        if op == "insert":
            k = _num(value)
            path = []
            if self.root is None:
                self.root = _TNode(k, value)
                return f"صار {value} جذر الشجرة."
            n = self.root
            while True:
                if k == n.key:
                    return f"{value} موجود من قبل؛ لا تتكرّر القيم في شجرة البحث."
                go_left = k < n.key
                path.append(f"{'أصغر' if go_left else 'أكبر'} من {n.label} فنذهب {'يسارًا' if go_left else 'يمينًا'}")
                nxt = n.left if go_left else n.right
                if nxt is None:
                    if go_left:
                        n.left = _TNode(k, value)
                    else:
                        n.right = _TNode(k, value)
                    break
                n = nxt
            return f"{value}: " + "، ثم ".join(path) + f". أُدرج، وعدد المقارنات {len(path)}."
        if op == "find":
            k = _num(value)
            n, steps = self.root, 0
            while n:
                steps += 1
                if k == n.key:
                    return f"وجدت {value}، وعدد المقارنات {steps}."
                n = n.left if k < n.key else n.right
            return f"{value} غير موجود، وعدد المقارنات {steps}."
        if op == "remove":
            k = _num(value)
            self.root, removed = self._remove(self.root, k)
            return f"حُذف {value}." if removed else f"{value} غير موجود."
        if op == "inorder":
            vals = []
            self._walk(self.root, vals, "in")
            return "بالترتيب: " + "، ".join(vals) if vals else "الشجرة فارغة."
        if op == "preorder":
            vals = []
            self._walk(self.root, vals, "pre")
            return "قبليًّا: " + "، ".join(vals) if vals else "الشجرة فارغة."
        if op == "height":
            return f"ارتفاع الشجرة {self._height(self.root)}."
        if op == "minmax":
            if not self.root:
                return "الشجرة فارغة."
            a = self.root
            while a.left:
                a = a.left
            b = self.root
            while b.right:
                b = b.right
            return f"أصغر قيمة {a.label} (أقصى اليسار)، وأكبر قيمة {b.label} (أقصى اليمين)."
        raise ValueError(op)

    def _remove(self, n, k) -> Tuple[Optional[_TNode], bool]:
        if n is None:
            return None, False
        if k < n.key:
            n.left, r = self._remove(n.left, k)
            return n, r
        if k > n.key:
            n.right, r = self._remove(n.right, k)
            return n, r
        if n.left is None:
            return n.right, True
        if n.right is None:
            return n.left, True
        s = n.right
        while s.left:
            s = s.left
        n.key, n.label = s.key, s.label
        n.right, _ = self._remove(n.right, s.key)
        return n, True

    def _walk(self, n, out, order) -> None:
        if n is None:
            return
        if order == "pre":
            out.append(n.label)
        self._walk(n.left, out, order)
        if order == "in":
            out.append(n.label)
        self._walk(n.right, out, order)

    def _height(self, n) -> int:
        return 0 if n is None else 1 + max(self._height(n.left), self._height(n.right))

    def read(self) -> str:
        if not self.root:
            return "الشجرة فارغة."
        lines = []

        def go(n, depth, side):
            if n is None:
                return
            kids = []
            if n.left:
                kids.append(f"يساره {n.left.label}")
            if n.right:
                kids.append(f"يمينه {n.right.label}")
            where = "الجذر" if depth == 0 else f"{side} في المستوى {depth}"
            lines.append(f"{n.label} ({where})" + (": " + "، ".join(kids) if kids else ": ورقة"))
            go(n.left, depth + 1, "ابن أيسر")
            go(n.right, depth + 1, "ابن أيمن")
        go(self.root, 0, "")
        return ". ".join(lines) + "."


def make(kind: str):
    return {"stack": Stack, "queue": Queue, "list": LinkedList, "bst": BST}[kind]()
