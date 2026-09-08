# Planejamento GIRO 2026 (Janeiro a Agosto)

Gerado automaticamente pelo script `scripts_pipeline/gerar_planejamento_giro_2026.py`.

## Regras de Negócio
- **Frequência:** Semanal (Quartas-feiras)
- **Janela de Coleta:** 4 a 6 dias anteriores ao programa
- **Mínimo de Boletins:** 4 (programa é descartado se < 4)
- **Corte:** Por silêncio de 1.0s (sem vinheta)
- **Fallback:** Desabilitado (regra rígida: ou corta ou falha)

## Programas Gerados: 34

### Janeiro (4 programas)
| Código | Data Exibição | Período Coleta | Dias | Arquivo JSON |
|--------|---------------|----------------|------|--------------|
| 0101 | 07/01/2026 | 02/01 - 07/01 | 6 | giro_0101.json |
| 0102 | 14/01/2026 | 09/01 - 14/01 | 6 | giro_0102.json |
| 0103 | 21/01/2026 | 16/01 - 21/01 | 6 | giro_0103.json |
| 0104 | 28/01/2026 | 23/01 - 28/01 | 6 | giro_0104.json |

### Fevereiro (4 programas)
| Código | Data Exibição | Período Coleta | Dias | Arquivo JSON |
|--------|---------------|----------------|------|--------------|
| 0201 | 04/02/2026 | 30/01 - 04/02 | 6 | giro_0201.json |
| 0202 | 11/02/2026 | 06/02 - 11/02 | 6 | giro_0202.json |
| 0203 | 18/02/2026 | 13/02 - 18/02 | 6 | giro_0203.json |
| 0204 | 25/02/2026 | 20/02 - 25/02 | 6 | giro_0204.json |

### Março (4 programas)
| Código | Data Exibição | Período Coleta | Dias | Arquivo JSON |
|--------|---------------|----------------|------|--------------|
| 0301 | 04/03/2026 | 27/02 - 04/03 | 6 | giro_0301.json |
| 0302 | 11/03/2026 | 06/03 - 11/03 | 6 | giro_0302.json |
| 0303 | 18/03/2026 | 13/03 - 18/03 | 6 | giro_0303.json |
| 0304 | 25/03/2026 | 20/03 - 25/03 | 6 | giro_0304.json |

### Abril (5 programas)
| Código | Data Exibição | Período Coleta | Dias | Arquivo JSON |
|--------|---------------|----------------|------|--------------|
| 0401 | 01/04/2026 | 27/03 - 01/04 | 6 | giro_0401.json |
| 0402 | 08/04/2026 | 03/04 - 08/04 | 6 | giro_0402.json |
| 0403 | 15/04/2026 | 10/04 - 15/04 | 6 | giro_0403.json |
| 0404 | 22/04/2026 | 17/04 - 22/04 | 6 | giro_0404.json |
| 0405 | 29/04/2026 | 24/04 - 29/04 | 6 | giro_0405.json |

### Maio (4 programas)
| Código | Data Exibição | Período Coleta | Dias | Arquivo JSON |
|--------|---------------|----------------|------|--------------|
| 0501 | 06/05/2026 | 01/05 - 06/05 | 6 | giro_0501.json |
| 0502 | 13/05/2026 | 08/05 - 13/05 | 6 | giro_0502.json |
| 0503 | 20/05/2026 | 15/05 - 20/05 | 6 | giro_0503.json |
| 0504 | 27/05/2026 | 22/05 - 27/05 | 6 | giro_0504.json |

### Junho (4 programas)
| Código | Data Exibição | Período Coleta | Dias | Arquivo JSON |
|--------|---------------|----------------|------|--------------|
| 0601 | 03/06/2026 | 29/05 - 03/06 | 6 | giro_0601.json |
| 0602 | 10/06/2026 | 05/06 - 10/06 | 6 | giro_0602.json |
| 0603 | 17/06/2026 | 12/06 - 17/06 | 6 | giro_0603.json |
| 0604 | 24/06/2026 | 19/06 - 24/06 | 6 | giro_0604.json |

### Julho (5 programas)
| Código | Data Exibição | Período Coleta | Dias | Arquivo JSON |
|--------|---------------|----------------|------|--------------|
| 0701 | 01/07/2026 | 26/06 - 01/07 | 6 | giro_0701.json |
| 0702 | 08/07/2026 | 03/07 - 08/07 | 6 | giro_0702.json |
| 0703 | 15/07/2026 | 10/07 - 15/07 | 6 | giro_0703.json |
| 0704 | 22/07/2026 | 17/07 - 22/07 | 6 | giro_0704.json |
| 0705 | 29/07/2026 | 24/07 - 29/07 | 6 | giro_0705.json |

### Agosto (4 programas)
| Código | Data Exibição | Período Coleta | Dias | Arquivo JSON |
|--------|---------------|----------------|------|--------------|
| 0801 | 05/08/2026 | 31/07 - 05/08 | 6 | giro_0801.json |
| 0802 | 12/08/2026 | 07/08 - 12/08 | 6 | giro_0802.json |
| 0803 | 19/08/2026 | 14/08 - 19/08 | 6 | giro_0803.json |
| 0804 | 26/08/2026 | 21/08 - 26/08 | 6 | giro_0804.json |

---

## Como Executar

Use o executor genérico passando o JSON desejado:

```bash
# Exemplo: Executar o primeiro programa de Janeiro
python scripts_pipeline/giro/executor_giro.py config/planejamento_2026/giro_0101.json

# Exemplo: Executar o último programa de Agosto
python scripts_pipeline/giro/executor_giro.py config/planejamento_2026/giro_0804.json
```

## Estrutura de Pastas Esperada

Os arquivos de áudio brutos devem estar organizados por data para que o pipeline os encontre:
```
data_brutos/
├── 2026-01-02/
├── 2026-01-03/
...
└── 2026-08-26/
```

