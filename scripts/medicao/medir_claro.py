"""Qual regra fica mais perto da referência em TOM CLARO: w = r ou a tabela w(r) de wr.json?

Até 16/09 nenhuma referência existia fora do MST-10: w = r nunca foi medido em tom claro. Este
script recebe renders do gerador sobre a base de um tom (skin01 = MST-01 por padrão) e compara, em
512 e a partir do build (o que o runtime faz), os compostos das duas regras com a referência.

Por referência: reamostra para 512 (Lanczos, só para medir; não é asset), divide pelo ganho de
controle (mediana ref/base na testa nua, fora da máscara, por canal), e mede dentro da máscara
nativa da camada (miolo alpha > 200, e núcleo r < 0,15 / banda 0,15-0,85 / claro >= 0,85):

    razão à base (mediana de Y/Y_base) por região, para REF*, w = r, tabela
    erro = mediana e média de |L_regra - L_ref*| em níveis sRGB, no miolo e na banda

Uso: python scripts/medicao/medir_claro.py --layer hair_buzz --tone MST-01 --ref A.png [--ref B.png]
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
os.environ.setdefault("MEDICAO_OUT", os.environ.get("TEMP", "."))
import medir_w_de_r as m
from gate_wr import table_of

EDGE = 512


def Y8(im):
    return m.srgb8(m.Y(m.lin(im[..., :3]))).astype(float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", default="hair_buzz")
    ap.add_argument("--tone", default="MST-01")
    ap.add_argument("--ref", action="append", required=True)
    ap.add_argument("--out", default=os.environ["MEDICAO_OUT"])
    a = ap.parse_args()
    wr = json.load(open(os.path.join(ROOT, "build", "wr.json"), encoding="utf8"))
    tones = json.load(open(os.path.join(ROOT, "build", "tones.json"), encoding="utf8"))
    src = m.g["load"](os.path.join(ROOT, "build", "source.webp"))
    base = m.base512(a.tone)
    lay = m.layer512(a.layer)
    table = table_of(wr, a.layer)
    hoje = m.over(base, m.hair_edge(lay, src, base, "r"))
    novo = m.over(base, m.apply_rule(lay, src, base, table))

    # regiões pela camada nativa em 512
    s0 = m.lin(src[..., :3])[..., 0]; l0 = m.lin(lay[..., :3])[..., 0]
    r = np.where(s0 > 0, l0 / np.where(s0 > 0, s0, 1), 0)
    sil = m.silhouette(src[..., :3])
    MIOLO = (lay[..., 3] > 200) & sil
    CORE, BAND, CLARO = MIOLO & (r < 0.15), MIOLO & (r >= 0.15) & (r < 0.85), MIOLO & (r >= 0.85)
    x0, y0, x1, y1 = [int(v * EDGE / 1254) for v in tones["windowDisplay"]]
    ctrl = np.zeros_like(sil); ctrl[y0:y1, x0:x1] = True; ctrl &= sil & ~(lay[..., 3] > 0)
    if ctrl.sum() < 200:
        ys, xs = np.nonzero(lay[..., 3] > 0); cols = (xs > EDGE * 0.42) & (xs < EDGE * 0.58)
        hb = int(np.percentile(ys[cols], 99)); ctrl = np.zeros_like(sil); ctrl[hb + 16:hb + 56, int(EDGE * 0.42):int(EDGE * 0.58)] = True
        ctrl &= sil & ~(lay[..., 3] > 0)
    Yb = Y8(base)
    ratio = lambda im, mk: float(np.median((m.Y(m.lin(im[..., :3])) / np.maximum(m.Y(m.lin(base[..., :3])), 1e-6))[mk]))
    print(f"camada {a.layer} sobre {a.tone} ({tones['tones'][[t['id'] for t in tones['tones']].index(a.tone)]['base']}), 512 do build; controle {ctrl.sum():,} px; miolo/núcleo/banda/claro {MIOLO.sum():,}/{CORE.sum():,}/{BAND.sum():,}/{CLARO.sum():,} px")
    print(f"{'imagem':28} {'miolo':>6} {'núcleo':>6} {'banda':>6} {'claro':>6} | {'L miolo':>7}")
    rows = {"w = r (hoje)": hoje, "tabela w(r)": novo}
    for k, im in rows.items():
        print(f"{k:28} {ratio(im, MIOLO):6.2f} {ratio(im, CORE):6.2f} {ratio(im, BAND):6.2f} {ratio(im, CLARO):6.2f} | {Y8(im)[MIOLO].mean():7.1f}")
    refs = []
    for p in a.ref:
        im = Image.open(p).convert("RGB")
        note = "" if im.size == (EDGE, EDGE) else f" (reamostrada de {im.size[0]} para medir)"
        R = np.asarray(im.resize((EDGE, EDGE), Image.LANCZOS)) if im.size != (EDGE, EDGE) else np.asarray(im)
        Rl = m.lin(R)
        gain = np.array([np.median((Rl[..., c] / np.maximum(m.lin(base[..., :3])[..., c], 1e-6))[ctrl]) for c in range(3)])
        Rn = m.srgb8(Rl / gain)
        refs.append(Rn)
        print(f"REF* {os.path.basename(p)[-14:]:22} {ratio(Rn, MIOLO):6.2f} {ratio(Rn, CORE):6.2f} {ratio(Rn, BAND):6.2f} {ratio(Rn, CLARO):6.2f} | {Y8(Rn)[MIOLO].mean():7.1f}   ganho R/G/B {gain[0]:.3f}/{gain[1]:.3f}/{gain[2]:.3f}{note}")
    print(f"\nerro |L_regra - L_ref*| em níveis (mediana / média), por referência:")
    print(f"{'regra':28} " + " ".join(f"{'miolo':>13} {'banda':>13} {'núcleo':>13}" for _ in refs))
    for k, im in rows.items():
        cells = []
        for Rn in refs:
            d = np.abs(Y8(im) - Y8(Rn))
            cells += [f"{np.median(d[mk]):6.1f}/{d[mk].mean():6.1f}" for mk in (MIOLO, BAND, CORE)]
        print(f"{k:28} " + " ".join(cells))
    sep = np.full((EDGE, 8, 3), 255, np.uint8)
    Image.fromarray(np.concatenate([hoje[..., :3], sep, novo[..., :3]] + sum([[sep, R] for R in refs], []), 1)).save(os.path.join(a.out, f"claro_{a.layer}_{a.tone}_hoje_tabela_refs.png"))
    print("imagem em", a.out)


if __name__ == "__main__":
    main()
