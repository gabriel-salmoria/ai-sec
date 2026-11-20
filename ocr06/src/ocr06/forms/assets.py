"""Baixa (uma vez) os modelos em branco e os mapeamentos de campos do OCRSD.

    python -m ocr06.forms.assets

Saída em data/forms/<template>/: template.pdf, template.png (rasterizado no mesmo tamanho
em pixels das páginas do OCRSD, que é o espaço das caixas do mapeamento) e mapping.json.
Só faz GETs de leitura na API (não usa a cota de geração).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "forms"
TEMPLATES = {
    "certidao_casamento": "mapeamento_certidao_casamento_v2",
    "certidao_casamento_cnj": "mapeamento_certidao_casamento_cnj_v2",
    "certidao_nascimento_cnj": "mapeamento_certidao_nascimento_cnj_v3",
    "certidao_obito": "mapeamento_certidao_obito_v4",
    "dnv": "mapeamento_seguindo_norma",
}


def _api():
    sys.path.insert(0, str(ROOT / "scripts" / "ocrsd"))
    from api import call  # noqa: E402
    return call


def page_size_px(template: str) -> tuple[int, int] | None:
    """Tamanho (w, h) das páginas do OCRSD deste modelo, lido de uma página já baixada."""
    for meta in sorted((ROOT / "data" / "ocrsd").glob("*/synthetic_0001.json")):
        m = json.loads(meta.read_text(encoding="utf-8"))
        if template not in (m["template_id"], m.get("source_template")):
            continue
        out = subprocess.run(["pdfimages", "-list", str(meta.with_suffix(".pdf"))],
                             capture_output=True, text=True).stdout.splitlines()[2:]
        sizes = [(int(c[3]), int(c[4])) for c in (l.split() for l in out) if c[2] == "image"]
        if sizes:
            return max(sizes, key=lambda s: s[0] * s[1])
    return None


def fetch(template: str, mapping_id: str) -> None:
    call = _api()
    d = OUT / template
    d.mkdir(parents=True, exist_ok=True)
    if not (d / "template.pdf").exists():
        (d / "template.pdf").write_bytes(call("GET", f"/api/v1/document-types/{template}/template", raw=True))
    if not (d / "mapping.json").exists():
        m = call("GET", f"/api/v1/document-types/{template}/mappings/{mapping_id}")
        (d / "mapping.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    if not (d / "template.png").exists():
        wh = page_size_px(template)
        if wh is None:
            raise SystemExit(f"nenhuma página do OCRSD para {template}; não sei o tamanho em px")
        subprocess.run(["pdftoppm", "-png", "-singlefile", "-scale-to-x", str(wh[0]),
                        "-scale-to-y", str(wh[1]), str(d / "template.pdf"), str(d / "template")],
                       check=True)
    print(template, "ok", page_size_px(template))


if __name__ == "__main__":
    for t, mid in TEMPLATES.items():
        fetch(t, mid)
