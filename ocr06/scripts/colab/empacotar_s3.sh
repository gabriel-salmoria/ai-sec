#!/usr/bin/env bash
# Session 3 pack: code + lora_v1 adapter + test sets (incl. BRESSAY images). One tar.
set -euo pipefail
cd "$(dirname "$0")/../../.."
OUT="${1:-/tmp/ocr06_s3.tar.gz}"
tar --exclude='__pycache__' --exclude='*.egg-info' -czf "$OUT" \
    ocr06/src ocr06/scripts ocr06/configs ocr06/pyproject.toml ocr06/requirements-gpu.txt \
    ocr06/requirements-vllm.txt ocr06/requirements.lock.txt ocr06/README.md ocr06/STATE.md ocr06/NOTES.md \
    ocr06/models/lora_v1/adapter \
    ocr06/data/pages/smoke5 ocr06/data/pages/teste_local ocr06/data/pages/teste_ocrsd \
    ocr06/data/pages/teste_local_novos ocr06/data/pages/teste_ocrsd_novos ocr06/data/pages/bressay100 \
    ocr06/data/pages/bressay ocr06/data/pages/metade_local_aval ocr06/data/pages/metade_ocrsd
ls -lh "$OUT"
