# PROJETO DE CORREÇÃO — PIPELINE DO NJUD

**Projeto:** Correção independente do pipeline NJUD  
**Status:** Verificação e correção necessária  
**Data:** 2026-09-09  

---

## 1. SITUAÇÃO ATUAL DO NJUD

### 1.1 Estado Confirmado

| Item | Status | Detalhe |
|---|---|---|
| `data/output/JORNAIS_FINAL/` | 75 .mp3s presentes | NJUDs prontos |
| `src/config/njud.py` | Existe | Configurações NJUD |
| `src/core/processamento/processar_boletim.py` | Compartilhado | Funciona para ambos |
| JSONs de planejamento NJUD | Existem | `config/planejamento_2026/` |
| `usar_separacao_stems` | **DESABILITADO** | `"usar_separacao_stems": false` |
| Vinhetas NJUD em `assets/vinhetas/njud/` | ✅ Presentes | 5 arquivos |

### 1.2 Vinhetas NJUD

```
assets/vinhetas/njud/
├── VHT_ABERTURA_NJUD.mp3
├── VHT_ENCERRAMENTO_NJUD.mp3
├── EFEITO_PASSAGEM_NJUD.mp3
├── RECEITA_NJUD.txt
└── TRILHA_ESCALADA_NJUD.mp3
```

### 1.3 Arquitetura NJUD

```
JORNAIS_DIVIDIDOS/<data>/ (CABEÇA + CORPO)
    │
    ├── [ETAPA 0 - OPCAO] Separar stems (Demucs)
    │     └── usar_separacao_stems=false → PULADO
    │
    ├── [ETAPA 1] Corte (divisor_boletins.audio.processar_arquivo)
    │     ├── Estratégias: calibracao_correlacao, etc.
    │     ├── Output: CABEÇA + CORPO separados
    │     └── PROBLEMA: áudio bruto sem remoção de vinheta
    │
    ├── [ETAPA 2] Auditoria (core/auditoria/regras.py)
    │     ├── RegraSemFallbackParaAudioCompleto
    │     └── Outras regras
    │
    └── [ETAPA 3] Montagem NJUD (divisor_boletins.montagem)
          ├── VHT_ABERTURA_NJUD → Abertura NJUD
          ├── Cabeca + Corpo (cortados)
          ├── EFEITO_PASSAGEM_NJUD → Efeito de passagem
          └── VHT_ENCERRAMENTO_NJUD → Encerramento NJUD
```

---

## 2. PROBLEMA POTENCIAL DO NJUD

### 2.1 Mesmo Problema?

**Sim, potencialmente.** O NJUD também tem `usar_separacao_stems=false`. Isso significa:

1. O corte (`processar_arquivo`) opera no áudio bruto do boletim
2. Se a vinheta de boletim está no início do áudio original, ela pode estar no CABEÇA
3. A montagem NJUD adiciona vinhetas de NJUD por cima

**Diferença:** O NJUD usa `JORNAIS_DIVIDIDOS/` (CABEÇA + CORPO já separados pelo script de divisão original), não `BOLETIM_RADIO_TJRN_*.mp3` (áudio bruto do boletim). Se a divisão CABEÇA/CORPO já removeu a vinheta de boletim, o NJUD pode não ter o problema.

### 2.2 Questão Crítica a Verificar

**Pergunta:** Os arquivos em `JORNAIS_DIVIDIDOS/` já são cortes limpos (sem vinheta de boletim) ou são o áudio bruto do boletim?

**Como verificar:**
- Se os CABEÇA e CORPO em `JORNAIS_DIVIDIDOS/` são resultados de corte → provavelmente sem vinheta
- Se são o áudio bruto do boletim → mesmo problema do GIRO

**Comando de verificação:**
```bash
# Verificar se JORNAIS_DIVIDIDOS contém arquivos pequenos (cortes) ou grandes (áudio bruto)
ls -lh data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS/2026-09-01/ | head -5
# Arquivos ~2-30s = cortes limpos
# Arquivos ~60s+ = áudio bruto (possível vinheta)
```

---

## 3. ANÁLISE DE DEPENDÊNCIA ENTRE GIRO E NJUD

### 3.1 Compartilhamento de Código

| Componente | Compartilhado? | Observação |
|---|---|---|
| `processar_boletim.py` | ✅ Sim | Ponto de entrada unificado |
| `regras.py` (auditoria) | ✅ Sim | Regras idênticas |
| `separacao_stems.py` | ✅ Sim | Módulo compartilhado |
| `config/planejamento_2026/` | ✅ Sim | 34 JSONs (28 GIRO + 6 NJUD) |
| `divisor_boletins/audio.py` | ✅ Sim | Corte unificado |
| `src/giro/montagem.py` | ❌ Não | Apenas GIRO |
| `assets/vinhetas/giro/` | ❌ Não | Apenas GIRO |
| `assets/vinhetas/njud/` | ❌ Não | Apenas NJUD |

### 3.2 Consequências

- **Corrigir `processar_boletim.py` afeta GIRO e NJUD simultaneamente**
- **Habilitar stems em `config/planejamento_2026/giro_*.json` NÃO afeta NJUD**
- **Montagem é independente:** GIRO usa `src/giro/montagem.py`, NJUD usa `divisor_boletins.montagem`
- **Vinhetas são isoladas:** cada programa tem seu próprio diretório de assets

---

## 4. VERIFICAÇÕES NECESSÁRIAS PARA NJUD

### 4.1 Checklist

- [ ] Confirmar `usar_separacao_stems` nos JSONs de planejamento NJUD
- [ ] Verificar se `JORNAIS_DIVIDIDOS/` contém cortes limpos ou áudio bruto
- [ ] Confirmar que `data/output/JORNAIS_FINAL/` contém 75 .mp3s sem vinheta de boletim
- [ ] Verificar se os NJUDs atuais têm estrutura correta (abertura → cabeça → efeito → corpo → encerramento)
- [ ] Testar um NJUD: reproduzir e confirmar que NÃO tem vinheta de boletim

### 4.2 Comandos de Verificação

```bash
# Verificar JSONs de planejamento NJUD
grep -r "usar_separacao_stems" config/planejamento_2026/njud*.json 2>/dev/null || echo "No NJUD JSONs found"

# Verificar JORNAIS_DIVIDIDOS
ls -lh data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS/2026-09-01/ | head -5

# Verificar NJUDs existentes
ls -lh data/output/JORNAIS_FINAL/ | head -5

# Verificar estrutura de um NJUD específico
python -c "
from pydub import AudioSegment
audio = AudioSegment.from_file('data/output/JORNAIS_FINAL/<arquivo>.mp3')
print(f'Duração: {len(audio)/1000:.1f}s')
print(f'Channels: {audio.channels}')
"
```

### 4.3 Ação Condicional

**Se JORNAIS_DIVIDIDOS são cortes limpos:**
- NJUD NÃO tem problema de vinheta
- Apenas verificar se está funcionando corretamente
- Nenhuma correção necessária

**Se JORNAIS_DIVIDIDOS são áudio bruto:**
- NJUD tem o mesmo problema do GIRO
- Aplicar correção (Fase 1: habilitar stems)
- Aplicar correção (Fase 2: remover vinheta de boletim)

---

## 5. PROJETO DE CORREÇÃO NJUD

### 5.1 Se NJUD Precisar de Correção

**Arquivos a modificar:**

```
config/planejamento_2026/
└── njud_*.json          ← MODIFICAR: "usar_separacao_stems": true

src/core/processamento/
└── processar_boletim.py ← NÃO MODIFICAR (já funciona para ambos)

src/core/auditoria/
└── regras.py           ← NÃO MODIFICAR (já funciona para ambos)

src/core/stems/
└── separacao_stems.py  ← NÃO MODIFICAR (já funciona para ambos)
```

**Ação:** Mesma abordagem do GIRO — habilitar `usar_separacao_stems: true` nos JSONs NJUD.

### 5.2 Se NJUD Estiver Correto

Nenhuma ação necessária. O NJUD está funcionando corretamente com os 75 .mp3s em `data/output/JORNAIS_FINAL/`.

---

## 6. RESUMO NJUD

| Aspecto | GIRO | NJUD |
|---|---|---|
| Problema de vinheta | ✅ Confirmado | ⚠️ Pendente verificação |
| `usar_separacao_stems` | false (34 JSONs) | ? (verificar) |
| Arquivos no output | 0 (apagado) | 75 (presente) |
| Vinhetas corretas | `assets/vinhetas/giro/` | `assets/vinhetas/njud/` |
| Correção necessária | Sim (3 fases) | Pendente |

---

## 7. ORDEM DE EXECUÇÃO NJUD

```
1. Verificar JSONs de planejamento NJUD (usar_separacao_stems)
   ↓
2. Verificar se JORNAIS_DIVIDIDOS/ são cortes limpos
   ↓
3. Se cortes limpos → NJUD está OK, nenhuma ação
   ↓
4. Se áudio bruto → Aplicar mesma correção do GIRO
   ↓
5. Rebuild NJUD se necessário
```

---

*Fim do projeto de correção NJUD.*
