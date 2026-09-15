"""Resolve E e T por pixel e por canal a partir de DOIS renders da mesma camada sobre duas bases:

    L1 = E + T*S    (render sobre tmp_1: raw/<camada>.png)
    L4 = E + T*B    (render sobre tmp_4: raw/_referencia/<camada>_tmp4_*.png)
    T = (L1 - L4) / (S - B);   E = L1 - T*S           (luz linear, por canal)

Sem limiar, sem classificar pixel, sem parâmetro escolhido. O que se mede:
  1. desalinhamento entre os dois renders (silhueta e máscara de pelo): permite resolver por pixel
     ou só por região? a que granularidade?
  2. E e T caem em [0,1]? E <= L1? (fora disso o modelo não fecha)
  3. E e T por região anatômica (controle, banda, núcleo) e a composição sobre outras bases.

Uso (de fora do repo): python scripts/medicao/medir_ET.py [--layer hair_buzz] [--ref raw/_referencia/x.png]
"""
import argparse, glob, importlib.util, os
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.environ.get("MEDICAO_OUT", os.getcwd())

code = open(os.path.join(HERE, "medir_pelo.py"), encoding="utf8").read()
g = {"__file__": os.path.join(HERE, "medir_pelo.py")}
exec(code[:code.index("# ---------------------------------------------------------------- 1. distribuição")], g)
lin, srgb8, silhouette = g["lin"], g["srgb8"], g["silhouette"]

spec = importlib.util.spec_from_file_location("extract_layers", os.path.join(ROOT, "scripts", "extract-layers.py"))
XL = importlib.util.module_from_spec(spec); spec.loader.exec_module(XL)

def rgb(path):
    return np.asarray(Image.open(path).convert("RGB"))

def Y(l):
    return 0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]

def boundary_displacement(m_from, m_to):
    """Para cada pixel de borda de m_from, distância à borda de m_to (px). Mediana e p90."""
    b_from = m_from & ~ndimage.binary_erosion(m_from)
    b_to = m_to & ~ndimage.binary_erosion(m_to)
    d = ndimage.distance_transform_edt(~b_to)[b_from]
    return float(np.median(d)), float(np.percentile(d, 90))

def block_mean(a, b):
    """Média por blocos b x b (H, W múltiplos por corte)."""
    H, W = a.shape[:2]
    h, w = H // b * b, W // b * b
    x = a[:h, :w]
    if a.ndim == 3:
        return x.reshape(h // b, b, w // b, b, 3).mean(axis=(1, 3))
    return x.reshape(h // b, b, w // b, b).mean(axis=(1, 3))

def upsample(a, b, H, W):
    r = np.repeat(np.repeat(a, b, axis=0), b, axis=1)
    out = np.zeros((H, W) + a.shape[2:], a.dtype)
    out[:r.shape[0], :r.shape[1]] = r
    return out

def solve(L1, L4, S, B):
    den = S - B
    T = np.where(np.abs(den) > 1e-4, (L1 - L4) / np.where(np.abs(den) > 1e-4, den, 1), np.nan)
    E = L1 - T * S
    return E, T

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", default="hair_buzz")
    ap.add_argument("--ref", default=None)
    a = ap.parse_args()
    ref_path = a.ref or sorted(glob.glob(os.path.join(ROOT, "raw", "_referencia", f"{a.layer}_tmp4_*.png")))[0]

    S8, B8 = rgb(os.path.join(ROOT, "raw", "tmp_1.png")), rgb(os.path.join(ROOT, "raw", "tmp_4.png"))
    L1_8, L4_8 = rgb(os.path.join(ROOT, "raw", f"{a.layer}.png")), rgb(ref_path)
    lay = np.asarray(Image.open(os.path.join(ROOT, "layers", f"{a.layer}.png")).convert("RGBA"))
    S, B, L1, L4 = lin(S8), lin(B8), lin(L1_8), lin(L4_8)
    H, W = S.shape[:2]
    sil1, sil4, silr = silhouette(S8), silhouette(B8), silhouette(L4_8)
    SIL = sil1 & sil4 & silr

    # regiões pela camada nativa (uma vez)
    lr, sr = lin(lay[..., 0]), S[..., 0]
    r = np.where(sr > 0, lr / np.where(sr > 0, sr, 1), 0)
    HAIR = (lay[..., 3] > 0) & SIL
    MIOLO = (lay[..., 3] > 200) & SIL
    CORE = MIOLO & (r < 0.15)
    BAND = MIOLO & (r >= 0.15) & (r < 0.85)
    ys, xs = np.nonzero(lay[..., 3] > 0)
    cols = (xs > W * 0.42) & (xs < W * 0.58)
    hb = int(np.percentile(ys[cols], 99))
    CONTROL = np.zeros_like(SIL); CONTROL[hb + 40:hb + 140, int(W * 0.42):int(W * 0.58)] = True
    CONTROL &= SIL & ~(lay[..., 3] > 0)

    # ---------------------------------------------------------------- 1. desalinhamento
    print(f"== {a.layer}: {os.path.relpath(ref_path, ROOT)} ==")
    m_nat, _ = XL.build_mask(S8, L1_8)
    m_ref, _ = XL.build_mask(B8, L4_8)
    print("\n== 1. desalinhamento entre os dois renders ==")
    print(f"silhueta: IoU {((sil1 & silr).sum() / (sil1 | silr).sum()):.4f}; deslocamento de borda tmp_1->ref mediana/p90 {boundary_displacement(sil1, silr)[0]:.1f}/{boundary_displacement(sil1, silr)[1]:.1f} px")
    print(f"máscara de pelo (receita da extração em cada par): IoU {((m_nat & m_ref).sum() / (m_nat | m_ref).sum()):.4f}; "
          f"área nativa {m_nat.sum():,} px, ref {m_ref.sum():,} px; deslocamento de borda nat->ref mediana/p90 "
          f"{boundary_displacement(m_nat, m_ref)[0]:.1f}/{boundary_displacement(m_nat, m_ref)[1]:.1f} px, ref->nat {boundary_displacement(m_ref, m_nat)[0]:.1f}/{boundary_displacement(m_ref, m_nat)[1]:.1f} px")

    # máscaras por critério RELATIVO (razão à própria base < 0,7), igual nos dois renders: separa geometria
    # de sensibilidade do limiar absoluto (|dif| > 16 pega menos pelo escuro sobre base escura)
    rel_nat = SIL & (Y(L1) / np.maximum(Y(S), 1e-6) < 0.7)
    rel_ref = SIL & (Y(L4) / np.maximum(Y(B), 1e-6) < 0.7)
    for m_ in (rel_nat, rel_ref):
        m_[:] = ndimage.binary_opening(m_, iterations=2)
    print(f"máscara por critério relativo (Y/Y(base) < 0,7, mesmo nos dois): IoU {((rel_nat & rel_ref).sum() / (rel_nat | rel_ref).sum()):.4f}; "
          f"área nativa {rel_nat.sum():,} px, ref {rel_ref.sum():,} px; deslocamento de borda nat->ref mediana/p90 "
          f"{boundary_displacement(rel_nat, rel_ref)[0]:.1f}/{boundary_displacement(rel_nat, rel_ref)[1]:.1f} px")
    # linha do cabelo nas colunas centrais: primeira linha (de baixo para cima) em que a razão cai abaixo de 0,7
    def hairline(mask):
        c0, c1 = int(W * 0.45), int(W * 0.55)
        col = mask[:, c0:c1].mean(axis=1) > 0.5
        rows = np.nonzero(col)[0]
        return int(rows.max()) if rows.size else -1
    print(f"linha do cabelo (colunas centrais, última linha com pelo): nativa y={hairline(rel_nat)}, ref y={hairline(rel_ref)}")

    # ---------------------------------------------------------------- 2. solução por pixel e por bloco
    print("\n== 2. E e T por granularidade (blocos b x b; b = 1 é por pixel). Fração dentro dos limites, no pelo ==")
    print(f"{'b':>3} {'T<0':>6} {'T>1':>6} {'E<0':>6} {'E>L1':>6} | {'T p50 núcleo':>12} {'E/L1 núcleo':>11} | {'T p50 banda':>11} {'E/L1 banda':>10} | {'T p50 controle':>14} {'E/L1 controle':>13} | {'|ΔT| vs 2b':>10} {'recon L4 rms':>12}")
    prev_T = None
    results = {}
    for b in [1, 2, 4, 8, 16, 32, 64]:
        if b == 1:
            E, T = solve(L1, L4, S, B)
        else:
            Eb, Tb = solve(block_mean(L1, b), block_mean(L4, b), block_mean(S, b), block_mean(B, b))
            E, T = upsample(Eb, b, H, W), upsample(Tb, b, H, W)
        results[b] = (E, T)
        Tr, Er = T[..., 0], E[..., 0]  # canal R para os limites; os outros na mesma ordem
        m = HAIR & np.isfinite(Tr)
        frac = lambda c: float(c[m].mean() * 100)
        row = [frac(Tr < 0), frac(Tr > 1), frac(Er < 0), frac(Er > L1[..., 0])]
        def reg(mask):
            mm = mask & np.isfinite(Tr)
            return float(np.median(Tr[mm])), float(np.median((Er / np.maximum(L1[..., 0], 1e-6))[mm]))
        tc, ec = reg(CORE); tb, eb = reg(BAND); tk, ek = reg(CONTROL)
        dT = float(np.nanmedian(np.abs(Tr - prev_T)[m])) if prev_T is not None else float("nan")
        recon = E + T * B
        rms = float(np.sqrt(np.mean((srgb8(Y(recon)).astype(float) - srgb8(Y(L4)).astype(float))[HAIR] ** 2)))
        print(f"{b:3d} {row[0]:5.1f}% {row[1]:5.1f}% {row[2]:5.1f}% {row[3]:5.1f}% | {tc:12.3f} {ec:11.2f} | {tb:11.3f} {eb:10.2f} | {tk:14.3f} {ek:13.2f} | {dT:10.3f} {rms:12.1f}")
        prev_T = Tr

    # onde E < 0 cai (b = 1 e b = 8): por região, e distância à linha do cabelo nativa
    for b in [1, 8]:
        E, T = results[b]
        neg = HAIR & np.isfinite(E[..., 0]) & (E[..., 0] < 0)
        n = neg.sum()
        inref = neg & rel_ref
        print(f"\nE<0 em b={b}: {n:,} px = {n / HAIR.sum() * 100:.1f}% do pelo; no núcleo {(neg & CORE).sum() / max(n, 1) * 100:.0f}%, "
              f"na banda {(neg & BAND).sum() / max(n, 1) * 100:.0f}%, fora do miolo {(neg & ~MIOLO).sum() / max(n, 1) * 100:.0f}%; "
              f"dentro da máscara relativa da REF {inref.sum() / max(n, 1) * 100:.0f}% (fora dela = onde a ref tem pele e o nativo tem pelo)")
        if b == 8:
            vis = srgb8(L4).copy()
            vis[neg] = [255, 40, 40]
            vis[rel_nat & ~rel_ref & ~neg] = [40, 120, 255]
            Image.fromarray(vis[y0:y1, x0:x1] if False else vis[40:560, 250:1004]).save(os.path.join(OUT, f"ET_{a.layer}_b8_Eneg_vermelho_soNativo_azul.png"))

    # ---------------------------------------------------------------- 3. E e T por canal, em b = 8 e 32
    for b in [8, 32]:
        E, T = results[b]
        print(f"\n== 3. b = {b}: medianas por canal (R, G, B) ==")
        for nome, mask in [("controle", CONTROL), ("banda", BAND), ("núcleo", CORE)]:
            mm = mask & np.isfinite(T[..., 0])
            tm = [float(np.median(T[..., c][mm])) for c in range(3)]
            em = [float(np.median(E[..., c][mm])) for c in range(3)]
            el = [float(np.median((E[..., c] / np.maximum(L1[..., c], 1e-6))[mm])) for c in range(3)]
            print(f"  {nome:9} T {tm[0]:.3f}/{tm[1]:.3f}/{tm[2]:.3f}   E(lin) {em[0]:.4f}/{em[1]:.4f}/{em[2]:.4f}   E/L1 {el[0]:.2f}/{el[1]:.2f}/{el[2]:.2f}")

    # ---------------------------------------------------------------- 4. composição sobre outras bases
    print("\n== 4. novo = E + T*base sobre tmp_1 (identidade), tmp_2, tmp_3, tmp_4 (reconstrução), b = 8 e 32 ==")
    bases = {n: lin(rgb(os.path.join(ROOT, "raw", f"{n}.png"))) for n in ["tmp_1", "tmp_2", "tmp_3", "tmp_4"]}
    y0, y1, x0, x1 = 40, 560, 250, 1004
    for b in [8, 32]:
        E, T = results[b]
        Ec, Tc = np.nan_to_num(np.clip(E, 0, None)), np.nan_to_num(np.clip(T, 0, 1))
        row = []
        for n, base in bases.items():
            out = Ec + Tc * base
            # fora do pelo a camada não existe: mostra a base
            comp = np.where(HAIR[..., None], out, base)
            comp8 = srgb8(comp)
            row.append(comp8[y0:y1, x0:x1])
            tgt = {"tmp_1": L1, "tmp_4": L4}.get(n)
            if tgt is not None:
                d = np.abs(srgb8(Y(comp)).astype(float) - srgb8(Y(tgt)).astype(float))[HAIR]
                print(f"  b={b:2d} {n}: |ΔL| média {d.mean():.2f}, p95 {np.percentile(d, 95):.1f} (contra o render real)")
        sep = np.full((y1 - y0, 6, 3), 255, np.uint8)
        img = [row[0]]
        for c in row[1:]: img += [sep, c]
        Image.fromarray(np.concatenate(img, 1)).save(os.path.join(OUT, f"ET_{a.layer}_b{b}_tmp1_tmp2_tmp3_tmp4.png"))
        # mapas E e T (canal R) no recorte
        tv = np.clip(np.nan_to_num(T[..., 0]), 0, 1)[y0:y1, x0:x1]
        ev = np.clip(np.nan_to_num(E[..., 0]) / 0.05, 0, 1)[y0:y1, x0:x1]
        Image.fromarray(np.concatenate([(tv * 255).astype(np.uint8), np.full((y1 - y0, 6), 255, np.uint8), (ev * 255).astype(np.uint8)], 1)).save(os.path.join(OUT, f"ET_{a.layer}_b{b}_mapas_T_E.png"))
    print("imagens em", OUT)

if __name__ == "__main__":
    main()
