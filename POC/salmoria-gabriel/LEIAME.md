# Template do Relatório de PoC (INE5448), versão 3.0

Este template é usado tanto para o relatório parcial quanto para o relatório final. Os relatórios de todos os alunos serão reunidos automaticamente nos anais do Workshop Acadêmico do Registro Civil do Brasil, por isso é importante seguir as regras abaixo.

## Arquivos

| Arquivo | O que é | Editar? |
|---|---|---|
| `relatorio.tex` | Todo o conteúdo do relatório | Sim |
| `ref.bib` | Referências bibliográficas | Sim (não renomeie) |
| `figuras/` | Imagens do relatório | Sim |
| `main.tex` | Arquivo de compilação | Só a opção `final` |
| `ine5448poc.sty` | Estilo comum (pacotes, ABNT, layout) | Não |
| `pocanais.py` | Verificador das regras | Não |

## Compilação

- **Overleaf:** envie a pasta inteira, compilador pdfLaTeX. O biber roda automaticamente.
- **Local:** `latexmk -pdf main.tex` (ou `pdflatex main`, `biber main`, `pdflatex main` duas vezes).

A bibliografia usa biblatex com o estilo `abnt-numeric` (pacote biblatex-abnt).

## Relatório parcial e relatório final

- **Parcial:** `\usepackage{ine5448poc}` em `main.tex`. Aparecem a seção "Situação Atual e Plano até o Workshop" e os quadros `\situacao{...}{...}`.
- **Final:** `\usepackage[final]{ine5448poc}`. Essa seção e os quadros são omitidos automaticamente, sem precisar apagar nada.

## Regras

1. Escreva tudo em `relatorio.tex`. Se quiser dividir o texto, crie outros `.tex` nesta pasta e chame com `\input{arquivo}`.
2. Não use `\usepackage`, `\documentclass`, `\begin{document}`, `\chapter`, `\part`, `\maketitle`, `\tableofcontents`, `\appendix`, `\bibliography`, `\addbibresource`, `\printbibliography`, `\graphicspath`, `\geometry`, `\pagestyle` nem `\include`. Precisa de outro pacote? Peça ao professor.
3. A seção de nível mais alto é `\section`. Apêndices começam com `\pocapendices`.
4. Figuras ficam em `figuras/` e são chamadas por caminho relativo: `\includegraphics{figuras/arquitetura.pdf}`.
5. Referências ficam em `ref.bib` e são citadas com `\cite{chave}`. Só aparecem as obras citadas. Páginas web: tipo `online` com `url` e `urldate`.
6. `\label` e `\ref` podem ser usados normalmente; os rótulos são isolados automaticamente nos anais.
7. Comandos próprios podem ser definidos com `\newcommand` em `relatorio.tex`.
8. Substitua todos os `\preencher{...}`. O que estiver dentro deles aparece em vermelho no PDF.
9. Mantenha `\begin{situacaoparcial}` e `\end{situacaoparcial}` sozinhos em suas linhas.

## Verificação antes da entrega

Com Python 3 instalado, na pasta do relatório:

```
python3 pocanais.py verificar .
```

O verificador aponta erros (que impedem a inclusão nos anais) e avisos (como campos `\preencher` ainda não substituídos).

## Entrega

Além do PDF, envie um `.zip` desta pasta com as fontes (`relatorio.tex`, `ref.bib`, `figuras/` e eventuais `.tex` adicionais), nomeado `sobrenome-nome.zip` (minúsculas, sem acentos).
