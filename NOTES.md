# assets — cabeças de manequim, camadas de feição

## Estrutura de pastas

| pasta | conteúdo |
|---|---|
| `raw/` | **output de gerador.** Os 32 renders de feição, as 4 bases `tmp_*` e as 10 bases MST `skin01..skin10.webp`. Um arquivo por camada, mesmo nome da camada. |
| `raw/_rejected/` | renders substituídos, guardados para rastreio |
| `layers/` | as 32 camadas extraídas, RGBA com a máscara no alpha |
| `layers/_rejected/` | camadas substituídas, guardadas para rastreio |
| `build/` | **o que vai para o jogo.** 512, WebP. Gerado por `make_build.py` |
| raiz | `tones.json`, `tone.ts`, os geradores, `requirements.txt`, `NOTES.md` e saídas de teste (`gate_*.png`) |

`raw/` e `layers/` são o material de trabalho e não são consumidos pelo jogo.
Só `build/` é.

**`raw/` e `layers/` ficam no repositório, por decisão (10/09/2026.)** São 53,2
e 54,2 MB, e o repositório não é servido ao cliente — quem é servido é `build/`,
com 541,8 KiB. Não há outra cópia dos renders nem das camadas: `layers/` é a
única fonte do build e `raw/` é a única fonte de uma reextração. Guardar os dois
aqui é o backup. **Não é omissão, é escolha:** se um dia sair, sai para um
armazenamento com endereço registrado neste arquivo, nunca por limpeza.

**Regra: output de gerador vai para `raw/`, nunca para `layers/`.**
`layers/` só recebe arquivo produzido pela extração. Um render salvo dentro de
`layers/` sobrescreve silenciosamente a camada de mesmo nome — foi o que
aconteceu em 09/09/2026 com `beard_stubble`.

## Ambiente

`requirements.txt` fixa as versões com que o pipeline foi verificado
(numpy 2.5.3, scipy 1.18.1, scikit-image 0.26.0, pillow 12.2.0; Python 3.14).

```
pip3 install -r requirements.txt
```

Reproduzido em macOS em 10/09/2026: `make_tones.py` devolve `tones.json` **byte
a byte igual** ao commitado, e `make_build.py` devolve os 42 WebP **byte a byte
iguais**. A única saída que não reproduz byte a byte entre plataformas é a faixa
de **rótulos** das folhas de contato, que depende da fonte do sistema; os
quadros em si são idênticos.

**Reproduzido também em Windows em 11/09/2026**, com Python 3.14 de 64 bits e
Pillow 12.2.0: os 43 arquivos do build saem byte a byte iguais, `source.webp`
incluído. **O build é reprodutível entre as duas plataformas**, e a versão do
Pillow é o que importa, não o sistema.

Armadilha nessa máquina: o `python` do PATH é uma instalação **de 32 bits**, e
scipy não publica mais wheel de 32 bits para Windows, então `pip install scipy`
falha com "No matching distribution found". O interpretador que atende ao
`requirements.txt` é o `pythoncore-3.14-64`. Antes de concluir que o build não
reproduz, conferir com qual interpretador ele rodou.

## Base do diff

`raw/tmp_1.png`. A pele dos 32 renders de feição bate com ela (distância de 5 a
9 unidades RGB na testa, no topo do crânio e no pescoço). **Não** é o `#eadaba`
que constava da especificação inicial; aquele valor está a ~60 unidades da pele
real dos renders e foi descartado.

`tmp_1..tmp_4` são as 4 cabeças sem feição ordenadas por luminância, numeração
provisória. As 10 bases da escala Monk serão tratadas à parte.

## Receita da máscara (aprovada)

```
d      = |tmp_1 - feição| em escala de cinza
d      = mediana(d, disk(3))          # mata o salpicado de textura
m      = d > 16
m      = abertura(m, disk(4))         # remove o que sobrou
m      = fechamento(m, disk(6))       # tapa buracos internos
m      = componentes com área >= 0,5% da área da cabeça (3.464 px)
m      = blur gaussiano 1.5           # antialias, por último
camada = feição em RGBA com m no alpha
```

Área da cabeça em `tmp_1`: 692.869 px.

**Onde os blobs são contados:** na máscara binária, depois do corte de 0,5% e
antes do blur. Contar no alpha já borrado e reaplicar o corte dá número
diferente, porque o blur encolhe os componentes pequenos abaixo do limite.

## Ordem de composição e posicionamento

Fonte única: `COMPOSE_ORDER` e `LAYER_OFFSET` em `tone.ts`. `make_prototipo.py`
lê os dois do módulo compilado, com `node`, em vez de manter uma segunda lista —
uma cópia em Python divergiria em silêncio no dia em que a ordem mudasse.

```
base → ear → eye → brow → nose → beard → mouth → hair
```

### `beard` vem ANTES de `mouth` (10/09/2026)

Pelo facial cresce **ao redor** do lábio, não sobre ele. Na ordem antiga
(`mouth → beard`) a barba apagava a boca inteira:

| barba | % do miolo da boca coberto |
|---|---|
| `beard_longfull`, `beard_shortfull`, `beard_stubble` | **100%** nas quatro bocas |
| `beard_goatee` | 76–83% |
| `beard_mustache` | 28–54% |
| `beard_chinstrap` | 0% |

Com três das seis barbas cobrindo 100%, o slot de boca era **inerte**: trocar de
boca não mudava um pixel do composto. `chinstrap` em zero é o controle que valida
a medição — ela contorna a mandíbula sem passar pela região labial.

**A inversão troca um problema conhecido por um menor, não por nenhum.** Agora é
a boca que desenha por cima, e a máscara da boca carrega pele do `tmp_1` em volta
do lábio, o que abre uma orla clara dentro da barba.

O tamanho dessa orla foi **medido errado na primeira passada** e está corrigido
aqui. O limiar de então, `r > 0,5`, não separa pele de lábio — o `r` mediano do
miolo de uma boca é 0,59 a 0,67, então `r > 0,5` captura o lábio inteiro. Pele
carregada de verdade é `r > 0,85`:

| barba | apaga da barba | **orla real (`r > 0,85`)** | % do total |
|---|---|---|---|
| `longfull` / `shortfull` / `stubble` | 3.896–4.889 | **123–568 px** | 2,5–14,6% |
| `goatee` | 2.953–3.825 | **103–532 px** | 2,7–18,0% |
| `mustache` | 1.096–2.549 | **11–277 px** | 0,4–25,3% |
| `chinstrap` | 0 | 0 | — |

**O grosso do que a boca apaga da barba é o próprio lábio, e apagar ali é
correto** — o lábio fica na frente. Em `mouth_full` sobre `longfull`, dos 4.636
px apagados só 237 (5,1%) são pele; 3.320 (72%) são lábio e 1.079 (23%) são a
faixa de transição. A leitura anterior ("69–88% é pele") superestimava o defeito
em uma ordem de grandeza.

**Resíduo aceito por decisão (10/09/2026).** A orla de 123–568 px fica como está.
Contra os ~27.000 px que a boca perdia inteiros na ordem antiga, é troca boa, e a
tentativa de corrigi-la foi medida e descartada logo abaixo.

### Terceira hipótese de correção de borda: `r · canvas` como regra geral — descartada

Terceira contando as hipóteses de borda do projeto inteiro: corte em `r`, cor
sólida + alpha, e esta. A cadeia de PELO numera as suas quatro à parte, e o
`w = r` adotado lá continua valendo — o que morre aqui é **estendê-lo à família
PELE**.

A ideia: generalizar a correção de PELO para toda camada, usando como referência
**o canvas já composto** em vez da base de tom. Onde a máscara de `mouth_*`
carrega pele, o valor deveria ser `r ·` (o que já está embaixo), que ali é a
barba — e não `r · tmp_1`.

**A metade da borda funciona.** Erro nos pixels com `r > 0,85` sobre a barba,
contra o que a barba já tinha posto:

| boca | px | hoje | `w = r` | `w = 1` |
|---|---|---|---|---|
| full | 237 | 87,3 | 13,3 | **5,7** |
| medium | 568 | 77,9 | 11,2 | **7,7** |
| thin | 123 | 85,9 | 20,6 | **5,6** |
| wide | 225 | 79,7 | 13,7 | **6,7** |

De ~80 níveis para 6, e é dedutível: onde `r ≈ 1`, `r · canvas → canvas`.

**A metade do miolo quebra.** Teste: a cor do lábio não pode depender de haver
barba atrás. Diferença entre compor com e sem barba, no miolo `r < 0,7`:

| boca | px | hoje | `w = r` | `w = 1` |
|---|---|---|---|---|
| full | 3.320 | **0,1** | 23,7 | 68,1 |
| medium | 2.180 | **0,1** | 22,6 | 65,6 |
| thin | 2.328 | **0,0** | 30,5 | 74,6 |
| wide | 3.287 | **0,0** | 24,5 | 67,1 |

Hoje o lábio é invariante à barba, como tem que ser. Visualmente, com `w = r` a
barba atravessa o lábio como textura; com `w = 1` o lábio some dentro dela.

Três razões, e a primeira explica as outras:

1. **`r` não é a mesma grandeza nas duas famílias.** Em PELO é **cobertura** — o
   fio é mais fino que o pixel, e `r` alto significa que quase toda a luz de trás
   passa, então `r · canvas` é literalmente o que deveria estar ali. Em PELE é
   **razão de cor** — o pixel é opaco, e `r = 0,59` não diz que 59% da luz passa,
   diz que o lábio é 0,59× mais escuro que a pele que havia ali. Medianas do
   miolo: 0,59 (`mouth_full`), 0,67 (`mouth_thin`), 0,72 (`nose_medium`); só 3 a
   11% do miolo passa de `r > 0,85`.
2. **`w = r` em PELE desliga a transferência de tom.** O termo `(1 − w) · camada`
   devolve o pixel **nativo**, que carrega a pele do `tmp_1`. Em PELO isso é certo
   (a cor do pelo é nativa); em PELE significa que o lábio não recebe tom nenhum,
   e em MST-10 ficaria com a pele do `tmp_1`.
3. **A generalização é válida por pixel, não por família.** `r · canvas` acerta em
   cobertura parcial e erra em feição opaca. Não é a família que decide, é o
   pixel — a família PELE apenas tem muito mais pixels opacos. Separar os dois
   dentro de uma camada é o mesmo problema de classificação que a hipótese 1 de
   PELO já reprovou.

Observação de subproduto, não medida: sobre pele lisa, `r · base` é a
transferência de tom **exata por pixel**, enquanto `k` é razão de médias numa
janela. As duas concordam onde `k` foi calibrado e divergem fora.

### Offset de `ear_*`

`ear_normal` e `ear_protruding` sentavam ~8% da altura do rosto alto demais: topo
74–78 px acima da linha dos olhos, base 72–75 px acima da base do nariz, no canvas
de referência 1254. Os dois extremos erram quase o mesmo e a altura da orelha bate
com o vão olho→nariz dentro de 5 px em 262 — **translação rígida, não erro de
tamanho**, que é o que um offset conserta sem tocar no asset.

`LAYER_OFFSET` guarda `dy = 75/1254` (fração da aresta, não pixels, para valer em
qualquer resolução de build). `offsetFor()` multiplica pela aresta e **arredonda
para pixel inteiro** — offset fracionário em `drawImage` reamostra, e o runtime
não interpola. Em 512 dá 31 px.

Verificado depois do offset, em 512:

| orelha | topo vs linha dos olhos | base vs base do nariz |
|---|---|---|
| `ear_normal` | −0,1 px | +1,2 px |
| `ear_protruding` | +1,9 px | +0,2 px |

**Só camadas da família PELE podem receber offset.** `offsetFor()` lança se uma
camada de PELO aparecer na tabela: `applyHairEdgeToRgba` lê `source` e `base` na
posição do próprio pixel, então deslocar a camada exigiria deslocar as duas
leituras junto.

### `brow_thick` — asset a regerar, não corrigir por offset

`brow_thick` desce demais: o miolo dele vai até `y = 490`, praticamente no centro
do olho (493–499), e invade **14,1% a 20,4%** do miolo de cada `eye_*`. Como
`brow` desenha por cima de `eye`, isso come a pálpebra visível.

| | almond | downturned | hooded | narrow | round |
|---|---|---|---|---|---|
| `brow_medium` | 0,0% | 1,3% | 1,5% | 0,8% | 3,9% |
| **`brow_thick`** | **14,1%** | **16,9%** | **17,5%** | **17,3%** | **20,4%** |
| `brow_thin` | 0,0% | 0,7% | 1,0% | 0,4% | 3,1% |

**Offset não resolve, piora.** Descer a sobrancelha aumenta a invasão; subir a
afasta do olho, e a distância já está no piso (ver abaixo). O problema é a
extensão vertical do próprio render, então **`brow_thick` fica na fila de
regeração**. `brow_medium` e `brow_thin` funcionam e ficam como estão.

### A métrica de altura de rosto neste asset

A cabeça é **careca**: não existe linha do cabelo, então o *trichion* não é
mensurável e a altura de rosto anatômica (trichion→mento) não pode ser medida
aqui. Toda proporção neste arquivo usa **crânio→queixo**: `y = 36` (topo da
silhueta de `tmp_1`) a `y = 980` (onde `beard_chinstrap`, `beard_shortfull` e
`beard_stubble` terminam, o que marca a mandíbula), **944 px**.

**Esse denominador é maior que o anatômico e subestima as proporções em ~15%.**
Uma razão medida em 9% aqui corresponde a ~10,5% na régua anatômica. Ao comparar
qualquer medida deste arquivo com literatura de proporção facial, corrija para
cima antes de concluir que algo está fora de faixa.

Exemplo do efeito, na distância sobrancelha→olho (esperado 10–15%):

| sobrancelha | medido (crânio→queixo) | corrigido (~+15%) |
|---|---|---|
| `brow_medium` | 9,4–10,1% | 10,8–11,6% |
| `brow_thin` | 9,0–9,7% | 10,4–11,2% |
| `brow_thick` | 6,8–7,5% | 7,8–8,6% |

`medium` e `thin` entram na faixa depois da correção; `thick` continua fora, o
que é consistente com o diagnóstico de invasão acima.

## Regiões anatômicas por slot (x0, y0, x1, y1)

| slot | caixa |
|---|---|
| nose | (430, 340, 830, 780) |
| mouth | (370, 600, 880, 850) |
| eye | (270, 380, 615, 640) e (639, 380, 985, 640) |
| brow | (270, 280, 615, 500) e (639, 280, 985, 500) |
| ear | (140, 370, 380, 840) e (874, 370, 1114, 840) |
| hair | (80, 0, 1180, 1120) — inclui a faixa até o topo do canvas |
| beard | (270, **480**, 985, 1140) |

`beard` foi corrigido de y0=620 para y0=480 em 09/09/2026: as costeletas sobem
até y≈484 e a caixa antiga as deixava de fora, reportando cobertura menor do
que a real.

## Transferência de tom (hipótese C, aprovada)

As camadas em `layers/` carregam a pele de `raw/tmp_1.png`. Para compor sobre
uma base de outro tom, a camada é retonalizada por **multiplicação em luz
linear, com fator por canal**:

```
1. sRGB da camada -> linear:  c <= 0.04045 ? c/12.92 : ((c+0.055)/1.055)^2.4
2. k = media_linear(pele do tom destino) / media_linear(pele de tmp_1), por canal
3. multiplica os pixels lineares por k, canal a canal
4. volta para sRGB, alpha intacto
```

Janela de pele para as médias do `k`: **bochecha direita `(780, 520, 870, 660)`**
— adjacente ao nariz, mesma altura, lado iluminado. A mesma janela nas duas
imagens. Ela mede pele **média**, que é o que a transferência precisa
reproduzir. Não confundir com a janela do `measuredHex`, que é outra e serve a
outro fim.

O fator é **por canal, não global**: é o que carrega o croma junto. Contra
`tmp_4` deu R 0,1299, G 0,1515, B 0,1771.

**A transferência roda em runtime** (`tone.ts`), a partir das 32 camadas. As
camadas pré-tingidas por tom **não são geradas**: seriam 32 × 10 = 320 arquivos
e ~542 MB de PNG, contra 54,2 MB das 32 atuais.

### Critério de aceitação: razão em luz linear, não delta em sRGB

A aceitação é a **razão de luminância entre nariz e pele, medida em luz linear,
no miolo da camada (alpha > 200)**, comparada com a mesma razão na composição
de origem sobre `tmp_1`.

O alvo antigo, "delta de luminância em sRGB ≈ −37", **não se aplica a
transferência multiplicativa** e foi aposentado. Motivo: sRGB é codificado com
gama. Uma multiplicação em luz linear preserva a razão, mas a diferença
absoluta em sRGB encolhe conforme o nível cai. O mesmo sombreamento que vale
−37 sobre pele clara vale −9 sobre pele escura, sem que nada tenha mudado
fisicamente. Medir o delta em sRGB entre dois níveis de brilho diferentes
compara coisas incomparáveis.

O −37 era o critério certo enquanto as hipóteses testadas eram **aditivas**
(Reinhard em Lab), porque ali a diferença é que se pretendia preservar. Elas
foram descartadas: nenhuma translação uniforme cabe: o nariz precisa descer 58
níveis de L abaixo da média da pele e a base escura só tem 29 até o preto, o
que joga narina para L negativo (30,8% do miolo abaixo de L=5 com sigma 1,43;
16,4% com sigma travado em 1,0).

Medições de C contra `tmp_4`:

| | A sobre tmp_1 (origem) | C sobre tmp_4 |
|---|---|---|
| razão de luminância linear nariz/pele | 0,626 | 0,744 |
| L mínimo | 13,2 | 2,0 |
| % do miolo com L < 5 | 0,0 | 0,7 |
| clipping de gamut | 0,0% | 0,0% |
| delta em sRGB (aposentado) | −37 | −9 |

A razão sobe de 0,626 para 0,744 porque a composição mistura a camada com a
base pelo alpha, e nas bordas suaves entra pele do destino, que puxa a média do
nariz para cima. O miolo é multiplicado exatamente por k.

## Procedência das 10 bases MST

As bases em `raw/skin01.webp` … `skin10.webp` **não são os renders originais**.
Vieram reduzidas de 1254 para **1092×1092** e reencodadas em **WebP com
perdas**, entre 23 e 68 KB cada. `k` e `measuredHex` saem delas, não dos
originais.

**As bases não são reescaladas nem convertidas.** Ampliar de volta para 1254
não recupera informação e inventa pixel. Quem se adapta são as **janelas**, que
descem para o espaço 1092 pelo fator 0,870813 (`scaled()` em `make_tones.py`):

| janela | referência 1254 | aplicada em 1092 |
|---|---|---|
| k | (780, 520, 870, 660) | (679, 453, 758, 575) |
| display | (585, 290, 660, 360) | (509, 253, 575, 313) |

Medir onde a informação está, em vez de esticar a informação até a régua.

### Geometria validada

Antes de aceitar, a moldura foi conferida contra `tmp_1`, em fração de canvas
para o tamanho não interferir:

- **IoU da silhueta ≥ 0,989** (skin01 0,9923, skin04 0,9892, skin10 0,9900);
- **landmarks dentro de 1,1%**: largura da bbox, largura máxima do crânio,
  têmporas a 25% e 35%, mandíbula a 80% e 90%, largura do pescoço;
- desvio médio de largura por faixa entre 0,38% e 1,22%, sem concentração em
  região nenhuma.

É a mesma cabeça, mesma moldura, só reescalada. Os desvios enormes que aparecem
no bruto (até 252%) estão todos entre `y` 35 e 41, a calota do crânio, onde a
largura é de poucas dezenas de pixels e a borda antisserrilhada desloca alguns
deles. Fora da calota o máximo cai para 8–12%, nas bordas.

Confirmado também que as bases são **sem feição**, como `tmp_1`: o gradiente
local dentro do rosto é 0,87 no skin01 e 1,26 no skin04, contra 3,53 no
`tmp_1`.

### Único ponto que reamostra

A folha de contato e a coluna "razão" precisam compor camada e base. Como a
base nunca é tocada, quem desce para 1092 é a **camada**. Nenhuma medida escrita
no `tones.json` vem daí: `k` e `measuredHex` saem direto do pixel da base.

## Os dois hexes de cada tom

`tones.json` traz dois campos de cor por tom, e eles servem a coisas
diferentes:

| campo | o que é | onde usar |
|---|---|---|
| `hex` | o valor nominal da escala Monk | procedência, rastreio, documentação |
| `measuredHex` | a pele do render **plenamente iluminada** | **o seletor da loja** |

O seletor mostra `measuredHex` porque é a cor que o jogador de fato vê na
cabeça. O nominal é um chip liso de referência e não corresponde a nenhum pixel
do asset.

### Como o measuredHex é medido

Janela **`(585, 290, 660, 360)`**: testa central e estreita, a parte mais
frontal ao observador. Menor curvatura, sombreamento mínimo — desvio de
luminância 0,043 contra 0,073 da bochecha.

Estatística: **média dos pixels na faixa p70–p90 de luminância** da janela,
promediados em luz linear. Selecionar por luminância e só então promediar
preserva o croma; tirar percentil canal a canal não preservaria.

**Esta faixa é de pele e não transfere para pelo.** A janela aqui é quase plana;
cabelo é massa 3D e na mesma faixa a medida cai na sombra. Para cabelo a faixa é
p90–p98 — ver "A faixa de cabelo é p90–p98", na seção de PELO.

Por que uma faixa e não a média da janela inteira: mesmo na testa, a média fica
~18 pontos de L\* abaixo do nominal, porque a janela ainda carrega queda de
iluminação nas bordas. O piso em p70 deixa isso de fora.

Por que um teto em p90 e não o decil superior aberto: acima de p90 entra
**reflexo especular**, que tem a cor da luz e não do pigmento, e lava o croma
dos tons escuros. Medido nas quatro `tmp_*`:

| base | média da janela | p90 pra cima | **p70–p90** |
|---|---|---|---|
| tmp_1 | #eaae96 · C\* 28,0 | #f4bca5 · C\* 25,9 | **#eeb59d · C\* 26,9** |
| tmp_2 | #90604d · C\* 25,3 | #a8806e · C\* 20,5 | **#9a6d59 · C\* 24,0** |
| tmp_3 | #765549 · C\* 17,5 | #8f7367 · C\* 14,3 | **#806053 · C\* 16,7** |
| tmp_4 | #67504a · C\* 11,0 | #816f68 · C\* 8,7 | **#715c55 · C\* 10,3** |

A faixa recupera quase todo o croma que o decil aberto perdia, e mantém o L\*
bem acima da média: 78,2 / 50,0 / 43,7 / 40,9 contra 76,0 / 45,5 / 39,4 / 36,3.

### O croma continua caindo, e isso é do render

O croma **não** para de cair com a faixa: 26,9 → 24,0 → 16,7 → 10,3. Mas a
queda aparece igual na média da janela (28,0 → 25,3 → 17,5 → 11,0), que não
tem seleção nenhuma por brilho. Ou seja, **é propriedade das imagens, não
artefato do percentil.** O que o percentil causava era a perda extra, e essa
foi corrigida.

Vale notar que a própria escala Monk não tem croma monotônico: sobe de C\* 5,6
no MST-01 até 27,9 no MST-06 e desce até 3,8 no MST-10. As quatro `tmp_*` são
todas do lado escuro dessa curva, onde cair é o esperado.

#### Fechado com as dez bases reais (10/09/2026)

A questão ficou em aberto enquanto só havia as quatro `tmp_*`. Com as dez bases
medidas, **a curva tem a forma da escala**: sobe limpo até o pico e desce limpo
depois, sem nenhuma inversão. O medo de que o croma caísse monotonicamente era
artefato da amostra — as quatro `tmp_*` só cobriam o lado descendente.

| id | nominal | L\* nom | C\* nom | measuredHex | L\* med | C\* med |
|---|---|---|---|---|---|---|
| MST-01 | `#f6ede4` | 94,2 | 5,6 | `#f0cbc1` | 84,5 | 15,1 |
| MST-02 | `#f3e7db` | 92,3 | 7,6 | `#efc2b1` | 81,9 | 19,9 |
| MST-03 | `#f7ead0` | 93,1 | 14,2 | `#f1cdae` | 84,7 | 21,7 |
| MST-04 | `#eadaba` | 87,6 | 17,8 | `#efbc9a` | 80,0 | 27,9 |
| MST-05 | `#d7bd96` | 77,9 | 23,4 | `#d9a984` | 72,8 | 28,8 |
| MST-06 | `#a07e56` | 55,1 | **27,9** | `#cd9775` | 66,8 | 30,4 |
| MST-07 | `#825c43` | 42,5 | 24,0 | `#b57a5d` | 56,6 | **32,0** |
| MST-08 | `#604134` | 30,7 | 17,7 | `#9b6b57` | 49,7 | 25,2 |
| MST-09 | `#3a312a` | 21,1 | 6,5 | `#805f51` | 43,3 | 17,5 |
| MST-10 | `#292420` | 14,6 | 3,8 | `#715a54` | 40,4 | 11,0 |

Três coisas que a tabela mostra, e que valem como registro:

1. **O pico existe e está no meio.** Nominal em MST-06 (27,9), medido em MST-07
   (32,0). O medido cai **um degrau depois** do nominal, por 1,6 ponto — menos
   que a tolerância de 2,0. É exatamente o caso que `validate_scale()` já
   absorve por empate, e a razão de ele existir: chip liso e pele renderizada
   distribuem croma de jeitos diferentes.
2. **O croma medido é sistematicamente maior que o nominal**, em todos os dez
   degraus. É a mesma distância estrutural já registrada acima — chip liso
   contra superfície iluminada — e não se fecha com janela nenhuma.
3. **A faixa de L\* medida é comprimida**: 84,5 → 40,4, contra 94,2 → 14,6 do
   nominal. `measuredHex` é pele **plenamente iluminada**, não a cor média do
   degrau; o piso em p70 é justamente o que impede a ponta escura de descer.

A pendência está encerrada. O que continua valendo é o ponto cego
MST-01 ↔ MST-02 da checagem, que é de outra natureza e segue assumido.

### Checagem da forma da escala, antes de escrever

`make_tones.py` mede L\* e C\* de cada `measuredHex` e confere a forma da série
**antes de escrever o `tones.json`**. Se reprovar, não escreve nada e imprime o
diagnóstico. `--force` escreve mesmo assim.

Duas checagens, ambas só rodam com as 10 bases:

| checagem | o que exige | o que pega |
|---|---|---|
| L\* | cai do primeiro ao último, tolerância 4,0 | base fora de ordem: o arquivo N é mais claro que o N−1 |
| C\* | sobe até MST-05/06 e cai depois, tolerância 2,0 | base fora da escala, e troca entre degraus do mesmo lado da curva |

A checagem de C\* não olha só onde está o pico. Ela exige subida limpa até ele e
descida limpa depois, porque uma troca entre dois degraus do mesmo lado mantém
o pico no lugar e só aparece assim.

**A posição do pico é comparada com tolerância, não com igualdade.** Se o
máximo de C\* empata, dentro de 2,0, com o melhor valor dentro de MST-05/06, a
posição nominal do pico é ruído e não reprova. Sem isso a série medida reprovava
por 1,3 ponto de croma entre MST-06 (30,3) e MST-07 (31,6) — menos que a própria
tolerância. A banda foi calibrada nos chips lisos da escala; pele renderizada
distribui croma de outro jeito e empurra o pico um degrau adiante.

**As tolerâncias não são folga arbitrária.** A escala Monk **não** é
estritamente ordenada por luminosidade: o MST-03 (`#f7ead0`, L\* 93,1) é 0,8
ponto mais claro que o MST-02 (`#f3e7db`, L\* 92,3). Os três primeiros degraus
são quase iguais em L\* e se distinguem por croma. Um teste estrito reprovaria a
escala oficial — foi o que aconteceu na primeira versão.

Verificado com a escala nominal e com trocas sintéticas:

- a escala nominal passa;
- sob ruído gaussiano de σ = 1,0 em L\* e C\*, 2,7% de falso positivo em 300 sorteios;
- toda troca entre degraus adjacentes é pega, **menos MST-01 ↔ MST-02**.

Esse ponto cego é assumido. Os dois chips distam 1,9 de L\* e 2,0 de C\*, dentro
das duas tolerâncias. São dois cremes quase idênticos; apertar para pegá-los
trocaria um erro invisível por falso positivo em cima de ruído de render.

### O que nenhuma janela conserta

A distância que sobra entre nominal e medido é de **croma, não de brilho**. Os
chips nominais são muito menos saturados que qualquer pele renderizada: em
`tmp_1`, o nominal MST-01 tem C\* 5,6 e a testa iluminada tem 26,9. É
estrutural, chip liso contra superfície iluminada, e nenhuma escolha de janela
ou de estatística fecha isso.

### Procedência dos hexes nominais

A fonte oficial **não foi lida**. `skintone.google/the-scale` é uma SPA: o
corpo não renderiza sem executar JS com o banner de consentimento aceito, e os
valores não estão no HTML servido (3.832 bytes de casca), nem no bundle
`assets/index.*.js`, nem no CSS. O snapshot do Internet Archive guarda a mesma
casca. Tentado em 09/09/2026.

Usada a lista da **Wikipédia**, de `#f6ede4` a `#292420`, que cita a
documentação do Google.

O que fecha a questão não é a Wikipédia, é a origem: **esses dez hexes são os
que foram usados nos prompts que geraram as bases**, então o rótulo corresponde
ao asset por construção, independente de a lista publicada estar certa. Se a
escala oficial divergir, quem estará errado é o nome da escala, não o
pareamento entre rótulo e arquivo.

## O build (512, WebP)

`make_build.py` produz `build/`, que é o único diretório que o jogo consome.

```
build/
  bases/    skin01..skin10.webp    512x512, WebP qualidade 88
  layers/   as 32 camadas .webp    512x512, WebP q88 + alpha_quality 100 + exact
  tones.json                        cópia, inalterada
  validacao_tons.png                gerada a partir dos webp de 512
```

**Reescala uma vez, no build. O runtime nunca interpola.** Base e camada chegam
no mesmo canvas de 512 e o runtime só compõe. Bases descem de 1092, camadas de
1254, ambas por Lanczos.

### As duas folhas de contato, e qual é qual

Existem duas, com o mesmo nome de arquivo e propósitos diferentes. Confundir as
duas é fácil e já custou uma investigação:

| arquivo | quem gera | do que compõe | o que valida |
|---|---|---|---|
| `validacao_tons.png` na **raiz** | `make_tones.py` | base 1092 + camada 1254 **reduzida** para 1092 | a **medição**: que o `k` medido produz a pele certa no material de trabalho |
| `build/validacao_tons.png` | `make_build.py` | base 512 + camada 512, **sem reamostrar nada** | a **entrega**: o que o jogo vai compor, depois do Lanczos e do WebP |

A do build é a que importa para aceitar uma release: ela é a única que exercita
o caminho real do runtime, em que base e camada já chegam no mesmo canvas.
`contact_sheet()` aborta se o build entregar canvas diferentes entre base e
camada.

Diferença medida entre as duas, nos quadros: 0,49 nível em média, mediana 0,
p99 3, máximo 13. É a reamostragem da camada que só existe na folha da raiz.

**Cuidado:** `make_tones.py --out build` sobrescreve `build/validacao_tons.png`
com a folha do material de trabalho. Use `--out` para um diretório temporário
quando quiser só conferir a medição.

Até 10/09/2026 a folha do build era produzida por um script que **não estava no
repositório** — o mesmo que deixou `__pycache__/make_tones.cpython-314.pyc` para
trás. `contact_sheet()` em `make_build.py` reimplementa esse passo, e reproduz a
folha commitada **pixel a pixel** nos 10 quadros (só os rótulos mudam, por causa
da fonte do sistema).

`tones.json` não muda com a resolução: o `k` é razão de médias e é invariante a
escala.

### Tamanhos

| | arquivos | total |
|---|---|---|
| bases | 10 | 144,2 KiB |
| camadas | 32 | 379,9 KiB |
| source | 1 | 17,6 KiB |
| **build** | 43 | **541,8 KiB** |

Medido em 11/09/2026, com `FLOOD_RADIUS = 4`. Com o raio 16 anterior as camadas
pesavam 433,3 KiB e o build 595,2 KiB, então a troca de raio devolveu **53,4 KiB,
9,0% do bundle**. O valor das camadas bateu na casa decimal com o previsto pela
varredura de raios, que estimava 379,9 KB.

Maiores camadas: `hair_midcurly` e `hair_braids` em torno de 31 KB,
`beard_longfull` 23 KB. Menores: `mouth_thin` 3,9 KB, `brow_thin` 4,3 KB.

**A folha de contato oscila entre máquinas e isso não é regressão.** A faixa de
rótulos é desenhada com a fonte do sistema, Arial Bold no macOS contra
`arialbd.ttf` no Windows, então todo rebuild em máquina diferente reescreve as
linhas 8 a 20 do PNG. Os dez quadros são reproduzíveis; só a legenda não é.
Ignorar essa parte do diff.

### O alpha não é comprimido com perda

`alpha_quality=100` faz o canal alfa passar sem perda: verificado, as 32
camadas voltam do WebP com o alfa **byte a byte idêntico** ao que o Lanczos
produziu. A borda da máscara é o que custou mais iteração no projeto e não vai
embora num parâmetro de encoder.

O RGB perde 2,89 níveis em média no miolo, o esperado da qualidade 88.

### Flood do RGB sob os pixels transparentes

**O `resize()` do Pillow zera o RGB onde o alpha é 0.** Ele premultiplica,
reescala e divide de volta; onde o alpha é zero a divisão não existe e sobra
preto. No PNG de 1254 esses pixels carregavam pele; no 512 viram preto puro.

Isso é inofensivo na composição — peso zero — mas vira **halo escuro** no dia
em que alguém gerar mipmap ou escalar a textura. `flood_rgb()` preenche o RGB
desses pixels com a cor do vizinho opaco mais próximo. O alfa não é tocado, e o
RGB de quem tem alpha > 0 também não.

**Fonte do flood: alpha ≥ 8.** Abaixo disso o un-premultiply divide por um alfa
minúsculo e o RGB é ruído: na faixa 1–3 a média dá (176, 43, 35) com extremos em
0 e 255, contra (218, 152, 127) estável de 8 para cima.

**Raio: 4 px**, desde 11/09/2026. Antes eram 16. Preto chapado comprime para
quase nada e área com cor não, então o raio custa caro em bytes, e o flood sem
limite custa quase o triplo.

#### A varredura de raios 2, 4, 8 e 16 (recuperada em 11/09/2026)

Esta medição foi dada como perdida: ela não estava em commit nenhum, e a sessão
que procurou por ela concluiu que teria de ser refeita do zero. Estava inteira
na árvore de trabalho não commitada da máquina Windows, junto com a mudança de
código que ela motivava. **É o terceiro caso do mesmo padrão na mesma semana, e
o único em que o dado voltou.** Ver a nota de processo no fim deste arquivo.

O critério que ela introduz é de mipmap, e não estava registrado antes: **cada
nível é gerado do anterior, então a exigência de pixels válidos dobra a cada
nível.** 1 px protege o mip 1 a 256, 2 px o mip 2 a 128, 4 px o mip 3 a 64, 8 px
o mip 4 a 32, 16 px o mip 5 a 16.

Medido sobre as 32 camadas, com o build inteiro em 491,8 KB sem flood:

| raio | camadas | build total | acréscimo | cobre até |
|---|---|---|---|---|
| sem flood | 347,6 KB | 491,8 KB | — | — |
| 2 | 349,4 KB | 493,6 KB | +1% | mip 2, cabeça a 128 px |
| **4** | **379,9 KB** | **524,1 KB** | **+9%** | **mip 3, cabeça a 64 px** |
| 8 | 408,4 KB | 552,6 KB | +17% | mip 4, cabeça a 32 px |
| 16 | 433,3 KB | 577,5 KB | +25% | mip 5, cabeça a 16 px |
| sem limite | 590,1 KB | 734,3 KB | +70% | tudo |

O flood total está descartado: 242 KB, metade do bundle, para proteger tamanhos
de tela que não existem.

**A decisão, aplicada em 11/09/2026.** Raio 4 protege até a cabeça desenhada a
64 px, que cobre o uso plausível, porque avatar de seletor fica entre 64 e 128.
Custa +9% contra os +25% do raio 16. A escolha original de 16 foi feita sem esta
tabela. **Abaixo de 64 px o raio 4 não protege; se o jogo passar a desenhar
cabeça menor que isso, subir para 8.**

### O flood muda o composto, e o motivo não é a composição

Esperava-se composto idêntico, já que pixel transparente tem peso zero. **Não
é.** Diferença média de 0,05 nível e máxima de 25, maior nos tons claros.

A causa é o **codec**, não a composição. WebP com perdas trabalha em blocos:
mudar o RGB dos pixels transparentes muda o conteúdo do bloco e, com ele, a
reconstrução dos pixels **opacos** do mesmo bloco. Peso zero na composição não
é peso zero na compressão.

A mudança é uma **melhora marginal, e em todos os 10 tons**, não um empate com
algum tom pior. Medida contra a camada de 512 sem compressão nenhuma, no MST-01
que é o pior caso e no MST-10:

| versão | miolo MST-01 | rampa MST-01 | miolo MST-10 | rampa MST-10 |
|---|---|---|---|---|
| sem flood | 2,758 | 1,731 | 1,090 | 0,683 |
| flood r4 | **2,690** | **1,710** | **1,064** | **0,673** |

Vinte medições, vinte vezes o flood igual ou melhor. A melhora é maior nos tons
claros, onde o `k` é maior e o contraste contra o preto era mais violento. Esta
tabela também vem da árvore não commitada, e é a mesma varredura recuperada: ela
substitui a medição anterior, que era de um tom só e do raio 16.

Sem o flood existe uma parede de preto contra pele dentro do bloco; o codec
gasta bits nessa aresta e produz ringing. Com o flood a aresta some.

## Duas famílias de camada

As 32 camadas se dividem em duas, e a divisão é sobre o que a cor delas
**é**, não sobre onde ficam no rosto:

| família | slots | tratamento |
|---|---|---|
| **PELE** | `nose_*`, `mouth_*`, `ear_*`, `eye_*` | segue o `k` do tom. É pele e tem que acompanhar a base. |
| **PELO** | `hair_*`, `beard_*`, `brow_*` | **não segue o `k`.** Tem tint próprio, seis cores, independente do tom de pele. |

Cor de cabelo não é função de tom de pele. Aplicar o `k` da pele em `hair_*` não
é só impreciso, é a origem do clipping pesado: 43 das 320 combinações passavam de
0,1%, chegando a 2,58% em `hair_midcurly` × MST-01, com perda média de 15,4
níveis de sRGB e máxima de 70. Isso desaparece quando PELO sai do `k`.

**O tint de PELO não está implementado.** Só a separação está decidida.

### A família PELO não é homogênea (10/09/2026)

`brow_*` não se comporta como `hair_*` e `beard_*`, e tratar os três com o mesmo
modelo é errado independentemente de qual modelo for escolhido.

Medindo `r = camada / tmp_1` em luz linear, no miolo (`alpha > 200`) e **dentro
da silhueta da cabeça**:

| camada | r < 0,15 (pelo opaco) | 0,15–0,85 | pico em zero ÷ ombro |
|---|---|---|---|
| `hair_midcurly` | 70,6% | 27,9% | 18,8 |
| `hair_braids` | 41,4% | 56,3% | 7,0 |
| `beard_longfull` | 68,6% | 31,0% | 28,6 |
| **`brow_thick`** | **9,6%** | **87,5%** | **0,1** |

(canal R; G e B na mesma ordem de grandeza)

`hair` e `beard` têm um núcleo opaco de verdade — dois terços do miolo abaixo de
r = 0,15. **A sobrancelha quase não tem:** 9,6%, e o modo em r≈0 é menor que o
ombro, não 7 a 29 vezes maior. Nesses renders sobrancelha é quase toda
semitransparente, mais parecida com sombra na pele do que com pelo opaco.

Consequência prática: qualquer tratamento calibrado em `hair_*` vai errar em
`brow_*` por construção. Se PELO ganhar um modelo, `brow` precisa ser verificado
à parte antes de herdar os parâmetros.

**O recorte pela silhueta não é detalhe.** Sem ele o número engana: 46% do miolo
de `hair_midcurly` e 63% do de `hair_braids` caem **fora** da cabeça, sobre o
fundo branco de `tmp_1`, onde `r` é a cor do cabelo dividida por 1,0 e não mede
sombra nenhuma. Incluir esses pixels infla o modo em zero e faz a distribuição
parecer mais separada do que é.

### A cadeia de PELO: quatro hipóteses, uma adotada (10/09/2026)

O problema: a máscara morfológica carrega pele do `tmp_1` junto com o pelo. Sobre
uma base de outro tom essa pele não acompanha, e desenha um **filete claro na
linha do cabelo** — largo e contínuo em MST-08 a 10, invisível em MST-04, que é
o tom nativo do `tmp_1`.

| # | hipótese | veredito |
|---|---|---|
| 1 | separar por um corte em `r` (bimodalidade) | **morta** |
| 2 | cor sólida + alpha | **morta** |
| 3 | corrigir só onde `r > 0,5` (limiar duro) | **morta** |
| 4 | **`w = r` contínuo** | **ADOTADA** |

`r = camada / tmp_1` em luz linear, por canal. É o fator de sombra medido contra
a base de origem, a mesma grandeza que sustenta a hipótese C.

#### 1. Corte em `r` — morta: `r` é contínuo

Exigiria distribuição bimodal com vale limpo. **Não é.** No canal B não há mínimo
local nenhum em `hair_midcurly`, `hair_braids` nem `beard_longfull` — a densidade
só decresce. Onde há mínimo, a profundidade contra o ombro é 0,03 a 0,38, e a
posição varia de 0,43 a 0,65 entre camadas e de 0,50 a 0,63 entre canais dentro
do próprio `brow_thick`. A massa na faixa ambígua 0,15–0,85 é de 28% a 88%.

O motivo é físico: **fio de cabelo é mais fino que pixel.** Quase todo pixel de
borda de mecha é cobertura parcial, e cobertura varia continuamente de 0 a 1.

#### 2. Cor sólida + alpha — morta: o pelo tem sombreamento próprio

Modelo `obs = a·C + (1−a)·tmp_1`, com `C` constante por camada e `a` por pixel,
resolvido por mínimos quadrados em luz linear.

| camada | `C` ajustado | erro médio | p99 | acima de 2,89 |
|---|---|---|---|---|
| `hair_midcurly` | `#230000` | 6,99 | 18,54 | 80,6% |
| `hair_braids` | `#1b0000` | 5,36 | 14,47 | 70,3% |
| `beard_longfull` | `#1f0f01` | 3,72 | 11,15 | 56,4% |
| `brow_thick` | `#490b00` | 3,75 | 17,57 | 50,3% |

A falha é estrutural: o resíduo é **94% a 100% perpendicular** ao eixo pele→`C`.
Os pixels não estão no segmento; não é alpha mal estimado. A causa é que **o pelo
tem sombreamento próprio** — nos pixels de pelo puro a luminância varia de 7,7×
(`beard_longfull`) a 45,7× (`hair_braids`) entre p5 e p95. Cabelo no render é um
objeto 3D iluminado, e nenhuma constante representa isso.

#### 3. Limiar duro em `r > 0,5` — morta: degrau de 67 níveis

Substituir o RGB por `r · base` só acima do limiar funciona onde age: o dano cai
de 42–79 níveis para **2,3 a 4,3**. Mas parte uma população contínua no meio.
Maior salto entre bins adjacentes de `r`:

| variante | maior salto |
|---|---|
| sem correção | 16,1 |
| **limiar 0,5** | **68,6** |
| `w = r` | 10,6 |

O erro pula de ~0 para ~60 níveis atravessando um pixel. Isso desenha um fio fino
no lugar do filete largo — trocou um artefato por outro.

#### 4. `w = r` — ADOTADA

Para todo pixel, em luz linear, sem limiar:

```
r     = camada / tmp_1                     por canal
w     = clamp(r_R, 0, 1)                   escalar: cobertura é geométrica
novo  = w · (r · base) + (1 − w) · camada
```

`w(0) = 0` deixa o pelo puro intocado; `w(1) = 1` refaz a pele pura a partir da
base do tom.

| | pelo (`r<0,15`) vs nativo | pele (`r>0,85`) vs `r·base` | maior salto | pico na transição |
|---|---|---|---|---|
| hoje | — | 40–79 | 16,1 | 73,3 |
| limiar 0,5 | 0,00 | 5,3–10,0 | 68,6 | 68,3 |
| **`w = r`** | **0,86–1,48** | **9,1–12,9** | **10,6** | **45,4** |
| `sqrt(r)` | 3,54–5,44 | 7,7–11,1 | 8,2 | 33,1 |

`w = r` é mais suave que **não corrigir nada** (10,6 contra 16,1) e mantém o pelo
dentro da régua de 2,89 — o que o WebP q88 já custa no miolo.

#### Por que o resultado é dedutível, e não empírico

Como `camada = r · tmp_1` por definição de `r`, o erro contra o alvo `r · base`
tem forma fechada:

```
erro = |w − 1| · r · |tmp_1 − base|
```

Verificado na medição: previsto 0,05160, observado 0,04963, razão **0,962** (os
4% são WebP e o `w` escalar contra `r` por canal).

Isso amarra o problema inteiro. Os dois extremos fixam `w(0) = 0` e `w(1) = 1`,
então **qualquer curva entre eles troca erro de um regime pelo outro** — não
existe `w` que zere os dois. Não é questão de procurar melhor.

`sqrt(r)` é a prova, e foi medida justamente por ser o meio geométrico entre
`w = r` e `w = 1`, o único ponto do intervalo que não exige escolher parâmetro:
reduziu o pico da transição em **27%** (45,4 → 33,1) e piorou o pelo em **3,7×**
(1,48 → 5,44), passando da régua nas nove combinações medidas. O desvio no pelo é
`w·r·Δ`: vale `r²·Δ` com `w = r` e `r^1,5·Δ` com `w = √r`, e em `r = 0,1` isso é
3,2× mais. A raiz é agressiva exatamente onde `r` é pequeno, que é o cabelo.

**Descartada pela régua dos 2,89.**

#### O resíduo aceito, e por que não se otimiza além daqui

Sobra o pico da transição: **~45 níveis em `r ≈ 0,35`**, sobre cerca de **7.500
px de borda por combinação** camada × tom.

**Não há verdade de referência para a transição.** Não existe render deste cabelo
sobre MST-10. O alvo `r · base` é uma extrapolação da hipótese C, boa nos
extremos e não verificável no meio. Otimizar além daqui é ajustar contra critério
inventado, e a forma fechada já mostra que o ganho viria do bolso do outro
regime.

#### O que isto NÃO resolve

Isto é **correção de borda**, não tint. `w = r` faz a pele que a máscara carrega
acompanhar o tom da base. **A cor do pelo continua sendo a nativa do render.**
O tint de seis cores segue não implementado e é problema separado — e a hipótese
2 mostra que ele não pode ser "trocar por uma cor sólida", porque o pelo tem
sombreamento próprio que uma constante não representa.

**Encerrado em 11/09/2026:** o tint não será implementado de forma nenhuma. Cor
e forma passaram a ser um slot só, e `w = r` fica sendo a única transformação da
família PELO. Ver "Saída adotada: cor e forma são um slot só".

#### Consequência para gerar por tom

O filete motivava gerar as 17 camadas de PELO por tom: +85 arquivos e +1,5 MB
para MST-06 a 10. **`w = r` resolve em runtime, com a camada que já existe.**
Esses arquivos deixam de ser necessários para este problema. O que eles
resolveriam é só o resíduo de transição acima.

#### O que o runtime passou a precisar

`r` exige o `tmp_1`, que o jogo não tinha. `make_build.py` passou a emitir
**`build/source.webp`** — `tmp_1` em 512, mesmo Lanczos e mesmo q88 das bases,
**17,6 KiB**. Medido:

- **o encode do source custa 0,02 nível** de erro médio no resultado final
  (p99 0,4–0,7), muito abaixo da régua;
- **não é preciso máscara de silhueta.** Fora da cabeça `tmp_1` e base são ambos
  fundo, `r · base ≈ camada`, e a transformação é inócua: diferença média de
  0,003 nível contra a versão com guarda.

### O tint de PELO: seis cores medidas, três reprovam (10/09/2026)

Isto mede o **tint**, que é problema separado da correção de borda `w = r`. A
borda faz a pele que a máscara carrega acompanhar o tom; o tint muda a cor do
pelo. Um não substitui o outro.

**As seis cores-alvo são ESCOLHA, não medida.** Foram definidas por decisão de
produto, não derivadas de nenhum render, e por isso são contestáveis — se a
paleta mudar, esta seção inteira precisa ser refeita. O que a medição decide é
se cada cor é **alcançável** por multiplicação a partir do pelo nativo, não se
ela é bonita.

```
k_tint = alvo_linear / nativa_linear          por canal
nativa = média em luz linear dos pixels de pelo opaco de cada camada
opaco  = alpha > 200 e r_R < 0,15
```

Mesma lógica multiplicativa do `k` de tom. Medido em `layers/*.png` a 1254,
sem passar pelo WebP.

#### Tabela 1 — a nativa de cada camada

| camada | px | hex | R linear | G linear | B linear | luminância |
|---|---|---|---|---|---|---|
| `hair_midcurly` | 260.255 | `#39251b` | 0,04117 | 0,01851 | 0,01066 | 0,02276 |
| `hair_braids` | 198.558 | `#2d211d` | 0,02641 | 0,01538 | 0,01244 | 0,01751 |
| `beard_longfull` | 181.535 | `#38241a` | 0,03940 | 0,01775 | 0,01047 | 0,02183 |
| `brow_thick` | **3.018** | `#4d2a1e` | 0,07415 | 0,02271 | 0,01274 | 0,03292 |

O pelo nativo é **muito escuro**: luminância linear entre 0,018 e 0,033, ou seja
2% a 3% do branco. É esse denominador que faz o `k_tint` explodir para as cores
claras.

`brow_thick` entra com 3.018 px contra 180–260 mil das outras. É a mesma coisa
já registrada acima: sobrancelha quase não tem núcleo opaco. **Todo resultado
dela abaixo é sobre uma amostra 60× menor e não deve ser lido como aprovação.**

#### Tabela 2 — `k_tint` por canal

| cor | alvo | `hair_midcurly` | `hair_braids` | `beard_longfull` | `brow_thick` |
|---|---|---|---|---|---|
| preto | `#1a1614` | 0,251 / 0,433 / 0,656 | 0,391 / 0,522 / 0,562 | 0,262 / 0,452 / 0,668 | 0,139 / 0,353 / 0,549 |
| castanho escuro | *nativa* | 1 / 1 / 1 | 1 / 1 / 1 | 1 / 1 / 1 | 1 / 1 / 1 |
| castanho claro | `#6b4a2f` | 3,571 / 3,699 / 2,667 | 5,567 / 4,454 / 2,285 | 3,731 / 3,859 / 2,714 | 1,983 / 3,016 / 2,231 |
| loiro | `#c8a165` | 14,03 / 19,25 / 12,21 | 21,87 / 23,18 / 10,46 | 14,66 / 20,08 / 12,43 | 7,79 / 15,70 / 10,22 |
| ruivo | `#b0522a` | 10,55 / 4,56 / 2,17 | 16,44 / 5,49 / 1,86 | 11,02 / 4,76 / 2,21 | 5,86 / 3,72 / 1,82 |
| grisalho | `#b4afa8` | 11,09 / **23,16** / **36,74** | 17,28 / 27,88 / 31,48 | 11,58 / 24,16 / 37,39 | 6,16 / 18,88 / 30,74 |

O grisalho é o caso extremo e explica a si mesmo: transformar marrom quente em
cinza neutro exige **multiplicar o azul por 31 a 37**, porque a nativa quase não
tem azul. Fator dessa ordem não sobrevive ao teto do gamut.

#### Tabela 3 — clipping

Percentual de pixels de pelo que estouram, com a perda em níveis de sRGB
(medida sem clamp, para saber o quanto passou de 255).

| cor | `hair_midcurly` | `hair_braids` | `beard_longfull` | `brow_thick` |
|---|---|---|---|---|
| preto | 0,0% | 0,0% | 0,0% | 0,0% |
| castanho escuro | 0,0% | 0,0% | 0,0% | 0,0% |
| castanho claro | 0,0% | 0,0% | 0,0% | 0,0% |
| **loiro** | **15,6%** · méd 35 · máx 132 | **19,6%** · méd 56 · máx 179 | **14,3%** · méd 29 · máx 129 | 0,0% |
| **ruivo** | **7,1%** · méd 22 · máx 57 | **12,5%** · méd 40 · máx 123 | **5,2%** · méd 18 · máx 63 | 0,0% |
| **grisalho** | **10,6%** · méd 43 · máx 238 | **14,6%** · méd 52 · máx 232 | **7,9%** · méd 34 · máx 228 | <0,05% · máx 19 |

**Preto e castanho claro passam limpos em todas as camadas. Loiro, ruivo e
grisalho reprovam.** Entre 5% e 20% do pelo estoura, com perda média de 18 a 56
níveis e picos acima de 200.

É a mesma física que tirou PELO do `k` de tom no início: lá o clipping chegava a
2,58% e já foi considerado inaceitável. Aqui é de 2 a 8 vezes pior.

#### Tabela 4 — o sombreamento próprio do pelo, antes e depois

Razão p95/p5 da luminância do pelo. Multiplicação por canal preserva razão, então
qualquer queda aqui é **efeito do clipping** achatando o sombreamento.

| cor | `hair_midcurly` | `hair_braids` | `beard_longfull` | `brow_thick` |
|---|---|---|---|---|
| preto | 14,8 → 15,3 | 70,8 → 74,3 | 9,6 → 9,7 | 2,7 → 2,9 |
| castanho escuro | 14,8 → 14,8 | 70,8 → 70,8 | 9,6 → 9,6 | 2,7 → 2,7 |
| castanho claro | 14,8 → 14,8 | 70,8 → 67,4 | 9,6 → 9,6 | 2,7 → 2,7 |
| loiro | 14,8 → 13,7 | 70,8 → **51,3 (−28%)** | 9,6 → 9,0 | 2,7 → 2,8 |
| ruivo | 14,8 → 13,6 | 70,8 → **49,5 (−30%)** | 9,6 → 9,2 | 2,7 → 2,6 |
| grisalho | 14,8 → **13,1 (−12%)** | 70,8 → **51,3 (−28%)** | 9,6 → 9,4 | 2,7 → 2,9 |

`hair_braids` é o mais frágil, perdendo até 30% da própria faixa de sombreamento.
Coerente com ele ser o de maior amplitude nativa (70,8, contra 9,6 do
`beard_longfull`): quem tem mais contraste tem mais a perder no teto.

#### Veredito

| cor | veredito |
|---|---|
| preto `#1a1614` | **passa** — `k` < 1 em todos os canais, não há teto a bater |
| castanho escuro (nativa) | **passa** por construção, `k` = 1 |
| castanho claro `#6b4a2f` | **passa** — `k` de 2 a 5,6, ainda dentro do gamut |
| loiro `#c8a165` | **reprova** — 14–20% estoura |
| ruivo `#b0522a` | **reprova** — 5–13% estoura |
| grisalho `#b4afa8` | **reprova** — 8–15% estoura, picos de 238 níveis |

Metade da paleta não é alcançável por multiplicação. O padrão é limpo: **escurecer
funciona, clarear não**, porque a nativa está a 2–3% do branco e não há headroom.

Isso não condena a ideia de tint — condena **tint multiplicativo para cores mais
claras que a nativa**. As saídas possíveis, nenhuma medida ainda: paleta só com
cores iguais ou mais escuras que a nativa; render por cor para as claras; ou uma
transformação que não seja multiplicação pura. A escolha é de produto, e a
medição só diz o que custa cada uma.

**Fechado em 11/09/2026.** A saída adotada não é nenhuma das três: cor e forma
viraram um slot só. Ver "Saída adotada: cor e forma são um slot só", abaixo.

**Discrepância registrada:** uma medição anterior desta mesma semana, feita em
outra sessão e não registrada, deu "6–19% com perda até 214 níveis". Os números
acima (5–20%, picos de 238) são da mesma ordem mas não idênticos. A diferença
provavelmente está na definição de pelo opaco ou na resolução usada; como aquela
medição não foi registrada, não há como reconciliar. Ver a nota de processo no
fim deste arquivo.

### Saída adotada: cor e forma são um slot só (11/09/2026)

**Decisão: não existe eixo de cor de cabelo.** `midcurly grisalho` não é uma
variação de `midcurly`; são dois itens de catálogo distintos, cada um com sua
forma e sua cor já fixadas no render. Esta é a saída adotada da cadeia do tint de
PELO, e ela fecha as três alternativas que a seção anterior deixou em aberto.

Dois motivos independentes, cada um suficiente sozinho.

**1. Tint multiplicativo não alcança as cores claras.** Medido e registrado na
seção anterior: loiro, ruivo e grisalho estouram de 5% a 20% dos pixels de pelo,
com picos de 238 níveis perdidos. A nativa está a 2–3% do branco em luz linear e
não há headroom. Escurecer funciona, clarear não.

**2. O gerador não controla forma e cor independentemente.** Foi a tentativa de
contornar o item 1 por render por cor, e ela falhou na premissa. A batelada tem
**24 renders de cor**, 8 grisalhos, 8 loiros e 8 ruivos, um de cada forma. A
estrutura foi medida numa amostra de 10, e **nenhum dos 10 preservou a estrutura
do cabelo**. Trocar a cor no gerador troca o penteado junto.

A medida que sustenta isso é um controle de tingimento sintético: remapear a
luminância do marrom para bater com a do render novo mantém a geometria idêntica
por construção, porque nenhum pixel se move. A distância entre perfis radiais de
autocorrelação, medida nos mesmos pixels e normalizada por contraste, separa o
que é pigmento do que é estrutura.

| render | artefato de cor | observado | estrutura | % da régua |
|---|---|---|---|---|
| `hair_longtied_grey` | 0,0009 | 0,1914 | 0,1905 | 339% |
| `hair_buzz_grey` | 0,0059 | 0,1555 | 0,1496 | 267% |
| `hair_braids_grey` | 0,0050 | 0,1488 | 0,1438 | 256% |
| `hair_shortcurly_grey` | 0,0007 | 0,1259 | 0,1253 | 223% |
| `hair_slickback_grey` | 0,0055 | 0,0598 | 0,0543 | 97% |
| `hair_midcurly_blonde` | 0,0025 | 0,0564 | 0,0539 | 96% |
| `hair_lowfade_grey` | 0,0008 | 0,0527 | 0,0519 | 92% |
| `hair_straightpart_grey` | 0,0134 | 0,0477 | 0,0344 | 61% |
| `hair_midcurly_grey` | 0,0021 | 0,0339 | 0,0318 | 57% |
| `hair_buzz_blonde` | 0,0000 | 0,0154 | 0,0154 | 28% |

A régua é `hair_midcurly` contra `hair_shortcurly`, que são formas diferentes de
propósito: 0,0561.

**O número que decide é a comparação entre as duas primeiras colunas.** Recolorir
sem mexer na forma custa no máximo 0,0134, e a menor mudança estrutural observada
é 0,0154. O piso do lote já é maior que o teto do que a cor sozinha explica.
Quatro renders passam de duas a três vezes a régua de "forma diferente de
propósito" e são penteados novos, não recolorizações: `longtied`, `buzz`,
`braids` e `shortcurly` grisalhos.

Confirmado por duas medidas independentes. A contagem de alternâncias claro e
escuro por varredura horizontal, por 100 px de cabelo, vai de 1,97 para 6,73 no
`shortcurly`, de 2,81 para 6,76 no `longtied` e de 4,95 para 8,41 no `buzz`. E o
IoU das máscaras de cabelo contra a própria forma fica entre 0,7539 e 0,8484,
enquanto o par de marrons de maior sobreposição, `buzz` contra `longtied`, dá
0,7958. O `hair_lowfade_grey` sobrepõe o próprio original menos do que duas
formas distintas se sobrepõem entre si. Não é artefato de limiar de máscara: o
IoU tem máximo entre os limiares 16 e 24 e cai nas pontas.

**Duas ressalvas de método, para o resultado não ser lido além do que mede.** O
descritor de textura é um teste de mão única: valor alto prova que a estrutura
mudou, valor baixo não prova que ela se manteve. Uma versão anterior do descritor
deu 1,3% de distância entre `braids` e `shortcurly`, que são formas obviamente
distintas. E a tentativa de medir o período dominante da trança e do cacho por
varredura foi descartada: a transformada engancha no envelope do cabelo inteiro
em vez do detalhe, e acusou 45% de variação até no par mais parecido do lote. Os
cortes de veredito em 100% e 40% da régua são arbitrados, não medidos.

#### A saída C é impublicável, não apenas degradada

A coluna do tint sintético que serviu de controle numérico acima é também a
evidência visual contra a terceira saída que a seção anterior listou, o tint com
clipping. Ela é **visualmente inaceitável**: vazamento laranja sobre a pele e
cabelo sem desenho, com as mechas achatadas numa massa. O clipping não degrada o
resultado de forma tolerável, ele destrói o asset. Registrado aqui para que a
saída C não volte com o argumento de que 5–20% de pixels estourados seria pouco.

#### Consequência de catálogo

Cabelo passa a ter **32 itens sem eixo de cor**: as 8 formas escuras nativas mais
os 24 renders de cor como itens próprios.

Os renders novos passam pelos **mesmos critérios de aceitação de qualquer asset**,
sem tratamento especial por serem variação de cor. O que muda em relação a um
asset avulso é o destino de quem reprova: como a geração é automatizada, o
reprovado **é regerado, não retirado do catálogo**. Corrigir a cor por
pós-processamento está fora de questão, porque seria exatamente a multiplicação
que o item 1 reprovou.

**Limiar de cor: dE76 ≤ 12**, contra o hex de referência da cor. É mais folgado
que os 10 usados em outras aceitações deste repositório, e o motivo está na
decisão desta seção: com cor e forma no mesmo slot, **o hex alvo é referência de
nome, não especificação**. O item precisa ser reconhecivelmente grisalho, loiro
ou ruivo; não precisa bater o hex.

Consequências que caem junto: não há campo de cor de cabelo no modelo, `tone.ts`
não ganha nenhuma transformação de tint, e a correção de borda `w = r` continua
sendo a única transformação da família PELO. O `brow_*` e o `beard_*` seguem sem
eixo de cor pelo mesmo motivo.

#### A medição de cor das 24 (11/09/2026)

Estatística do `measuredHex`: faixa de luminância, promediada em luz linear.
Alvos: grisalho `#b4afa8`, loiro `#c8a165`, ruivo `#b0522a`. **Limiar dE76 ≤ 12.**

**Correção de método, e ela invalida números de uma versão anterior desta
seção.** O NOTES define pelo opaco como `r < 0,15`, com `r = camada / tmp_1` em
luz linear. Esse critério foi calibrado em cabelo castanho escuro, onde opaco e
escuro coincidem, e **não transfere para cabelo claro**: pelo grisalho opaco tem
`r` em torno de 0,7 contra a pele do `tmp_1`, então `r < 0,15` seleciona só as
sombras mais fundas e puxa a medida para o escuro. Em `hair_buzz_blonde` sobravam
82 pixels de 1254².

Opacidade é propriedade geométrica, não cromática. O pelo opaco passa a ser
**a máscara de cabelo erodida por `disk(4)`**, que derruba a orla de cobertura
parcial sem olhar para a cor.

#### A faixa de cabelo é p90–p98. A de pele é p70–p90 e não transfere

**Decidido em 11/09/2026.** Medir cor de cabelo usa a faixa **p90–p98** de
luminância. A faixa p70–p90 continua valendo para pele e **não vale para pelo**.

O motivo é geométrico. A janela de pele é a testa central, quase plana, com
desvio de luminância de 0,043. Cabelo é massa 3D com sombreamento próprio, de
7,7× a 45,7× entre p5 e p95 conforme medido na hipótese 2. Na mesma faixa
percentual, a testa entrega a cor do pigmento e o cabelo entrega a sombra.

**Esta é uma família de erro que já apareceu seis vezes neste arquivo, e vale
nomeá-la: métrica calibrada num contexto não transfere para outro só porque a
fórmula roda.**

- **O alvo de −37 em sRGB**, aposentado em favor da razão de luminância linear:
  −37 sobre pele clara é −9 sobre pele escura, e a fórmula não avisa.
- **O teto em p90 do `measuredHex`**, que existe porque acima dele entra reflexo
  especular, que tem a cor da luz e não do pigmento.
- **O `r < 0,15` para pelo opaco**, que é critério de escuridão disfarçado de
  critério de opacidade: funciona em cabelo castanho e seleciona só sombra em
  cabelo claro.
- **A faixa p70–p90 aplicada a cabelo**, que é da testa quase plana e cai na
  sombra numa massa 3D.
- **HSV `S` contra Lab `C*`**: `S` é normalizado pelo brilho e `C*` não, então
  uma imagem escura "passa" em saturação e reprova em croma. Ver "O que o prompt
  move e o que não move", na seção do gerador.
- **A mediana de V como cor de cabelo**: numa massa 3D com sombreamento próprio a
  mediana mede sombra e amostra, não pigmento. Nos loiros regerados ela variou
  de 135 a 184 com a mesma linha de cor. O critério passou a V p90, que mede a
  mecha iluminada. Ver "Loiro: o critério de cor passa a ser V p90".

O padrão a reconhecer é sempre o mesmo: a definição foi escrita olhando um caso,
e o caso novo difere na variável que a definição não menciona.

As 24 foram medidas nas duas faixas antes da decisão:

| cor | p70–p90 médio | passam | p90–p98 médio | passam |
|---|---|---|---|---|
| grisalho | 11,3 | 6 de 8 | **5,8** | **8 de 8** |
| loiro | 14,2 | 2 de 8 | 14,2 | 1 de 8 |
| ruivo | 15,6 | 1 de 8 | **25,1** | **0 de 8** |

**O grisalho é problema de métrica, não de asset.** O erro médio cai pela metade
e os 8 passam. O loiro dá o mesmo erro médio nas duas faixas e reprova nas duas.
O ruivo **piora** na faixa clara e reprova mais claramente.

A decomposição explica por quê:

| cor | faixa | ΔL\* | ΔC\* | Δmatiz |
|---|---|---|---|---|
| grisalho | p70–p90 | −8,3 | +6,7 | −27,2° |
| grisalho | p90–p98 | **+1,6** | +4,2 | −24,9° |
| loiro | p70–p90 | −7,7 | −7,3 | −16,0° |
| loiro | p90–p98 | +2,7 | **−11,7** | −13,3° |
| ruivo | p70–p90 | −0,8 | −15,4 | −0,1° |
| ruivo | p90–p98 | **+13,3** | **−21,1** | +0,7° |

No grisalho, trocar de faixa zera o erro de luminância e o croma já era pequeno,
então sobra pouco. No loiro e no ruivo o que domina é **falta de croma**, e
croma não se conserta escolhendo faixa: na faixa clara ele piora, porque o
realce especular tem a cor da luz e lava o pigmento. É o mesmo motivo pelo qual
o `measuredHex` da pele tem teto em p90.

O ruivo acerta o matiz com precisão notável, dentro de 1° nas duas faixas. Ele
é do tom certo e fraco demais.

#### Veredito das 24

**Os 8 grisalhos estão aprovados**, 8 de 8 na faixa de cabelo, erro médio 5,8.
Reprová-los na faixa de pele teria sido reprovar a régua, não o asset.

**Os 8 loiros e os 8 ruivos vão para regeração, com mais saturação.** O erro
deles é de croma e é estável nas duas faixas, então não é artefato de método. O
matiz do ruivo está certo dentro de 1°, o que estreita o pedido: é para saturar,
não para mudar de cor.

| cor | destino |
|---|---|
| grisalho | aprovado, 8 de 8 |
| loiro | regerar com mais croma |
| ruivo | regerar com mais croma, matiz mantido |

**Atualizado em 14/09/2026:** os loiros foram regerados e os 8 aprovados pelo
critério de V p90. Os ruivos não foram regerados; a correção de valor em pós foi
a quarta hipótese de correção de cor, descartada. O valor deles passa por V p90
e o croma segue em aberto. Ver as seções de loiro e de ruivo abaixo.

#### Loiro: o critério de cor passa a ser V p90 (14/09/2026)

**Critério: V p90 > 200**, no lugar da mediana. Medido no Chrome sobre os 8
loiros regerados, a mediana de V foi de 135 a 184 com a mesma linha de cor, em
dois grupos que não são ruído:

| grupo | estilos | V p50 no Chrome |
|---|---|---|
| volume alto | shortcurly, midcurly, braids, straightpart | 164–184 |
| rente ao crânio | buzz, lowfade, slickback, longtied | 135–146 |

Duas causas somadas, nenhuma é erro de geração. **Óptica real**: estilo rente
mostra couro cabeludo entre os fios, e o pixel fica escuro com o pigmento certo.
**Viés de amostra**: a máscara do Chrome pega a casca externa, que em estilo
rente é borda sombreada; o `n` dela ia de 3.657 px no `longtied` a 10.476 no
`braids`. Com p90 a faixa no Chrome fecha em 167–208.

**Aceito por decisão, não corrigir:** matiz 26–33 contra alvo 36, porque texto
não move matiz além de ~2°; e S 0,67 no `shortcurly` e 0,68 no `braids`, porque
dourado mais forte em cabelo volumoso é plausível.

**Medido com a ferramenta versionada**, `scripts/hair-color.py measure`, sobre o
pelo opaco da extração:

| arquivo | n | H | S | V p50 | V p90 | V p90 > 200 |
|---|---|---|---|---|---|---|
| braids | 243.865 | 29,1 | 0,616 | 166 | 234 | passa |
| buzz | 97.615 | 26,4 | 0,495 | 174 | 209 | passa |
| longtied | 140.268 | 26,7 | 0,478 | 157 | **201** | passa |
| lowfade | 131.412 | 26,5 | 0,589 | 148 | **202** | passa |
| midcurly | 308.929 | 28,6 | 0,541 | 178 | 219 | passa |
| shortcurly | 169.461 | 31,0 | 0,623 | 175 | 216 | passa |
| slickback | 137.870 | 27,5 | 0,541 | 167 | 215 | passa |
| straightpart | 185.639 | 28,7 | 0,539 | 162 | 214 | passa |

**Os 8 passam. O critério é definido na máscara versionada**, decidido em
14/09/2026: ela pega o cabelo inteiro e é a que está em código. A
máscara versionada tem de 25 a 30 vezes mais pixels que a do Chrome e pega o
cabelo inteiro, não a casca. Nela a mediana vai de 148 a 178 e os dois grupos
não se separam: o `buzz`, que é o mais rente, tem a terceira maior mediana. O
limiar de 200 foi calibrado na máscara do Chrome, onde o p90 desce a 167, e com
ela alguns destes reprovariam; a medição do Chrome fica como registro da
calibração, não como critério. `longtied` e `lowfade` passam por 1 e 2 níveis.

Os 8 aprovados estão versionados em `raw/hair_*_blonde.png`; os de 11/09 foram
para `raw/_rejected/hair_*_blonde_v1.png`.

#### Ruivo: curva de valor em pós — quarta hipótese de correção de cor, descartada (14/09/2026)

**Descartada e revertida.** Nenhum arquivo corrigido entrou no repositório; o
`raw/hair_midcurly_red.png` é o render original, byte a byte. Três motivos, e o
terceiro bastaria sozinho:

1. **O halo é impublicável.** A máscara S pega pele sombreada da linha do cabelo
   e a curva clareia essa pele, deixando uma borda alaranjada dura na testa.
2. **A faixa dinâmica cai 33%.** A razão p95/p5 de luminância do pelo opaco vai
   de 31,72 a 21,21 no `midcurly_red`, com o decil mais claro inteiro em 255. É
   o gate que protege o desenho da mecha, e ele não se negocia pelo número que
   protege.
3. **A curva corrige o eixo errado.** Pelo critério de V p90 adotado para o
   loiro, o valor dos ruivos já passa: V p90 de 150 a 181 contra alvo 176. O
   "escuro demais" veio da mediana, que é a estatística aposentada. O erro do
   ruivo na faixa de cabelo é **croma**, e uma curva sobre V não mexe em croma.
   Em 5 dos 8 ela piorou o dE p90–p98.

**As quatro hipóteses de correção de cor de cabelo, todas descartadas:**

| # | hipótese | motivo |
|---|---|---|
| 1 | tint multiplicativo sobre a camada nativa | estoura de 5% a 20% nas cores claras; não há headroom |
| 2 | render por cor, com forma preservada | o gerador não controla forma e cor independentemente |
| 3 | tint com clipping | impublicável: vazamento laranja na pele, cabelo sem desenho |
| 4 | curva de valor em pós, só no ruivo | halo na pele, faixa dinâmica −33%, eixo errado |

O que ficou adotado é cor e forma no mesmo slot, com a cor vinda do render.
`fix-value` continua em `scripts/hair-color.py` só para reproduzir esta medição.

**Estado do ruivo:** valor aceito pelo critério de V p90. O erro em aberto é
croma, e nenhuma correção dele está em andamento.

O registro abaixo é a medição que levou ao descarte.


**Decidido:** levar a mediana de V ao máximo que a razão p90/p50 permite, sem
comprimir a razão para bater 176. O gate da faixa dinâmica não se negocia pelo
número que ele protege, e 176 é derivado do hex, que é referência de nome.

**Aplicado só no `midcurly_red`, e parado no composto.** O composto mostrou um
defeito visível: **halo alaranjado na testa, seguindo a linha do cabelo, com
borda dura.** A máscara S, cabelo da extração com HSV S ≥ 0,50, **pega pele
sombreada da linha do cabelo**, e a curva clareia essa pele. A separação por
saturação vale para testa iluminada, com S em torno de 0,42, e não para a pele
que o cabelo sombreia. Pixels da máscara S em que o render é igual à cabeça
careca:

| diferença máxima contra `tmp_1` | px | % da máscara S | S mediana |
|---|---|---|---|
| < 24 | 1.354 | 0,4% | 0,545 |
| < 40 | 8.140 | 2,4% | 0,557 |
| < 60 | 21.478 | 6,4% | 0,588 |

Além do halo, no `midcurly_red`:

| métrica | antes | depois |
|---|---|---|
| V p50 / p90 | 122 / 181 | 172 / 255 |
| razão p90/p50 | 1,4836 | 1,4826 |
| p95/p5 de luminância, pelo opaco | 31,72 | **21,21, −33,1%** |
| pixels em V = 255 na máscara | 0 | **34.625, 10,3%** |
| degrau de V na borda da máscara | −23,2 | **+34,6** |
| dE76 p90–p98 | 33,4 | 32,2 |
| H / S | 17,68 / 0,850 | 17,70 / 0,850 |

No teto da razão não sobra folga acima de p90, e **o decil mais claro inteiro vai
a 255**. A faixa dinâmica perde um terço. H e S não mudaram.

**Os outros 7 foram só medidos**, nada aplicado:

| arquivo | V p50 | V p90 | mediana possível | faixa dinâmica | dE p90–p98 antes → depois |
|---|---|---|---|---|---|
| braids | 101 | 165 | 156,1, teto | −14,3% | 21,4 → 26,0 |
| buzz | 140 | 176 | 176, alvo | −12,2% | 21,6 → 23,4 |
| longtied | 120 | 162 | 176, alvo | −35,3% | 28,8 → 27,1 |
| lowfade | 107 | 150 | 176, alvo | −18,7% | 21,8 → 24,9 |
| shortcurly | 122 | 171 | 176, alvo | −21,2% | 21,9 → 25,6 |
| slickback | 117 | 165 | 176, alvo | −34,2% | 29,3 → 27,9 |
| straightpart | 113 | 171 | 168,5, teto | −27,2% | 24,2 → 27,0 |

**A curva de V corrigia o eixo errado.** Em 5 dos 8 ela piora o dE na faixa de
cabelo, e em nenhum chega perto de 12. O V p90 antes da correção vai de 150 a 181
contra o alvo de 176: pela mesma lógica que trocou a mediana por p90 no loiro,
**o valor do ruivo já está no alvo**, e o "escuro demais" veio da mediana. O erro
do ruivo na faixa de cabelo é falta de croma, e a curva de V não mexe em croma.
**Decidido em 14/09/2026: hipótese descartada e revertida.**

#### Modo de falha do gerador, para a próxima batelada

**Resposta vazia em cerca de 14% dos envios, sem erro.** O gerador não sinaliza
falha: devolve vazio e segue. Resolvido por reenvio simples, sem mudar o prompt
nem os parâmetros.

Consequência operacional: uma batelada de N itens exige aproximadamente 1,16 × N
envios, e **a contagem de arquivos na pasta é o único sinal de que a batelada
terminou**. Conferir a contagem esperada antes de considerar a batelada completa,
em vez de assumir que ausência de erro significa sucesso.

#### O que o prompt move e o que não move (14/09/2026)

Achado da regeração do `hair_midcurly_blonde`, e **generalizável para qualquer
batelada futura de assets**. Alvo `#c8a165`, que em HSV é H 36, S 0,495, V 200:

| eixo | move com prompt? | evidência |
|---|---|---|
| **V**, brilho | **sim** | 155 → 191 contra alvo 200, numa geração só, trocando `not pale` por `bright, luminous` e declarando o hex como mid-tone |
| **S**, saturação | sim | 0,54 → 0,49 contra alvo 0,495 |
| **H**, matiz | **não** | 24–31 → 30 contra alvo 36. `clearly yellow-gold` moveu cerca de 2°, e os seis graus restantes não cederam |

**Consequência: matiz exato é pós-processamento, não geração.** Se H virar
requisito duro algum dia, a saída é rotação de matiz em pós sobre a máscara de
cabelo, e não mais uma rodada de prompts. Rodada de prompt para corrigir matiz é
custo sem retorno.

**Matiz do loiro em torno de 30 está aceito por decisão.** Não conta como
reprovação na aceitação de cor dos loiros.

**O mecanismo que reconciliou duas medições que pareciam contraditórias**, e que
vai voltar:

> HSV `S` é normalizado por `V` (`S = (max−min)/max`), logo invariante a brilho,
> e por isso a saturação "passava". Lab `C*` não é normalizado: `a*` e `b*`
> encolhem com `L*`, então escurecer derruba o croma mesmo com a proporção entre
> canais intacta. As duas medições diziam a mesma coisa, que a imagem está
> escura, por eixos diferentes. Não havia contradição.

Na prática: quando uma medida em HSV e outra em Lab discordarem sobre saturação,
olhar o brilho antes de concluir qualquer coisa sobre cor.

**Vocabulário: o que é proibido é o adjetivo de cor, não a palavra.** `deep`
como adjetivo de cor, em `deep red` ou `deep blonde`, empurra o valor para baixo
e é **proibido nas linhas de cor**. `deep shadows between the strands` é
**estrutura de sombreamento**, não cor, e tem 25 renders de evidência a favor: a
geração de loiro que passou, V 155 → 191, usava essa linha. O mesmo vale para
`rich`, `dark`, `muted` e `not pale`: banidos como adjetivo de cor, irrelevantes
fora disso.

A palavra chegou a ser banida por inteiro, e o banimento pegou uma linha que
estava funcionando. A regra a aplicar é pela função da palavra na linha, não pela
palavra.

### Clipping residual da família PELE, aceito por decisão

Isolando PELE, das 150 combinações sobra **uma** acima de 0,1%:

| combinação | % no miolo | o que é |
|---|---|---|
| `eye_round` × MST-01 | 0,21% (93 px) | esclera |
| `ear_normal` × MST-01 | 0,09% (41 px) | especular na hélice |
| `ear_protruding` × MST-01 | 0,09% (25 px) | especular na hélice |

Os oito `nose_*` e `mouth_*` ficam limpos em todos os 10 tons. Todo o resíduo
está em olho e orelha, e sempre no MST-01, o tom mais claro, onde o `k` do azul
é 1,74.

**Decisão: deixar estourar.** Marcar a esclera para escapar do `k` zeraria o
0,21%, mas custa uma exceção no modelo, e o ganho não paga.

Registro honesto do tamanho do efeito, porque a decisão foi tomada com a ideia de
"branco ficando branco" e a medida mostra um pouco mais que isso: **nenhum desses
pixels estava saturado antes.** Mediana de origem 191/199/206 no `eye_round` e
244/222/211 no `ear_normal`; o corte tira em média 9 a 16 níveis de sRGB, com
máximo de 62. É cinza claro virando branco, em 159 pixels no total, no tom mais
claro da escala. Continua desprezível — só não é literalmente nulo.

### A íris recebe o k

As camadas `eye_*` são ~74% pele de pálpebra, ~16% cílios e pupila, ~2 a 4%
esclera e **7 a 9% íris**. A íris recebe o `k` junto com o resto e muda de tom
com a pele. Fisicamente errado: cor de olho não depende de tom de pele.

Aceito porque é imperceptível em marrom, que é a única cor de íris nos assets
atuais. **Se cor de olho virar slot próprio, a íris sai da camada** e vira
família própria, como o PELO.

### Compor não acrescenta clipping

O clipping nasce inteiro na multiplicação da camada pelo `k`. A composição
depois é interpolação entre dois valores já dentro da faixa, e interpolação não
sai do intervalo dos extremos. Medir na camada transformada é medir onde o
fenômeno existe; medir no composto daria o mesmo número.

## Decisões

### Os slots do avatar são oito (15/09/2026)

**tom, nose, mouth, eye, brow, ear, hair, beard.**

A fila de trabalho chegou a falar em "schema de nove slots". **Foi erro de
contagem do Santiago**, registrado como tal: o nono era `hairColor`, e esse eixo
deixou de existir quando cor e forma viraram um slot só, em 11/09/2026.

`tom` é a base de `build/bases/`. Os outros sete são famílias de camada em
`layers/`. O campo `scar` do avatar do jogo, em `src/game/skin.ts`, é do modelo
procedural em SVG, não é camada, e fica fora.

### Conflito aberto: composição por camadas contra catálogo de retratos (15/09/2026)

**Resolvido em 15/09/2026 a favor da saída A: camadas vencem.** O registro do
conflito fica abaixo como estava, porque é o contexto da decisão. Ver "Decisão:
composição por camadas vence o catálogo de retratos", logo depois das saídas.

Os fatos, em ordem:

- **10/08** autorizou composição do avatar por camadas.
- **24/08** decidiu retratos WebP com SKU discreto, `faceId` único por gate, e o
  criador traço a traço **explicitamente fora de escopo**. A regra do catálogo diz
  que o eixo é o rosto e que corte de cabelo nunca define item sozinho.
- **As duas últimas semanas construíram o que 24/08 excluiu:** este pipeline de
  camadas, com 32 itens de cabelo que são o mesmo rosto com outro cabelo.
- **A decisão de 24/08 é a mais recente e é a que está em código**, em
  `api/_lib/catalog.ts`. O contrato de asset dela é retrato 512×640, sem alpha,
  até 80 KB, em `public/skins/<tier>_<id>.webp`. As camadas daqui são 512×512 com
  alpha.

As três saídas possíveis, **sem recomendação**:

| | saída | o que muda |
|---|---|---|
| **A** | camadas vencem | o catálogo de retratos é substituído, o gate de `faceId` cai, e a posse é validada contra a tupla de 8 slots |
| **B** | retratos vencem | o pipeline vira gerador: compõe, achata em 512×640 sem alpha, e cada combinação vira SKU; as camadas viram ferramenta interna |
| **C** | convivem | retratos como SKU pago, criador por camadas como grátis |

`catalog.ts` com os 32 itens de cabelo estava parado até esta decisão.

### Decisão: composição por camadas vence o catálogo de retratos (15/09/2026)

**Saída A.** O catálogo de retratos é substituído, o gate de `faceId` cai, e a
posse passa a ser validada contra a tupla de 8 slots.

**Os dois motivos da decisão de 24/08 envelheceram:**

- **Validar 8 itens não é materialmente mais difícil que validar 1.** É o mesmo
  lookup repetido por slot, e o inventário já é log de eventos com posse
  derivada. A dificuldade que justificava um item por avatar não existe no
  código que está aí.
- **"Mesmo rosto, outro cabelo" só era problema quando o produto era o rosto.**
  Com retrato como SKU, dois itens de mesmo rosto eram o mesmo produto vendido
  duas vezes, e o gate de `faceId` impedia isso. Com o item como produto, trocar
  o cabelo é exatamente o que se vende, e o problema deixa de existir.

**As razões a favor:**

- **O criador é conteúdo compartilhável.** Um avatar montado pelo jogador é algo
  que ele mostra; um retrato escolhido de uma lista, não.
- **SKU por item vende melhor que SKU por rosto no grão de 500 moedas.** O preço
  de entrada compra uma peça, e o avatar se completa em várias compras pequenas,
  em vez de uma compra grande por um rosto inteiro.

**Nada foi implementado nesta data.** Antes de qualquer código há um
levantamento, só de leitura, sobre o que o gate de `faceId` protege, como a posse
é verificada no replay, quantos avatares procedurais existem salvos e em que
estado está o catálogo de retratos. A base de avatares salvos pode mudar o
faseamento de A, com migração ou reset; não muda se A vale.

### O levantamento: A sai sem custo de migração (15/09/2026)

Feito só com leitura do repositório do jogo, em `origin/main` 33bea4f. É o que
torna A barata.

**Não há o que migrar:**

- o catálogo de retratos tem **0 SKUs de produção**: `CATALOG = []` desde 24/08,
  com 3 fixtures de teste fora de `public/`;
- a loja está fechada pela flag `tfwallet:v1:store_open`, então **ninguém comprou
  nada**;
- o editor do avatar procedural (`src/game/skin.ts`) viveu só na branch `reforma`,
  de 16/06 a 09/07, e **nunca chegou à produção**. O primeiro deploy de produção da
  `reforma`, `9478798`, já trazia a remoção; todo deploy de produção de 08/07 a
  23/07 foi conferido sem ele. O avatar só era gravado em `localStorage`, que é
  separado por domínio, então preview não vaza para produção.

**Posse com 8 slots é o mesmo lookup.** O inventário é um `LRANGE` do log de
eventos, e `ownedItems` deriva a posse dele. Validar a tupla são 8 checagens
contra o mesmo conjunto, não 8 leituras.

**O servidor não muda enquanto o visual não tiver efeito no jogo.**
`replayJournal`, o replay do leaderboard, não olha cosmético. O equipado só
entra no journal se um item passar a ter efeito, como já diz o "PASSO 4" em
`src/game/wallet.ts`.

**O equipado vira tupla de 8**, validada no cliente contra `ownedItems`, como o
item único é validado hoje.

**O gate de `faceId` cai junto com o contrato de retrato** (512×640 sem alpha,
`public/skins/<tier>_<id>.webp`, sidecars em `art/skins/`). Os cinco lugares que
mudam:

| lugar | o que tem hoje |
|---|---|
| `api/_lib/catalog.ts` | campo `faceId`, `OPENING_MIN_FACES_PER_TIER` e `facesByTier` em `openingReadiness` |
| `api/_lib/assetContract.test.ts` | gate de `faceId` único e declarado, e os gates de pasta e sidecar nos dois sentidos |
| `scripts/open-store.ts` | portão de abertura que imprime e exige rostos distintos por tier |
| `docs/lancamento-loja.md` | critério de "12 retratos, 3 `faceId` por tier" |
| `scripts/build-skin-assets.py` | conversor para o contrato de retrato, que pede "`faceId` único" |

O contrato em si mora em `api/_lib/assetContract.ts`, com as fixtures em
`test/fixtures/skins/` e os sidecars em `art/skins/`; sai junto com o gate.

### Distribuição por jsDelivr: tag, não branch (15/09/2026)

O `build/` é servido pelo jsDelivr a partir de **tag git**, nunca de branch.

```
https://cdn.jsdelivr.net/gh/TheSMF-Group/thefenomeno-assets@<tag>/build/<caminho>
```

Exemplo, na primeira tag: `https://cdn.jsdelivr.net/gh/TheSMF-Group/thefenomeno-assets@skins-v1/build/layers/hair_midcurly_red.webp`.

**Por que tag:** o jsDelivr segura o conteúdo de branch em cache por horas. Um
asset corrigido e pushado continua servido velho, e isso vira bug que parece do
build. Tag é imutável, então a URL identifica exatamente um conteúdo.

**Regras:**

- tag nova a cada mudança publicada em `build/`; **nunca mover uma tag existente**,
  porque o cache dela não expira pelo mesmo motivo;
- nome no padrão `skins-vN`, sequencial;
- a tag aponta para um commit de `skins-import` em que regressão e build passam.

`@main` não serve `build/`: o pipeline vive em `skins-import`, que não tem
histórico em comum com o `main`. O jogo hoje aponta seus outros assets para
`@main`, e isso não muda nada aqui.

| tag | conteúdo de `build/` |
|---|---|
| `skins-v1` | 10 bases de tom, 32 camadas nativas, 24 camadas de cabelo colorido, `source.webp` e `tones.json` |

O commit de cada tag sai de `git rev-list -n1 <tag>`; ele não é copiado para cá
para não existir em dois lugares.


### beard_stubble — aprovado com 2 blobs, por decisão

Aprovado em 09/09/2026 **por decisão, não por passar no critério.** O critério
pede 1 blob contíguo para o slot `beard`; esta camada tem 2.

Motivo: a costeleta desconectada é característica do render, não artefato de
máscara. No render definitivo a barba não encosta no corpo principal do lado
direito, e a máscara está reproduzindo isso corretamente.

| | v1 (arquivada) | v2 (definitiva) |
|---|---|---|
| blobs | 2 | 2 |
| área | 70.384 px | 144.024 px |
| esquerda / direita | 23.951 / 46.433 | 65.462 / 78.562 |
| razão E/D | 0,52 | **0,83** |
| % na região (y0=480) | 100,0 | **100,0** |
| blob solto | costeleta esquerda, 3.519 px | costeleta direita, 6.614 px |

A v2 foi promovida por ser simétrica (0,83 contra 0,52) e por cobrir queixo,
mandíbula e as duas costeletas. Fontes e camadas da v1 ficam em `_rejected/`.

Tentativa descartada: limiar 10 com corte de 0,2% sobre a v1. Gerou blob
espúrio na têmpora e subiu pela bochecha até a altura dos olhos, derrubando a
cobertura da região para 85,7%.

### hair_lowfade_grey — aprovado com 2 blobs, por decisão

Aprovado em 14/09/2026 **por decisão, não por passar no critério**, mesmo
tratamento do `beard_stubble`. O critério pede 1 blob contíguo para o slot
`hair`; esta camada tem 2.

| blob | área | onde |
|---|---|---|
| principal | 130.798 px, 18,88% da cabeça | topo, y 0–450, x 290–948 |
| solto | 4.432 px, 0,64% da cabeça | têmpora esquerda, y 345–455, x 292–358 |

Motivo: o blob solto é o pedaço do degradê na têmpora esquerda, separado da
massa do topo pela zona que desbota. **É característica do render, não artefato
de máscara.** Um low fade tem por definição uma faixa em que o cabelo some, e o
que sobra abaixo dela fica desconectado. Só aparece do lado esquerdo, que é onde
o render deixou mais pelo abaixo da faixa.

O critério de 1 blob sempre foi um proxy para "a máscara é a feição, e não a
cabeça inteira nem ruído espalhado". Nesta camada ele cumpre esse papel: os dois
blobs são cabelo, e nenhum é pele, fundo ou salpicado. Registrado como exceção em
`BLOB_EXCEPTIONS` no `scripts/extract-layers.py`, ao lado do `beard_stubble`.

### hair_lowfade_blonde — aprovado com 2 blobs, por decisão

Aprovado em 15/09/2026 **por decisão, não por passar no critério**, pelo mesmo
precedente do `hair_lowfade_grey`.

| blob | área | onde |
|---|---|---|
| principal | 136.040 px, 19,63% da cabeça | topo, y 5–338, x 294–947 |
| solto | 3.491 px, 0,50% da cabeça | têmpora esquerda, y 359–453, x 291–339 |

O blob solto é o mesmo degradê na têmpora esquerda que o grisalho tem, na mesma
região: lá são 4.432 px em y 345–455, x 292–358. O loiro de 11/09 tinha 1 blob, e
o regerado ganhou a ilha. O blob solto passa o corte de área mínima de 3.464 px
por 27. Registrado em `BLOB_EXCEPTIONS` no `scripts/extract-layers.py`.

### Extração das camadas de cor (15/09/2026)

`scripts/extract-layers.py` rodado nos 24 renders de cor de `raw/`, com o
Python 3.14 de 64 bits. Antes, a regressão contra `layers/` reproduziu **32 de
32 byte a byte**. Depois de extrair, `--regress` sobre as 56 camadas de `layers/`
reproduz **56 de 56**.

**As 24 passam o gate.** Na primeira passada `hair_lowfade_blonde` reprovou com 2
blobs e ficou fora; foi aprovado por decisão e está em `BLOB_EXCEPTIONS`. Ver
"hair_lowfade_blonde — aprovado com 2 blobs, por decisão".

| camada | blobs | cobertura |
|---|---|---|
| grisalhas, 8 | 1; 2 no `lowfade`, por decisão | 92.940 a 315.922 px |
| loiras, 8 | 1; 2 no `lowfade`, por decisão | 109.115 a 337.317 px |
| ruivas, 8 | 1 | 122.377 a 377.992 px |

Nenhuma camada tem pixel fora da caixa de região.

**O build dobra, e é esperado:** são 24 camadas novas. `make_build.py` pega toda
camada de `layers/`, então elas entram sem mudança de código.

| | arquivos | tamanho |
|---|---|---|
| bases | 10 | 144,2 KiB |
| camadas nativas | 32 | 379,9 KiB |
| **camadas de cabelo colorido** | **24** | **575,0 KiB, 51,5% do build** |
| source | 1 | 17,6 KiB |
| **build** | **67** | **1.116,8 KiB**, antes 541,8 |

Os 43 arquivos que já existiam saíram byte a byte iguais. Camada de cabelo
colorido pesa em média 24,0 KiB contra 11,9 KiB das nativas.

**Por slot**, as camadas:

| slot | arquivos | total | média | maior |
|---|---|---|---|---|
| `hair` | 32 | 741,4 KiB | 23,2 KiB | 41,6 KiB |
| `beard` | 6 | 89,7 KiB | 15,0 KiB | 24,9 KiB |
| `eye` | 5 | 41,8 KiB | 8,4 KiB | 8,9 KiB |
| `nose` | 4 | 29,3 KiB | 7,3 KiB | 8,4 KiB |
| `mouth` | 4 | 19,3 KiB | 4,8 KiB | 5,3 KiB |
| `brow` | 3 | 18,8 KiB | 6,3 KiB | 8,2 KiB |
| `ear` | 2 | 14,7 KiB | 7,3 KiB | 7,9 KiB |

**Cabelo é 66,4% do build**: 741,4 KiB nos 32 itens, dos quais
575,0 KiB são os 24 coloridos e 166,4 KiB os 8 nativos.

**Consequência para o carregamento, registrada sem decisão.** Se o jogo baixar o
`build/` inteiro antes do primeiro frame, são 1.116,8 KiB, e perto de 1 MB disso
é cabelo que o jogador não está usando. Isso é problema de UX, não de disco. A
saída é carregar sob demanda por slot: um avatar precisa de uma base, do
`source.webp` e de uma camada por slot, o que dá **104,3 KiB no caso típico
e 137,3 KiB no pior caso**, contra 1.116,8 KiB do `build/` inteiro.

### Renders de cor e bigodes versionados (14/09/2026)

Os 24 renders de cor e três arquivos de bigode existiam só na cópia de trabalho de
uma máquina, fora do git. Mesma classe de risco da medição de flood, que quase se
perdeu. Entraram em `raw/`:

| arquivo original | destino | status |
|---|---|---|
| 8 `hair_*_grey.png` | `raw/` | aprovados |
| 8 `hair_*_blonde.png`, 8 `hair_*_red.png` | `raw/` | material de trabalho, reprovados por cor |
| `beard_mustache (2).png`, 1.674.310 bytes | `raw/beard_mustache_v3.png` | o bom da última rodada |
| `beard_mustache (1).png`, 1.545.810 bytes | `raw/_rejected/beard_mustache_v2.png` | descartado |
| `mustache_vs_mouths.png` | `raw/_rejected/` | diagnóstico, **movido, não apagado** |

`(1)` e `(2)` eram artefato do Windows, não versionamento. A ordem v2/v3 é a de
gravação. O `beard_mustache.png` de 09/09, fonte da camada atual, não mudou.

O ruivo do `midcurly` foi substituído pelo ruivo novo, 1.910.232 bytes, que é a
base da correção em pós; o de 11/09 está em `raw/_rejected/hair_midcurly_red_v1.png`.

### As outras 31 camadas

Passam o critério: `nose`/`mouth` com 1 blob, `eye`/`brow`/`ear` com 2 blobs
simétricos (desvio do eixo ≤ 12 px, diferença de altura ≤ 6 px, razão de área
≥ 0,88), `hair`/`beard` com 1 blob, todas com ≥ 95% dentro da região do slot.

### Limpeza e saneamento do repositório (10/09/2026)

- **`__pycache__/` saiu do índice** e entrou no `.gitignore` (`__pycache__/`,
  `*.pyc`). O `.pyc` que estava commitado guardava o caminho de origem
  `C:\Users\guilherme.santiago\Downloads\assets\make_tones.py` — ver a lacuna
  registrada abaixo.
- **`raw/preview.webp` apagado.** Era byte a byte idêntico a `raw/skin01.webp`,
  não estava documentado e não era referenciado por nenhum script. Inerte,
  porque os dois geradores exigem prefixo `skin`, mas era duplicata.
- **`raw/tmp_1.png` convertido de RGBA para RGB.** Era o único dos 36 renders de
  `raw/` em RGBA. O alpha era uniformemente 255 (valor único verificado), e o
  RGB saiu **idêntico byte a byte** da conversão. `make_tones.py` já lia esse
  arquivo com `.convert("RGB")` nos dois pontos de uso, então nenhuma medida
  muda: `tones.json` foi regerado depois e saiu igual ao anterior.

### A extração agora está no repositório (11/09/2026)

`scripts/extract-layers.py` implementa a receita da máscara desta seção, mais o
gate de blobs e o de região por slot. Sem argumentos ele valida e não escreve;
com `--write` escreve em `layers/`; com `--regress` compara byte a byte contra o
que já está commitado.

**A receita documentada reproduz as 32 camadas byte a byte, `beard_stubble`
incluída.** Escrito do zero a partir da descrição, o código reproduz o artefato.
Isso valida o texto da receita, não só o código, e mostra que `layers/` é de uma
geração só.

Quatro detalhes que a descrição em prosa não fixava, e que a regressão fixou:

- **O blur é o do Pillow, não o do scipy.** `ImageFilter.GaussianBlur(1.5)` usa
  três passadas de box blur; o kernel exato do scipy difere em até 4 níveis de
  alpha, o bastante para nenhuma camada bater byte a byte.
- **O diff é em escala de cinza, e o limiar é estrito.** Testadas as variantes
  `>= 16`, máximo por canal e média por canal: só `cinza > 16` reproduz.
- **A mediana usa `mode="nearest"`.** Com o `reflect` padrão do scipy, a borda
  espelha conteúdo e desloca o limiar nas primeiras linhas do quadro.
- **A morfologia é a do skimage, não a do scipy.** A do scipy trata o fora do
  quadro como fundo e erode a partir da borda.

Os dois últimos só aparecem em cabelo que toca o topo do canvas. Sem eles,
`midcurly`, `longtied`, `slickback` e `straightpart` perdiam uma faixa de cerca
de 10 linhas no topo, e `braids` e `lowfade` erravam por 87 e 89 px. Levaram a
uma conclusão errada antes de serem encontrados: a de que `layers/` misturava
duas gerações e as seis precisavam ser reextraídas. **Não precisavam. O erro era
da implementação, não do asset**, e a reextração teria sobrescrito seis camadas
boas por seis piores.

### O gate de região não contém as camadas aprovadas

Rodando o gate contra as 32 já aprovadas, três estouram a caixa do NOTES, todas
por baixo e por pouco:

| camada | px fora | onde | caixa |
|---|---|---|---|
| `beard_longfull` | 2.433 | y 1140–1161 | y1 = 1140 |
| `mouth_thin` | 677 | y 850–861 | y1 = 850 |
| `mouth_full` | 57 | y 850–851 | y1 = 850 |

São camadas aprovadas, então quem está errado é a caixa, não o asset.
**Corrigidas em 11/09/2026: `beard` de y1 1140 para 1165, `mouth` de y1 850 para
865.** Os assets não foram tocados. Com as caixas novas as 32 aprovadas passam o
gate de região.

### A caixa de `hair`, alargada

De `(.10, .00, .90, .75)` para **`(.10, .00, .90, .80)`** em 11/09/2026. Medido
sobre os 24 renders novos, o alargamento é necessário em **3 deles**, e **só no
eixo y**: as três tranças passam de `y` 0,75, chegando a 0,781 no
`hair_braids_red`. O eixo `x` fica como estava: o mínimo dos 24 é 0,121 e o
máximo 0,869, ambos no `hair_midcurly_red`, e os dois dentro de 0,10 e 0,90.
Alargar `x` também chegou a ser feito e foi revertido, por não ter nada que o
justificasse.

`hair_braids_red` a 0,781 deixa pouca margem contra o novo teto de 0,80.

### Lacuna conhecida: a extração não está no repositório

A receita da máscara está especificada neste arquivo, mas **nenhum `.py` do
repositório a implementa.** `make_tones.py` e `make_build.py` consomem
`layers/`; nada a produz. As 32 camadas em `layers/` não são reproduzíveis a
partir do que está versionado.

É a mesma lacuna que existia na folha de contato do build, e que
`contact_sheet()` fechou. Enquanto o extrator não estiver aqui, `layers/` é
**fonte primária, não derivada** — o que é mais uma razão para ela não sair do
repositório.

## Nota de processo: medição que decide entra aqui na mesma sessão

**Três medições desta semana morreram sem registro.** Não foram perdidas por
acidente de máquina — foram feitas, usaram-se para decidir, e não entraram neste
arquivo:

| medição | o que decidia | como acabou |
|---|---|---|
| flood de RGB, raios 2 / 4 / 8 / 16 | o `FLOOD_RADIUS` do build | perdida inteira; sobrou só a lembrança de "raio 4", sem número que a sustentasse. O código seguiu em 16 |
| dano por tom das camadas de PELO | se valia gerar 85 arquivos por tom | refeita do zero em 10/09/2026 |
| tint de PELO, seis cores | metade da paleta | refeita do zero em 10/09/2026; os números não reconciliam com os da original |

O custo não é o retrabalho, é pior: **na terceira, os números não bateram.** A
medição original dava "6–19%, perda até 214"; a refeita deu "5–20%, picos de
238". Mesma ordem, valores diferentes, e sem registro não há como saber qual
está certa nem por que divergem. Uma decisão tomada sobre a primeira não é
auditável hoje.

**Regra: medição que decide alguma coisa entra no NOTES na mesma sessão em que
foi feita**, com os números, a definição de cada grandeza e o critério de
aceitação. Não no fim do dia, não no commit seguinte, não "quando estabilizar" —
uma medição que só existe na transcrição de uma sessão já está perdida.

O sintoma de que isso está acontecendo de novo é fácil de reconhecer: alguém
citando um resultado de memória, com o número redondo e sem a definição junto.

## A mancha em tom escuro é da máscara de PELO, não de `w` (15/09/2026)

Achado no criador do jogo: em MST-10 o rosto grátis (`hair_buzz`, `brow_medium`,
`beard_stubble`) mostra manchas claras de contorno geográfico na testa, nas
bochechas e no queixo, em área sem pelo nenhum. A réplica em Python de `tone.ts`
bate com o canvas do jogo pixel a pixel, então não é defeito de porta. **`w` não
foi tocado em nenhuma medição abaixo.**

**A fração de pelo opaco não separa dois grupos.** `r < 0,15` no miolo
(`alpha > 200`, dentro da silhueta), resolução cheia: rampa contínua de 74% a 0%
(cabelos 59–74%, `hair_braids` 42, `hair_buzz` 25, `beard_mustache` 25,
`beard_goatee` 15, `beard_shortfull` 15, `brow_thick` 9,6, `beard_chinstrap` 4,7,
`brow_medium` 2,7, `brow_thin` 0,4, `beard_stubble` 0,0). Fora da stubble, o maior
salto entre vizinhos é de 6×. O eixo não é "quanto pelo tem", é "quanta pele a
máscara pegou".

**Pele a mais de 20 px do pelo opaco mais próximo** (build 512): `beard_stubble`
100% do miolo (não tem pelo opaco), `brow_thin` 100%, `brow_medium` 65,6%,
`beard_chinstrap` 46,6%, `hair_buzz` 12,6%, `beard_shortfull` 8,4%; os cabelos
longos e cacheados ficam em 0–1,6%.

**Coincide com as manchas.** No rosto grátis em MST-10, 75,6% do erro (composto
clareando a base em mais de 10 níveis de L) cai no miolo distante, 19,1% no miolo
perto do pelo e 5,3% fora do miolo de PELO. Por camada, o miolo distante está
quase todo errado (66,7% no buzz, 99,5–99,7% em stubble e sobrancelhas).

**Remover do alpha a pele quase pura (`r > 0,85`) não resolve: 1,3% a menos de
erro.** Essa pele é só 0–1,9% do miolo. A pele distante não é pele do `tmp_1`
copiada: tem `r` mediano de 0,55 (`hair_buzz`), 0,42 (`brow_medium`) e 0,66
(`beard_stubble`), ou seja, é pele **mais escura** que a do `tmp_1` naquele pixel.
Um corte por `r` não a separa do pelo semitransparente, que vive na mesma faixa;
é a hipótese 1 da cadeia de PELO de novo. O que distingue essa pele é a
**geometria** (distância ao pelo), não o valor.

**Não resolvido nesta data.** O problema é a extração incluindo região que
deveria ser transparente. Para a stubble e as sobrancelhas o critério de
distância ao pelo opaco não se aplica, porque elas não têm núcleo opaco.

**Tempo do criador, registrado e encerrado:** carga fria, primeiro rosto em
1685 ms desde a navegação, ~790 ms da tela; anúncios terminam aos 3256 ms, depois
do rosto.

### Grupo A (corte de distância) e grupo B (w = 1): o gate grátis não fecha (15/09/2026)

Medido com `scripts/medicao/medir_grupos.py`, sem implementar. Erro = composto
clareando a base em mais de 10 níveis de L, em MST-10.

**Grupo B com w = 1 funciona.** `beard_stubble`, `brow_thin`, `brow_medium`: no
rosto grátis o erro cai **76,3%** só com B, e a mancha da barba e das sobrancelhas
some; em MST-01 a textura fica.

**Grupo A com corte > 20 px quase não mexe no que se vê.** Camada sozinha:
`hair_buzz` −24,6%, `beard_chinstrap` −44,6%, `beard_shortfull` −10,5%. A faixa de
testa do buzz vai de 6.008 para 4.408 px: o que sobra é um halo **a menos de 20 px
do pelo**, que o corte por definição não alcança.

**Rosto grátis, MST-10:** hoje 28.773 px; só A 27.173 (−5,6%); só B 6.826
(−76,3%); **A + B 5.226 (−81,8%)**. Do resto, 4.827 px estão no miolo do buzz, na
linha do cabelo. **O gate não passa.**

**O corte cria regressão em tom claro.** Em MST-01, A + B muda mais de 10 níveis
em 4,75% da silhueta, e o contorno do corte aparece como degrau na testa: a pele
da camada, que ali era a certa, dá lugar à base.

**Camadas do meio:** o corte quase não muda o erro (`beard_goatee` 8.351 → 7.998,
`hair_lowfade` 2.943 → 2.635, `beard_mustache` 2.892 → 2.892, `brow_thick`
4.543 → 4.398). O que se vê é o mesmo halo alaranjado junto ao pelo do buzz.

**w = 1 zera o erro em qualquer camada, e por isso "erro 0" não prova nada em
camada com pelo opaco:** o pelo opaco escurece 23 a 42 níveis
(`hair_lowfade` 23, `beard_chinstrap` 32, `beard_goatee` 37, `brow_thick` 39).
O critério precisa de uma segunda régua, a cor do pelo, que esta medição não
decide.

**O limiar de "tem núcleo" não se confirma.** O salto 9,6% → 4,7% (`brow_thick`
→ `beard_chinstrap`) é de 2×; no build de 512 a rampa é 10,1 / 4,3 / 1,3 / 0,24 /
0,00, sem corte limpo, e as camadas dos dois lados se comportam igual diante do
corte.

**Aberto:** o halo a menos de 20 px do pelo, que aparece no buzz e nas camadas do
meio.

### O halo junto ao pelo não é o fechamento da extração (15/09/2026)

Medido com `scripts/medicao/medir_morfologia.py`, sem implementar. A reextração
passa pelo mesmo caminho do build (Lanczos, flood, WebP q88 alpha 100) e, com a
receita, reproduz `build/layers/hair_buzz.webp` e `beard_goatee.webp` com
diferença zero.

**A espessura não é constante.** Distância de cada pixel de erro do `hair_buzz`
(sozinho, MST-10, w = r) ao pelo opaco: platô de 0 a 20 px em 512, p25 7,2,
p50 13,5, p75 19,9, IQR 12,7; a faixa mais cheia tem só 8,6% dos pixels. À borda
externa da máscara: p25 6,0, p50 10,4, p75 16,0, IQR 10,0. É cauda, não pico. O
fechamento `disk(6)` em 1254 vale 2,45 px em 512 e não gera uma faixa de 13 px.

**Fechamento menor não muda o halo.** `hair_buzz`: erro 6.513 (disk 6) →
6.479 (disk 2) → 6.473 (disk 0); rosto grátis com o grupo B em w = 1: 6.826 →
6.792 → 6.786. Gate de blobs passa nos três; cobertura cai só 213 px.

**Nas outras camadas, idem.** Queda de erro com disk(0), sozinha em MST-10:
`beard_goatee` 0,5%, `hair_lowfade` 1,5%, `beard_mustache` −0,4%, `brow_thick`
0,4%, `hair_midcurly` 1,3%, `beard_longfull` 0,6%. Todas passam o gate de blobs
com disk(2) e disk(0). O fechamento de fato tapa buracos internos em
`beard_goatee` (8.865 px) e `hair_midcurly` (921 px), e sem ele eles voltam como
buracos.

**Conclusão:** o halo é **cobertura** — o próprio limiar de diferença pega pele
em que o render com pelo difere do `tmp_1` numa faixa larga junto ao pelo — e
não morfologia. Grupo B (w = 1 em `beard_stubble`, `brow_thin`, `brow_medium`)
continua valendo. O corte de distância está abandonado. **O halo segue aberto.**

### Render de referência: o gerador sobre a base escura (15/09/2026)

Restrição relaxada por decisão do Santiago: **um** render de verdade, não asset.
`hair_buzz` sobre `raw/tmp_4.png`, que é MST-10 no canvas de 1254 (k tmp_4/tmp_1
= 0,1299/0,1515/0,1771, igual ao `tones.json`; IoU de silhueta 0,9941 contra
`tmp_1`). Feito no ChatGPT web (gpt-image, C2PA "OpenAI Media Service API"), com
duas imagens de entrada: `tmp_4.png` a editar e `raw/hair_buzz.png` como o corte a
copiar. Prompt, entradas e origem em `raw/_referencia/hair_buzz_tmp4_chatgpt_1.json`;
o PNG (1254×1254, 1,8 MB) está em `raw/_referencia/`. Comparador:
`scripts/medicao/comparar_referencia.py`; gerador por API, para repetir:
`scripts/medicao/gerar_referencia.py`.

**A geometria não é a mesma** (IoU de silhueta 0,9666 contra `tmp_4`; testa da
referência 6% mais clara que `tmp_4` na mediana, com espalhamento 0,75–1,45 pixel
a pixel). Por isso nada abaixo é pixel a pixel: são medianas por região anatômica,
definidas UMA vez pela camada nativa, e perfis verticais pela testa.

**Razão de luminância à base, `Y(img)/Y(tmp_4)`, p10/p50/p90:**

| imagem | testa nua (controle) | banda (0,15 ≤ r < 0,85) | núcleo (r < 0,15) | L núcleo | L banda |
|---|---|---|---|---|---|
| **referência** | 0,75/**1,06**/1,45 | 0,25/**0,62**/1,23 | 0,14/**0,29**/0,55 | **37,3** | **57,5** |
| nativo (w = 0) | 1,00 | 0,76/1,82/4,88 | 0,26/0,60/1,03 | 53,2 | 101,7 |
| w = r (hoje) | 1,00 | 0,63/1,35/2,45 | 0,25/0,54/0,91 | 50,7 | 84,4 |
| w = 1 | 1,00 | 0,17/0,29/0,61 | 0,05/0,09/0,13 | 17,3 | 42,6 |

**Perfil vertical pelas colunas centrais** (razão à base, y em px de 1254):

| y | 80 | 120 | 160 | 200 | 220 | 300 |
|---|---|---|---|---|---|---|
| referência | 0,40 | 0,46 | 0,36 | 0,52 | 1,05 | 1,09 |
| w = r | 0,82 | 0,90 | 0,87 | 1,03 | 1,00 | 1,00 |
| w = 1 | 0,14 | 0,22 | 0,27 | 0,61 | 1,00 | 1,00 |

**O que a referência decide:**

- **Não existe faixa clara.** Na referência a calota inteira fica **abaixo** da
  base (0,36–0,52) e a testa volta a ~1,05 em 20 px. A faixa branca da linha do
  cabelo em `w = r` (ratio 0,9–1,0 onde deveria ser 0,4–0,5) é erro do modelo,
  não do gerador.
- **Na banda, `w = 1` acerta:** 0,34/0,61 contra 0,36/0,52 da referência em
  y = 180–200. Pele transmitida é o modelo certo perto da linha do cabelo,
  como já era para stubble e sobrancelhas.
- **No núcleo, `w = 1` erra por escuro e o nativo erra por claro.** Referência
  L 37,3; `w = 1` 17,3; nativo 53,2. Em luz linear: referência 0,29 da base,
  `w = 1` 0,09, nativo 0,60. Resolvendo `L = E + T·S` e `ref = E + T·B` com
  `B/S = 0,15`: **T = 0,055 e E = 0,235·B, ou seja, 39% da luminância do pixel
  nativo do núcleo é emissão própria do pelo (fica), e 61% é pele transmitida
  (escala com a base).** `w = r` põe T = r² ≈ 0,008 (quase tudo fica, por isso
  claro demais); `w = 1` põe E = 0 (escuro demais).
- Em `hair_buzz` a "cor do cabelo" que se vê **depende do tom**, porque a
  calota de máquina é pelo esparso sobre couro cabeludo. A regra "cor do pelo é
  dado" vale para a emissão E, não para o pixel inteiro.

Ressalvas: um render só, sem medida de variância do gerador; e a referência é o
que o gerador faz, não física. Foi adotada como verdade por decisão.

### Correção do briefing: "cor do pelo é dado" vale para E, não para o pixel (15/09/2026)

A restrição "cor do pelo é dado, não derivado do tom; loiro sobre pele escura
continua loiro" estava errada como escrita, e teria bloqueado a solução certa.
Vale para a **emissão própria do pelo E**. O pixel de pelo esparso (máquina,
barba por fazer, sobrancelha) é `E + T·base` e **depende do tom por
construção**: a referência mostra o núcleo da máquina a 0,27 da base em MST-10,
contra 0,60 se a cor nativa fosse mantida. Dito de outro modo: `w = r` estava
protegendo a coisa errada.

### {E, T} por pixel a partir de dois renders (15/09/2026)

Modelo: `L1 = E + T·S` (render sobre `tmp_1`) e `L4 = E + T·B` (render sobre
`tmp_4`), duas equações por pixel e por canal, `T = (L1 − L4)/(S − B)`,
`E = L1 − T·S`. Sem limiar, sem classificar, sem parâmetro. Script:
`scripts/medicao/medir_ET.py`. Duas referências do buzz, mesmo prompt
(`raw/_referencia/hair_buzz_tmp4_chatgpt_{1,2}.png`).

**Fecha onde tem que fechar.** Testa nua (controle): T 0,97–0,99, E ≈ 0,01·L1.
T em [0,1] em 99% do pelo em qualquer granularidade. Núcleo (r < 0,15):
T ≈ 0,09 e **E/L1 = 0,33 / 0,49 / 0,68 por canal R/G/B** (ref 1): a emissão do
pelo é mais neutra que a pele. Banda: T ≈ 0,26, E/L1 0,14 / 0,20 / 0,28.

**Não fecha em 8–10% do pelo (E < 0), e é geometria, não ruído.** 91% desses
pixels estão na banda; a fração não cai com blocos maiores (b = 1 → 64:
10,1 / 8,7 / 7,8 / 8,7 / 10,4 / 12,6 / 5,6%). Espacialmente é um blob
compacto no centro da linha do cabelo, onde o render nativo tem uma ponta
(pelo) e as referências têm a linha reta (pele). A máscara relativa
(`Y/Y(base) < 0,7`) tem IoU 0,54 entre nativo e ref 1, com a linha do cabelo
nas colunas centrais em y = 200 no nativo e 201–202 nas refs: a linha bate, a
densidade ao longo dela não.

**Granularidade.** As medianas regionais de T e E/L1 são estáveis de b = 2 a
b = 16 (|ΔT| entre escalas 0,02–0,03); a textura de fio some acima de b = 2
(reconstrução da referência: rms 1,9 níveis em b = 1, 10,5 em b = 2, 14 em
b = 8). **Por pixel, {E, T} de dois renders desalinhados não serve de asset;
por região, serve de calibração.**

**Variância do gerador, com duas referências.** Ganho global de pele, medido
na testa nua: ref 1 **1,07** (R 1,072 / G 1,055 / B 1,067), ref 2 **0,91**
(0,937 / 0,888 / 0,880). É deriva de exposição, não pelo, e contamina T
diretamente (ref 2 sem normalizar: E < 0 em 15–16%). **Cada referência é
dividida pelo próprio ganho de controle** antes de qualquer conta (região
sem pelo, mesmo render, por canal: contexto idêntico). Normalizadas, as duas
concordam: banda 0,58 / 0,54, núcleo 0,27 / 0,25 da base. Entre si: IoU de
silhueta 0,9964, IoU da máscara relativa 0,73, |Δrazão| em blocos de 8 px
mediana 0,083 (sem normalizar).

### Regra candidata: w(r) por tabela medida, aplicada por pixel (15/09/2026)

`novo = L − w(r)·r·(S − B)`, com `w(r)` = mediana de `T/r` por faixa de `r`,
por canal, resolvida em blocos de 8 px da referência normalizada. A aplicação
é por pixel sobre o render nativo, alinhado por construção; interpolação
linear entre centros de faixa. **Nenhuma constante escolhida**: a tabela é
medição. Script: `scripts/medicao/medir_w_de_r.py`.

| r | w(r) canal R, ref 1 | ref 2 |
|---|---|---|
| < 0,10 | 0,67 | 0,75 |
| 0,10–0,15 | 0,76 | 0,78 |
| 0,15–0,20 | 0,80 | 0,81 |
| 0,20–0,30 | 0,84 | 0,86 |
| 0,30–0,40 | 0,87 | 0,90 |
| 0,40–0,50 | 0,90 | 0,91 |
| 0,50–0,70 | 0,92–0,94 | 0,93–0,94 |
| 0,70–0,90 | 0,95–0,96 | 0,95 |

Monótona, com quartis a ±0,04, e menor nos canais G e B (núcleo: 0,67 / 0,57 /
0,43 em R/G/B). `w = r` põe 0,10 no núcleo e 0,30 na banda; `w = 1` põe 1. A
verdade está perto de 1 e desce devagar com a densidade do pelo.

**Validação cruzada** (calibra numa referência, testa na outra, ambas
normalizadas):

| | banda p50 | núcleo p50 | L núcleo |
|---|---|---|---|
| ref 1* / ref 2* | 0,58 / 0,54 | 0,27 / 0,25 | 36,0 / 34,2 |
| tabela da ref 1 | 0,60 | 0,26 | 33,7 |
| tabela da ref 2 | 0,57 | 0,24 | 32,3 |
| `w = r` (hoje) | 1,36 | 0,54 | 50,7 |
| `w = 1` | 0,29 | 0,09 | 17,3 |

O erro fora da amostra (0,03–0,06 na razão) é do tamanho da diferença entre as
duas referências (0,02–0,04). Identidade sobre `tmp_1`: 0.

**Gate em 512** (rosto grátis MST-10, `w = 1` em stubble e brow_medium, `w(r)`
no buzz): mancha **6.826 → 313 px**. MST-05 e MST-01: 72 → 72 e 89 → 89,
|ΔL| > 10 em 0,4–0,7% da silhueta contra hoje, ou seja, o tom claro não muda.

**O que a regra não alcança:** as linhas y = 160–200 do perfil (0,44 / 0,75
contra 0,33 / 0,49 das referências). Ali o render nativo tem r ≈ 0,8 (quase
pele) e as referências têm linha do cabelo densa: o gerador desenhou o cabelo
mais baixo e mais denso na cabeça escura. Regra nenhuma aplicada ao nativo
alcança pelo que o nativo não tem.

**Duas hipóteses de um render só, medidas e mortas.** `plano_croma`
(L = α·Ĥ + β·S, NNLS) e `cobertura_sombra` (L = a·H + (1−a)·s·S): pelo e pele
**têm a mesma cromaticidade** nesta batelada (pelo escuro fora da silhueta a
4,6–8,3° da direção da pele; núcleo a 3,5–12,8°; loiro a 3,5–5,0°; pele contra
branco 25,5°), então nenhuma decomposição por cor separa cobertura de sombra —
o solver decide pelo ruído. Contra a referência, as duas caem entre `w = r` e
`w = 1` (núcleo L 30,8 e 25,3 contra 37,3) e deixam a linha do cabelo clara. É
o que fecha a porta do render único: **a segunda equação precisa vir de um
segundo render.** `escala`, `piso_pelo` e `diagnostico` não rodaram (limite de
gasto de agentes).

**O que falta medir, e o custo:** stubble (E deve dar ≈ 0: aí `w = 1` deixa
de ser lista e vira consequência) e um cabelo volumoso (T ≈ 0 no núcleo: aí o
loiro sobrevive por construção). Cada camada custa um render no ChatGPT:
medido hoje, 5–8 min por camada dirigindo o navegador (geração 60–90 s,
download pelo visualizador, cópia) mais ~1 min de conta; 17 camadas ≈ 2 h,
mais ~14% de reenvios. Se o modelo fechar nas três famílias, a correção é
reextrair as 17 de PELO como {E, T} por região ou como tabela `w(r)` por
camada, e o runtime vira uma multiplicação e uma soma.
