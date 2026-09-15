"""Regra candidata: w(r) por TABELA MEDIDA na referência, aplicada por pixel ao render nativo.

    novo = L - w(r) * r * (S - B)          (= E + T*B com T = w(r)*r, E = (1 - w(r))*L)

w(r) = mediana de T/r por faixa de r, resolvida em blocos de 8 px a partir de dois renders da mesma
camada (tmp_1 e tmp_4). Nenhum parâmetro escolhido: a tabela é medição; a aplicação por pixel usa o
render nativo, alinhado por construção. Interpolação linear entre os centros das faixas; fora da
tabela, o valor da ponta. Por canal.

Calibra em --calib e testa em --test (referências distintas = teste fora da amostra).
Uso (de fora do repo): python scripts/medicao/medir_w_de_r.py --calib raw/_referencia/x_1.png --test raw/_referencia/x_2.png
"""
import argparse, os
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.environ.get("MEDICAO_OUT", os.getcwd())
code = open(os.path.join(HERE, "medir_pelo.py"), encoding="utf8").read()
g = {"__file__": os.path.join(HERE, "medir_pelo.py")}
exec(code[:code.index("# ---------------------------------------------------------------- 1. distribuição")], g)
exec(code[code.index("# ---------------------------------------------------------------- composição"):code.index("GRATIS = {")], g)
lin, srgb8, silhouette, over, hair_edge = (g[k] for k in ["lin", "srgb8", "silhouette", "over", "hair_edge"])
layer512, base512, lut, tone_layer, TONE, ORDER, SKIN, OFFSET = (g[k] for k in ["layer512", "base512", "lut", "tone_layer", "TONE", "ORDER", "SKIN", "OFFSET"])

EDGES = np.array([0, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2])

def rgb(p):
    return np.asarray(Image.open(p).convert("RGB"))

def Y(l):
    return 0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]

def blk(a, b):
    h, w = a.shape[0] // b * b, a.shape[1] // b * b
    return a[:h, :w].reshape(h // b, b, w // b, b, *a.shape[2:]).mean(axis=(1, 3))

def control_gain(L4, B, lay, sil):
    """Ganho global do gerador, por canal: mediana de L4/B na testa nua (sem pelo), que por construção
    deveria ser idêntica a tmp_4. Medido no próprio render; remove deriva de exposição, não pelo."""
    H, W = B.shape[:2]
    ys, xs = np.nonzero(lay[..., 3] > 0)
    cols = (xs > W * 0.42) & (xs < W * 0.58)
    hb = int(np.percentile(ys[cols], 99))
    ctrl = np.zeros(B.shape[:2], bool)
    ctrl[hb + 40:hb + 140, int(W * 0.42):int(W * 0.58)] = True
    ctrl &= sil & ~(lay[..., 3] > 0)
    return np.array([np.median((L4[..., c] / np.maximum(B[..., c], 1e-6))[ctrl]) for c in range(3)])

def calibrate(layer, ref_path, b=8, normalize=True):
    """Tabela w(r) por canal: mediana de T/r por faixa de r, em blocos b, dentro do pelo e da silhueta."""
    S8, B8 = rgb(os.path.join(ROOT, "raw", "tmp_1.png")), rgb(os.path.join(ROOT, "raw", "tmp_4.png"))
    S, B = lin(S8), lin(B8)
    L1, L4 = lin(rgb(os.path.join(ROOT, "raw", f"{layer}.png"))), lin(rgb(ref_path))
    lay = np.asarray(Image.open(os.path.join(ROOT, "layers", f"{layer}.png")).convert("RGBA"))
    if normalize:
        gain = control_gain(L4, B, lay, silhouette(S8) & silhouette(B8) & silhouette(rgb(ref_path)))
        print(f"  ganho de controle de {os.path.basename(ref_path)} (R/G/B): {gain[0]:.3f}/{gain[1]:.3f}/{gain[2]:.3f} -> referência dividida por ele")
        L4 = L4 / gain
    Sb, Bb, L1b, L4b = blk(S, b), blk(B, b), blk(L1, b), blk(L4, b)
    sil = silhouette(S8) & silhouette(B8) & silhouette(rgb(ref_path))
    m = (blk(sil.astype(float)[..., None], b)[..., 0] > 0.99) & (blk((lay[..., 3] > 0).astype(float)[..., None], b)[..., 0] > 0.5)
    r = L1b / np.maximum(Sb, 1e-6)
    T = (L1b - L4b) / np.where(np.abs(Sb - Bb) > 1e-4, Sb - Bb, np.nan)
    table = np.full((3, len(EDGES) - 1), np.nan)
    for c in range(3):
        for i, (lo, hi) in enumerate(zip(EDGES[:-1], EDGES[1:])):
            mm = m & (r[..., c] >= lo) & (r[..., c] < hi) & np.isfinite(T[..., c])
            if mm.sum() >= 20:
                table[c, i] = np.median((T[..., c] / np.maximum(r[..., c], 1e-6))[mm])
    return table

def w_of_r(r, table):
    """Interpolação linear nos centros das faixas, por canal; fora da tabela, valor da ponta; clip [0,1]."""
    centers = (EDGES[:-1] + EDGES[1:]) / 2
    out = np.empty_like(r)
    for c in range(3):
        ok = np.isfinite(table[c])
        out[..., c] = np.interp(r[..., c], centers[ok], table[c][ok])
    return np.clip(out, 0, 1)

def apply_rule(lay_rgba, src_rgba, base_rgba, table):
    """Por pixel: novo = L - w(r)*r*(S - B), alpha intocado. Mesma assinatura que hair_edge."""
    L, S, B = lin(lay_rgba[..., :3]), lin(src_rgba[..., :3]), lin(base_rgba[..., :3])
    r = np.where(S > 0, L / np.where(S > 0, S, 1), 0)
    w = w_of_r(r, table)
    out = lay_rgba.copy()
    out[..., :3] = srgb8(L - w * r * (S - B))
    return out

def region_stats(comp, base, lay, S8, sil, label):
    lr, sr = lin(lay[..., 0]), lin(S8)[..., 0]
    r = np.where(sr > 0, lr / np.where(sr > 0, sr, 1), 0)
    MIOLO = (lay[..., 3] > 200) & sil
    CORE = MIOLO & (r < 0.15)
    BAND = MIOLO & (r >= 0.15) & (r < 0.85)
    ratio = Y(lin(comp)) / np.maximum(Y(lin(base)), 1e-6)
    Lc = srgb8(Y(lin(comp))).astype(float)
    c0, c1 = int(comp.shape[1] * 0.42), int(comp.shape[1] * 0.58)
    prof = np.median(ratio[:, c0:c1], axis=1)
    print(f"{label:34} banda p50 {np.median(ratio[BAND]):.2f}  núcleo p50 {np.median(ratio[CORE]):.2f}  "
          f"L núcleo {Lc[CORE].mean():5.1f}  L banda {Lc[BAND].mean():5.1f}  perfil y80/120/160/200: "
          f"{prof[80]:.2f}/{prof[120]:.2f}/{prof[160]:.2f}/{prof[200]:.2f}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", default="hair_buzz")
    ap.add_argument("--calib", required=True)
    ap.add_argument("--test", default=None)
    ap.add_argument("--sem-normalizar", action="store_true", help="não divide a referência pelo ganho de controle")
    a = ap.parse_args()
    table = calibrate(a.layer, a.calib, normalize=not a.sem_normalizar)
    print(f"== tabela w(r) calibrada em {os.path.basename(a.calib)} (mediana de T/r por faixa de r; R/G/B) ==")
    for i, (lo, hi) in enumerate(zip(EDGES[:-1], EDGES[1:])):
        if np.isfinite(table[:, i]).any():
            print(f"  r {lo:4.2f}-{hi:4.2f}: " + "/".join("  nan" if not np.isfinite(v) else f"{v:.3f}" for v in table[:, i]))

    S8, B8 = rgb(os.path.join(ROOT, "raw", "tmp_1.png")), rgb(os.path.join(ROOT, "raw", "tmp_4.png"))
    lay = np.asarray(Image.open(os.path.join(ROOT, "layers", f"{a.layer}.png")).convert("RGBA"))
    S4 = np.dstack([S8, np.full(S8.shape[:2], 255, np.uint8)])
    B4 = np.dstack([B8, np.full(B8.shape[:2], 255, np.uint8)])
    sil = silhouette(S8) & silhouette(B8)
    comp = over(B4, apply_rule(lay, S4, B4, table))[..., :3]
    print("\n== 1254 sobre tmp_4: razão à base por região (regiões pela camada nativa); REF* = normalizada pelo ganho de controle ==")
    for p in [a.calib] + ([a.test] if a.test else []):
        ref8 = rgb(p)
        region_stats(ref8, B8, lay, S8, sil, f"REF {os.path.basename(p)}")
        if not a.sem_normalizar:
            gain = control_gain(lin(ref8), lin(B8), lay, sil & silhouette(ref8))
            region_stats(srgb8(lin(ref8) / gain), B8, lay, S8, sil, f"REF* {os.path.basename(p)}")
    region_stats(comp, B8, lay, S8, sil, "w(r) tabela, por pixel")
    region_stats(over(B4, hair_edge(lay, S4, B4, "r"))[..., :3], B8, lay, S8, sil, "w = r")
    region_stats(over(B4, hair_edge(lay, S4, B4, "1"))[..., :3], B8, lay, S8, sil, "w = 1")
    ident = over(S4, apply_rule(lay, S4, S4, table))
    print(f"identidade sobre tmp_1: max |dif| RGB {int(np.abs(ident[..., :3].astype(int) - over(S4, lay)[..., :3].astype(int)).max())}")
    y0, y1, x0, x1 = 40, 560, 250, 1004
    row = [rgb(a.calib)[y0:y1, x0:x1]] + ([rgb(a.test)[y0:y1, x0:x1]] if a.test else []) + [comp[y0:y1, x0:x1]]
    sep = np.full((y1 - y0, 6, 3), 255, np.uint8)
    img = [row[0]]
    for c in row[1:]:
        img += [sep, c]
    Image.fromarray(np.concatenate(img, 1)).save(os.path.join(OUT, f"wr_{a.layer}_ref_vs_regra_1254.png"))

    # gate em 512: rosto grátis, w(r) no buzz, w = 1 nas de sombra
    src512 = g["load"](os.path.join(ROOT, "build", "source.webp"))
    GR = {"ear": "ear_normal", "eye": "eye_almond", "brow": "brow_medium", "nose": "nose_medium",
          "beard": "beard_stubble", "mouth": "mouth_medium", "hair": a.layer}
    W1 = {"beard_stubble", "brow_thin", "brow_medium"}

    def face(tid, rule):
        base = base512(tid)
        Lt = lut(TONE[tid]["k"])
        cv = base.copy()
        for slot in ORDER:
            n = GR[slot]
            l = layer512(n)
            if slot in SKIN:
                cv = over(cv, tone_layer(l, Lt), OFFSET.get(n, 0))
            elif n in W1:
                cv = over(cv, hair_edge(l, src512, base, "1"))
            elif rule == "tabela":
                cv = over(cv, apply_rule(l, src512, base, table))
            else:
                cv = over(cv, hair_edge(l, src512, base, rule))
        return cv

    sil512 = silhouette(src512[..., :3])
    print("\n== gate 512 (rosto grátis; stubble e brow_medium em w = 1) ==")
    for tid in ["MST-10", "MST-05", "MST-01"]:
        base = base512(tid)
        hoje, novo = face(tid, "r"), face(tid, "tabela")
        Lb = srgb8(Y(lin(base[..., :3]))).astype(float)
        stain = lambda im: int((((srgb8(Y(lin(im[..., :3]))).astype(float) - Lb) > 10) & sil512).sum())
        d = np.abs(srgb8(Y(lin(novo[..., :3]))).astype(float) - srgb8(Y(lin(hoje[..., :3]))).astype(float))[sil512]
        print(f"  {tid}: mancha hoje {stain(hoje):,} -> w(r) {stain(novo):,} px; |dL| vs hoje na silhueta: média {d.mean():.1f}, >10 em {(d > 10).mean() * 100:.1f}%")
        sep = np.full((512, 8, 3), 255, np.uint8)
        Image.fromarray(np.concatenate([hoje[..., :3], sep, novo[..., :3]], 1)).save(os.path.join(OUT, f"wr_gate_{tid}_hoje_regra.png"))
    print("imagens em", OUT)

if __name__ == "__main__":
    main()
