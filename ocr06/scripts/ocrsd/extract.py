# Pull the clean page image (without the watermark layer) out of every usable OCRSD PDF and
# write data/pages/ocrsd/pages.jsonl with the handwritten field values and boxes.
#
# Kept: the five formatted templates (old and CNJ marriage, CNJ birth, death, DNV with the
# normative mapping). Dropped:
#   - batches generated with filter "none": their PDFs are not flattened (handwriting as
#     separate layers), so the page image alone is a blank form;
#   - the old birth template (renders unfilled placeholders), the DNV "default" mapping
#     (nonsense values) and the boring no-format forms (CadÚnico, CNPJ, DREI, procurações).
# Per field: `text` is what is drawn; `requested` is the Portuguese value OCRSD asked for;
# `accent_stripped` marks neural-writer fields whose value lost accents/ç/º// (those are
# kept out of the training loss and of name scoring). Test split: held-out writers (split_of).
import glob, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from ocr06.forms.records import NEURAL_SAFE, field_class, mapping_fields  # noqa: E402

DATA = os.path.join(ROOT, "data")
src, out = os.path.join(DATA, "ocrsd"), os.path.join(DATA, "pages", "ocrsd")
os.makedirs(os.path.join(out, "images"), exist_ok=True)
KEEP = {"certidao_casamento", "certidao_casamento_cnj", "certidao_nascimento_cnj", "certidao_obito", "dnv"}


def split_of(batch, hw):
    """Teste = escritores reservados (as mãos neurais entram no treino; só alguns escritores
    ficam de fora) + 10% dos lotes com fonte, para checar regressão."""
    import hashlib
    m, w = hw.get("model"), hw.get("writer")
    if m == "sjvasquez" and w in (10, 11):
        return "test"
    if m == "aaron1259" and w is not None and w >= 400:
        return "test"
    if m == "wpvnteam" and w in (6, 7):
        return "test"
    if m in (None, "font") and int(hashlib.sha1(batch.encode()).hexdigest()[:6], 16) / 0xFFFFFF < 0.1:
        return "test"
    return "train"


rows, skipped = [], {}
for d in sorted(glob.glob(os.path.join(src, "*", ""))):
    batch = os.path.basename(os.path.normpath(d))
    pdfs = sorted(glob.glob(os.path.join(d, "synthetic_*.pdf")))
    if not pdfs:
        continue
    job = json.load(open(os.path.join(d, "job.json"))) if os.path.exists(os.path.join(d, "job.json")) else None
    first = json.load(open(pdfs[0][:-4] + ".json", encoding="utf-8"))
    template = first.get("source_template") or first["template_id"]
    filt = job["options"].get("filter_preset") if job else \
        ("none" if not (first.get("visual_filters") or {}).get("enabled") else "?")
    mapping = job["options"].get("mapping_id") if job else None
    why = ("template" if template not in KEEP else
           "unfiltered" if filt == "none" else
           "dnv-default" if template == "dnv" and mapping != "mapeamento_seguindo_norma" else None)
    if why:
        skipped[why] = skipped.get(why, 0) + len(pdfs)
        continue
    mf = mapping_fields(template)
    for pdf in pdfs:
        doc_id = f"{batch}_{os.path.basename(pdf)[:-4]}"
        meta = json.load(open(pdf[:-4] + ".json", encoding="utf-8"))
        hw = meta.get("handwriting") or {}
        neural = hw.get("model") not in (None, "font")
        prefix = os.path.join(out, "images", doc_id)
        if not os.path.exists(prefix + ".jpg"):
            subprocess.run(["pdfimages", "-j", "-f", "1", "-l", "1", pdf, prefix], check=True)
            imgs = sorted(glob.glob(prefix + "-*"))
            os.replace(imgs[0], prefix + ".jpg")
            for extra in imgs[1:]:
                os.remove(extra)
        fields = []
        for f in meta["fields"]:
            els = f.get("elements") or []
            if els and any("checked" in e for e in els):
                text = "; ".join(e.get("label", "") for e in els if e.get("checked"))
                cls = "closed"
            else:
                text = " ".join((f.get("value") or "").split())
                cls = field_class(mf.get(f["field_id"], {}).get("data_type"), text)
            if not text:
                continue
            req = f.get("requested_value")
            stripped = bool(neural and isinstance(req, str) and req != f.get("value")
                            and any(c not in NEURAL_SAFE for c in req))
            fields.append({"kind": "manuscrito", "label": f["field_id"], "text": text, "cls": cls,
                           "requested": req if isinstance(req, str) else None,
                           "accent_stripped": stripped, "box": f["bbox"]})
        rows.append({"id": doc_id, "image": f"pages/ocrsd/images/{doc_id}.jpg", "batch": batch,
                     "template": template, "writing": hw.get("model") or "font",
                     "writer": hw.get("writer"), "bias": hw.get("bias"), "filter": filt,
                     "split": split_of(batch, hw),
                     "fields": fields})
with open(os.path.join(out, "pages.jsonl"), "w", encoding="utf-8") as fh:
    for r in rows:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
print(len(rows), "pages,", sum(len(r["fields"]) for r in rows), "fields ->", out, "| skipped:", skipped)
