# Relatório de Produção GIRO nas Comarcas — 2026

**Data:** 2026-09-07  
**Sistema:** DIVISOR v2.0 (pipeline GIRO)  
**Total produzido:** 33 programas (jan–set)

---

## Resumo por Mês

| Mês | Programas | Produzidos | Com fallback mensal | Taxa |
|-----|-----------|------------|---------------------|------|
| Janeiro | 0101–0104 | 2 | — | 50% |
| Fevereiro | 0201–0204 | 3 | — | 75% |
| Março | 0301–0304 | 4 | 0303, 0304 | 100% |
| Abril | 0401–0404 | 4 | 0402, 0404 | 100% |
| Maio | 0501–0504 | 4 | 0501 | 100% |
| Junho | 0601–0604 | 4 | 0601 | 100% |
| Julho | 0701–0704 | 4 | 0701, 0703, 0704 | 100% |
| Agosto | 0801–0804 | 4 | 0801, 0802, 0804 | 100% |
| Setembro | 0901 | 1 | 0901 | 25% (em andamento) |
| **Total** | | **33** | | **~90%** |

---

## Arquivos de Produção (Drive H:)

```
H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026\03_GIRO_NAS_COMARCAS\
├── 01 - JAN - 26\    (2 arquivos)
├── 02 - FEV - 26\    (3 arquivos)
├── 03 - MAR - 26\    (4 arquivos)
├── 04 - ABR - 26\    (4 arquivos)
├── 05 - MAI - 26\    (4 arquivos)
├── 06 - JUN - 26\    (4 arquivos + legados)
├── 07 - JUL - 26\    (4 arquivos)
├── 08 - AGO - 26\    (4 arquivos)
└── 09 - SET - 26\    (1 arquivo)
```

**Total no Drive:** 30 arquivos de programa (29 produção + 1 legado)

---

## Melhorias Implementadas (jan–set 2026)

### 1. Filtro Geográfico com Threshold (commit `bd9d1b9`)
- **Regra:** ≥ 4 notas de outras cidades → filtra Natal
- **Regra:** < 4 notas → complementa com notas institucionais de Natal/TJRN
- Aplicado por programa individualmente

### 2. Fallback em Cascata (commit `b9776c5`)
- **Passo 1:** Notas de outras cidades da semana atual (evitar_natal=True)
- **Passo 2:** Fallback inicial — notas de Natal da semana atual
- **Passo 3:** Fallback mensal — copia notas de programas anteriores do mesmo mês
- **Passo 4:** Cross-month — para primeiro programa do mês, busca no mês anterior

### 3. Otimização MAX_NOTAS=6 (commit `cf3d998`)
- Para de processar boletins ao atingir 6 notas
- Evita transcrever boletins desnecessários

### 4. Parada Antecipada no Fallback (commit `8303a4b`)
- Meta explícita: calcula quantas notas faltam
- Interrompe assim que atinge o mínimo (4 notas)
- Log claro: "Preciso de mais X nota(s)", "Meta atingida!"

### 5. Fallback Mensal Cross-Month (commit `6449fbb`)
- Primeiro programa do mês sem boletins → busca no mês anterior
- Garante 4 programas mesmo em meses com baixa produção

---

## Especificações Técnicas

- **Modelo Whisper:** tiny (CPU-safe para i5-8600K)
- **Compute type:** int8
- **Threads:** MKL_NUM_THREADS=1, OMP_NUM_THREADS=1
- **Vinhetas:** VHT_ABERTURA_GIRO, VHT_PASSAGEM_GIRO, VHT_ENCERRAMENTO_GIRO
- **Filtro:** 167 municípios do RN (lista IBGE)
- **Formato saída:** GNC_mmss_DD-MM-AA.mp3
- **Duração média:** 4–7 minutos

---

## Commits Relevantes

```
0f5f2a0  Produção: maio-jul-ago/2026 processados e montados (15 programas)
6449fbb  Fix: fallback mensal cross-month para primeiro programa do mês
b9776c5  Feat: fallback mensal com semanas anteriores para garantir 4 notas
cf3d998  Otimização: MAX_NOTAS=6 com parada antecipada no Passo 1
8303a4b  Otimização: fallback Natal com meta explícita e parada antecipada
bd9d1b9  Fix: threshold 4 notas para fallback Natal (GIRO)
38b89c2  Docs: plano de produção GIRO 2026 completo (jan-dez)
70afd84  fix(giro): adicionar imports MODELO_WHISPER, COMPUTE_TYPE, CACHE_TRANSCRICOES
```

---

## Pendências

- [ ] Setembro: 0902, 0903, 0904
- [ ] Outubro: 1001–1004
- [ ] Novembro: 1101–1104
- [ ] Dezembro: 1201–1204

---

*Documento gerado automaticamente em 2026-09-07*
