"""Controles na saída do modelo: confiança por palavra e sinais para revisão humana.

Nada aqui depende do modelo; recebe o texto gerado e, se houver, a log-probabilidade de
cada token (o vLLM devolve com `SamplingParams(logprobs=...)`). A linha vai para revisão
se qualquer verificação falhar. As verificações não bloqueiam a saída: num cartório quem
decide é o operador, e o sistema só aponta onde olhar.

  vazia        a predição ficou vazia depois de remover HTML
  tamanho      mais caracteres do que cabem na largura da imagem (ver preprocess.max_chars)
  html         sobrou marcação ou bloco de código (o prompt pede só o texto)
  caracteres   caracteres fora do que aparece em documento manuscrito em português
  repeticao    o mesmo trecho repetido várias vezes (o modelo entrou em laço)
  instrucao    a saída parece resposta a uma instrução e não transcrição (injeção pela imagem)
  confianca    alguma palavra com confiança abaixo de guard.min_word_conf
"""
from __future__ import annotations

import math
import re
import unicodedata

ALLOWED = re.compile(r"[\wÀ-ÿ\s.,;:!?'\"()\[\]/\-–—ºª°%$&+=*#@]")
HTML = re.compile(r"<[^>]+>|```|&[a-z]+;")
# Frases típicas de um modelo que obedeceu a um comando em vez de transcrever. Uma
# linha manuscrita pode conter essas palavras, por isso o resultado é só revisão.
# "ignor-" sozinho marcava 16 linhas legítimas do BRESSAY ("ignoram", "ignorantes"),
# então só conta seguido de instrução/tarefa/comando.
INSTRUCTION = re.compile(
    r"\b(ignor\w* (a|as|o|os|esta|essa|esse|este|sua|suas) (instru|tarefa|comando|pedido|regra)\w*"
    r"|instru[cç][aãõ]\w* (anterior|original)\w*|prompt|system|assistant|como (um|uma) (modelo|ia|assistente)"
    r"|n[aã]o posso|desculp\w+|aqui est[aá]|segue a transcri\w+|transcri[cç][aã]o:)",
    re.IGNORECASE)


def word_confidence(tokens: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """[(texto_do_token, logprob)] -> [(palavra, confiança)], com a confiança da palavra
    igual à probabilidade do pior token que a compõe. Espaço separa palavras; um token
    que contém espaço no meio fecha a palavra anterior e abre a seguinte."""
    words: list[tuple[str, float]] = []
    cur, worst = "", 0.0
    for text, lp in tokens:
        for i, part in enumerate(re.split(r"(\s+)", text)):
            if not part:
                continue
            if part.isspace():
                if cur:
                    words.append((cur, math.exp(worst)))
                cur, worst = "", 0.0
                continue
            cur += part
            worst = min(worst, lp)
    if cur:
        words.append((cur, math.exp(worst)))
    return words


def tokens_from_vllm(out) -> list[tuple[str, float]]:
    """CompletionOutput do vLLM -> [(texto_do_token, logprob)] dos tokens gerados.
    `out.logprobs` é uma lista (um item por token) de dicionários {token_id: Logprob}, e o
    token gerado está nesse dicionário junto com os mais prováveis. Sem logprobs, devolve []."""
    toks = []
    for tid, lp in zip(out.token_ids, out.logprobs or []):
        if tid in lp:
            toks.append((lp[tid].decoded_token or "", lp[tid].logprob))
    return toks


def repeated(text: str, min_len: int = 3, times: int = 4) -> bool:
    """True se algum trecho de pelo menos `min_len` caracteres aparece `times` vezes seguidas."""
    return re.search(rf"(.{{{min_len},}}?)\1{{{times - 1},}}", text) is not None


def check(pred_raw: str, pred: str, limit_chars: int, cfg: dict,
          tokens: list[tuple[str, float]] | None = None, allow_html: bool = False) -> dict:
    """pred_raw: saída do modelo; pred: já normalizada (sem HTML). Devolve
    {revisao, motivos, palavras_baixa_confianca, confianca_min}. allow_html=True para o
    prompt nativo do Chandra, que responde em HTML por definição."""
    gc = cfg.get("guard", {})
    reasons = []
    if not pred.strip():
        reasons.append("vazia")
    if len(pred) > limit_chars:
        reasons.append("tamanho")
    if not allow_html and HTML.search(pred_raw):
        reasons.append("html")
    text = unicodedata.normalize("NFC", pred)
    bad = [c for c in text if not ALLOWED.match(c)]
    if len(bad) > gc.get("max_bad_chars", 0):
        reasons.append("caracteres")
    if repeated(text):
        reasons.append("repeticao")
    if INSTRUCTION.search(text):
        reasons.append("instrucao")
    low, conf_min = [], None
    if tokens:
        wc = word_confidence(tokens)
        if wc:
            conf_min = round(min(c for _, c in wc), 4)
        low = [w for w, c in wc if c < gc.get("min_word_conf", 0.5)]
        if low:
            reasons.append("confianca")
    return {"revisao": bool(reasons), "motivos": reasons,
            "palavras_baixa_confianca": low, "confianca_min": conf_min}
