# Melhorias no Pipeline de Boletins - TJRN

## Problema Identificado
O pipeline de boletins estava com dificuldades para:
1. Encontrar limites precisos dos boletins quando passados com roteiro
2. Detectar claquetes (marcadores B1, B2, etc.)
3. Identificar assinaturas de locutores
4. Fazer divisões corretas entre trechos dos boletins

## Melhorias Implementadas

### 1. Detecção Aprimorada de Marcadores de Boletim (`segmentacao_boletins.py`)

**Antes:** Apenas buscava padrão "B1", "B2", etc.

**Agora:** Multi-estratégia:
- **Estratégia 1:** Padrão principal "Bn" (B1, B2, B3...)
- **Estratégia 2:** Padrões alternativos ("boletim 1", "bulletin 1", "bloco 1", "parte 1")
- **Estratégia 3:** Inferência por gaps de silêncio quando poucos marcadores são detectados

```python
def detectar_marcadores_boletim(transcricao):
    # 1. Busca padrão Bn
    # 2. Busca padrões alternativos
    # 3. Infere por gaps de silêncio se necessário
```

### 2. Detecção Aprimorada de Assinaturas (`config.py` + `deteccao.py`)

**Antes:** Regex simples e rígida

**Agora:** Sistema em camadas:

#### Configuração Expandida (`config.py`)
```python
# Padrão primário ampliado
_PADRAO_ASSINATURA_NORMALIZADA = re.compile(
    r"(?:tribunal de justica(?:\s+do)?\s+(?:rio grande do)?\s+norte|"
    r"radio justica|justica FM|boletim informativo)"
    r"(?:\s+para a\s+radio(?:\s+justica)?|\s+da\s+hora)?[\s,]+"
    r"(?:[A-Za-z]+\s+)?[A-Za-z]+(?:\s+[A-Za-z]+)*\s*$"
)

# Padrões alternativos de fallback
_PADROES_ASSINATURA_ALTERNATIVOS = [
    re.compile(r"\b(?:leonardo|samuel|marcos|ana|paula)\s+[A-Za-z]+\b"),
    re.compile(r"\breportagem\s+(?:de|:)\s*[A-Za-z]+\b"),
    re.compile(r"\blocucao\s+(?:de|:)\\s*[A-Za-z]+\b"),
]
```

#### Detecção em Camadas (`deteccao.py`)
```python
def detectar_fim_corpo(segmentos, ancora_encerramento, duracao_total, logger):
    # 1. Regex primária + confirmação por timing
    # 2. Padrões alternativos de assinatura
    # 3. Heurística de capitalização (nomes próprios)
    # 4. Âncora de encerramento confirmada
    # 5. Margem de segurança sobre âncora
```

### 3. Novo Módulo de Alinhamento de Roteiro (`alinhamento_roteiro.py`)

**Funcionalidade:** Quando o roteiro está disponível, alinha o texto exato do roteiro com a transcrição Whisper para encontrar limites precisos.

**Recursos:**
- Extração de CABEÇA e OFF do roteiro (suporta múltiplos formatos)
- Normalização robusta (acentos, pontuação, espaços)
- Alinhamento por janela deslizante com SequenceMatcher
- Score combinado (similaridade + overlap de palavras-chave)
- Integração com fallback para estratégias existentes

**Uso:**
```python
from divisor_boletins.alinhamento_roteiro import integrar_alinhamento_roteiro

resultado = integrar_alinhamento_roteiro(
    segmentos=segmentos_whisper,
    texto_roteiro=roteiro_google_doc,
    duracao_total=duracao,
    fallback_strategy="ancoras_vad"
)

if not resultado["fallback_necessario"]:
    inicio_cabeca = resultado["inicio_cabeca"]
    fim_cabeca = resultado["fim_cabeca"]
    inicio_corpo = resultado["inicio_corpo"]
    fim_corpo = resultado["fim_corpo"]
```

### 4. Configurações Ajustadas (`config.py`)

- Janela de passagem ampliada (7s-25s) para evitar confusão gap vinheta→manchete
- Limiares calibrados para detecção de âncoras
- Suporte a variações de texto nas vinhetas

## Como Usar

### Pipeline com Roteiro Disponível
```python
from src.divisor_boletins.audio import processar_arquivo
from src.divisor_boletins.alinhamento_roteiro import integrar_alinhamento_roteiro

# 1. Transcrever
segmentos, texto = transcrever_audio(caminho_audio, modelo, logger)

# 2. Tentar alinhamento com roteiro
resultado = integrar_alinhamento_roteiro(
    segmentos, texto_roteiro, duracao_total
)

# 3. Se falhar, usar estratégias padrão
if resultado["fallback_necessario"]:
    processar_arquivo(
        caminho_audio, pasta_saida, modelo, logger,
        estrategia="calibracao_correlacao"
    )
```

### Pipeline Sem Roteiro (Melhorias Automáticas)
As melhorias de detecção de marcadores e assinaturas são aplicadas automaticamente.

## Benefícios Esperados

1. **Maior precisão na detecção de limites** - especialmente quando há roteiro
2. **Menos cortes incorretos** - detecção de assinaturas mais robusta
3. **Fallback automático** - múltiplas estratégias em cascata
4. **Logs detalhados** - cada decisão é registrada para auditoria
5. **Suporte a variações** - diferentes formatos de roteiro e assinatura

## Arquivos Modificados

- `/workspace/src/divisor_boletins/config.py` - Padrões de assinatura expandidos
- `/workspace/src/divisor_boletins/deteccao.py` - Detecção de fim_corpo em camadas
- `/workspace/src/gravador_inteligente/segmentacao_boletins.py` - Detecção multi-estratégia de marcadores
- `/workspace/src/divisor_boletins/alinhamento_roteiro.py` - NOVO: módulo de alinhamento

## Próximos Passos Sugeridos

1. Integrar `alinhamento_roteiro.py` no `audio.py` como estratégia prioritária
2. Adicionar suporte a download automático de roteiros do Google Docs
3. Criar testes unitários para cada estratégia de detecção
4. Documentar casos de uso específicos do TJRN
