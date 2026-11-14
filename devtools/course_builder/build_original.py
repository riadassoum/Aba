import json, sys, io, contextlib, copy
sys.path.insert(0, sys.argv[1])
from original_challenges import TRACKS, OUT, FUNC, CLASS
tracks = {k: {"id": k, "title": t, "challenges": []} for k, t in TRACKS}
def run(src):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(src, "<ref>", "exec"), {"__name__": "__main__"})
    return buf.getvalue().strip()
n = 0
for track, cid, title, prompt, hint, ref in OUT:
    tracks[track]["challenges"].append({"cid": "o_" + cid, "title": title, "prompt": prompt, "hint": hint,
        "starter": "", "check": {"kind": "output", "expect": run(ref)}, "topic": track, "source": "aba"}); n += 1
for track, cid, title, prompt, hint, fn, ref, inputs in FUNC:
    ns = {}; exec(ref, ns)
    cases = [[a, ns[fn](*copy.deepcopy(a))] for a in inputs]
    import re
    sig = re.search(re.escape(fn) + r"\(([^)]*)\)", prompt)
    tracks[track]["challenges"].append({"cid": "o_" + cid, "title": title, "prompt": prompt, "hint": hint,
        "starter": f"def {fn}({sig.group(1) if sig else ''}):\n    pass\n", "check": {"kind": "func", "name": fn, "cases": cases},
        "topic": track, "source": "aba"}); n += 1
for track, cid, title, prompt, hint, ref, test in CLASS:
    tracks[track]["challenges"].append({"cid": "o_" + cid, "title": title, "prompt": prompt, "hint": hint,
        "starter": "", "check": {"kind": "script", "test": test, "expect": run(ref + "\n" + test)}, "topic": track, "source": "aba"}); n += 1
json.dump({"source": "Original challenges written for ABA.", "tracks": [tracks[k] for k, _ in TRACKS]},
          open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(n, {k: len(v["challenges"]) for k, v in tracks.items()})
