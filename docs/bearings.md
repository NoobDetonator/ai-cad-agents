# Rolamentos

Cinco ferramentas especializadas criam geometrias convencionais e adaptadas à
impressão 3D. Todas usam o `ToolRegistry`, transações e `cad.undo`.

## Catálogo

| Ferramenta | Resultado |
| --- | --- |
| `cad.create_deep_groove_ball_bearing` | rolamento rígido de esferas com pistas e gaiola opcional |
| `cad.create_thrust_ball_bearing` | rolamento axial de uma direção |
| `cad.create_cylindrical_roller_bearing` | rolamento radial de rolos cilíndricos |
| `cad.create_print_in_place_roller_bearing` | rolamento capturado para impressão em uma operação |
| `cad.create_printed_plain_bushing` | bucha polimérica com folga, canais e alívio de primeira camada |

## Regras principais

- `groove_conformity` controla a relação entre canal e esfera;
- quantidade e tamanho dos elementos são validados contra sobreposição;
- folgas são valores geométricos explícitos, não classes C1–C5;
- o modelo axial não deve ser usado como suporte radial;
- `print_clearance` e `axial_clearance` dependem de material, processo e máquina;
- peças print-in-place devem esfriar, ser limpas e liberadas manualmente.

## Limites

Os resultados são modelos conceituais. O sistema não calcula vida L10, contato de
Hertz, deflexão, aquecimento, lubrificação, ajuste ISO, contração ou resistência
entre camadas. Componentes impressos devem ser tratados como protótipos de baixa
carga até ensaio real.

## Referências técnicas

- [SKF — princípios de rolamentos](https://cdn.skfmediahub.skf.com/api/public/0901d196807026e8/pdf_preview_medium/0901d196807026e8_pdf_preview_medium.pdf)
- [SKF — rolamento rígido 6206-RZ](https://www.skf.com/rs/products/rolling-bearings/ball-bearings/deep-groove-ball-bearings/productid-6206-RZ)
- [SKF — rolamento de rolos NJ 1011 ECP](https://www.skf.com/id/products/rolling-bearings/roller-bearings/cylindrical-roller-bearings/single-row-cylindrical-roller-bearings/productid-NJ%201011%20ECP?failover=true)
- [FDM de rolamentos sem montagem](https://doi.org/10.1016/j.promfg.2018.07.102)
- [Análise de tolerância em mecanismos FDM](https://doi.org/10.3390/app11041860)

## Teste

`tests/freecad_bearings_smoke.py` cria os cinco modelos no FreeCAD real, valida
BReps, interferências internas, propriedades, orientação e undo. Marcador:
`FREECAD_BEARINGS_SMOKE_OK`.
