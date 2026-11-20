# Wave 3: probes for the templates not tried yet, then 12 more jobs for each of the five
# templates that already render well, varying handwriting, ink and scan degradation.
import json, os, random
rng = random.Random(3)
BLUE, BLACK, DARK = "#193787", "#1a1a1a", "#0b2a6f"
INKS = [("azul", BLUE), ("preto", BLACK), ("azulesc", DARK)]
FILTERS = ["none", "light", "medium", "medium", "strong"]


def font(fam, inten, color):
    return {"model": "font", "font_family": fam, "intensity": inten, "writer": None, "handwriting": True,
            "text_handwriting": True, "bias": 0.75, "color": color, "width": 1.5, "pressure": 0.25,
            "dropout": 0.0, "text_policy": "normalize"}


def neural(model, writer, color):
    return {"model": model, "font_family": "caveat", "intensity": 0.65, "writer": writer, "handwriting": True,
            "text_handwriting": True, "bias": 0.75, "color": color, "width": 1.5, "pressure": 0.25,
            "dropout": 0.0, "text_policy": "normalize"}


def writing(k):
    ink, color = INKS[k % 3]
    kind = k % 5
    ink, color = INKS[(k // 5) % 3]
    if kind in (0, 1):
        fam = ["caveat", "homemade_apple"][kind]
        inten = rng.choice([0.25, 0.45, 0.65, 0.85, 0.95])
        return f"{fam.split('_')[0]}{int(inten * 100)}-{ink}", font(fam, inten, color), False
    model, w = [("sjvasquez", rng.randint(0, 11)), ("aaron1259", rng.randint(1, 480)),
                ("wpvnteam", rng.randint(0, 7))][kind - 2]
    return f"{model[:5]}-w{w}-{ink}", neural(model, w, color), True


GOOD = {"casamento_cnj": ("certidao_casamento_cnj", "mapeamento_certidao_casamento_cnj_v2"),
        "nascimento_cnj": ("certidao_nascimento_cnj", "mapeamento_certidao_nascimento_cnj_v3"),
        "cadunico": ("declaracao_residencia_cadunico", "declaracao_residencia_cadunico_v1"),
        "obito": ("certidao_obito", "mapeamento_certidao_obito_v4"),
        "casamento": ("certidao_casamento", "mapeamento_certidao_casamento_v2")}
PROBE = {"proc_amplos": ("procuracao_publica_amplos_poderes", "procuracao_publica_amplos_poderes_v1"),
         "proc_venda": ("procuracao_publica_venda_imovel", "procuracao_publica_venda_imovel_v1"),
         "proc_inss": ("procuracao_publica_movimentacao_pensao_inss", "procuracao_publica_movimentacao_pensao_inss_v1"),
         "drei_simpl": ("drei_certidao_simplificada", "drei_certidao_simplificada_v1"),
         "cnpj_qsa": ("cnpj_quadro_socios_administradores", "cnpj_quadro_socios_administradores_v1")}

jobs, k = [], 0
for t, (dt, mid) in PROBE.items():
    name, w, _ = writing(0)  # font-based, keeps numbers
    jobs.append({"dir": f"w3_{t}_{name}", "document_type": dt, "mapping_id": mid, "writing": w, "count": 10,
                 "seed": 31001 + k, "filter": "medium", "text_only": False})
    k += 1
for rep in range(12):
    for t, (dt, mid) in GOOD.items():
        name, w, text_only = writing(rep + 3 * list(GOOD).index(t))
        jobs.append({"dir": f"w3_{t}_{name}_{rep:02d}", "document_type": dt, "mapping_id": mid, "writing": w,
                     "count": 10, "seed": 31001 + k, "filter": rng.choice(FILTERS), "text_only": text_only})
        k += 1
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs_wave3.json")
json.dump(jobs, open(out, "w"), indent=1, ensure_ascii=False)
print(len(jobs), "jobs ->", out)
