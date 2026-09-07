# Plano de Produção GIRO nas Comarcas - 2026 Completo

## Visão Geral Anual

**Programa:** GIRO nas Comarcas (GNC)  
**Frequência:** Semanal (todas as terças-feiras)  
**Total de programas em 2026:** 52 edições  
**Duração estimada por programa:** 3-5 minutos  
**Formato de saída:** `GNC_mmss_DD-MM-AA.mp3`

---

## Estrutura de Diretórios (comum a todos os meses)

```
src/
├── giro/
│   ├── cli.py              # Entry point principal
│   ├── transcricao.py      # Transcrição com cache
│   ├── filtro.py           # Filtro geográfico (RN_CIDADES)
│   ├── montagem.py         # Montagem com vinhetas
│   ├── utils.py            # Utilitários (nome_programa)
│   └── sync_drive.py       # Sync para Google Drive
config/
├── giro.py                 # SettingsGiro (unificado)
└── njud.py                 # SettingsNJUD
assets/vinhetas/giro/
├── VHT_ABERTURA_GIRO.mp3
├── VHT_PASSAGEM_GIRO.mp3
└── VHT_ENCERRAMENTO_GIRO.mp3
logs/giro/                  # Logs namespaced
data/input/JORNAIS/         # Entradas (MP3 brutos)
data/output/GIRO_COMARCAS/  # Saídas processadas
```

---

## Variáveis de Ambiente Obrigatórias

```bash
# Modelo Whisper (CPU-safe para i5-8600K)
export MODELO_WHISPER="tiny"
export COMPUTE_TYPE="int8"

# Limitação de threads (evita mkl_malloc failure)
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2

# Diretórios
export DIR_DRIVE_JORNAIS="/mnt/google-drive/JORNAIS"  # ou H:/JORNAIS no Windows
export GNC_DRIVE_SYNC="true"  # habilita sync automático

# Paths internos (config/giro.py)
# BASE_DIR, DIR_PROCESSED, DIR_OUTPUT já definidos em SettingsGiro
```

---

## Calendário de Produção 2026

### Regra de Negócio
- **Dia de produção:** Terça-feira de cada semana
- **Código do programa:** `GNC_mmss_DD-MM-AA.mp3`
  - `mmss`: minuto e segundo de início da vinheta de abertura (ex: 0130 = 1min30s)
  - `DD-MM-AA`: data de exibição (terça-feira)
- **Conteúdo:** Notícias das 167 cidades do RN filtradas por `RN_CIDADES`

### Feriados e Exceções
- Não há edição em feriados nacionais que caiam em terça-feira (remanejo para quarta)
- Recesso forense (janeiro e julho): manutenção do cronograma normal (notícias acumuladas)

---

## FEVEREIRO/2026

**Terças-feiras:** 03, 10, 17, 24  
**Programas:** 0201, 0202, 0203, 0204

| Programa | Data | Código Arquivo | Status |
|----------|------|----------------|--------|
| Semana 1 | 03/02/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 2 | 10/02/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 3 | 17/02/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 4 | 24/02/2026 | GNC_*.mp3 | ⏳ Pendente |

**Comandos de Produção (repetir para cada semana):**

```bash
# 1. Gerar plano de corte (ajustar DATA para cada semana)
python -m src.giro.cli data/input/JORNAIS --ano 2026 --mes 02 --semana 1 --verbose

# 2. Verificar transcrições cacheadas
ls -lh data/output/GIRO_COMARCAS/transcricoes/

# 3. Filtrar notas do RN
python -m src.giro.filtro data/output/GIRO_COMARCAS/transcricoes/ --rn-only

# 4. Montar programa
python -m src.giro.montagem data/output/GIRO_COMARCAS/notas_filtradas/ --output data/output/GIRO_COMARCAS/programas/

# 5. Validar duração (3-5 min ideal)
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 data/output/GIRO_COMARCAS/programas/GNC_*.mp3

# 6. Sync para Drive (se GNC_DRIVE_SYNC=true)
python -m src.giro.sync_drive data/output/GIRO_COMARCAS/programas/
```

**Checklist Fevereiro:**
- [ ] Jornal de 03/02 processado
- [ ] Jornal de 10/02 processado
- [ ] Jornal de 17/02 processado
- [ ] Jornal de 24/02 processado
- [ ] Logs verificados em `logs/giro/`
- [ ] BackupDrive confirmado (4 arquivos)

---

## MARÇO/2026

**Terças-feiras:** 03, 10, 17, 24, 31  
**Programas:** 0301, 0302, 0303, 0304, 0305

| Programa | Data | Código Arquivo | Status |
|----------|------|----------------|--------|
| Semana 1 | 03/03/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 2 | 10/03/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 3 | 17/03/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 4 | 24/03/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 5 | 31/03/2026 | GNC_*.mp3 | ⏳ Pendente |

**Comandos:** Mesmos de fevereiro, ajustando `--mes 03 --semana N`

**Checklist Março:**
- [ ] 5 programas processados
- [ ] Duração média validada (3-5 min)
- [ ] Nenhuma nota duplicada entre semanas
- [ ] Logs sem erros críticos

---

## ABRIL/2026

**Terças-feiras:** 07, 14, 21, 28  
**Programas:** 0401, 0402, 0403, 0404

| Programa | Data | Código Arquivo | Status |
|----------|------|----------------|--------|
| Semana 1 | 07/04/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 2 | 14/04/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 3 | 21/04/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 4 | 28/04/2026 | GNC_*.mp3 | ⏳ Pendente |

**Atenção:** Tiradentes (21/04) é feriado nacional — se cair em terça, verificar se há notícias suficientes. Se não, remarcar para 22/04 (quarta).

**Checklist Abril:**
- [ ] 4 programas processados
- [ ] Feriado de 21/04 tratado (se aplicável)
- [ ] BackupDrive confirmado

---

## MAIO/2026

**Terças-feiras:** 05, 12, 19, 26  
**Programas:** 0501, 0502, 0503, 0504

| Programa | Data | Código Arquivo | Status |
|----------|------|----------------|--------|
| Semana 1 | 05/05/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 2 | 12/05/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 3 | 19/05/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 4 | 26/05/2026 | GNC_*.mp3 | ⏳ Pendente |

**Atenção:** Dia do Trabalho (01/05) não afeta terça-feira.

**Checklist Maio:**
- [ ] 4 programas processados
- [ ] Validação de áudio (sem truncamentos)

---

## JUNHO/2026

**Terças-feiras:** 02, 09, 16, 23, 30  
**Programas:** 0601, 0602, 0603, 0604, 0605

| Programa | Data | Código Arquivo | Status |
|----------|------|----------------|--------|
| Semana 1 | 02/06/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 2 | 09/06/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 3 | 16/06/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 4 | 23/06/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 5 | 30/06/2026 | GNC_*.mp3 | ⏳ Pendente |

**Atenção:** São João (24/06) não afeta terça-feira.

**Checklist Junho:**
- [ ] 5 programas processados
- [ ] Fechamento do semestre 1 (backup completo)

---

## JULHO/2026

**Terças-feiras:** 07, 14, 21, 28  
**Programas:** 0701, 0702, 0703, 0704

| Programa | Data | Código Arquivo | Status |
|----------|------|----------------|--------|
| Semana 1 | 07/07/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 2 | 14/07/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 3 | 21/07/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 4 | 28/07/2026 | GNC_*.mp3 | ⏳ Pendente |

**Atenção:** Recesso forense — notícias podem ser escassas. Acumular da semana anterior se necessário.

**Checklist Julho:**
- [ ] 4 programas processados
- [ ] Conteúdo mínimo validado (não vazio)
- [ ] Cache de transcrição limpo (opcional)

---

## AGOSTO/2026

**Terças-feiras:** 04, 11, 18, 25  
**Programas:** 0801, 0802, 0803, 0804

| Programa | Data | Código Arquivo | Status |
|----------|------|----------------|--------|
| Semana 1 | 04/08/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 2 | 11/08/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 3 | 18/08/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 4 | 25/08/2026 | GNC_*.mp3 | ⏳ Pendente |

**Checklist Agosto:**
- [ ] 4 programas processados
- [ ] Validação de integridade (auditoria)

---

## SETEMBRO/2026

**Terças-feiras:** 01, 08, 15, 22, 29  
**Programas:** 0901, 0902, 0903, 0904, 0905

| Programa | Data | Código Arquivo | Status |
|----------|------|----------------|--------|
| Semana 1 | 01/09/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 2 | 08/09/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 3 | 15/09/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 4 | 22/09/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 5 | 29/09/2026 | GNC_*.mp3 | ⏳ Pendente |

**Atenção:** Independência (07/09) não afeta terça-feira.

**Checklist Setembro:**
- [ ] 5 programas processados
- [ ] Auditoria de integridade completa

---

## OUTUBRO/2026

**Terças-feiras:** 06, 13, 20, 27  
**Programas:** 1001, 1002, 1003, 1004

| Programa | Data | Código Arquivo | Status |
|----------|------|----------------|--------|
| Semana 1 | 06/10/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 2 | 13/10/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 3 | 20/10/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 4 | 27/10/2026 | GNC_*.mp3 | ⏳ Pendente |

**Atenção:** Nossa Senhora Aparecida (12/10) e Dia do Servidor (28/10) não afetam terças.

**Checklist Outubro:**
- [ ] 4 programas processados
- [ ] Backup trimestral (Q3) confirmado

---

## NOVEMBRO/2026

**Terças-feiras:** 03, 10, 17, 24  
**Programas:** 1101, 1102, 1103, 1104

| Programa | Data | Código Arquivo | Status |
|----------|------|----------------|--------|
| Semana 1 | 03/11/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 2 | 10/11/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 3 | 17/11/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 4 | 24/11/2026 | GNC_*.mp3 | ⏳ Pendente |

**Atenção:** Finados (02/11) e Proclamação da República (15/11) não afetam terças.

**Checklist Novembro:**
- [ ] 4 programas processados
- [ ] Preparação para fechamento anual

---

## DEZEMBRO/2026

**Terças-feiras:** 01, 08, 15, 22, 29  
**Programas:** 1201, 1202, 1203, 1204, 1205

| Programa | Data | Código Arquivo | Status |
|----------|------|----------------|--------|
| Semana 1 | 01/12/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 2 | 08/12/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 3 | 15/12/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 4 | 22/12/2026 | GNC_*.mp3 | ⏳ Pendente |
| Semana 5 | 29/12/2026 | GNC_*.mp3 | ⏳ Pendente |

**Atenção:** Natal (25/12) e Ano Novo (01/01) — programa de 29/12 pode ser o último do ano. Verificar recesso forense.

**Checklist Dezembro:**
- [ ] 5 programas processados (ou 4 se recesso)
- [ ] Backup anual completo (52 programas)
- [ ] Relatório final gerado
- [ ] Limpeza de cache (opcional)

---

## Fluxo Operacional Padrão (Semanal)

### Passo 1: Preparação (segunda-feira)
```bash
# Verificar entrada de jornais
ls -lh data/input/JORNAIS/*.mp3 | grep "$(date -d 'yesterday' +%d-%m-%y)"

# Rodar pré-processamento se necessário
python -m src.divisor_boletins.audio data/input/JORNAIS/ data/output/GIRO_COMARCAS/cortes/ --apply
```

### Passo 2: Processamento GIRO (terça-feira manhã)
```bash
# Transcrever (cache automático)
python -m src.giro.cli data/input/JORNAIS --ano 2026 --mes MM --semana N --verbose

# Filtrar RN
python -m src.giro.filtro data/output/GIRO_COMARCAS/transcricoes/ --rn-only --output data/output/GIRO_COMARCAS/notas_filtradas/

# Montar
python -m src.giro.montagem data/output/GIRO_COMARCAS/notas_filtradas/ --output data/output/GIRO_COMARCAS/programas/ --vinhetas assets/vinhetas/giro/
```

### Passo 3: Validação (terça-feira tarde)
```bash
# Duração
for f in data/output/GIRO_COMARCAS/programas/GNC_*.mp3; do
  dur=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$f")
  echo "$(basename $f): ${dur}s"
done

# Integridade (opcional)
python -m src.audit.integrity data/output/GIRO_COMARCAS/programas/ --modelo tiny
```

### Passo 4: Distribuição (terça-feira fim de tarde)
```bash
# Sync automático (se GNC_DRIVE_SYNC=true)
python -m src.giro.sync_drive data/output/GIRO_COMARCAS/programas/

# Ou manual
cp data/output/GIRO_COMARCAS/programas/GNC_*.mp3 /mnt/google-drive/JORNAIS/MM-MES-26/
```

### Passo 5: Registro (terça-feira noite)
```bash
# Log de produção
echo "[$(date +%Y-%m-%d)] GNC produzido: $(ls data/output/GIRO_COMARCAS/programas/GNC_*.mp3 | wc -l) programas" >> logs/giro/producao_2026.log

# Atualizar planilha de controle (opcional)
```

---

## Tratamento de Erros Comuns

### Erro 1: "Áudio vazio ou sem fala detectada"
**Causa:** Jornal bruto sem conteúdo ou falha na transcrição.  
**Solução:**
```bash
# Verificar arquivo bruto
ffprobe data/input/JORNAIS/jornal_DD-MM-AA.mp3

# Forçar re-transcrição (limpar cache)
rm data/output/GIRO_COMARCAS/transcricoes/jornal_DD-MM-AA.json
python -m src.giro.transcricao data/input/JORNAIS/jornal_DD-MM-AA.mp3 --force
```

### Erro 2: "Nenhuma nota do RN encontrada"
**Causa:** RN_CIDADES desatualizado ou jornal sem notícias locais.  
**Solução:**
- Verificar `RN_CIDADES` em `config/giro.py` (167 municípios)
- Cruzar com IBGE se necessário
- Acumular notas da semana anterior

### Erro 3: "mkl_malloc failure" (CPU)
**Causa:** Modelo Whisper "small" ou threads excessivas.  
**Solução:**
```bash
export MODELO_WHISPER="tiny"
export COMPUTE_TYPE="int8"
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
```

### Erro 4: "Google Drive não montado"
**Causa:** Path incorreto ou drive desconectado.  
**Solução:**
```bash
# Verificar mount
df -h | grep google-drive  # Linux
dir H:  # Windows

# Ajustar DIR_DRIVE_JORNAIS em .env
```

---

## Monitoramento e Logs

### Localização dos Logs
```
logs/giro/
├── transcricao_YYYYMMDD.log    # Transcrições
├── filtro_YYYYMMDD.log         # Filtro geográfico
├── montagem_YYYYMMDD.log       # Montagem de programas
├── sync_drive_YYYYMMDD.log     # Sync para Drive
└── producao_2026.log           # Log mestre anual
```

### Comandos de Verificação
```bash
# Últimos erros
grep -i "erro\|fail\|alert" logs/giro/*.log | tail -20

# Programas produzidos
ls -1 data/output/GIRO_COMARCAS/programas/GNC_*.mp3 | wc -l

# Tamanho médio dos programas
du -ch data/output/GIRO_COMARCAS/programas/GNC_*.mp3 | grep total
```

---

## Métricas de Qualidade

| Métrica | Meta | Tolerância |
|---------|------|------------|
| Duração do programa | 3-5 min | 2-6 min |
| Notas por programa | 5-10 | 3-15 |
| Cidades cobertas | ≥10 por programa | ≥5 |
| Tempo de processamento | <30 min | <60 min |
| Taxa de sucesso | 100% | ≥95% |

---

## Checklist Anual de Fechamento (Dezembro)

- [ ] 52 programas produzidos (ou menos se recesso)
- [ ] Todos os programas no Google Drive
- [ ] Logs arquivados (`logs/giro/2026/`)
- [ ] Cache limpo (opcional)
- [ ] Relatório estatístico gerado
- [ ] RN_CIDADES atualizado para 2027
- [ ] Vinhetas verificadas (qualidade de áudio)
- [ ] Backup local e na nuvem confirmado
- [ ] Planejamento 2027 iniciado

---

## Contato e Suporte

**Documentação:** `docs/AGENTE_GIRO.md`, `docs/PLANO_MODULARIZACAO.md`  
**Configurações:** `config/giro.py` (SettingsGiro)  
**Logs:** `logs/giro/`  
**Drive:** `GNC_DRIVE_SYNC=true` → `DIR_DRIVE_JORNAIS`

---

*Documento gerado em 2026-01-XX | Versão 1.0 | Commit de referência: 2b90c75 + f2fc0b7*
