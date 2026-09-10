"""Gera prototipo.html: criacao de personagem, um arquivo so, sem servidor.

Nao e codigo de producao e nao persiste nada.

  PELE  (nose, mouth, ear, eye)  -> recebe o k do tom          (drawTonedLayer)
  PELO  (hair, beard, brow)      -> correcao de borda w = r    (drawHairLayer)

A cor do pelo continua sendo a nativa: w = r e correcao de borda, nao tint. O
tint de seis cores segue nao implementado. Ver "A cadeia de PELO" no NOTES.

Por que tudo vai embutido no HTML em base64: o prototipo roda de file://, e ali
uma imagem carregada do disco CONTAMINA o canvas — getImageData passa a lancar
SecurityError, e sem getImageData nao da para aplicar o k. Data URI nao
contamina. Sao 577,6 KB de build, ~770 KB em base64: cabe folgado num arquivo.

A matematica de tom NAO e reescrita aqui. tone.ts e compilado com tsc e o
JavaScript emitido vai embutido, para o prototipo nao poder divergir do runtime.

  python3 make_prototipo.py

Le build/ e tone.ts. Nao escreve nada em build/, layers/ ou raw/.
"""
import base64
import json
import os
import shutil
import subprocess
import tempfile

BUILD = "build"
OUT = "prototipo.html"

# Ordem de composicao. Definida no NOTES: a base primeiro, o cabelo por ultimo.
ORDER = ["ear", "eye", "brow", "nose", "mouth", "beard", "hair"]

# As duas familias. PELE segue o k do tom; PELO nao.
PELE = {"nose", "mouth", "ear", "eye"}
PELO = {"hair", "beard", "brow"}

# Onde "nenhum" e uma escolha valida. Todo rosto tem nariz, boca e olhos.
OPTIONAL = {"ear", "brow", "beard", "hair"}

LABEL = {"ear": "orelha", "eye": "olho", "brow": "sobrancelha", "nose": "nariz",
         "mouth": "boca", "beard": "barba", "hair": "cabelo"}

TSC = "/opt/homebrew/lib/node_modules/typescript/bin/tsc"


def data_uri(path):
    with open(path, "rb") as fh:
        return "data:image/webp;base64," + base64.b64encode(fh.read()).decode("ascii")


def compile_tone():
    """tone.ts -> JavaScript. O prototipo usa o compilado, nunca uma copia."""
    tsc = TSC if os.path.exists(TSC) else shutil.which("tsc")
    if not tsc:
        raise SystemExit("tsc nao encontrado; instale typescript ou ajuste TSC")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([tsc, "tone.ts", "--outDir", tmp, "--target", "ES2020",
                        "--module", "commonjs", "--strict"], check=True)
        with open(os.path.join(tmp, "tone.js"), encoding="utf8") as fh:
            return fh.read()


def main():
    with open(os.path.join(BUILD, "tones.json"), encoding="utf8") as fh:
        table = json.load(fh)

    bases = {}
    for tone in table["tones"]:
        name = os.path.splitext(tone["base"])[0] + ".webp"
        bases[tone["id"]] = data_uri(os.path.join(BUILD, "bases", name))

    slots = {slot: [] for slot in ORDER}
    layers = {}
    for f in sorted(os.listdir(os.path.join(BUILD, "layers"))):
        if not f.endswith(".webp"):
            continue
        name = os.path.splitext(f)[0]
        slot = name.split("_")[0]
        if slot not in slots:
            raise SystemExit(f"camada {name} nao cai em nenhum slot conhecido")
        slots[slot].append(name)
        layers[name] = data_uri(os.path.join(BUILD, "layers", f))

    assets = {
        "tones": table["tones"],
        # base de origem: o runtime calcula r = camada / source para a familia PELO
        "source": data_uri(os.path.join(BUILD, "source.webp")),
        "bases": bases,
        "layers": layers,
        "slots": slots,
        "order": ORDER,
        "pele": sorted(PELE),
        "pelo": sorted(PELO),
        "optional": sorted(OPTIONAL),
        "label": LABEL,
    }

    html = TEMPLATE.replace("__TONE_JS__", compile_tone())
    html = html.replace("__ASSETS__", json.dumps(assets, ensure_ascii=False))
    with open(OUT, "w", encoding="utf8") as fh:
        fh.write(html)

    kb = os.path.getsize(OUT) / 1024
    print(f"escrito {OUT}  ({kb:.0f} KB, {len(layers)} camadas + {len(bases)} bases embutidas)")
    print(f"abra com: open {OUT}")


TEMPLATE = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TheFenomeno — protótipo de criação de personagem</title>
<style>
  :root {
    --bg: #14141a; --panel: #1d1d26; --line: #2e2e3c;
    --ink: #e8e8f0; --dim: #9a9aae; --accent: #7c3aed;
    --pele: #3b82f6; --pelo: #f59e0b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font: 14px/1.5 ui-sans-serif, -apple-system, system-ui, sans-serif;
  }
  .wrap { display: flex; gap: 24px; padding: 24px; align-items: flex-start;
          max-width: 1180px; margin: 0 auto; flex-wrap: wrap; }
  .stage { position: sticky; top: 24px; }
  canvas { width: 512px; height: 512px; max-width: 100%; display: block;
           background: #fff; border-radius: 10px; border: 1px solid var(--line); }
  .stage-foot { display: flex; gap: 8px; margin-top: 12px; }
  .panel { flex: 1; min-width: 340px; }
  h1 { font-size: 15px; margin: 0 0 4px; letter-spacing: .01em; }
  .sub { color: var(--dim); font-size: 12px; margin: 0 0 18px; }
  .slot { border-top: 1px solid var(--line); padding: 12px 0; }
  .slot-head { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }
  .slot-name { font-weight: 600; font-size: 13px; }
  .fam { font-size: 10px; letter-spacing: .08em; text-transform: uppercase;
         padding: 1px 6px; border-radius: 999px; border: 1px solid currentColor; }
  .fam.pele { color: var(--pele); }
  .fam.pelo { color: var(--pelo); }
  .fam-note { color: var(--dim); font-size: 11px; margin-left: auto; }
  .row { display: flex; flex-wrap: wrap; gap: 6px; }
  button {
    font: inherit; font-size: 12px; color: var(--ink); cursor: pointer;
    background: var(--panel); border: 1px solid var(--line);
    padding: 5px 10px; border-radius: 7px;
  }
  button:hover { border-color: #4a4a5e; }
  button[aria-pressed="true"] { background: var(--accent); border-color: var(--accent); }
  button.none[aria-pressed="true"] { background: #3f3f52; border-color: #55556b; }
  .primary { background: var(--accent); border-color: var(--accent); padding: 8px 14px; font-size: 13px; }
  .ghost { background: transparent; padding: 8px 14px; font-size: 13px; }
  .tone-row button { width: 34px; height: 34px; padding: 0; border-radius: 8px; }
  .swatch { display: block; width: 100%; height: 100%; border-radius: 6px; }
  .readout { margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--line);
             color: var(--dim); font-size: 11px; font-family: ui-monospace, monospace;
             white-space: pre-wrap; }
  .err { color: #fca5a5; background: #2a1414; border: 1px solid #5b2020;
         padding: 12px; border-radius: 8px; margin: 24px; display: none; }
</style>
</head>
<body>
<div id="erro" class="err"></div>
<div class="wrap">
  <div class="stage">
    <canvas id="cv" width="512" height="512"></canvas>
    <div class="stage-foot">
      <button class="primary" id="aleatorio">Rosto aleatório</button>
      <button class="ghost" id="limpar">Só a base</button>
    </div>
    <div class="readout" id="readout"></div>
  </div>
  <div class="panel">
    <h1>Protótipo de criação de personagem</h1>
    <p class="sub">
      Composição em 512, direto de <code>build/</code>. O runtime não interpola:
      base e camada já chegam no mesmo canvas. PELO leva a correção de borda
      <code>w = r</code>; a cor do pelo continua nativa.
    </p>
    <div id="controles"></div>
  </div>
</div>

<script>
// ---- tone.ts compilado (tsc --target ES2020 --module commonjs --strict) ----
var exports = {};
var module = { exports: exports };
__TONE_JS__
</script>

<script>
(function () {
  "use strict";
  var A = __ASSETS__;

  var canvas = document.getElementById("cv");
  var ctx = canvas.getContext("2d", { willReadFrequently: true });
  var readout = document.getElementById("readout");

  function falhar(msg) {
    var box = document.getElementById("erro");
    box.textContent = msg;
    box.style.display = "block";
  }

  // Cache de LUT por tom, igual ao que tone.ts oferece via createToneCache.
  var lutCache = {};
  function lutDe(toneId) {
    if (!lutCache[toneId]) {
      var tone = A.tones.filter(function (t) { return t.id === toneId; })[0];
      lutCache[toneId] = exports.buildToneLut(tone.k);
    }
    return lutCache[toneId];
  }

  // ---- estado ----
  var estado = { tone: "MST-05" };
  A.order.forEach(function (slot) {
    estado[slot] = A.optional.indexOf(slot) === -1 ? A.slots[slot][0] : null;
  });

  // ---- imagens ----
  var imgs = {};
  var pendentes = 0;
  var falhou = 0;

  function carregar(chave, uri) {
    pendentes += 1;
    var im = new Image();
    im.onload = function () { imgs[chave] = im; pendentes -= 1; if (!pendentes) desenhar(); };
    im.onerror = function () { falhou += 1; pendentes -= 1; if (!pendentes) desenhar(); };
    im.src = uri;
  }

  carregar("source", A.source);
  Object.keys(A.bases).forEach(function (id) { carregar("base:" + id, A.bases[id]); });
  Object.keys(A.layers).forEach(function (n) { carregar("layer:" + n, A.layers[n]); });

  // ---- desenho ----
  function desenhar() {
    if (falhou) { falhar(falhou + " asset(s) não carregaram. Regere com make_prototipo.py."); return; }
    var base = imgs["base:" + estado.tone];
    if (!base) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(base, 0, 0);

    var lut = lutDe(estado.tone);
    var linhas = ["tom   " + estado.tone];

    A.order.forEach(function (slot) {
      var nome = estado[slot];
      if (!nome) { linhas.push(pad(A.label[slot]) + "—"); return; }
      var layer = imgs["layer:" + nome];
      if (!layer) return;

      // O runtime nunca interpola: se o build não entregou o mesmo canvas, o
      // protótipo tem que gritar em vez de esticar.
      if (layer.width !== base.width || layer.height !== base.height) {
        falhar("canvas divergente: " + nome + " " + layer.width + " vs base " + base.width);
        return;
      }

      if (A.pele.indexOf(slot) !== -1) {
        // FAMÍLIA PELE — recebe o k do tom, pela função compilada de tone.ts.
        exports.drawTonedLayer(ctx, layer, lut, 0, 0);
        linhas.push(pad(A.label[slot]) + nome + "   [PELE · k aplicado]");
      } else {
        // FAMÍLIA PELO — NÃO recebe o k. Leva a correção de borda w = r, que
        // faz a pele carregada pela máscara acompanhar o tom da base. A cor do
        // pelo continua nativa: isto é correção de borda, não tint.
        exports.drawHairLayer(ctx, layer, imgs.source, base, 0, 0);
        linhas.push(pad(A.label[slot]) + nome + "   [PELO · borda w = r]");
      }
    });

    readout.textContent = linhas.join("\n");
  }

  function pad(s) { return (s + "            ").slice(0, 12); }

  // ---- controles ----
  var controles = document.getElementById("controles");

  function secao(titulo, familia, nota) {
    var d = document.createElement("div");
    d.className = "slot";
    var h = document.createElement("div");
    h.className = "slot-head";
    var n = document.createElement("span");
    n.className = "slot-name";
    n.textContent = titulo;
    h.appendChild(n);
    if (familia) {
      var f = document.createElement("span");
      f.className = "fam " + familia.toLowerCase();
      f.textContent = familia;
      h.appendChild(f);
    }
    if (nota) {
      var s = document.createElement("span");
      s.className = "fam-note";
      s.textContent = nota;
      h.appendChild(s);
    }
    d.appendChild(h);
    var row = document.createElement("div");
    row.className = "row";
    d.appendChild(row);
    controles.appendChild(d);
    return row;
  }

  // tom de pele
  var rowTom = secao("Tom de pele", null, "escala Monk");
  rowTom.className = "row tone-row";
  A.tones.forEach(function (t) {
    var b = document.createElement("button");
    b.title = t.id + " · " + t.measuredHex;
    b.setAttribute("aria-pressed", String(t.id === estado.tone));
    var sw = document.createElement("span");
    sw.className = "swatch";
    // measuredHex: a pele como ela de fato renderiza. É o que o seletor mostra.
    sw.style.background = t.measuredHex;
    b.appendChild(sw);
    b.onclick = function () {
      estado.tone = t.id;
      Array.prototype.forEach.call(rowTom.children, function (o) {
        o.setAttribute("aria-pressed", String(o === b));
      });
      desenhar();
    };
    rowTom.appendChild(b);
  });

  // um slot por linha
  A.order.forEach(function (slot) {
    var familia = A.pele.indexOf(slot) !== -1 ? "PELE" : "PELO";
    var nota = familia === "PELE" ? "segue o k do tom" : "cor nativa + borda w = r";
    var row = secao(A.label[slot], familia, nota);
    var opcoes = A.slots[slot].slice();
    if (A.optional.indexOf(slot) !== -1) opcoes.unshift(null);

    opcoes.forEach(function (nome) {
      var b = document.createElement("button");
      b.textContent = nome === null ? "nenhum" : nome.slice(slot.length + 1);
      if (nome === null) b.className = "none";
      b.setAttribute("aria-pressed", String(estado[slot] === nome));
      b.onclick = function () {
        estado[slot] = nome;
        Array.prototype.forEach.call(row.children, function (o) {
          o.setAttribute("aria-pressed", String(o === b));
        });
        desenhar();
      };
      row.appendChild(b);
    });
    row.dataset.slot = slot;
  });

  function sincronizarBotoes() {
    Array.prototype.forEach.call(controles.querySelectorAll(".row"), function (row) {
      var slot = row.dataset.slot;
      if (!slot) return;
      var opcoes = A.slots[slot].slice();
      if (A.optional.indexOf(slot) !== -1) opcoes.unshift(null);
      Array.prototype.forEach.call(row.children, function (b, i) {
        b.setAttribute("aria-pressed", String(opcoes[i] === estado[slot]));
      });
    });
    Array.prototype.forEach.call(rowTom.children, function (b, i) {
      b.setAttribute("aria-pressed", String(A.tones[i].id === estado.tone));
    });
  }

  function escolher(lista) { return lista[Math.floor(Math.random() * lista.length)]; }

  document.getElementById("aleatorio").onclick = function () {
    estado.tone = escolher(A.tones).id;
    A.order.forEach(function (slot) {
      var opcoes = A.slots[slot].slice();
      // "nenhum" entra no sorteio dos slots opcionais, com o mesmo peso.
      if (A.optional.indexOf(slot) !== -1) opcoes.push(null);
      estado[slot] = escolher(opcoes);
    });
    sincronizarBotoes();
    desenhar();
  };

  document.getElementById("limpar").onclick = function () {
    A.order.forEach(function (slot) { estado[slot] = null; });
    sincronizarBotoes();
    desenhar();
  };
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
