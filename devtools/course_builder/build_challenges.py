import json, os, sys, copy
SC = sys.argv[2] if len(sys.argv) > 2 else "work"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exercism_spec import SPECS, TRACKS

EX = SC + "/exercism"


def walk(c):
    for x in c.get("cases", []):
        if "cases" in x:
            yield from walk(x)
        else:
            yield x


def canon(slug):
    d = json.load(open(f"{EX}/{slug}.json"))
    cs = list(walk(d))
    replaced = {c["reimplements"] for c in cs if c.get("reimplements")}
    return [c for c in cs if c.get("uuid") not in replaced]


def to_args(spec, inp):
    if spec.get("optional_args"):
        return [inp[k] for k in spec["args"] if inp.get(k) is not None]
    if spec.get("key_dict"):
        return [inp["phrase"], inp["key"]["a"], inp["key"]["b"]]
    if spec.get("queen"):
        w, b = inp["white_queen"]["position"], inp["black_queen"]["position"]
        return [[w["row"], w["column"]], [b["row"], b["column"]]]
    return [inp[k] for k in spec["args"]]


import re as _re


def starter_from_prompt(spec):
    m = _re.search(_re.escape(spec["fn"]) + r"\(([^)]*)\)", spec["prompt"])
    if not m or not m.group(1).strip():
        return None
    return "def " + spec["fn"] + "(" + m.group(1) + "):\n    pass\n"


def norm(v, spec):
    if spec.get("round") and isinstance(v, (int, float)):
        return round(v, spec["round"])
    if spec.get("unordered") and isinstance(v, list):
        return sorted(json.dumps(x, sort_keys=True) for x in v)
    return v


out = {"source": "Exercism problem-specifications (MIT License, (c) Exercism); Arabic statements and reference solutions written for ABA.",
       "tracks": []}
tracks = {k: {"id": k, "title": t, "challenges": []} for k, t in TRACKS}
total_cases = 0
for spec in SPECS:
    cases = [c for c in canon(spec["slug"]) if c["property"] == spec["prop"]]
    ns = {}
    exec(spec["ref"], ns)
    fn = ns[spec["fn"]]
    good, bad = [], []
    for c in cases:
        exp = c["expected"]
        if isinstance(exp, dict) and "error" in exp:
            continue
        args = to_args(spec, c["input"])
        try:
            got = fn(*copy.deepcopy(args))
        except Exception as e:
            bad.append((c.get("description"), repr(e)))
            continue
        if norm(got, spec) == norm(exp, spec):
            good.append([args, exp])
        else:
            bad.append((c.get("description"), args, exp, got))
    if bad:
        print("MISMATCH", spec["fn"], len(bad), bad[:2])
    if len(good) < 2:
        print("TOO FEW", spec["fn"], len(good))
        continue
    total_cases += len(good)
    check = {"kind": "func", "name": spec["fn"], "cases": good}
    if spec.get("unordered"):
        check["unordered"] = True
    if spec.get("round"):
        check["round"] = spec["round"]
    tracks[spec["track"]]["challenges"].append({
        "cid": f"ex_{spec['fn']}", "title": spec["title"], "prompt": spec["prompt"], "hint": spec["hint"],
        "starter": starter_from_prompt(spec) or f"def {spec['fn']}({', '.join(['name=\"you\"'] if spec.get('optional_args') else (['text', 'a', 'b'] if spec.get('key_dict') else [a if a.isidentifier() and not any(ch.isupper() for ch in a) else ''.join('_' + ch.lower() if ch.isupper() else ch for ch in a) for a in spec['args']]))}):\n    pass\n",
        "check": check, "topic": spec["track"], "source": f"exercism:{spec['slug']}"})
out["tracks"] = [tracks[k] for k, _ in TRACKS]
dst = sys.argv[1]
os.makedirs(os.path.dirname(dst), exist_ok=True)
json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print({t["id"]: len(t["challenges"]) for t in out["tracks"]}, "cases", total_cases)
