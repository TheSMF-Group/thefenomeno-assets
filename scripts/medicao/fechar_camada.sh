#!/usr/bin/env bash
# Fecha o par de referências de UMA camada de PELO:
#   1. pega os dois downloads mais novos do ChatGPT em ~/Downloads (o mais antigo dos dois = par 1);
#   2. copia para raw/_referencia/<camada>_tmp4_chatgpt_{1,2}.png com sidecar JSON;
#   3. roda medir_ET.py (resumo) e medir_w_de_r.py nos dois sentidos, normalizado.
# Uso: bash scripts/medicao/fechar_camada.sh <camada> "<descrição do pelo no prompt>" [pasta_de_saida] [arquivo_par1 arquivo_par2]
# Requer: os dois renders já baixados e NENHUM download novo entre eles e a chamada (confira o md5 impresso).
# O campo "prompt" do sidecar é o gabarito genérico; se o prompt real foi outro, corrija o JSON à mão.
# Nunca rodar em paralelo com um download do navegador: duas vezes pegou o arquivo errado (por isso os args explícitos).
set -euo pipefail
LAYER="$1"; DESC="$2"; OUTBASE="${3:-$PWD}"
P=/c/Users/guilherme.santiago/AppData/Local/Python/pythoncore-3.14-64/python.exe
A="$(cd "$(dirname "$0")/../.." && pwd)"
REF="$A/raw/_referencia"
if [ "${4:-}" != "" ] && [ "${5:-}" != "" ]; then
  F1="$4"; F2="$5"                      # arquivos explícitos: par 1 e par 2
else
  mapfile -t NEW < <(ls -t "$HOME"/Downloads/ChatGPT*.png | head -2)
  F1="${NEW[1]}"; F2="${NEW[0]}"
fi
[ -n "$F1" ] && [ -n "$F2" ] || { echo "faltam downloads"; exit 1; }
echo "par 1 = $(basename "$F1")"; echo "par 2 = $(basename "$F2")"
cp "$F1" "$REF/${LAYER}_tmp4_chatgpt_1.png"; cp "$F2" "$REF/${LAYER}_tmp4_chatgpt_2.png"
md5sum "$REF/${LAYER}_tmp4_chatgpt_1.png" "$REF/${LAYER}_tmp4_chatgpt_2.png" | cut -c1-32
PYTHONIOENCODING=utf-8 "$P" - "$LAYER" "$DESC" "$REF" <<'EOF'
import json, os, sys
from PIL import Image
layer, desc, ref = sys.argv[1:4]
for n in (1, 2):
    p = f"{ref}/{layer}_tmp4_chatgpt_{n}.png"
    im = Image.open(p)
    assert im.size == (1254, 1254), (p, im.size)
    meta = {"origem": f"ChatGPT web, {__import__('datetime').date.today().strftime('%d/%m/%Y')}, dirigido pelo Claude no Chrome do Santiago; par {n} de 2, mesmo prompt",
            "modelo": "gpt-image via ChatGPT",
            "entradas": ["raw/tmp_4.png (imagem 1, a editar)", f"raw/{layer}.png (imagem 2, o pelo a copiar)"],
            "prompt": f"Image 1 (imagem1_tmp_4.png) is a bald 3D mannequin head with dark brown skin, front view, white background. Image 2 (imagem2_{layer}.png) is the same mannequin with lighter skin wearing {desc}. Edit image 1 only: add exactly the same {desc.split(' (')[0]} from image 2 to the head in image 1 - same shape, same position, same coverage and density, same dark hair colour, same deep shadows between the hairs. Keep everything else in image 1 pixel-identical: same face, same dark skin tone, same lighting, same white background, same framing and size. Do not lighten the skin anywhere. Photorealistic render. Output one image only, the same size as image 1.",
            "papel": f"verdade de referencia (par {n} de 2) para E e T do {layer} em tom escuro; NAO e asset"}
    open(p.replace(".png", ".json"), "w", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    print(p, im.size, os.path.getsize(p))
EOF
R1="$REF/${LAYER}_tmp4_chatgpt_1.png"; R2="$REF/${LAYER}_tmp4_chatgpt_2.png"
D="$OUTBASE/ET_$LAYER"; mkdir -p "$D/w12" "$D/w21"
for R in "$R1" "$R2"; do
  echo "===== E,T $LAYER $(basename "$R")"
  (cd "$D" && PYTHONIOENCODING=utf-8 "$P" "$A/scripts/medicao/medir_ET.py" --layer "$LAYER" --ref "$R" 2>&1 | grep -v "Warning\|_methods\|rcount" | sed -n '4,4p;6,7p;/^  8 /p;/b = 8: medianas/,/núcleo/p')
done
echo "===== w(r) $LAYER: calibra 1, testa 2"
(cd "$D/w12" && PYTHONIOENCODING=utf-8 "$P" "$A/scripts/medicao/medir_w_de_r.py" --layer "$LAYER" --calib "$R1" --test "$R2" 2>&1 | grep -v Warning | sed -n '1,16p;/1254 sobre/,/identidade/p;/gate 512/,/MST-01/p')
echo "===== w(r) $LAYER: calibra 2, testa 1"
(cd "$D/w21" && PYTHONIOENCODING=utf-8 "$P" "$A/scripts/medicao/medir_w_de_r.py" --layer "$LAYER" --calib "$R2" --test "$R1" 2>&1 | grep -v Warning | sed -n '2,16p;/w(r) tabela/p')
