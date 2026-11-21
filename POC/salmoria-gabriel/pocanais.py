#!/usr/bin/env python3
"""
pocanais.py | Verificação dos relatórios de PoC (INE5448) e geração dos anais.

Uso:
  python3 pocanais.py verificar <pasta_do_relatorio> [...]
      Verifica se um ou mais relatórios seguem as regras do template.
      Pode ser usado pelos alunos antes da entrega.

  python3 pocanais.py gerar [--relatorios relatorios] [--final] [--forcar]
      Verifica todos os relatórios em relatorios/<id>/, copia cada um para
      capitulos/<id>/ com os rótulos (\\label, \\ref, ...) prefixados pelo
      identificador do aluno e escreve capitulos/lista.tex para anais.tex.

      --final   trata \\preencher{...} e \\situacao{...} remanescentes como erro
      --forcar  gera mesmo com erros (os relatórios com erro são pulados)

A ordem dos capítulos segue o arquivo ordem.txt (um identificador por
linha), se existir; caso contrário, a ordem alfabética das pastas.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

PROIBIDOS = [
    (r"\\documentclass\b", "\\documentclass"),
    (r"\\usepackage\b", "\\usepackage (peça o pacote ao professor)"),
    (r"\\RequirePackage\b", "\\RequirePackage"),
    (r"\\begin\{document\}", "\\begin{document}"),
    (r"\\end\{document\}", "\\end{document}"),
    (r"\\chapter\b", "\\chapter (use \\section como nível mais alto)"),
    (r"\\part\b", "\\part"),
    (r"\\maketitle\b", "\\maketitle (use \\pocinicio)"),
    (r"\\tableofcontents\b", "\\tableofcontents"),
    (r"\\appendix\b", "\\appendix (use \\pocapendices)"),
    (r"\\addbibresource\b", "\\addbibresource"),
    (r"\\printbibliography\b", "\\printbibliography (use \\pocreferencias)"),
    (r"\\bibliography\{", "\\bibliography"),
    (r"\\bibliographystyle\b", "\\bibliographystyle"),
    (r"\\graphicspath\b", "\\graphicspath"),
    (r"\\geometry\b", "\\geometry"),
    (r"\\pagestyle\b", "\\pagestyle"),
    (r"\\include\{", "\\include (use \\input)"),
]
OBRIGATORIOS = ["\\poctitulo", "\\pocaluno", "\\poctutor", "\\pocresumo",
                "\\pocpalavraschave", "\\pocinicio", "\\pocreferencias"]

CMDS_ROTULO = r"label|ref|eqref|pageref|autoref|nameref|vref|cref|Cref|cpageref|Cpageref|labelcref"


def sem_comentarios(texto):
    linhas = []
    for linha in texto.splitlines():
        m = re.search(r"(?<!\\)%", linha)
        linhas.append(linha[:m.start()] if m else linha)
    return "\n".join(linhas)


def arquivos_tex(pasta):
    return sorted(p for p in pasta.rglob("*.tex") if p.name != "main.tex")


def chaves_bib(caminho):
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    return re.findall(r"^\s*@\s*\w+\s*\{\s*([^,\s]+)\s*,", texto, flags=re.M)


def verificar(pasta, final=False):
    pasta = Path(pasta)
    erros, avisos = [], []
    rel = pasta / "relatorio.tex"
    bib = pasta / "ref.bib"
    if not rel.exists():
        return [f"{pasta}: relatorio.tex não encontrado"], []
    if not bib.exists():
        erros.append("ref.bib não encontrado (não renomeie o arquivo)")

    corpo_total = ""
    for arq in arquivos_tex(pasta):
        nome = arq.relative_to(pasta)
        corpo = sem_comentarios(arq.read_text(encoding="utf-8", errors="replace"))
        corpo_total += corpo + "\n"
        for padrao, desc in PROIBIDOS:
            if re.search(padrao, corpo):
                erros.append(f"{nome}: uso proibido de {desc}")
        for m in re.finditer(r"\\(?:includegraphics|input|lstinputlisting)\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}", corpo):
            alvo = m.group(1).strip()
            if alvo.startswith("/") or re.match(r"^[A-Za-z]:", alvo) or ".." in alvo:
                erros.append(f"{nome}: caminho absoluto ou fora da pasta: {alvo}")
            if "includegraphics" in m.group(0):
                cand = [pasta / alvo] + [pasta / (alvo + e) for e in (".pdf", ".png", ".jpg", ".jpeg", ".eps")]
                if not any(c.exists() for c in cand):
                    erros.append(f"{nome}: figura não encontrada: {alvo}")
        n = len(re.findall(r"\\preencher\{", corpo))
        if n:
            (erros if final else avisos).append(f"{nome}: {n} campo(s) \\preencher{{...}} ainda não substituído(s)")
        n = len(re.findall(r"\\situacao\{", corpo))
        if n and final:
            avisos.append(f"{nome}: {n} quadro(s) \\situacao{{...}} remanescente(s) (ocultos na versão final)")

    for cmd in OBRIGATORIOS:
        if cmd not in corpo_total:
            erros.append(f"comando obrigatório ausente: {cmd}")

    if re.search(r"\\begin\{situacaoparcial\}[^\n]*\S", corpo_total) or \
       re.search(r"\S[^\n]*\\end\{situacaoparcial\}", corpo_total):
        erros.append("\\begin{situacaoparcial} e \\end{situacaoparcial} devem ficar sozinhos em suas linhas")

    if bib.exists():
        chaves = chaves_bib(bib)
        dup = sorted({c for c in chaves if chaves.count(c) > 1})
        if dup:
            erros.append(f"ref.bib: chaves duplicadas: {', '.join(dup)}")
        citadas = set()
        for m in re.finditer(r"\\[a-zA-Z]*cite[a-zA-Z]*\*?\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]*)\}", corpo_total):
            citadas.update(k.strip() for k in m.group(1).split(",") if k.strip())
        faltando = sorted(citadas - set(chaves) - {"*"})
        if faltando:
            erros.append(f"citações sem entrada em ref.bib: {', '.join(faltando)}")
        if "*" in citadas:
            avisos.append("\\nocite{*} lista obras não citadas; prefira citar apenas o que foi usado")

    rotulos = re.findall(r"\\label\{([^}]*)\}", corpo_total)
    dup = sorted({r for r in rotulos if rotulos.count(r) > 1})
    if dup:
        erros.append(f"rótulos \\label duplicados: {', '.join(dup)}")
    return erros, avisos


def prefixar_rotulos(texto, pref):
    def chaves(lista):
        return ",".join(pref + k.strip() if k.strip() else k for k in lista.split(","))

    texto = re.sub(r"\\(" + CMDS_ROTULO + r")(\*?)\{([^}]*)\}",
                   lambda m: f"\\{m.group(1)}{m.group(2)}{{{chaves(m.group(3))}}}", texto)
    texto = re.sub(r"\\hyperref\[([^\]]*)\]", lambda m: f"\\hyperref[{pref}{m.group(1).strip()}]", texto)

    def opcoes_lst(m):
        return re.sub(r"(\blabel\s*=\s*)(\{?)([^,\]}]+)(\}?)",
                      lambda n: f"{n.group(1)}{n.group(2)}{pref}{n.group(3).strip()}{n.group(4)}", m.group(0))
    texto = re.sub(r"\\begin\{lstlisting\}\[[^\]]*\]", opcoes_lst, texto)
    texto = re.sub(r"\\lstinputlisting\[[^\]]*\]", opcoes_lst, texto)
    return texto


def id_valido(nome):
    return re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", nome) is not None


def cmd_verificar(args):
    total = 0
    for pasta in args.pastas:
        erros, avisos = verificar(pasta, final=args.final)
        print(f"== {pasta}")
        for e in erros:
            print(f"  ERRO:  {e}")
        for a in avisos:
            print(f"  AVISO: {a}")
        if not erros and not avisos:
            print("  OK")
        total += len(erros)
    return 1 if total else 0


def cmd_gerar(args):
    base = Path(__file__).resolve().parent
    origem = (base / args.relatorios).resolve()
    destino = base / "capitulos"
    if not origem.is_dir():
        print(f"Pasta {origem} não encontrada.")
        return 1
    pastas = {p.name: p for p in origem.iterdir() if p.is_dir() and not p.name.startswith(".")}
    ordem_arq = base / "ordem.txt"
    if ordem_arq.exists():
        ordem = [l.strip() for l in ordem_arq.read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.startswith("#")]
        ausentes = [i for i in ordem if i not in pastas]
        for i in ausentes:
            print(f"AVISO: {i} está em ordem.txt mas não existe em {args.relatorios}/")
        ordem = [i for i in ordem if i in pastas] + sorted(set(pastas) - set(ordem))
    else:
        ordem = sorted(pastas)

    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir()
    incluidos, com_erro = [], []
    for ident in ordem:
        if not id_valido(ident):
            print(f"== {ident}\n  ERRO:  nome de pasta inválido; use sobrenome-nome em minúsculas, sem acentos")
            com_erro.append(ident)
            continue
        erros, avisos = verificar(pastas[ident], final=args.final)
        print(f"== {ident}")
        for e in erros:
            print(f"  ERRO:  {e}")
        for a in avisos:
            print(f"  AVISO: {a}")
        if erros:
            com_erro.append(ident)
            continue
        alvo = destino / ident
        shutil.copytree(pastas[ident], alvo, ignore=shutil.ignore_patterns(
            "*.aux", "*.log", "*.out", "*.toc", "*.bbl", "*.bcf", "*.blg", "*.run.xml",
            "*.fls", "*.fdb_latexmk", "*.synctex.gz", "comment.cut", "*.pdf_tex",
            "main.tex", "main.pdf", "ine5448poc.sty", ".git"))
        for arq in alvo.rglob("*.tex"):
            texto = arq.read_text(encoding="utf-8", errors="replace")
            arq.write_text(prefixar_rotulos(texto, f"{ident}:"), encoding="utf-8")
        incluidos.append(ident)

    if com_erro and not args.forcar:
        print(f"\n{len(com_erro)} relatório(s) com erro: {', '.join(com_erro)}")
        print("Corrija-os ou use --forcar para gerar os anais sem eles.")
        shutil.rmtree(destino)
        return 1

    linhas = ["% Gerado automaticamente por pocanais.py. Não edite.\n"]
    linhas += [f"\\pocincluir{{capitulos/{i}}}\n" for i in incluidos]
    (destino / "lista.tex").write_text("".join(linhas), encoding="utf-8")
    print(f"\n{len(incluidos)} capítulo(s) em capitulos/lista.tex.")
    if com_erro:
        print(f"Pulados por erro: {', '.join(com_erro)}")
    print("Compile com:  latexmk -pdf anais.tex")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verificar", help="verifica relatórios")
    v.add_argument("pastas", nargs="+")
    v.add_argument("--final", action="store_true")
    g = sub.add_parser("gerar", help="prepara os capítulos dos anais")
    g.add_argument("--relatorios", default="relatorios")
    g.add_argument("--final", action="store_true")
    g.add_argument("--forcar", action="store_true")
    args = ap.parse_args()
    sys.exit(cmd_verificar(args) if args.cmd == "verificar" else cmd_gerar(args))


if __name__ == "__main__":
    main()
