# -*- coding: utf-8 -*-
"""
abaAcademy.quran_morph
======================

صرف القرآن كلمة كلمة — the morphology of every word of the Qur'an: its parts
(prefixes, stem, suffixes), part of speech, root, lemma, case or mood,
tense, person, gender and number, and verb form. With a root index: every
place a root occurs, and how often.

Data: the Quranic Arabic Corpus morphology v0.4 (corpus.quran.com, GPL) in
the revised Arabic-script edition by mustafa0x
(https://github.com/mustafa0x/quran-morphology), with its table of Arabic
grammatical terms. Read as it is; nothing is inferred.
"""

from __future__ import annotations

import json
import os
import random
import re
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
QURAN = os.path.join(HERE, "resources", "quran")
HARAKAT = re.compile("[ً-ْٰۖ-ۭ]")

PERSON = {"1": "للمتكلّم", "2": "للمخاطب", "3": "للغائب"}
GENDER = {"M": "مذكّر", "F": "مؤنّث"}
NUMBER = {"S": "مفرد", "D": "مثنّى", "P": "جمع"}


def plain(s: str) -> str:
    """Spoken spelling: the dagger alif as a plain alif, no tatweel or marks."""
    from .tajweed import bare
    return bare(s.replace("\u0640", ""))


@dataclass
class Segment:
    text: str
    tag: str
    feats: List[str]

    def get(self, key: str) -> str:
        for f in self.feats:
            if f.startswith(key + ":"):
                return f[len(key) + 1:]
        return ""


@dataclass
class Word:
    surah: int
    ayah: int
    index: int
    segments: List[Segment] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.segments)

    @property
    def stem(self) -> Optional[Segment]:
        for s in self.segments:
            if "PREF" not in s.feats and "SUFF" not in s.feats:
                return s
        return self.segments[0] if self.segments else None

    @property
    def root(self) -> str:
        for s in self.segments:
            r = s.get("ROOT")
            if r:
                return r
        return ""


class Morphology:
    _inst = None

    def __init__(self):
        with open(os.path.join(QURAN, "morphology-terms-ar.json"), encoding="utf-8") as f:
            self.terms = json.load(f)
        self.words: "OrderedDict[Tuple[int, int, int], Word]" = OrderedDict()
        self.by_ayah: Dict[Tuple[int, int], List[Word]] = defaultdict(list)
        self.by_root: Dict[str, List[Word]] = defaultdict(list)
        path = os.path.join(QURAN, "morphology.txt")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    p = line.rstrip("\n").split("\t")
                    if len(p) != 4 or not p[0][:1].isdigit():
                        continue
                    s, a, w, _ = (int(x) for x in p[0].split(":"))
                    key = (s, a, w)
                    word = self.words.get(key)
                    if word is None:
                        word = self.words[key] = Word(s, a, w)
                        self.by_ayah[(s, a)].append(word)
                    word.segments.append(Segment(p[1], p[2], p[3].split("|")))
        for word in self.words.values():
            if word.root:
                self.by_root[word.root].append(word)
        with open(os.path.join(QURAN, "quran_data.json"), encoding="utf-8") as f:
            self.surahs = json.load(f)["surahs"]

    @classmethod
    def get(cls) -> "Morphology":
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst

    def surah_name(self, n: int) -> str:
        name = plain(self.surahs[n - 1]["name"])
        return name[5:] if name.startswith("سورة ") else name

    # -- describing ---------------------------------------------------------------

    def _pgn(self, code: str) -> str:
        """3MS -> للغائب، مذكّر، مفرد"""
        out = []
        for ch in code:
            if ch in PERSON:
                out.append(PERSON[ch])
            elif ch in GENDER:
                out.append(GENDER[ch])
            elif ch in NUMBER:
                out.append(NUMBER[ch])
        return "، ".join(out)

    def describe_segment(self, seg: Segment) -> str:
        t = self.terms
        feats = seg.feats
        if seg.tag == "P" or "PREF" in feats:
            for f in feats:
                if f in t["particles"]:
                    return f"{seg.text}: {t['particles'][f]}"
            if "DET" in feats:
                return f"{seg.text}: أل التعريف"
            return f"{seg.text}: سابقة"
        if "SUFF" in feats and "PRON" in feats:
            code = next((f for f in feats if re.fullmatch("[123]?[MF]?[SDP]", f)), "")
            return f"{seg.text}: ضمير متّصل" + (f" ({self._pgn(code)})" if code else "")
        parts = []
        kind = None
        for f in feats:
            if f in t["types"] and f not in ("N", "V"):
                kind = t["types"][f]
        if seg.tag == "V":
            tense = next((t["verb_tenses"][f] for f in feats if f in t["verb_tenses"]), "")
            parts.append("فعل " + tense if tense else "فعل")
            if "PASS" in feats:
                parts.append("مبنيّ للمجهول")
            vf = seg.get("VF")
            if vf.isdigit() and 1 <= int(vf) <= len(t["verb_forms_tri"]):
                parts.append("على وزن " + t["verb_forms_tri"][int(vf) - 1])
            mood = seg.get("MOOD")
            if mood in t["verb_grammar"]:
                parts.append(t["verb_grammar"][mood])
            code = next((f for f in feats if re.fullmatch("[123][MF]?[SDP]", f)), "")
            if code:
                parts.append(self._pgn(code))
        elif seg.tag == "N":
            form = next((t["noun_forms"][f] for f in feats if f in t["noun_forms"]), "")
            parts.append(kind or form or "اسم")
            if form and kind:
                parts.append(form)
            if "ADJ" in feats:
                parts.append("صفة")
            case = next((t["noun_grammar"][f] for f in feats if f in t["noun_grammar"]), "")
            if case:
                parts.append(case)
            gn = next((f for f in feats if re.fullmatch("[MF][SDP]?|[SDP]", f)), "")
            if gn:
                parts.append(self._pgn(gn))
            if "INDEF" in feats:
                parts.append("نكرة")
        else:
            name = t["particles"].get(seg.tag) or t["types"].get(seg.tag) or seg.tag
            parts.append(name)
        fam = seg.get("FAM")
        if fam:
            parts.append(t["FAM"].get(plain(fam), t["FAM"].get(fam, "")) or "")
        lem = seg.get("LEM")
        text = f"{seg.text}: " + "، ".join(p for p in parts if p)
        if seg.get("ROOT"):
            text += f"، الجذر {' '.join(seg.get('ROOT'))}"
        if lem and plain(lem) != plain(seg.text):
            text += f"، وأصلها {lem}"
        return text

    def describe_word(self, word: Word) -> str:
        lines = [f"{plain(word.text)}:"]
        lines += [self.describe_segment(s) for s in word.segments]
        return "\n".join(lines)

    def root_report(self, root: str, limit: int = 40) -> str:
        r = plain(root).replace(" ", "")
        occ = self.by_root.get(r, [])
        if not occ:
            return f"لم يرد الجذر {root} في القرآن الكريم بهذا الرسم."
        lemmas: Dict[str, int] = {}
        for w in occ:
            lem = next((s.get("LEM") for s in w.segments if s.get("ROOT")), "")
            lemmas[lem] = lemmas.get(lem, 0) + 1
        surahs = sorted({w.surah for w in occ})
        lines = [f"ورد الجذر {' '.join(r)} {len(occ)} مرّة في {len(surahs)} سورة، بهذه الصيغ:"]
        lines.append("، ".join(f"{l} ({n})" for l, n in sorted(lemmas.items(), key=lambda x: -x[1])))
        lines.append("مواضعه الأولى:")
        for w in occ[:limit]:
            lines.append(f"{plain(w.text)}: سورة {self.surah_name(w.surah)} الآية {w.ayah}")
        return "\n".join(lines)


@dataclass
class Question:
    prompt: str
    options: List[str]
    answer: str
    explanation: str


def make_question(m: Morphology, kind: str = "root", surah: Optional[int] = None,
                  rng: Optional[random.Random] = None) -> Optional[Question]:
    rng = rng or random.Random()
    keys = [k for k in m.by_ayah if surah is None or k[0] == surah]
    roots = list(m.by_root)
    for _ in range(40):
        s, a = rng.choice(keys)
        words = [w for w in m.by_ayah[(s, a)] if w.root]
        if not words:
            continue
        w = rng.choice(words)
        context = " ".join(plain(x.text) for x in m.by_ayah[(s, a)])
        if kind == "root":
            right = " ".join(w.root)
            # near roots share letters, so the learner must really know it
            near = [r for r in roots if r != w.root and len(set(r) & set(w.root)) >= 2]
            rng.shuffle(near)
            far = [r for r in roots if r != w.root and r not in near]
            rng.shuffle(far)
            opts = [" ".join(r) for r in (near[:2] + far)[:3]] + [right]
            rng.shuffle(opts)
            return Question(f"سورة {m.surah_name(s)}، الآية {a}: {context}\nما جذر كلمة {plain(w.text)}؟",
                            opts, right, m.describe_word(w))
        if kind == "pos":
            stem = w.stem
            if stem is None:
                continue
            right = {"V": "فعل", "N": "اسم"}.get(stem.tag)
            if not right:
                continue
            opts = ["اسم", "فعل", "حرف"]
            return Question(f"سورة {m.surah_name(s)}، الآية {a}: {context}\nما نوع كلمة {plain(w.text)}؟",
                            opts, right, m.describe_word(w))
    return None
