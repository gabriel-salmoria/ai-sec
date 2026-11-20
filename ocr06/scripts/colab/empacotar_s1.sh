#!/usr/bin/env bash
# Packs what session 1 needs (no git): code, the lora_v0 adapter and the test page sets.
# Output: $1 (default /tmp/ocr06_s1.tar.gz), paths relative to ai-sec/ (extract in /content/ai-sec).
set -euo pipefail
cd "$(dirname "$0")/../../.."
OUT="${1:-/tmp/ocr06_s1.tar.gz}"
tar --exclude='__pycache__' --exclude='*.egg-info' -czf "$OUT" \
    ocr06/src ocr06/scripts ocr06/configs ocr06/pyproject.toml ocr06/requirements-gpu.txt \
    ocr06/requirements-vllm.txt ocr06/requirements.lock.txt ocr06/README.md ocr06/STATE.md ocr06/NOTES.md \
    ocr06/models/lora_v0/adapter \
    ocr06/data/pages/modelos_em_branco ocr06/data/pages/smoke5 ocr06/data/pages/teste_local \
    ocr06/data/pages/teste_ocrsd ocr06/data/pages/metade_local ocr06/data/pages/metade_ocrsd
ls -lh "$OUT"
