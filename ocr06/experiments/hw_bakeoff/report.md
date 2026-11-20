# Handwriting generator bake-off (2026-11-15, GTX 1060 6 GB)

| Generator | Device | s/line | Accents/ç | Look | Decision |
|---|---|---|---|---|---|
| Graves RNN, sjvasquez weights (`scripts/hw/render_graves.py`, numpy port) | CPU | 0.5 | no (also no Q/X/Z uppercase, º, /) | real pen cursive; `bias` controls neatness | **use**, accent-free strings only |
| VATr++ (`blowing-up-groundhogs/vatrpp`, MIT) | GPU | 0.04 | no ("Conceição" → "Conceicho", "São" → "Sho") | most human-looking; IAM writers as styles (161) | **use**, accent-free strings only |
| Emuru (`blowing-up-groundhogs/emuru`) | GPU | 0.9 | partial and unreliable (drops Ã/ç, degenerate outputs) | font-like, grey | not used |

- aaron1259 / wpvnteam (OCRSD's other neural writers) are not public (`git ls-remote` asks for credentials), so they stay OCRSD-only.
- Style references `refs/bressay_*` were cut from BRESSAY *test* pages: fine for this sheet, never for training data. Production uses IAM writer indices (VATr++) and the 12 sjvasquez styles; styles 10–11 (Graves) and IAM 141–160 (VATr++) are reserved for test pages.
- Sheets: `sheet_graves.jpg`, `sheet_vatrpp.jpg`, `sheet_emuru.jpg`, `graves_bias.jpg`, `graves_styles.jpg`; numbers in `summary.json`.
