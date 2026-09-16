"""Gate visual da tabela w(r) ligada ao runtime: compõe rostos nativos em 512 A PARTIR DO BUILD,
com a réplica de tone.ts, nas duas regras:

    hoje  = w = r em toda camada de PELO (o runtime antes de wr.json)
    novo  = w(r) de build/wr.json onde a camada tem tabela, w = r onde não tem (o runtime com wr.json)

Combinações (todas nativas; sobrancelha e barba de tabela):
    A  buzz + stubble + brow_medium         (o rosto grátis)
    B  midcurly + longfull + brow_thick
    C  lowfade + goatee + brow_thin
    D  slickback + chinstrap + brow_medium

Para MST-10 escreve <out>/gate_wr_<combo>_MST-10.png (hoje | novo) e conta a mancha (pixels da
silhueta mais de 10 níveis de L acima da base). Para MST-01 e MST-05 mede se o composto MUDOU em
relação a hoje: pixels diferentes, |dif| máximo e média de |dL|. O critério do Santiago é
"idênticos"; o script só mede e imprime, quem pára é quem lê.

Uso: python scripts/medicao/gate_wr.py [--out DIR]
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
os.environ.setdefault("MEDICAO_OUT", os.environ.get("TEMP", "."))
import medir_w_de_r as m

COMBOS = {
    "A": {"hair": "hair_buzz", "beard": "beard_stubble", "brow": "brow_medium"},
    "B": {"hair": "hair_midcurly", "beard": "beard_longfull", "brow": "brow_thick"},
    "C": {"hair": "hair_lowfade", "beard": "beard_goatee", "brow": "brow_thin"},
    "D": {"hair": "hair_slickback", "beard": "beard_chinstrap", "brow": "brow_medium"},
}
SKIN_FREE = {"ear": "ear_normal", "eye": "eye_almond", "nose": "nose_medium", "mouth": "mouth_medium"}


def table_of(wr, name):
    e = wr["layers"].get(name)
    if not e:
        return None
    return np.array([[np.nan if v is None else v for v in e[ch]] for ch in "rgb"], dtype=float)


def face(tid, parts, wr, src512, rule):
    base = m.base512(tid)
    Lt = m.lut(m.TONE[tid]["k"])
    cv = base.copy()
    for slot in m.ORDER:
        n = parts.get(slot)
        if not n:
            continue
        l = m.layer512(n)
        if slot in m.SKIN:
            cv = m.over(cv, m.tone_layer(l, Lt), m.OFFSET.get(n, 0))
            continue
        t = table_of(wr, n) if rule == "novo" else None
        cv = m.over(cv, m.apply_rule(l, src512, base, t) if t is not None else m.hair_edge(l, src512, base, "r"))
    return cv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.environ["MEDICAO_OUT"])
    a = ap.parse_args()
    wr = json.load(open(os.path.join(ROOT, "build", "wr.json"), encoding="utf8"))
    assert list(map(float, wr["edges"])) == list(map(float, m.EDGES)), "edges de wr.json != EDGES da réplica"
    src512 = m.g["load"](os.path.join(ROOT, "build", "source.webp"))
    sil = m.silhouette(src512[..., :3])
    Y = lambda im: m.srgb8(m.Y(m.lin(im[..., :3]))).astype(float)
    print(f"tabela: {len(wr['layers'])} camadas em build/wr.json")
    print(f"\n{'combo':6} {'tom':7} {'mancha hoje':>12} {'mancha novo':>12} {'px diferentes':>14} {'|dif| max':>10} {'|dL| média':>11}")
    for key, hair in COMBOS.items():
        parts = {**SKIN_FREE, **hair}
        for tid in ["MST-10", "MST-05", "MST-01"]:
            base = m.base512(tid)
            hoje, novo = face(tid, parts, wr, src512, "hoje"), face(tid, parts, wr, src512, "novo")
            Lb = Y(base)
            stain = lambda im: int((((Y(im) - Lb) > 10) & sil).sum())
            d = np.abs(hoje[..., :3].astype(int) - novo[..., :3].astype(int))
            diff_px = int((d.max(axis=2) > 0).sum())
            dL = np.abs(Y(novo) - Y(hoje))[sil]
            print(f"{key:6} {tid:7} {stain(hoje):12,} {stain(novo):12,} {diff_px:14,} {int(d.max()):10} {dL.mean():11.2f}")
            if tid == "MST-10":
                sep = np.full((512, 8, 3), 255, np.uint8)
                Image.fromarray(np.concatenate([hoje[..., :3], sep, novo[..., :3]], 1)).save(os.path.join(a.out, f"gate_wr_{key}_{tid}.png"))
            elif diff_px:
                sep = np.full((512, 8, 3), 255, np.uint8)
                amp = np.clip(d.max(axis=2) * 16, 0, 255).astype(np.uint8)
                Image.fromarray(np.concatenate([hoje[..., :3], sep, novo[..., :3], sep, np.stack([amp] * 3, -1)], 1)).save(os.path.join(a.out, f"gate_wr_{key}_{tid}_dif.png"))
    print(f"\nimagens em {a.out}")


if __name__ == "__main__":
    main()
