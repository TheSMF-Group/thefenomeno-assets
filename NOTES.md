# assets — cabeças de manequim, camadas de feição

## Estrutura de pastas

| pasta | conteúdo |
|---|---|
| `raw/` | **output de gerador.** Os 32 renders de feição + as 4 bases `tmp_*`. Um arquivo por camada, mesmo nome da camada. |
| `raw/_rejected/` | renders substituídos, guardados para rastreio |
| `layers/` | as 32 camadas extraídas, RGBA com a máscara no alpha |
| `layers/_rejected/` | camadas substituídas, guardadas para rastreio |
| `build/` | **o que vai para o jogo.** 512, WebP. Gerado por `make_build.py` |
| raiz | `tones.json`, `tone.ts`, os geradores, `NOTES.md` e saídas de teste (`gate_*.png`) |

`raw/` e `layers/` são o material de trabalho e não são consumidos pelo jogo.
Só `build/` é.

**Regra: output de gerador vai para `raw/`, nunca para `layers/`.**
`layers/` só recebe arquivo produzido pela extração. Um render salvo dentro de
`layers/` sobrescreve silenciosamente a camada de mesmo nome — foi o que
aconteceu em 09/09/2026 com `beard_stubble`.

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
e ~510 MB de PNG, contra 51 MB das 32 atuais.

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
todas do lado escuro dessa curva, onde cair é o esperado. **Só dá para julgar
isso de verdade com as dez bases reais.**

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
