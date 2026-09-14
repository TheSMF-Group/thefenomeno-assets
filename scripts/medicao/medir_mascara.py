"""Medição, sem implementar: a máscara de PELO carrega pele longe do pelo?

Reusa a réplica validada de medir_pelo.py (bate com o canvas do /criar). w não é tocado:
todo composto aqui é w = r, como está em tone.ts.
"""
import os, sys
import numpy as np
from PIL import Image
from scipy import ndimage

sys.argv = [sys.argv[0]]
HERE = os.path.dirname(os.path.abspath(__file__))
src_code = open(os.path.join(HERE, "medir_pelo.py"), encoding="utf8").read()
# só as definições: corta antes das seções que imprimem
cut = src_code.index("# ---------------------------------------------------------------- 1. distribuição")
ns = {"__file__": os.path.join(HERE, "medir_pelo.py")}
exec(src_code[:cut], ns)
cut2 = src_code.index("# ---------------------------------------------------------------- composição")
cut3 = src_code.index('GRATIS = {')
exec(src_code[cut2:cut3], ns)
g = ns
A, lin, load, silhouette, PELO = g["A"], g["lin"], g["load"], g["silhouette"], g["PELO"]
g["SOMBRA"] = []  # w = r em tudo
layer512, base512, hair_edge, over, compose, srgb8 = (g[k] for k in ["layer512", "base512", "hair_edge", "over", "compose", "srgb8"])

DIST = 20
src512 = load(os.path.join(A, "build", "source.webp"))
sil512 = silhouette(src512[..., :3])
src_full = load(os.path.join(A, "raw", "tmp_1.png"), "RGB")
sil_full = silhouette(src_full)

def Y(rgb):
    l = lin(rgb[..., :3]); return 0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]
def L(rgb):
    return srgb8(Y(rgb)).astype(np.float64)

def rmap(lay, src):
    lr, sr = lin(lay[..., 0]), lin(src[..., 0])
    return np.where(sr > 0, lr / np.where(sr > 0, sr, 1), 0)

def distant(lay, src, sil, dist_px):
    miolo = (lay[..., 3] > 200) & sil
    r = rmap(lay, src)
    opaco = miolo & (r < 0.15)
    if opaco.sum() == 0:
        d = np.full(miolo.shape, np.inf)
    else:
        d = ndimage.distance_transform_edt(~opaco)
    return miolo, r, opaco, miolo & (d > dist_px)

# ---------------------------------------------------------------- 1
print(f"== 1. miolo (alpha>200, na silhueta) a mais de {DIST} px do pelo opaco (r<0,15) mais próximo ==")
print("512 = build, onde o runtime compõe; cheia = layers/ + raw/tmp_1.png, com 20 px e com 49 px (20 px de 512 em escala)")
print(f"{'camada':18} {'miolo 512':>9} {'distante 512':>12} {'%':>6} {'r med dist':>10} | {'miolo cheio':>11} {'% >20px':>8} {'% >49px':>8}")
R1 = {}
for name in PELO:
    lay = layer512(name)
    miolo, r, opaco, far = distant(lay, src512, sil512, DIST)
    full = load(os.path.join(A, "layers", f"{name}.png"))
    mf, rf, of, far20 = distant(full, src_full, sil_full, 20)
    far49 = mf & (ndimage.distance_transform_edt(~of) > 49 if of.sum() else np.ones_like(mf))
    R1[name] = (miolo, r, far)
    rmed = float(np.median(r[far])) if far.sum() else float("nan")
    print(f"{name:18} {miolo.sum():9,} {far.sum():12,} {far.sum()/miolo.sum()*100:6.1f} {rmed:10.2f} | {mf.sum():11,} {far20.sum()/mf.sum()*100:8.1f} {far49.sum()/mf.sum()*100:8.1f}")

# ---------------------------------------------------------------- 2
print("\n== 2. coincidência: miolo distante x mapa de erro, tom 10, cada camada sozinha com w = r ==")
print("erro = composto clareia a base em mais de 10 níveis de L (o 'clarão')")
print(f"{'camada':18} {'erro px':>8} {'erro no distante':>16} {'distante com erro':>17} | {'erro no perto':>13}")
base10 = base512("MST-10")
for name in PELO:
    miolo, r, far = R1[name]
    comp = over(base10, hair_edge(layer512(name), src512, base10, "r"))
    err = ((L(comp) - L(base10)) > 10) & miolo
    near = miolo & ~far
    e = err.sum()
    print(f"{name:18} {e:8,} {((err & far).sum()/e*100 if e else 0):15.1f}% {((err & far).sum()/far.sum()*100 if far.sum() else 0):16.1f}% | {((err & near).sum()/e*100 if e else 0):12.1f}%")

# imagem: rosto grátis em tom 10, erro x distante (união das camadas de PELO do rosto)
GR = {"ear": "ear_normal", "eye": "eye_almond", "brow": "brow_medium", "nose": "nose_medium",
      "beard": "beard_stubble", "mouth": "mouth_medium", "hair": "hair_buzz"}
face = compose("MST-10", GR, False)
err_face = ((L(face) - L(base10)) > 10) & sil512
far_u = np.zeros_like(sil512); miolo_u = np.zeros_like(sil512)
for n in [GR["brow"], GR["beard"], GR["hair"]]:
    far_u |= R1[n][2]; miolo_u |= R1[n][0]
viz = face[..., :3].astype(np.float64) * 0.35
viz[err_face & far_u] = [255, 220, 0]      # erro E distante: amarelo
viz[err_face & ~far_u] = [230, 40, 40]     # erro perto do pelo: vermelho
viz[~err_face & far_u] = [40, 120, 255]    # distante sem erro: azul
img = np.concatenate([face[..., :3], np.full((512, 8, 3), 255, np.uint8), viz.astype(np.uint8)], axis=1)
Image.fromarray(img).save(os.path.join(g["OUT"], "mascara_MST10_gratis_erro_x_distante.png"))
e = err_face.sum()
print(f"\nrosto grátis tom 10 (brow_medium + beard_stubble + hair_buzz): erro {e:,} px; "
      f"{(err_face & far_u).sum()/e*100:.1f}% dele no miolo distante, {(err_face & ~far_u & miolo_u).sum()/e*100:.1f}% no miolo perto, "
      f"{(err_face & ~miolo_u).sum()/e*100:.1f}% fora do miolo de PELO")

# ---------------------------------------------------------------- 3
print("\n== 3. pele quase pura (r > 0,85) e remoção do alpha, tom 10, w = r ==")
print(f"{'camada':18} {'r>0,85 % miolo':>14} {'r>0,85 % dist':>13} | {'erro antes':>10} {'erro depois':>11} {'queda':>6} | {'r med do erro que sobra':>22}")
for name in PELO:
    miolo, r, far = R1[name]
    lay = layer512(name)
    pele = (lay[..., 3] > 0) & (r > 0.85)
    cut_lay = lay.copy(); cut_lay[pele, 3] = 0
    before = ((L(over(base10, hair_edge(lay, src512, base10, "r"))) - L(base10)) > 10) & miolo
    after_c = over(base10, hair_edge(cut_lay, src512, base10, "r"))
    after = ((L(after_c) - L(base10)) > 10) & miolo
    b, a = before.sum(), after.sum()
    rm = float(np.median(r[after])) if a else float("nan")
    print(f"{name:18} {((r>0.85)&miolo).sum()/miolo.sum()*100:14.1f} {((r>0.85)&far).sum()/max(far.sum(),1)*100:13.1f} | {b:10,} {a:11,} {((b-a)/b*100 if b else 0):5.1f}% | {rm:22.2f}")

# histograma de r no miolo distante das camadas do rosto grátis
print("\nr no miolo distante (rosto grátis):")
for n in [GR["hair"], GR["brow"], GR["beard"]]:
    miolo, r, far = R1[n]
    v = r[far]
    if v.size:
        q = np.percentile(v, [5, 25, 50, 75, 95])
        print(f"  {n:14} p5 {q[0]:.2f}  p25 {q[1]:.2f}  p50 {q[2]:.2f}  p75 {q[3]:.2f}  p95 {q[4]:.2f}   (n={v.size:,})")

# imagem do rosto grátis com r>0,85 removido do alpha
def compose_cut(tid, parts):
    base = base512(tid); src = src512; Lt = g["lut"](g["TONE"][tid]["k"]); cv = base.copy()
    for slot in g["ORDER"]:
        n = parts[slot]; lay = layer512(n)
        if slot in g["SKIN"]:
            cv = over(cv, g["tone_layer"](lay, Lt), g["OFFSET"].get(n, 0))
        else:
            rr = rmap(lay, src); c = lay.copy(); c[(c[..., 3] > 0) & (rr > 0.85), 3] = 0
            cv = over(cv, hair_edge(c, src, base, "r"))
    return cv
cut_face = compose_cut("MST-10", GR)
img = np.concatenate([face[..., :3], np.full((512, 8, 3), 255, np.uint8), cut_face[..., :3]], axis=1)
Image.fromarray(img).save(os.path.join(g["OUT"], "mascara_MST10_gratis_r085_removido.png"))
ec = (((L(cut_face) - L(base10)) > 10) & sil512).sum()
print(f"\nrosto grátis tom 10, r>0,85 fora do alpha: erro {e:,} -> {ec:,} px ({(e-ec)/e*100:.1f}% a menos)")
