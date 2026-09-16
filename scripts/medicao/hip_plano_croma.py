"""Hipótese 'plano_croma' — medição, sem implementar.

Cada pixel de PELO vive no plano gerado por dois vetores em RGB linear:
    L = alpha * H_hat + beta * S          alpha >= 0, 0 <= beta <= 1
H_hat = direção de croma do pelo (unitária, fixa por camada), S = pele da source (por pixel).
Três equações, duas incógnitas: mínimos quadrados com caixa, por pixel, forma fechada
(interior ou uma das faces alpha=0, beta=0, beta=1). H_hat por camada por ALS:
    dado H, resolve (alpha, beta); dado (alpha, beta), H = autovetor principal de
    sum alpha_i v_i v_i^T com v_i = L_i - beta_i S_i.
Inicialização: direção do pixel de menor luminância do miolo.

Composição (regra):   novo = L + beta * (B - S)          [E = L - beta S, T = beta escalar]
  - identidade exata (base = source devolve L);
  - o resíduo do ajuste fica no pelo, não é descartado.
Variante estrita:     novo = alpha * H_hat + beta * B      (só para o resíduo, item d).

Reusa a réplica de tone.ts em medir_pelo.py (validada contra o canvas do jogo).
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
REPORT = {}

SRC = load(os.path.join(A, "build", "source.webp"))
SIL = silhouette(SRC[..., :3])
SOMBRA_W1 = {"beard_stubble", "brow_thin", "brow_medium"}   # fechado: w = 1
ALVOS = ["hair_buzz", "beard_goatee", "beard_shortfull", "beard_chinstrap", "hair_lowfade", "beard_mustache", "brow_thick"]
LOIROS = ["hair_buzz_blonde", "hair_midcurly_blonde"]

def Y(rgb):
    l = lin(rgb[..., :3]); return 0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]
def Llev(rgb):
    return srgb8(Y(rgb)).astype(np.float64)
def srgb_cont(l):
    l = np.maximum(np.asarray(l, dtype=np.float64), 0)
    return 255 * np.where(l <= 0.0031308, 12.92 * l, 1.055 * np.power(l, 1 / 2.4) - 0.055)
def rmap(lay, src):
    lr, sr = lin(lay[..., 0]), lin(src[..., 0])
    return np.where(sr > 0, lr / np.where(sr > 0, sr, 1), 0)

# ---------------------------------------------------------------- solver por pixel
def solve_ab(L, S, H, amax=None):
    """min ||a H + b S - L||^2  s.a. a in [0, amax], b in [0, 1]. L,S: (N,3); H: (3,). Forma fechada:
    solução interior ou a melhor entre as faces a=0, b=0, b=1, a=amax (cada uma clipada)."""
    HS = S @ H; SS = (S * S).sum(1); HL = L @ H; SL = (L * S).sum(1); LL = (L * L).sum(1)
    def res2(a, b):
        return LL - 2 * (a * HL + b * SL) + a * a + 2 * a * b * HS + b * b * SS
    det = SS - HS * HS
    ok = det > 1e-14
    a0 = np.where(ok, (SS * HL - HS * SL) / np.where(ok, det, 1), 0)
    b0 = np.where(ok, (SL - HS * HL) / np.where(ok, det, 1), 0)
    hi = np.inf if amax is None else amax
    cands = []
    feas = ok & (a0 >= 0) & (a0 <= hi) & (b0 >= 0) & (b0 <= 1)
    cands.append((np.where(feas, a0, 0), np.where(feas, b0, 0), np.where(feas, res2(a0, b0), np.inf)))
    # face a = 0
    b = np.clip(SL / np.maximum(SS, 1e-14), 0, 1); cands.append((np.zeros_like(b), b, res2(0 * b, b)))
    # face b = 0
    a = np.clip(HL, 0, hi); cands.append((a, np.zeros_like(a), res2(a, 0 * a)))
    # face b = 1
    a = np.clip(HL - HS, 0, hi); cands.append((a, np.ones_like(a), res2(a, np.ones_like(a))))
    if amax is not None:
        b = np.clip((SL - amax * HS) / np.maximum(SS, 1e-14), 0, 1)
        cands.append((np.full_like(b, amax), b, res2(np.full_like(b, amax), b)))
    R = np.stack([c[2] for c in cands]); k = np.argmin(R, axis=0)
    a = np.choose(k, [c[0] for c in cands]); b = np.choose(k, [c[1] for c in cands])
    return a, b, np.sqrt(np.maximum(R[k, np.arange(k.size)], 0))

def fit_H(L, S, iters=60, tol_deg=0.01, amax=None):
    """ALS. Inicializa pela direção do pixel de menor luminância. Devolve H, histórico."""
    y = 0.2126 * L[:, 0] + 0.7152 * L[:, 1] + 0.0722 * L[:, 2]
    order = np.argsort(y)
    for i in order:
        if np.linalg.norm(L[i]) > 0:
            H = L[i] / np.linalg.norm(L[i]); break
    hist = []
    for it in range(iters):
        a, b, r = solve_ab(L, S, H, amax)
        V = L - b[:, None] * S
        M = (V * a[:, None]).T @ V
        w, U = np.linalg.eigh(M)
        Hn = U[:, -1]
        if Hn @ (V * a[:, None]).sum(0) < 0:
            Hn = -Hn
        ang = np.degrees(np.arccos(np.clip(H @ Hn, -1, 1)))
        hist.append((it, float(np.sqrt((r ** 2).mean())), float(ang)))
        H = Hn
        if ang < tol_deg:
            break
    a, b, r = solve_ab(L, S, H, amax)
    return H, hist, a, b, r

def angle(u, v):
    return float(np.degrees(np.arccos(np.clip(u @ v / np.linalg.norm(u) / np.linalg.norm(v), -1, 1))))

# ---------------------------------------------------------------- estimativa de H por camada
H_CACHE = {}
def estimate(name, res):
    """res = '512' (build webp + source.webp) ou '1254' (layers png + raw/tmp_1). Devolve dict."""
    key = (name, res)
    if key in H_CACHE:
        return H_CACHE[key]
    if res == "512":
        lay, src, sil = layer512(name), SRC, SIL
    else:
        lay = load(os.path.join(A, "layers", f"{name}.png")); src = load(os.path.join(A, "raw", "tmp_1.png")); sil = silhouette(src[..., :3])
    miolo = (lay[..., 3] > 200)
    inside = miolo & sil; outside = miolo & ~sil
    Lall = lin(lay[..., :3]); Sall = lin(src[..., :3])
    L_in, S_in = Lall[inside], Sall[inside]
    t0 = time.time()
    H, hist, a, b, r = fit_H(L_in, S_in)
    # H com todos os pixels do miolo (dentro + fora, fora S = fundo branco): checagem
    H_all = fit_H(Lall[miolo], Sall[miolo])[0] if outside.sum() > 50 else None
    Smean = S_in.mean(0)
    # prior físico: brilho máximo do pelo fora da silhueta (E = alpha, |H| = 1), se existir
    amax = None
    if outside.sum() > 50:
        a_out, b_out, _ = solve_ab(Lall[outside], Sall[outside], H)
        amax = float(a_out.max())
    res_lev = np.abs(srgb_cont(a[:, None] * H + b[:, None] * S_in) - srgb_cont(L_in)).mean(1)
    d = {"H": H, "hist": hist, "iters": len(hist), "conv_deg": hist[-1][2], "rms_lin": hist[-1][1],
         "ang_H_S": angle(H, Smean), "ang_H_Hall": (angle(H, H_all) if H_all is not None else None),
         "H_srgb": tuple(int(v) for v in srgb8(H / H.max() * 0.5)),  # só para leitura humana
         "Smean_dir": Smean / np.linalg.norm(Smean), "amax": amax, "n_in": int(inside.sum()), "n_out": int(outside.sum()),
         "res_mean": float(res_lev.mean()), "res_p95": float(np.percentile(res_lev, 95)),
         "beta_med": float(np.median(b)), "alpha0_frac": float((a == 0).mean()), "beta0_frac": float((b == 0).mean()),
         "t": time.time() - t0}
    H_CACHE[key] = d
    return d

# ---------------------------------------------------------------- regra
def rule(lay, src, base, H, amax=None, strict=False, return_T=False):
    """novo = L + beta (B - S). Aplica em todo pixel (fora da silhueta S = B = fundo -> inócuo)."""
    Lf = lin(lay[..., :3]); Sf = lin(src[..., :3]); Bf = lin(base[..., :3])
    sh = Lf.shape[:2]
    a, b, _ = solve_ab(Lf.reshape(-1, 3), Sf.reshape(-1, 3), H, amax)
    a = a.reshape(sh); b = b.reshape(sh)
    if strict:
        novo = a[..., None] * H + b[..., None] * Bf
    else:
        novo = Lf + b[..., None] * (Bf - Sf)
    out = lay.copy()
    out[..., :3] = srgb8(np.clip(novo, 0, 1))
    if return_T:
        return out, b.astype(np.float32), a.astype(np.float32)
    return out

def alone(lay, base, mode):
    return over(base, hair_edge(lay, SRC, base, mode))

def metrics(name, tid, H, amax=None, strict=False):
    lay = layer512(name); base = base512(tid)
    miolo = (lay[..., 3] > 200) & SIL
    r = rmap(lay, SRC); nucleo = miolo & (r < 0.15)
    nat = over(base, lay)                                # w = 0: nativa sobre a base
    hoje = alone(lay, base, "r")
    novo = over(base, rule(lay, SRC, base, H, amax, strict))
    Lb = Llev(base)
    m_before = ((Llev(hoje) - Lb) > 10) & miolo
    m_after = ((Llev(novo) - Lb) > 10) & miolo
    d = {"layer": name, "tone": tid, "stain_px_before": int(m_before.sum()), "stain_px_after": int(m_after.sum()),
         "stain_pct_miolo_after": float(m_after.sum() / max(miolo.sum(), 1) * 100),
         "core_dL": float(np.abs(Llev(novo) - Llev(nat))[nucleo].mean()) if nucleo.any() else -1.0,
         "core_dL_w_r": float(np.abs(Llev(hoje) - Llev(nat))[nucleo].mean()) if nucleo.any() else -1.0,
         "core_px": int(nucleo.sum()), "miolo_px": int(miolo.sum()),
         "dark_pct_miolo": float(((Llev(novo) - Llev(nat)) < -10)[miolo].mean() * 100),
         "mean_dL_vs_nat_miolo": float((Llev(novo) - Llev(nat))[miolo].mean())}
    if tid == "MST-01":
        d["mst01_regression_pct"] = float((np.abs(Llev(novo) - Llev(hoje)) > 10)[SIL].mean() * 100)
    return d, hoje, novo

def save_row(fname, imgs, half=False):
    sep = np.full((imgs[0].shape[0], 8, 3), 255, np.uint8)
    row = [imgs[0][..., :3]]
    for im in imgs[1:]:
        row += [sep, im[..., :3]]
    img = Image.fromarray(np.concatenate(row, axis=1))
    if half:
        img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
    img.save(os.path.join(OUT, fname))

# ================================================================ 1. H_hat por camada
print("== 1. H_hat por camada (ALS, 512 e 1254), condicionamento e resíduo ==")
print(f"{'camada':22} {'res':>5} {'iters':>5} {'conv°':>6} {'ang(H,S)°':>9} {'ang(in,all)°':>12} {'H sRGB(ilustr)':>16} {'res med':>7} {'res p95':>7} {'beta med':>8} {'a=0%':>5} {'b=0%':>5} {'amax':>7} {'n_out':>7}")
for name in ALVOS + LOIROS + ["hair_buzz_grey", "hair_buzz_red", "hair_midcurly"]:
    for res in ["512", "1254"]:
        e = estimate(name, res)
        print(f"{name:22} {res:>5} {e['iters']:5d} {e['conv_deg']:6.3f} {e['ang_H_S']:9.2f} {(e['ang_H_Hall'] if e['ang_H_Hall'] is not None else float('nan')):12.2f} {str(e['H_srgb']):>16} {e['res_mean']:7.2f} {e['res_p95']:7.2f} {e['beta_med']:8.3f} {e['alpha0_frac']*100:5.1f} {e['beta0_frac']*100:5.1f} {(e['amax'] if e['amax'] is not None else float('nan')):7.3f} {e['n_out']:7,}")
    e5, e1 = estimate(name, "512"), estimate(name, "1254")
    print(f"{'':22} ang(H512, H1254) = {angle(e5['H'], e1['H']):.2f}°   H512 = {np.round(e5['H'], 4)}  Sdir = {np.round(e5['Smean_dir'], 4)}")
REPORT["H"] = {k[0] + "@" + k[1]: {"H": [float(v) for v in d["H"]], "ang_H_S": d["ang_H_S"], "iters": d["iters"], "conv_deg": d["conv_deg"],
                                   "res_mean": d["res_mean"], "res_p95": d["res_p95"], "amax": d["amax"], "n_out": d["n_out"]} for k, d in H_CACHE.items()}

print("\n  histórico ALS hair_buzz@512 (iter, rms lin, giro°):", [(i, round(r, 5), round(a, 3)) for i, r, a in estimate("hair_buzz", "512")["hist"]][:12])
print("  histórico ALS hair_buzz_blonde@512:", [(i, round(r, 5), round(a, 3)) for i, r, a in estimate("hair_buzz_blonde", "512")["hist"]][:12])

# sensibilidade à inicialização: H a partir do pixel mais claro e de S
print("\n  sensibilidade da ALS à inicialização (512): ângulo entre H(init escuro) e H(init = direção de S)")
for name in ["hair_buzz", "beard_goatee", "hair_buzz_blonde"]:
    lay = layer512(name); inside = (lay[..., 3] > 200) & SIL
    L_in, S_in = lin(lay[..., :3])[inside], lin(SRC[..., :3])[inside]
    H0 = estimate(name, "512")["H"]
    Hs = S_in.mean(0) / np.linalg.norm(S_in.mean(0))
    H = Hs.copy()
    for it in range(60):
        a, b, r = solve_ab(L_in, S_in, H); V = L_in - b[:, None] * S_in
        w, U = np.linalg.eigh((V * a[:, None]).T @ V); Hn = U[:, -1]
        if Hn @ (V * a[:, None]).sum(0) < 0: Hn = -Hn
        ang = angle(H, Hn); H = Hn
        if ang < 0.01: break
    print(f"    {name:20} {angle(H0, H):.2f}°  (init S convergiu em {it+1} iters)")

# ================================================================ 2. métricas por camada x tom
print("\n== 2. camada sozinha: regra novo = L + beta (B - S) ==")
print("mancha = miolo com L(comp) - L(base) > 10; núcleo = r_R < 0,15 & miolo; nativo = camada sobre a base com w = 0")
RESULTS = []
combos = [(n, "MST-10") for n in ALVOS] + [("hair_buzz", "MST-05"), ("hair_buzz", "MST-01")] + [(n, "MST-01") for n in ALVOS if n != "hair_buzz"] + [(n, "MST-10") for n in LOIROS]
print(f"{'camada':22} {'tom':7} {'mancha w=r':>10} {'mancha nova':>11} {'% miolo':>7} {'núcleo dL':>9} {'núcleo w=r':>10} {'núc px':>7} {'escur>10%':>9} {'dL méd':>7} {'MST01 regr%':>11}")
IMGS = {}
for name, tid in combos:
    e = estimate(name, "512")
    d, hoje, novo = metrics(name, tid, e["H"])
    IMGS[(name, tid)] = (hoje, novo)
    RESULTS.append(d)
    print(f"{name:22} {tid:7} {d['stain_px_before']:10,} {d['stain_px_after']:11,} {d['stain_pct_miolo_after']:7.2f} {d['core_dL']:9.2f} {d['core_dL_w_r']:10.2f} {d['core_px']:7,} {d['dark_pct_miolo']:9.1f} {d['mean_dL_vs_nat_miolo']:7.1f} {d.get('mst01_regression_pct', float('nan')):11.2f}")

# onde o beta cai: núcleo (r<0,15), banda de halo (pixels de erro do w=r) e o resto do miolo
print("\n  beta (= T) por região, 512, MST-10: mediana de beta, de r_R e de T=w·r=r² do w=r; e |L| médio vs beta·|S| no núcleo")
print(f"  {'camada':20} {'núcleo beta':>11} {'núcleo r':>8} {'núcleo r²':>9} {'beta·|S|/|L|':>12} | {'halo beta':>9} {'halo r':>7} {'halo r²':>7} | {'resto beta':>10} {'resto r':>7}")
for name in ALVOS + LOIROS:
    lay = layer512(name); base = base512("MST-10"); e = estimate(name, "512")
    _, T, Aa = rule(lay, SRC, base, e["H"], return_T=True)
    miolo = (lay[..., 3] > 200) & SIL; r = rmap(lay, SRC)
    nuc = miolo & (r < 0.15)
    hoje = alone(lay, base, "r"); halo = miolo & ((Llev(hoje) - Llev(base)) > 10)
    resto = miolo & ~nuc & ~halo
    Lf = lin(lay[..., :3]); Sf = lin(SRC[..., :3])
    frac = (T * np.linalg.norm(Sf, axis=2) / np.maximum(np.linalg.norm(Lf, axis=2), 1e-9))
    f = lambda m, x: float(np.median(x[m])) if m.any() else float("nan")
    print(f"  {name:20} {f(nuc, T):11.3f} {f(nuc, r):8.3f} {f(nuc, r*r):9.3f} {f(nuc, frac):12.3f} | {f(halo, T):9.3f} {f(halo, r):7.3f} {f(halo, r*r):7.3f} | {f(resto, T):10.3f} {f(resto, r):7.3f}")

# variante estrita (alpha H + beta B) e com prior amax, só buzz e goatee em MST-10, para comparar
print("\n  variantes em MST-10 (mancha nova / núcleo dL): estrita alpha·H + beta·B; com prior alpha <= amax (fora da silhueta)")
for name in ["hair_buzz", "beard_goatee", "hair_lowfade", "hair_buzz_blonde"]:
    e = estimate(name, "512")
    ds, _, _ = metrics(name, "MST-10", e["H"], strict=True)
    line = f"    {name:20} estrita: mancha {ds['stain_px_after']:6,} núcleo {ds['core_dL']:6.2f}"
    if e["amax"] is not None:
        dp, _, _ = metrics(name, "MST-10", e["H"], amax=e["amax"])
        line += f" | prior amax={e['amax']:.3f}: mancha {dp['stain_px_after']:6,} núcleo {dp['core_dL']:6.2f}"
    else:
        line += " | prior: sem pelo fora da silhueta"
    print(line)

# identidade
print("\n== 3. identidade: compor sobre a própria source ==")
idmax = 0
for name in ALVOS + LOIROS:
    e = estimate(name, "512")
    t = rule(layer512(name), SRC, SRC, e["H"])
    d = np.abs(t[..., :3].astype(int) - layer512(name)[..., :3].astype(int)).max()
    ts = rule(layer512(name), SRC, SRC, e["H"], strict=True)
    dstrict = np.abs(ts[..., :3].astype(int) - layer512(name)[..., :3].astype(int))
    idmax = max(idmax, int(d))
    print(f"  {name:20} regra max|dif| {d}   (estrita: max {dstrict.max()}, média {dstrict.mean():.2f})")
REPORT["identity_max"] = idmax

# imagens: buzz sozinho MST-10 e MST-01 hoje | regra; loiros
save_row("buzz_MST10_hoje_regra.png", IMGS[("hair_buzz", "MST-10")])
save_row("buzz_MST01_hoje_regra.png", IMGS[("hair_buzz", "MST-01")])
save_row("buzz_MST05_hoje_regra.png", IMGS[("hair_buzz", "MST-05")])
for n in LOIROS:
    save_row(f"{n}_MST10_hoje_regra.png", IMGS[(n, "MST-10")])
grid = [np.concatenate([IMGS[(n, "MST-10")][0][..., :3], np.full((512, 8, 3), 255, np.uint8), IMGS[(n, "MST-10")][1][..., :3]], axis=1) for n in ALVOS[1:]]
Image.fromarray(np.concatenate(grid, axis=0)).resize((grid[0].shape[1] // 2, len(grid) * 256), Image.LANCZOS).save(os.path.join(OUT, "alvos_MST10_hoje_regra_meia.png"))
# mapa de beta (T) e alpha do buzz em 512
_, T, Aa = rule(layer512("hair_buzz"), SRC, base512("MST-10"), estimate("hair_buzz", "512")["H"], return_T=True)
viz = np.zeros((512, 512 * 2 + 8, 3), np.uint8)
viz[:, :512] = (np.clip(T, 0, 1) * 255)[..., None]
viz[:, 520:] = (np.clip(Aa / max(Aa.max(), 1e-6), 0, 1) ** (1 / 2.2) * 255)[..., None]
viz[:, 512:520] = 255
Image.fromarray(viz).save(os.path.join(OUT, "buzz_512_beta_alpha.png"))

# loiro: cor do pelo antes/depois
print("\n== 4. loiro sobre MST-10: cor do pelo (mediana sRGB) nos pixels de pelo (alpha_fit > mediana) nativo x regra ==")
for n in LOIROS:
    lay = layer512(n); base = base512("MST-10"); e = estimate(n, "512")
    novo, T, Aa = rule(lay, SRC, base, e["H"], return_T=True)
    miolo = (lay[..., 3] > 200) & SIL
    pelo = miolo & (Aa > np.median(Aa[miolo]))
    nat = np.median(lay[..., :3][pelo], axis=0); nv = np.median(novo[..., :3][pelo], axis=0)
    dL = (Llev(over(base, novo)) - Llev(over(base, lay)))[pelo]
    print(f"  {n:20} nativo {nat.astype(int)}  regra {nv.astype(int)}  dL médio no pelo {dL.mean():+.2f}, |dL|>10 em {(np.abs(dL) > 10).mean()*100:.1f}% do pelo; beta mediana no pelo {np.median(T[pelo]):.3f}")
    REPORT[f"blonde_{n}"] = {"nat": nat.tolist(), "novo": nv.tolist(), "dL_mean": float(dL.mean()), "pct_gt10": float((np.abs(dL) > 10).mean() * 100)}

# ================================================================ 5. gate
print("\n== 5. GATE: rosto grátis MST-10 (brow_medium e stubble com w = 1; buzz: hoje w = r | regra) ==")
GR = {"ear": "ear_normal", "eye": "eye_almond", "brow": "brow_medium", "nose": "nose_medium",
      "beard": "beard_stubble", "mouth": "mouth_medium", "hair": "hair_buzz"}
def face(tid, hair_rule):
    base = base512(tid); Lt = lut(TONE[tid]["k"]); cv = base.copy()
    for slot in ORDER:
        n = GR[slot]; lay = layer512(n)
        if slot in SKIN:
            cv = over(cv, tone_layer(lay, Lt), OFFSET.get(n, 0))
        elif n in SOMBRA_W1:
            cv = over(cv, hair_edge(lay, SRC, base, "1"))
        elif hair_rule:
            cv = over(cv, rule(lay, SRC, base, estimate(n, "512")["H"]))
        else:
            cv = over(cv, hair_edge(lay, SRC, base, "r"))
    return cv
B10 = base512("MST-10")
g_hoje, g_nova = face("MST-10", False), face("MST-10", True)
eh = ((Llev(g_hoje) - Llev(B10)) > 10) & SIL
en = ((Llev(g_nova) - Llev(B10)) > 10) & SIL
buzz_nuc = (layer512("hair_buzz")[..., 3] > 200) & SIL & (rmap(layer512("hair_buzz"), SRC) < 0.15)
nat_face = over(B10, layer512("hair_buzz"))
gate_core = float(np.abs(Llev(g_nova) - Llev(nat_face))[buzz_nuc].mean())
print(f"  mancha na silhueta: hoje {eh.sum():,} px | regra {en.sum():,} px ({(eh.sum()-en.sum())/max(eh.sum(),1)*100:.1f}% a menos)")
print(f"  núcleo do buzz no gate (regra vs nativa sobre base): {gate_core:.2f} níveis")
save_row("gate_MST10_hoje_regra.png", [g_hoje, g_nova])
viz = g_nova[..., :3].astype(np.float64) * 0.35; viz[en] = [255, 40, 40]
save_row("gate_MST10_regra_erro_restante.png", [g_nova, viz.astype(np.uint8)])
g01h, g01n = face("MST-01", False), face("MST-01", True)
save_row("gate_MST01_hoje_regra.png", [g01h, g01n])
print(f"  MST-01 gate: |dL|>10 em {(np.abs(Llev(g01n) - Llev(g01h)) > 10)[SIL].mean()*100:.2f}% da silhueta")
REPORT["gate"] = {"before": int(eh.sum()), "after": int(en.sum()), "core": gate_core}

# ================================================================ 6. compostos 1254 sobre tmp_4
print("\n== 6. compostos 1254 sobre tmp_4 (source tmp_1, camada layers/hair_buzz.png, alpha simples) ==")
src4 = load(os.path.join(A, "raw", "tmp_1.png")); base4 = load(os.path.join(A, "raw", "tmp_4.png"))
lay4 = load(os.path.join(A, "layers", "hair_buzz.png"))
H4 = estimate("hair_buzz", "1254")["H"]
novo4, T4, A4 = rule(lay4, src4, base4, H4, return_T=True)
for fname, im in [("tmp4_1254_regra.png", over(base4, novo4)), ("tmp4_1254_w_r.png", over(base4, hair_edge(lay4, src4, base4, "r"))),
                  ("tmp4_1254_w_1.png", over(base4, hair_edge(lay4, src4, base4, "1")))]:
    Image.fromarray(im[..., :3], "RGB").save(os.path.join(OUT, fname))
np.save(os.path.join(OUT, "tmp4_1254_T.npy"), T4.astype(np.float32))
for f in ["tmp4_1254_regra.png", "tmp4_1254_w_r.png", "tmp4_1254_w_1.png", "tmp4_1254_T.npy"]:
    p = os.path.join(OUT, f); print(f"  {f}: {'existe' if os.path.exists(p) else 'FALTA'} {os.path.getsize(p) if os.path.exists(p) else 0:,} bytes")
sil4 = silhouette(src4[..., :3]); miolo4 = (lay4[..., 3] > 200) & sil4
c4 = over(base4, novo4); h4 = over(base4, hair_edge(lay4, src4, base4, "r"))
Lb4 = Llev(base4)
print(f"  1254: mancha miolo w=r {(((Llev(h4) - Lb4) > 10) & miolo4).sum():,} px | regra {(((Llev(c4) - Lb4) > 10) & miolo4).sum():,} px; "
      f"núcleo (r<0,15) dL regra vs nativa {np.abs(Llev(c4) - Llev(over(base4, lay4)))[miolo4 & (rmap(lay4, src4) < 0.15)].mean():.2f}")
# recorte da linha do cabelo lado a lado em 1254 (hoje | regra), meia escala
crop = (slice(150, 650), slice(250, 1000))
save_row("tmp4_1254_recorte_w_r_regra.png", [h4[crop], c4[crop]], half=False)

json.dump({"results": RESULTS, **{k: v for k, v in REPORT.items()}}, open(os.path.join(OUT, "relatorio.json"), "w"), indent=1, default=float)
print("\nimagens em", OUT)
