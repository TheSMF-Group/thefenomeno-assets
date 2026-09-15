"""Compara o render de referência (gerador sobre raw/tmp_4.png) com os compostos de hair_buzz sobre
tmp_4 em 1254: linhas de base (nativo w=0, w=r, w=1) e as regras das hipóteses em
<scratch>/hip/<slug>/tmp4_1254_regra.png.

A referência NÃO é asset: serve para saber como o gerador resolve a relação pele-pelo em tom escuro.
A geometria pode não bater pixel a pixel, então nada aqui depende de alinhamento: são distribuições
de razão-à-base por região anatômica, perfis verticais pela testa e mapas em escala grossa.

Uso (de fora do repo, para as imagens não caírem nele):
  python scripts/medicao/comparar_referencia.py [--ref raw/_referencia/x.png ...] [--hip DIR]
Sem --ref, só as linhas de base são medidas (autoteste do comparador).
"""
import argparse, glob, os
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
code = open(os.path.join(HERE, "medir_pelo.py"), encoding="utf8").read()
g = {"__file__": os.path.join(HERE, "medir_pelo.py")}
exec(code[:code.index("# ---------------------------------------------------------------- 1. distribuição")], g)
exec(code[code.index("# ---------------------------------------------------------------- composição"):code.index("GRATIS = {")], g)
OUT, lin, load, silhouette, srgb8, hair_edge, over = (g[k] for k in ["OUT", "lin", "load", "silhouette", "srgb8", "hair_edge", "over"])

SRC = load(os.path.join(ROOT, "raw", "tmp_1.png"))          # RGBA 1254
BASE = load(os.path.join(ROOT, "raw", "tmp_4.png"))         # RGBA 1254, MST-10
LAYER = load(os.path.join(ROOT, "layers", "hair_buzz.png"))
SIL = silhouette(SRC[..., :3])
EDGE = SRC.shape[0]

def Y(rgb):
    l = lin(rgb[..., :3]); return 0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]

def rmap(lay, src):
    lr, sr = lin(lay[..., 0]), lin(src[..., 0])
    return np.where(sr > 0, lr / np.where(sr > 0, sr, 1), 0)

# regiões anatômicas, definidas UMA vez pela camada nativa (a hipótese de alinhamento é declarada, não assumida)
R = rmap(LAYER, SRC)
MIOLO = (LAYER[..., 3] > 200) & SIL
CORE = MIOLO & (R < 0.15)
BAND = MIOLO & (R >= 0.15) & (R < 0.85)
# controle: pele nua da testa abaixo da banda, sem fio — 40 px abaixo do ponto mais baixo da máscara no centro
ys, xs = np.nonzero(LAYER[..., 3] > 0)
cols = (xs > EDGE * 0.42) & (xs < EDGE * 0.58)
hair_bottom = int(np.percentile(ys[cols], 99)) if cols.any() else int(EDGE * 0.3)
CONTROL = np.zeros_like(SIL); CONTROL[hair_bottom + 40:hair_bottom + 140, int(EDGE * 0.42):int(EDGE * 0.58)] = True
CONTROL &= SIL & ~(LAYER[..., 3] > 0)

def baselines():
    out = {"nativo (w=0)": over(BASE, LAYER)}
    out["w = r"] = over(BASE, hair_edge(LAYER, SRC, BASE, "r"))
    out["w = 1"] = over(BASE, hair_edge(LAYER, SRC, BASE, "1"))
    return out

def to_1254(img_u8):
    """Referência em outro tamanho: reamostra SÓ a referência, para medição (não é asset)."""
    if img_u8.shape[0] == EDGE and img_u8.shape[1] == EDGE:
        return img_u8, False
    im = Image.fromarray(img_u8[..., :3]).resize((EDGE, EDGE), Image.LANCZOS)
    return np.array(im), True

def stats(name, rgb, ref_sil=None):
    ratio = Y(rgb) / np.maximum(Y(BASE), 1e-6)
    row = {"nome": name}
    for reg, m in [("controle", CONTROL), ("banda", BAND), ("nucleo", CORE)]:
        v = ratio[m]
        row[reg] = (np.percentile(v, 10), np.percentile(v, 50), np.percentile(v, 90))
    Lc = srgb8(Y(rgb)).astype(float); Lb = srgb8(Y(BASE)).astype(float)
    row["mancha_px"] = int(((Lc - Lb) > 10)[MIOLO].sum())
    row["nucleo_L"] = float(Lc[CORE].mean())
    row["banda_L"] = float(Lc[BAND].mean())
    return row

def profile(rgb):
    """Perfil vertical de razão-à-base pela testa (colunas centrais), tolerante a desalinhamento."""
    ratio = Y(rgb) / np.maximum(Y(BASE), 1e-6)
    c0, c1 = int(EDGE * 0.42), int(EDGE * 0.58)
    return np.median(ratio[:, c0:c1], axis=1)

def coarse(rgb, sigma=12):
    ratio = Y(rgb) / np.maximum(Y(BASE), 1e-6)
    ratio = np.where(SIL, ratio, 1.0)
    return ndimage.gaussian_filter(ratio, sigma)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", nargs="*", default=sorted(glob.glob(os.path.join(ROOT, "raw", "_referencia", "*.png"))))
    ap.add_argument("--hip", default=os.environ.get("HIP_DIR", ""))
    a = ap.parse_args()

    imgs = baselines()
    if a.hip:
        for p in sorted(glob.glob(os.path.join(a.hip, "*", "tmp4_1254_regra.png"))):
            slug = os.path.basename(os.path.dirname(p))
            im = np.array(Image.open(p).convert("RGB"))
            if im.shape[:2] == (EDGE, EDGE):
                imgs[f"hip:{slug}"] = np.dstack([im, np.full(im.shape[:2], 255, np.uint8)])
            else:
                print(f"  {slug}: tmp4_1254_regra.png tem {im.shape[:2]}, esperado {EDGE}; ignorado")
    refs = {}
    for p in a.ref:
        im = np.array(Image.open(p).convert("RGB"))
        im1254, resampled = to_1254(im)
        rsil = silhouette(im1254)
        iou = (rsil & SIL).sum() / (rsil | SIL).sum()
        print(f"referência {os.path.basename(p)}: {im.shape[1]}x{im.shape[0]}{' (reamostrada para medir)' if resampled else ''}; IoU silhueta vs tmp_4 {iou:.4f}")
        refs[f"REF {os.path.basename(p)}"] = np.dstack([im1254, np.full(im1254.shape[:2], 255, np.uint8)])
    allimgs = {**refs, **imgs}

    print(f"\nrazão Y(img)/Y(tmp_4): p10 / p50 / p90 por região (controle = pele nua da testa, {CONTROL.sum():,} px; banda {BAND.sum():,} px; núcleo {CORE.sum():,} px)")
    print(f"{'imagem':28} {'controle':>20} {'banda':>20} {'núcleo':>20} {'mancha px':>9} {'L núcleo':>8} {'L banda':>7}")
    for name, rgb in allimgs.items():
        s = stats(name, rgb)
        f = lambda t: f"{t[0]:.2f}/{t[1]:.2f}/{t[2]:.2f}"
        print(f"{name:28} {f(s['controle']):>20} {f(s['banda']):>20} {f(s['nucleo']):>20} {s['mancha_px']:9,} {s['nucleo_L']:8.1f} {s['banda_L']:7.1f}")

    # perfis verticais
    print("\nperfil vertical (mediana das colunas centrais) da razão Y/Y(tmp_4), linhas de 20 px, y de 60 a 520:")
    ys = list(range(60, 520, 20))
    print("y      " + " ".join(f"{y:5d}" for y in ys))
    for name, rgb in allimgs.items():
        pr = profile(rgb)
        print(f"{name[:24]:24} " + " ".join(f"{pr[y]:5.2f}" for y in ys))

    # imagens: lado a lado (recorte da testa) e mapas grossos
    y0, y1, x0, x1 = 40, 560, 250, 1004
    crops, maps = [], []
    for name, rgb in allimgs.items():
        crops.append(rgb[y0:y1, x0:x1, :3])
        cm = coarse(rgb)[y0:y1, x0:x1]
        vis = np.clip((cm - 0.4) / 0.9, 0, 1)  # 0,4 → preto, 1,3 → branco
        maps.append((np.stack([vis] * 3, -1) * 255).astype(np.uint8))
    sep = np.full((y1 - y0, 6, 3), 255, np.uint8)
    row = [crops[0]]
    for c in crops[1:]: row += [sep, c]
    mrow = [maps[0]]
    for m in maps[1:]: mrow += [sep, m]
    Image.fromarray(np.concatenate(row, 1)).save(os.path.join(OUT, "ref_vs_compostos_testa.png"))
    Image.fromarray(np.concatenate(mrow, 1)).save(os.path.join(OUT, "ref_vs_compostos_razao_grossa.png"))
    print("\nordem nas imagens:", " | ".join(allimgs.keys()))
    print("imagens em", OUT)

if __name__ == "__main__":
    main()
