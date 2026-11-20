"""Write the bake-off job files (jobs/<generator>.jsonl) for the three generators.

Rows: the 12 test strings + 3 character probes. Columns: 4 styles per generator.
Graves also gets accent-folded copies of the rejected rows, a 13-style row and a
bias sweep; Emuru also gets one CPU timing job.
"""
import json
import os
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = [l.rstrip("\n") for l in open(os.path.join(HERE, "test_strings.txt"), encoding="utf-8") if l.strip()]
PROBES = [
    "á â ã à é ê í ó ô õ ú ü ç",
    "Á Ã É Í Ó Õ Ú Ç º / Q X Z",
    "0 1 2 3 4 5 6 7 8 9",
]
ROWS = TESTS + PROBES

COLUMNS = {
    "graves": [("unprimed", None), ("style3", 3), ("style7", 7), ("style9", 9)],
    "vatrpp": [("iam0", 0), ("iam7", 7), ("bressay_1631", "bressay_1631"), ("bressay_7574", "bressay_7574")],
    "emuru": [("bressay_1631", "bressay_1631"), ("bressay_7574", "bressay_7574"),
              ("bressay_0675", "bressay_0675"), ("graves_style3", "graves_style3")],
}


def fold(s):
    """Strip diacritics (what the project would send to Graves)."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def main():
    os.makedirs(os.path.join(HERE, "jobs"), exist_ok=True)
    for gen, cols in COLUMNS.items():
        jobs = []
        for col, style in cols:
            for r, text in enumerate(ROWS):
                params = {"seed": 1000 + r}
                if gen == "graves":
                    params["bias"] = 0.75
                else:
                    params["allow_unseen"] = True  # test what happens with accents
                jobs.append({"id": f"{gen}_{col}_r{r:02d}", "text": text, "style": style, "params": params})
                if gen == "graves" and fold(text) != text:
                    jobs.append({"id": f"{gen}_{col}_r{r:02d}_fold", "text": fold(text), "style": style,
                                 "params": dict(params)})
        if gen == "graves":
            for s in range(13):
                jobs.append({"id": f"graves_allstyles_s{s:02d}", "text": "Belo Horizonte - MG", "style": s,
                             "params": {"bias": 0.75, "seed": 7}})
            for b in [0.1, 0.3, 0.5, 0.75, 1.0, 2.0]:
                for st in [None, 3]:
                    jobs.append({"id": f"graves_bias_{'none' if st is None else st}_{b}", "style": st,
                                 "text": "filha de Ana Paula Rocha e de Pedro Henrique",
                                 "params": {"bias": b, "seed": 11}})
        with open(os.path.join(HERE, "jobs", f"{gen}.jsonl"), "w", encoding="utf-8") as f:
            for j in jobs:
                f.write(json.dumps(j, ensure_ascii=False) + "\n")
        print(gen, len(jobs), "jobs")
    with open(os.path.join(HERE, "jobs", "emuru_cpu.jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"id": "emuru_cpu_r00", "text": TESTS[0], "style": "bressay_1631",
                            "params": {"seed": 1000}}, ensure_ascii=False) + "\n")
    with open(os.path.join(HERE, "jobs", "rows.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": ROWS, "columns": {g: [c for c, _ in cols] for g, cols in COLUMNS.items()}},
                  f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
