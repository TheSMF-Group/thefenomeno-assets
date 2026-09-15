"""Medição, sem implementar: PELO opaco x sombra, e w = 1 nas camadas de sombra.

Réplica de diagnóstico das funções de tone.ts (LUT de k, applyHairEdgeToRgba), validada
contra pixels lidos do canvas do /criar. Não é código de produção.
"""
import json, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage

A = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # raiz do repo
OUT = os.environ.get("MEDICAO_OUT", os.getcwd())  # imagens: fora do repo por padrão, rode de outra pasta

def lin(u8):
    c = u8.astype(np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def srgb8(l):
    l = np.asarray(l, dtype=np.float64)
    c = np.where(l <= 0, 0.0, np.where(l <= 0.0031308, 12.92 * l, 1.055 * np.power(np.maximum(l, 0), 1 / 2.4) - 0.055))
    v = c * 255
    return np.clip(np.floor(v + 0.5), 0, 255).astype(np.uint8)  # Math.round

def load(p, mode="RGBA"):
    return np.array(Image.open(p).convert(mode))

def silhouette(src_rgb):
    bg = (src_rgb >= 250).all(axis=2)
    lab, n = ndimage.label(~bg)
    if n == 0:
        return ~bg
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    return ndimage.binary_fill_holes(lab == (1 + int(np.argmax(sizes))))

HAIR = ["braids", "buzz", "longtied", "lowfade", "midcurly", "shortcurly", "slickback", "straightpart"]
BEARD = ["chinstrap", "goatee", "longfull", "mustache", "shortfull", "stubble"]
BROW = ["medium", "thick", "thin"]
PELO = [f"hair_{n}" for n in HAIR] + [f"beard_{n}" for n in BEARD] + [f"brow_{n}" for n in BROW]

def dist(layer_rgba, src_rgb, sil):
    a = layer_rgba[..., 3]
    miolo = (a > 200) & sil
    lr, sr = lin(layer_rgba[..., 0]), lin(src_rgb[..., 0])
    r = np.where(sr > 0, lr / np.where(sr > 0, sr, 1), 0)[miolo]
    n = r.size
    return {"miolo": int(n), "opaco_px": int((r < 0.15).sum()), "opaco": (r < 0.15).mean() * 100,
            "meio": ((r >= 0.15) & (r <= 0.85)).mean() * 100, "pele": (r > 0.85).mean() * 100,
            "r_mediana": float(np.median(r))}

# ---------------------------------------------------------------- 1. distribuição
print("== 1. fração de pelo opaco (r < 0,15, canal R, miolo alpha>200, dentro da silhueta) ==")
src_full = load(os.path.join(A, "raw", "tmp_1.png"), "RGB")
sil_full = silhouette(src_full)
src512 = load(os.path.join(A, "build", "source.webp"), "RGB")
sil512 = silhouette(src512)
rows = []
for name in PELO:
    full = load(os.path.join(A, "layers", f"{name}.png"))
    assert full.shape[:2] == src_full.shape[:2], (name, full.shape, src_full.shape)
    d_full = dist(full, src_full, sil_full)
    d512 = dist(load(os.path.join(A, "build", "layers", f"{name}.webp")), src512, sil512)
    rows.append((name, d_full, d512))
rows.sort(key=lambda x: -x[1]["opaco"])
print(f"{'camada':22} {'opaco% cheio':>12} {'opaco px cheio':>15} {'miolo px':>10} {'0,15-0,85%':>10} {'>0,85%':>7} {'r med':>6} | {'opaco% 512':>10} {'opaco px 512':>12}")
for name, d, e in rows:
    print(f"{name:22} {d['opaco']:12.2f} {d['opaco_px']:15,} {d['miolo']:10,} {d['meio']:10.1f} {d['pele']:7.1f} {d['r_mediana']:6.2f} | {e['opaco']:10.2f} {e['opaco_px']:12,}")

fr = np.array([d["opaco"] for _, d, _ in rows])
logf = np.log10(np.maximum(fr, 1e-3))
gaps = logf[:-1] - logf[1:]
k = int(np.argmax(gaps))
print(f"\nmaior salto em log10: entre {rows[k][0]} ({fr[k]:.2f}%) e {rows[k+1][0]} ({fr[k+1]:.2f}%), fator {10**gaps[k]:.1f}x")
second = sorted(gaps, reverse=True)[1]
print(f"segundo maior salto: fator {10**second:.1f}x")
SOMBRA = [n for n, _, _ in rows[k + 1:]]
OPACO = [n for n, _, _ in rows[: k + 1]]
print("grupo opaco:", OPACO)
print("grupo sombra:", SOMBRA)

# ---------------------------------------------------------------- composição (réplica tone.ts)
tones = json.load(open(os.path.join(A, "build", "tones.json"), encoding="utf8"))
TONE = {t["id"]: t for t in tones["tones"]}
EDGE = 512
ORDER = ["ear", "eye", "brow", "nose", "beard", "mouth", "hair"]
SKIN = {"nose", "mouth", "ear", "eye"}
OFFSET = {"ear_normal": round(75 / 1254 * EDGE), "ear_protruding": round(75 / 1254 * EDGE)}
LAYER_CACHE = {}

def layer512(name):
    if name not in LAYER_CACHE:
        LAYER_CACHE[name] = load(os.path.join(A, "build", "layers", f"{name}.webp"))
    return LAYER_CACHE[name]

def base512(tid):
    return load(os.path.join(A, "build", "bases", TONE[tid]["base"]))

def lut(k):
    v = np.arange(256, dtype=np.uint8)
    return [srgb8(lin(v) * k[c]) for c in "rgb"]

def tone_layer(rgba, L):
    out = rgba.copy()
    for c in range(3):
        out[..., c] = L[c][rgba[..., c]]
    return out

def hair_edge(rgba, src_rgba, base_rgba, mode):
    l = lin(rgba[..., :3]); s = lin(src_rgba[..., :3]); b = lin(base_rgba[..., :3])
    if mode == "r":
        w = np.where(s[..., 0] > 0, l[..., 0] / np.where(s[..., 0] > 0, s[..., 0], 1), 0)
        w = np.clip(np.nan_to_num(w), 0, 1)[..., None]
    else:
        w = 1.0
    r = np.where(s > 0, l / np.where(s > 0, s, 1), 0)
    out = rgba.copy()
    out[..., :3] = srgb8(w * (r * b) + (1 - w) * l)
    return out

def over(dst, src, dy=0):
    s = np.zeros_like(src)
    if dy:
        s[dy:] = src[:-dy]
    else:
        s = src
    a = s[..., 3:4].astype(np.float64) / 255
    res = dst.astype(np.float64)
    res[..., :3] = s[..., :3] * a + dst[..., :3] * (1 - a)
    res[..., 3] = 255
    return np.clip(np.floor(res + 0.5), 0, 255).astype(np.uint8)

def compose(tid, parts, sombra_w1):
    base = base512(tid)
    src = load(os.path.join(A, "build", "source.webp"))
    L = lut(TONE[tid]["k"])
    cv = base.copy()
    for slot in ORDER:
        name = parts.get(slot)
        if not name:
            continue
        lay = layer512(name)
        if slot in SKIN:
            cv = over(cv, tone_layer(lay, L), OFFSET.get(name, 0))
        else:
            mode = "1" if (sombra_w1 and name in SOMBRA) else "r"
            cv = over(cv, hair_edge(lay, src, base, mode))
    return cv

GRATIS = {"ear": "ear_normal", "eye": "eye_almond", "brow": "brow_medium", "nose": "nose_medium",
          "beard": "beard_stubble", "mouth": "mouth_medium", "hair": "hair_buzz"}

print("\n== validação da réplica contra o canvas do /criar (MST-10, rosto grátis, w = r) ==")
antes10 = compose("MST-10", GRATIS, False)
for (x, y), canvas in [((180, 300), (88, 61, 52)), ((330, 300), (109, 73, 57)), ((256, 380), (116, 80, 66)), ((256, 110), (122, 100, 94))]:
    got = tuple(int(v) for v in antes10[y, x, :3])
    print(f"  ({x},{y}) réplica {got} canvas {canvas} diff {tuple(g - c for g, c in zip(got, canvas))}")

# ---------------------------------------------------------------- 2. w = 1 nas de sombra
def Ylin(rgb):
    l = lin(rgb[..., :3])
    return 0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]

def Llevels(rgb):
    return srgb8(Ylin(rgb)).astype(np.float64)

print("\n== 2. camada sozinha sobre a base: w = r contra w = 1 ==")
print("mancha = L(composto) - L(base) no miolo, em níveis sRGB; sombra de verdade só escurece (negativo)")
print("clarão = % do miolo com L(composto) > L(base) + 10")
print("textura = desvio de Y(composto)/Y(base) no miolo, como % do desvio nativo de Y(camada)/Y(tmp_1)")
src_rgba = load(os.path.join(A, "build", "source.webp"))
nat_ratio_cache = {}
for tid in ["MST-10", "MST-01"]:
    base = base512(tid)
    print(f"\n-- {tid} --")
    print(f"{'camada':18} {'grupo':6} | {'mancha w=r':>10} {'clarão w=r':>10} {'textura w=r':>11} | {'mancha w=1':>10} {'clarão w=1':>10} {'textura w=1':>11}")
    for name in SOMBRA + OPACO:
        lay = layer512(name)
        miolo = (lay[..., 3] > 200) & sil512
        if name not in nat_ratio_cache:
            yl, ys = Ylin(lay), Ylin(src_rgba)
            nat_ratio_cache[name] = np.std((yl / np.maximum(ys, 1e-6))[miolo])
        res = []
        for mode in ["r", "1"]:
            comp = over(base, hair_edge(lay, src_rgba, base, mode))
            dL = (Llevels(comp) - Llevels(base))[miolo]
            ratio = (Ylin(comp) / np.maximum(Ylin(base), 1e-6))[miolo]
            res.append((dL.mean(), (dL > 10).mean() * 100, np.std(ratio) / nat_ratio_cache[name] * 100))
        g = "sombra" if name in SOMBRA else "opaco"
        print(f"{name:18} {g:6} | {res[0][0]:10.1f} {res[0][1]:9.1f}% {res[0][2]:10.0f}% | {res[1][0]:10.1f} {res[1][1]:9.1f}% {res[1][2]:10.0f}%")

# ---------------------------------------------------------------- gate: imagens antes/depois
def save_pair(tid, parts, fname):
    a = compose(tid, parts, False)
    b = compose(tid, parts, True)
    img = np.concatenate([a, np.full((EDGE, 8, 4), 255, np.uint8), b], axis=1)
    Image.fromarray(img, "RGBA").save(os.path.join(OUT, fname))
    return a, b

a10, b10 = save_pair("MST-10", GRATIS, "gate_MST10_buzz_stubble_antes_depois.png")
save_pair("MST-01", GRATIS, "gate_MST01_buzz_stubble_antes_depois.png")
LOIRO = dict(GRATIS, hair="hair_midcurly_blonde", beard="beard_shortfull", brow="brow_thick")
save_pair("MST-10", LOIRO, "gate_MST10_midcurly_blonde_shortfull_antes_depois.png")

miolo_st = (layer512("beard_stubble")[..., 3] > 200) & sil512
dl_a = (Llevels(a10) - Llevels(base512("MST-10")))[miolo_st]
dl_b = (Llevels(b10) - Llevels(base512("MST-10")))[miolo_st]
print(f"\ngate MST-10 grátis, no miolo da stubble: ΔL médio antes {dl_a.mean():.1f}, depois {dl_b.mean():.1f}; clarão >10 antes {(dl_a>10).mean()*100:.1f}%, depois {(dl_b>10).mean()*100:.1f}%")
print("imagens em", OUT)
