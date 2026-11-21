# -*- coding: utf-8 -*-
"""
Build abaAcademy/resources/verbs/<lang>.json for French, Spanish and Italian
from the verb lists and conjugation templates of verbecc by Brett Tolbert
(LGPL-3.0, https://github.com/bretttolbert/verbecc), themselves based on
Verbiste by Pierre Sarrazin (GPL-2.0-or-later). The XML is only read.

Output: {"templates": {name: {"Mood/tense": [[form, ...] per person]}},
         "verbs": [[infinitive, template, english, frequency], ...]}

Usage: python3 build_verbs.py VERBECC_XML_DIR OUT_DIR
"""

import json
import os
import sys
import xml.etree.ElementTree as ET


def main(src, out):
    os.makedirs(out, exist_ok=True)
    for lang in ("fr", "es", "it"):
        root = ET.parse(os.path.join(src, "conjugations", f"conjugations-{lang}.xml")).getroot()
        templates = {}
        for t in root.findall("template"):
            table = {}
            for mood in t:
                for tense in mood:
                    table[f"{mood.tag}/{tense.tag}"] = [[(i.text or "") for i in p.findall("i")] for p in tense.findall("p")]
            templates[t.get("name")] = table
        verbs = []
        vroot = ET.parse(os.path.join(src, "verbs", f"verbs-{lang}.xml")).getroot()
        for v in vroot.findall("v"):
            inf = (v.findtext("i") or "").strip()
            tpl = (v.findtext("t") or "").strip()
            if inf and tpl in templates:
                verbs.append([inf, tpl, (v.findtext("en") or "").strip()])
        # how often each verb's forms occur in the academy's sentence bank,
        # so drills start with the verbs a learner meets most
        counts = {}
        sent = os.path.join(out, "..", "sentences", f"{lang}.tsv")
        if os.path.exists(sent):
            import re
            from collections import Counter
            tok = Counter()
            for line in open(sent, encoding="utf-8"):
                tok.update(re.findall(r"[\w']+", line.split("\t")[0].lower()))
            vforms, owners = {}, Counter()
            for v in verbs:
                inf, tpl = v[0], v[1]
                suffix = tpl.split(":", 1)[1] if ":" in tpl else ""
                rad = inf[: len(inf) - len(suffix)] if suffix and inf.endswith(suffix) else inf
                vforms[inf] = {(rad + e).lower() for k, rows in templates[tpl].items() if "artici" not in k
                               for p in rows for e in p if e}
                owners.update(vforms[inf])
            for inf, forms in vforms.items():
                # a form two verbs share (suis: être, suivre) tells us nothing
                counts[inf] = sum(tok[f] for f in forms if owners[f] == 1)
            for v in verbs:
                v.append(counts.get(v[0], 0))
        with open(os.path.join(out, f"{lang}.json"), "w", encoding="utf-8") as f:
            json.dump({"source": "verbecc (LGPL-3.0) / Verbiste (GPL-2.0-or-later)",
                       "templates": templates, "verbs": verbs}, f, ensure_ascii=False, separators=(",", ":"))
        print(lang, len(templates), "templates", len(verbs), "verbs")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
