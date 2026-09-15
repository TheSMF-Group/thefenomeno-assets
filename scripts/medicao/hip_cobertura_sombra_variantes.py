"""Auxiliar de hip_cobertura_sombra: por que o modelo não separa pelo de pele nesta batelada.

1. trajetória do MLE de H (|H| e direção por iteração): converge ou deriva?
2. ângulo cromático por pixel entre L e S no núcleo (r<0,15), na banda e no pelo sobre branco;
3. a regra com H = observação direta (H_out) e com a direção do MLE em magnitude fixa, no buzz e nos loiros.
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv = [sys.argv[0]]
src = open(os.path.join(HERE, "hip_cobertura_sombra.py"), encoding="utf8").read()
g = {"__file__": os.path.join(HERE, "hip_cobertura_sombra.py")}
exec(src[:src.index("# ---------------------------------------------------------------- 1. H por camada")], g)
for k in ["A", "OUT", "lin", "load", "silhouette", "srgb8", "layer512", "base512", "hair_edge", "over", "SRC", "SIL", "SRC_F", "SIL_F",
          "Y", "L8", "rmap", "fit_au", "estimate_H", "angle", "hexof", "init_H", "H_out_direct", "apply_rule", "alone", "save_row"]:
    globals()[k] = g[k]

def ang_pix(Lp, Sp):
    c = (Lp * Sp).sum(1) / np.maximum(np.linalg.norm(Lp, axis=1) * np.linalg.norm(Sp, axis=1), 1e-12)
    return np.degrees(np.arccos(np.clip(c, -1, 1)))

# ---------------------------------------------------------------- 1. trajetória do MLE
print("== 1. trajetória do MLE de H no hair_buzz (512) ==")
lay = layer512("hair_buzz"); miolo = (lay[..., 3] > 200) & SIL
Lp = lin(lay[..., :3])[miolo]; Sp = lin(SRC[..., :3])[miolo]
Smed = np.median(Sp, axis=0)
H = init_H(lay, SRC, SIL); H0 = H.copy()
print(f"  it {0:5d}  H {hexof(H)} |H| {np.linalg.norm(H):.3f}  H·S° {angle(H, Smed):5.1f}")
for it in range(1, 3001):
    a, u = fit_au(Lp, Sp, H)
    H = np.maximum((a[:, None] * (Lp - u[:, None] * Sp)).sum(0) / (a * a).sum(), 0)
    if it in (1, 5, 20, 100, 300, 1000, 3000):
        res = Lp - (a[:, None] * H[None, :] + u[:, None] * Sp)
        print(f"  it {it:5d}  H {hexof(H)} |H| {np.linalg.norm(H):.3f}  H·S° {angle(H, Smed):5.1f}  a=1 {(a >= 0.999).mean()*100:5.2f}%  res lin {np.sqrt((res*res).sum(1)).mean():.5f}")

# ---------------------------------------------------------------- 2. ângulo cromático por pixel
print("\n== 2. ângulo cromático entre o pixel L e a pele S do mesmo pixel (graus) ==")
print("  se pelo e pele têm a mesma cromaticidade, nenhuma decomposição por cor separa os dois")
print(f"{'camada':22} {'núcleo p50':>10} {'p90':>6} {'banda p50':>10} {'p90':>6} {'pele>0,85 p50':>13} | {'fora, vs branco p50':>19} {'p90':>6} {'fora vs S mediana':>17}")
for name in ["hair_buzz", "hair_midcurly", "hair_braids", "beard_goatee", "brow_thick", "hair_buzz_blonde", "hair_midcurly_blonde"]:
    lay = layer512(name); miolo = (lay[..., 3] > 200) & SIL
    r = rmap(lay, SRC)
    Lp = lin(lay[..., :3]); Sp = lin(SRC[..., :3])
    core = miolo & (r < 0.15); band = miolo & (r >= 0.15) & (r <= 0.85); pele = miolo & (r > 0.85)
    fora = (lay[..., 3] > 200) & ~SIL
    def q(m):
        if m.sum() == 0: return (float("nan"), float("nan"))
        d = ang_pix(Lp[m], Sp[m]); return (np.median(d), np.percentile(d, 90))
    c, b, p = q(core), q(band), q(pele)
    if fora.sum():
        dw = ang_pix(Lp[fora], np.ones((fora.sum(), 3)))
        ds = ang_pix(Lp[fora], np.tile(np.median(Sp[miolo], axis=0), (fora.sum(), 1)))
        f = f"{np.median(dw):19.1f} {np.percentile(dw, 90):6.1f} {np.median(ds):17.1f}"
    else:
        f = f"{'-':>19} {'-':>6} {'-':>17}"
    print(f"{name:22} {c[0]:10.1f} {c[1]:6.1f} {b[0]:10.1f} {b[1]:6.1f} {p[0]:13.1f} | {f}")
print("  referência: ângulo entre a pele S mediana do miolo e o branco =", f"{angle(np.median(lin(SRC[..., :3])[SIL], axis=0), np.ones(3)):.1f}°")

# ---------------------------------------------------------------- 3. variantes de H
print("\n== 3. variantes de H, camada sozinha sobre MST-10 (512) ==")
print("  mancha = px do miolo com L(comp) − L(base) > 10; núcleo dL = |L(novo) − L(nativo)| médio em r<0,15; bright dL = idem nos px mais claros que a pele (loiro)")
print(f"{'camada':22} {'variante':26} {'H hex':>8} {'H·S°':>5} | {'mancha':>7} {'núcleo dL':>9} {'T/r núcleo':>11} | {'bright dL':>9} {'T bright':>8}")
B10 = base512("MST-10")
for name in ["hair_buzz", "hair_midcurly", "beard_goatee", "hair_buzz_blonde", "hair_midcurly_blonde"]:
    lay = layer512(name); miolo = (lay[..., 3] > 200) & SIL
    r = rmap(lay, SRC); core = miolo & (r < 0.15)
    bright = miolo & (Y(lay) > Y(SRC))
    Lp = lin(lay[..., :3])[miolo]; Sp = lin(SRC[..., :3])[miolo]; Smed = np.median(Sp, axis=0)
    Hm, _, _ = estimate_H(Lp, Sp, init_H(lay, SRC, SIL))
    Ho, n_out = H_out_direct(lay, SIL)
    variants = [("MLE (300 it)", Hm)]
    if Ho is not None:
        variants.append((f"H_out direto (n={n_out})", Ho))
        # magnitude de H_out escalada até o pixel mais claro do núcleo na direção de H_out (a<=1 nunca ativa)
        proj = (Lp @ Ho) / (Ho @ Ho)
        variants.append(("H_out dir, |H| = max proj", Ho * max(proj.max(), 1e-9)))
    variants.append(("dir MLE, |H| = |H_out|" if Ho is not None else "dir MLE, |H| = 0,5·|MLE|", Hm / np.linalg.norm(Hm) * (np.linalg.norm(Ho) if Ho is not None else 0.5 * np.linalg.norm(Hm))))
    nat = over(B10, lay); Lb = L8(B10)
    for vname, Hv in variants:
        new, T, a, _ = apply_rule(lay, SRC, B10, Hv)
        comp = over(B10, new)
        st = int(((L8(comp) - Lb) > 10)[miolo].sum())
        cdl = np.abs(L8(comp) - L8(nat))[core].mean() if core.any() else float("nan")
        tr = f"{np.median(T[core]):.3f}/{np.median(r[core]):.3f}" if core.any() else "-"
        bdl = (L8(comp) - L8(nat))[bright].mean() if bright.any() else float("nan")
        tb = np.median(T[bright]) if bright.any() else float("nan")
        print(f"{name:22} {vname:26} {hexof(Hv):>8} {angle(Hv, Smed):5.1f} | {st:7,} {cdl:9.2f} {tr:>11} | {bdl:+9.2f} {tb:8.3f}")
        if name == "hair_buzz" and vname.startswith("H_out direto"):
            save_row("hair_buzz_MST-10_hoje_regraHout.png", [alone(lay, B10, "r"), comp])
    if name == "hair_buzz":
        print(f"  w = r: núcleo dL {np.abs(L8(alone(lay, B10, 'r')) - L8(nat))[core].mean():.2f}; w = 1: {np.abs(L8(alone(lay, B10, '1')) - L8(nat))[core].mean():.2f}")

# ---------------------------------------------------------------- 4. degenerescência: a mesma L, duas leituras
print("\n== 4. degenerescência no núcleo do buzz com H = H_out: resíduo da leitura 'é pelo' contra 'é pele sombreada' ==")
lay = layer512("hair_buzz"); miolo = (lay[..., 3] > 200) & SIL; r = rmap(lay, SRC); core = miolo & (r < 0.15)
Lp = lin(lay[..., :3])[core]; Sp = lin(SRC[..., :3])[core]
Ho, _ = H_out_direct(lay, SIL)
# leitura pelo: a = proj em H, u = 0; leitura pele: a = 0, u = proj em S
a_h = np.clip((Lp @ Ho) / (Ho @ Ho), 0, 1); res_h = np.linalg.norm(Lp - a_h[:, None] * Ho[None, :], axis=1)
u_s = np.clip((Lp * Sp).sum(1) / (Sp * Sp).sum(1), 0, 1); res_s = np.linalg.norm(Lp - u_s[:, None] * Sp, axis=1)
lvl = lambda x: srgb8(x).astype(float)
print(f"  |L| mediano no núcleo {np.median(np.linalg.norm(Lp, axis=1)):.4f} (linear)")
print(f"  resíduo 'só pelo' mediano {np.median(res_h):.5f}, 'só pele sombreada' {np.median(res_s):.5f}; pele ganha em {(res_s < res_h).mean()*100:.1f}% dos px do núcleo")
print(f"  em níveis sRGB da luminância: pelo {np.median(np.abs(lvl(0.2126*Lp[:,0]+0.7152*Lp[:,1]+0.0722*Lp[:,2]) - lvl(a_h*(0.2126*Ho[0]+0.7152*Ho[1]+0.0722*Ho[2])))):.1f}, pele {np.median(np.abs(lvl(0.2126*Lp[:,0]+0.7152*Lp[:,1]+0.0722*Lp[:,2]) - lvl(u_s*(0.2126*Sp[:,0]+0.7152*Sp[:,1]+0.0722*Sp[:,2])))):.1f}")
