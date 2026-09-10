"""Gera assets/build/: tudo em 512, WebP. Ver NOTES.md.

Reescala uma vez, no build. O runtime nunca interpola: recebe base e camada ja
no mesmo canvas e so compoe.

  bases   1092 -> 512, Lanczos, WebP qualidade 88
  camadas 1254 -> 512, Lanczos, WebP qualidade 88 com alpha_quality=100

O alpha das camadas NAO e comprimido com perda. A borda da mascara e o que
custou mais iteracao no projeto; alpha_quality=100 faz o canal alfa passar
sem perda, e exact=True impede o encoder de zerar o RGB sob os pixels
totalmente transparentes.

Nao toca em raw/ nem em layers/.
"""
import os
import shutil

import numpy as np
from PIL import Image
from scipy import ndimage

# De que opacidade para cima o RGB de um pixel e confiavel como fonte do flood.
# Abaixo disso o un-premultiply do resize divide por um alpha minusculo e o
# resultado e ruido: na faixa alpha 1..3 o RGB medio da uma cor suja
# (176, 43, 35) com extremos em 0 e 255, contra ~(218, 152, 127) estavel de
# alpha 8 para cima.
FLOOD_SOURCE_ALPHA = 8

# Ate onde o flood vai, em pixels do canvas de 512. Uma faixa de 16 px cobre os
# primeiros niveis de mipmap (ate 32x32) e a escala de textura que da para
# esperar. O flood completo nao acrescenta seguranca util e custa quase o triplo
# em bytes: numa amostra de 6 camadas, +22% com raio 16 contra +59% sem limite,
# porque area preta chapada comprime para quase nada e area com cor nao.
FLOOD_RADIUS = 16


def flood_rgb(im):
    """
    Preenche o RGB dos pixels totalmente transparentes com a cor do vizinho
    opaco mais proximo, ate FLOOD_RADIUS px para fora da mascara. O alpha nao e
    tocado, e o RGB de quem tem alpha > 0 tambem nao — esses pesam na
    composicao.

    Por que: o resize com alpha do Pillow premultiplica, e onde o alpha e 0 a
    divisao de volta nao existe, entao o RGB sai preto. Hoje isso e inofensivo
    (peso zero na composicao), mas vira halo escuro no dia em que alguem gerar
    mipmap ou escalar a textura. Custa nada agora.
    """
    rgb = np.asarray(im.convert("RGB")).copy()
    alpha = np.asarray(im.getchannel("A"))
    holes = alpha == 0
    source = alpha >= FLOOD_SOURCE_ALPHA
    if not holes.any() or not source.any():
        return im
    # indice do pixel-fonte mais proximo, para cada pixel
    dist, (iy, ix) = ndimage.distance_transform_edt(~source, return_indices=True)
    band = holes & (dist <= FLOOD_RADIUS)
    rgb[band] = rgb[iy[band], ix[band]]
    out = Image.fromarray(rgb).convert("RGBA")
    out.putalpha(im.getchannel("A"))
    return out

OUT = 512
BUILD = "build"
BASE_OPTS = {"quality": 88, "method": 6}
LAYER_OPTS = {"quality": 88, "alpha_quality": 100, "exact": True, "method": 6}


def kb(path):
    return os.path.getsize(path) / 1024


def main():
    for sub in ("bases", "layers"):
        os.makedirs(os.path.join(BUILD, sub), exist_ok=True)

    bases = sorted(f for f in os.listdir("raw")
                   if f.lower().startswith("skin") and f.lower().endswith((".png", ".webp")))
    layers = sorted(f for f in os.listdir("layers") if f.endswith(".png"))

    print("| base | origem | saida KB |")
    print("|---|---|---|")
    total_b = 0
    for f in bases:
        im = Image.open(f"raw/{f}").convert("RGB")
        src = im.size[0]
        out = os.path.join(BUILD, "bases", os.path.splitext(f)[0] + ".webp")
        im.resize((OUT, OUT), Image.LANCZOS).save(out, "WEBP", **BASE_OPTS)
        total_b += kb(out)
        print("| %s | %dpx | %.1f |" % (os.path.basename(out), src, kb(out)))
    print("| **10 bases** | | **%.1f KB** |" % total_b)

    print()
    print("| camada | origem | saida KB | alpha identico ao downscale |")
    print("|---|---|---|---|")
    total_l = 0
    alpha_ok = 0
    rgb_err = []
    for f in layers:
        im = Image.open(f"layers/{f}").convert("RGBA")
        src = im.size[0]
        small = flood_rgb(im.resize((OUT, OUT), Image.LANCZOS))
        out = os.path.join(BUILD, "layers", os.path.splitext(f)[0] + ".webp")
        small.save(out, "WEBP", **LAYER_OPTS)
        total_l += kb(out)

        # o alpha tem que voltar byte a byte igual ao que o Lanczos produziu
        back = Image.open(out).convert("RGBA")
        same = np.array_equal(np.asarray(back.getchannel("A")), np.asarray(small.getchannel("A")))
        alpha_ok += same
        core = np.asarray(small.getchannel("A")) > 200
        if core.any():
            d = np.abs(np.asarray(back.convert("RGB")).astype(int)
                       - np.asarray(small.convert("RGB")).astype(int))[core]
            rgb_err.append(d.mean())
        print("| %s | %dpx | %.1f | %s |" % (os.path.basename(out), src, kb(out), "sim" if same else "NAO"))
    print("| **32 camadas** | | **%.1f KB** | %d de %d |" % (total_l, alpha_ok, len(layers)))

    print()
    print("total do build: %.1f KB (%.2f MB)" % (total_b + total_l, (total_b + total_l) / 1024))
    print("erro medio de RGB no miolo, pela qualidade 88: %.2f niveis (max por camada %.2f)"
          % (float(np.mean(rgb_err)), float(np.max(rgb_err))))

    shutil.copy("tones.json", os.path.join(BUILD, "tones.json"))
    print("copiado tones.json (inalterado: k e razao de medias, invariante a escala)")


if __name__ == "__main__":
    main()
