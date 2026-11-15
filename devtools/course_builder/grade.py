"""Order a language's sentence pairs into graded lessons.

Words are taught in order of CEFR level (CEFR-J for English and, through
their English equivalents, for the other languages), then frequency; a
sentence is placed in the first lesson at which every word in it is known.
"""
import json, re, sys, collections

TOK = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.U)


def local_rules():
    """Optional selection rules kept outside the repository (local_rules.py
    beside these scripts)."""
    try:
        import local_rules as R
        return R
    except ImportError:
        return None


_DIGITS = re.compile(r"\d+")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def plausible(foreign, arabic):
    """Reject pairs whose translation is unlikely to match: wildly different
    lengths, or different numbers in the two sentences."""
    a, f = len(arabic.strip()), len(foreign.strip())
    if not a or not f or not (0.35 <= a / f <= 2.8):
        return False
    if sorted(_DIGITS.findall(foreign)) != sorted(_DIGITS.findall(arabic.translate(_AR_DIGITS))):
        return False
    return True


def load(S, c):
    rules = local_rules()
    pairs = [p for p in json.load(open(f"{S}/tatoeba/pairs_{c}.json", encoding="utf-8"))
             if (rules is None or not rules.blocked(c, p["t"], p["ar"])) and plausible(p["t"], p["ar"])]
    freq = json.load(open(f"{S}/tatoeba/freq_{c}.json", encoding="utf-8"))
    lex = json.load(open(f"{S}/wikt/lex_{c}.json", encoding="utf-8"))
    return pairs, freq, lex


NAMES = {"tom", "mary", "john", "alice", "ken", "jack", "bob", "mike", "tony", "jim", "marie", "maria",
         "tomás", "tomu", "tom'un", "boston", "tokyo", "london", "paris", "japan", "jane", "lucy",
         "bill", "taro", "dan", "linda", "emily", "david", "mennad", "baya", "sami", "layla", "ziri",
         "yanni", "skura", "rima", "mari", "tomun", "tomla", "tom'a", "tom'u", "tom'la", "tom'dan",
         "mary'nin", "mary'ye", "mary'yi", "tom'dan", "toma", "toms", "marias", "marys", "tomás"}


def norm(c, w):
    return w.lower()


def is_name(w):
    lw = w.lower()
    if lw in NAMES:
        return True
    base = re.split(r"['’]", lw)[0]
    return base in NAMES


def grade(c, pairs, freq, lex, per_lesson=10, max_vocab=4500, cap=30, min_sent=10, level_of=None):
    """Graded lessons. Words are taught in order of CEFR level, then frequency
    (``level_of(word)`` gives 0 for A1 … 5 for C2; without it, frequency only).
    A sentence enters the first lesson by which all of its words are known."""
    rank = {}
    for i, w in enumerate(freq):
        rank.setdefault(w.lower(), i)
    level_of = level_of or (lambda w: 0)
    seen = set()
    items = []
    for p in pairs:
        t = p["t"].strip()
        if t in seen or len(t) > 140:
            continue
        seen.add(t)
        toks = [w for w in TOK.findall(t) if not is_name(w)]
        if not toks:
            continue
        forms = {w.lower() for w in toks}
        items.append({"t": t, "ar": p["ar"], "forms": forms, "len": len(t)})
    occurring = collections.Counter(f for it in items for f in it["forms"])
    known_words = [w for w in occurring if rank.get(w, 10 ** 6) < 10 ** 6 and not is_name(w)]
    level = {w: level_of(w) for w in known_words}
    vocab = sorted(known_words, key=lambda w: (level[w], rank[w]))[:max_vocab]
    in_vocab = set(vocab)
    # each sentence waits for its unknown words
    waiting = {}
    by_word = collections.defaultdict(list)
    for idx, it in enumerate(items):
        if not it["forms"] <= in_vocab:
            continue
        waiting[idx] = len(it["forms"])
        for f in it["forms"]:
            by_word[f].append(idx)
    used = set()
    lessons, pending, new_words, new_levels = [], [], [], []
    for k, w in enumerate(vocab):
        new_words.append(w)
        new_levels.append(level[w])
        for idx in by_word.get(w, ()):
            waiting[idx] -= 1
            if waiting[idx] == 0:
                pending.append(idx)
        last = k == len(vocab) - 1
        if len(new_words) >= per_lesson and (len(pending) >= min_sent or len(new_words) >= 3 * per_lesson) or last:
            fresh = set(new_words)
            pending.sort(key=lambda x: (-len(items[x]["forms"] & fresh), items[x]["len"]))
            take, rest = pending[:cap], pending[cap:]
            used.update(take)
            lv = collections.Counter(new_levels).most_common(1)[0][0]
            lessons.append({"new": new_words, "level": lv, "vocab_end": k + 1,
                            "sentences": [{"t": items[x]["t"], "ar": items[x]["ar"]} for x in take]})
            pending = rest[: cap * 3]
            new_words, new_levels = [], []
    tail = [idx for idx in range(len(items)) if idx not in used]
    tail.sort(key=lambda x: (max(rank.get(f, 10 ** 6) for f in items[x]["forms"]), items[x]["len"]))
    reading = []
    for j in range(0, len(tail), cap):
        chunk = [items[x] for x in tail[j:j + cap]]
        unknown = []
        for it in chunk:
            for f in sorted(it["forms"], key=lambda f: -rank.get(f, 10 ** 6)):
                if f not in in_vocab and f not in unknown:
                    unknown.append(f)
        reading.append({"new": unknown[:20], "sentences": [{"t": it["t"], "ar": it["ar"]} for it in chunk]})
    return lessons, reading, vocab


if __name__ == "__main__":
    S = sys.argv[1]
    for c in sys.argv[2:]:
        pairs, freq, lex = load(S, c)
        lessons, reading, vocab = grade(c, pairs, freq, lex)
        ns = [len(l["sentences"]) for l in lessons]
        print(c, "lessons", len(lessons), "reading", len(reading), "vocab", len(vocab),
              "sentences in graded", sum(ns), "min/avg", min(ns), sum(ns) // len(ns),
              "lexicon cover of vocab", sum(1 for w in vocab if w in lex) / len(vocab))
        print("  L1", lessons[0]["new"], lessons[0]["sentences"][:3])
        print("  L50", lessons[50]["new"][:10], lessons[50]["sentences"][:2])
