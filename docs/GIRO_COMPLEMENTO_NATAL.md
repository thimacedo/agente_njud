# Complemento de Notas no GIRO - Mecanismo de Fallback para Natal

## Problema Identificado

No processamento do GIRO nas Comarcas, o filtro geográfico padrão exclui notícias de Natal para priorizar cidades do interior do RN. Porém, em semanas com poucas notas disponíveis, isso pode resultar em programas com menos de 3 notas, comprometendo a qualidade do conteúdo.

**Exemplo do log:**
```
2026-09-07 14:00:40 | INFO | [pipeline]   Boletim processado: 0/1 notas aceitas
...
2026-09-07 14:01:19 | INFO | [seleção]   0202: 3 notas aceitas (de 50 boletins processados)
```

Neste caso, de 50 boletins processados, apenas 3 notas foram aceitas - todas de outras cidades. Se houvesse menos de 3, o programa ficaria incompleto.

## Solução Implementada

### Novo Parâmetro `--min-notas`

Adicionado ao CLI do GIRO:
```bash
python -m src.giro.cli data/input/JORNAIS --ano 2026 --mmss 0202 --min-notas 3
```

**Comportamento:**
1. **Primeira passada**: Processa todos os boletins com `evitar_natal=True` (filtro padrão)
2. **Verificação**: Se total de notas aceitas < `min_notas_programa`:
   - Log informativo é gerado
   - Re-processa todos os boletins com `evitar_natal=False`
   - Aceita notícias de Natal (prioritariamente institucionais do TJRN)
3. **Segunda verificação**: Se ainda assim não atingir o mínimo, mantém as notas disponíveis

### Código Adicionado (`src/giro/cli.py`)

```python
# ---- Complementar com Natal se necessário ----
if len(notas_aceitas_total) < min_notas_programa and evitar_natal:
    log_info(
        "seleção",
        f"  {mmss}: apenas {len(notas_aceitas_total)} notas aceitas "
        f"(mínimo desejado: {min_notas_programa}). "
        f"Reprocessando sem filtro de Natal...",
    )
    # Re-processar boletins já filtrados por Natal, agora aceitando
    idx_nota_global = 0
    notas_aceitas_total = []
    modelo_whisper = None

    for boletim_path, data_boletim in boletins_no_periodo:
        # ... re-processa com evitar_natal=False
```

## Critérios para Aceitar Notícias de Natal

Quando o fallback é acionado, o filtro `filtrar_nota()` no `src/giro/filtro.py` aceita notícias de Natal que:

1. **Mencionam instituições do RN** (prioritário):
   - "Tribunal de Justiça do Rio Grande do Norte"
   - "TJRN"
   - "Justiça do RN"

2. **São de órgãos estaduais**:
   - Assembleia Legislativa do RN
   - Governo do Estado
   - Secretarias Estaduais

3. **Não são meramente locais**:
   - Evita notícias de varas específicas de bairros
   - Prioriza decisões de impacto estadual

## Fluxo Operacional

### Cenário Normal (≥3 notas de outras cidades)
```
Boletins → Transcrição → Filtro (Natal EXCLUÍDO) → ≥3 notas → Programa montado
```

### Cenário de Fallback (<3 notas)
```
Boletins → Transcrição → Filtro (Natal EXCLUÍDO) → <3 notas
       ↓
Re-processamento → Filtro (Natal INCLUÍDO) → ≥3 notas → Programa montado
```

### Cenário Crítico (<3 notas mesmo com Natal)
```
Boletins → Transcrição → Filtro (Natal INCLUÍDO) → <3 notas
       ↓
Programa montado com notas disponíveis (status: "sem_notas" se 0)
```

## Exemplo de Uso

### Processamento Padrão (fallback automático)
```bash
python -m src.giro.cli data/input/JORNAIS \
    --ano 2026 \
    --mmss 0202 \
    --verbose
```

### Forçar Mínimo de 5 Notas
```bash
python -m src.giro.cli data/input/JORNAIS \
    --ano 2026 \
    --mmss 0202 \
    --min-notas 5 \
    --verbose
```

### Desativar Filtro de Natal Completamente
```bash
python -m src.giro.cli data/input/JORNAIS \
    --ano 2026 \
    --mmss 0202 \
    --nao-evitar-natal
```

## Logs Esperados

### Caso Normal (suficientes notas do interior)
```
[seleção]   0202: 5 notas aceitas (de 42 boletins processados)
```

### Caso de Fallback Acionado
```
[seleção]   0202: 2 notas aceitas (de 38 boletins processados)
[seleção]   0202: apenas 2 notas aceitas (mínimo desejado: 3). Reprocessando sem filtro de Natal...
[nota]   Re-processando boletim BOLETIM_RADIO_TJRN_03_02_2026_B1_...mp3 (2026-02-03)...
[nota]   Nota 4 ACEITA: GNC_0202_N03_03-02-26.mp3 (Notícia do RN — menciona Tribunal de Justiça do RN)
[seleção]   0202: 4 notas aceitas após relaxar filtro de Natal
```

## Configuração Recomendada

| Período | `--min-notas` | Justificativa |
|---------|---------------|---------------|
| Janeiro | 3 | Mês curto, férias forenses |
| Fevereiro | 3 | Retorno gradual |
| Março-Junho | 4-5 | Período normal de trabalho |
| Julho | 3 | Férias forenses de julho |
| Agosto-Novembro | 4-5 | Período normal |
| Dezembro | 3 | Encerramento de ano |

## Validação

Após processamento, verificar:
1. Número de notas no programa montado (deve ser ≥ `min_notas`)
2. Qualidade das notas de Natal incluídas (devem ser institucionais)
3. Logs em `logs/giro/giro_processamento.log`

## Próximos Passos (Opcional)

- [ ] Criar relatório de quantas vezes o fallback foi acionado por mês
- [ ] Ajustar `min_notas` dinamicamente conforme período do ano
- [ ] Priorizar notícias de Natal por tipo institucional automaticamente
