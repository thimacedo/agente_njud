# Plano de Produção GIRO — Janeiro/2026

## Visão Geral

Produção de 4 programas GIRO nas Comarcas referentes a janeiro de 2026,
a serem veiculados nas terças-feiras de janeiro.

## Pré-requisitos

### Estrutura de Diretórios

```
assets/vinhetas/giro/
├── VHT_ABERTURA_GIRO.mp3
├── VHT_PASSAGEM_GIRO.mp3
└── VHT_ENCERRAMENTO_GIRO.mp3

data/
├── processed/GIRO_COMARCAS/
│   ├── estado/
│   └── <mmss>/
├── output/GIRO_COMARCAS/
└── cache/giro/transcricoes/

logs/giro/
```

### Variáveis de Ambiente (.env)

| Variável | Valor Padrão | Descrição |
|---|---|---|
| `MODELO_WHISPER` | `tiny` | Modelo Whisper (tiny evita MKL OOM) |
| `COMPUTE_TYPE` | `int8` | Tipo de computação CPU |
| `GNC_DRIVE_SYNC` | `H:\Meu Drive\...` | Pasta de destino no Drive |
| `LIMIAR_ANCORA_GIRO` | `0.55` | Similaridade mínima para âncoras |
| `LIMIAR_FIM_PASSAGEM_GIRO` | `0.8` | Gap mínimo para fim de passagem |
| `LIMIAR_INICIO_FALA_GIRO` | `0.3` | Gap mínimo para início de fala |

### Vinhetas Necessárias

| Arquivo | Função | Duração Esperada |
|---|---|---|
| `VHT_ABERTURA_GIRO.mp3` | Abertura do programa | ~5s |
| `VHT_PASSAGEM_GIRO.mp3` | Transição entre notas | ~3s |
| `VHT_ENCERRAMENTO_GIRO.mp3` | Encerramento do programa | ~5s |

## Calendário de Produção

| Programa | Data Veiculação | Código | Período das Notícias |
|---|---|---|---|
| Semana 1 | 06/01/2026 (terça) | `0101` | 29/12 a 04/01 |
| Semana 2 | 13/01/2026 (terça) | `0102` | 05/01 a 11/01 |
| Semana 3 | 20/01/2026 (terça) | `0103` | 12/01 a 18/01 |
| Semana 4 | 27/01/2026 (terça) | `0104` | 19/01 a 25/01 |

## Fluxo de Processamento

### 1. Gerar Plano

```bash
cd E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR
python -m giro E:/JORNAIS/ --lista-plano --ano 2026
```

### 2. Processar Programa (transcrição + filtro + corte)

```bash
# Programa 0101 (exemplo)
python -m giro E:/JORNAIS/ --mmss 0101 --ano 2026 --verbose

# Processar todos de janeiro
python -m giro E:/JORNAIS/ --ano 2026 --verbose
```

### 3. Montar Programa

```bash
python -m giro --montar data/processed/GIRO_COMARCAS/ --mmss-list 0101,0102,0103,0104
```

### 4. Copiar para Drive

Os programas montados em `data/output/GIRO_COMARCAS/` devem ser copiados para:
```
H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026\02_JORNAIS_GIRO\03_AUDIOS_RADIO\
```

## Critérios de Qualidade

### Filtro Geográfico

- **Excluídos automaticamente:** Notícias de outros estados (fora RN)
- **Evitadas:** Notícias exclusivamente sobre Natal (configurável com `--nao-evitar-natal`)
- **Aceitas:** Notícias de cidades do interior do RN (167 municípios)

### Validação de Áudio

- Duração mínima de nota: 2.0s
- Duração mínima de programa: 60.0s
- Sem cortes no meio da fala (verificado por energia RMS nas bordas)
- Sem alucinações conhecidas do Whisper

### Duração Esperada

| Componente | Duração |
|---|---|
| Abertura | ~5s |
| Cada nota | 15-45s |
| Passagem entre notas | ~3s |
| Encerramento | ~5s |
| **Programa total** | **3-8 min** |

## Monitoramento e Logs

### Arquivos de Log

```
logs/giro/
├── giro_processamento.log    # Log principal de processamento
└── giro_montagem.log         # Log de montagem dos programas
```

### Comandos de Verificação

```bash
# Verificar notas processadas
ls data/processed/GIRO_COMARCAS/0101/

# Verificar programas montados
ls data/output/GIRO_COMARCAS/

# Verificar erros nos logs
grep -i "erro\|ERRO" logs/giro/giro_processamento.log

# Verificar cache de transcrições
ls data/cache/giro/transcricoes/ | wc -l
```

## Tratamento de Erros

| Problema | Causa | Solução |
|---|---|---|
| `mkl_malloc failure` | Modelo Whisper grande demais | Usar `MODELO_WHISPER=tiny` (padrão) |
| `ModuleNotFoundError: faster-whisper` | Dependência não instalada | `pip install faster-whisper` |
| Cache corrompido | Interrupção durante escrita | `rm -rf data/cache/giro/transcricoes/*` |
| Poucas notas aceitas | Filtro geográfico muito restritivo | Verificar `LIMIAR_ANCORA_GIRO` |
| Áudio vazio na saída | Boletim sem fala detectada | Verificar transcrição no log |
| `Path("logs")` relativo | Bug antigo (corrigido em a1d4a4e) | Atualizar para versão mais recente |

## Pós-Produção

1. **Backup:** Copiar programas montados para Drive
2. **Registro:** Anotar no controle de produção (data, programa, notas aceitas/rejeitadas)
3. **Limpeza:** Remover arquivos temporários de `data/processed/GIRO_COMARCAS/<mmss>/`
4. **Cache:** Manter cache de transcrições para reprocessamento futuro

## Checklist

### Antes do Processamento
- [ ] Vinhetas GIRO presentes em `assets/vinhetas/giro/`
- [ ] Boletins de janeiro disponíveis em `E:/JORNAIS/`
- [ ] `.env` configurado com `MODELO_WHISPER=tiny`
- [ ] Espaço em disco suficiente (~2GB por programa)
- [ ] Pasta do Drive montada (se aplicável)

### Durante o Processamento
- [ ] Log sem erros críticos
- [ ] Notas sendo aceitas (não todas rejeitadas)
- [ ] Cache de transcrições sendo populado
- [ ] Programas montados com duração esperada

### Após o Processamento
- [ ] Programas copiados para Drive
- [ ] Logs revisados
- [ ] Controle de produção atualizado
- [ ] Arquivos temporários limpos

## Comandos Rápidos

```bash
# Setup inicial
cd E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR

# Processar um programa específico
python -m giro E:/JORNAIS/ --mmss 0101 --verbose

# Processar todos os programas de janeiro
python -m giro E:/JORNAIS/ --ano 2026

# Montar programas já processados
python -m giro --montar data/processed/GIRO_COMARCAS/

# Verificar status
ls data/output/GIRO_COMARCAS/*.mp3
ls logs/giro/
```
