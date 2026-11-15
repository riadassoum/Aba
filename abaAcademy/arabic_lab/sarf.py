# -*- coding: utf-8 -*-
"""
abaAcademy.arabic_lab.sarf
==========================

مختبر الصرف — an Arabic morphology dictionary and trainer built on Arramooz,
the open Arabic dictionary by Taha Zerrouki (GPL-2.0): about 29,000 nouns
(with root, pattern, kind, the verb they derive from, gender, broken plural
and a definition) and about 8,000 triliteral verbs (with root, conjugation
class and transitivity).

What it offers:
* look a word up: every entry spelled the same way, with all its details;
* the family of a root: every noun and verb of that root;
* quizzes: the broken plural of a noun and the singular of a plural, the
  masdar of a verb, its active participle, the present tense of a sound
  triliteral verb from its class (bab), and whether a verb is transitive.

Quiz words are taken from the more frequent part of the dictionary, and a
question is only asked when its answer is unambiguous in the data.
"""

from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "resources", "arabic", "sarf.json")

HARAKAT = re.compile("[ً-ْٰ]")
FATHA, DAMMA, KASRA, SUKUN = "َ", "ُ", "ِ", "ْ"

# the six conjugation classes of the triliteral verb: past and present vowel
# on the middle radical, with the verb that names each class
BABS = {
    1: ("فَعَلَ يَفْعُلُ", FATHA, DAMMA, "نَصَرَ يَنْصُرُ"),
    2: ("فَعَلَ يَفْعِلُ", FATHA, KASRA, "ضَرَبَ يَضْرِبُ"),
    3: ("فَعَلَ يَفْعَلُ", FATHA, FATHA, "فَتَحَ يَفْتَحُ"),
    4: ("فَعِلَ يَفْعَلُ", KASRA, FATHA, "عَلِمَ يَعْلَمُ"),
    5: ("فَعُلَ يَفْعُلُ", DAMMA, DAMMA, "كَرُمَ يَكْرُمُ"),
    6: ("فَعِلَ يَفْعِلُ", KASRA, KASRA, "حَسِبَ يَحْسِبُ"),
}
WEAK = set("اويىءأإؤئآة")


def plain(s: str) -> str:
    return HARAKAT.sub("", s or "")


def bare_ending(s: str) -> str:
    """The word without its case ending, as it is said in isolation."""
    return re.sub("[ًٌٍُ]$", "", s or "")


class Sarf:
    _inst = None

    def __init__(self, path: str = DATA):
        self.words: List[dict] = []
        self.verbs: List[dict] = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            self.words, self.verbs = d["words"], d["verbs"]
        self.by_plain: Dict[str, List[dict]] = {}
        self.by_root: Dict[str, List[dict]] = {}
        for w in self.words:
            self.by_plain.setdefault(w["u"], []).append(w)
            if w.get("root"):
                self.by_root.setdefault(w["root"], []).append(w)
        self.verbs_by_plain: Dict[str, List[dict]] = {}
        self.verbs_by_root: Dict[str, List[dict]] = {}
        for v in self.verbs:
            self.verbs_by_plain.setdefault(plain(v["v"]), []).append(v)
            self.verbs_by_root.setdefault(v["root"], []).append(v)

    @classmethod
    def get(cls) -> "Sarf":
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst

    # -- lookup ------------------------------------------------------------------

    @staticmethod
    def describe(w: dict) -> str:
        parts = [bare_ending(w["w"]) + ": " + w["kind"]]
        if w.get("root"):
            parts.append("الجذر " + " ".join(w["root"]))
        if w.get("wazn"):
            parts.append("الوزن " + bare_ending(w["wazn"]))
        if w.get("origin"):
            parts.append("من الفعل " + w["origin"])
        if w.get("gender"):
            parts.append(w["gender"])
        if w.get("plural"):
            parts.append("الجمع " + " أو ".join(bare_ending(p) for p in w["plural"]))
        if w.get("singular"):
            parts.append("مفرده " + bare_ending(w["singular"]))
        text = "، ".join(parts) + "."
        if w.get("def"):
            text += "\nالمعنى: " + w["def"]
        return text

    @staticmethod
    def describe_verb(v: dict) -> str:
        name, _, _, model = BABS.get(v["bab"], ("", "", "", ""))
        text = f"{v['v']}: فعل ثلاثي، الجذر {' '.join(v['root'])}، من باب {name} مثل {model}"
        if v.get("trans"):
            text += f"، {v['trans']}"
        pres = present_tense(v)
        if pres:
            text += f"، ومضارعه {pres}"
        return text + "."

    def lookup(self, text: str) -> List[str]:
        key = plain(text.strip())
        out = [self.describe_verb(v) for v in self.verbs_by_plain.get(key, [])]
        out += [self.describe(w) for w in self.by_plain.get(key, [])]
        if not out and key.startswith("ال"):
            return self.lookup(key[2:])
        return out

    def root_family(self, root: str) -> List[str]:
        r = plain(root).replace(" ", "")
        out = [f"{v['v']} (فعل)" for v in self.verbs_by_root.get(r, [])]
        out += [f"{bare_ending(w['w'])} ({w['kind']})" for w in self.by_root.get(r, [])]
        return out


def present_tense(v: dict) -> str:
    """يَفْعُلُ and the rest, for a sound triliteral verb whose written past
    vowel agrees with its class. Weak, hamzated and doubled verbs return ''."""
    letters = plain(v["v"])
    if len(letters) != 3 or any(c in WEAK for c in letters) or "ّ" in v["v"]:
        return ""
    bab = BABS.get(v["bab"])
    if not bab:
        return ""
    _, past_v, pres_v, _ = bab
    m = re.fullmatch(f"(.){FATHA}(.)([{FATHA}{DAMMA}{KASRA}])(.){FATHA}", v["v"])
    if not m or m.group(3) != past_v:
        return ""
    c1, c2, c3 = m.group(1), m.group(2), m.group(4)
    return f"يَ{c1}{SUKUN}{c2}{pres_v}{c3}{DAMMA}"


@dataclass
class Question:
    prompt: str
    options: List[str]
    answer: str
    explanation: str


KINDS = [("plural", "جمع التكسير"), ("singular", "مفرد الجمع"), ("masdar", "مصدر الفعل"),
         ("fa3il", "اسم الفاعل"), ("present", "مضارع الفعل الثلاثي"), ("trans", "اللازم والمتعدّي")]


class Trainer:
    def __init__(self, sarf: Sarf, rng: Optional[random.Random] = None, top: int = 800, min_freq: int = 2000):
        self.s = sarf
        self.rng = rng or random.Random()
        common = sorted(sarf.words, key=lambda w: -w.get("f", 0))

        def unique(pred):
            out = []
            for w in common:
                if w.get("f", 0) < min_freq:
                    break
                if pred(w) and len(sarf.by_plain.get(w["u"], [])) and \
                        sum(1 for x in sarf.by_plain[w["u"]] if pred(x)) == 1:
                    out.append(w)
                if len(out) >= top:
                    break
            return out

        self.plurals = unique(lambda w: w.get("plural") and w.get("number") == "مفرد" and w["kind"] == "اسم جامد")
        self.masdars = unique(lambda w: w["kind"] == "مصدر" and w.get("origin") and HARAKAT.search(w["origin"]))
        self.fa3il = unique(lambda w: w["kind"] == "اسم فاعل" and w.get("origin") and w.get("gender") == "مذكر"
                            and HARAKAT.search(w["origin"]))
        verbs = [v for v in sorted(sarf.verbs, key=lambda v: -v.get("f", 0)) if v.get("f", 0) >= min_freq]
        once = {}
        for v in verbs:
            once.setdefault(v["v"], []).append(v)
        self.present = [v for v in verbs if len(once[v["v"]]) == 1 and present_tense(v)][:top]
        self.trans = [v for v in verbs if len(once[v["v"]]) == 1 and v.get("trans") in ("لازم", "متعدٍّ")][:top]

    def _wrong(self, pool, right, field, n=3):
        out = []
        cand = list(pool)
        self.rng.shuffle(cand)
        for w in cand:
            v = field(w)
            if v and v != right and v not in out:
                out.append(v)
            if len(out) == n:
                break
        return out

    def question(self, kind: Optional[str] = None) -> Optional[Question]:
        kind = kind or self.rng.choice([k for k, _ in KINDS])
        r = self.rng
        if kind == "plural" and self.plurals:
            w = r.choice(self.plurals)
            right = bare_ending(w["plural"][0])
            opts = self._wrong(self.plurals, right, lambda x: bare_ending(x["plural"][0])) + [right]
            r.shuffle(opts)
            return Question(f"ما جمع {bare_ending(w['w'])}؟", opts, right, self.s.describe(w).split("\n")[0])
        if kind == "singular" and self.plurals:
            w = r.choice(self.plurals)
            right = bare_ending(w["w"])
            opts = self._wrong(self.plurals, right, lambda x: bare_ending(x["w"])) + [right]
            r.shuffle(opts)
            return Question(f"ما مفرد {bare_ending(w['plural'][0])}؟", opts, right,
                            f"{bare_ending(w['plural'][0])} جمع {right}.")
        if kind == "masdar" and self.masdars:
            w = r.choice(self.masdars)
            right = bare_ending(w["w"])
            opts = self._wrong(self.masdars, right, lambda x: bare_ending(x["w"])) + [right]
            r.shuffle(opts)
            return Question(f"ما مصدر الفعل {w['origin']}؟", opts, right, f"مصدر {w['origin']}: {right}.")
        if kind == "fa3il" and self.fa3il:
            w = r.choice(self.fa3il)
            right = bare_ending(w["w"])
            opts = self._wrong(self.fa3il, right, lambda x: bare_ending(x["w"])) + [right]
            r.shuffle(opts)
            return Question(f"ما اسم الفاعل من {w['origin']}؟", opts, right, f"اسم الفاعل من {w['origin']}: {right}.")
        if kind == "present" and self.present:
            v = r.choice(self.present)
            right = present_tense(v)
            c1, c2, c3 = plain(v["v"])
            forms = {f"يَ{c1}{SUKUN}{c2}{x}{c3}{DAMMA}" for x in (FATHA, DAMMA, KASRA)}
            opts = sorted(forms)
            r.shuffle(opts)
            name, _, _, model = BABS[v["bab"]]
            return Question(f"ما مضارع {v['v']}؟", opts, right, f"{v['v']} {right}، من باب {name} مثل {model}.")
        if kind == "trans" and self.trans:
            v = r.choice(self.trans)
            right = v["trans"]
            return Question(f"هل الفعل {v['v']} لازم أم متعدٍّ؟", ["لازم", "متعدٍّ"], right,
                            f"{v['v']} {right}: " + ("يكتفي بفاعله." if right == "لازم" else "يحتاج إلى مفعول به."))
        return None
