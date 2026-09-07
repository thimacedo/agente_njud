# Planejamento de Produção - GIRO nas Comarcas - Janeiro/2026

## Visão Geral

Este documento descreve o plano de produção dos programas do **GIRO nas Comarcas** referentes a **janeiro de 2026**, utilizando a infraestrutura modularizada e unificada do repositório.

---

## 1. Pré-requisitos

### 1.1 Estrutura de Diretórios Esperada

```
/workspace/
├── src/
│   ├── giro/                    # Módulo GIRO
│   │   ├── cli.py               # Entry point principal
│   │   ├── transcricao.py       # Transcrição com Whisper
│   │   ├── filtro.py            # Filtro geográfico
│   │   ├── montagem.py          # Montagem dos programas
│   │   ├── log.py               # Logs namespaced
│   │   └── config.py            # Configs de domínio (thresholds, RN)
│   └── config/
│       ├── giro.py              # SettingsGiro (infraestrutura)
│       └── njud.py              # SettingsNJUD (compartilhado)
├── data/
│   ├── input/
│   │   └── JORNAIS/             # Boletins brutos (entrada)
│   │       ├── 2026-01-02_...mp3
│   │       ├── 2026-01-03_...mp3
│   │       └── ...
│   ├── processed/
│   │   └── GIRO_COMARCAS/       # Processados intermediários
│   │       ├── estado/          # Estado por nota (JSON)
│   │       └── <N>.mp3          # Cortes individuais
│   └── output/
│       └── GIRO_COMARCAS/       # Programas finais montados
│           ├── GNC_0101_06-01-26.mp3
│           ├── GNC_0102_13-01-26.mp3
│           └── ...
├── assets/
│   └── vinhetas/
│       └── giro/
│           ├── VHT_ABERTURA_GIRO.mp3
│           ├── VHT_PASSAGEM_GIRO.mp3
│           └── VHT_ENCERRAMENTO_GIRO.mp3
└── logs/
    └── giro/
        ├── giro_processamento.log
        └── giro_montagem.log
```

### 1.2 Variáveis de Ambiente (Opcionais)

```bash
# Modelo Whisper (default: "tiny")
export MODELO_WHISPER="tiny"

# Tipo de computação (default: "int8")
export COMPUTE_TYPE="int8"

# Limiares do GIRO (defaults configurados em config/giro.py)
export LIMIAR_ANCORA_GIRO="0.55"
export LIMIAR_FIM_PASSAGEM_GIRO="0.8"
export LIMIAR_INICIO_FALA_GIRO="0.3"

# Diretório do Drive (Windows)
export DIR_DRIVE_GIRO="H:\\Meu Drive\\RADIO TJRN CONTEÚDO\\00_PRODUCAO_2026\\02_JORNAIS_GIRO\\03_AUDIOS_RADIO"

# Ano padrão
export ANO_PADRAO="2026"
```

### 1.3 Vinhetas Necessárias

Verificar existência em `assets/vinhetas/giro/`:
- ✅ `VHT_ABERTURA_GIRO.mp3`
- ✅ `VHT_PASSAGEM_GIRO.mp3`
- ✅ `VHT_ENCERRAMENTO_GIRO.mp3`

---

## 2. Calendário de Produção - Janeiro/2026

### 2.1 Programação Regular

| Semana | Terça-feira | Código | Data Base |
|--------|-------------|--------|-----------|
| 1      | 06/01/2026  | 0101   | 2026-01-06 |
| 2      | 13/01/2026  | 0102   | 2026-01-13 |
| 3      | 20/01/2026  | 0103   | 2026-01-20 |
| 4      | 27/01/2026  | 0104   | 2026-01-27 |

**Total:** 4 programas em janeiro/2026

### 2.2 Boletins Necessários por Programa

Cada programa requer **~10 boletins** da semana anterior (ou mesma semana, conforme disponibilidade):

| Programa | Período de Coleta | Quantidade Mínima |
|----------|-------------------|-------------------|
| 0101     | 29/12/2025 - 05/01/2026 | 10 boletins |
| 0102     | 06/01/2026 - 12/01/2026 | 10 boletins |
| 0103     | 13/01/2026 - 19/01/2026 | 10 boletins |
| 0104     | 20/01/2026 - 26/01/2026 | 10 boletins |

---

## 3. Fluxo de Processamento

### 3.1 Etapa 1: Geração do Plano

O plano define quais boletins serão processados para cada programa.

**Comando:**
```bash
cd /workspace/src
python -c "from giro.utils import gerar_plano; gerar_plano(ano=2026, mes='JAN')"
```

**Saída esperada:**
- `data/plano_giro_2026.csv` com colunas: `codigo,mmss,data_terca,boletins_previstos`

### 3.2 Etapa 2: Processamento Completo (CLI Principal)

**Para processar todos os programas de janeiro:**
```bash
cd /workspace
python -m src.giro.cli \
    data/input/JORNAIS \
    --saida data/output/GIRO_COMARCAS \
    --ano 2026 \
    --verbose
```

**Para processar um programa específico (ex: 0101):**
```bash
cd /workspace
python -m src.giro.cli \
    data/input/JORNAIS \
    --saida data/output/GIRO_COMARCAS \
    --mmss 0101 \
    --ano 2026 \
    --verbose
```

### 3.3 Etapa 3: Verificação do Estado

Os arquivos de estado são persistidos em:
```
data/processed/GIRO_COMARCAS/estado/
├── 0001.json
├── 0002.json
└── ...
```

Cada JSON contém:
```json
{
  "id_nota": "0001",
  "texto_completo": "...",
  "cidades_mencionadas": ["Parnamirim", "Mossoró"],
  "classificacao": "INTERIOR",
  "corte_aprovado": true,
  "caminho_corte": "data/processed/GIRO_COMARCAS/0001.mp3"
}
```

### 3.4 Etapa 4: Montagem Final

A montagem é automática no fluxo principal, mas pode ser reexecutada:

```bash
cd /workspace
python -c "
from giro.montagem import montar_programa
from pathlib import Path

montar_programa(
    codigo='0101',
    ano=2026,
    pasta_estado=Path('data/processed/GIRO_COMARCAS/estado'),
    pasta_saida=Path('data/output/GIRO_COMARCAS')
)
```

---

## 4. Critérios de Qualidade

### 4.1 Filtro Geográfico

Uma nota é aprovada se:
- ✅ Mencionar **pelo menos 1 cidade do interior** (RN_CIDADES - Natal)
- ✅ Não for classificada como `NATAL` ou `DESCONHECIDO`
- ✅ Tiver duração entre **30s e 180s**

### 4.2 Validação de Áudio

Cada corte deve passar por:
1. **Transcrição bem-sucedida** (Whisper retorna texto não-vazio)
2. **Presença de LOC+OFF** (estrutura básica de nota jornalística)
3. **Sem truncamento** (início e fim completos)

### 4.3 Programa Final

Cada programa montado deve ter:
- 🎵 Vinheta de abertura (`VHT_ABERTURA_GIRO.mp3`)
- 📰 8-12 notas filtradas (ordem cronológica)
- 🎵 Vinhetas de passagem entre notas (opcional)
- 🎵 Vinheta de encerramento (`VHT_ENCERRAMENTO_GIRO.mp3`)
- ⏱️ Duração total: **10-15 minutos**

---

## 5. Monitoramento e Logs

### 5.1 Arquivos de Log

| Log | Caminho | Finalidade |
|-----|---------|------------|
| Processamento | `logs/giro/giro_processamento.log` | Transcrição, filtros, cortes |
| Montagem | `logs/giro/giro_montagem.log` | Seleção de notas, concatenação |

### 5.2 Comandos de Verificação

**Verificar status dos programas:**
```bash
ls -lh data/output/GIRO_COMARCAS/GNC_*.mp3
```

**Verificar logs de erro:**
```bash
grep -i "erro\|falha\|alerta" logs/giro/giro_processamento.log | tail -20
```

**Contar notas processadas:**
```bash
ls data/processed/GIRO_COMARCAS/estado/*.json | wc -l
```

---

## 6. Tratamento de Erros Comuns

### 6.1 Boletins sem Áudio Válido

**Sintoma:** Whisper retorna texto vazio  
**Ação:** Verificar qualidade do áudio original  
```bash
ffprobe data/input/JORNAIS/2026-01-XX_*.mp3
```

### 6.2 Poucas Notas Aprovadas

**Sintoma:** < 8 notas após filtro  
**Causas possíveis:**
- Boletins muito focados em Natal
- Limiar de âncora muito alto  
**Ajuste:**
```bash
export LIMIAR_ANCORA_GIRO="0.45"  # Reduzir de 0.55 para 0.45
```

### 6.3 Erro de Memória (mkl_malloc)

**Sintoma:** `mkl_malloc failure` na CPU  
**Causa:** Modelo Whisper inadequado  
**Solução:** Confirmar que está usando `MODELO_WHISPER="tiny"`  
```bash
echo $MODELO_WHISPER  # Deve imprimir "tiny"
```

---

## 7. Pós-Produção

### 7.1 Backup para Drive

Se `DIR_DRIVE_GIRO` estiver configurado e acessível:

```bash
# Copiar programas para o Drive
cp data/output/GIRO_COMARCAS/GNC_01*.mp3 \
   "$DIR_DRIVE_GIRO/"
```

### 7.2 Registro de Produção

Criar planilha de controle:
```csv
Programa,Data_Processamento,Notas_Incluidas,Duracao_Total,Status
0101,2026-01-06,10,12:34,CONCLUÍDO
0102,2026-01-13,9,11:45,CONCLUÍDO
...
```

### 7.3 Limpeza de Cache (Opcional)

Após validação:
```bash
# Manter apenas estado e programas finais
rm -rf data/processed/GIRO_COMARCAS/transcricoes_cache/
```

---

## 8. Checklist de Produção

### Antes de Iniciar
- [ ] Vinhetas presentes em `assets/vinhetas/giro/`
- [ ] Boletins de janeiro disponíveis em `data/input/JORNAIS/`
- [ ] Variável `MODELO_WHISPER="tiny"` configurada
- [ ] Espaço em disco suficiente (~2GB livres)

### Durante o Processamento
- [ ] Monitorar logs em tempo real: `tail -f logs/giro/giro_processamento.log`
- [ ] Verificar progresso de transcrição
- [ ] Validar primeiras notas cortadas

### Após Conclusão
- [ ] Todos os 4 programas gerados em `data/output/GIRO_COMARCAS/`
- [ ] Duração de cada programa entre 10-15 min
- [ ] Logs sem erros críticos
- [ ] Backup realizado no Drive (se aplicável)

---

## 9. Comandos Rápidos de Referência

```bash
# Processar janeiro completo
python -m src.giro.cli data/input/JORNAIS --ano 2026 --verbose

# Processar apenas o programa 0103
python -m src.giro.cli data/input/JORNAIS --mmss 0103 --ano 2026

# Ver programas gerados
ls -lh data/output/GIRO_COMARCAS/

# Ver logs recentes
tail -50 logs/giro/giro_processamento.log

# Reexecutar montagem de um programa
python -c "from giro.montagem import montar_programa; montar_programa('0102', 2026)"
```

---

## 10. Responsáveis e Contatos

| Função | Responsável | Contato |
|--------|-------------|---------|
| Operação do Pipeline | Agente Autônomo | Via logs |
| Validação de Conteúdo | Operador Humano | - |
| Suporte Técnico | Desenvolvimento | GitHub Issues |

---

**Documento criado em:** 2026-01-XX  
**Versão:** 1.0  
**Status:** Pronto para produção  
