"""Sanity check of page predictions before spending GPU time on the long runs.
    python check_preds.py experiments/paginas/base/smoke5.jsonl [...]
Fails (exit 1) only if the setup is broken: an empty prediction or one with no layout block.
Hitting the token limit or looping is reported but is a model behaviour, not a failure."""
import json, re, sys
bad = []
for path in sys.argv[1:]:
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        p = r["pred"]
        why = []
        if len(p.strip()) < 50: why.append("vazia")
        if "data-bbox" not in p: why.append("sem blocos")
        if r.get("fim") == "length": why.append("limite de tokens")
        chunks = re.findall(r".{40}", p)
        if chunks and max(chunks.count(c) for c in set(chunks)) >= 5: why.append("laço")
        print(f"{path}:{r['id']}: {r.get('tokens')} tokens, fim={r.get('fim')} {'OK' if not why else why}")
        if "vazia" in why or "sem blocos" in why: bad.append((r["id"], why))
sys.exit(1 if bad else 0)
