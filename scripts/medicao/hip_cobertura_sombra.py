"""Hipótese cobertura_sombra (medição, sem implementar).

Modelo por pixel de PELO, em luz linear, por canal:
    L = a·H + (1 − a)·s·S           0 <= a <= 1 (cobertura de pelo), 0 <= s <= 1 (sombra na pele)
H é a cor do pelo da camada (3 canais, absoluta). Reparametrizando u = (1 − a)·s:
    L = a·H + u·S,   a >= 0, u >= 0, a + u <= 1
que é um mínimo quadrado linear em (a, u) sobre um triângulo, resolvido em forma fechada por pixel
(ponto interior ou melhor ponto das três arestas). Na formulação geral L = E + T·S:
    T = u = (1 − a)·s,   E = L − T·S
Composição (regra):  novo = L − T·(S − B) = E + T·B.  Sobre B = S devolve L exatamente (identidade).
Variante "modelo puro" novo_puro = a·H + u·B só serve para medir o resíduo do modelo.

H por camada: MLE alternado sob o próprio modelo (dado H ajusta (a,u) por pixel; dado (a,u) ajusta H por
mínimos quadrados) nos pixels do miolo dentro da silhueta. Validado nos cabelos volumosos contra a
observação direta H_out = mediana dos pixels alpha>200 FORA da silhueta (pelo sobre fundo branco).

Rode de fora do repo ou com MEDICAO_OUT apontando para a pasta de imagens.
"""
import json, os, sys, time
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
code = open(os.path.join(HERE, "medir_pelo.py"), encoding="utf8").read()
g = {"__file__": os.path.join(HERE, "medir_pelo.py")}
exec(code[:code.index("# ---------------------------------------------------------------- 1. distribuição")], g)
exec(code[code.index("# ---------------------------------------------------------------- composição"):code.index("GRATIS = {")], g)
A, lin, load, silhouette, srgb8 = (g[k] for k in ["A", "lin", "load", "silhouette", "srgb8"])
layer512, base512, hair_edge, over = (g[k] for k in ["layer512", "base512", "hair_edge", "over"])
lut, tone_layer, TONE, ORDER, SKIN, OFFSET = (g[k] for k in ["lut", "tone_layer", "TONE", "ORDER", "SKIN", "OFFSET"])
OUT = os.environ.get("MEDICAO_OUT", os.getcwd())
os.makedirs(OUT, exist_ok=True)

SRC = load(os.path.join(A, "build", "source.webp"))
SIL = silhouette(SRC[..., :3])
SRC_F = load(os.path.join(A, "raw", "tmp_1.png"))
SIL_F = silhouette(SRC_F[..., :3])
REGUA = 2.89

def Y(rgb):
    l = lin(rgb[..., :3]); return 0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]
def L8(rgb):
    return srgb8(Y(rgb)).astype(np.float64)
def rmap(lay, src):
    lr, sr = lin(lay[..., 0]), lin(src[..., 0])
    return np.where(sr > 0, lr / np.where(sr > 0, sr, 1), 0)
def srgbf(l):
    l = np.maximum(l, 0)
    return 255 * np.where(l <= 0.0031308, 12.92 * l, 1.055 * np.power(l, 1 / 2.4) - 0.055)

# ---------------------------------------------------------------- o ajuste por pixel
def fit_au(Lp, Sp, H):
    """Mínimos quadrados de L ≈ a·H + u·S com a>=0, u>=0, a+u<=1. Lp, Sp: (N,3); H: (3,). Devolve a, u."""
    H = np.asarray(H, dtype=np.float64)
    hh = float(H @ H)
    hs = Sp @ H
    ss = (Sp * Sp).sum(1)
    lh = Lp @ H
    ls = (Lp * Sp).sum(1)
    det = hh * ss - hs * hs
    ok = det > 1e-9 * hh * np.maximum(ss, 1e-12)
    d = np.where(ok, det, 1.0)
    a0 = np.where(ok, (lh * ss - ls * hs) / d, -1.0)
    u0 = np.where(ok, (hh * ls - hs * lh) / d, -1.0)
    inside = ok & (a0 >= 0) & (u0 >= 0) & (a0 + u0 <= 1)
    def res(a, u):
        dd = a[:, None] * H[None, :] + u[:, None] * Sp - Lp
        return (dd * dd).sum(1)
    # aresta a = 0
    a1 = np.zeros(len(Lp)); u1 = np.clip(ls / np.maximum(ss, 1e-12), 0, 1)
    # aresta u = 0
    a2 = np.clip(lh / max(hh, 1e-12), 0, 1); u2 = np.zeros(len(Lp))
    # aresta a + u = 1
    D = H[None, :] - Sp
    a3 = np.clip(((Lp - Sp) * D).sum(1) / np.maximum((D * D).sum(1), 1e-12), 0, 1); u3 = 1 - a3
    R = np.stack([res(a1, u1), res(a2, u2), res(a3, u3)], 1)
    k = R.argmin(1)
    a = np.choose(k, [a1, a2, a3]); u = np.choose(k, [u1, u2, u3])
    a = np.where(inside, a0, a); u = np.where(inside, u0, u)
    return a, u

def estimate_H(Lp, Sp, H0, iters=300, tol=1e-7):
    """MLE alternado de H sob o modelo. Devolve H, iterações, resíduo médio (linear)."""
    H = np.asarray(H0, dtype=np.float64).copy()
    for it in range(iters):
        a, u = fit_au(Lp, Sp, H)
        den = float((a * a).sum())
        if den <= 0:
            break
        Hn = np.maximum((a[:, None] * (Lp - u[:, None] * Sp)).sum(0) / den, 0)
        step = np.abs(Hn - H).max()
        H = Hn
        if step < tol:
            break
    a, u = fit_au(Lp, Sp, H)
    resid = Lp - (a[:, None] * H[None, :] + u[:, None] * Sp)
    return H, it + 1, float(np.sqrt((resid * resid).sum(1)).mean())

def angle(u, v):
    u = np.asarray(u, float); v = np.asarray(v, float)
    c = (u @ v) / max(np.linalg.norm(u) * np.linalg.norm(v), 1e-12)
    return float(np.degrees(np.arccos(np.clip(c, -1, 1))))

def hexof(Hlin):
    return "#" + "".join(f"{int(v):02x}" for v in srgb8(np.asarray(Hlin)))

def init_H(lay, src, sil):
    """Inicialização do MLE: mediana RGB linear do quartil mais escuro (Y) do miolo dentro da silhueta.
    Só inicialização; a sensibilidade a ela é medida abaixo."""
    miolo = (lay[..., 3] > 200) & sil
    l = lin(lay[..., :3])[miolo]
    y = 0.2126 * l[:, 0] + 0.7152 * l[:, 1] + 0.0722 * l[:, 2]
    q = y <= np.percentile(y, 25)
    return np.median(l[q], axis=0)

def H_out_direct(lay, sil):
    """Observação direta: mediana RGB linear dos pixels alpha>200 FORA da silhueta (pelo sobre branco)."""
    m = (lay[..., 3] > 200) & ~sil
    if m.sum() == 0:
        return None, 0
    return np.median(lin(lay[..., :3])[m], axis=0), int(m.sum())

def H_for(lay, src, sil, verbose_name=None):
    """Estimador adotado: MLE nos pixels do miolo DENTRO da silhueta. Devolve H e diagnóstico."""
    miolo = (lay[..., 3] > 200) & sil
    Lp = lin(lay[..., :3])[miolo]; Sp = lin(src[..., :3])[miolo]
    H0 = init_H(lay, src, sil)
    H, it, res = estimate_H(Lp, Sp, H0)
    # sensibilidade à inicialização: ×0,5, ×2 e mediana do miolo inteiro
    alts = []
    for h0 in [H0 * 0.5, H0 * 2.0, np.median(Lp, axis=0)]:
        Ha, _, _ = estimate_H(Lp, Sp, h0)
        alts.append(angle(Ha, H))
    Smed = np.median(Sp, axis=0)
    diag = {"H": H, "H0": H0, "iters": it, "resid_lin": res, "init_angle_max": max(alts),
            "angle_H_S": angle(H, Smed), "Smed": Smed, "n": int(miolo.sum())}
    return H, diag

# ---------------------------------------------------------------- aplicação da regra
def apply_rule(lay, src, base, H):
    """novo = L − T·(S − B), T = u do ajuste. Devolve rgba novo, T (HxW), a (HxW), resíduo linear (HxWx3)."""
    h, w = lay.shape[:2]
    l = lin(lay[..., :3]); s = lin(src[..., :3]); b = lin(base[..., :3])
    a, u = fit_au(l.reshape(-1, 3), s.reshape(-1, 3), H)
    a = a.reshape(h, w); u = u.reshape(h, w)
    T = u[..., None]
    out = lay.copy()
    out[..., :3] = srgb8(l - T * (s - b))
    resid = l - (a[..., None] * np.asarray(H)[None, None, :] + T * s)
    return out, u, a, resid

def alone(lay, base, mode):
    return over(base, hair_edge(lay, SRC, base, mode))

def save_row(fname, imgs, half=False):
    sep = np.full((imgs[0].shape[0], 8, 3), 255, np.uint8)
    row = [imgs[0][..., :3]]
    for im in imgs[1:]:
        row += [sep, im[..., :3]]
    img = Image.fromarray(np.concatenate(row, axis=1))
    if half:
        img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
    img.save(os.path.join(OUT, fname))

# ---------------------------------------------------------------- 1. H por camada + validação do estimador
PELO = g["PELO"]
ALVO = ["hair_buzz", "beard_goatee", "beard_shortfull", "beard_chinstrap", "hair_lowfade", "beard_mustache", "brow_thick"]
BLONDE = ["hair_buzz_blonde", "hair_midcurly_blonde"]
print("== 1. H por camada (512): MLE dentro da silhueta contra observação direta fora dela ==")
print(f"{'camada':22} {'H_mle hex':>9} {'|H|':>6} {'it':>4} {'res':>7} {'init°':>6} {'H·S°':>6} | {'H_out hex':>9} {'n_out':>7} {'ang mle/out°':>12} {'H_out·S°':>8}")
HS = {}
DIAG = {}
for name in PELO + BLONDE:
    lay = layer512(name)
    H, d = H_for(lay, SRC, SIL)
    Ho, n_out = H_out_direct(lay, SIL)
    HS[name] = H; DIAG[name] = d
    extra = f"{hexof(Ho):>9} {n_out:7,} {angle(H, Ho):12.1f} {angle(Ho, d['Smed']):8.1f}" if Ho is not None else f"{'-':>9} {n_out:7,} {'-':>12} {'-':>8}"
    print(f"{name:22} {hexof(H):>9} {np.linalg.norm(H):6.3f} {d['iters']:4d} {d['resid_lin']:7.4f} {d['init_angle_max']:6.2f} {d['angle_H_S']:6.1f} | {extra}")
print("  init° = maior ângulo entre o H final e o H final partindo de outra inicialização (×0,5, ×2, mediana do miolo)")
print("  H·S° = ângulo entre H e a pele mediana S do miolo: condicionamento da decomposição (0° = indistinguível)")

# ---------------------------------------------------------------- 2. métricas obrigatórias
def metrics(name, tid, H):
    lay = layer512(name); base = base512(tid)
    miolo = (lay[..., 3] > 200) & SIL
    r = rmap(lay, SRC)
    core = miolo & (r < 0.15)
    comp_r = alone(lay, base, "r")
    nat = over(base, lay)
    new_lay, T, a, resid = apply_rule(lay, SRC, base, H)
    comp_n = over(base, new_lay)
    Lb = L8(base)
    st_before = int(((L8(comp_r) - Lb) > 10)[miolo].sum())
    st_after = int(((L8(comp_n) - Lb) > 10)[miolo].sum())
    core_dL = float(np.abs(L8(comp_n) - L8(nat))[core].mean()) if core.any() else -1.0
    core_dL_w1 = float(np.abs(L8(alone(lay, base, "1")) - L8(nat))[core].mean()) if core.any() else -1.0
    # resíduo do modelo em níveis sRGB (média dos 3 canais de |sRGB(L̂) − sRGB(L)|)
    l = lin(lay[..., :3]); lhat = l - resid
    rs = np.abs(srgbf(lhat) - srgbf(l)).mean(axis=2)
    band = miolo & ~core
    # T contra r no miolo
    out = {"layer": name, "tone": tid, "miolo": int(miolo.sum()), "core_n": int(core.sum()),
           "stain_before": st_before, "stain_after": st_after, "stain_pct_after": st_after / max(miolo.sum(), 1) * 100,
           "stain_pct_before": st_before / max(miolo.sum(), 1) * 100,
           "core_dL": core_dL, "core_dL_w1": core_dL_w1,
           "res_mean": float(rs[miolo].mean()), "res_p95": float(np.percentile(rs[miolo], 95)),
           "res_core_mean": float(rs[core].mean()) if core.any() else -1.0,
           "res_band_mean": float(rs[band].mean()) if band.any() else -1.0,
           "res_over_regua_pct": float((rs[miolo] > REGUA).mean() * 100),
           "T_med_core": float(np.median(T[core])) if core.any() else -1.0, "r_med_core": float(np.median(r[core])) if core.any() else -1.0,
           "T_med_band": float(np.median(T[band])) if band.any() else -1.0, "r_med_band": float(np.median(r[band])) if band.any() else -1.0,
           "a_gt0_pct": float((a[miolo] > 0).mean() * 100), "a_eq1_pct": float((a[miolo] >= 0.999).mean() * 100),
           "bound_pct": float(((a + T)[miolo] >= 0.999).mean() * 100)}
    # pixel de erro restante: onde (distância ao pelo opaco)
    if core.any():
        err_after = ((L8(comp_n) - Lb) > 10) & miolo
        if err_after.any():
            dd = ndimage.distance_transform_edt(~core)[err_after]
            out["err_after_dist_p50"] = float(np.median(dd))
    return out, comp_r, comp_n, nat, T, a

def identity(name, H):
    lay = layer512(name)
    new_lay, _, _, _ = apply_rule(lay, SRC, SRC, H)
    return int(np.abs(new_lay[..., :3].astype(int) - lay[..., :3].astype(int)).max())

def mst01_regression(name, H):
    lay = layer512(name); base = base512("MST-01")
    comp_r = alone(lay, base, "r")
    comp_n = over(base, apply_rule(lay, SRC, base, H)[0])
    d = np.abs(L8(comp_n) - L8(comp_r))
    return float((d > 10)[SIL].mean() * 100), float(d[SIL].mean())

print("\n== 2. métricas obrigatórias (512, réplica) ==")
print("mancha = px do miolo com L(composto) − L(base) > 10; nucleo_dL = média |L(novo) − L(nativo w=0)| em r<0,15; resíduo em níveis sRGB (média dos 3 canais)")
hdr = f"{'camada':22} {'tom':6} {'miolo':>7} {'núcleo':>6} | {'mancha w=r':>10} {'mancha nova':>11} {'%miolo':>6} | {'núcleo dL':>9} {'(w=1)':>6} | {'res méd':>7} {'p95':>6} {'núcleo':>6} {'banda':>6} {'>régua%':>7} | {'T/r núcleo':>10} {'T/r banda':>9} | {'a>0%':>5} {'a=1%':>5} {'a+u=1%':>6}"
print(hdr)
RESULTS = []
IMGS = {}
combos = [(n, "MST-10") for n in ALVO] + [("hair_buzz", "MST-05"), ("hair_buzz", "MST-01"), ("beard_goatee", "MST-01"), ("brow_thick", "MST-01")] + [(n, "MST-10") for n in BLONDE]
for name, tid in combos:
    m, comp_r, comp_n, nat, T, a = metrics(name, tid, HS[name])
    RESULTS.append(m)
    IMGS[(name, tid)] = (comp_r, comp_n, nat, T, a)
    print(f"{name:22} {tid:6} {m['miolo']:7,} {m['core_n']:6,} | {m['stain_before']:10,} {m['stain_after']:11,} {m['stain_pct_after']:6.2f} | {m['core_dL']:9.2f} {m['core_dL_w1']:6.1f} | {m['res_mean']:7.2f} {m['res_p95']:6.2f} {m['res_core_mean']:6.2f} {m['res_band_mean']:6.2f} {m['res_over_regua_pct']:7.1f} | {m['T_med_core']:.3f}/{m['r_med_core']:.3f} {m['T_med_band']:.3f}/{m['r_med_band']:.3f} | {m['a_gt0_pct']:5.1f} {m['a_eq1_pct']:5.1f} {m['bound_pct']:6.1f}")

print("\n== 2c. identidade (base = source) e 2e. regressão em MST-01 contra w = r ==")
IDENT = {}; REG01 = {}
for name in ALVO + BLONDE:
    IDENT[name] = identity(name, HS[name])
    REG01[name] = mst01_regression(name, HS[name])
    print(f"  {name:22} identidade max|dif| RGB {IDENT[name]:3d} | MST-01: {REG01[name][0]:5.2f}% da silhueta com |ΔL|>10, |ΔL| médio {REG01[name][1]:.2f}")

# ---------------------------------------------------------------- 2f. loiro: cor do pelo preservada?
print("\n== 2f. loiro sobre MST-10: o pelo continua loiro? ==")
for name in BLONDE:
    lay = layer512(name); base = base512("MST-10")
    comp_r, comp_n, nat, T, a = IMGS[(name, "MST-10")]
    miolo = (lay[..., 3] > 200) & SIL
    yl, ys = Y(lay), Y(SRC)
    bright = miolo & (yl > ys)          # mais claro que a pele que cobre: sob o modelo (s<=1) tem pelo
    dl = L8(comp_n) - L8(nat)
    dr = L8(comp_r) - L8(nat)
    print(f"  {name:22} miolo {miolo.sum():,}; px mais claros que a pele {bright.sum():,} ({bright.mean()/max(miolo.mean(),1e-9)*100:.1f}% do miolo)")
    print(f"    nesses px: ΔL novo vs nativo média {dl[bright].mean():+.2f} (p5 {np.percentile(dl[bright],5):+.1f}, p95 {np.percentile(dl[bright],95):+.1f}); w=r dava {dr[bright].mean():+.2f}; T mediano {np.median(T[bright]):.3f}, a mediano {np.median(a[bright]):.3f}")
    print(f"    miolo inteiro: ΔL novo vs nativo média {dl[miolo].mean():+.2f}; w=r {dr[miolo].mean():+.2f}; % do miolo escurecido >10: novo {(dl[miolo] < -10).mean()*100:.1f}%, w=r {(dr[miolo] < -10).mean()*100:.1f}%")

# ---------------------------------------------------------------- 3. imagens 512
print("\n== 3. imagens 512 ==")
for name, tid in [("hair_buzz", "MST-10"), ("hair_buzz", "MST-01"), ("hair_buzz", "MST-05"), ("beard_goatee", "MST-10"), ("brow_thick", "MST-10"), ("hair_buzz_blonde", "MST-10"), ("hair_midcurly_blonde", "MST-10")]:
    comp_r, comp_n, nat, T, a = IMGS[(name, tid)]
    fn = f"{name}_{tid}_hoje_regra.png"
    save_row(fn, [comp_r, comp_n])
    print("  ", fn)
# mapas T e a do buzz
comp_r, comp_n, nat, T, a = IMGS[("hair_buzz", "MST-10")]
lay = layer512("hair_buzz"); r = rmap(lay, SRC)
def gray(x):
    return np.repeat((np.clip(x, 0, 1) * 255).astype(np.uint8)[..., None], 3, axis=2)
msk = lay[..., 3] > 0
save_row("hair_buzz_mapas_r_T_a.png", [gray(np.where(msk, r, 0)), gray(np.where(msk, T, 0)), gray(np.where(msk, a, 0))])
print("   hair_buzz_mapas_r_T_a.png  (r | T = u | a, preto = 0, branco = 1)")

# ---------------------------------------------------------------- 4. gate: rosto grátis MST-10
print("\n== 4. gate: rosto grátis MST-10 ==")
GR = {"ear": "ear_normal", "eye": "eye_almond", "brow": "brow_medium", "nose": "nose_medium",
      "beard": "beard_stubble", "mouth": "mouth_medium", "hair": "hair_buzz"}
W1 = {"beard_stubble", "brow_thin", "brow_medium"}
def face(tid, parts, buzz_rule):
    base = base512(tid); Lt = lut(TONE[tid]["k"]); cv = base.copy()
    for slot in ORDER:
        n = parts[slot]; lay = layer512(n)
        if slot in SKIN:
            cv = over(cv, tone_layer(lay, Lt), OFFSET.get(n, 0))
        elif n in W1:
            cv = over(cv, hair_edge(lay, SRC, base, "1"))
        elif buzz_rule and n == "hair_buzz":
            cv = over(cv, apply_rule(lay, SRC, base, HS[n])[0])
        else:
            cv = over(cv, hair_edge(lay, SRC, base, "r"))
    return cv
B10 = base512("MST-10")
hoje = face("MST-10", GR, False); nova = face("MST-10", GR, True)
e_h = ((L8(hoje) - L8(B10)) > 10) & SIL; e_n = ((L8(nova) - L8(B10)) > 10) & SIL
buzz_core = (layer512("hair_buzz")[..., 3] > 200) & SIL & (rmap(layer512("hair_buzz"), SRC) < 0.15)
gate_core_dL = float(np.abs(L8(nova) - L8(hoje))[buzz_core].mean())
print(f"  mancha na silhueta: hoje (w=r no buzz, w=1 em stubble/brow_medium) {e_h.sum():,} px | regra {e_n.sum():,} px | núcleo do buzz |ΔL| regra vs hoje {gate_core_dL:.2f}")
save_row("gate_MST10_gratis_hoje_regra.png", [hoje, nova])
viz = nova[..., :3].astype(np.float64) * 0.35; viz[e_n] = [255, 40, 40]
save_row("gate_MST10_gratis_regra_erro.png", [nova, viz.astype(np.uint8)])
hoje01 = face("MST-01", GR, False); nova01 = face("MST-01", GR, True)
save_row("gate_MST01_gratis_hoje_regra.png", [hoje01, nova01])
d01 = np.abs(L8(nova01) - L8(hoje01))
print(f"  MST-01 rosto grátis: |ΔL|>10 em {(d01 > 10)[SIL].mean()*100:.2f}% da silhueta")

# ---------------------------------------------------------------- 5. compostos 1254 sobre tmp_4
print("\n== 5. compostos 1254 sobre tmp_4 (hair_buzz) ==")
lay_f = load(os.path.join(A, "layers", "hair_buzz.png"))
base_f = load(os.path.join(A, "raw", "tmp_4.png"))
H_f, d_f = H_for(lay_f, SRC_F, SIL_F)
print(f"  H (1254) {hexof(H_f)} |H| {np.linalg.norm(H_f):.3f} it {d_f['iters']} init° {d_f['init_angle_max']:.2f} H·S° {d_f['angle_H_S']:.1f}; contra H (512) {hexof(HS['hair_buzz'])}: {angle(H_f, HS['hair_buzz']):.1f}°")
new_f, T_f, a_f, _ = apply_rule(lay_f, SRC_F, base_f, H_f)
def hair_edge_f(mode):
    return hair_edge(lay_f, SRC_F, base_f, mode)
comps = {"tmp4_1254_regra.png": over(base_f, new_f), "tmp4_1254_w_r.png": over(base_f, hair_edge_f("r")), "tmp4_1254_w_1.png": over(base_f, hair_edge_f("1"))}
for fn, im in comps.items():
    Image.fromarray(im[..., :3], "RGB").save(os.path.join(OUT, fn))
np.save(os.path.join(OUT, "tmp4_1254_T.npy"), T_f.astype(np.float32))
for fn in list(comps) + ["tmp4_1254_T.npy"]:
    p = os.path.join(OUT, fn); print(f"  {p}  existe={os.path.exists(p)}  {os.path.getsize(p)/1024:.0f} KB")
miolo_f = (lay_f[..., 3] > 200) & SIL_F
Lb_f = L8(base_f)
for fn, im in comps.items():
    print(f"  {fn:22} mancha no miolo (1254) {int(((L8(im) - Lb_f) > 10)[miolo_f].sum()):,} px")
core_f = miolo_f & (rmap(lay_f, SRC_F) < 0.15)
nat_f = over(base_f, lay_f)
print(f"  núcleo dL (1254): regra {np.abs(L8(comps['tmp4_1254_regra.png']) - L8(nat_f))[core_f].mean():.2f}, w=r {np.abs(L8(comps['tmp4_1254_w_r.png']) - L8(nat_f))[core_f].mean():.2f}, w=1 {np.abs(L8(comps['tmp4_1254_w_1.png']) - L8(nat_f))[core_f].mean():.2f}")
save_row("tmp4_1254_w_r_regra_w_1.png", [comps["tmp4_1254_w_r.png"], comps["tmp4_1254_regra.png"], comps["tmp4_1254_w_1.png"]], half=True)

json.dump({"H_512": {k: v.tolist() for k, v in HS.items()}, "H_1254_buzz": H_f.tolist(), "results": RESULTS, "ident": IDENT, "reg01": REG01},
          open(os.path.join(OUT, "resultados.json"), "w"), indent=1)
print("\nimagens em", OUT)
