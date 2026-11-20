#!/usr/bin/env bash
# Session 4 packs: (1) code + lora_v1 adapter + test sets (small, goes first so the install
# starts at once); (2) training data: data/final/pages_v2 + every image it references.
set -euo pipefail
cd "$(dirname "$0")/../../.."
OUT="${1:-/tmp/ocr06_s4}"
tar --exclude='__pycache__' --exclude='*.egg-info' -czf "${OUT}_code.tar.gz" \
    ocr06/src ocr06/scripts ocr06/configs ocr06/pyproject.toml ocr06/requirements-gpu.txt \
    ocr06/requirements-vllm.txt ocr06/requirements.lock.txt ocr06/README.md ocr06/STATE.md ocr06/NOTES.md \
    ocr06/models/lora_v1/adapter ocr06/data/pages/smoke5 ocr06/data/pages/teste_local ocr06/data/pages/forms_v2_normal
python3 - "$OUT" <<'PY'
import json, sys
paths = set()
for s in ("train", "val"):
    for l in open(f"ocr06/data/final/pages_v2/{s}.jsonl"):
        paths.add("ocr06/data/" + json.loads(l)["image"])
open(sys.argv[1] + "_files.txt", "w").write("\n".join(sorted(paths)) + "\nocr06/data/final/pages_v2\n")
print(len(paths), "imagens")
PY
tar -czf "${OUT}_data.tar.gz" -T "${OUT}_files.txt"
ls -lh "${OUT}_code.tar.gz" "${OUT}_data.tar.gz"
