#!/usr/bin/env python3
"""Extrai as camadas de feicao por diff contra a cabeca sem feicao.

A receita e a do NOTES.md, secao "Receita da mascara (aprovada)":

    d      = |tmp_1 - feicao| em escala de cinza
    d      = mediana(d, disk(3))          # mata o salpicado de textura
    m      = d > 16
    m      = abertura(m, disk(4))         # remove o que sobrou
    m      = fechamento(m, disk(6))       # tapa buracos internos
    m      = componentes com area >= 0,5% da area da cabeca (3.464 px)
    m      = blur gaussiano 1.5           # antialias, por ultimo
    camada = feicao em RGBA com m no alpha

Os blobs sao contados na mascara binaria, DEPOIS do corte de 0,5% e ANTES do
blur. Contar no alpha ja borrado e reaplicar o corte da numero diferente, porque
o blur encolhe os componentes pequenos abaixo do limite.

Uso:
    python scripts/extract-layers.py                 # valida, nao escreve
    python scripts/extract-layers.py --write         # escreve em layers/
    python scripts/extract-layers.py --out DIR       # escreve em outro lugar
    python scripts/extract-layers.py hair_midcurly   # so os nomes dados
"""
import argparse, os, sys
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
from skimage.morphology import disk, opening as sk_opening, closing as sk_closing

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")
LAYERS = os.path.join(ROOT, "layers")
BASE = "tmp_1.png"

# --- receita ---
MEDIAN_DISK = 3
THRESHOLD = 16
OPEN_DISK = 4
CLOSE_DISK = 6
MIN_AREA_FRAC = 0.005
BLUR_SIGMA = 1.5
HEAD_AREA = 692869            # area da cabeca em tmp_1, do NOTES
MIN_AREA = int(round(HEAD_AREA * MIN_AREA_FRAC))   # 3.464 px

CANVAS = 1254

# --- regioes anatomicas por slot, em fracao do canvas ---
# As caixas absolutas do NOTES estao em px de 1254; aqui ficam em fracao para
# nao amarrar a resolucao.
#
# Tres caixas foram corrigidas em 11/09/2026, depois que o gate acusou camadas
# JA APROVADAS caindo fora delas. Quem estava errado era a caixa:
#   beard  y1 1140 -> 1165  (beard_longfull desce ate y 1161)
#   mouth  y1  850 ->  865  (mouth_thin desce ate y 861)
#   hair   y1 .75  -> .80   (as trancas descem ate y .781)
# O eixo x de hair fica em .10/.90: medido nos 24 renders novos, o extremo e
# x .121 no midcurly_red e x .869 no midcurly_red, ambos dentro.
def frac(x0, y0, x1, y1):
    return (x0 / CANVAS, y0 / CANVAS, x1 / CANVAS, y1 / CANVAS)

REGIONS = {
    "nose":  [frac(430, 340, 830, 780)],
    "mouth": [frac(370, 600, 880, 865)],
    "eye":   [frac(270, 380, 615, 640), frac(639, 380, 985, 640)],
    "brow":  [frac(270, 280, 615, 500), frac(639, 280, 985, 500)],
    "ear":   [frac(140, 370, 380, 840), frac(874, 370, 1114, 840)],
    "beard": [frac(270, 480, 985, 1165)],
    "hair":  [(0.10, 0.00, 0.90, 0.80)],
}

# blobs esperados por slot: 1 contiguo, 2 para os pares laterais
EXPECTED_BLOBS = {"eye": 2, "brow": 2, "ear": 2}

# aprovados por decisao, nao por criterio (ver NOTES, secao Decisoes)
BLOB_EXCEPTIONS = {
    "beard_stubble": 2,       # costeleta desconectada do render, 09/09/2026
    "hair_lowfade_grey": 2,   # pedaco do degrade na tempora esquerda, 14/09/2026
    "hair_lowfade_blonde": 2, # mesmo degrade na tempora esquerda do lowfade_grey, 15/09/2026
}


def slot_of(name):
    return name.split("_", 1)[0]


def build_mask(base_rgb, feat_rgb):
    """Retorna (mascara binaria pos-corte, alpha borrado 0-255)."""
    g_base = np.asarray(Image.fromarray(base_rgb).convert("L")).astype(np.int16)
    g_feat = np.asarray(Image.fromarray(feat_rgb).convert("L")).astype(np.int16)
    d = np.abs(g_base - g_feat).astype(np.uint8)
    # Duas escolhas de borda que a receita em prosa nao fixava, e que a
    # regressao contra layers/ fixou. Sem as duas, as camadas de cabelo que
    # tocam o topo do canvas perdem uma faixa de ~10 linhas.
    #   mode="nearest" na mediana: com o "reflect" padrao do scipy a borda
    #   espelha conteudo e desloca o limiar nas primeiras linhas.
    #   morfologia do skimage em vez da do scipy: a do scipy trata o fora do
    #   quadro como fundo e erode a partir da borda; a do skimage nao.
    d = ndimage.median_filter(d, footprint=disk(MEDIAN_DISK), mode="nearest")
    m = d > THRESHOLD
    m = sk_opening(m, disk(OPEN_DISK))
    m = sk_closing(m, disk(CLOSE_DISK))
    lab, n = ndimage.label(m)
    if n:
        sizes = ndimage.sum_labels(np.ones_like(lab), lab, range(1, n + 1))
        keep = {i + 1 for i, s in enumerate(sizes) if s >= MIN_AREA}
        m = np.isin(lab, list(keep)) if keep else np.zeros_like(m)
    # O blur e o do Pillow, nao o do scipy. A diferenca entre os dois e de ate
    # 4 niveis de alpha, e a referencia em layers/ reproduz byte a byte so com
    # o do Pillow, que usa tres passadas de box blur em vez do kernel exato.
    alpha = np.asarray(Image.fromarray((m * 255).astype(np.uint8))
                       .filter(ImageFilter.GaussianBlur(BLUR_SIGMA)))
    return m, alpha


def gate(name, m):
    """Porta de blobs e de regiao. Devolve (blobs, dentro, fora_px, cobertura)."""
    lab, n = ndimage.label(m)
    blobs = n
    slot = slot_of(name)
    boxes = REGIONS.get(slot)
    if boxes is None:
        return blobs, None, None, m.sum()
    H, W = m.shape
    allowed = np.zeros_like(m)
    for x0, y0, x1, y1 in boxes:
        allowed[int(y0 * H):int(np.ceil(y1 * H)), int(x0 * W):int(np.ceil(x1 * W))] = True
    fora = int((m & ~allowed).sum())
    return blobs, fora == 0, fora, int(m.sum())


def extract(name, base_rgb):
    feat = np.asarray(Image.open(os.path.join(RAW, name + ".png")).convert("RGB"))
    m, alpha = build_mask(base_rgb, feat)
    rgba = np.dstack([feat, alpha])
    return m, rgba


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--out", default=LAYERS)
    ap.add_argument("--regress", action="store_true",
                    help="compara byte a byte com layers/ em vez de escrever")
    a = ap.parse_args()

    base = np.asarray(Image.open(os.path.join(RAW, BASE)).convert("RGB"))

    if a.names:
        names = a.names
    elif a.regress:
        names = sorted(f[:-4] for f in os.listdir(LAYERS) if f.endswith(".png"))
    else:
        skip = {"tmp_1", "tmp_2", "tmp_3", "tmp_4", "preview"}
        names = sorted(f[:-4] for f in os.listdir(RAW)
                       if f.endswith(".png") and f[:-4] not in skip
                       and slot_of(f[:-4]) in REGIONS)

    print(f"base {BASE} | area minima {MIN_AREA} px | {len(names)} alvos\n")
    hdr = f"{'camada':26} {'blobs':>5} {'esp':>4} {'cobertura':>10} {'fora da caixa':>13} {'veredito':>9}"
    if a.regress:
        hdr += "  regressao"
    print(hdr)

    fails, regress_ok, regress_bad = [], [], []
    for name in names:
        if not os.path.exists(os.path.join(RAW, name + ".png")):
            print(f"{name:26} {'sem render em raw/':>40}")
            continue
        m, rgba = extract(name, base)
        blobs, dentro, fora, cov = gate(name, m)
        exp = BLOB_EXCEPTIONS.get(name, EXPECTED_BLOBS.get(slot_of(name), 1))
        ok = (blobs == exp) and (dentro is not False)
        if not ok:
            fails.append((name, blobs, exp, fora))
        line = (f"{name:26} {blobs:5d} {exp:4d} {cov:10d} "
                f"{('-' if fora is None else fora):>13} {('ok' if ok else 'FALHA'):>9}")
        if a.regress:
            ref = os.path.join(LAYERS, name + ".png")
            if os.path.exists(ref):
                import io as _io
                buf = _io.BytesIO()
                Image.fromarray(rgba, "RGBA").save(buf, "PNG")
                same_bytes = buf.getvalue() == open(ref, "rb").read()
                refa = np.asarray(Image.open(ref).convert("RGBA"))
                same_px = bool((refa == rgba).all())
                dalpha = int(np.abs(refa[..., 3].astype(int) - rgba[..., 3].astype(int)).max())
                tag = "byte" if same_bytes else ("pixel" if same_px else f"dif a<={dalpha}")
                (regress_ok if same_px else regress_bad).append(name)
                line += f"  {tag}"
            else:
                line += "  (sem ref)"
        print(line)
        if a.write:
            os.makedirs(a.out, exist_ok=True)
            Image.fromarray(rgba, "RGBA").save(os.path.join(a.out, name + ".png"))

    print()
    if a.regress:
        print(f"regressao: {len(regress_ok)} reproduzem, {len(regress_bad)} divergem")
        for n in regress_bad:
            print(f"  diverge: {n}")
    if fails:
        print(f"\n{len(fails)} reprovam o gate:")
        for n, b, e, f in fails:
            why = []
            if b != e: why.append(f"{b} blobs, esperado {e}")
            if f: why.append(f"{f} px fora da caixa")
            print(f"  {n:26} " + "; ".join(why))
    else:
        print("gate: todos passam")
    return 0


if __name__ == "__main__":
    sys.exit(main())
