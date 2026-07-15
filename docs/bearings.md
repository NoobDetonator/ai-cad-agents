# Rolamentos convencionais e para impressão 3D

Este domínio acrescenta geometrias especializadas ao mesmo `ToolRegistry`. Os
schemas e regras de produto não importam FreeCAD; o adaptador BRep fica em
`src/aicad/adapters/freecad/bearings.py`. Toda criação é validada antes de abrir
a transação, recalculada, verificada e reversível por `cad.undo`.

## Base técnica

- Rolamentos rígidos de esferas têm pistas profundas e contínuas, baixo atrito
  e aceitam carga radial e axial nos dois sentidos. A ferramenta representa a
  osculação entre pista e esfera por um canal toroidal de raio controlado por
  `groove_conformity`.
- Rolamentos axiais de esferas são separáveis e destinados a carga axial; o
  modelo de uma direção tem arruela de eixo, conjunto de esferas/gaiola e
  arruela de alojamento. Ele não deve ser interpretado como suporte de carga
  radial.
- Rolamentos de rolos cilíndricos favorecem alta capacidade radial. O modelo
  expõe diâmetro, comprimento, quantidade, folga e gaiola, sem alegar um tipo
  industrial de flange NJ/NUP.
- Folga interna é o deslocamento possível entre os anéis e depende das pistas e
  elementos rolantes. O projeto recebe a folga geométrica em milímetros; ele
  não converte automaticamente classes C1–C5 porque ajuste, temperatura, carga
  e aplicação alteram a seleção.
- Mecanismos impressos sem montagem precisam de folgas relativamente grandes e
  sofrem desvios dependentes de orientação, altura de camada, material e
  máquina. Por isso a ferramenta print-in-place exige folga explícita e não
  promete um valor universal.

Fontes consultadas:

- [SKF — deep groove ball bearing 6206-RZ](https://www.skf.com/rs/products/rolling-bearings/ball-bearings/deep-groove-ball-bearings/productid-6206-RZ)
- [SKF — rolling bearings and thrust-bearing principles](https://cdn.skfmediahub.skf.com/api/public/0901d196807026e8/pdf_preview_medium/0901d196807026e8_pdf_preview_medium.pdf)
- [SKF — cylindrical roller bearing NJ 1011 ECP](https://www.skf.com/id/products/rolling-bearings/roller-bearings/cylindrical-roller-bearings/single-row-cylindrical-roller-bearings/productid-NJ%201011%20ECP?failover=true)
- [SKF — radial internal clearance classes and application factors](https://www.skf.com/binaries/pub12/Images/0901d196804664be-Compilation-of-the-SKF-Pulp-and-Paper-Practices-issues-1-15-11147-EN_tcm_12-264609.pdf)
- [FDM-based printing of full-complement bearings](https://doi.org/10.1016/j.promfg.2018.07.102)
- [Statistical tolerance analysis of FDM non-assembly mechanisms](https://doi.org/10.3390/app11041860)
- [Plastic ball-bearing production by additive manufacturing](https://doi.org/10.1007/s11665-025-10649-0)
- [Vibration damping of FDM metal/polymer sleeve bearings](https://doi.org/10.1177/08927057221094984)

## Ferramentas

### `cad.create_deep_groove_ball_bearing`

Cria dois anéis com canais toroidais, esferas igualmente espaçadas e gaiola
opcional conectada, com dois trilhos axiais e montantes entre as esferas.
`groove_conformity` aceita 1,00 a
1,25; valores maiores criam pista menos conformal. O resultado é um compound
com sólidos separados e metadados de folga, elemento e tipo.

### `cad.create_thrust_ball_bearing`

Cria duas arruelas anulares com canais voltados uma para a outra, esferas no
plano médio e gaiola opcional. A direção registrada é
`axial_z_single_direction`.

### `cad.create_cylindrical_roller_bearing`

Cria anel interno, anel externo, rolos verticais e uma gaiola conectada formada
por dois trilhos e montantes entre os rolos. A
validação usa a distância de corda entre centros, não apenas o comprimento de
arco, para impedir sobreposição dos rolos.

### `cad.create_print_in_place_roller_bearing`

Cria anéis e rolos separados para impressão em uma operação, na orientação
`axis_z_upright`. Aros cônicos de 45 graus reduzem a saliência sem apoio e deixam
a abertura menor que o diâmetro dos rolos, mantendo-os capturados. A folga
`print_clearance` é aplicada em cada lado radial; `axial_clearance` separa os
roletes dos aros. A peça deve esfriar, ser limpa e liberada por rotação manual.

### `cad.create_printed_plain_bushing`

Cria uma bucha de deslizamento para polímero com diâmetro de funcionamento igual
a `shaft_diameter + running_clearance`. Canais axiais opcionais reduzem a área de
contato e oferecem caminho para lubrificante ou detritos. A primeira faixa do
furo recebe `elephant_foot_relief` para compensar o alargamento externo comum
nas primeiras camadas.

## Limites de engenharia

Os objetos são modelos CAD conceituais. O sistema ainda não calcula vida L10,
pressão de contato de Hertz, deflexão, velocidade limite, aquecimento,
lubrificação, ajuste eixo/alojamento, tolerância ISO, contração do polímero ou
resistência entre camadas. Um rolamento impresso deve ser tratado como protótipo
de baixa carga até ser ensaiado no material, orientação e impressora reais.

## Testes

`tests/freecad_bearings_smoke.py` cria os cinco tipos no FreeCAD real, valida
cada BRep e compara todos os sólidos internos para garantir que o volume comum
não ultrapassa a tolerância. Também confere propriedades, orientação e undo. O
marcador esperado é `FREECAD_BEARINGS_SMOKE_OK`.
