# HANDOFF — sessão Windows, 14/09/2026

Nota operacional de fim de sessão. Inventário, não decisão: as decisões estão no
`NOTES.md`.

Base: `skins-import` em `693d2728ed1b646d98ff1617e70e4034dd75c4d6`. Este arquivo é o commit seguinte.

## PRs mergeados nesta sessão

- #5 — docs: tamanho do build após o raio 4, e a reprodução em Windows
- #6 — docs: `hair_lowfade_grey` aprovado por decisão; o que o prompt move e o que não move
- #7 — feat: versiona os renders de cor e os bigodes que existiam só numa máquina
- #8 — feat: `hair-color.py`, medição de cor de cabelo e correção de valor em pós
- #9 — docs: critério V p90 do loiro; correção do ruivo parada no composto
- #10 — feat: versiona os 8 loiros regerados, aprovados por V p90
- #11 — docs: ruivo, quarta hipótese de correção de cor descartada; máscara do loiro decidida
- #12 — feat: versiona os três regerados de 11/09 que estavam só em `~/Downloads`

## Catálogo de cabelo

| grupo | itens | estado |
|---|---|---|
| escuras nativas | 8 | aprovadas, camada extraída |
| grisalhas | 8 | aprovadas |
| loiras | 8 | aprovadas |
| ruivas | 8 | valor aprovado, croma em aberto |

## Em `raw/` e ainda não extraído

- **24 renders de cor**: `raw/hair_<forma>_grey.png`, `raw/hair_<forma>_blonde.png`,
  `raw/hair_<forma>_red.png`, para as 8 formas.
- **`raw/beard_mustache_v3.png`**.
- **Três regerados**, em `raw/_regerados_2026-09-11/`: `brow_thick.png`,
  `beard_stubble.png`, `beard_mustache.png`. Estavam só em `~/Downloads` da máquina
  Windows. Não sobrescrevem os arquivos de mesmo nome na raiz de `raw/`, que são a
  fonte das camadas atuais. O `beard_mustache.png` desta pasta, com 1.531.806 bytes,
  é um arquivo diferente do `beard_mustache_v3.png`, com 1.674.310.

## Pendências abertas

- **Croma do ruivo**: sem correção em andamento; quatro hipóteses de correção de cor
  descartadas, listadas no `NOTES.md`.
- **Matiz do loiro 26–33** contra alvo 36: aceito por decisão.
- **`hair_lowfade_grey`**: aprovado com 2 blobs, por decisão; está em `BLOB_EXCEPTIONS`
  de `scripts/extract-layers.py`.

## Próxima sessão, na ordem

1. Extrair as 24 camadas.
2. Schema de nove slots.
3. `catalog.ts`.
4. Servir `build/` por jsDelivr.

## Armadilhas conhecidas desta semana

- **Python 32-bit no PATH do Windows faz o build parecer irreprodutível.** Use o
  Python 3.14 de 64 bits, `pythoncore-3.14-64`.
- **O `git clean` quase apagou assets não rastreados.**
- **Três métodos usados para decidir existiam em uma máquina só.**
