"""Gera assets/build/: tudo em 512, WebP. Ver NOTES.md.

Reescala uma vez, no build. O runtime nunca interpola: recebe base e camada ja
no mesmo canvas e so compoe.

  bases   1092 -> 512, Lanczos, WebP qualidade 88
  camadas 1254 -> 512, Lanczos, WebP qualidade 88 com alpha_quality=100

O alpha das camadas NAO e comprimido com perda. A borda da mascara e o que
custou mais iteracao no projeto; alpha_quality=100 faz o canal alfa passar
sem perda, e exact=True impede o encoder de zerar o RGB sob os pixels
totalmente transparentes.

Escreve tambem build/source.webp: a base de origem (tmp_1) no mesmo canvas de
512. O runtime precisa dela para a familia PELO, que calcula r = camada / source
por pixel. Ver "A cadeia de PELO" no NOTES.

Escreve tambem build/validacao_tons.png, a folha de contato composta A PARTIR
DO BUILD: base e camada ja em 512, sem reamostrar nada, que e o que o runtime
faz. Nao confundir com a folha que make_tones.py escreve na raiz, que compoe o
material de trabalho (1092 e 1254) e serve para validar a medicao, nao a
entrega.

Nao toca em raw/ nem em layers/.
"""
import json
import os
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

# De que opacidade para cima o RGB de um pixel e confiavel como fonte do flood.
# Abaixo disso o un-premultiply do resize divide por um alpha minusculo e o
# resultado e ruido: na faixa alpha 1..3 o RGB medio da uma cor suja
# (176, 43, 35) com extremos em 0 e 255, contra ~(218, 152, 127) estavel de
# alpha 8 para cima.
FLOOD_SOURCE_ALPHA = 8

# Ate onde o flood vai, em pixels do canvas de 512.
#
# Cada nivel de mipmap e gerado do anterior, entao a exigencia de pixels validos
# dobra a cada nivel: 1 px protege o mip 1 (256), 2 px o mip 2 (128), 4 px o mip
# 3 (64), 8 px o mip 4 (32), 16 px o mip 5 (16).
#
# 4 px protege ate a cabeca desenhada a 64 px, que cobre o uso plausivel: avatar
# de seletor fica entre 64 e 128. Abaixo de 64 px nao protege; se o jogo passar
# a desenhar cabeca menor que isso, subir para 8.
#
# Custo medido sobre as 32 camadas, com o build inteiro em 491,8 KB sem flood:
#
#   raio  2    +1,8 KB   (+1%)    so mip 2
#   raio  4   +32,3 KB   (+9%)    <- aqui
#   raio  8   +60,8 KB  (+17%)    mip 4
#   raio 16   +85,7 KB  (+25%)    mip 5
#   sem limite +242,4 KB (+70%)
#
# O flood total esta descartado: metade do bundle para proteger tamanhos de tela
# que nao existem. A escolha anterior de 16 foi feita antes desta tabela existir.
FLOOD_RADIUS = 4


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
# A base de origem das camadas. O runtime precisa dela para calcular
# r = camada / source, que e o que a correcao de borda de PELO consome.
SOURCE = "raw/tmp_1.png"
BASE_OPTS = {"quality": 88, "method": 6}
LAYER_OPTS = {"quality": 88, "alpha_quality": 100, "exact": True, "method": 6}

# Camada usada na folha de contato. A mesma de make_tones.py, para que os
# quadros das duas folhas sejam comparaveis um a um.
PROBE = "nose_medium"

SHEET_FRAME = 200   # lado do quadro na folha
SHEET_GUTTER = 6    # espaco entre quadros
SHEET_LABEL = 26    # altura da faixa do rotulo


def kb(path):
    return os.path.getsize(path) / 1024


def to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def to_srgb(c):
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(np.clip(c, 0, None), 1 / 2.4) - 0.055)


def sheet_font():
    for path in ("C:/Windows/Fonts/arialbd.ttf",
                 "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(path, 18)
        except OSError:
            continue
    return ImageFont.load_default()


def contact_sheet():
    """
    Folha de validacao gerada DO BUILD.

    Base e camada saem de build/, ja em 512, e sao compostas sem reamostrar
    nada — que e exatamente o que o runtime faz. E o que separa esta folha da
    que make_tones.py escreve na raiz: aquela valida o material de trabalho
    (bases de 1092, camadas de 1254, e precisa reduzir a camada para compor);
    esta valida o que vai para o jogo, depois do Lanczos e do WebP.

    O k sai de build/tones.json e e aplicado em luz linear, com round e nao
    trunc, para bater byte a byte com o que tone.ts desenha.
    """
    with open(os.path.join(BUILD, "tones.json"), encoding="utf8") as fh:
        tones = json.load(fh)["tones"]

    layer_path = os.path.join(BUILD, "layers", PROBE + ".webp")
    layer = Image.open(layer_path).convert("RGBA")
    alpha = layer.getchannel("A")
    lin = to_linear(np.asarray(layer.convert("RGB")) / 255.0)

    frames = []
    for tone in tones:
        base_name = os.path.splitext(tone["base"])[0] + ".webp"
        base = Image.open(os.path.join(BUILD, "bases", base_name)).convert("RGBA")
        # O runtime nunca interpola: se o build nao entregou base e camada no
        # mesmo canvas, o build esta errado e a folha nao tem o que validar.
        if base.size != layer.size:
            raise SystemExit("build inconsistente: %s e %s.webp estao em canvas "
                             "diferentes (%s x %s)"
                             % (base_name, PROBE, base.size, layer.size))
        k = np.array([tone["k"]["r"], tone["k"]["g"], tone["k"]["b"]])
        toned = np.clip(to_srgb(lin * k), 0, 1)
        toned_img = Image.fromarray(np.round(toned * 255).astype(np.uint8)).convert("RGBA")
        toned_img.putalpha(alpha)
        frame = base.copy()
        frame.alpha_composite(toned_img)
        frames.append((tone["id"], frame.convert("RGB")))

    step = SHEET_FRAME + SHEET_GUTTER
    width = len(frames) * SHEET_FRAME + (len(frames) - 1) * SHEET_GUTTER
    sheet = Image.new("RGB", (width, SHEET_FRAME + SHEET_LABEL), "white")
    draw = ImageDraw.Draw(sheet)
    font = sheet_font()
    for i, (tone_id, frame) in enumerate(frames):
        sheet.paste(frame.resize((SHEET_FRAME, SHEET_FRAME), Image.LANCZOS), (i * step, SHEET_LABEL))
        draw.text((i * step + 2, 4), tone_id, fill="black", font=font)
    out = os.path.join(BUILD, "validacao_tons.png")
    sheet.save(out)
    print("escrito %s  %s  (%d quadros, composto em %dpx sem reamostrar)"
          % (out, sheet.size, len(frames), layer.size[0]))


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

    # A base de origem, no mesmo canvas de 512 e no mesmo encode das bases.
    # Sem ela o runtime nao consegue calcular r e a familia PELO fica sem
    # correcao de borda. Medido: o encode custa 0,02 nivel de erro medio no
    # resultado final (p99 0,4-0,7), bem abaixo dos 2,89 do WebP no miolo.
    src_out = os.path.join(BUILD, "source.webp")
    (Image.open(SOURCE).convert("RGB")
     .resize((OUT, OUT), Image.LANCZOS).save(src_out, "WEBP", **BASE_OPTS))
    print()
    print("escrito %s (%s -> %dpx, %.1f KB) — origem de r para a familia PELO"
          % (src_out, SOURCE, OUT, kb(src_out)))

    shutil.copy("tones.json", os.path.join(BUILD, "tones.json"))
    print("copiado tones.json (inalterado: k e razao de medias, invariante a escala)")

    print()
    contact_sheet()


if __name__ == "__main__":
    main()
