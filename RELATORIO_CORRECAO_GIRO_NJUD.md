# RELATÓRIO COMPLETO DE PRODUÇÃO E CORREÇÃO — GIRO e NJUD

**Data:** 2026-09-09  
**Autor:** Agente GIRO (Thiago Macedo)  
**Status:** Crítico — produção bloqueada por erro de vinheta de boletim  

---

## 1. SITUAÇÃO ATUAL DA PRODUÇÃO GIRO

### 1.1 Dados Consolidados

| Localização | Conteúdo | Count | Status |
|---|---|---|---|
| `E:\...\DIVISOR\GIRO\` | Arquivos fonte BOLETIM_RADIO_TJRN_*.mp3 | 673 | ✅ Limpo |
| `E:\...\DIVISOR\data\output\GIRO_COMARCAS\` | GNCs gerados | 0 | ⚠️ APAGADO PELO USUÁRIO |
| `E:\...\DIVISOR\data\processed\PRODUCAO_2026\GIRO_COMARCAS\` | Diretórios de programa | 28 | ✅ Preservado |
| `H:\...\03_GIRO_NAS_COMARCAS\` | GNCs sincronizados | 28 | ✅ Preservado |
| `E:\...\DIVISOR\assets\vinhetas\boletim\` | Vinhetas de boletim (VHT_ABERTURA, VHT_PASSAGEM, VHT_ENCERRAMENTO) | 3 .mp3 | ⚠️ CAUSA RAIZ |
| `E:\...\DIVISOR\assets\vinhetas\giro\` | Vinhetas de giro (VHT_ABERTURA_GIRO, VHT_PASSAGEM_GIRO, VHT_ENCERRAMENTO_GIRO) | 3 .mp3 | ✅ Corretas |
| `E:\...\DIVISOR\assets\vinhetas\njud\` | Vinhetas de NJUD | 5 arquivos | ✅ Corretas |

### 1.2 Problema Principal

**O usuário apagou `data/output/GIRO_COMARCAS/` e os programas continuam saindo com vinhetas de boletim.** Isso indica que:

1. A montagem (`montagem.py`) carrega vinhetas de GIRO (`assets/vinhetas/giro/`) — funcional
2. Os cortes estão produzindo áudio que **já contém vinheta de boletim embutida**
3. A causa raiz: os **cortes (`divisor_boletins.audio.processar_arquivo`)** estão operando em áudio bruto de boletim sem remover a vinheta antes do corte

### 1.3 Causa Raiz Identificada

O pipeline tem **3 estágios independentes** que não estão coordenados:

1. **Separação de stems** (`core/stems/separacao_stems.py`) — opcional, `usar_separacao_stems=False` por padrão em todos os JSONs de planejamento
2. **Corte** (`divisor_boletins.audio.processar_arquivo`) — opera no áudio original (sem stem limpeza)
3. **Montagem** (`src/giro/montagem.py`) — adiciona vinhetas de GIRO corretas por cima

**Se o estágio 1 está desabilitado (`usar_separacao_stems=False`), o estágio 2 corta o áudio bruto do boletim que ainda contém a trilha/locução de boletim original, incluindo a vinheta de abertura.** O estágio 3 então adiciona vinhetas de GIRO por cima — resultado: VINHETA DE BOLETIM + VINHETA DE GIRO = erro audível.

---

## 2. ANÁLISE ARQUITETURAL DO PIPELINE

### 2.1 Fluxo Corrente (com problemas)

```
BOLETIM_RADIO_TJRN_*.mp3 (fonte)
    │
    ├── [ETAPA 0 - OPCAO] Separar stems (Demucs, dois-stems=vocals)
    │     └── Se usar_separacao_stems=False → PULADO → áudio bruto mantido
    │
    ├── [ETAPA 1] Corte (divisor_boletins.audio.processar_arquivo)
    │     ├── Estratégias: calibracao_correlacao, ancora_vad_forcado, etc.
    │     ├── Output: CABECA + CORPO (arquivos JORNAIS_DIVIDIDOS/)
    │     └── PROBLEMA: opera em áudio bruto se ETAPA 0 pulada
    │
    ├── [ETAPA 2] Auditoria (core/auditoria/regras.py)
    │     ├── RegraSemFallbackParaAudioCompleto (obrigatória)
    │     ├── RegraDurationsValidas
    │     ├── RegraCabecaCorpoExistentes
    │     └── RegraSemAlucinacoesWhisper
    │
    ├── [ETAPA 3] Extração de notas (src/giro/transcricao.py)
    │     ├── _detectar_notas_por_assinatura (LOC/OFF TJRN)
    │     ├── _detectar_notas_por_silencio (gaps na transcrição)
    │     └── cortar_nota() — recorta do boletim original
    │
    └── [ETAPA 4] Montagem (src/giro/montagem.py)
          ├── VHT_ABERTURA_GIRO → Abertura correta
          ├── Para cada nota: VHT_PASSAGEM_GIRO + Nota (cortada do boletim)
          └── VHT_ENCERRAMENTO_GIRO → Encerramento correto
```

### 2.2 Onde a Vinheta de Boletim Entra

A vinheta de boletim (`VHT_ABERTURA_BOLETIM.mp3`) entra em duas vias:

**Via A — Áudio bruto:** Quando `usar_separacao_stems=False`, o áudio do boletim não é processado para remover a vinheta. O corte (`processar_arquivo`) faz o corte no áudio bruto onde a vinheta de abertura do boletim ainda está presente no início do arquivo CABEÇA.

**Via B — Nota cortada:** A `extrair_notas()` em `transcricao.py` detecta notas pela assinatura LOC/OFF TJRN. Quando a primeira nota começa logo após a vinheta de abertura do boletim, o corte começa naquele ponto — mas o áudio de abertura do boletim (com a vinheta) fica de fora em teoria. **O problema real é que `processar_arquivo` corta CABEÇA e CORPO do boletim original, e o áudio original inclui a vinheta.**

### 2.3 Por Que "Apenas Apagar data/output" Não Resolve

Os GNCs em `data/output/` são o **resultado final** da montagem. Se o estágio anterior (corte) ainda produz CABEÇA/CORPO com vinheta embutida, re-executar a montagem regenera o mesmo problema. É preciso corrigir na **fonte do corte** ou na **preparação do áudio de entrada**.

---

## 3. DIAGNÓSTICO DETALHADO DOS FALHOS

### 3.1 Separação de Stems — DESABILITADA

- **Local:** `config/planejamento_2026/giro_*.json` → `"usar_separacao_stems": false`
- **Impacto:** Demucs não é executado → vinheta de boletim permanece no áudio de corte
- **Código:** `executar_programa.py` → `usar_separacao_stems=json_config.get("parametros", {}).get("usar_separacao_stems", ...)`
- **Correção necessária:** Alterar para `true` nos JSONs de planejamento, OU adicionar lógica de remoção de vinheta de boletim antes do corte

### 3.2 Detecção de Notas — FUNCIONAL MAS FRAGIL

- **`_detectar_notas_por_assinatura`** detecta início de nota por `Tribunal de Justiça do Rio Grande do Norte`
- **`_detectar_notas_por_silencio`** detecta gaps ≥ 2.5s entre segmentos whisper
- **Problema:** Se o primeiro segmento de um boletim começa com a vinheta de abertura, a assinatura TJRN aparece no meio (não no início), fazendo com que a detecção de notas comece **antes** da primeira assinatura real
- **Código:** `src/giro/transcricao.py` linhas 216-254

### 3.3 Montagem — CORRETA MAS DEPENDE DA ENTRADA

- **`montar_programa()`** carrega corretamente: `VHT_ABERTURA_GIRO.mp3`, `VHT_PASSAGEM_GIRO.mp3`, `VHT_ENCERRAMENTO_GIRO.mp3` de `assets/vinhetas/giro/`
- **Estrutura:** Vinheta_abertura → [VHT_PASSAGEM + Nota] × N → VHT_ENCERRAMENTO
- **Problema:** Se a "Nota" já contém vinheta de boletim (porque o corte falhou), a montagem adiciona vinhetas de GIRO por cima
- **Código:** `src/giro/montagem.py` — funcional, mas depende de corte limpo

### 3.4 RegraSemFallbackParaAudioCompleto — EXISTE MAS NÃO PREVENDE VINHETA

- **Função:** Detecta se proporção de corte > 95% (corte não aconteceu)
- **Limitação:** Quando o corte "funciona" mas inclui a vinheta de boletim na CABEÇA, a proporção pode ser normal (~50-80%), passando pela auditoria
- **Código:** `src/core/auditoria/regras.py` classe `RegraSemFallbackParaAudioCompleto`

### 3.5 Vinhetas de Boletim — PRESENTES EM assets/

- `assets/vinhetas/boletim/VHT_ABERTURA_BOLETIM.mp3` (266KB)
- `assets/vinhetas/boletim/VHT_PASSAGEM_BOLETIM.mp3` (29KB)
- `assets/vinhetas/boletim/VHT_ENCERRAMENTO_BOLETIM.mp3` (259KB)

**Estas vinhetas estão no diretório de assets mas NÃO são usadas em nenhum ponto do pipeline de GIRO ou NJUD.** Elas só existem como referência. O pipeline não as remove do áudio de entrada.

---

## 4. CORREÇÃO NECESSÁRIA — PROCEDIMENTO COMPLETO

### 4.1 Estratégia de Correção (3 camadas)

| Camada | Ação | Prioridade | Complexidade |
|---|---|---|---|
| **A** | Inserir remoção de vinheta de boletim como etapa obrigatória antes do corte | 🔴 Alta | Média |
| **B** | Habilitar `usar_separacao_stems=true` nos JSONs de planejamento | 🟡 Média | Baixa |
| **C** | Adicionar detector de vinheta na etapa de cortes (debug/visualização) | 🟢 Baixa | Baixa |

### 4.2 Camada A: Remoção de Vinheta como Etapa Obrigatória

**Problema:** O áudio de boletim contém a vinheta de abertura no início. Quando o corte acontece, a vinheta é incluída na primeira CABEÇA.

**Solução:** Criar uma função `remover_vinheta_boletim()` que:
1. Carrega `VHT_ABERTURA_BOLETIM.mp3` como referência
2. Transcreve o início do áudio do boletim
3. Se a vinheta for detectada nos primeiros segundos, corta essa região
4. Exporta o áudio "limpo" para uso no corte

**Implementação proposta em `src/giro/transcricao.py`:**

```python
def remover_vinheta_boletim(
    caminho_audio: Path,
    caminho_vinheta: Path,
    limiar_confianca: float = 0.5,
) -> Optional[AudioSegment]:
    """
    Remove a vinheta de abertura do boletim antes do corte.
    
    Usa transcrição para detectar se a vinheta está presente no início
    do áudio. Se detectada, remove essa região e retorna o áudio limpo.
    
    Returns:
        Áudio limpo (sem vinheta), ou None se não conseguir processar
    """
```

**Local de chamada:** `src/core/processamento/processar_boletim.py` na função `processar_um_arquivo()`, ANTES de chamar `processar_arquivo()`.

### 4.3 Camada B: Habilitar Separação de Stems

**Modificação:** Em todos os `config/planejamento_2026/giro_*.json`, alterar:
```json
"usar_separacao_stems": false
```
para:
```json
"usar_separacao_stems": true
```

**Nota:** Demucs é pesado (600s timeout por arquivo). Para 673 arquivos, isso adiciona tempo significativo. **Alternativa:** usar o modo de cache — se o stem vocal já foi processado (cache hit), é instantâneo.

### 4.4 Camada C: Detector de Vinheta na Etapa de Cortes

**Problema do usuário:** "isto é um erro que deveria sido visto de forma simples na etapa de cortes"

**Solução:** Adicionar um `VinhetaDetector` que verifica, após o corte, se o arquivo CABEÇA gerado contém a vinheta de boletim:

```python
class RegraVinhetaBoletimAusente:
    """Detecta se a vinheta de boletim ainda está presente no corte."""
    
    nome = "vinheta_boletim_ausente"
    
    def verificar(self, auditavel: Auditavel, **kwargs) -> tuple[bool, Optional[str]]:
        # Transcreve início do CABEÇA
        # Se encontrar palavras-chave da vinheta de boletim → FALHA
        # Se não encontrar → OK
```

**Local:** `src/core/auditoria/regras.py` — adicionar nova regra à lista.

### 4.5 Inversão de Vinheta para Subtração de Frequência

**Pergunta do usuário:** "é necessário fazer algum outro processo, como inverter a vinheta para subtrair a frequencia?"

**Resposta:** **Não.** Inversão de fase (phase inversion) para subtração de frequência funciona quando:
- A vinheta está exatamente sincronizada com o áudio original
- Ambos têm o mesmo sample rate e número de canais
- A vinheta é uma cópia exata do trecho original

**Na prática:** A vinheta de boletim (`VHT_ABERTURA_BOLETIM.mp3`) é um arquivo independente gravado. Não é uma cópia exata do trecho no boletim original. A subtração de fase não funcionaria confiavelmente.

**Melhor abordagem:** Remoção baseada em **transcrição + detecção de fronteira** (Camada A acima).

### 4.6 Divisão de Stems — Está Funcionando?

**Sim, mas está desabilitada.** O módulo `core/stems/separacao_stems.py`:
- Funciona via Demucs (`htdemucs`, `two-stems=vocals`)
- Tem cache de disco (funciona com `cache_dir: Path("data/cache_stems")`)
- Pós-processamento verifica se vinhetas ainda aparecem no stem vocal
- **Ponto fraco:** `usar_separacao_stems=False` em todos os planejamentos

**Recomendação:** Testar com `usar_separacao_stems=true` para 1-2 programas piloto antes de habilitar em massa (673 arquivos).

---

## 5. PROJETO DE CORREÇÃO — GIRO

### 5.1 Estrutura de Arquivos

```
E:\...\DIVISOR\
├── src/giro/
│   ├── transcricao.py          ← ADICIONAR: remover_vinheta_boletim()
│   ├── filtro.py               ← NÃO MODIFICAR
│   ├── montagem.py             ← NÃO MODIFICAR (funcional)
│   └── config.py               ← NÃO MODIFICAR (funcional)
├── src/core/
│   ├── processamento/
│   │   └── processar_boletim.py ← MODIFICAR: chamar remover_vinheta_boletim()
│   ├── auditoria/
│   │   └── regras.py           ← ADICIONAR: RegraVinhetaBoletimAusente
│   └── stems/
│       └── separacao_stems.py  ← NÃO MODIFICAR (funcional)
├── config/
│   └── planejamento_2026/
│       └── giro_*.json         ← MODIFICAR: "usar_separacao_stems": true
├── scripts_pipeline/
│   └── executar_programa.py    ← NÃO MODIFICAR (funcional)
└── assets/vinhetas/boletim/    ← NÃO MODIFICAR (referência)
```

### 5.2 Ordem de Implementação

1. **Fase 1 — Preparação (1 hora)**
   - Habilitar `usar_separacao_stems: true` em todos os `giro_*.json`
   - Verificar se Demucs funciona no ambiente (CPU only, i5-8600K)
   - Testar pipeline completo com 1 programa (ex: 0701)

2. **Fase 2 — Remoção de Vinheta (2 horas)**
   - Implementar `remover_vinheta_boletim()` em `transcricao.py`
   - Integrar em `processar_boletim.py` antes do corte
   - Testar com áudio de boletim real

3. **Fase 3 — Detector de Vinheta (1 hora)**
   - Implementar `RegraVinhetaBoletimAusente` em `regras.py`
   - Adicionar ao `Auditor` em `processar_boletim.py`
   - Gerar relatório visual simples (texto)

4. **Fase 4 — Rebuild Completo (2-4 horas)**
   - Limpar `data/processed/PRODUCAO_2026/GIRO_COMARCAS/`
   - Limpar `data/output/GIRO_COMARCAS/`
   - Re-executar pipeline completo para 28 programas
   - Sincronizar com H:\03_GIRO_NAS_COMARCAS\

5. **Fase 5 — Verificação (1 hora)**
   - Verificar que GNCs NÃO contêm vinheta de boletim
   - Confirmar contagem de 4-6 notas por programa
   - Confirmar estrutura vinheta→manchete→passagem→nota→...→vinheta

---

## 6. PROJETO DE CORREÇÃO — NJUD

### 6.1 Diferença Arquitetural NJUD vs GIRO

O NJUD tem a mesma estrutura de pipeline (stems → corte → auditoria → montagem), mas com diferenças cruciais:

| Aspecto | GIRO | NJUD |
|---|---|---|
| Fonte | `BOLETIM_RADIO_TJRN_*.mp3` | `JORNAIS_DIVIDIDOS/<data>/` (CABECA+CORPO) |
| Vinheta | `VHT_ABERTURA_BOLETIM.mp3` | `VHT_ABERTURA_NJUD.mp3` |
| Separação | `usar_separacao_stems=false` | `usar_separacao_stems`? |
| Estrutura | Notas individuais | CABEÇA + CORPO |

### 6.2 Estado NJUD

- `data/output/JORNAIS_FINAL/` contém 75 .mp3s (NJUDs prontos)
- `src/config/njud.py` contém configurações NJUD
- `src/core/processamento/processar_boletim.py` é compartilhado (funciona para ambos)
- JSONs de planejamento NJUD existem em `config/planejamento_2026/`

### 6.3 Risco NJUD

**Se o NJUD usa `usar_separacao_stems=true`, a vinheta de boletim não é um problema para NJUD** (já que o corte usa o stem vocal). Mas se NJUD também usa `false`, o mesmo problema pode ocorrer.

**Ação necessária:** Verificar `usar_separacao_stems` nos JSONs de planejamento NJUD e comparar com GIRO.

---

## 7. RESUMO EXECUTIVO

### O que está funcionando:
- ✅ 28 programas GIRO montados e sincronizados para H:\
- ✅ Estrutura de montagem correta (vinhetas GIRO adequadas)
- ✅ Separação de stems funcional (mas desabilitada)
- ✅ Detecção de notas por assinatura funcional
- ✅ RegraSemFallbackParaAudioCompleto implementada
- ✅ Persistência de estado funcional

### O que está quebrado:
- ❌ Vinheta de boletim embutida nos cortes (causa raiz)
- ❌ `usar_separacao_stems=false` em todos os JSONs de planejamento GIRO
- ❌ Sem detector de vinheta na etapa de cortes (incapaz de visualizar o erro)
- ❌ Nenhum procedimento de remoção de vinheta antes do corte

### Solução mínima viável:
1. Habilitar `usar_separacao_stems: true` nos JSONs → Demucs remove vinheta automaticamente
2. Se Demucs for lento/heavy, implementar `remover_vinheta_boletim()` como alternativa leve
3. Adicionar `RegraVinhetaBoletimAusente` para detector o erro na auditoria

### Solução ideal:
1. **Camada A + B + C** implementadas conforme seção 4
2. **Pipeline rebuild completo** para todos os 28 programas
3. **Verificação automatizada** que falha se vinheta de boletim for detectada

---

## 8. NOTAS TÉCNICAS

### 8.1 Por Que Não É Inversão de Frequência
- Inversão de fase requer cópia exata do trecho — impossível com vinheta de referência gravada separadamente
- Demucs `two-stems=vocals` já resolve isso separando locução da música/trilha
- Abordagem baseada em transcrição é mais robusta

### 8.2 Demucs no i5-8600K
- CPU-only (sem GPU dedicada)
- Modelo `htdemucs` funcional mas lento
- Tempo estimado: ~2-5 min por arquivo (600s timeout)
- Para 673 arquivos: ~22-56 horas de processamento
- **Cache resolve:** após primeiro processamento, cache hit é instantâneo

### 8.3 Regra Geográfica Não Afetada
- `RN_CIDADES`, `OUTROS_ESTADOS_PALAVRAS`, `NATAL_PALAVRAS` em `src/giro/config.py` continuam funcionando
- A correção da vinheta não afeta o filtro geográfico
- Regra de fallback RN-interior/Natal permanece intacta

---

*Fim do relatório.*
