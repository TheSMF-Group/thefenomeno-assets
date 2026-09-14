#!/usr/bin/env python3
"""Cor de cabelo: medição e correção de valor em pós.

Subcomandos:

    python scripts/hair-color.py measure ARQ... --hex '#c8a165' [--v90-min 200]
    python scripts/hair-color.py fix-value ARQ... --hex '#b0522a' [--target-median 176]
                                 [--apply --out DIR]

ARQ é um caminho de PNG. Nada é escrito no repositório: `fix-value` só grava
arquivos com --apply, e só em --out.

Máscaras, todas derivadas da extração versionada (scripts/extract-layers.py),
para a medição de cor não divergir da geometria da camada:

    cabelo  = build_mask() da extração, a mesma receita que gera layers/
    opaco   = cabelo erodido por disk(4); é onde se mede cor e faixa dinâmica
    mascara S = cabelo ∩ HSV S >= 0,50, só os componentes 8-conexos com a área
              mínima da extração. É onde a curva de valor é aplicada. Separa
              cabelo ruivo (S 0,77–0,89) de pele (S ~0,42). É a versão
              versionada do "run contíguo", que nunca foi commitado.

Faixa de cor para cabelo: p90–p98 de luminância, em luz linear. A p70–p90 é de
pele e não transfere; ver NOTES.

Curva de `fix-value`: ganho linear g = alvo / p50 sobre V, que preserva a razão
p90/p50 por construção. O alvo é o menor entre --target-median e o teto que a
razão permite, 255 * p50 / p90. Acima de p90:
  - se sobra folga (g * p90 < 255), um ombro contínuo em p90 leva o topo a 255
    sem estourar; o expoente sai das condições de continuidade, não é escolhido;
  - no teto (g * p90 == 255), não sobra folga e tudo acima de p90 vai a 255.
    Isso é clipping do decil mais claro, e é reportado.
A curva é aplicada como razão por pixel nos três canais, então H e S ficam
invariantes; o arredondamento para 8 bits é a única fonte de desvio, e é medido.
"""
import argparse, importlib.util, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from skimage.morphology import disk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "extract_layers", os.path.join(ROOT, "scripts", "extract-layers.py"))
XL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(XL)

S_MIN = 0.50
OPAQUE_ERODE = 4
YW = np.array([0.2126, 0.7152, 0.0722])


def load_u8(path):
    return np.asarray(Image.open(path).convert("RGB"))


def hsv(rgb):
    rgb = rgb.astype(np.float64)
    mx, mn = rgb.max(2), rgb.min(2)
    d = mx - mn
    S = np.where(mx > 0, d / np.maximum(mx, 1e-9), 0.0)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    H = np.zeros_like(mx)
    nz = d > 1e-9
    rm = nz & (mx == r)
    gm = nz & (mx == g) & ~rm
    bm = nz & ~rm & ~gm
    H[rm] = (60 * (g - b)[rm] / d[rm]) % 360
    H[gm] = 60 * (b - r)[gm] / d[gm] + 120
    H[bm] = 60 * (r - g)[bm] / d[bm] + 240
    return H, S, mx


def lin(rgb):
    c = rgb.astype(np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lab(v):
    M = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    x = M @ v / np.array([0.95047, 1.0, 1.08883])
    f = np.where(x > 0.008856, np.cbrt(x), 7.787 * x + 16 / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def hex_lab(h):
    return lab(lin(np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.uint8)))


def masks(path):
    base = load_u8(os.path.join(ROOT, "raw", "tmp_1.png"))
    img = load_u8(path)
    hair, _ = XL.build_mask(base, img)
    opaque = ndimage.binary_erosion(hair, disk(OPAQUE_ERODE))
    return img, hair, opaque


def s_mask(img, hair):
    _, S, _ = hsv(img)
    cand = hair & (S >= S_MIN)
    lb, n = ndimage.label(cand, structure=np.ones((3, 3)))
    sz = ndimage.sum_labels(np.ones_like(lb), lb, range(1, n + 1))
    return np.isin(lb, [i + 1 for i, s in enumerate(sz) if s >= XL.MIN_AREA])


def stats(img, region, opaque, tlab):
    H, S, V = hsv(img)
    hs = ((H[region] + 180) % 360) - 180
    px = lin(img)[opaque]
    Y = px @ YW
    lo, hi = np.percentile(Y, [90, 98])
    band = px[(Y >= lo) & (Y <= hi)].mean(0)
    p5, p95 = np.percentile(Y, [5, 95])
    v50, v90 = np.percentile(V[region], [50, 90])
    return dict(n=int(region.sum()), H=float(np.median(hs)), S=float(np.median(S[region])),
                V50=float(v50), V90=float(v90), razao=float(v90 / max(v50, 1e-9)),
                dE=float(np.linalg.norm(lab(band) - tlab)), faixa=float(p95 / max(p5, 1e-12)))


def cmd_measure(a):
    tlab = hex_lab(a.hex)
    print(f"regiao = pelo opaco (cabelo da extracao erodido por disk({OPAQUE_ERODE})) | alvo {a.hex}\n")
    print(f"{'arquivo':30} {'n':>7} {'H':>6} {'S':>6} {'V p50':>6} {'V p90':>6} {'dE p90-98':>9} {'p95/p5':>7}"
          + ("  V p90 > %g?" % a.v90_min if a.v90_min is not None else ""))
    for path in a.files:
        img, hair, opaque = masks(path)
        s = stats(img, opaque, opaque, tlab)
        line = (f"{os.path.basename(path)[:-4]:30} {s['n']:7d} {s['H']:6.1f} {s['S']:6.3f} {s['V50']:6.1f} "
                f"{s['V90']:6.1f} {s['dE']:9.1f} {s['faixa']:7.2f}")
        if a.v90_min is not None:
            line += "  " + ("passa" if s["V90"] > a.v90_min else "NAO")
        print(line)


def curve_params(p50, p90, target):
    teto = 255.0 * p50 / p90
    alvo = min(target, teto)
    g = alvo / p50
    return alvo, teto, g, g * p90


def apply_curve(V, g, p90, yk):
    y = g * V
    if g > 1:
        if yk < 255 - 1e-6:
            n = g * (255 - p90) / (255 - yk)
            u = np.clip((V - p90) / (255 - p90), 0, 1)
            y = np.where(V > p90, yk + (255 - yk) * (1 - (1 - u) ** n), y)
        else:
            y = np.where(V > p90, 255.0, y)
    return np.minimum(y, 255.0)


def cmd_fix(a):
    tlab = hex_lab(a.hex)
    for path in a.files:
        name = os.path.basename(path)[:-4]
        img, hair, opaque = masks(path)
        M = s_mask(img, hair)
        _, S0, V0 = hsv(img)
        p50, p90 = np.percentile(V0[M], [50, 90])
        alvo, teto, g, yk = curve_params(p50, p90, a.target_median)
        modo = "alvo" if alvo >= a.target_median - 1e-9 else "teto da razao"
        ratio = np.where(M, apply_curve(V0, g, p90, yk) / np.maximum(V0, 1e-9), 1.0)
        out = np.clip(np.round(img.astype(np.float64) * ratio[..., None]), 0, 255).astype(np.uint8)

        b, d = stats(img, M, opaque, tlab), stats(out, M, opaque, tlab)
        _, _, V1 = hsv(out)
        H0, _, _ = hsv(img)
        H1, S1, _ = hsv(out)
        dH = np.abs(((H1[M] - H0[M] + 180) % 360) - 180)
        dS = np.abs(S1[M] - S0[M])
        sat_b, sat_d = int((V0[M] >= 255).sum()), int((V1[M] >= 255).sum())
        fora = hair & ~M
        ring_in = M & ndimage.binary_dilation(fora)
        ring_out = fora & ndimage.binary_dilation(M)
        step_b = float(V0[ring_in].mean() - V0[ring_out].mean()) if ring_out.any() else float("nan")
        step_d = float(V1[ring_in].mean() - V1[ring_out].mean()) if ring_out.any() else float("nan")

        print(f"\n=== {name} | mascara S cobre {M.sum()/hair.sum()*100:.1f}% do cabelo ===")
        print(f"V na mascara S: p50 {p50:.1f} p90 {p90:.1f} | teto da mediana com a razao preservada: {teto:.1f}"
              f" | mediana aplicada: {alvo:.1f} ({modo}) | ganho {g:.4f}")
        print(f"{'metrica':26} {'antes':>9} {'depois':>9}")
        for k, lbl, fmt in [("H", "H mediana", "{:9.2f}"), ("S", "S mediana", "{:9.3f}"),
                            ("V50", "V p50", "{:9.1f}"), ("V90", "V p90", "{:9.1f}"),
                            ("razao", "razao p90/p50", "{:9.4f}"), ("faixa", "p95/p5 lum, pelo opaco", "{:9.2f}"),
                            ("dE", "dE76 p90-p98", "{:9.1f}")]:
            print(f"{lbl:26} {fmt.format(b[k])} {fmt.format(d[k])}")
        print(f"{'faixa dinamica':26} {(d['faixa']/b['faixa']-1)*100:+8.1f}%")
        print(f"{'pixels V=255 na mascara':26} {sat_b:9d} {sat_d:9d}   ({sat_d/M.sum()*100:.1f}% da mascara depois)")
        print(f"{'degrau V na borda':26} {step_b:+9.1f} {step_d:+9.1f}   (dentro menos fora da mascara S)")
        print(f"{'efeito em H, graus':26} mediana {np.median(dH):.2f}  p99 {np.percentile(dH, 99):.2f}")
        print(f"{'efeito em S':26} mediana {np.median(dS):.4f}  p99 {np.percentile(dS, 99):.4f}")

        if a.apply:
            os.makedirs(a.out, exist_ok=True)
            Image.fromarray(out).save(os.path.join(a.out, f"{name}.png"))
            W = 627
            pair = Image.new("RGB", (W * 2 + 8, W + 24), "white")
            dr = ImageDraw.Draw(pair)
            for i, (arr, lbl) in enumerate([(img, "antes"), (out, f"depois: mediana {alvo:.1f}, razao preservada")]):
                pair.paste(Image.fromarray(arr).resize((W, W), Image.LANCZOS), (i * (W + 8), 24))
                dr.text((i * (W + 8) + 4, 6), lbl, fill="black")
            pair.save(os.path.join(a.out, f"{name}_antes_depois.png"))
            ys, xs = np.where(hair)
            cy, cx = int(np.percentile(ys, 35)), int(np.median(xs))
            y0, x0 = max(cy - 170, 0), max(cx - 260, 0)
            z = Image.new("RGB", (520 * 2 + 8, 340), "white")
            z.paste(Image.fromarray(img[y0:y0 + 340, x0:x0 + 520]), (0, 0))
            z.paste(Image.fromarray(out[y0:y0 + 340, x0:x0 + 520]), (528, 0))
            z.save(os.path.join(a.out, f"{name}_zoom.png"))
            print(f"gravados em {a.out}: {name}.png, {name}_antes_depois.png, {name}_zoom.png")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure")
    m.add_argument("files", nargs="+")
    m.add_argument("--hex", required=True)
    m.add_argument("--v90-min", type=float)
    f = sub.add_parser("fix-value")
    f.add_argument("files", nargs="+")
    f.add_argument("--hex", required=True)
    f.add_argument("--target-median", type=float, default=176.0)
    f.add_argument("--apply", action="store_true")
    f.add_argument("--out")
    a = ap.parse_args()
    if a.cmd == "fix-value" and a.apply and not a.out:
        ap.error("--apply exige --out")
    {"measure": cmd_measure, "fix-value": cmd_fix}[a.cmd](a)


if __name__ == "__main__":
    main()
