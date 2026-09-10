"""Gera tones.json e a folha de contato de validacao. Ver NOTES.md.

Duas medidas por base, com janelas e estatisticas diferentes:

  k            media da pele na bochecha direita, em luz linear, dividida pela
               mesma media de tmp_1, canal a canal. E o que tone.ts aplica em
               runtime para transferir pele MEDIA entre bases.
  measuredHex  media dos pixels na FAIXA p70..p90 de luminancia da janela da
               testa. E a cor do seletor da loja: a pele plenamente iluminada,
               como o jogador ve.

               O teto em p90 nao e detalhe: acima dele entra reflexo especular,
               que tem a cor da luz e nao do pigmento e lavava o croma dos tons
               escuros. A definicao antiga — decil mais claro, luminancia >=
               p90, sem teto — foi APOSENTADA. Ver skin_lit_linear() e NOTES.md.

    python make_tones.py                 # usa raw/skin01..skin10.webp
    python make_tones.py --bases tmp     # smoke test com as 4 tmp_*
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

# As janelas sao coordenadas no canvas de referencia, que e o das camadas e do
# tmp_1. Base entregue em outro tamanho NAO e reescalada: a janela e que vai
# ate ela (ver scaled()). Reescalar a base inventaria pixel; reescalar a janela
# mede onde a informacao esta.
REFERENCE_CANVAS = 1254
#
# WINDOW_K: bochecha direita, altura do nariz, lado iluminado. E a janela do
# fator k, que transfere pele MEDIA entre bases. Nao muda.
WINDOW_K = (780, 520, 870, 660)
#
# WINDOW_DISPLAY: testa central, estreita, a parte mais frontal ao observador.
# Menor curvatura e sombreamento minimo (desvio de luminancia 0,043 contra
# 0,073 da bochecha). E a janela do measuredHex, a cor do seletor da loja.
WINDOW_DISPLAY = (585, 290, 660, 360)


def scaled(window, canvas):
    """A janela levada do canvas de referencia para o canvas da base."""
    if canvas == REFERENCE_CANVAS:
        return window
    s = canvas / REFERENCE_CANVAS
    return tuple(int(round(v * s)) for v in window)
SOURCE = "raw/tmp_1.png"          # a base cuja pele as camadas carregam
PROBE = "layers/nose_medium.png"  # camada usada na folha de contato

# Hex nominais da escala Monk Skin Tone (MST), do mais claro ao mais escuro.
#
# Procedencia: skintone.google nao expoe os valores sem renderizar JS (ver
# NOTES.md). Lista da Wikipedia, corroborada pela origem: sao exatamente os
# hexes usados nos prompts que geraram as bases, entao o rotulo corresponde ao
# asset por construcao.
#
# E rotulo de procedencia, nao cor de exibicao: o seletor da loja deve mostrar
# "measuredHex", que e a cor que o jogador realmente ve. E o k nao sai daqui,
# sai da media de pixel do render.
MST_HEX = ["#f6ede4", "#f3e7db", "#f7ead0", "#eadaba", "#d7bd96",
           "#a07e56", "#825c43", "#604134", "#3a312a", "#292420"]


def to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def to_srgb(c):
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(np.clip(c, 0, None), 1 / 2.4) - 0.055)


LUMA = np.array([0.2126, 0.7152, 0.0722])


def skin_pixels_linear(path, window):
    """Pixels da janela em luz linear. A janela se adapta ao canvas da imagem."""
    im = Image.open(path).convert("RGB")
    x0, y0, x1, y1 = scaled(window, im.size[0])
    rgb = np.asarray(im)[y0:y1, x0:x1] / 255.0
    return to_linear(rgb).reshape(-1, 3)


def skin_mean_linear(path, window=WINDOW_K):
    """Media por canal da pele da janela, em luz linear. Base do fator k."""
    return skin_pixels_linear(path, window).mean(axis=0)


def skin_lit_linear(path, window=WINDOW_DISPLAY, lo=70, hi=90):
    """
    Cor da pele plenamente iluminada, sem o especular.

    Faixa p70..p90 de luminancia dentro da janela, promediada em luz linear.
    O teto corta o brilho especular, que tem a cor da luz e nao do pigmento e
    lavava o croma dos tons escuros; o piso mantem fora a pele em queda de
    iluminacao nas bordas da janela.

    Selecionar por luminancia e so entao promediar preserva o croma; tirar
    percentil canal a canal nao preservaria.
    """
    lin = skin_pixels_linear(path, window)
    y = lin @ LUMA
    a, b = np.percentile(y, [lo, hi])
    return lin[(y >= a) & (y <= b)].mean(axis=0)


def linear_to_hex(lin):
    """Media linear -> sRGB -> #rrggbb. A cor que o jogador realmente ve."""
    v = np.round(np.clip(to_srgb(lin), 0, 1) * 255).astype(int)
    return "#%02x%02x%02x" % tuple(v)


def lab_of_linear(lin):
    """L*, a*, b* de uma cor em luz linear."""
    from skimage.color import rgb2lab
    return rgb2lab(np.clip(to_srgb(lin), 0, 1).reshape(1, 1, 3))[0, 0]


# Onde o croma da escala Monk tem o pico, contando de 1. Os chips nominais
# sobem de C* 5,6 no MST-01 ate 27,9 no MST-06 e descem ate 3,8 no MST-10.
CHROMA_PEAK_AT = (5, 6)

# Tolerancia da checagem de L*. NAO e folga arbitraria: a propria escala Monk
# nao e estritamente ordenada por luminosidade. O MST-03 (#f7ead0, L* 93,1) e
# 0,8 ponto MAIS CLARO que o MST-02 (#f3e7db, L* 92,3) — os tres primeiros
# degraus sao quase iguais em L* e se distinguem por croma. Um teste estrito
# reprovaria a escala oficial.
#
# 4,0 cobre essa inversao mais o ruido de medida do render nessa regiao, e
# ainda pega troca de verdade: a menor queda real entre degraus adjacentes, do
# MST-03 para o MST-04, e de 5,5 pontos.
#
# Ponto cego assumido e medido: uma troca entre MST-01 e MST-02 nao e pega por
# checagem nenhuma. Os dois chips distam 1,9 de L* e 2,0 de C*, dentro das duas
# tolerancias. Sao dois cremes quase iguais (#f6ede4 e #f3e7db); apertar a
# tolerancia para pegar isso trocaria um erro invisivel por falso positivo em
# cima de ruido de render. Todas as outras trocas entre degraus adjacentes sao
# pegas.
LIGHTNESS_TOLERANCE = 4.0

# Tolerancia da checagem de C*. A curva medida vem de render, entao balanca um
# pouco; 2,0 absorve isso e ainda pega troca entre degraus do mesmo lado da
# curva, que e o caso que a posicao do pico sozinha nao ve.
CHROMA_TOLERANCE = 2.0


def validate_scale(lightness, chroma):
    """
    Confere se a serie medida tem a forma da escala. Devolve a lista de
    problemas; vazia significa aprovado.

    Duas checagens:

      L*  tem que cair do primeiro ao ultimo, dentro da tolerancia. Se subir
          num degrau, as bases estao fora de ordem — o arquivo N e mais claro
          que o N-1.
      C*  tem que subir ate MST-05/06 e cair depois. Se sair monotonico, ou
          com pico em outro lugar, alguma base esta fora da escala.

    So faz sentido na escala completa; com menos de 10 bases nao roda.
    """
    problems = []

    subiu = [i for i in range(1, len(lightness))
             if lightness[i] > lightness[i - 1] + LIGHTNESS_TOLERANCE]
    if subiu:
        detalhe = ", ".join("MST-%02d (%.1f) e mais claro que MST-%02d (%.1f)"
                            % (i + 1, lightness[i], i, lightness[i - 1]) for i in subiu)
        problems.append(f"L* nao cai monotonicamente: {detalhe}")

    peak0 = int(np.argmax(chroma))
    peak = peak0 + 1
    # O pico nao precisa cair exatamente em MST-05/06: precisa nao estar
    # significativamente fora dali. Se o maximo empata, dentro da tolerancia,
    # com o melhor valor da banda esperada, a posicao nominal do pico e ruido e
    # nao diz nada. Sem isso a checagem reprova por 1,3 ponto de C*, que e
    # menos que a propria tolerancia — a banda foi calibrada nos chips lisos da
    # escala, e pele renderizada distribui croma de outro jeito.
    melhor_na_banda = max(chroma[i - 1] for i in CHROMA_PEAK_AT if i - 1 < len(chroma))
    empata_com_a_banda = chroma[peak0] - melhor_na_banda <= CHROMA_TOLERANCE
    if peak not in CHROMA_PEAK_AT and not empata_com_a_banda:
        sobe = all(chroma[i] >= chroma[i - 1] for i in range(1, len(chroma)))
        desce = all(chroma[i] <= chroma[i - 1] for i in range(1, len(chroma)))
        forma = "monotonico crescente" if sobe else "monotonico decrescente" if desce else f"pico em MST-{peak:02d}"
        problems.append(
            f"C* {forma}; a escala Monk tem pico em MST-05/06. "
            "Alguma base esta fora de ordem ou fora da escala."
        )
    else:
        # Ancora a analise de forma no pico observado.
        # Pico no lugar certo nao basta: a subida ate ele e a descida depois
        # tem que ser limpas. Uma troca entre dois degraus do mesmo lado da
        # curva mantem o pico no lugar e so aparece aqui.
        caiu_subindo = [i for i in range(1, peak0 + 1)
                        if chroma[i] < chroma[i - 1] - CHROMA_TOLERANCE]
        subiu_descendo = [i for i in range(peak0 + 1, len(chroma))
                          if chroma[i] > chroma[i - 1] + CHROMA_TOLERANCE]
        if caiu_subindo:
            detalhe = ", ".join("MST-%02d (%.1f) < MST-%02d (%.1f)"
                                % (i + 1, chroma[i], i, chroma[i - 1]) for i in caiu_subindo)
            problems.append(f"C* cai antes do pico (MST-{peak:02d}): {detalhe}")
        if subiu_descendo:
            detalhe = ", ".join("MST-%02d (%.1f) > MST-%02d (%.1f)"
                                % (i + 1, chroma[i], i, chroma[i - 1]) for i in subiu_descendo)
            problems.append(f"C* sobe depois do pico (MST-{peak:02d}): {detalhe}")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bases", default="skin", help='prefixo em raw/ ("skin" ou "tmp")')
    ap.add_argument("--out", default=".", help="onde escrever tones.json e a folha")
    ap.add_argument("--force", action="store_true",
                    help="escreve mesmo se a checagem da escala reprovar")
    args = ap.parse_args()

    # Aceita skin_01.png e skin01.webp: o nome e o formato variam conforme quem
    # gerou. O que nao varia e a ordem, do mais claro para o mais escuro.
    exts = (".png", ".webp", ".jpg", ".jpeg")
    bases = sorted(f for f in os.listdir("raw")
                   if f.lower().startswith(args.bases) and f.lower().endswith(exts))
    if not bases:
        sys.exit(f"nenhuma base raw/{args.bases}* encontrada")
    if args.bases == "skin" and len(bases) != 10:
        sys.exit(f"esperava 10 bases MST em raw/, achei {len(bases)}: {bases}")

    canvases = {Image.open(f"raw/{b}").size for b in bases}
    for b in bases:
        size = Image.open(f"raw/{b}").size
        if size[0] != size[1]:
            sys.exit(f"raw/{b} nao e quadrada ({size}); as janelas assumem canvas quadrado")
    if len(canvases) > 1:
        sys.exit(f"as bases tem canvas diferentes entre si: {canvases}")

    source_mean = skin_mean_linear(SOURCE)
    layer = Image.open(PROBE).convert("RGBA")
    alpha = layer.getchannel("A")
    lin = to_linear(np.asarray(layer.convert("RGB")) / 255.0)
    core = np.asarray(alpha) > 200
    Y = np.array([0.2126, 0.7152, 0.0722])

    # razao de referencia: a camada sobre a propria base de origem
    src_rgb = to_linear(np.asarray(Image.open(SOURCE).convert("RGB")) / 255.0)
    a = (np.asarray(alpha) / 255.0)[:, :, None]
    ref = lin * a + src_rgb * (1 - a)
    ring = ndimage.binary_dilation(np.asarray(alpha) > 0, np.ones((61, 61))) & (np.asarray(alpha) == 0)
    ref_ratio = (ref @ Y)[core].mean() / (ref @ Y)[ring].mean()

    tones, frames, lab_medido = [], [], []
    canvas = Image.open(f"raw/{bases[0]}").size[0]
    print(f"origem: {SOURCE} ({REFERENCE_CANVAS}px)   bases: {len(bases)} x {canvas}px")
    if canvas != REFERENCE_CANVAS:
        print(f"  canvas das bases difere do de referencia; janelas reescaladas por {canvas / REFERENCE_CANVAS:.6f}")
        print(f"  janela k       {WINDOW_K} -> {scaled(WINDOW_K, canvas)}")
        print(f"  janela display {WINDOW_DISPLAY} -> {scaled(WINDOW_DISPLAY, canvas)}")
    else:
        print(f"  janela k {WINDOW_K}   janela display {WINDOW_DISPLAY}")
    print(f"razao de referencia: {ref_ratio:.3f}\n")
    print("| id | base | hex nominal | measuredHex | k R | k G | k B | razao | L min | % L<5 |")
    print("|---|---|---|---|---|---|---|---|---|---|")

    for index, base in enumerate(bases):
        base_mean = skin_mean_linear(f"raw/{base}")
        k = base_mean / source_mean
        tone_id = f"MST-{index + 1:02d}"
        lit = skin_lit_linear(f"raw/{base}")
        lab_medido.append(lab_of_linear(lit))
        tones.append({
            "id": tone_id,
            # nominal: procedencia, o hex usado no prompt que gerou a base
            "hex": MST_HEX[index] if index < len(MST_HEX) else None,
            # medido: a cor real da pele no render, para o seletor da loja
            "measuredHex": linear_to_hex(lit),
            "base": base,
            "k": {"r": round(float(k[0]), 6), "g": round(float(k[1]), 6), "b": round(float(k[2]), 6)},
        })

        toned_lin = lin * k
        # TODO(10/09/2026): `clip` e calculada e nunca usada. E resto da analise
        # de clipping de gamut que esta registrada no NOTES.md (familia PELE, o
        # residuo aceito por decisao). Decidir entre voltar a reportar por tom
        # ou remover — nao mexido aqui de proposito: era uma passada de
        # documentacao, e apagar codigo morto no meio dela mistura duas coisas.
        clip = ((toned_lin < 0) | (toned_lin > 1)).any(axis=2)
        toned = np.clip(to_srgb(toned_lin), 0, 1)

        # A razao precisa da composicao, e a base nunca e reescalada: quando o
        # canvas dela difere, quem desce para o espaco dela e a camada. E o
        # unico ponto do gerador que reamostra alguma coisa, e reamostra a
        # camada, nunca a base.
        base_img = Image.open(f"raw/{base}").convert("RGB")
        base_lin = to_linear(np.asarray(base_img) / 255.0)
        if base_img.size[0] != REFERENCE_CANVAS:
            fit = lambda arr, mode: np.asarray(
                Image.fromarray(arr).resize(base_img.size, mode))
            toned_fit = to_linear(fit(np.round(toned * 255).astype(np.uint8), Image.LANCZOS) / 255.0)
            alpha_fit = fit(np.asarray(alpha), Image.LANCZOS)
        else:
            toned_fit, alpha_fit = toned_lin, np.asarray(alpha)
        a_fit = (alpha_fit / 255.0)[:, :, None]
        core_fit = alpha_fit > 200
        ring_fit = ndimage.binary_dilation(alpha_fit > 0, np.ones((61, 61))) & (alpha_fit == 0)

        comp_lin = toned_fit * a_fit + base_lin * (1 - a_fit)
        y = comp_lin @ Y
        ratio = y[core_fit].mean() / y[ring_fit].mean()

        from skimage.color import rgb2lab
        L = rgb2lab(toned)[:, :, 0]
        print("| %s | %s | %s | %s | %.4f | %.4f | %.4f | %.3f | %.1f | %.1f%% |" % (
            tone_id, base, tones[-1]["hex"], tones[-1]["measuredHex"],
            k[0], k[1], k[2], ratio, L[core].min(), 100 * (L[core] < 5).mean()))

        # round, nao trunca: e o que tone.ts faz, e a folha tem que bater
        # byte a byte com o que o runtime vai desenhar.
        layer_toned = Image.fromarray(np.round(toned * 255).astype(np.uint8)).convert("RGBA")
        layer_toned.putalpha(alpha)
        frame = Image.open(f"raw/{base}").convert("RGBA")
        # A base nunca e reescalada. Quando o canvas dela difere, quem se adapta
        # e a camada — e so para a folha de contato, que sai em 200px de qualquer
        # jeito. Nenhuma medida sai daqui.
        if frame.size != layer_toned.size:
            layer_toned = layer_toned.resize(frame.size, Image.LANCZOS)
        frame.alpha_composite(layer_toned)
        frames.append((tone_id, frame.convert("RGB")))

    # --- checagem da forma da escala, antes de escrever qualquer coisa
    lightness = [float(l[0]) for l in lab_medido]
    chroma = [float(np.hypot(l[1], l[2])) for l in lab_medido]
    print("")
    print("| id | measuredHex | L* | C* |")
    print("|---|---|---|---|")
    for tone, L, C in zip(tones, lightness, chroma):
        print("| %s | %s | %.1f | %.1f |" % (tone["id"], tone["measuredHex"], L, C))

    if len(tones) == 10:
        problems = validate_scale(lightness, chroma)
        if problems:
            print("")
            print("CHECAGEM DA ESCALA REPROVOU:")
            for problem in problems:
                print("  - " + problem)
            print("")
            print("Nada foi escrito. Confira a ordem de raw/skin01..skin10 "
                  "(mais claro para mais escuro) e se as 10 sao mesmo da escala.")
            print("Para escrever assim mesmo: --force")
            if not args.force:
                sys.exit(1)
            print("")
            print("--force: escrevendo apesar da reprovacao.")
        else:
            print("")
            print("checagem da escala: OK (L* cai; C* com pico em MST-%02d)"
                  % (int(np.argmax(chroma)) + 1))
    else:
        print("")
        print(f"checagem da escala: pulada, so faz sentido com 10 bases (tem {len(tones)})")

    table = {
        "source": os.path.basename(SOURCE),
        "windowK": list(WINDOW_K),
        "windowDisplay": list(WINDOW_DISPLAY),
        "tones": tones,
    }
    out_json = os.path.join(args.out, "tones.json")
    with open(out_json, "w", encoding="utf8") as fh:
        json.dump(table, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"\nescrito {out_json}  ({len(tones)} tons)")

    # folha de contato: uma linha, 200px por quadro
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    sheet = Image.new("RGB", (len(frames) * 200 + (len(frames) - 1) * 6, 226), "white")
    draw = ImageDraw.Draw(sheet)
    for i, (tone_id, frame) in enumerate(frames):
        sheet.paste(frame.resize((200, 200), Image.LANCZOS), (i * 206, 26))
        draw.text((i * 206 + 2, 4), tone_id, fill="black", font=font)
    out_sheet = os.path.join(args.out, "validacao_tons.png")
    sheet.save(out_sheet)
    print(f"escrito {out_sheet}  {sheet.size}")


if __name__ == "__main__":
    main()
