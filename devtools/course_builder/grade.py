"""Order a language's sentence pairs into graded lessons.

Each lesson introduces the next most frequent word forms; a sentence is placed
in the first lesson at which every word in it is known.
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


def load(S, c):
    rules = local_rules()
    pairs = [p for p in json.load(open(f"{S}/tatoeba/pairs_{c}.json", encoding="utf-8"))
             if rules is None or not rules.blocked(c, p["t"], p["ar"])]
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


def grade(c, pairs, freq, lex, per_lesson=10, max_vocab=4500, cap=30, min_sent=10):
    rank = {}
    for i, w in enumerate(freq):
        rank.setdefault(w.lower(), i)
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
        r = max(rank.get(f, 10 ** 6) for f in forms)
        items.append((r, len(t), t, p["ar"], forms))
    items.sort(key=lambda x: (x[0], x[1]))
    # vocabulary: forms in rank order that actually occur in the sentences
    occurring = collections.Counter(f for it in items for f in it[4])
    vocab = [w for w in sorted(occurring, key=lambda f: rank.get(f, 10 ** 6))
             if rank.get(w, 10 ** 6) < 10 ** 6 and not is_name(w)][:max_vocab]
    lessons, pending, k, i = [], [], 0, 0
    new_words = []
    while k < len(vocab):
        chunk = vocab[k:k + per_lesson]
        k += per_lesson
        new_words += chunk
        bound = rank[vocab[k - 1]] if k <= len(vocab) else rank[vocab[-1]]
        while i < len(items) and items[i][0] <= bound:
            pending.append(items[i])
            i += 1
        if len(pending) >= min_sent or k >= len(vocab):
            pending.sort(key=lambda x: x[1])
            # prefer sentences that use the newest words
            fresh = set(new_words)
            pending.sort(key=lambda x: (-len(x[4] & fresh), x[1]))
            take, rest = pending[:cap], pending[cap:]
            lessons.append({"new": new_words,
                            "sentences": [{"t": x[2], "ar": x[3]} for x in take],
                            "vocab_end": k})
            # leftover easy sentences stay available for later lessons (spread out)
            pending = rest[: cap * 3]
            new_words = []
    tail = items[i:] + pending
    tail.sort(key=lambda x: (x[0], x[1]))
    reading = []
    for j in range(0, len(tail), cap):
        chunk = tail[j:j + cap]
        unknown = []
        for x in chunk:
            for f in sorted(x[4], key=lambda f: -rank.get(f, 10 ** 6)):
                if rank.get(f, 10 ** 6) >= (rank[vocab[-1]] if vocab else 0) and f not in unknown:
                    unknown.append(f)
        reading.append({"new": unknown[:20], "sentences": [{"t": x[2], "ar": x[3]} for x in chunk]})
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
