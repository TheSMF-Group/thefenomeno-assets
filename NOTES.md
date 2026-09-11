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
com 577,6 KB. Não há outra cópia dos renders nem das camadas: `layers/` é a
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
| bases | 10 | 144,2 KB |
| camadas | 32 | 433,3 KB |
| **build** | 42 | **577,6 KB** |

Maiores camadas: `hair_midcurly` e `hair_braids` em torno de 31 KB,
`beard_longfull` 23 KB. Menores: `mouth_thin` 3,9 KB, `brow_thin` 4,3 KB.

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

**Raio: 16 px.** Cobre 100% dos transparentes até 16 px da máscara, o que atende
os primeiros níveis de mipmap (até 32×32). Flood sem limite não acrescenta
segurança útil e custa quase o triplo, porque preto chapado comprime para quase
nada e área com cor não:

| variante | camadas | acréscimo |
|---|---|---|
| sem flood | 347,6 KB | — |
| **raio 16** | **433,3 KB** | +25% |
| flood total | 590,1 KB | +70% |

### O flood muda o composto, e o motivo não é a composição

Esperava-se composto idêntico, já que pixel transparente tem peso zero. **Não
é.** Diferença média de 0,05 nível e máxima de 25, maior nos tons claros.

A causa é o **codec**, não a composição. WebP com perdas trabalha em blocos:
mudar o RGB dos pixels transparentes muda o conteúdo do bloco e, com ele, a
reconstrução dos pixels **opacos** do mesmo bloco. Peso zero na composição não
é peso zero na compressão.

A mudança é uma **melhora marginal**, medida contra a camada de 512 sem
compressão nenhuma:

| versão | erro no miolo | erro na rampa da borda |
|---|---|---|
| sem flood | 2,758 | 1,731 |
| com flood r16 | **2,691** | **1,653** |

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

**Este é o terceiro caso da mesma família neste arquivo, e vale nomeá-la:
critério calibrado numa população não transfere para outra só porque a fórmula
roda.** Os outros dois:

- **O alvo de −37 em sRGB**, aposentado em favor da razão de luminância linear:
  −37 sobre pele clara é −9 sobre pele escura, e a fórmula não avisa.
- **O teto em p90 do `measuredHex`**, que existe porque acima dele entra reflexo
  especular, que tem a cor da luz e não do pigmento.

Junto com o `r < 0,15` para pelo opaco, que é critério de escuridão disfarçado
de critério de opacidade, são quatro. O padrão a reconhecer é sempre o mesmo: a
definição foi escrita olhando um caso, e o caso novo difere na variável que a
definição não menciona.

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

#### Modo de falha do gerador, para a próxima batelada

**Resposta vazia em cerca de 14% dos envios, sem erro.** O gerador não sinaliza
falha: devolve vazio e segue. Resolvido por reenvio simples, sem mudar o prompt
nem os parâmetros.

Consequência operacional: uma batelada de N itens exige aproximadamente 1,16 × N
envios, e **a contagem de arquivos na pasta é o único sinal de que a batelada
terminou**. Conferir a contagem esperada antes de considerar a batelada completa,
em vez de assumir que ausência de erro significa sucesso.

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
