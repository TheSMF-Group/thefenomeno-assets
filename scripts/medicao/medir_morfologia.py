"""Medição, sem implementar: o halo junto ao pelo é o fechamento da extração?

1. distância de cada pixel de erro do hair_buzz em MST-10 ao pelo opaco e à borda da máscara;
2. hair_buzz reextraído com fechamento disk(6) (receita), disk(2) e disk(0), nada mais mudado;
3. o mesmo nas camadas do meio e nas de núcleo forte.

Cada camada reextraída passa pelo mesmo caminho do build (Lanczos 1254 -> 512, flood do RGB,
WebP q88 com alpha_quality 100) e é decodificada de volta, para compor como o runtime compõe.
O caminho é validado contra build/layers/ com o fechamento da receita.

Rode de fora do repo: python scripts/medicao/medir_morfologia.py (imagens em MEDICAO_OUT ou cwd).
"""
import importlib.util, io, os
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

code = open(os.path.join(HERE, "medir_pelo.py"), encoding="utf8").read()
g = {"__file__": os.path.join(HERE, "medir_pelo.py")}
exec(code[:code.index("# ---------------------------------------------------------------- 1. distribuição")], g)
exec(code[code.index("# ---------------------------------------------------------------- composição"):code.index("GRATIS = {")], g)
OUT, lin, load, silhouette, srgb8 = (g[k] for k in ["OUT", "lin", "load", "silhouette", "srgb8"])
layer512, base512, hair_edge, over = (g[k] for k in ["layer512", "base512", "hair_edge", "over"])
lut, tone_layer, TONE, ORDER, SKIN, OFFSET = (g[k] for k in ["lut", "tone_layer", "TONE", "ORDER", "SKIN", "OFFSET"])

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

ex = load_module("extract_layers", os.path.join(ROOT, "scripts", "extract-layers.py"))
cwd = os.getcwd(); os.chdir(ROOT)
mb = load_module("make_build", os.path.join(ROOT, "make_build.py"))
os.chdir(cwd)

RAW_BASE = np.asarray(Image.open(os.path.join(ROOT, "raw", ex.BASE)).convert("RGB"))
SRC = load(os.path.join(ROOT, "build", "source.webp"))
SIL = silhouette(SRC[..., :3])
B10, B01 = base512("MST-10"), base512("MST-01")

def extract_close(name, close):
    """Receita inteira, só o raio do fechamento muda. Devolve (gate, rgba 512 decodificado, máscara 1254)."""
    saved = ex.CLOSE_DISK
    ex.CLOSE_DISK = close
    try:
        m, rgba = ex.extract(name, RAW_BASE)
    finally:
        ex.CLOSE_DISK = saved
    blobs, dentro, fora, cov = ex.gate(name, m)
    exp = ex.BLOB_EXCEPTIONS.get(name, ex.EXPECTED_BLOBS.get(ex.slot_of(name), 1))
    small = mb.flood_rgb(Image.fromarray(rgba, "RGBA").resize((mb.OUT, mb.OUT), Image.LANCZOS))
    buf = io.BytesIO(); small.save(buf, "WEBP", **mb.LAYER_OPTS)
    dec = np.array(Image.open(io.BytesIO(buf.getvalue())).convert("RGBA"))
    holes = int((ndimage.binary_fill_holes(m) & ~m).sum())
    return {"blobs": blobs, "exp": exp, "ok": blobs == exp and dentro is not False, "cov": cov,
            "fora": fora, "holes": holes, "kb": len(buf.getvalue()) / 1024}, dec, m

def Y(rgb):
    l = lin(rgb[..., :3]); return 0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]
def L(rgb):
    return srgb8(Y(rgb)).astype(np.float64)
def rmap(lay):
    lr, sr = lin(lay[..., 0]), lin(SRC[..., 0])
    return np.where(sr > 0, lr / np.where(sr > 0, sr, 1), 0)
def err(comp, base):
    return ((L(comp) - L(base)) > 10) & SIL
def alone(lay, base, mode="r"):
    return over(base, hair_edge(lay, SRC, base, mode))

def face(tid, parts, override=None, w1=()):
    base = base512(tid); Lt = lut(TONE[tid]["k"]); cv = base.copy()
    for slot in ORDER:
        n = parts[slot]
        lay = (override or {}).get(n)
        if lay is None:
            lay = layer512(n)
        if slot in SKIN:
            cv = over(cv, tone_layer(lay, Lt), OFFSET.get(n, 0))
        else:
            cv = over(cv, hair_edge(lay, SRC, base, "1" if n in w1 else "r"))
    return cv

def save_row(fname, imgs, half=False):
    sep = np.full((512, 8, 3), 255, np.uint8)
    row = [imgs[0][..., :3]]
    for im in imgs[1:]:
        row += [sep, im[..., :3]]
    img = Image.fromarray(np.concatenate(row, axis=1))
    if half:
        img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
    img.save(os.path.join(OUT, fname))

# ---------------------------------------------------------------- validação do caminho
print("== validação: reextração com a receita (disk 6) contra build/layers/ ==")
for n in ["hair_buzz", "beard_goatee"]:
    _, dec, _ = extract_close(n, 6)
    ref = layer512(n)
    d = np.abs(dec.astype(int) - ref.astype(int))
    print(f"  {n:14} max |dif| RGB {d[..., :3].max()}, alpha {d[..., 3].max()}; pixels diferentes {(d.max(axis=2) > 0).sum():,}")

# ---------------------------------------------------------------- 1. espessura do halo
print("\n== 1. hair_buzz sozinho em MST-10 (w = r): distância de cada pixel de erro ==")
buzz = layer512("hair_buzz")
miolo = (buzz[..., 3] > 200) & SIL
opaco = miolo & (rmap(buzz) < 0.15)
e = err(alone(buzz, B10), B10) & (buzz[..., 3] > 0)
d_op = ndimage.distance_transform_edt(~opaco)[e]
d_edge = ndimage.distance_transform_edt(buzz[..., 3] > 0)[e]   # distância à borda externa da máscara
for nome, d in [("ao pelo opaco", d_op), ("à borda externa da máscara", d_edge)]:
    h, _ = np.histogram(d, bins=np.arange(0, 42, 2))
    q = np.percentile(d, [10, 25, 50, 75, 90])
    moda = int(np.argmax(h)) * 2
    print(f"\n  distância {nome} (512 px), n = {d.size:,}")
    print(f"  p10 {q[0]:.1f}  p25 {q[1]:.1f}  p50 {q[2]:.1f}  p75 {q[3]:.1f}  p90 {q[4]:.1f}   IQR {q[3]-q[1]:.1f}")
    print(f"  moda na faixa {moda}-{moda+2} px; {h.max()/d.size*100:.1f}% nela; {((d >= moda - 2) & (d < moda + 4)).mean()*100:.1f}% em ±1 faixa")
    for k, c in enumerate(h):
        print(f"   {k*2:2d}-{k*2+2:2d} {c:6,} {'#' * int(round(c / max(h.max(), 1) * 50))}")
print(f"\n  referência: fechamento disk(6) em 1254 = {6 * 512 / 1254:.2f} px em 512; abertura disk(4) = {4 * 512 / 1254:.2f} px; blur sigma 1,5 = {1.5 * 512 / 1254:.2f} px")

# ---------------------------------------------------------------- 2. buzz com fechamento menor
GR = {"ear": "ear_normal", "eye": "eye_almond", "brow": "brow_medium", "nose": "nose_medium",
      "beard": "beard_stubble", "mouth": "mouth_medium", "hair": "hair_buzz"}
B_GROUP = ["beard_stubble", "brow_thin", "brow_medium"]
print("\n== 2. hair_buzz reextraído: fechamento disk(6) receita, disk(2), disk(0) ==")
print(f"{'fechamento':10} {'blobs':>5} {'esp':>3} {'gate':>5} {'cobertura':>10} {'buracos tapados':>15} {'KB':>5} | {'erro só buzz':>12} {'rosto grátis A=nada B=w1':>24} | {'MST-01 |ΔL|>10':>15}")
buzz_imgs, face_imgs = [], []
hoje01 = face("MST-01", GR, w1=B_GROUP)
for close in [6, 2, 0]:
    gate, dec, _ = extract_close("hair_buzz", close)
    a10 = alone(dec, B10)
    f10 = face("MST-10", GR, override={"hair_buzz": dec}, w1=B_GROUP)
    f01 = face("MST-01", GR, override={"hair_buzz": dec}, w1=B_GROUP)
    d01 = (np.abs(L(f01) - L(hoje01)) > 10)[SIL].mean() * 100
    buzz_imgs.append(a10); face_imgs.append(f10)
    print(f"disk({close})    {gate['blobs']:5d} {gate['exp']:3d} {('ok' if gate['ok'] else 'FALHA'):>5} {gate['cov']:10,} {gate['holes']:15,} {gate['kb']:5.1f} | "
          f"{err(a10, B10).sum():12,} {err(f10, B10).sum():24,} | {d01:14.2f}%")
save_row("morf_2_buzz_MST10_disk6_2_0.png", buzz_imgs)
save_row("morf_2_gratis_MST10_B_disk6_2_0.png", face_imgs)

# ---------------------------------------------------------------- 3. outras camadas
print("\n== 3. outras camadas, sozinhas em MST-10 (w = r) ==")
print(f"{'camada':16} {'fech':>4} {'blobs':>5} {'esp':>3} {'gate':>5} {'cobertura':>10} {'buracos tapados':>15} | {'erro':>6} {'queda':>6}")
for n in ["beard_goatee", "hair_lowfade", "beard_mustache", "brow_thick", "hair_midcurly", "beard_longfull"]:
    base_err = None; imgs = []
    for close in [6, 2, 0]:
        gate, dec, _ = extract_close(n, close)
        comp = alone(dec, B10); imgs.append(comp)
        e = err(comp, B10).sum()
        base_err = e if base_err is None else base_err
        print(f"{n:16} {close:4d} {gate['blobs']:5d} {gate['exp']:3d} {('ok' if gate['ok'] else 'FALHA'):>5} {gate['cov']:10,} {gate['holes']:15,} | {e:6,} {(base_err - e)/base_err*100 if base_err else 0:5.1f}%")
    save_row(f"morf_3_{n}_MST10_disk6_2_0.png", imgs, half=True)
    if n in ("hair_midcurly", "beard_longfull"):
        save_row(f"morf_3_{n}_MST01_disk6_0.png", [alone(extract_close(n, c)[1], B01) for c in (6, 0)], half=True)
print("imagens em", OUT)
