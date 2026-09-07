# Plano de Produção GIRO nas Comarcas — 2026 Completo

## Visão Geral Anual

- **Programa:** GIRO nas Comarcas (GNC)
- **Frequência:** Semanal (terças-feiras)
- **Total de programas em 2026:** 48 edições (4 por mês × 12 meses)
- **Duração estimada por programa:** 3–7 minutos
- **Formato de saída:** `GNC_mmss_DD-MM-AA.mp3`
  - `mmss` = mês (01–12) + semana do mês (01–04)
  - `DD-MM-AA` = data de exibição (terça-feira)
- **Conteúdo:** Notícias do RN filtradas por `RN_CIDADES` (167 municípios)

## Regra de Negócio do Plano

O plano é gerado por `src/giro/utils.py → gerar_plano(ano)`:

- O ano começa na 1ª terça de janeiro (dia ISO 2 da 1ª semana ISO).
- Cada mês tem 4 programas (ss = 01..04).
- A faixa de notícias de cada programa é a **segunda→domingo da semana anterior** à terça de exibição.
- O mês do boletim é o mês da segunda-feira da semana de notícias.

## Calendário de Produção 2026

### Janeiro/2026

| mmss | Terça | Notícias (seg→dom) | Boletim-mês | Status |
|------|-------|-------------------|-------------|--------|
| 0101 | 06/01 | 28/12→03/01 | dez/25 | ❌ Sem boletins |
| 0102 | 13/01 | 04/01→10/01 | jan/26 | ✅ GNC_0102_13-01-2026.mp3 |
| 0103 | 20/01 | 11/01→17/01 | jan/26 | ✅ GNC_0103_20-01-2026.mp3 |
| 0104 | 27/01 | 18/01→24/01 | jan/26 | ❌ Sem boletins |

### Fevereiro/2026

| mmss | Terça | Notícias (seg→dom) | Boletim-mês | Status |
|------|-------|-------------------|-------------|--------|
| 0201 | 03/02 | 25/01→31/01 | jan/26 | ⏳ Pendente |
| 0202 | 10/02 | 01/02→07/02 | fev/26 | ⏳ Pendente |
| 0203 | 17/02 | 08/02→14/02 | fev/26 | ⏳ Pendente |
| 0204 | 24/02 | 15/02→21/02 | fev/26 | ⏳ Pendente |

### Março/2026

| mmss | Terça | Notícias (seg→dom) | Boletim-mês | Status |
|------|-------|-------------------|-------------|--------|
| 0301 | 03/03 | 22/02→28/02 | fev/26 | ⏳ Pendente |
| 0302 | 10/03 | 01/03→07/03 | mar/26 | ⏳ Pendente |
| 0303 | 17/03 | 08/03→14/03 | mar/26 | ⏳ Pendente |
| 0304 | 24/03 | 15/03→21/03 | mar/26 | ⏳ Pendente |
| 0401 | 31/03 | 22/03→28/03 | mar/26 | ⏳ Pendente |

### Abril/2026

| mmss | Terça | Notícias (seg→dom) | Boletim-mês | Status |
|------|-------|-------------------|-------------|--------|
| 0402 | 07/04 | 29/03→04/04 | mar/26 | ⏳ Pendente |
| 0403 | 14/04 | 05/04→11/04 | abr/26 | ⏳ Pendente |
| 0404 | 21/04 | 12/04→18/04 | abr/26 | ⏳ Pendente |
| 0501 | 28/04 | 19/04→25/04 | abr/26 | ⏳ Pendente |

**⚠️ Atenção:** Tiradentes (21/04) é feriado — 0404 pode ter conteúdo reduzido.

### Maio/2026

| mmss | Terça | Notícias (seg→dom) | Boletim-mês | Status |
|------|-------|-------------------|-------------|--------|
| 0502 | 05/05 | 26/04→02/05 | abr/26 | ⏳ Pendente |
| 0503 | 12/05 | 03/05→09/05 | mai/26 | ⏳ Pendente |
| 0504 | 19/05 | 10/05→16/05 | mai/26 | ⏳ Pendente |
| 0601 | 26/05 | 17/05→23/05 | mai/26 | ⏳ Pendente |

### Junho/2026

| mmss | Terça | Notícias (seg→dom) | Boletim-mês | Status |
|------|-------|-------------------|-------------|--------|
| 0602 | 02/06 | 24/05→30/05 | mai/26 | ⏳ Pendente |
| 0603 | 09/06 | 31/05→06/06 | mai/26 | ⏳ Pendente |
| 0604 | 16/06 | 07/06→13/06 | jun/26 | ⏳ Pendente |
| 0701 | 23/06 | 14/06→20/06 | jun/26 | ⏳ Pendente |

**📋 Fechamento Semestre 1** (após 0701)

### Julho/2026

| mmss | Terça | Notícias (seg→dom) | Boletim-mês | Status |
|------|-------|-------------------|-------------|--------|
| 0702 | 30/06 | 21/06→27/06 | jun/26 | ⏳ Pendente |
| 0703 | 07/07 | 28/06→04/06 | jun/26 | ⏳ Pendente |
| 0704 | 14/07 | 05/07→11/07 | jul/26 | ⏳ Pendente |
| 0801 | 21/07 | 12/07→18/07 | jul/26 | ⏳ Pendente |

**⚠️ Atenção:** Recesso forense — notícias podem ser escassas. Acumular da semana anterior.

### Agosto/2026

| mmss | Terça | Notícias (seg→dom) | Boletim-mês | Status |
|------|-------|-------------------|-------------|--------|
| 0802 | 28/07 | 19/07→25/07 | jul/26 | ⏳ Pendente |
| 0803 | 04/08 | 26/07→01/08 | jul/26 | ⏳ Pendente |
| 0804 | 11/08 | 02/08→08/08 | ago/26 | ⏳ Pendente |
| 0901 | 18/08 | 09/08→15/08 | ago/26 | ⏳ Pendente |

### Setembro/2026

| mmss | Terça | Notícias (seg→dom) | Boletim-mês | Status |
|------|-------|-------------------|-------------|--------|
| 0902 | 25/08 | 16/08→22/08 | ago/26 | ⏳ Pendente |
| 0903 | 01/09 | 23/08→29/08 | ago/26 | ⏳ Pendente |
| 0904 | 08/09 | 30/08→05/09 | set/26 | ⏳ Pendente |
| 1001 | 15/09 | 06/09→12/09 | set/26 | ⏳ Pendente |

### Outubro/2026

| mmss | Terça | Notícias (seg→dom) | Boletim-mês | Status |
|------|-------|-------------------|-------------|--------|
| 1002 | 22/09 | 13/09→19/09 | set/26 | ⏳ Pendente |
| 1003 | 29/09 | 20/09→26/09 | set/26 | ⏳ Pendente |
| 1004 | 06/10 | 27/09→03/09 | set/26 | ⏳ Pendente |
| 1101 | 13/10 | 04/10→10/10 | out/26 | ⏳ Pendente |

### Novembro/2026

| mmss | Terça | Notícias (seg→dom) | Boletim-mês | Status |
|------|-------|-------------------|-------------|--------|
| 1102 | 20/10 | 11/10→17/10 | out/26 | ⏳ Pendente |
| 1103 | 27/10 | 18/10→24/10 | out/26 | ⏳ Pendente |
| 1104 | 03/11 | 25/10→31/10 | out/26 | ⏳ Pendente |
| 1201 | 10/11 | 01/11→07/11 | nov/26 | ⏳ Pendente |

### Dezembro/2026

| mmss | Terça | Notícias (seg→dom) | Boletim-mês | Status |
|------|-------|-------------------|-------------|--------|
| 1202 | 17/11 | 08/11→14/11 | nov/26 | ⏳ Pendente |
| 1203 | 24/11 | 15/11→21/11 | nov/26 | ⏳ Pendente |
| 1204 | 01/12 | 22/11→28/11 | nov/26 | ⏳ Pendente |

**⚠️ Último programa do ano:** 1204 (01/12). Recesso forense começa ~20/12.

---

## Fluxo Operacional Padrão (Semanal)

### Comando único (processamento completo)

```bash
# Variáveis de ambiente (i5-8600K, 6C/6T, sem GPU)
set MKL_NUM_THREADS=1
set OMP_NUM_THREADS=1
set MODELO_WHISPER=tiny
set COMPUTE_TYPE=int8

# Processar programa específico
cd E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR
set PYTHONPATH=src
python -m giro JORNAIS/ --mmss MMSS --verbose

# Montar programa (após processamento)
python -m giro --montar data/processed/GIRO_COMARCAS/MMSS/

# Sync para Drive (manual)
copy data\output\GIRO_COMARCAS\GNC_MMSS_DD-MM-AA.mp3 "H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026\03_GIRO_NAS_COMARCAS\MM - MES - 26\"
```

### Validação

```bash
# Duração do programa
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 data/output/GIRO_COMARCAS/GNC_MMSS_DD-MM-AA.mp3

# Metas: 3–7 min (180–420s)
```

---

## Estrutura de Diretórios (Pipeline GIRO)

```
DIVISOR/
├── src/giro/
│   ├── cli.py              # Entry point: processar_giro(), montar_giro()
│   ├── transcricao.py      # transcrever_boletim() + processar_boletim()
│   ├── filtro.py           # filtrar_nota() — filtro geográfico RN
│   ├── montagem.py         # montar_programa() — vinhetas + notas
│   ├── plano.py            # gerar_plano_csv() — alocação mmss
│   ├── sync_drive.py       # sincronizar_programa() → Drive H:
│   ├── utils.py            # gerar_plano(), nome_programa()
│   └── config.py           # Importa de config.giro.settings
├── src/config/giro.py      # SettingsGiro (paths, thresholds, vinhetas)
├── assets/vinhetas/giro/
│   ├── VHT_ABERTURA_GIRO.mp3
│   ├── VHT_PASSAGEM_GIRO.mp3
│   └── VHT_ENCERRAMENTO_GIRO.mp3
├── data/
│   ├── processed/GIRO_COMARCAS/MMSS/  # Notas cortadas
│   └── output/GIRO_COMARCAS/           # Programas montados (.mp3)
├── logs/giro/                          # Logs namespaced
└── JORNAIS/                            # Boletins de entrada
```

---

## Tratamento de Erros Comuns

### Erro: `NameError: name 'MODELO_WHISPER' is not defined`
**Causa:** Import faltante em `transcricao.py`.  
**Fix:** Adicionar `MODELO_WHISPER, COMPUTE_TYPE, CACHE_TRANSCRICOES` ao import do `.config`.  
**Status:** ✅ Corrigido (commit `70afd84`).

### Erro: `mkl_malloc: failed to allocate memory`
**Causa:** Muitas threads Whisper em CPU.  
**Fix:** `MKL_NUM_THREADS=1 OMP_NUM_THREADS=1` + modelo `tiny`.

### Erro: Nenhuma nota aceita
**Causa:** Boletins sem notícias do RN ou filtro muito restritivo.  
**Fix:** Verificar `RN_CIDADES` em `src/giro/config.py` (167 municípios).

### Erro: Drive H: não montado
**Fix:** Verificar `dir H:` no Windows. Caminho: `H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026\03_GIRO_NAS_COMARCAS\`

---

## Métricas de Qualidade

| Métrica | Meta | Tolerância |
|---------|------|------------|
| Duração do programa | 3–5 min | 2–7 min |
| Notas por programa | 4–6 | 2–10 |
| Tempo de processamento | <15 min | <30 min |
| Taxa de sucesso mensal | 100% | ≥75% (3/4 programas) |

---

## Checklist Anual de Fechamento (Dezembro)

- [ ] 48 programas produzidos (ou menos se falta de boletins)
- [ ] Todos os programas no Google Drive H:
- [ ] Logs arquivados em `logs/giro/`
- [ ] Cache de transcrição limpo (opcional)
- [ ] RN_CIDADES atualizado para 2027
- [ ] Vinhetas verificadas (qualidade de áudio)
- [ ] Relatório estatístico gerado

---

*Documento gerado em 2026-09-07 | Versão 2.0 | Commit base: 70afd84*
*Plano gerado via `src/giro/utils.py → gerar_plano(2026)`*
