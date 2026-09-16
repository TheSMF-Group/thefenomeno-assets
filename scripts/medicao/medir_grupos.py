"""Medição, sem implementar: grupo A (núcleo opaco, corte de distância na extração) e
grupo B (sem núcleo, w = 1), sobre o rosto grátis em MST-10.

Rode de fora do repo (as imagens vão para MEDICAO_OUT ou para a pasta corrente):
  python scripts/medicao/medir_grupos.py

Reusa as definições de medir_pelo.py, cuja réplica de tone.ts bate com o canvas do /criar.
"""
import os
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
code = open(os.path.join(HERE, "medir_pelo.py"), encoding="utf8").read()
g = {"__file__": os.path.join(HERE, "medir_pelo.py")}
exec(code[:code.index("# ---------------------------------------------------------------- 1. distribuição")], g)
exec(code[code.index("# ---------------------------------------------------------------- composição"):code.index("GRATIS = {")], g)
A, OUT, lin, load, silhouette, srgb8 = (g[k] for k in ["A", "OUT", "lin", "load", "silhouette", "srgb8"])
layer512, base512, hair_edge, over = (g[k] for k in ["layer512", "base512", "hair_edge", "over"])
lut, tone_layer, TONE, ORDER, SKIN, OFFSET = (g[k] for k in ["lut", "tone_layer", "TONE", "ORDER", "SKIN", "OFFSET"])

DIST = 20
SRC = load(os.path.join(A, "build", "source.webp"))
SIL = silhouette(SRC[..., :3])

def Y(rgb):
    l = lin(rgb[..., :3]); return 0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]
def L(rgb):
    return srgb8(Y(rgb)).astype(np.float64)
def rmap(lay):
    lr, sr = lin(lay[..., 0]), lin(SRC[..., 0])
    return np.where(sr > 0, lr / np.where(sr > 0, sr, 1), 0)

def cut_distance(lay):
    """Tira do alpha a pele DENTRO da silhueta a mais de DIST px do pelo opaco (r < 0,15 no miolo)."""
    miolo = (lay[..., 3] > 200) & SIL
    opaco = miolo & (rmap(lay) < 0.15)
    if not opaco.any():
        return lay.copy(), 0
    far = SIL & (lay[..., 3] > 0) & (ndimage.distance_transform_edt(~opaco) > DIST)
    out = lay.copy(); out[far, 3] = 0
    return out, int(far.sum())

def face(tid, parts, cut=(), w1=()):
    base = base512(tid); Lt = lut(TONE[tid]["k"]); cv = base.copy()
    for slot in ORDER:
        n = parts[slot]; lay = layer512(n)
        if slot in SKIN:
            cv = over(cv, tone_layer(lay, Lt), OFFSET.get(n, 0))
        else:
            if n in cut:
                lay = cut_distance(lay)[0]
            cv = over(cv, hair_edge(lay, SRC, base, "1" if n in w1 else "r"))
    return cv

def err(comp, base, region=None):
    e = (L(comp) - L(base)) > 10
    return e & (SIL if region is None else region)

def save(name, *imgs):
    sep = np.full((512, 8, 3), 255, np.uint8)
    row = [imgs[0][..., :3]]
    for im in imgs[1:]:
        row += [sep, im[..., :3]]
    Image.fromarray(np.concatenate(row, axis=1)).save(os.path.join(OUT, name))

B10, B01 = base512("MST-10"), base512("MST-01")
GRUPO_A = ["hair_buzz", "beard_chinstrap", "beard_shortfull"]
GRUPO_B = ["beard_stubble", "brow_thin", "brow_medium"]
MEIO = ["beard_goatee", "brow_thick", "hair_lowfade", "beard_mustache"]

# ---------------------------------------------------------------- 1. grupo A com corte
print(f"== 1. grupo A, corte de distância > {DIST} px, camada sozinha em MST-10, w = r ==")
print(f"{'camada':16} {'px cortados':>11} {'erro antes':>10} {'erro depois':>11} {'queda':>6}")
for n in GRUPO_A:
    lay = layer512(n); c, k = cut_distance(lay)
    a = err(over(B10, hair_edge(lay, SRC, B10, "r")), B10).sum()
    b = err(over(B10, hair_edge(c, SRC, B10, "r")), B10).sum()
    print(f"{n:16} {k:11,} {a:10,} {b:11,} {(a-b)/a*100:5.1f}%")
buzz_a = over(B10, hair_edge(layer512("hair_buzz"), SRC, B10, "r"))
buzz_b = over(B10, hair_edge(cut_distance(layer512("hair_buzz"))[0], SRC, B10, "r"))
save("grupos_1_buzz_MST10_antes_depois.png", buzz_a, buzz_b)
testa = np.zeros_like(SIL); testa[60:200, 120:400] = True
print(f"faixa de testa (y 60-200, x 120-400): erro {err(buzz_a, B10, SIL & testa).sum():,} -> {err(buzz_b, B10, SIL & testa).sum():,} px")

# ---------------------------------------------------------------- 2. rosto grátis A + B
print("\n== 2. rosto grátis (buzz + stubble + brow_medium), MST-10 ==")
GR = {"ear": "ear_normal", "eye": "eye_almond", "brow": "brow_medium", "nose": "nose_medium",
      "beard": "beard_stubble", "mouth": "mouth_medium", "hair": "hair_buzz"}
hoje = face("MST-10", GR)
so_a = face("MST-10", GR, cut=GRUPO_A)
so_b = face("MST-10", GR, w1=GRUPO_B)
ab = face("MST-10", GR, cut=GRUPO_A, w1=GRUPO_B)
e0 = err(hoje, B10).sum()
for nome, im in [("hoje (w = r)", hoje), ("só A", so_a), ("só B", so_b), ("A + B", ab)]:
    e = err(im, B10)
    print(f"  {nome:14} erro {e.sum():7,} px  ({(e0 - e.sum())/e0*100:5.1f}% a menos)")
save("grupos_2_gratis_MST10_hoje_A_B_AB.png", hoje, so_a, so_b, ab)
e_ab = err(ab, B10)
viz = ab[..., :3].astype(np.float64) * 0.35
viz[e_ab] = [255, 40, 40]
Image.fromarray(np.concatenate([ab[..., :3], np.full((512, 8, 3), 255, np.uint8), viz.astype(np.uint8)], axis=1)).save(os.path.join(OUT, "grupos_2_gratis_MST10_AB_erro_restante.png"))
ys, xs = np.nonzero(e_ab)
if ys.size:
    print(f"  erro restante em A + B: y {ys.min()}-{ys.max()}, x {xs.min()}-{xs.max()}; "
          f"{(e_ab & (layer512('hair_buzz')[...,3] > 200)).sum():,} px no miolo do buzz, "
          f"{(e_ab & (layer512('brow_medium')[...,3] > 200)).sum():,} no da sobrancelha, "
          f"{(e_ab & (layer512('beard_stubble')[...,3] > 200)).sum():,} no da stubble")
hoje01, ab01 = face("MST-01", GR), face("MST-01", GR, cut=GRUPO_A, w1=GRUPO_B)
save("grupos_2_gratis_MST01_hoje_AB.png", hoje01, ab01)
d01 = np.abs(L(ab01) - L(hoje01))[SIL]
print(f"  MST-01, A + B contra hoje: |ΔL| médio {d01.mean():.2f}, p99 {np.percentile(d01, 99):.1f}, "
      f"{(d01 > 10).mean()*100:.2f}% da silhueta muda mais de 10 níveis")

# ---------------------------------------------------------------- 3. camadas do meio
print("\n== 3. camadas do meio, sozinhas em MST-10 ==")
print(f"{'camada':16} {'erro w=r':>8} {'% erro perto':>12} {'com corte':>9} {'w=1':>6} | {'cor do pelo opaco w=1':>22}")
for n in MEIO + ["brow_thick", "beard_chinstrap", "brow_medium"]:
    lay = layer512(n)
    miolo = (lay[..., 3] > 200) & SIL
    r = rmap(lay)
    opaco = miolo & (r < 0.15)
    far = miolo & (ndimage.distance_transform_edt(~opaco) > DIST) if opaco.any() else miolo
    now = over(B10, hair_edge(lay, SRC, B10, "r"))
    e = err(now, B10, miolo)
    ec = err(over(B10, hair_edge(cut_distance(lay)[0], SRC, B10, "r")), B10, miolo).sum()
    w1 = over(B10, hair_edge(lay, SRC, B10, "1"))
    e1 = err(w1, B10, miolo).sum()
    cor = np.abs(L(w1) - L(now))[opaco].mean() if opaco.any() else float("nan")
    print(f"{n:16} {e.sum():8,} {(e & ~far).sum()/max(e.sum(),1)*100:11.1f}% {ec:9,} {e1:6,} | {cor:18.1f} níveis")

imgs = []
for n in MEIO:
    lay = layer512(n)
    imgs.append(np.concatenate([over(B10, hair_edge(lay, SRC, B10, "r"))[..., :3], np.full((512, 8, 3), 255, np.uint8),
                                over(B10, hair_edge(cut_distance(lay)[0], SRC, B10, "r"))[..., :3]], axis=1))
grid = np.concatenate(imgs, axis=0)
Image.fromarray(grid).resize((grid.shape[1] // 2, grid.shape[0] // 2), Image.LANCZOS).save(os.path.join(OUT, "grupos_3_meio_MST10_antes_corte.png"))

# ---------------------------------------------------------------- limiar
print("\n== limiar de 'tem núcleo': custo de cada lado da fronteira, MST-10 ==")
print("para cada candidata: erro com corte (tratada como A) e com w = 1 (tratada como B), e quanto w = 1 escurece o pelo opaco")
for n in ["beard_shortfull", "brow_thick", "beard_chinstrap", "brow_medium", "brow_thin"]:
    lay = layer512(n); miolo = (lay[..., 3] > 200) & SIL; opaco = miolo & (rmap(lay) < 0.15)
    now = over(B10, hair_edge(lay, SRC, B10, "r")); w1 = over(B10, hair_edge(lay, SRC, B10, "1"))
    ec = err(over(B10, hair_edge(cut_distance(lay)[0], SRC, B10, "r")), B10, miolo).sum()
    print(f"  {n:16} opaco {opaco.sum()/miolo.sum()*100:5.2f}% (512) | como A: erro {ec:6,} | como B: erro {err(w1, B10, miolo).sum():5,}, "
          f"pelo opaco escurece {np.abs(L(w1) - L(now))[opaco].mean() if opaco.any() else float('nan'):.1f} níveis")
print("imagens em", OUT)
