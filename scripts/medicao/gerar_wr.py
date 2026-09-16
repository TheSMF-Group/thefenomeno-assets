"""Gera wr.json: a tabela w(r) por camada, por canal, por faixa de r, em formato de asset.

Fonte: os pares de referência em raw/_referencia/<camada>_tmp4_chatgpt_{1,2}.png. Para cada camada,
as duas referências são normalizadas pelo próprio ganho de pele nua e os blocos das duas entram
juntos na mediana de T/r por faixa (a "tabela agrupada"). É medição, não escolha: a mesma conta de
medir_w_de_r.calibrate, com o dobro de amostra. Faixa com menos de 20 blocos fica null.

O runtime (tone.ts, applyHairEdgeToRgba) interpola linearmente nos centros das faixas com valor,
repete a ponta fora delas e prende w em [0, 1] — o mesmo que medir_w_de_r.w_of_r.

Camada sem entrada em wr.json cai para w = r no runtime (as 24 coloridas; ver NOTES).

Uso (da raiz do repo): python scripts/medicao/gerar_wr.py
Escreve wr.json na raiz; make_build.py copia para build/.
"""
import glob, json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
os.environ.setdefault("MEDICAO_OUT", os.environ.get("TEMP", "."))
import medir_w_de_r as m   # importa a réplica (imprime a validação dela; inofensivo)

EDGES = m.EDGES


def samples(layer, ref_path, b=8):
    """(r, T/r, máscara) em blocos b para uma referência normalizada. Mesma conta de calibrate."""
    S8, B8 = m.rgb(os.path.join(ROOT, "raw", "tmp_1.png")), m.rgb(os.path.join(ROOT, "raw", "tmp_4.png"))
    S, B = m.lin(S8), m.lin(B8)
    R8 = m.rgb(ref_path)
    L1, L4 = m.lin(m.rgb(os.path.join(ROOT, "raw", f"{layer}.png"))), m.lin(R8)
    lay = np.asarray(Image.open(os.path.join(ROOT, "layers", f"{layer}.png")).convert("RGBA"))
    sil = m.silhouette(S8) & m.silhouette(B8) & m.silhouette(R8)
    gain = m.control_gain(L4, B, lay, sil)
    L4 = L4 / gain
    Sb, Bb, L1b, L4b = m.blk(S, b), m.blk(B, b), m.blk(L1, b), m.blk(L4, b)
    mask = (m.blk(sil.astype(float)[..., None], b)[..., 0] > 0.99) & (m.blk((lay[..., 3] > 0).astype(float)[..., None], b)[..., 0] > 0.5)
    r = L1b / np.maximum(Sb, 1e-6)
    T = (L1b - L4b) / np.where(np.abs(Sb - Bb) > 1e-4, Sb - Bb, np.nan)
    w = T / np.maximum(r, 1e-6)
    return r, w, mask, gain


def pooled_table(layer, refs):
    rs, ws, ms, gains = [], [], [], []
    for p in refs:
        r, w, mask, gain = samples(layer, p)
        rs.append(r); ws.append(w); ms.append(mask); gains.append(gain)
    r, w, mask = np.concatenate(rs), np.concatenate(ws), np.concatenate(ms)
    table = np.full((3, len(EDGES) - 1), np.nan)
    for c in range(3):
        for i, (lo, hi) in enumerate(zip(EDGES[:-1], EDGES[1:])):
            mm = mask & (r[..., c] >= lo) & (r[..., c] < hi) & np.isfinite(w[..., c])
            if mm.sum() >= 20:
                table[c, i] = np.median(w[..., c][mm])
    return table, gains


def main():
    layers = sorted({os.path.basename(p).split("_tmp4_")[0] for p in glob.glob(os.path.join(ROOT, "raw", "_referencia", "*_tmp4_chatgpt_1.png"))})
    out = {
        "source": "tmp_1.png",
        "reference": "tmp_4.png (MST-10), dois renders por camada, normalizados pela testa nua",
        "rule": "novo = L - w(r) * r * (S - B) em luz linear, por canal; w interpolado nos centros das faixas, ponta repetida fora, preso em [0, 1]",
        "edges": [float(e) for e in EDGES],
        "layers": {},
    }
    print(f"{'camada':22} {'ganhos R (ref1/ref2)':22} tabela R por faixa")
    for layer in layers:
        refs = sorted(glob.glob(os.path.join(ROOT, "raw", "_referencia", f"{layer}_tmp4_chatgpt_[12].png")))
        if len(refs) != 2:
            print(f"  {layer}: {len(refs)} referência(s), precisa de 2; pulada"); continue
        if layer.count("_") > 1:   # nativas têm um só "_" (hair_buzz); coloridas dois (hair_midcurly_blonde)
            print(f"  {layer}: colorida, sem método (NOTES); fica em w = r"); continue
        table, gains = pooled_table(layer, refs)
        out["layers"][layer] = {ch: [None if not np.isfinite(v) else round(float(v), 3) for v in table[c]] for c, ch in enumerate("rgb")}
        print(f"{layer:22} {gains[0][0]:.3f}/{gains[1][0]:.3f}{'':12} " + " ".join("  -- " if v is None else f"{v:.3f}" for v in out["layers"][layer]["r"]))
    path = os.path.join(ROOT, "wr.json")
    # compacto: asset de produção, sem indentação (16/09: indentado dava 8.127 bytes, 3,7 KB de nada)
    open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"\n{len(out['layers'])} camadas em {path}: {os.path.getsize(path):,} bytes (compacto)")


if __name__ == "__main__":
    main()
